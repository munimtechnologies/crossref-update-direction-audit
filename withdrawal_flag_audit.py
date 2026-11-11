#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Audit 13 (pre-registered in PREREG-13.md): does OpenAlex's is_retracted flag items that
Crossref records only as withdrawn?

A Crossref record can carry retractive `update-to` links of several types (retraction, withdrawal,
partial_retraction, removal), deposited by the publisher (`source: publisher`) or added from the
Retraction Watch database (`source: retraction-watch`). This script walks every Crossref record
matched by filter=update-type:X for those four types and collects, for every linked target T, the
(type, source) pairs that point at it and whether any Retraction Watch link points at it. Groups:

  w_only   every retractive link to T is a publisher `withdrawal`; no RW link of any type
  w_self   w_only targets whose own record carries the publisher withdrawal link to itself
  r_only   every retractive link to T is a publisher `retraction`; no RW link
  w_rw     T has a publisher `withdrawal` link and also an RW link

It then asks OpenAlex for is_retracted on every w_only and w_rw target and on a fixed sample of
r_only targets, and reports the flag share in each group.

No API keys. api.crossref.org and api.openalex.org (mailto set).
Usage: python withdrawal_flag_audit.py --out-dir /out
"""
import argparse
import collections
import csv
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

MAILTO = "mv2@munimtech.com"
UA = "crossref-withdrawal-flag-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
CROSSREF = "https://api.crossref.org/works"
OPENALEX = "https://api.openalex.org/works"
RAW = "https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/main/"
PLAN = "PREREG-13.md"
PLAN_MARK = b"Pre-registration 13"
SELECT = "DOI,update-to,title,publisher"
UPDATE_TYPES = ["retraction", "withdrawal", "partial_retraction", "removal"]
RETRACTIVE = set(UPDATE_TYPES)
OA_BATCH = 50
SAMPLE_N = 3000
GRADE_N = 20
CONTROL_W = "10.1016/j.cgh.2026.10.001"     # withdrawn in place by its publisher (read 2026-11-11)
CONTROL_R = "10.1053/j.gastro.2024.07.040"  # publisher retraction link only (read 2026-11-11)
ASKABLE = re.compile(r"^10\.\d{4,9}/[^\s|,:&#+?%<>;\"\\]+$")
STATUS_PREFIX = re.compile(
    r"^(?:retracted(?: article)?|withdrawn(?: article)?|removed|temporary removal|"
    r"temporarily removed)\s*[:.\-\]]\s*")
MARK_END = re.compile(r"[\[(]\s*(?:retracted|withdrawn)(?: article)?\s*[\])]$")
LEAD = " \"'[(*"
GROUPS = ["w_only", "r_only", "w_rw", "other"]


# ---------------------------------------------------------------- pure helpers
def ascii_fold(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(ch if ord(ch) < 128 else ("" if unicodedata.combining(ch) else " ") for ch in s)


def norm_doi(d):
    d = str(d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/",
              "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d.strip()


def norm_type(t):
    return re.sub(r"[\s\-]+", "_", str(t or "").strip().lower())


def first(v):
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


def t_marked(title):
    """Title marked as retracted/withdrawn by its publisher ('WITHDRAWN: ...', '... (Retracted)')."""
    c = re.sub(r"\s+", " ", ascii_fold(title).lower()).strip()
    return bool(STATUS_PREFIX.match(c.lstrip(LEAD)) or MARK_END.search(c))


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return round(num / den, 4) if den else None


def askable(doi):
    return bool(ASKABLE.match(doi or ""))


def classify(pairs, rw_any):
    """Group of one target from its set of (type, source) retractive links and its RW flag."""
    pub = {ut for ut, src in pairs if src == "publisher"}
    types = {ut for ut, _ in pairs}
    if rw_any:
        return "w_rw" if "withdrawal" in pub else "other"
    if types == {"withdrawal"} and "withdrawal" in pub:
        return "w_only"
    if types == {"retraction"} and "retraction" in pub:
        return "r_only"
    return "other"


# ---------------------------------------------------------------- Crossref walk
class Targets:
    def __init__(self):
        self.seen = set()
        self.n_records = 0
        self.links = collections.defaultdict(set)   # target -> {(type, source)}
        self.rw_any = set()                         # targets of any RW-sourced link
        self.self_w = set()                         # records with a publisher withdrawal self-link
        self.titles = {}
        self.publisher = {}

    def add(self, item):
        rec = norm_doi(item.get("DOI"))
        if not rec or rec in self.seen:
            return
        self.seen.add(rec)
        self.n_records += 1
        self.titles[rec] = first(item.get("title"))[:300]
        self.publisher[rec] = str(item.get("publisher") or "")[:80]
        for u in item.get("update-to") or []:
            if not isinstance(u, dict):
                continue
            t, ut = norm_doi(u.get("DOI")), norm_type(u.get("type"))
            src = str(u.get("source") or "").strip().lower()
            if not t:
                continue
            if src == "retraction-watch":
                self.rw_any.add(t)
            if ut not in RETRACTIVE:
                continue
            self.links[t].add((ut, src))
            if t == rec and ut == "withdrawal" and src == "publisher":
                self.self_w.add(t)

    def groups(self):
        out = {}
        for t, pairs in self.links.items():
            out[t] = classify(pairs, t in self.rw_any)
        return out


# ---------------------------------------------------------------- grading
def rate(rows):
    """(found, flagged) for rows of (found, is_retracted)."""
    found = [r for r in rows if r[0]]
    return len(found), sum(1 for r in found if r[1] is True)


def grade(n_w, w_found, w_flag, s_found, s_flag, r_found, r_flag, x_found, x_flag, gates):
    """Predictions P1-P6 of PREREG-13.md. n_w: w_only targets; *_found / *_flag: OpenAlex found
    and is_retracted true in w_only (w), w_self (s), the r_only sample (r) and w_rw (x)."""
    res = {}

    def put(k, value, ok, note):
        res[k] = {"value": value, "held": ok, "note": note}

    put("P1", n_w, 200 <= n_w <= 4000, "w_only targets in 200-4,000")
    x = share(w_found, n_w)
    put("P2", x, x is not None and x >= 0.9, "OpenAlex finds >= 90% of w_only targets")
    if s_found >= 30:
        x = share(s_flag, s_found)
        put("P3", x, x <= 0.2, "is_retracted true for <= 20% of found w_self targets")
    else:
        put("P3", s_found, None, "inconclusive: fewer than 30 w_self targets found")
    pr = share(r_flag, r_found) if r_found >= 100 else None
    if pr is not None:
        put("P4", pr, pr >= 0.9, "is_retracted true for >= 90% of found sampled r_only targets")
    else:
        put("P4", r_found, None, "inconclusive: fewer than 100 r_only targets found")
    pw = share(w_flag, w_found)
    if pr is not None and pw is not None and w_found >= 30:
        gap = round(pr - pw, 4)
        put("P5", gap, gap >= 0.5, "r_only flag share minus w_only flag share >= 50 points")
    else:
        put("P5", None, None, "inconclusive: P4 inconclusive or fewer than 30 w_only found")
    if x_found >= 30:
        x = share(x_flag, x_found)
        put("P6", x, x >= 0.8, "is_retracted true for >= 80% of found w_rw targets")
    else:
        put("P6", x_found, None, "inconclusive: fewer than 30 w_rw targets found")
    if not all(g.get("ok") for g in gates.values()):
        for k in res:
            res[k]["note"] += " (a gate failed: reported descriptively, not graded)"
    return res


# ---------------------------------------------------------------- network
STATS = collections.Counter()
_LAST = {}


def http(url, tries=6, timeout=120, gap=0.5, host="x"):
    delay = 5
    last = -1
    for _ in range(tries):
        wait = _LAST.get(host, 0.0) + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST[host] = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                STATS["%s_%d" % (host, r.status)] += 1
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = e.code
            STATS["%s_%d" % (host, e.code)] += 1
            if e.code in (400, 404, 410, 414):
                return e.code, b""
            time.sleep(delay)
            delay = min(delay * 2, 120)
        except Exception:
            STATS["%s_neterr" % host] += 1
            time.sleep(delay)
            delay = min(delay * 2, 120)
    return last, b""


def jload(body):
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, AttributeError):
        return None


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def wait_for_plan(minutes):
    deadline = time.monotonic() + 60 * minutes
    while True:
        st, b = http(RAW + PLAN, tries=1, host="gh", gap=1.0)
        if st == 200 and PLAN_MARK in b:
            return now()
        if time.monotonic() >= deadline:
            return None
        time.sleep(60)


def walk(w, utype, max_pages):
    cursor, total = "*", None
    for page in range(max_pages):
        url = ("%s?filter=update-type:%s&rows=1000&select=%s&mailto=%s&cursor=%s"
               % (CROSSREF, utype, SELECT, MAILTO, urllib.parse.quote(cursor, safe="")))
        st, body = http(url, host="crossref", gap=0.3)
        msg = (jload(body) or {}).get("message") if st == 200 else None
        if not isinstance(msg, dict):
            print("walk %s page %d failed: %s" % (utype, page, st), file=sys.stderr, flush=True)
            return False, total
        total = msg.get("total-results", total)
        items = msg.get("items") or []
        if not items:
            return True, total
        for it in items:
            w.add(it)
        cursor = msg.get("next-cursor") or ""
        if not cursor:
            return True, total
        if page % 20 == 0:
            print("%s: %d records after page %d (total %s)" % (utype, w.n_records, page + 1, total),
                  flush=True)
    return False, total


def openalex(dois):
    """({doi: (is_retracted, title)}, batches asked, batches failed). Only askable DOIs."""
    out = {}
    ok = [d for d in dois if askable(d)]
    n_b = n_fail = 0
    for i in range(0, len(ok), OA_BATCH):
        b = ok[i:i + OA_BATCH]
        n_b += 1
        url = ("%s?filter=doi:%s&select=doi,is_retracted,display_name&per-page=100&mailto=%s"
               % (OPENALEX, "|".join(urllib.parse.quote(d, safe="/()") for d in b), MAILTO))
        st, body = http(url, host="openalex", gap=0.2)
        obj = jload(body) if st == 200 else None
        if obj is None:
            n_fail += 1
            continue
        for r in obj.get("results") or []:
            out[norm_doi(r.get("doi"))] = (r.get("is_retracted"), str(r.get("display_name") or "")[:200])
        if n_b % 20 == 0:
            print("openalex %d/%d" % (i + len(b), len(ok)), flush=True)
    return out, n_b, n_fail


# ---------------------------------------------------------------- main
FIELDS = ["target", "group", "self_w", "links", "crossref_title", "title_marked", "publisher",
          "askable", "oa_found", "is_retracted", "oa_title", "grade", "note"]


def row(t, g, tg, oa):
    pairs = sorted(tg.links.get(t, ()))
    hit = oa.get(t)
    title = tg.titles.get(t, "")
    return {"target": t, "group": g, "self_w": t in tg.self_w,
            "links": ";".join("%s/%s" % p for p in pairs), "crossref_title": title,
            "title_marked": t_marked(title) if title else "", "publisher": tg.publisher.get(t, ""),
            "askable": askable(t), "oa_found": hit is not None,
            "is_retracted": "" if hit is None else hit[0], "oa_title": "" if hit is None else hit[1]}


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        wr.writeheader()
        for r in rows:
            wr.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-min", type=int, default=120)
    ap.add_argument("--max-pages", type=int, default=400)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()
    s = {"preregistered": PLAN, "started": now()}
    s["plan_live_at"] = wait_for_plan(a.wait_min)
    if not s["plan_live_at"]:
        s["error"] = "plan not live; nothing run"
        with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)
        return 0
    s["data_started"] = now()

    tg = Targets()
    walk_ok, totals = True, {}
    for ut in UPDATE_TYPES:
        ok, tot = walk(tg, ut, a.max_pages)
        totals[ut] = tot
        if ut in ("retraction", "withdrawal"):
            walk_ok = walk_ok and ok
    grp = tg.groups()
    c = collections.Counter(grp.values())
    print("walk done: %d records, %d targets, %s, %.0fs"
          % (tg.n_records, len(grp), dict(c), time.monotonic() - t0), flush=True)

    w_only = sorted(t for t, g in grp.items() if g == "w_only")
    w_rw = sorted(t for t, g in grp.items() if g == "w_rw")
    r_all = sorted((t for t, g in grp.items() if g == "r_only"), key=lambda t: sha_key("a13r", t))
    r_s = r_all[:SAMPLE_N]
    ask = sorted(set(w_only) | set(w_rw) | set(r_s) | {CONTROL_W, CONTROL_R})
    oa, n_b, n_fail = openalex(ask)

    def rows_of(ts):
        return [(t in oa, oa[t][0] if t in oa else None) for t in ts]

    w_self = [t for t in w_only if t in tg.self_w]
    w_found, w_flag = rate(rows_of(w_only))
    s_found, s_flag = rate(rows_of(w_self))
    r_found, r_flag = rate(rows_of(r_s))
    x_found, x_flag = rate(rows_of(w_rw))

    gates = {
        "G1_walk_complete": {"value": totals, "ok": walk_ok},
        "G2_controls": {"value": [grp.get(CONTROL_W), CONTROL_W in tg.self_w, grp.get(CONTROL_R),
                                  CONTROL_W in oa, CONTROL_R in oa],
                        "ok": grp.get(CONTROL_W) == "w_only" and CONTROL_W in tg.self_w
                        and grp.get(CONTROL_R) == "r_only" and CONTROL_W in oa and CONTROL_R in oa},
        "G3_openalex_failures": {"value": [n_fail, n_b], "ok": n_fail <= 0.02 * max(n_b, 1)},
        "G4_plan_live_first": {"value": s["plan_live_at"], "ok": bool(s["plan_live_at"])},
    }
    preds = grade(len(w_only), w_found, w_flag, s_found, s_flag, r_found, r_flag, x_found, x_flag,
                  gates)

    write_csv(os.path.join(a.out_dir, "w_only.csv"), [row(t, "w_only", tg, oa) for t in w_only])
    write_csv(os.path.join(a.out_dir, "w_rw.csv"), [row(t, "w_rw", tg, oa) for t in w_rw])
    write_csv(os.path.join(a.out_dir, "r_only_sample.csv"),
              [row(t, "r_only", tg, oa) for t in sorted(r_s)])
    unflag = [t for t in w_self if t in oa and oa[t][0] is False]
    write_csv(os.path.join(a.out_dir, "grade20_w_self_unflagged.csv"),
              [row(t, "w_only", tg, oa) for t in sorted(unflag, key=lambda t: sha_key("a13g", t))[:GRADE_N]])

    pub_unflag = collections.Counter(tg.publisher.get(t, "") for t in unflag)
    s.update({
        "n_records": tg.n_records, "n_targets": len(grp), "groups": {k: c[k] for k in GROUPS},
        "crossref_totals": totals, "n_w_self": len(w_self), "n_r_only": len(r_all),
        "n_r_sample": len(r_s), "openalex_asked": len(ask),
        "openalex_unaskable": sum(1 for t in ask if not askable(t)),
        "w_only": [w_found, w_flag], "w_self": [s_found, s_flag], "r_only_sample": [r_found, r_flag],
        "w_rw": [x_found, x_flag],
        "w_self_title_marked": sum(1 for t in w_self if t_marked(tg.titles.get(t, ""))),
        "w_self_unflagged_by_publisher": pub_unflag.most_common(20),
        "controls_openalex": {CONTROL_W: oa.get(CONTROL_W), CONTROL_R: oa.get(CONTROL_R)},
        "gates": gates, "all_gates_ok": all(g["ok"] for g in gates.values()), "predictions": preds,
        "http": dict(STATS), "elapsed_s": round(time.monotonic() - t0, 1),
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({"groups": s["groups"], "w_only": s["w_only"], "w_self": s["w_self"],
                      "r_only_sample": s["r_only_sample"], "w_rw": s["w_rw"],
                      "gates_ok": s["all_gates_ok"],
                      "predictions": {k: x["held"] for k, x in preds.items()}}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
