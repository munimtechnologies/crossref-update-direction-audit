#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Audit 12 (pre-registered in PREREG-12.md): how many PubMed IDs in the Retraction Watch database
are the right PMID with its last digit(s) cut off?

For every row of the Retraction Watch CSV (any RetractionNature) and for both PMID fields
(OriginalPaperPubMedID = paper side "O", RetractionPubMedID = notice side "N"), the script fetches
the PubMed record (E-utilities esummary, JSON) and asks whether it fits what RW says about that
side:

  doi    PubMed's DOI for the record equals RW's DOI for the same side
  link   the record and the row's other PMID are linked in PubMed (either direction, any type),
         or the record cites RW's DOI for the other side
  title  (paper side only) word-set Jaccard of RW's Title and PubMed's title >= 0.6

A record that fits nothing ("unfit") and whose PMID has <= 7 digits is tested against its
extensions: PMID*10+d (d = 0..9), and for <= 6 digits also PMID*100+dd. Status per row-side:

  absent / malformed   RW has no usable PMID
  missing              PubMed returns no record for it
  fit                  it fits (evidence doi, link or title)
  no_basis             RW gives nothing to check it against
  truncated            exactly one extension fits by doi or link
  ambiguous            more than one extension fits by doi or link (or by title only)
  truncated_probable   no extension fits by doi or link; exactly one fits by title
  unfit_other          unfit and no extension fits (or the PMID already has 8 digits)

No API keys. Sources: gitlab.com/crossref/retraction-watch-data (CSV), eutils.ncbi.nlm.nih.gov
(tool and email set). Usage: python rw_truncated_pmid_census.py --out-dir /out
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
UA = "rw-truncated-pmid-census/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
TOOL = "mv2-rw-truncated-pmid-census"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
RAW = "https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/main/"
PLAN = "PREREG-12.md"
PLAN_MARK = b"Pre-registration 12"
RW_URLS = [
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv",
    "https://api.labs.crossref.org/data/retractionwatch?mailto=" + MAILTO,
]
SUMMARY_BATCH = 200
GRADE_N = 20
OLD_RECORD_ID = 10000
IMPOSSIBLE_YEAR = 2001
IMPOSSIBLE_BELOW = 10000000
# Controls read by hand on 2026-11-11 (gate G3): (RW record id, side, expected status, expected fix)
CONTROLS = [("2154", "O", "truncated", "21633303"),
            ("475", "N", "truncated", "23289124"),
            ("2154", "N", "fit", "")]
NEEDED = ("Record ID", "Title", "OriginalPaperPubMedID", "RetractionPubMedID",
          "OriginalPaperDOI", "RetractionDOI", "RetractionNature")
csv.field_size_limit(1 << 24)


# ---------------------------------------------------------------- pure helpers
def parse_pmid(s):
    """('12345', 'ok') | ('', 'none') | ('', 'malformed') for an RW PubMed ID field."""
    s = str(s if s is not None else "").strip()
    if s in ("", "0", "0.0"):
        return "", "none"
    m = re.fullmatch(r"(\d+)(?:\.0)?", s)
    if not m:
        return "", "malformed"
    v = m.group(1).lstrip("0")
    return (v, "ok") if v else ("", "none")


def norm_doi(d):
    d = str(d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/",
              "http://dx.doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d.strip().rstrip(".")


def first_doi(s):
    for part in re.split(r"[;\s]+", str(s or "")):
        d = norm_doi(part)
        if re.match(r"^10\.\d{4,9}/\S+$", d):
            return d
    return ""


REF_DOI = re.compile(r"doi:\s*(10\.\d{4,9}/\S+)", re.I)


def ref_doi(refsource):
    m = REF_DOI.search(str(refsource or ""))
    return m.group(1).rstrip(".,;").lower() if m else ""


def words(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\b(retracted|retraction|notice of|withdrawn)\b", " ", s)
    return {w for w in re.findall(r"[a-z0-9]+", s) if len(w) > 2}


def jaccard(a, b):
    A, B = words(a), words(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def year_of(s):
    m = re.search(r"(1[89]\d\d|20\d\d)", str(s or ""))
    return int(m.group(1)) if m else None


def int_or_none(s):
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return None


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return round(num / den, 4) if den else None


def candidates(p):
    """PMIDs that p could be a truncation of: one dropped digit (p <= 7 digits), two (p <= 6)."""
    p = str(p)
    if not p.isdigit() or len(p) > 7:
        return []
    v = int(p)
    out = [str(v * 10 + d) for d in range(10)]
    if len(p) <= 6:
        out += [str(v * 100 + d) for d in range(100)]
    return out


def rw_sides(lines):
    """One dict per (RW row, side) that has a valid PMID, plus counters."""
    sides, st = [], collections.Counter()
    header_ok = None
    for row in csv.DictReader(lines):
        if header_ok is None:
            header_ok = all(k in row for k in NEEDED)
        st["rows"] += 1
        o, so = parse_pmid(row.get("OriginalPaperPubMedID"))
        n, sn = parse_pmid(row.get("RetractionPubMedID"))
        base = {
            "record_id": str(row.get("Record ID") or "").strip(),
            "nature": str(row.get("RetractionNature") or "").strip(),
            "title": str(row.get("Title") or "")[:200],
            "o": o, "n": n,
            "o_doi": first_doi(row.get("OriginalPaperDOI")),
            "n_doi": first_doi(row.get("RetractionDOI")),
            "o_year": year_of(row.get("OriginalPaperDate")),
            "journal": str(row.get("Journal") or "")[:80],
            "publisher": str(row.get("Publisher") or "")[:80],
        }
        for side, p, s in (("O", o, so), ("N", n, sn)):
            st["%s_%s" % (side, s)] += 1
            if p:
                d = dict(base)
                d["side"], d["pmid"] = side, p
                sides.append(d)
    st["header_ok"] = 1 if header_ok else 0
    return sides, st


def compact(uid, d):
    """Small record from one esummary result entry, or None if PubMed returned an error."""
    if not isinstance(d, dict) or d.get("error"):
        return None
    doi = ""
    for a in d.get("articleids") or []:
        if isinstance(a, dict) and a.get("idtype") == "doi" and a.get("value"):
            doi = norm_doi(a["value"])
            break
    refs = []
    for r in d.get("references") or []:
        if isinstance(r, dict):
            refs.append((str(r.get("reftype") or "").strip().lower(),
                         str(r.get("pmid") or "").strip(), ref_doi(r.get("refsource"))))
    return {"pmid": str(uid), "doi": doi, "title": str(d.get("title") or "")[:200],
            "pubtype": [str(p).strip().lower() for p in d.get("pubtype") or []], "refs": refs}


def side_info(s):
    """(own DOI, other PMID, other DOI) for a row-side."""
    if s["side"] == "O":
        return s["o_doi"], s["n"], s["n_doi"]
    return s["n_doi"], s["o"], s["o_doi"]


def fit(s, rec, recs):
    """'doi' | 'link' | 'title' | '' : does PubMed record `rec` fit what RW says about side s?"""
    if not rec:
        return ""
    own, other, other_doi = side_info(s)
    if own and rec["doi"] == own:
        return "doi"
    if other and other != rec["pmid"]:
        if any(p == other for _, p, _ in rec["refs"]):
            return "link"
        orec = recs.get(other)
        if orec and any(p == rec["pmid"] for _, p, _ in orec["refs"]):
            return "link"
    if other_doi and other_doi != own and any(d == other_doi for _, _, d in rec["refs"]):
        return "link"
    if s["side"] == "O" and jaccard(s["title"], rec["title"]) >= 0.6:
        return "title"
    return ""


def has_basis(s):
    own, other, other_doi = side_info(s)
    return bool(own or other or other_doi or (s["side"] == "O" and len(words(s["title"])) >= 3))


def judge(s, recs):
    """Status dict for one row-side. recs must already hold the side's PMID, the row's other
    PMID and (for unfit PMIDs) the candidates."""
    rec = recs.get(s["pmid"])
    if rec is None:
        return {"status": "missing", "evidence": "", "fix": ""}
    f = fit(s, rec, recs)
    if f:
        return {"status": "fit", "evidence": f, "fix": ""}
    if not has_basis(s):
        return {"status": "no_basis", "evidence": "", "fix": ""}
    strong, weak = [], []
    for c in candidates(s["pmid"]):
        e = fit(s, recs.get(c), recs)
        if e in ("doi", "link"):
            strong.append((c, e))
        elif e == "title":
            weak.append((c, e))
    if len(strong) == 1:
        return {"status": "truncated", "evidence": strong[0][1], "fix": strong[0][0]}
    if len(strong) > 1:
        return {"status": "ambiguous", "evidence": "doi/link", "fix": ";".join(c for c, _ in strong)}
    if len(weak) == 1:
        return {"status": "truncated_probable", "evidence": "title", "fix": weak[0][0]}
    if len(weak) > 1:
        return {"status": "ambiguous", "evidence": "title", "fix": ";".join(c for c, _ in weak)}
    return {"status": "unfit_other", "evidence": "", "fix": ""}


def needs_candidates(s, recs):
    rec = recs.get(s["pmid"])
    return (rec is not None and not fit(s, rec, recs) and has_basis(s)
            and len(s["pmid"]) <= 7)


def is_impossible(s):
    """Paper side, paper dated 2001 or later, PMID below 10,000,000 (assigned before ~1999)."""
    return (s["side"] == "O" and s.get("o_year") is not None and s["o_year"] >= IMPOSSIBLE_YEAR
            and int(s["pmid"]) < IMPOSSIBLE_BELOW)


def is_old(s):
    v = int_or_none(s.get("record_id"))
    return v is not None and v < OLD_RECORD_ID


def grade(sides, gates):
    """Predictions P1-P6 of PREREG-12.md from judged row-sides (each has 'status')."""
    c = collections.Counter(s["status"] for s in sides)
    res = {}

    def put(k, value, ok, note):
        res[k] = {"value": value, "held": ok, "note": note}

    tr = [s for s in sides if s["status"] == "truncated"]
    put("P1", len(tr), 40 <= len(tr) <= 1000, "confirmed truncations (row-sides) in 40-1,000")
    one = sum(1 for s in tr if len(s["fix"]) == len(s["pmid"]) + 1 and len(s["fix"]) == 8)
    v = share(one, len(tr))
    put("P2", v, v is not None and v >= 0.8,
        ">= 80% of confirmed truncations are an 8-digit PMID missing one digit")
    judged = [s for s in sides if s["status"] not in ("missing",)]
    old = [s for s in judged if is_old(s)]
    new = [s for s in judged if not is_old(s)]
    r_old = share(sum(1 for s in old if s["status"] == "truncated"), len(old))
    r_new = share(sum(1 for s in new if s["status"] == "truncated"), len(new))
    if r_old is None or r_new is None:
        put("P3", [r_old, r_new], None, "inconclusive: an empty group")
    else:
        ok = (r_old > 0 and r_new == 0) or (r_new > 0 and r_old >= 5 * r_new)
        put("P3", [r_old, r_new], ok,
            "truncation rate for RW record IDs < 10,000 is >= 5x the rate for IDs >= 10,000")
    imp = [s for s in sides if is_impossible(s)]
    if len(imp) >= 10:
        v = share(sum(1 for s in imp if s["status"] == "truncated"), len(imp))
        put("P4", v, v >= 0.7, ">= 70% of 'impossible' paper PMIDs are confirmed truncations")
    else:
        put("P4", len(imp), None, "inconclusive: fewer than 10 impossible paper PMIDs")
    base = [s for s in sides if s["status"] not in ("missing", "no_basis")]
    v = share(c["fit"], len(base))
    put("P5", v, v is not None and v >= 0.97,
        "fit >= 97% of row-sides that PubMed returns and RW gives a basis for")
    put("P6", [c["unfit_other"], len(tr)], c["unfit_other"] >= len(tr),
        "unfit_other row-sides >= confirmed truncations")
    if not all(g.get("ok") for g in gates.values()):
        for k in res:
            res[k]["note"] += " (a gate failed: reported descriptively, not graded)"
    return res


# ---------------------------------------------------------------- network
STATS = collections.Counter()
_LAST = {}


def http(url, data=None, tries=6, timeout=120, gap=0.4, host="x"):
    delay = 5
    last = -1
    for _ in range(tries):
        wait = _LAST.get(host, 0.0) + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST[host] = time.monotonic()
        body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, headers={"User-Agent": UA,
                                                              "Cache-Control": "no-cache"})
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


def load_rw(tmp):
    for u in RW_URLS:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            with open(tmp, encoding="utf-8-sig", errors="replace", newline="") as f:
                sides, st = rw_sides(f)
            if st["header_ok"]:
                return sides, st, u
            STATS["rw_badheader"] += 1
        except Exception as e:
            STATS["rw_error"] += 1
            print("RW download failed from %s: %s" % (u, e), file=sys.stderr, flush=True)
    return [], collections.Counter(), ""


def fetch(pmids, recs, label):
    """Fill recs {pmid: compact or None}; returns the number of PMIDs whose batch failed."""
    failed = 0
    todo = [p for p in pmids if p not in recs]
    for i in range(0, len(todo), SUMMARY_BATCH):
        b = todo[i:i + SUMMARY_BATCH]
        data = {"db": "pubmed", "retmode": "json", "id": ",".join(b), "tool": TOOL, "email": MAILTO}
        st, body = http(EUTILS + "esummary.fcgi", data=data, host="ncbi", gap=0.4)
        try:
            res = json.loads(body.decode("utf-8")).get("result") if st == 200 else None
        except (ValueError, UnicodeDecodeError, AttributeError):
            res = None
        if not isinstance(res, dict):
            failed += len(b)
            STATS["esummary_batch_failed"] += 1
            continue
        for p in b:
            recs[p] = compact(p, res.get(p))
        if (i // SUMMARY_BATCH) % 25 == 0:
            print("%s esummary %d/%d" % (label, i + len(b), len(todo)), flush=True)
    return failed


# ---------------------------------------------------------------- main
FIELDS = ["record_id", "side", "pmid", "status", "evidence", "fix", "nature", "o", "n",
          "o_doi", "n_doi", "o_year", "title", "pm_doi", "pm_title", "fix_doi", "fix_title",
          "journal", "publisher", "grade", "note"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-min", type=int, default=120)
    ap.add_argument("--tmp", default="/tmp/retraction_watch.csv")
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

    sides, rst = [], collections.Counter()
    sides, rst, src = load_rw(a.tmp)
    s["rw_source"], s["rw_counts"] = src, dict(rst)
    print("RW %d rows, %d row-sides with a PMID from %s" % (rst["rows"], len(sides), src), flush=True)

    recs = {}
    want = sorted({x["pmid"] for x in sides} | {x["o"] for x in sides if x["o"]}
                  | {x["n"] for x in sides if x["n"]}, key=int)
    failed = fetch(want, recs, "base")
    cand = sorted({c for x in sides if needs_candidates(x, recs) for c in candidates(x["pmid"])}
                  - set(recs), key=int)
    s["n_candidates"] = len(cand)
    failed_c = fetch(cand, recs, "candidates")

    for x in sides:
        x.update(judge(x, recs))
        r = recs.get(x["pmid"]) or {}
        x["pm_doi"], x["pm_title"] = r.get("doi", ""), r.get("title", "")[:150]
        fr = recs.get(x["fix"].split(";")[0]) if x["fix"] else None
        x["fix_doi"] = (fr or {}).get("doi", "")
        x["fix_title"] = (fr or {}).get("title", "")[:150]

    ctl = {}
    for rid, side, want_status, want_fix in CONTROLS:
        hit = [x for x in sides if x["record_id"] == rid and x["side"] == side]
        got = (hit[0]["status"], hit[0]["fix"]) if hit else ("absent", "")
        ctl["%s_%s" % (rid, side)] = {"got": got, "ok": got == (want_status, want_fix)}
    n_ids = len(want) + len(cand)
    gates = {
        "G1_rw_rows": {"value": rst["rows"], "ok": rst["rows"] >= 60000 and bool(rst["header_ok"])},
        "G2_esummary_failed": {"value": failed + failed_c,
                               "ok": (failed + failed_c) <= 0.02 * max(n_ids, 1)},
        "G3_controls": {"value": ctl, "ok": all(v["ok"] for v in ctl.values())},
        "G4_plan_live_first": {"value": s["plan_live_at"], "ok": bool(s["plan_live_at"])},
    }
    preds = grade(sides, gates)

    sides.sort(key=lambda x: (x["status"], int_or_none(x["record_id"]) or 0, x["side"]))
    tr_like = [x for x in sides if x["status"] in ("truncated", "truncated_probable", "ambiguous")]
    write_csv(os.path.join(a.out_dir, "truncated.csv"), tr_like)
    uo = [x for x in sides if x["status"] == "unfit_other"]
    write_csv(os.path.join(a.out_dir, "unfit_other.csv"), uo)
    write_csv(os.path.join(a.out_dir, "missing.csv"), [x for x in sides if x["status"] == "missing"])
    write_csv(os.path.join(a.out_dir, "impossible.csv"), [x for x in sides if is_impossible(x)])
    tr = [x for x in sides if x["status"] == "truncated"]
    write_csv(os.path.join(a.out_dir, "grade20_truncated.csv"),
              sorted(tr, key=lambda x: sha_key("a12", x["record_id"], x["side"]))[:GRADE_N])
    write_csv(os.path.join(a.out_dir, "grade20_unfit_other.csv"),
              sorted(uo, key=lambda x: sha_key("a12u", x["record_id"], x["side"]))[:GRADE_N])

    s.update({
        "n_row_sides": len(sides), "n_pmids_requested": len(want),
        "esummary_failed_ids": failed, "candidate_failed_ids": failed_c,
        "status": dict(collections.Counter(x["status"] for x in sides)),
        "status_by_side": {sd: dict(collections.Counter(x["status"] for x in sides if x["side"] == sd))
                           for sd in ("O", "N")},
        "fit_evidence": dict(collections.Counter(x["evidence"] for x in sides if x["status"] == "fit")),
        "truncated_by_nature": dict(collections.Counter(x["nature"] for x in tr)),
        "truncated_distinct_pmids": len({x["pmid"] for x in tr}),
        "truncated_old_records": sum(1 for x in tr if is_old(x)),
        "truncated_by_publisher": collections.Counter(x["publisher"] for x in tr).most_common(20),
        "unfit_other_by_publisher": collections.Counter(x["publisher"] for x in uo).most_common(20),
        "impossible": len([x for x in sides if is_impossible(x)]),
        "gates": gates, "all_gates_ok": all(g["ok"] for g in gates.values()),
        "predictions": preds, "http": dict(STATS), "elapsed_s": round(time.monotonic() - t0, 1),
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({"row_sides": len(sides), "status": s["status"], "gates_ok": s["all_gates_ok"],
                      "predictions": {k: v["held"] for k, v in preds.items()}}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
