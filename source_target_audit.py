#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Audit 11 (pre-registered in PREREG-11.md): for the same retraction notice in Crossref, do the
publisher and Retraction Watch name the same retracted paper?

Since 2023 a Crossref notice record can carry two kinds of retractive `update-to` link: the ones
its publisher deposited (`source: publisher`) and the ones Crossref added from the Retraction
Watch database (`source: retraction-watch`). Both say "this notice retracts that paper". This
script walks every Crossref record matched by filter=update-type:X (X = retraction, withdrawal,
partial_retraction, removal), drops self-links (target == notice), and for each notice compares
P (publisher targets) with R (Retraction Watch targets):

  agree           P == R
  overlap         P and R share a target but differ otherwise
  disjoint        P and R share no target: the two sources name different papers
  publisher_only  only P;  rw_only: only R

For `disjoint` notices it asks which side the notice's own title describes: containment of each
target's title words in the notice title (words of 3+ letters, digits and boilerplate dropped).
`rw_right` (an R target >= 0.6, every P target < 0.3), `publisher_right` (the reverse),
`both_match` (both >= 0.6) or `undetermined`. It also records the edit distance between the
closest P and R DOIs (a typo leaves a small distance), whether the target the title does not
describe has any other retraction evidence, and OpenAlex is_retracted for that target.
Calibration: the same title rule on a sample of `agree` notices; descriptive: publisher-only
notices whose title does not describe their target.

No API keys. api.crossref.org and api.openalex.org (mailto set).
Usage: python source_target_audit.py --out-dir /out
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
UA = "crossref-source-target-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
CROSSREF = "https://api.crossref.org/works"
OPENALEX = "https://api.openalex.org/works"
RAW = "https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/main/"
PLAN = "PREREG-11.md"
PLAN_MARK = b"Pre-registration 11"
SELECT = "DOI,update-to,title,publisher,member,created"
UPDATE_TYPES = ["retraction", "withdrawal", "partial_retraction", "removal"]
RETRACTIVE = set(UPDATE_TYPES)
TITLE_BATCH = 20
GRADE_N = 20
HI, LO, MISMATCH = 0.6, 0.3, 0.2
MIN_WORDS = 4
NEAR = 2
# notice, publisher target, Retraction Watch target; read by hand in live Crossref on 2026-11-10
CONTROL = ("10.1016/s0015-0282(16)58061-3", "10.1016/s0015-0282(16)56091-9",
           "10.1016/s0015-0282(16)56090-7")

STOP = set("""
the and for with from that this into its are was were has have been their our not but than also
via per all any can one two retraction retractions retracted retract notice note notes withdrawal
withdrawn withdraw removal removed temporary statement expression concern article articles paper
correction corrected erratum errata corrigendum corrigenda addendum publisher author authors
journal vol volume pages issue
""".split())

STATUS_PREFIX = re.compile(
    r"^(?:retracted(?: article)?|withdrawn(?: article)?|removed|temporary removal|"
    r"temporarily removed)\s*[:.\-\]]\s*")
MARK_END = re.compile(r"[\[(]\s*(?:retracted|withdrawn)(?: article)?\s*[\])]$")
LEAD = " \"'[(*"
SIDES = ["agree", "overlap", "disjoint", "publisher_only", "rw_only"]
VERDICTS = ["rw_right", "publisher_right", "both_match", "undetermined"]


# ---------------------------------------------------------------- pure helpers
def ascii_fold(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(ch if ord(ch) < 128 else ("" if unicodedata.combining(ch) else " ") for ch in s)


def words(s):
    """Informative words of a title: 3+ characters, not all digits, not boilerplate."""
    s = re.sub(r"<[^>]+>", " ", ascii_fold(s)).lower()
    return {w for w in re.findall(r"[a-z0-9]+", s)
            if len(w) > 2 and not w.isdigit() and w not in STOP}


def containment(target_title, notice_title):
    """Share of the target title's words found in the notice title; None if either is too short."""
    t, n = words(target_title), words(notice_title)
    if len(t) < MIN_WORDS or len(n) < MIN_WORDS:
        return None
    return round(len(t & n) / len(t), 4)


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


def created_year(item):
    dp = ((item or {}).get("created") or {}).get("date-parts") or [[None]]
    try:
        return int(dp[0][0])
    except (TypeError, ValueError, IndexError):
        return None


def t_marked(title):
    """Title marked as retracted/withdrawn by its publisher ('RETRACTED: ...', '... (Retracted)')."""
    c = re.sub(r"\s+", " ", ascii_fold(title).lower()).strip()
    return bool(STATUS_PREFIX.match(c.lstrip(LEAD)) or MARK_END.search(c))


def levenshtein(a, b):
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def min_distance(ps, rs):
    return min((levenshtein(p, r) for p in ps for r in rs), default=None)


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return round(num / den, 4) if den else None


def side_class(ps, rs):
    p, r = set(ps), set(rs)
    if p and r:
        if p == r:
            return "agree"
        return "overlap" if p & r else "disjoint"
    return "publisher_only" if p else "rw_only"


def best(targets, notice_title, titles):
    vals = [containment(titles.get(t, ""), notice_title) for t in targets]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def verdict(notice_title, ps, rs, titles):
    """(verdict, best containment over P, best over R) for one notice."""
    cp, cr = best(ps, notice_title, titles), best(rs, notice_title, titles)
    if cp is None or cr is None:
        return "undetermined", cp, cr
    if cr >= HI and cp < LO:
        return "rw_right", cp, cr
    if cp >= HI and cr < LO:
        return "publisher_right", cp, cr
    if cp >= HI and cr >= HI:
        return "both_match", cp, cr
    return "undetermined", cp, cr


# ---------------------------------------------------------------- Crossref walk
class Walker:
    """Per-notice publisher (P) and Retraction Watch (R) retractive targets, self-links dropped."""

    def __init__(self):
        self.seen = set()
        self.notices = {}
        self.pub_count = collections.Counter()   # target -> notices with a publisher link to it
        self.rw_count = collections.Counter()    # target -> notices with an RW link to it
        self.self_any = set()                    # records with a retractive link to themselves
        self.self_src = collections.Counter()
        self.other_src = 0
        self.n_records = 0

    def add(self, item):
        rec = norm_doi(item.get("DOI"))
        if not rec or rec in self.seen:
            return
        self.seen.add(rec)
        self.n_records += 1
        ps, rs = set(), set()
        rw_self = False
        for u in item.get("update-to") or []:
            if not isinstance(u, dict):
                continue
            t, ut = norm_doi(u.get("DOI")), norm_type(u.get("type"))
            src = str(u.get("source") or "").strip().lower()
            if ut not in RETRACTIVE or not t:
                continue
            if t == rec:
                self.self_any.add(rec)
                self.self_src[src] += 1
                rw_self = rw_self or src == "retraction-watch"
                continue
            if src == "publisher":
                ps.add(t)
            elif src == "retraction-watch":
                rs.add(t)
            else:
                self.other_src += 1
        if not ps and not rs:
            return
        for t in ps:
            self.pub_count[t] += 1
        for t in rs:
            self.rw_count[t] += 1
        self.notices[rec] = {
            "notice": rec, "P": sorted(ps), "R": sorted(rs), "notice_title": first(item.get("title"))[:300],
            "publisher": str(item.get("publisher") or "")[:80], "member": str(item.get("member") or ""),
            "year": created_year(item), "rw_self": rw_self}


def evidence_p(t, w, titles):
    """Other signs that publisher target t is retracted, besides this one notice's link."""
    ev = []
    if w.rw_count[t] > 0:
        ev.append("rw")
    if w.pub_count[t] > 1:
        ev.append("other_notice")
    if t in w.self_any:
        ev.append("self")
    if t_marked(titles.get(t, "")):
        ev.append("title")
    return ev


def evidence_r(t, w, titles):
    """Other signs that Retraction Watch target t is retracted, besides this one notice's RW link."""
    ev = []
    if w.pub_count[t] > 0:
        ev.append("publisher")
    if w.rw_count[t] > 1:
        ev.append("other_rw")
    if t in w.self_any:
        ev.append("self")
    if t_marked(titles.get(t, "")):
        ev.append("title")
    return ev


# ---------------------------------------------------------------- grading
def grade(c, v, near_rw, cal, pub_only, oa_wrong, gates):
    """Predictions P1-P7 of PREREG-11.md.

    c: Counter of sides; v: Counter of disjoint verdicts; near_rw: rw_right notices with near DOIs;
    cal: (informative, >= HI, < MISMATCH) for sampled agree notices; pub_only: (informative,
    < MISMATCH) for publisher-only notices; oa_wrong: (checked, is_retracted true) for P targets of
    rw_right notices."""
    res = {}

    def put(k, value, ok, note):
        res[k] = {"value": value, "held": ok, "note": note}

    both = c["agree"] + c["overlap"] + c["disjoint"]
    put("P1", both, 10000 <= both <= 45000, "notices with both publisher and RW targets in 10,000-45,000")
    x = share(c["disjoint"], both)
    put("P2", x, x is not None and 0.002 <= x <= 0.03, "disjoint share of two-source notices in 0.2%-3%")
    dec = v["rw_right"] + v["publisher_right"]
    if dec >= 5:
        x = share(v["rw_right"], dec)
        put("P3", x, x >= 0.5, "rw_right >= 50% of decided disjoint notices")
    else:
        put("P3", dec, None, "inconclusive: fewer than 5 decided disjoint notices")
    if v["rw_right"] >= 5:
        x = share(near_rw, v["rw_right"])
        put("P4", x, x >= 0.5, "rw_right notices whose closest P and R DOIs differ by <= 2 edits >= 50%")
    else:
        put("P4", v["rw_right"], None, "inconclusive: fewer than 5 rw_right notices")
    n_inf, n_hi, n_lo = cal
    if n_inf >= 100:
        a, b = share(n_hi, n_inf), share(n_lo, n_inf)
        put("P5", [a, b], a >= 0.9 and b <= 0.03,
            "sampled agree notices: >= 90% containment >= 0.6 and <= 3% below 0.2")
    else:
        put("P5", n_inf, None, "inconclusive: fewer than 100 informative agree notices")
    n_inf, n_mis = pub_only
    if n_inf >= 100:
        x = share(n_mis, n_inf)
        put("P6", x, x <= 0.02, "publisher-only notices whose title does not describe the target <= 2%")
    else:
        put("P6", n_inf, None, "inconclusive: fewer than 100 informative publisher-only notices")
    n_chk, n_flag = oa_wrong
    if n_chk >= 5:
        x = share(n_flag, n_chk)
        put("P7", x, x >= 0.8, "OpenAlex is_retracted true for >= 80% of rw_right publisher targets")
    else:
        put("P7", n_chk, None, "inconclusive: fewer than 5 targets checked in OpenAlex")
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


def crossref_titles(dois):
    """({doi: title}, set of DOIs whose batch failed or that cannot be asked)."""
    out, failed = {}, {d for d in dois if "," in d}
    ok = [d for d in dois if "," not in d]
    for i in range(0, len(ok), TITLE_BATCH):
        b = ok[i:i + TITLE_BATCH]
        f = ",".join("doi:" + urllib.parse.quote(d, safe="/") for d in b)
        st, body = http("%s?filter=%s&rows=%d&select=DOI,title&mailto=%s"
                        % (CROSSREF, f, len(b) + 5, MAILTO), host="crossref", gap=0.3)
        msg = (jload(body) or {}).get("message") if st == 200 else None
        if not isinstance(msg, dict):
            failed.update(b)
            continue
        for it in msg.get("items") or []:
            out[norm_doi(it.get("DOI"))] = first(it.get("title"))[:300]
        if (i // TITLE_BATCH) % 250 == 0:
            print("titles %d/%d" % (i + len(b), len(ok)), flush=True)
    return out, failed


def openalex(dois):
    out = {}
    ok = [d for d in dois if "|" not in d and "," not in d]
    run_fail = 0
    for i in range(0, len(ok), 50):
        b = ok[i:i + 50]
        url = ("%s?filter=doi:%s&select=doi,is_retracted,cited_by_count&per-page=100&mailto=%s"
               % (OPENALEX, "|".join(urllib.parse.quote(d, safe="/()") for d in b), MAILTO))
        st, body = http(url, host="openalex", gap=0.2)
        obj = jload(body) if st == 200 else None
        if obj is None:
            run_fail += 1
            if run_fail >= 5:
                print("openalex: 5 batches in a row failed, stopping", file=sys.stderr, flush=True)
                break
            continue
        run_fail = 0
        for r in obj.get("results") or []:
            out[norm_doi(r.get("doi"))] = (r.get("is_retracted"), r.get("cited_by_count"))
    return out


# ---------------------------------------------------------------- main
FIELDS = ["notice", "side", "verdict", "cont_p", "cont_r", "doi_dist", "near", "P", "R",
          "p_missing", "notice_title", "p_titles", "r_titles", "evidence_p", "evidence_r",
          "oa_p", "oa_r", "publisher", "member", "year", "grade", "note"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        wr.writeheader()
        for r in rows:
            wr.writerow(r)


def show(n):
    """Copy of a notice dict with list fields joined for CSV."""
    r = dict(n)
    for k in ("P", "R"):
        r[k] = ";".join(n[k])
    return r


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-min", type=int, default=60)
    ap.add_argument("--max-pages", type=int, default=400)
    ap.add_argument("--agree-sample", type=int, default=5000)
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

    w = Walker()
    walk_ok, totals = True, {}
    for ut in UPDATE_TYPES:
        ok, tot = walk(w, ut, a.max_pages)
        totals[ut] = tot
        if ut in ("retraction", "withdrawal"):
            walk_ok = walk_ok and ok
    notices = list(w.notices.values())
    for n in notices:
        n["side"] = side_class(n["P"], n["R"])
    c = collections.Counter(n["side"] for n in notices)
    print("walk done: %d records, %d notices, %s, %.0fs"
          % (w.n_records, len(notices), dict(c), time.monotonic() - t0), flush=True)

    agree = sorted((n for n in notices if n["side"] == "agree"), key=lambda n: sha_key("a11a", n["notice"]))
    agree_s = agree[:a.agree_sample]
    need = [n for n in notices if n["side"] in ("overlap", "disjoint", "publisher_only")] + agree_s
    dois = sorted({t for n in need for t in n["P"] + n["R"]})
    titles, tfail = crossref_titles(dois)

    for n in need:
        n["verdict"], n["cont_p"], n["cont_r"] = verdict(n["notice_title"], n["P"], n["R"], titles)
        n["p_missing"] = sum(1 for t in n["P"] if t not in titles and t not in tfail)
        n["p_titles"] = " || ".join(titles.get(t, "")[:150] for t in n["P"])[:600]
        n["r_titles"] = " || ".join(titles.get(t, "")[:150] for t in n["R"])[:600]

    cal_inf = [n for n in agree_s if n["cont_p"] is not None]
    cal = (len(cal_inf), sum(1 for n in cal_inf if n["cont_p"] >= HI),
           sum(1 for n in cal_inf if n["cont_p"] < MISMATCH))
    pub = [n for n in notices if n["side"] == "publisher_only"]
    pub_inf = [n for n in pub if n["cont_p"] is not None]
    pub_mis = [n for n in pub_inf if n["cont_p"] < MISMATCH]

    dis = [n for n in notices if n["side"] == "disjoint"]
    v = collections.Counter()
    near_rw = 0
    for n in dis:
        v[n["verdict"]] += 1
        n["doi_dist"] = min_distance(n["P"], n["R"])
        n["near"] = n["doi_dist"] is not None and n["doi_dist"] <= NEAR
        n["evidence_p"] = ";".join(sorted({e for t in n["P"] for e in evidence_p(t, w, titles)}))
        n["evidence_r"] = ";".join(sorted({e for t in n["R"] for e in evidence_r(t, w, titles)}))
        if n["verdict"] == "rw_right" and n["near"]:
            near_rw += 1

    rwr = [n for n in dis if n["verdict"] == "rw_right"]
    pbr = [n for n in dis if n["verdict"] == "publisher_right"]
    oa = openalex(sorted({t for n in rwr for t in n["P"]} | {t for n in pbr for t in n["R"]}))
    oa_chk = oa_flag = 0
    for n in dis:
        n["oa_p"] = ";".join(str(oa.get(t, ("", ""))[0]) for t in n["P"])
        n["oa_r"] = ";".join(str(oa.get(t, ("", ""))[0]) for t in n["R"])
    for t in sorted({t for n in rwr for t in n["P"]}):
        if t in oa and oa[t][0] in (True, False):
            oa_chk += 1
            oa_flag += 1 if oa[t][0] is True else 0

    ctl = w.notices.get(CONTROL[0])
    ctl_val = [ctl["side"], ctl.get("verdict")] if ctl else ["missing", None]
    gates = {
        "G1_walk_complete": {"value": totals, "ok": walk_ok},
        "G2_control_notice": {"value": ctl_val, "ok": ctl_val == ["disjoint", "rw_right"]},
        "G3_title_failures": {"value": len(tfail), "ok": len(tfail) <= 0.02 * max(len(dois), 1)},
        "G4_plan_live_first": {"value": s["plan_live_at"], "ok": bool(s["plan_live_at"])},
    }
    preds = grade(c, v, near_rw, cal, (len(pub_inf), len(pub_mis)), (oa_chk, oa_flag), gates)

    key = lambda n: (n["publisher"], n["notice"])
    write_csv(os.path.join(a.out_dir, "disjoint.csv"), [show(n) for n in sorted(dis, key=key)])
    write_csv(os.path.join(a.out_dir, "overlap.csv"),
              [show(n) for n in sorted((n for n in notices if n["side"] == "overlap"), key=key)])
    write_csv(os.path.join(a.out_dir, "grade20_disjoint.csv"),
              [show(n) for n in sorted((n for n in dis if n["notice"] != CONTROL[0]),
                                       key=lambda n: sha_key("a11", n["notice"]))[:GRADE_N]])
    write_csv(os.path.join(a.out_dir, "publisher_only_mismatch.csv"),
              [show(n) for n in sorted(pub_mis, key=key)])
    write_csv(os.path.join(a.out_dir, "grade20_publisher_only_mismatch.csv"),
              [show(n) for n in sorted(pub_mis, key=lambda n: sha_key("a11p", n["notice"]))[:GRADE_N]])
    write_csv(os.path.join(a.out_dir, "agree_sample_mismatch.csv"),
              [show(n) for n in sorted((n for n in cal_inf if n["cont_p"] < MISMATCH), key=key)])

    both = c["agree"] + c["overlap"] + c["disjoint"]
    s.update({
        "n_records": w.n_records, "n_notices": len(notices), "sides": {k: c[k] for k in SIDES},
        "n_two_source": both, "crossref_totals": totals, "self_links_by_source": dict(w.self_src),
        "other_source_links": w.other_src,
        "notices_rw_self_with_publisher_target": sum(1 for n in notices if n["rw_self"] and n["P"]),
        "disjoint_verdicts": {k: v[k] for k in VERDICTS}, "rw_right_near": near_rw,
        "publisher_right_near": sum(1 for n in pbr if n["near"]),
        "disjoint_near": sum(1 for n in dis if n["near"]),
        "disjoint_p_missing": sum(1 for n in dis if n["p_missing"]),
        "rw_right_p_no_other_evidence": sum(1 for n in rwr if not n["evidence_p"]),
        "publisher_right_r_no_other_evidence": sum(1 for n in pbr if not n["evidence_r"]),
        "oa_rw_right_p_targets": [oa_chk, oa_flag],
        "calibration_agree_sample": {"sampled": len(agree_s), "informative": cal[0], "hi": cal[1],
                                     "below_mismatch": cal[2]},
        "publisher_only": {"notices": len(pub), "informative": len(pub_inf), "mismatch": len(pub_mis)},
        "disjoint_by_publisher": collections.Counter(n["publisher"] for n in dis).most_common(20),
        "rw_right_by_publisher": collections.Counter(n["publisher"] for n in rwr).most_common(20),
        "publisher_right_by_publisher": collections.Counter(n["publisher"] for n in pbr).most_common(20),
        "pub_mismatch_by_publisher": collections.Counter(n["publisher"] for n in pub_mis).most_common(20),
        "n_title_dois": len(dois), "n_titles_found": len(titles), "title_failed": len(tfail),
        "gates": gates, "all_gates_ok": all(g["ok"] for g in gates.values()), "predictions": preds,
        "http": dict(STATS), "elapsed_s": round(time.monotonic() - t0, 1),
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({"sides": s["sides"], "verdicts": s["disjoint_verdicts"],
                      "gates_ok": s["all_gates_ok"],
                      "predictions": {k: x["held"] for k, x in preds.items()}}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
