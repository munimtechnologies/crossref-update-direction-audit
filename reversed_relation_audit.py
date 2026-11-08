# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Crossref reversed-relation audit 2 (date-free).

Crossref records a correction or retraction as a relation on the NOTICE: the notice carries
"update-to" naming the work it updates, and Crossref then shows "updated-by" on that work.
Audit 1 looked for relations whose "notice" was published long before its target. Its hand
sample showed that half of those flags were only print-date artefacts, while the real errors
were mostly REVERSED relations: the original article carries "update-to" pointing at its own
erratum or retraction notice.

This audit finds reversed relations without using dates. A non-self relation of a notice type
is "reversed" when the record carrying update-to has an ordinary title (or a "RETRACTED:" /
"WITHDRAWN:" title, which marks the retracted article itself) while the record it points at is
titled as a notice ("Erratum", "Correction to: ...", "Retraction notice", "...: Retraction").

It also asks OpenAlex (is_retracted) about a sample of reversed retraction-type relations.

No API keys. Sources: api.crossref.org and api.openalex.org.

Usage: python reversed_relation_audit.py --out-dir /out [--max-pages N]
"""
import argparse
import collections
import concurrent.futures
import csv
import datetime
import hashlib
import html
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
UA = "crossref-reversed-relation-audit/2.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
API = "https://api.crossref.org/works"
OPENALEX = "https://api.openalex.org/works"
SELECT = ("DOI,update-to,issued,type,title,publisher,member,is-referenced-by-count,"
          "container-title")

# update types that describe a notice about an earlier work (same set as audit 1)
NOTICE_TYPES = {"erratum", "correction", "corrigendum", "retraction", "partial_retraction",
                "withdrawal", "removal", "expression_of_concern", "addendum", "clarification"}
RETRACTIVE = {"retraction", "partial_retraction", "withdrawal", "removal"}
SLACK_DAYS = 31
TARGET_BATCH = 80
OA_BATCH = 40
OA_SAMPLE = 200
GRADE_N = 40
PART_ROWS = 3000
FALLBACK_CAP = 5000
TARGET_BUDGET_S = 200 * 60
WORKERS = 3
TITLE_KEEP = 400

# any notice word anywhere in a title (same as audit 1)
NOTICE_WORDS = re.compile(
    r"\b(errat(?:um|a)|corrections?|corrigend(?:um|a)|retract(?:ions?|ed)|withdrawn|withdrawal"
    r"|expression of concern|addend(?:um|a)|clarification|notice of)\b")
# a title that IS a notice: starts with a notice word ...
NOTICE_PREFIX = re.compile(
    r"^(?:errat(?:um|a)|corrections?|corrigend(?:um|a)|retraction|notice of retraction"
    r"|withdrawal|(?:editorial )?expression of concern|addend(?:um|a)|author correction"
    r"|publisher correction|publisher'?s note|additions and corrections)\b")
# ... or ends with one after a colon, full stop or dash ("Sample size ...: Retraction")
NOTICE_SUFFIX = re.compile(
    r"[:.\-]\s*(?:errat(?:um|a)|corrections?|corrigend(?:um|a)|retraction(?: notice)?)\s*$")
# the retracted article itself, as Elsevier, Wiley and others retitle it
RETRACTED_MARK = re.compile(r"^(?:retracted|withdrawn)\b|\(retracted(?: article)?\)")


# ---------------------------------------------------------------- pure helpers
def fold(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii").lower()


def norm_doi(d):
    d = str(d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d


def norm_type(t):
    return re.sub(r"[\s\-]+", "_", str(t or "").strip().lower())


def first(v):
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


def clean_title(t):
    """Plain lower-case ASCII title without HTML tags or leading punctuation."""
    s = html.unescape(str(t or ""))
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub("[‐-―− ]", " ", s)   # unicode dashes / nbsp split words
    s = fold(s)
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"^[^a-z0-9]+", "", s)


def notice_titled(t):
    c = clean_title(t)
    return bool(NOTICE_PREFIX.match(c) or NOTICE_SUFFIX.search(c))


def retracted_marked(t):
    return bool(RETRACTED_MARK.search(clean_title(t)))


def plain_title(t):
    c = clean_title(t)
    return bool(c) and not NOTICE_WORDS.search(c)


def direction_class(r_title, t_title):
    """forward / notice_to_notice / reversed_plain / reversed_marked / reversed_other / neither."""
    if notice_titled(r_title):
        return "notice_to_notice" if notice_titled(t_title) else "forward"
    if notice_titled(t_title):
        if plain_title(r_title):
            return "reversed_plain"
        if retracted_marked(r_title):
            return "reversed_marked"
        return "reversed_other"
    return "neither"


REVERSED = ("reversed_plain", "reversed_marked")


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
    """(earliest, latest) date covered by a Crossref date-parts list; None without a year."""
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
    """Audit 1's rule: the record carrying update-to is >slack days older than its target."""
    if not r_rng or not t_rng:
        return None
    return r_rng[1] + datetime.timedelta(days=slack) < t_rng[0]


def relations_of(item):
    r = norm_doi(item.get("DOI"))
    rng = issued_range(item)
    title = first(item.get("title"))[:TITLE_KEEP]
    out = []
    for u in item.get("update-to") or []:
        if not isinstance(u, dict):
            continue
        t = norm_doi(u.get("DOI"))
        out.append({
            "source": r, "target": t, "utype": norm_type(u.get("type")),
            "usource": str(u.get("source") or ""), "self": t == r,
            "r_min": rng[0] if rng else None, "r_max": rng[1] if rng else None,
            "member": str(item.get("member") or ""), "publisher": str(item.get("publisher") or ""),
            "r_cites": _int_or_none(item.get("is-referenced-by-count")) or 0,
            "r_type": str(item.get("type") or ""), "r_title": title,
            "r_container": first(item.get("container-title"))[:80],
        })
    return out


def target_summary(item):
    rng = issued_range(item)
    return {"min": rng[0] if rng else None, "max": rng[1] if rng else None,
            "type": str(item.get("type") or ""), "member": str(item.get("member") or ""),
            "title": first(item.get("title"))[:TITLE_KEEP],
            "cites": _int_or_none(item.get("is-referenced-by-count")) or 0,
            "upd": tuple(sorted({norm_doi(u.get("DOI")) for u in (item.get("update-to") or [])
                                 if isinstance(u, dict)}))}


def batchable(doi):
    return bool(doi) and "," not in doi and "|" not in doi and not re.search(r"\s", doi)


def batch_url(dois, rows):
    f = ",".join("doi:" + urllib.parse.quote(d, safe="/") for d in dois)
    return "%s?filter=%s&rows=%d&select=%s&mailto=%s" % (API, f, rows, SELECT, MAILTO)


def openalex_url(dois):
    f = "|".join(urllib.parse.quote("https://doi.org/" + d, safe="/:") for d in dois)
    return "%s?filter=doi:%s&select=doi,is_retracted&per-page=50&mailto=%s" % (OPENALEX, f, MAILTO)


def parse_openalex(body):
    """{doi: is_retracted} from an OpenAlex list response (True if any matching work is)."""
    out = {}
    for w in (json.loads(body.decode("utf-8")).get("results") or []):
        d = norm_doi(w.get("doi"))
        if d:
            out[d] = bool(out.get(d)) or bool(w.get("is_retracted"))
    return out


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def rate(num, den):
    return (num / den) if den else None


def compute_predictions(s):
    """Mechanical predictions fixed in PREREG.md (R4 is hand-graded)."""
    def holds(c):
        return None if c is None else bool(c)

    g = s["complete"] and s["n_records"] >= 450000 and (s["coverage"] or 0) >= 0.95
    r2 = None
    if s["n_rev_dated"] >= 20:
        r2 = s["n_rev_not_predating"] / s["n_rev_dated"] >= 0.40
    r3 = None
    if s["n_reversed"]:
        r3 = s["n_rev_members"] >= 25 and s["top_member_share"] < 0.5
    r5 = None
    if s["oa_n_source"] >= 20:
        r5 = s["oa_source_not_retracted"] / s["oa_n_source"] >= 0.10
    return {"G": holds(g), "R1": holds(s["n_reversed"] >= 1500), "R2": holds(r2),
            "R3": holds(r3), "R4": "hand-graded (grade_reversed40.csv)", "R5": holds(r5)}


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


def fetch_notices(max_pages):
    rels, n, cursor, complete, total = [], 0, "*", False, None
    for page in range(max_pages):
        url = ("%s?filter=is-update:true&rows=500&select=%s&mailto=%s&cursor=%s"
               % (API, SELECT, MAILTO, urllib.parse.quote(cursor, safe="")))
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
            rels.extend(relations_of(it))
            n += 1
        cursor = msg.get("next-cursor") or ""
        if not cursor:
            complete = True
            break
        if page % 20 == 0:
            print("records: %d after page %d (total %s)" % (n, page + 1, total), flush=True)
    return rels, n, complete, total


def lookup_batch(dois):
    st, body = http_get(batch_url(dois, len(dois) + 5))
    if st != 200:
        return None
    try:
        items = (json.loads(body.decode("utf-8")).get("message") or {}).get("items") or []
    except ValueError:
        return None
    return {norm_doi(it.get("DOI")): target_summary(it) for it in items}


def lookup_one(doi):
    st, body = http_get("%s/%s?mailto=%s" % (API, urllib.parse.quote(doi, safe="/"), MAILTO))
    if st != 200:
        return st, None
    try:
        return st, target_summary(json.loads(body.decode("utf-8")).get("message") or {})
    except Exception:
        return -2, None


def openalex_lookup(dois):
    """{doi: is_retracted} for DOIs OpenAlex knows; failed batches are counted, not retried."""
    out, failed = {}, 0
    ok = sorted({d for d in dois if batchable(d)})
    for i in range(0, len(ok), OA_BATCH):
        st, body = http_get(openalex_url(ok[i:i + OA_BATCH]))
        if st != 200:
            failed += 1
            continue
        try:
            out.update(parse_openalex(body))
        except Exception:
            failed += 1
    return out, failed


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# ---------------------------------------------------------------- main
REL_FIELDS = ["source", "target", "utype", "usource", "direction", "v1_category", "r_min", "r_max",
              "t_min", "t_max", "member", "publisher", "r_type", "r_cites", "r_title",
              "r_container", "t_type", "t_member", "t_cites", "t_title", "mutual"]


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

    rels, n_records, complete, total = fetch_notices(a.max_pages)
    print("records %d (total-results %s), relations %d, complete=%s"
          % (n_records, total, len(rels), complete), flush=True)

    need = sorted({r["target"] for r in rels if not r["self"] and r["utype"] in NOTICE_TYPES
                   and r["target"]})
    targets, failed_batches, skipped = {}, 0, 0
    batch_list = list(chunks([d for d in need if batchable(d)], TARGET_BATCH))
    singles = [d for d in need if not batchable(d)]

    def run_batch(b):
        if time.monotonic() - t0 > TARGET_BUDGET_S:
            return "skipped", b, None
        res = lookup_batch(b)
        return ("ok" if res is not None else "failed"), b, res

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for status, b, res in ex.map(run_batch, batch_list):
            done += 1
            if status == "ok":
                targets.update(res)
            elif status == "failed":
                failed_batches += 1
                singles.extend(b)
            else:
                skipped += 1
            if done % 500 == 0:
                print("target batches %d/%d, found %d" % (done, len(batch_list), len(targets)),
                      flush=True)
    missing = sorted(set(need) - set(targets), key=lambda d: sha_key("fb", d))
    fallback = sorted(set(singles) | set(missing[:FALLBACK_CAP]), key=lambda d: sha_key("fb", d))
    fb_status = collections.Counter()

    def run_one(d):
        if time.monotonic() - t0 > TARGET_BUDGET_S + 20 * 60:
            return d, "skipped", None
        st, meta = lookup_one(d)
        return d, st, meta

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for d, st, meta in ex.map(run_one, fallback):
            fb_status[str(st)] += 1
            if meta is not None:
                targets[d] = meta
    print("targets needed %d, found %d" % (len(need), len(targets)), flush=True)

    # classify non-self notice-type relations whose target was found
    judged = []
    for r in rels:
        if r["self"] or r["utype"] not in NOTICE_TYPES:
            continue
        tgt = targets.get(r["target"])
        if tgt is None:
            continue
        r["t_min"], r["t_max"] = tgt["min"], tgt["max"]
        r["t_type"], r["t_member"], r["t_cites"], r["t_title"] = (
            tgt["type"], tgt["member"], tgt["cites"], tgt["title"])
        r["mutual"] = r["source"] in tgt["upd"]
        r["direction"] = direction_class(r["r_title"], tgt["title"])
        p = predates((r["r_min"], r["r_max"]) if r["r_min"] else None,
                     (tgt["min"], tgt["max"]) if tgt["min"] else None)
        r["v1_category"] = "undated" if p is None else ("predates" if p else "ok")
        judged.append(r)
    rev = [r for r in judged if r["direction"] in REVERSED]

    # OpenAlex: reversed retraction-type relations (sample) and a forward control sample
    rev_retr = sorted([r for r in rev if r["utype"] in RETRACTIVE],
                      key=lambda r: sha_key("oa", r["source"], r["target"]))[:OA_SAMPLE]
    fwd_retr = sorted([r for r in judged if r["direction"] == "forward" and r["utype"] in RETRACTIVE],
                      key=lambda r: sha_key("oa", r["source"], r["target"]))[:OA_SAMPLE]
    oa_dois = set()
    for r in rev_retr + fwd_retr:
        oa_dois.add(r["source"])
        oa_dois.add(r["target"])
    oa, oa_failed = openalex_lookup(sorted(oa_dois))
    for r in rev_retr + fwd_retr:
        r["oa_source_retracted"] = oa.get(r["source"], "")
        r["oa_target_retracted"] = oa.get(r["target"], "")

    def oa_counts(rows, key, want):
        known = [r for r in rows if r[key] != ""]
        return len(known), sum(1 for r in known if r[key] is want)

    oa_ns, oa_s_false = oa_counts(rev_retr, "oa_source_retracted", False)
    oa_nt, oa_t_true = oa_counts(rev_retr, "oa_target_retracted", True)
    c_ns, c_s_true = oa_counts(fwd_retr, "oa_source_retracted", True)
    c_nt, c_t_true = oa_counts(fwd_retr, "oa_target_retracted", True)

    # outputs
    rev_sorted = sorted(rev, key=lambda r: (r["publisher"], -int(r["r_cites"] or 0), r["source"]))
    for i, part in enumerate(chunks(rev_sorted, PART_ROWS)):
        write_csv(os.path.join(a.out_dir, "reversed_part%02d.csv" % (i + 1)), part, REL_FIELDS)
    top = sorted(rev, key=lambda r: -int(r["r_cites"] or 0))[:300]
    write_csv(os.path.join(a.out_dir, "reversed_top300_by_citations.csv"), top, REL_FIELDS)
    grade = sorted(rev, key=lambda r: sha_key("g2", r["source"], r["target"]))[:GRADE_N]
    write_csv(os.path.join(a.out_dir, "grade_reversed40.csv"), grade, REL_FIELDS + ["grade", "note"])
    other = sorted([r for r in judged if r["direction"] == "reversed_other"],
                   key=lambda r: sha_key("ro", r["source"], r["target"]))[:200]
    write_csv(os.path.join(a.out_dir, "reversed_other_sample200.csv"), other, REL_FIELDS)
    oa_fields = REL_FIELDS + ["oa_source_retracted", "oa_target_retracted"]
    write_csv(os.path.join(a.out_dir, "openalex_reversed_retractions.csv"), rev_retr, oa_fields)
    write_csv(os.path.join(a.out_dir, "openalex_forward_control.csv"), fwd_retr, oa_fields)

    per = collections.defaultdict(collections.Counter)
    for r in judged:
        k = (r["member"], r["publisher"])
        per[k]["judged"] += 1
        per[k][r["direction"]] += 1
    mem_rows = []
    for (m, p), c in per.items():
        nrev = c["reversed_plain"] + c["reversed_marked"]
        mem_rows.append({"member": m, "publisher": p, "judged": c["judged"],
                         "reversed_plain": c["reversed_plain"],
                         "reversed_marked": c["reversed_marked"],
                         "reversed_other": c["reversed_other"], "forward": c["forward"],
                         "rate": round(rate(nrev, c["judged"]) or 0, 6)})
    mem_rows.sort(key=lambda x: (-(x["reversed_plain"] + x["reversed_marked"]), -x["judged"]))
    write_csv(os.path.join(a.out_dir, "member_table.csv"), mem_rows,
              ["member", "publisher", "judged", "reversed_plain", "reversed_marked",
               "reversed_other", "forward", "rate"])

    # statistics
    need_set = set(need)
    covered = sum(1 for d in need_set if d in targets)
    by_member = collections.Counter(r["member"] for r in rev)
    rev_dated = [r for r in rev if r["v1_category"] in ("predates", "ok")]
    # notices that Crossref shows as retracted only because an original points at them
    notice_retracted_by_reversal = sorted({r["target"] for r in rev if r["utype"] in RETRACTIVE})
    s = {
        "complete": complete, "n_records": n_records, "coverage": rate(covered, len(need_set)),
        "n_reversed": len(rev), "n_rev_dated": len(rev_dated),
        "n_rev_not_predating": sum(1 for r in rev_dated if r["v1_category"] == "ok"),
        "n_rev_members": len(by_member),
        "top_member_share": (by_member.most_common(1)[0][1] / len(rev)) if rev else None,
        "oa_n_source": oa_ns, "oa_source_not_retracted": oa_s_false,
    }
    pred = compute_predictions(s)
    summary = dict(s)
    summary.update({
        "total_results_reported": total, "relations": len(rels), "judged": len(judged),
        "directions": dict(collections.Counter(r["direction"] for r in judged).most_common()),
        "reversed_by_type": {d: dict(collections.Counter(r["utype"] for r in rev
                                                         if r["direction"] == d).most_common())
                             for d in REVERSED},
        "reversed_by_source": dict(collections.Counter(r["usource"] for r in rev).most_common()),
        "reversed_by_v1_category": dict(collections.Counter(r["v1_category"] for r in rev)),
        "reversed_mutual": sum(1 for r in rev if r["mutual"]),
        "reversed_by_member_top25": [[m, n] for m, n in by_member.most_common(25)],
        "reversed_by_prefix_top25": collections.Counter(r["source"].split("/")[0]
                                                        for r in rev).most_common(25),
        "reversed_by_decade": dict(sorted(collections.Counter(
            (r["r_max"].year // 10 * 10) for r in rev if r["r_max"]).items())),
        "reversed_sources_10plus_cites": sum(1 for r in rev if (r["r_cites"] or 0) >= 10),
        "reversed_sources_100plus_cites": sum(1 for r in rev if (r["r_cites"] or 0) >= 100),
        "distinct_reversed_sources": len({r["source"] for r in rev}),
        "notices_shown_retracted_by_reversal": len(notice_retracted_by_reversal),
        "self_relations_retractive": sum(1 for r in rels if r["self"] and r["utype"] in RETRACTIVE),
        "openalex": {"reversed_sampled": len(rev_retr), "reversed_source_known": oa_ns,
                     "reversed_source_not_retracted": oa_s_false,
                     "reversed_target_known": oa_nt, "reversed_target_retracted": oa_t_true,
                     "control_sampled": len(fwd_retr), "control_source_known": c_ns,
                     "control_source_(notice)_retracted": c_s_true,
                     "control_target_known": c_nt, "control_target_retracted": c_t_true,
                     "failed_batches": oa_failed},
        "targets_needed": len(need), "targets_found": len(targets),
        "target_failed_batches": failed_batches, "target_skipped_batches": skipped,
        "fallback_status": dict(fb_status),
        "predictions": pred, "http": dict(STATS), "elapsed_s": round(time.monotonic() - t0, 1),
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: summary[k] for k in ("n_records", "judged", "directions", "n_reversed",
                                              "predictions")}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
