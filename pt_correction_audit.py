# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Crossref update-direction audit 3: Physics Today correction links.

In Crossref, a correction notice carries "update-to" naming the work it corrects. A notice
cannot correct an item printed in a LATER issue. Audit 1 found 303 Physics Today relations whose
notice is dated more than a month before its target. Reading a few by hand (PREREG-3.md) showed
single-page "Corrections" columns from the 2007-2008 back-file deposit carrying 10-20 targets
each, some of them printed months after the column.

This audit reads every Physics Today record with update-to, looks up every target, and orders
notice and target by (volume, issue), with the issued date only as a fallback and as a second
definition. It compares back-file notices (deposited 2+ years after print) with notices deposited
when they were printed, and, as a control, AIP Publishing's other journals.

No API keys. Source: api.crossref.org only.

Usage: python pt_correction_audit.py --out-dir /out [--max-pages N]
"""
import argparse
import collections
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
UA = "crossref-pt-correction-audit/3.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
API = "https://api.crossref.org/works"
SELECT = ("DOI,update-to,issued,created,volume,issue,page,title,type,member,container-title,"
          "ISSN,is-referenced-by-count")
PT_ISSNS = {"0031-9228", "1945-0699"}
PT_FILTER = "is-update:true,issn:0031-9228"
AIP_FILTER = "is-update:true,member:317"
NOTICE_TYPES = {"erratum", "correction", "corrigendum", "retraction", "partial_retraction",
                "withdrawal", "removal", "expression_of_concern", "addendum", "clarification"}
SLACK_DAYS = 31
BATCH = 60
FALLBACK_CAP = 300
GRADE_N = 20
JUDGED = ("later", "same_issue", "earlier")


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


def clean_text(s):
    s = html.unescape(str(s or ""))
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _int_or_none(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _last_day(y, m):
    if m == 12:
        return 31
    return (datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)).day


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


def created_date(item):
    s = str(((item or {}).get("created") or {}).get("date-time") or "")[:10]
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def strict_int(v):
    s = str(v if v is not None else "").strip()
    return int(s) if re.fullmatch(r"\d{1,4}", s) else None


def vol_issue(item):
    v = strict_int(item.get("volume"))
    i = strict_int(item.get("issue"))
    return (v, i) if v is not None and i is not None else None


def later_vi(n_vi, t_vi):
    """True if the target is in a later (volume, issue) than the notice; None if unknown."""
    if not n_vi or not t_vi:
        return None
    return tuple(t_vi) > tuple(n_vi)


def later_date(n_rng, t_rng, slack=0):
    """True if the target's earliest issued day is after the notice's latest + slack days."""
    if not n_rng or not t_rng:
        return None
    return t_rng[0] > n_rng[1] + datetime.timedelta(days=slack)


def is_pt(item):
    issns = {str(x).strip() for x in (item.get("ISSN") or [])}
    if issns & PT_ISSNS:
        return True
    return fold(first(item.get("container-title"))).strip() == "physics today"


def era(n_rng, created):
    """backfile: deposited 2+ calendar years after print; contemporaneous: within 120 days."""
    if not n_rng or not created:
        return "unknown"
    if created.year - n_rng[1].year >= 2:
        return "backfile"
    if (created - n_rng[1]).days <= 120:
        return "contemporaneous"
    return "other"


def rec(item):
    """Compact record of a Crossref work (notice or target)."""
    seen, targets = set(), []
    for u in item.get("update-to") or []:
        if isinstance(u, dict) and u.get("DOI"):
            t = norm_doi(u.get("DOI"))
            if t not in seen:
                seen.add(t)
                targets.append((t, norm_type(u.get("type"))))
    return {"doi": norm_doi(item.get("DOI")), "rng": issued_range(item),
            "created": created_date(item), "vi": vol_issue(item),
            "title": clean_text(first(item.get("title")))[:200],
            "page": str(item.get("page") or "")[:20], "pt": is_pt(item),
            "container": clean_text(first(item.get("container-title")))[:80],
            "cites": _int_or_none(item.get("is-referenced-by-count")) or 0, "targets": targets}


def classify(notice, tgt, target_doi):
    """self / missing / not_pt / later / same_issue / earlier / undated."""
    if target_doi == notice["doi"]:
        return "self"
    if tgt is None:
        return "missing"
    if not tgt["pt"]:
        return "not_pt"
    lv = later_vi(notice["vi"], tgt["vi"])
    if lv is True:
        return "later"
    if lv is False:
        return "same_issue" if tuple(notice["vi"]) == tuple(tgt["vi"]) else "earlier"
    ld = later_date(notice["rng"], tgt["rng"])
    if ld is None:
        return "undated"
    if ld:
        return "later"
    if tgt["rng"][0] >= notice["rng"][0]:
        return "same_issue"
    return "earlier"


def build_relations(notices, targets):
    listing = collections.defaultdict(set)
    for n in notices:
        for t, _ in n["targets"]:
            if t != n["doi"]:
                listing[t].add(n["doi"])
    rels = []
    for n in notices:
        e = era(n["rng"], n["created"])
        for t, ut in n["targets"]:
            tg = targets.get(t)
            rels.append({
                "notice": n["doi"], "target": t, "utype": ut, "era": e,
                "cls": classify(n, tg, t), "n_targets": len(n["targets"]),
                "n_listing": len(listing.get(t, ())),
                "later_vi": later_vi(n["vi"], tg["vi"]) if tg else None,
                "later_date": later_date(n["rng"], tg["rng"]) if tg else None,
                "later_date31": later_date(n["rng"], tg["rng"], SLACK_DAYS) if tg else None,
                "n": n, "t": tg})
    return rels


def _ratio(a, b):
    return (a / b) if b else None


def pt_stats(notices, rels):
    s = {"n_notices": len(notices), "n_relations": len(rels)}
    eras = {n["doi"]: era(n["rng"], n["created"]) for n in notices}
    by_era = collections.Counter(eras.values())
    s["notices_by_era"] = dict(sorted(by_era.items()))

    def mean_targets(e):
        ns = [n for n in notices if eras[n["doi"]] == e]
        return _ratio(sum(len(n["targets"]) for n in ns), len(ns))

    s["back_mean_targets"] = mean_targets("backfile")
    s["contemp_mean_targets"] = mean_targets("contemporaneous")
    s["n_contemp_notices"] = by_era.get("contemporaneous", 0)
    s["cls_by_era"] = {e: dict(sorted(collections.Counter(r["cls"] for r in rels
                                                          if r["era"] == e).items()))
                       for e in sorted(by_era)}
    nonself = {r["target"] for r in rels if r["cls"] != "self"}
    s["distinct_targets"] = len(nonself)
    s["distinct_targets_found"] = len({r["target"] for r in rels
                                       if r["cls"] not in ("self", "missing")})
    s["target_coverage"] = _ratio(s["distinct_targets_found"], s["distinct_targets"])
    s["n_self"] = sum(r["cls"] == "self" for r in rels)
    s["n_later"] = sum(r["cls"] == "later" for r in rels)
    s["n_later_vi_def"] = sum(r["later_vi"] is True and r["cls"] == "later" for r in rels)
    s["n_later_date_def"] = sum(r["later_date"] is True and r["cls"] not in ("self", "not_pt")
                                for r in rels)
    s["n_later_both"] = sum(r["later_vi"] is True and r["later_date"] is True
                            and r["cls"] == "later" for r in rels)
    s["n_later_date31"] = sum(r["later_date31"] is True and r["cls"] not in ("self", "not_pt")
                              for r in rels)
    back = [r for r in rels if r["era"] == "backfile" and r["cls"] in JUDGED]
    s["back_rel_judged"] = len(back)
    s["back_later"] = sum(r["cls"] == "later" for r in back)
    s["back_later_share"] = _ratio(s["back_later"], s["back_rel_judged"])
    s["contemp_rel_judged"] = sum(r["era"] == "contemporaneous" and r["cls"] in JUDGED
                                  for r in rels)
    s["contemp_later"] = sum(r["era"] == "contemporaneous" and r["cls"] == "later" for r in rels)
    later_by_notice = collections.Counter(r["notice"] for r in back if r["cls"] == "later")
    big = [n for n in notices if eras[n["doi"]] == "backfile" and len(n["targets"]) >= 3]
    s["back_notices3"] = len(big)
    s["back_notices3_with_later"] = sum(later_by_notice[n["doi"]] > 0 for n in big)
    tset = collections.defaultdict(set)
    for r in rels:
        if r["era"] == "backfile" and r["cls"] != "self":
            tset[r["target"]].add(r["notice"])
    s["back_distinct_targets"] = len(tset)
    s["back_shared_targets"] = sum(len(v) >= 2 for v in tset.values())

    def half(lo, hi):
        rr = [r for r in back if r["n"]["vi"] and lo <= r["n"]["vi"][1] <= hi]
        return len(rr), sum(r["cls"] == "later" for r in rr)

    s["h1_n"], s["h1_later"] = half(1, 6)
    s["h2_n"], s["h2_later"] = half(7, 12)
    # items that Crossref shows as corrected only by notices printed before them
    cls_by_target = collections.defaultdict(set)
    for r in rels:
        if r["cls"] in JUDGED:
            cls_by_target[r["target"]].add(r["cls"])
    s["items_only_later"] = sum(v == {"later"} for v in cls_by_target.values())
    s["items_judged"] = len(cls_by_target)
    return s


def aip_stats(aip_notices, targets):
    """AIP Publishing outside Physics Today: audit 1's date rule (slack 31 days)."""
    table = collections.defaultdict(lambda: [0, 0])
    judged = later = 0
    for n in aip_notices:
        e = era(n["rng"], n["created"])
        for t, ut in n["targets"]:
            if t == n["doi"] or ut not in NOTICE_TYPES:
                continue
            tg = targets.get(t)
            if not tg:
                continue
            ld = later_date(n["rng"], tg["rng"], SLACK_DAYS)
            if ld is None:
                continue
            judged += 1
            later += int(ld)
            table[(n["container"], e)][0] += 1
            table[(n["container"], e)][1] += int(ld)
    return {"aip_other_notices": len(aip_notices), "aip_other_judged": judged,
            "aip_other_later": later, "aip_other_later_share": _ratio(later, judged)}, table


def compute_predictions(s):
    """Mechanical predictions fixed in PREREG-3.md."""
    def h(c):
        return None if c is None else bool(c)

    g = s["complete"] and s["n_notices"] >= 270 and (s["target_coverage"] or 0) >= 0.95
    p2 = None
    if s["n_contemp_notices"] >= 10:
        p2 = s["contemp_later"] <= 1 and (s["contemp_mean_targets"] or 0) <= 1.3
    p3 = None if s["back_mean_targets"] is None else s["back_mean_targets"] >= 3
    p4 = None if not s["back_rel_judged"] else s["back_later"] / s["back_rel_judged"] >= 0.30
    p5 = None if not s["back_notices3"] else \
        s["back_notices3_with_later"] / s["back_notices3"] >= 0.60
    p6 = None if not s["back_distinct_targets"] else \
        s["back_shared_targets"] / s["back_distinct_targets"] >= 0.05
    p7 = None
    if s["h1_n"] >= 30 and s["h2_n"] >= 30:
        r1 = s["h1_later"] / s["h1_n"]
        r2 = s["h2_later"] / s["h2_n"]
        p7 = (r1 >= 1.5 * r2) if r2 > 0 else (r1 > 0)
    p8 = None
    if s.get("aip_complete") and s.get("aip_other_judged", 0) >= 1000:
        p8 = s["aip_other_later"] / s["aip_other_judged"] <= 0.01
    return {"G": h(g), "P1": h(s["n_later_vi_def"] >= 250), "P2": h(p2), "P3": h(p3),
            "P4": h(p4), "P5": h(p5), "P6": h(p6), "P7": h(p7), "P8": h(p8)}


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def batchable(doi):
    return bool(doi) and "," not in doi and "|" not in doi and not re.search(r"\s", doi)


def batch_url(dois, rows):
    f = ",".join("doi:" + urllib.parse.quote(d, safe="/") for d in dois)
    return "%s?filter=%s&rows=%d&select=%s&mailto=%s" % (API, f, rows, SELECT, MAILTO)


def _d(x):
    return x.isoformat() if x else ""


def _vi(x, k):
    return x[k] if x else ""


def relation_row(r):
    n, t = r["n"], r["t"] or {}
    return {"notice": r["notice"], "target": r["target"], "utype": r["utype"], "era": r["era"],
            "cls": r["cls"], "n_targets": r["n_targets"], "n_listing": r["n_listing"],
            "later_vi": r["later_vi"], "later_date": r["later_date"],
            "n_title": n["title"], "n_volume": _vi(n["vi"], 0), "n_issue": _vi(n["vi"], 1),
            "n_page": n["page"], "n_issued": _d(n["rng"][0] if n["rng"] else None),
            "n_created": _d(n["created"]),
            "t_title": t.get("title", ""), "t_volume": _vi(t.get("vi"), 0),
            "t_issue": _vi(t.get("vi"), 1), "t_page": t.get("page", ""),
            "t_issued": _d(t["rng"][0] if t.get("rng") else None),
            "t_container": t.get("container", ""), "t_cites": t.get("cites", "")}


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


def http_get(url, tries=6, timeout=120):
    """(status, body). 400/404/410 definitive; -1 = network failure."""
    delay = 5
    last = -1
    for _ in range(tries):
        PACE.wait()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                STATS["http_%d" % r.status] += 1
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = e.code
            STATS["http_%d" % e.code] += 1
            if e.code in (400, 404, 410):
                return e.code, b""
            if e.code in (403, 429) or e.code >= 500:
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            return e.code, b""
        except Exception:
            STATS["http_neterr"] += 1
            time.sleep(delay)
            delay = min(delay * 2, 120)
    return last, b""


def walk(filt, max_pages):
    items, cursor, complete, total = [], "*", False, None
    for page in range(max_pages):
        url = ("%s?filter=%s&rows=500&select=%s&mailto=%s&cursor=%s"
               % (API, filt, SELECT, MAILTO, urllib.parse.quote(cursor, safe="")))
        st, body = http_get(url)
        if st != 200:
            print("%s page %d failed: %s" % (filt, page, st), file=sys.stderr, flush=True)
            break
        try:
            msg = json.loads(body.decode("utf-8")).get("message") or {}
        except ValueError:
            print("%s page %d: bad JSON" % (filt, page), file=sys.stderr, flush=True)
            break
        total = msg.get("total-results", total)
        batch = msg.get("items") or []
        if not batch:
            complete = True
            break
        items.extend(batch)
        cursor = msg.get("next-cursor") or ""
        if not cursor:
            complete = True
            break
    print("%s: %d records (total %s, complete %s)" % (filt, len(items), total, complete),
          flush=True)
    return items, complete, total


def lookup_all(dois):
    found = {}
    todo = sorted(d for d in dois if batchable(d))
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        st, body = http_get(batch_url(chunk, len(chunk) + 5))
        if st != 200:
            continue
        try:
            for it in json.loads(body.decode("utf-8"))["message"]["items"]:
                found[norm_doi(it.get("DOI"))] = rec(it)
        except (ValueError, KeyError, TypeError):
            continue
        if (i // BATCH) % 25 == 0:
            print("targets: %d of %d looked up" % (i + len(chunk), len(todo)), flush=True)
    missing = sorted(d for d in dois if d not in found)[:FALLBACK_CAP]
    for d in missing:
        st, body = http_get("%s/%s?mailto=%s" % (API, urllib.parse.quote(d, safe="/"), MAILTO))
        if st != 200:
            continue
        try:
            r = rec(json.loads(body.decode("utf-8"))["message"])
        except (ValueError, KeyError, TypeError):
            continue
        found[r["doi"]] = r
        found.setdefault(d, r)
    return found


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-pages", type=int, default=200)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.time()

    pt_items, pt_complete, pt_total = walk(PT_FILTER, a.max_pages)
    aip_items, aip_complete, aip_total = walk(AIP_FILTER, a.max_pages)
    pt_notices = [rec(i) for i in pt_items]
    pt_dois = {n["doi"] for n in pt_notices}
    aip_notices = [rec(i) for i in aip_items if not is_pt(i) and norm_doi(i.get("DOI")) not in pt_dois]

    need = set()
    for n in pt_notices:
        need.update(t for t, _ in n["targets"] if t != n["doi"])
    for n in aip_notices:
        need.update(t for t, ut in n["targets"] if t != n["doi"] and ut in NOTICE_TYPES)
    targets = lookup_all(need)

    rels = build_relations(pt_notices, targets)
    s = pt_stats(pt_notices, rels)
    s["complete"] = pt_complete
    s["pt_total_results"] = pt_total
    a_s, table = aip_stats(aip_notices, targets)
    s.update(a_s)
    s["aip_complete"] = aip_complete
    s["aip_total_results"] = aip_total
    s["predictions"] = compute_predictions(s)
    s["http"] = dict(STATS)
    s["minutes"] = round((time.time() - t0) / 60, 1)
    s["run_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    rows = [relation_row(r) for r in rels]
    fields = list(rows[0].keys()) if rows else ["notice"]
    rows.sort(key=lambda r: (r["n_issued"], r["notice"], r["t_issued"]))
    write_csv(os.path.join(a.out_dir, "pt_relations.csv"), rows, fields)

    nrows = []
    for n in pt_notices:
        rr = [r for r in rels if r["notice"] == n["doi"]]
        nrows.append({"notice": n["doi"], "title": n["title"], "volume": _vi(n["vi"], 0),
                      "issue": _vi(n["vi"], 1), "page": n["page"],
                      "issued": _d(n["rng"][0] if n["rng"] else None),
                      "created": _d(n["created"]), "era": era(n["rng"], n["created"]),
                      "n_targets": len(n["targets"]),
                      "n_later": sum(r["cls"] == "later" for r in rr),
                      "n_earlier": sum(r["cls"] == "earlier" for r in rr),
                      "n_same_issue": sum(r["cls"] == "same_issue" for r in rr),
                      "n_other": sum(r["cls"] not in JUDGED for r in rr)})
    nrows.sort(key=lambda r: (r["issued"], r["notice"]))
    write_csv(os.path.join(a.out_dir, "pt_notices.csv"), nrows, list(nrows[0].keys()) if nrows
              else ["notice"])

    later = [r for r in rows if r["cls"] == "later"]
    later.sort(key=lambda r: sha_key(r["notice"], r["target"]))
    grade = [dict(r, grade="", note="") for r in later[:GRADE_N]]
    write_csv(os.path.join(a.out_dir, "grade_later20.csv"), grade, fields + ["grade", "note"])

    trows = [{"container": k[0], "era": k[1], "judged": v[0], "later31": v[1],
              "share": round(v[1] / v[0], 4) if v[0] else ""} for k, v in table.items()]
    trows.sort(key=lambda r: (-r["judged"], r["container"], r["era"]))
    write_csv(os.path.join(a.out_dir, "aip_table.csv"), trows,
              ["container", "era", "judged", "later31", "share"])

    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, sort_keys=True, default=str)
    print(json.dumps(s["predictions"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
