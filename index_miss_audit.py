#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Made with AI agents working in the name of MV2 of Munim, Inc. (mv2@munimtech.com).
"""Audit 6: do other indexes flag the retractions that Crossref's update metadata hides?

Input: the 294 notices of audit 4b (results/audit4b/notices_hidden.csv at commit f1f5aef),
titled as retractions or withdrawals but deposited with a non-retractive update type, whose
papers had no retractive update from any source in Crossref on 2026-11-09.

For every paper those notices point at (the notice itself when it only points at itself),
this script reads four sources and records whether each one flags the paper as retracted:

  cr  Crossref REST API, live: any `updated-by` entry of a retractive type (any source);
  rw  the Retraction Watch CSV (Crossref's GitLab copy), read directly: a row whose
      OriginalPaperDOI is the paper and whose RetractionNature is "Retraction";
  oa  OpenAlex: `is_retracted`;
  pm  PubMed (by DOI): publication type "Retracted Publication" or a "Retraction in" link.

Predictions and gates are in PREREG-6.md and are graded by grade() below.
"""
import argparse
import collections
import csv
import hashlib
import io
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
UA = "index-miss-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
INPUT_COMMIT = "f1f5aefc0887215ba03e87992c8719a061db3b91"
INPUT_PATH = "results/audit4b/notices_hidden.csv"
INPUT_URLS = [
    "https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/%s/%s"
    % (INPUT_COMMIT, INPUT_PATH),
]
RW_URLS = [
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv",
    "https://api.labs.crossref.org/data/retractionwatch?mailto=" + MAILTO,
]
CR_API = "https://api.crossref.org/works/"
OA_API = "https://api.openalex.org/works"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
OA_BATCH = 40
PM_BATCH = 100
GRADE_N = 20
EXPECTED_NOTICES = 294

# Notices whose titles are topics, not notices (found while grading audit 4b; NOTE-4b.md).
TOPIC_NOTICES = {
    "10.1002/14651858.cd012540.pub2", "10.1002/14651858.cd012572.pub2",
    "10.1002/14651858.cd012572.pub3", "10.1017/apj.2026.10053",
}

RETRACTIVE = {"retraction", "partial_retraction", "withdrawal", "removal"}
MARK = re.compile(r"\bretract(?:ed|ion)?\b|\bwithdrawn\b")
csv.field_size_limit(1 << 24)


# ---------------------------------------------------------------- pure helpers
def norm_doi(d):
    d = str(d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/",
              "http://dx.doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d.strip()


def norm_type(t):
    return re.sub(r"[\s\-]+", "_", str(t or "").strip().lower())


def is_retractive(t):
    t = norm_type(t)
    return t in RETRACTIVE or t.startswith("retra") or "withdraw" in t


def first(v):
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


def ascii_lower(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")
    return s.lower()


def title_marked(title):
    """True when a paper's own title says it is retracted or withdrawn."""
    return bool(MARK.search(ascii_lower(title)))


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return (num / den) if den else None


def papers_from_notices(rows):
    """{paper DOI: dict}, plus the excluded topic notices.

    A paper is every target of a notice other than the notice itself; when a notice only
    points at itself, the notice record is the paper (it was retitled in place)."""
    papers, excluded = {}, []
    for r in rows:
        rec = norm_doi(r.get("record"))
        if not rec:
            continue
        if rec in TOPIC_NOTICES:
            excluded.append(rec)
            continue
        ts = [norm_doi(t) for t in str(r.get("targets") or "").split(";")]
        ts = [t for t in ts if t]
        others = [t for t in ts if t != rec]
        for t in (others or [rec]):
            p = papers.setdefault(t, {
                "doi": t, "notices": [], "publisher": str(r.get("publisher") or ""),
                "notice_year": str(r.get("year") or ""), "self_paper": t == rec})
            if rec not in p["notices"]:
                p["notices"].append(rec)
    return papers, excluded


def crossref_status(msg):
    ups = [u for u in (msg.get("updated-by") or []) if isinstance(u, dict)]
    retr = [u for u in ups if is_retractive(u.get("type"))]
    return {
        "cr_found": True,
        "cr_title": first(msg.get("title"))[:200],
        "cr_type": str(msg.get("type") or ""),
        "cr_has_updated_by": bool(ups),
        "cr_update_types": ";".join(sorted({norm_type(u.get("type")) for u in ups})),
        "cr_flagged": bool(retr),
        "cr_flag_sources": ";".join(sorted({str(u.get("source") or "") for u in retr})),
    }


def rw_index(text_lines):
    """Index the Retraction Watch CSV: original DOI -> natures, notice DOI -> natures."""
    orig = collections.defaultdict(set)
    notice = collections.defaultdict(set)
    n = 0
    for row in csv.DictReader(text_lines):
        n += 1
        nature = str(row.get("RetractionNature") or "").strip()
        for d in re.split(r"[;\s]+", str(row.get("OriginalPaperDOI") or "")):
            d = norm_doi(d)
            if d.startswith("10."):
                orig[d].add(nature)
        for d in re.split(r"[;\s]+", str(row.get("RetractionDOI") or "")):
            d = norm_doi(d)
            if d.startswith("10."):
                notice[d].add(nature)
    return orig, notice, n


def rw_status(paper, orig, notice):
    nat = orig.get(paper["doi"], set())
    known = any(norm_doi(x) in notice for x in paper["notices"])
    return {
        "rw_natures": ";".join(sorted(nat)),
        "rw_flagged": any(x.lower() == "retraction" for x in nat),
        "rw_notice_known": known,
    }


def openalex_parse(obj):
    out = {}
    for w in (obj or {}).get("results") or []:
        d = norm_doi(w.get("doi"))
        if d:
            out[d] = {"oa_found": True, "oa_retracted": bool(w.get("is_retracted")),
                      "oa_cites": w.get("cited_by_count")}
    return out


def pubmed_doi(rec):
    for a in rec.get("articleids") or []:
        if isinstance(a, dict) and str(a.get("idtype")) == "doi":
            return norm_doi(a.get("value"))
    return ""


def pubmed_flag(rec):
    pts = [str(p) for p in rec.get("pubtype") or []]
    rtypes = sorted({str(r.get("reftype") or "") for r in rec.get("references") or []
                     if isinstance(r, dict)})
    retracted_pt = "Retracted Publication" in pts
    retraction_in = any(t.lower().startswith(("retraction in", "partial retraction in"))
                        for t in rtypes)
    return {
        "pm_found": True, "pm_pmid": str(rec.get("uid") or ""),
        "pm_pubtypes": ";".join(pts), "pm_reftypes": ";".join(rtypes),
        "pm_retracted_type": retracted_pt, "pm_retraction_in": retraction_in,
        "pm_flagged": retracted_pt or retraction_in,
    }


def judge(p):
    flags = [p.get(k) is True for k in ("cr_flagged", "rw_flagged", "oa_retracted", "pm_flagged")]
    p["n_flags"] = sum(flags)
    p["missed_by_all"] = not any(flags)
    p["missed_by_all_held"] = (p["missed_by_all"] and p.get("cr_found") is True
                               and p.get("oa_found") is True)
    return p


def _rate(rows, key):
    return share(sum(1 for r in rows if r.get(key) is True), len(rows))


def grade(papers, gates):
    """Grade the eight automatic predictions of PREREG-6.md (P9 is graded by hand)."""
    allp = [p for p in papers if p.get("cr_found") is True]
    A = [p for p in allp if p.get("cr_flagged") is not True]
    Aoa = [p for p in A if p.get("oa_found") is True]
    Apm = [p for p in A if p.get("pm_found") is True]
    marked = [p for p in Aoa if p.get("title_marked") is True]
    plain = [p for p in Aoa if p.get("title_marked") is not True]
    held = [p for p in A if p.get("missed_by_all_held") is True]
    res = {}

    def put(k, value, ok, note=""):
        res[k] = {"value": value, "held": ok, "note": note}

    v = share(len(A), len(allp))
    put("P1", v, v is not None and v >= 0.90, "share of papers still unflagged in live Crossref >= 0.90")
    v = _rate(A, "rw_flagged")
    put("P2", v, v is not None and v < 0.20, "share of A that the RW CSV lists as retracted < 0.20")
    v = share(sum(1 for p in Aoa if p.get("oa_retracted") is not True), len(Aoa))
    put("P3", v, v is not None and v >= 0.40, "share of A in OpenAlex with is_retracted false >= 0.40")
    if len(marked) >= 10 and len(plain) >= 10:
        v = _rate(marked, "oa_retracted") - _rate(plain, "oa_retracted")
        put("P4", v, v >= 0.30, "OpenAlex flag rate, retitled minus not retitled >= 0.30")
    else:
        put("P4", None, None, "inconclusive: fewer than 10 papers in a group")
    v = share(len(Apm), len(A))
    put("P5", v, v is not None and v < 0.40, "share of A found in PubMed by DOI < 0.40")
    if len(Apm) >= 10:
        v = share(sum(1 for p in Apm if p.get("pm_flagged") is not True), len(Apm))
        put("P6", v, v >= 0.30, "share of A in PubMed with no retraction flag >= 0.30")
    else:
        put("P6", None, None, "inconclusive: fewer than 10 papers in PubMed")
    put("P7", len(held), len(held) >= 60, "papers missed by every source (held by Crossref and OpenAlex) >= 60")
    n20 = sum(1 for p in held if isinstance(p.get("oa_cites"), int) and p["oa_cites"] >= 20)
    put("P8", n20, n20 >= 10, "missed-by-all papers with >= 20 OpenAlex citations >= 10")
    if not all(g.get("ok") for g in gates.values()):
        for k in res:
            res[k]["note"] += " (a gate failed: the audit is inconclusive)"
    return res


# ---------------------------------------------------------------- network
STATS = collections.Counter()
_LAST = collections.defaultdict(float)


def http_get(url, tries=5, timeout=120, gap=0.5, host="x"):
    delay = 5
    last = -1
    for _ in range(tries):
        wait = _LAST[host] + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST[host] = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                STATS["%s_%d" % (host, r.status)] += 1
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = e.code
            STATS["%s_%d" % (host, e.code)] += 1
            if e.code in (400, 404, 410):
                return e.code, b""
            time.sleep(delay)
            delay = min(delay * 2, 120)
        except Exception:
            STATS["%s_neterr" % host] += 1
            time.sleep(delay)
            delay = min(delay * 2, 120)
    return last, b""


_FAILS = collections.Counter()
BREAK_AFTER = 4  # consecutive failed calls before a host is given up (keeps the job in time)


def get_json(url, host, gap):
    if _FAILS[host] >= BREAK_AFTER:
        STATS["%s_skipped_breaker" % host] += 1
        return None
    st, body = http_get(url, host=host, gap=gap)
    if st not in (200, 404):
        _FAILS[host] += 1
    else:
        _FAILS[host] = 0
    if st != 200:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError:
        STATS["%s_badjson" % host] += 1
        return None


def load_input():
    for u in INPUT_URLS:
        st, body = http_get(u, host="gh", gap=1.0)
        if st == 200 and body:
            text = body.decode("utf-8-sig")
            return list(csv.DictReader(io.StringIO(text))), u
    return [], ""


def load_rw(tmp_path):
    for u in RW_URLS:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp_path, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            with open(tmp_path, encoding="utf-8-sig", errors="replace", newline="") as f:
                head = f.readline()
                if "OriginalPaperDOI" not in head:
                    STATS["rw_badheader"] += 1
                    continue
                f.seek(0)
                orig, notice, n = rw_index(f)
            return orig, notice, n, u
        except Exception as e:
            STATS["rw_error"] += 1
            print("RW download failed from %s: %s" % (u, e), file=sys.stderr, flush=True)
    return {}, {}, 0, ""


def crossref_lookup(papers):
    for i, p in enumerate(papers.values()):
        url = "%s%s?mailto=%s" % (CR_API, urllib.parse.quote(p["doi"], safe="/"), MAILTO)
        obj = get_json(url, "cr", 0.5)
        if obj and isinstance(obj.get("message"), dict):
            p.update(crossref_status(obj["message"]))
        else:
            p["cr_found"] = False
        if i % 50 == 0:
            print("crossref %d/%d" % (i + 1, len(papers)), flush=True)


def openalex_url(dois):
    f = "doi:" + "|".join(urllib.parse.quote(d, safe="/()") for d in dois)
    return ("%s?filter=%s&select=doi,is_retracted,cited_by_count&per-page=%d&mailto=%s"
            % (OA_API, f, OA_BATCH + 10, MAILTO))


def openalex_lookup(papers):
    dois = sorted(papers)
    batchable = [d for d in dois if "|" not in d and "," not in d]
    STATS["oa_unbatchable"] += len(dois) - len(batchable)
    got = {}
    for i in range(0, len(batchable), OA_BATCH):
        b = batchable[i:i + OA_BATCH]
        obj = get_json(openalex_url(b), "oa", 1.0)
        if obj is not None:
            got.update(openalex_parse(obj))
            continue
        STATS["oa_batch_failed"] += 1
        for d in b:  # one bad DOI must not lose the whole batch
            obj = get_json(openalex_url([d]), "oa", 1.0)
            if obj is not None:
                got.update(openalex_parse(obj))
    for d, p in papers.items():
        if d in got:
            p.update(got[d])
        else:
            p.setdefault("oa_found", False)


def pubmed_lookup(papers):
    want = {}
    for i, (d, p) in enumerate(papers.items()):
        term = urllib.parse.quote('"%s"[doi]' % d, safe="")
        url = "%sesearch.fcgi?db=pubmed&retmode=json&retmax=5&term=%s&tool=index-miss-audit&email=%s" % (
            EUTILS, term, MAILTO)
        obj = get_json(url, "pm", 0.4)
        if obj is None:
            p["pm_error"] = True
            continue
        ids = ((obj.get("esearchresult") or {}).get("idlist")) or []
        for pmid in ids[:5]:
            want.setdefault(str(pmid), set()).add(d)
        if i % 50 == 0:
            print("pubmed esearch %d/%d" % (i + 1, len(papers)), flush=True)
    pmids = sorted(want)
    for i in range(0, len(pmids), PM_BATCH):
        b = pmids[i:i + PM_BATCH]
        url = "%sesummary.fcgi?db=pubmed&retmode=json&id=%s&tool=index-miss-audit&email=%s" % (
            EUTILS, ",".join(b), MAILTO)
        obj = get_json(url, "pm", 0.4)
        res = (obj or {}).get("result") or {}
        for pmid in b:
            rec = res.get(pmid)
            if not isinstance(rec, dict):
                continue
            rd = pubmed_doi(rec)
            for d in want[pmid]:
                if rd == d and not papers[d].get("pm_found"):
                    papers[d].update(pubmed_flag(rec))
    for p in papers.values():
        p.setdefault("pm_found", False)


# ---------------------------------------------------------------- main
PAPER_FIELDS = [
    "doi", "notices", "publisher", "notice_year", "self_paper", "cr_found", "cr_title", "cr_type",
    "title_marked", "cr_has_updated_by", "cr_update_types", "cr_flagged", "cr_flag_sources",
    "rw_natures", "rw_flagged", "rw_notice_known", "oa_found", "oa_retracted", "oa_cites",
    "pm_found", "pm_pmid", "pm_pubtypes", "pm_reftypes", "pm_retracted_type",
    "pm_retraction_in", "pm_flagged", "n_flags", "missed_by_all", "missed_by_all_held",
]


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tmp", default="/tmp/retraction_watch.csv")
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()

    rows, src = load_input()
    papers, excluded = papers_from_notices(rows)
    print("notices %d from %s, papers %d, excluded topic notices %d"
          % (len(rows), src, len(papers), len(excluded)), flush=True)

    orig, notice, rw_rows, rw_src = load_rw(a.tmp)
    print("retraction watch rows %d from %s" % (rw_rows, rw_src), flush=True)
    for p in papers.values():
        p.update(rw_status(p, orig, notice))
    orig = notice = None

    crossref_lookup(papers)
    openalex_lookup(papers)
    pubmed_lookup(papers)

    for p in papers.values():
        p["title_marked"] = title_marked(p.get("cr_title", "")) if p.get("cr_found") else ""
        judge(p)
        p["notices"] = ";".join(p["notices"])

    plist = sorted(papers.values(), key=lambda p: (p["publisher"], p["doi"]))
    found = [p for p in plist if p.get("cr_found") is True]
    A = [p for p in found if p.get("cr_flagged") is not True]
    pm_err = sum(1 for p in plist if p.get("pm_error"))
    gates = {
        "G1_input_rows": {"value": len(rows), "ok": len(rows) == EXPECTED_NOTICES},
        "G2_papers": {"value": len(plist), "ok": len(plist) >= 280},
        "G3_crossref_found": {"value": share(len(found), len(plist)),
                              "ok": (share(len(found), len(plist)) or 0) >= 0.95},
        "G4_updated_by_present": {
            "value": share(sum(1 for p in found if p.get("cr_has_updated_by")), len(found)),
            "ok": (share(sum(1 for p in found if p.get("cr_has_updated_by")), len(found)) or 0) >= 0.80},
        "G5_rw_rows": {"value": rw_rows, "ok": rw_rows >= 50000},
        "G6_openalex_found": {"value": share(sum(1 for p in A if p.get("oa_found")), len(A)),
                              "ok": (share(sum(1 for p in A if p.get("oa_found")), len(A)) or 0) >= 0.70},
        "G7_pubmed_errors": {"value": pm_err, "ok": pm_err <= 0.05 * max(len(plist), 1)},
    }
    preds = grade(plist, gates)

    held = [p for p in plist if p.get("missed_by_all_held") is True and p.get("cr_flagged") is not True]
    write_csv(os.path.join(a.out_dir, "papers.csv"), plist, PAPER_FIELDS)
    write_csv(os.path.join(a.out_dir, "missed_by_all.csv"), held, PAPER_FIELDS)
    sample = sorted(held, key=lambda p: sha_key("g6", p["doi"]))[:GRADE_N]
    write_csv(os.path.join(a.out_dir, "grade20.csv"), sample, PAPER_FIELDS + ["grade", "note"])

    by_pub = collections.Counter(p["publisher"] for p in held)
    summary = {
        "preregistered": "PREREG-6.md", "input": src, "rw_source": rw_src,
        "n_notices": len(rows), "excluded_topic_notices": excluded,
        "n_papers": len(plist), "n_crossref_found": len(found), "n_still_unflagged_A": len(A),
        "A_flagged_by": {
            "rw": sum(1 for p in A if p.get("rw_flagged") is True),
            "openalex": sum(1 for p in A if p.get("oa_retracted") is True),
            "pubmed": sum(1 for p in A if p.get("pm_flagged") is True),
        },
        "A_rw_notice_known": sum(1 for p in A if p.get("rw_notice_known") is True),
        "A_rw_any_nature": dict(collections.Counter(
            n for p in A for n in str(p.get("rw_natures") or "").split(";") if n)),
        "A_openalex_found": sum(1 for p in A if p.get("oa_found") is True),
        "A_pubmed_found": sum(1 for p in A if p.get("pm_found") is True),
        "A_title_marked": sum(1 for p in A if p.get("title_marked") is True),
        "n_missed_by_all_held": len(held),
        "missed_by_all_held_by_publisher": by_pub.most_common(30),
        "crossref_flagged_now_sources": dict(collections.Counter(
            p.get("cr_flag_sources") for p in found if p.get("cr_flagged") is True)),
        "gates": gates, "all_gates_ok": all(g["ok"] for g in gates.values()),
        "predictions": preds, "http": dict(STATS),
        "elapsed_s": round(time.monotonic() - t0, 1),
    }
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({"gates_ok": summary["all_gates_ok"], "A": len(A),
                      "missed_by_all_held": len(held),
                      "predictions": {k: v["held"] for k, v in preds.items()}}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
