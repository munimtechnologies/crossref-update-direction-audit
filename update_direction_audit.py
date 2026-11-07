# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Crossref update-direction audit 1.

Crossref records corrections, retractions and other editorial updates as a relation on the
NOTICE: the notice's record carries "update-to" naming the work it updates, and Crossref then
shows "updated-by" on that work. A notice cannot be published before the work it corrects.

This script reads every Crossref record that carries "update-to" (filter is-update:true),
looks up each target it names, and counts relations of notice types (erratum, correction,
retraction, ...) in which the "notice" was published more than 31 days BEFORE the work it
claims to update. Those relations point the wrong way, or at the wrong work.

For those "predating" relations it also reads the target's reference list and asks whether the
target cites the "notice" (the pattern seen in Nature records before this audit was written).

No API keys. Source: api.crossref.org only.

Usage: python update_direction_audit.py --out-dir /out [--max-pages N]
"""
import argparse
import collections
import concurrent.futures
import csv
import datetime
import gzip
import hashlib
import json
import os
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

MAILTO = "mv2@munimtech.com"
UA = "crossref-update-direction-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
API = "https://api.crossref.org/works"
NOTICE_SELECT = ("DOI,update-to,issued,type,title,publisher,member,is-referenced-by-count,"
                 "container-title")
TARGET_SELECT = NOTICE_SELECT
REF_SELECT = "DOI,reference"

# update types that describe a notice about an earlier work (fixed in PREREG.md)
NOTICE_TYPES = {"erratum", "correction", "corrigendum", "retraction", "partial_retraction",
                "withdrawal", "removal", "expression_of_concern", "addendum", "clarification"}
SLACK_DAYS = 31
SPRINGER_MEMBER = "297"
TARGET_BATCH = 80
REF_BATCH = 20
CITE_CAP = 6000
FALLBACK_CAP = 5000
GRADE_N = 40
TARGET_BUDGET_S = 200 * 60     # stop starting new target lookups after this much run time
CITE_BUDGET_S = 245 * 60       # stop starting reference lookups after this much run time
WORKERS = 3

NOTICE_WORDS = re.compile(
    r"\b(errat(?:um|a)|correction|corrigend(?:um|a)|retract(?:ion|ed)|withdrawn|withdrawal"
    r"|expression of concern|addend(?:um|a)|clarification|notice of)\b")


# ---------------------------------------------------------------- pure helpers
def fold(s):
    """ASCII-folded lower-case text."""
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii").lower()


def norm_doi(d):
    return str(d or "").strip().lower()


def norm_type(t):
    return re.sub(r"[\s\-]+", "_", str(t or "").strip().lower())


def first(v):
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


def _last_day(y, m):
    if m == 12:
        return 31
    return (datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)).day


def _int_or_none(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def date_range(parts):
    """(earliest, latest) date covered by a Crossref date-parts list such as [2004, 8].

    Invalid months or days fall back to the coarser precision. None when there is no year."""
    if not isinstance(parts, (list, tuple)) or not parts:
        return None
    y = _int_or_none(parts[0])
    if y is None or y < 1000 or y > 2100:
        return None
    m = _int_or_none(parts[1]) if len(parts) > 1 else None
    if m is not None and not 1 <= m <= 12:
        m = None
    d = _int_or_none(parts[2]) if (m is not None and len(parts) > 2) else None
    if d is not None and not 1 <= d <= _last_day(y, m):
        d = None
    if m is None:
        return (datetime.date(y, 1, 1), datetime.date(y, 12, 31))
    if d is None:
        return (datetime.date(y, m, 1), datetime.date(y, m, _last_day(y, m)))
    day = datetime.date(y, m, d)
    return (day, day)


def issued_range(item):
    dp = ((item or {}).get("issued") or {}).get("date-parts") or [[None]]
    return date_range(dp[0] if dp else None)


def predates(r_rng, t_rng, slack=SLACK_DAYS):
    """True if the notice certainly appeared more than `slack` days before the target."""
    if not r_rng or not t_rng:
        return None
    return r_rng[1] + datetime.timedelta(days=slack) < t_rng[0]


def notice_like_title(title):
    return bool(NOTICE_WORDS.search(fold(title)))


def relations_of(item):
    """One row per update-to entry of a Crossref record."""
    r = norm_doi(item.get("DOI"))
    rng = issued_range(item)
    title = first(item.get("title"))
    out = []
    for u in item.get("update-to") or []:
        if not isinstance(u, dict):
            continue
        t = norm_doi(u.get("DOI"))
        out.append({
            "notice": r, "target": t, "utype": norm_type(u.get("type")),
            "usource": str(u.get("source") or ""), "self": t == r,
            "r_min": rng[0] if rng else None, "r_max": rng[1] if rng else None,
            "member": str(item.get("member") or ""), "publisher": str(item.get("publisher") or ""),
            "r_cites": _int_or_none(item.get("is-referenced-by-count")) or 0,
            "r_type": str(item.get("type") or ""), "r_title": title[:150],
            "r_container": first(item.get("container-title"))[:80],
            "r_notice_title": notice_like_title(title),
        })
    return out


def target_summary(item):
    rng = issued_range(item)
    return {"min": rng[0] if rng else None, "max": rng[1] if rng else None,
            "type": str(item.get("type") or ""), "member": str(item.get("member") or ""),
            "title": first(item.get("title"))[:150],
            "cites": _int_or_none(item.get("is-referenced-by-count")) or 0,
            "upd": tuple(sorted({norm_doi(u.get("DOI")) for u in (item.get("update-to") or [])
                                 if isinstance(u, dict)}))}


def classify(rel, tgt):
    """self / other_type / target_missing / undated / predates / ok."""
    if rel["self"]:
        return "self"
    if rel["utype"] not in NOTICE_TYPES:
        return "other_type"
    if tgt is None:
        return "target_missing"
    r_rng = (rel["r_min"], rel["r_max"]) if rel["r_min"] else None
    t_rng = (tgt["min"], tgt["max"]) if tgt.get("min") else None
    p = predates(r_rng, t_rng)
    if p is None:
        return "undated"
    return "predates" if p else "ok"


def batchable(doi):
    return bool(doi) and "," not in doi and not re.search(r"\s", doi)


def batch_url(dois, select, rows):
    f = ",".join("doi:" + urllib.parse.quote(d, safe="/") for d in dois)
    return "%s?filter=%s&rows=%d&select=%s&mailto=%s" % (API, f, rows, select, MAILTO)


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def rate(num, den):
    return (num / den) if den else None


def median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2


def compute_predictions(s):
    """Mechanical predictions fixed in PREREG.md (P4 is hand-graded)."""
    def holds(c):
        return None if c is None else bool(c)

    g = holds(s["complete"] and s["n_records"] >= 450000 and (s["coverage"] or 0) >= 0.90)
    r297, roth = s["rate_297"], s["rate_other"]
    p3 = None
    if r297 is not None and roth is not None:
        p3 = (r297 >= 3 * roth) if roth > 0 else (r297 > 0)
    p5 = None
    if s["n_pred_refs"] >= 20:
        p5 = s["n_pred_cites"] / s["n_pred_refs"] >= 0.5
    p6 = None
    if s["share10_pred"] is not None and s["share10_ok"] is not None:
        p6 = (s["share10_pred"] >= 5 * s["share10_ok"]) if s["share10_ok"] > 0 else (s["share10_pred"] > 0)
    p7 = None
    if s["n_1038"] >= 20:
        p7 = s["n_1038_pre2010"] / s["n_1038"] >= 0.8
    return {
        "G": g,
        "P1": holds(s["n_predates"] >= 500),
        "P2": holds(None if not s["n_predates"] else s["n_predates_297"] / s["n_predates"] >= 0.5),
        "P3": holds(p3),
        "P4": "hand-graded (grade_predates40.csv)",
        "P5": holds(p5),
        "P6": holds(p6),
        "P7": holds(p7),
    }


# ---------------------------------------------------------------- network
class Pacer:
    def __init__(self, per_second):
        self.gap = 1.0 / per_second
        self.lock = threading.Lock()
        self.next = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        d = t - time.monotonic()
        if d > 0:
            time.sleep(d)


PACE = Pacer(3)
STATS = collections.Counter()
STATS_LOCK = threading.Lock()


def _stat(k):
    with STATS_LOCK:
        STATS[k] += 1


def http_get(url, tries=6, timeout=120):
    """(status, body). 400/404/410 definitive; -1 = network failure."""
    delay = 5
    last = -1
    for _ in range(tries):
        PACE.wait()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                _stat("http_%d" % r.status)
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = e.code
            _stat("http_%d" % e.code)
            if e.code in (400, 404, 410):
                return e.code, b""
            if e.code in (403, 429) or e.code >= 500:
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            return e.code, b""
        except Exception:
            _stat("http_neterr")
            time.sleep(delay)
            delay = min(delay * 2, 120)
    return last, b""


def fetch_notices(max_pages, raw_path):
    rels, n, cursor, complete, total = [], 0, "*", False, None
    with gzip.open(raw_path, "wt", encoding="utf-8") as raw:
        for page in range(max_pages):
            url = ("%s?filter=is-update:true&rows=500&select=%s&mailto=%s&cursor=%s"
                   % (API, NOTICE_SELECT, MAILTO, urllib.parse.quote(cursor, safe="")))
            st, body = http_get(url)
            if st != 200:
                print("notice page %d failed: %s" % (page, st), file=sys.stderr, flush=True)
                break
            try:
                msg = json.loads(body.decode("utf-8")).get("message") or {}
            except ValueError:
                print("notice page %d: bad JSON" % page, file=sys.stderr, flush=True)
                break
            total = msg.get("total-results", total)
            batch = msg.get("items") or []
            if not batch:
                complete = True
                break
            for it in batch:
                raw.write(json.dumps(it, ensure_ascii=False) + "\n")
                rels.extend(relations_of(it))
                n += 1
            cursor = msg.get("next-cursor") or ""
            if not cursor:
                complete = True
                break
            if page % 20 == 0:
                print("notices: %d records after page %d (total %s)" % (n, page + 1, total), flush=True)
    return rels, n, complete, total


def lookup_batch(dois):
    """{doi: summary} for the DOIs Crossref returns; None if the call failed."""
    st, body = http_get(batch_url(dois, TARGET_SELECT, len(dois) + 5))
    if st != 200:
        return None
    try:
        items = (json.loads(body.decode("utf-8")).get("message") or {}).get("items") or []
    except ValueError:
        return None
    out = {}
    for it in items:
        out[norm_doi(it.get("DOI"))] = target_summary(it)
    return out


def lookup_one(doi):
    st, body = http_get("%s/%s?mailto=%s" % (API, urllib.parse.quote(doi, safe="/"), MAILTO))
    if st != 200:
        return st, None
    try:
        return st, target_summary(json.loads(body.decode("utf-8")).get("message") or {})
    except Exception:
        return -2, None


def refs_batch(dois):
    """{doi: set of reference DOIs} (empty set = no references deposited); None on failure."""
    st, body = http_get(batch_url(dois, REF_SELECT, len(dois) + 5))
    if st != 200:
        return None
    try:
        items = (json.loads(body.decode("utf-8")).get("message") or {}).get("items") or []
    except ValueError:
        return None
    out = {}
    for it in items:
        out[norm_doi(it.get("DOI"))] = {norm_doi(r.get("DOI")) for r in (it.get("reference") or [])
                                        if isinstance(r, dict) and r.get("DOI")}
    return out


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# ---------------------------------------------------------------- main
REL_FIELDS = ["notice", "target", "utype", "usource", "category", "r_min", "r_max", "t_min",
              "t_max", "gap_days", "member", "publisher", "r_type", "r_cites", "r_notice_title",
              "r_title", "r_container", "t_type", "t_member", "t_cites", "t_title", "mutual",
              "t_has_refs", "t_cites_r"]


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-pages", type=int, default=2000)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()

    rels, n_records, complete, total = fetch_notices(
        a.max_pages, os.path.join(a.out_dir, "update_records_raw.jsonl.gz"))
    print("records %d (total-results %s), relations %d, complete=%s"
          % (n_records, total, len(rels), complete), flush=True)

    # targets of non-self notice-type relations
    need = sorted({r["target"] for r in rels if not r["self"] and r["utype"] in NOTICE_TYPES
                   and r["target"]})
    targets, failed_batches = {}, 0
    lock = threading.Lock()
    batch_list = list(chunks([d for d in need if batchable(d)], TARGET_BATCH))
    singles = [d for d in need if not batchable(d)]

    def run_batch(b):
        if time.monotonic() - t0 > TARGET_BUDGET_S:
            return "skipped", b
        res = lookup_batch(b)
        return ("ok" if res is not None else "failed"), (b, res)

    done, skipped_batches = 0, 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for status, payload in ex.map(run_batch, batch_list):
            done += 1
            if status == "ok":
                b, res = payload
                with lock:
                    targets.update(res)
            elif status == "failed":
                failed_batches += 1
                singles.extend(payload[0])
            else:
                skipped_batches += 1
            if done % 500 == 0:
                print("target batches: %d/%d, found %d" % (done, len(batch_list), len(targets)), flush=True)
    missing = sorted((set(need) - set(targets)), key=lambda d: sha_key("fb", d))
    fallback = sorted(set(singles) | set(missing[:FALLBACK_CAP]), key=lambda d: sha_key("fb", d))
    fb_status = collections.Counter()

    def run_one(d):
        if time.monotonic() - t0 > TARGET_BUDGET_S + 20 * 60:
            return d, "skipped", None
        st, meta = lookup_one(d)
        return d, st, meta

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for d, st, meta in ex.map(run_one, fallback[:FALLBACK_CAP + len(singles)]):
            fb_status[str(st)] += 1
            if meta is not None:
                targets[d] = meta
    print("targets needed %d, found %d, fallback %s" % (len(need), len(targets), dict(fb_status)),
          flush=True)

    # classify
    for r in rels:
        tgt = targets.get(r["target"]) if r["target"] else None
        r["category"] = classify(r, tgt)
        if tgt is not None:
            r["t_min"], r["t_max"] = tgt["min"], tgt["max"]
            r["t_type"], r["t_member"], r["t_cites"], r["t_title"] = (
                tgt["type"], tgt["member"], tgt["cites"], tgt["title"])
            r["mutual"] = r["notice"] in tgt["upd"]
            if r["r_max"] and tgt["min"]:
                r["gap_days"] = (tgt["min"] - r["r_max"]).days
    pred_rows = [r for r in rels if r["category"] == "predates"]
    ok_rows = [r for r in rels if r["category"] == "ok"]

    # does the target cite the "notice"?
    cite_order = sorted(pred_rows, key=lambda r: sha_key(r["notice"], r["target"]))[:CITE_CAP]
    cite_targets = sorted({r["target"] for r in cite_order if batchable(r["target"])})
    refmap = {}

    def run_refs(b):
        if time.monotonic() - t0 > CITE_BUDGET_S:
            return None
        return refs_batch(b)

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for res in ex.map(run_refs, list(chunks(cite_targets, REF_BATCH))):
            if res:
                refmap.update(res)
    for r in pred_rows:
        refs = refmap.get(r["target"])
        if refs is None:
            r["t_has_refs"], r["t_cites_r"] = "", ""
        else:
            r["t_has_refs"] = bool(refs)
            r["t_cites_r"] = (r["notice"] in refs) if refs else ""

    # outputs
    pred_sorted = sorted(pred_rows, key=lambda r: (r["publisher"], r["notice"], r["target"]))
    write_csv(os.path.join(a.out_dir, "predates.csv"), pred_sorted, REL_FIELDS)
    grade = sorted(pred_rows, key=lambda r: sha_key(r["notice"], r["target"]))[:GRADE_N]
    write_csv(os.path.join(a.out_dir, "grade_predates40.csv"), grade, REL_FIELDS + ["grade", "note"])
    top = sorted(pred_rows, key=lambda r: -int(r["r_cites"] or 0))[:200]
    write_csv(os.path.join(a.out_dir, "predates_top200_by_citations.csv"), top, REL_FIELDS)
    miss = [r for r in rels if r["category"] == "target_missing"]
    write_csv(os.path.join(a.out_dir, "target_missing_sample.csv"),
              sorted(miss, key=lambda r: sha_key(r["notice"], r["target"]))[:300], REL_FIELDS)

    per_pub = collections.defaultdict(collections.Counter)
    for r in rels:
        if r["category"] in ("predates", "ok"):
            per_pub[(r["member"], r["publisher"])][r["category"]] += 1
    pub_rows = []
    for (m, p), c in per_pub.items():
        den = c["predates"] + c["ok"]
        pub_rows.append({"member": m, "publisher": p, "dated_relations": den,
                         "predates": c["predates"], "rate": round(rate(c["predates"], den) or 0, 6)})
    pub_rows.sort(key=lambda x: (-x["predates"], -x["dated_relations"]))
    write_csv(os.path.join(a.out_dir, "publisher_table.csv"), pub_rows,
              ["member", "publisher", "dated_relations", "predates", "rate"])

    self_c = collections.Counter((r["publisher"], r["utype"], r["usource"]) for r in rels if r["self"])
    write_csv(os.path.join(a.out_dir, "self_relations.csv"),
              [{"publisher": k[0], "utype": k[1], "usource": k[2], "n": v}
               for k, v in self_c.most_common()], ["publisher", "utype", "usource", "n"])

    # statistics for the predictions
    dated = pred_rows + ok_rows
    d297 = [r for r in dated if r["member"] == SPRINGER_MEMBER]
    doth = [r for r in dated if r["member"] != SPRINGER_MEMBER]
    p297 = sum(1 for r in d297 if r["category"] == "predates")
    poth = sum(1 for r in doth if r["category"] == "predates")
    with_refs = [r for r in pred_rows if r.get("t_has_refs") is True]
    cites = sum(1 for r in with_refs if r.get("t_cites_r") is True)
    s10p = rate(sum(1 for r in pred_rows if (r["r_cites"] or 0) >= 10), len(pred_rows))
    s10o = rate(sum(1 for r in ok_rows if (r["r_cites"] or 0) >= 10), len(ok_rows))
    r1038 = [r for r in pred_rows if r["notice"].startswith("10.1038/")]
    r1038_old = [r for r in r1038 if r["r_max"] and r["r_max"] < datetime.date(2010, 1, 1)]
    need_set = set(need)
    covered = sum(1 for d in need_set if d in targets and targets[d]["min"])
    s = {
        "complete": complete, "n_records": n_records, "coverage": rate(covered, len(need_set)),
        "n_predates": len(pred_rows), "n_predates_297": p297,
        "rate_297": rate(p297, len(d297)), "rate_other": rate(poth, len(doth)),
        "n_pred_refs": len(with_refs), "n_pred_cites": cites,
        "share10_pred": s10p, "share10_ok": s10o,
        "n_1038": len(r1038), "n_1038_pre2010": len(r1038_old),
    }
    pred = compute_predictions(s)
    summary = dict(s)
    summary.update({
        "total_results_reported": total, "relations": len(rels),
        "categories": dict(collections.Counter(r["category"] for r in rels)),
        "utypes_all": dict(collections.Counter(r["utype"] for r in rels).most_common()),
        "predates_by_utype": dict(collections.Counter(r["utype"] for r in pred_rows).most_common()),
        "predates_by_source": dict(collections.Counter(r["usource"] for r in pred_rows).most_common()),
        "predates_by_publisher": collections.Counter(r["publisher"] for r in pred_rows).most_common(25),
        "predates_by_prefix": collections.Counter(r["notice"].split("/")[0] for r in pred_rows).most_common(25),
        "predates_by_notice_decade": dict(sorted(collections.Counter(
            (r["r_max"].year // 10 * 10) for r in pred_rows if r["r_max"]).items())),
        "predates_notice_like_title": sum(1 for r in pred_rows if r["r_notice_title"]),
        "ok_notice_like_title": sum(1 for r in ok_rows if r["r_notice_title"]),
        "predates_mutual": sum(1 for r in pred_rows if r.get("mutual")),
        "predates_gap_days_median": median([r["gap_days"] for r in pred_rows
                                            if r.get("gap_days") is not None]),
        "n_dated_297": len(d297), "n_dated_other": len(doth),
        "targets_needed": len(need), "targets_found": len(targets), "targets_dated": covered,
        "target_failed_batches": failed_batches, "target_skipped_batches": skipped_batches,
        "fallback_status": dict(fb_status),
        "cite_targets_checked": len(refmap), "self_relations": sum(self_c.values()),
        "predictions": pred, "http": dict(STATS), "elapsed_s": round(time.monotonic() - t0, 1),
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: summary[k] for k in ("n_records", "relations", "categories", "n_predates",
                                              "predictions")}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
