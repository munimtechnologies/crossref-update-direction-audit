#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Audit 10 (pre-registered in PREREG-10.md): does PubMed link the same notice to the same paper
that the Retraction Watch database names?

Retraction Watch (RW, now published by Crossref) gives, for each retraction, the PubMed ID of the
original paper (OriginalPaperPubMedID, "O") and of the retraction notice (RetractionPubMedID, "N").
PubMed curates its own links: the notice record says "Retraction of <paper>" and the paper record
says "Retraction in <notice>". This script takes every RW row whose RetractionNature is
"Retraction" and whose two PMIDs are both present and different, fetches both PubMed records
(E-utilities esummary, JSON) and classifies each distinct (O, N) pair, first rule that applies:

  o_missing          PubMed returns no record for O
  n_missing          PubMed returns no record for N
  agree_both         N has a retractive link to O and O has a retractive link to N
  agree_one_side     only one of those two links exists
  linked_other_type  O and N are linked, but only with a non-retractive type (erratum, comment...)
  n_targets_other    N has retractive links, but only to other PMIDs (a different paper)
  o_linked_other     O has retractive links, but only to other notices; N has none
  unlinked           neither record has any link to the other, nor the cases above

For n_targets_other pairs it fetches the other target(s) T and asks which paper RW's own DOI and
title describe: `rw_pmid_wrong` (T matches, O does not), `pubmed_link_suspect` (O matches, T does
not) or `undetermined`, once by DOI and once by title words.

No API keys. Sources: gitlab.com/crossref/retraction-watch-data (CSV), eutils.ncbi.nlm.nih.gov
(tool and email set, <= 2.5 requests/s). Usage: python rw_pubmed_link_census.py --out-dir /out
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
UA = "rw-pubmed-link-census/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
TOOL = "mv2-rw-pubmed-link-census"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
RAW = "https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/main/"
PLAN = "PREREG-10.md"
PLAN_MARK = b"Pre-registration 10"
RW_URLS = [
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv",
    "https://api.labs.crossref.org/data/retractionwatch?mailto=" + MAILTO,
]
SUMMARY_BATCH = 200
GRADE_N = 20
CONTROL = ("31662796", "34422117")  # (paper, notice), read by hand 2026-11-10: linked both ways
NOTICE_PUBTYPES = {"retraction notice", "retraction of publication"}
csv.field_size_limit(1 << 24)

CLASSES = ["o_missing", "n_missing", "agree_both", "agree_one_side", "linked_other_type",
           "n_targets_other", "o_linked_other", "unlinked"]
FOUND_CLASSES = CLASSES[2:]


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


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return round(num / den, 4) if den else None


def is_retr_link(rt):
    rt = str(rt or "").strip().lower()
    return (rt.startswith("retraction") or rt.startswith("partial retraction")
            or "retracted and republished" in rt or "retraction and republication" in rt)


def rw_pairs(lines):
    """Distinct (O, N) pairs from RW CSV lines, plus counters.

    Keeps rows whose RetractionNature is 'Retraction' (case-insensitive) with both PMIDs valid.
    O == N rows are counted (same_pmid) and dropped."""
    pairs, st = {}, collections.Counter()
    header_ok = None
    reader = csv.DictReader(lines)
    for row in reader:
        if header_ok is None:
            header_ok = all(k in row for k in ("OriginalPaperPubMedID", "RetractionPubMedID",
                                                "RetractionNature"))
        st["rows"] += 1
        if str(row.get("RetractionNature") or "").strip().lower() != "retraction":
            continue
        st["retraction_rows"] += 1
        o, so = parse_pmid(row.get("OriginalPaperPubMedID"))
        n, sn = parse_pmid(row.get("RetractionPubMedID"))
        st["o_" + so] += 1
        st["n_" + sn] += 1
        if not (o and n):
            continue
        if o == n:
            st["same_pmid"] += 1
            continue
        st["eligible_rows"] += 1
        key = (o, n)
        if key in pairs:
            pairs[key]["rw_rows"] += 1
            continue
        pairs[key] = {
            "o": o, "n": n, "rw_rows": 1,
            "rw_record_id": str(row.get("Record ID") or "").strip(),
            "rw_title": str(row.get("Title") or "")[:200],
            "rw_doi": first_doi(row.get("OriginalPaperDOI")),
            "rw_notice_doi": first_doi(row.get("RetractionDOI")),
            "rw_journal": str(row.get("Journal") or "")[:80],
            "rw_publisher": str(row.get("Publisher") or "")[:80],
            "rw_retraction_date": str(row.get("RetractionDate") or "")[:20],
        }
    st["header_ok"] = 1 if header_ok else 0
    return pairs, st


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


def links_to(a, b):
    """Reftypes on record a that point at record b (by PMID, or by DOI in the citation)."""
    out = set()
    if not a or not b:
        return out
    for rt, pmid, d in a["refs"]:
        if (pmid and pmid == b["pmid"]) or (d and b["doi"] and d == b["doi"]):
            out.add(rt)
    return out


def retr_targets(rec, exclude):
    """PMIDs that rec links with a retractive type, minus `exclude`."""
    if not rec:
        return []
    return sorted({p for rt, p, _ in rec["refs"] if is_retr_link(rt) and p and p not in exclude})


def o_flagged(rec):
    if not rec:
        return False
    if "retracted publication" in rec["pubtype"]:
        return True
    return any(is_retr_link(rt) and rt.endswith(" in") for rt, _, _ in rec["refs"])


def is_notice(rec):
    return bool(rec) and any(p in NOTICE_PUBTYPES for p in rec["pubtype"])


def classify(o, n, recs):
    """(class, other PMIDs) for paper PMID o and notice PMID n, given {pmid: compact record}."""
    ro, rn = recs.get(o), recs.get(n)
    if ro is None:
        return "o_missing", []
    if rn is None:
        return "n_missing", []
    n_to_o = {t for t in links_to(rn, ro) if is_retr_link(t)}
    o_to_n = {t for t in links_to(ro, rn) if is_retr_link(t)}
    if n_to_o and o_to_n:
        return "agree_both", []
    if n_to_o or o_to_n:
        return "agree_one_side", []
    if links_to(rn, ro) or links_to(ro, rn):
        return "linked_other_type", []
    t = retr_targets(rn, {o, n})
    if t:
        return "n_targets_other", t
    t = retr_targets(ro, {o, n})
    if t:
        return "o_linked_other", t
    return "unlinked", []


def adjudicate(pair, others, recs):
    """Which paper do RW's own DOI and title describe: O (PubMed suspect) or a T (RW PMID wrong)?"""
    ro = recs.get(pair["o"]) or {}
    ts = [recs[t] for t in others if recs.get(t)]
    rd = pair.get("rw_doi") or ""
    o_doi = bool(rd) and ro.get("doi") == rd
    t_doi = bool(rd) and any(t.get("doi") == rd for t in ts)
    if t_doi and not o_doi:
        by_doi = "rw_pmid_wrong"
    elif o_doi and not t_doi:
        by_doi = "pubmed_link_suspect"
    else:
        by_doi = "undetermined"
    so = jaccard(pair.get("rw_title"), ro.get("title"))
    st = max([jaccard(pair.get("rw_title"), t.get("title")) for t in ts] or [0.0])
    if st >= 0.6 and so < 0.3:
        by_title = "rw_pmid_wrong"
    elif so >= 0.6 and st < 0.3:
        by_title = "pubmed_link_suspect"
    else:
        by_title = "undetermined"
    return {"by_doi": by_doi, "by_title": by_title, "sim_o": round(so, 3), "sim_t": round(st, 3),
            "o_doi": ro.get("doi", ""), "t_dois": ";".join(t.get("doi", "") for t in ts),
            "o_title": ro.get("title", ""), "t_titles": " || ".join(t.get("title", "")[:120] for t in ts)}


def grade(c, adj, unlinked_o_unflagged, n_pairs, gates):
    """Predictions P1-P8 of PREREG-10.md. c: Counter of classes; adj: list of adjudications."""
    found = sum(c[k] for k in FOUND_CLASSES)
    res = {}

    def put(k, value, ok, note):
        res[k] = {"value": value, "held": ok, "note": note}

    put("P1", n_pairs, 8000 <= n_pairs <= 30000, "eligible distinct (O, N) pairs in 8,000-30,000")
    v = share(c["agree_both"] + c["agree_one_side"], found)
    put("P2", v, v is not None and v >= 0.85, "agree_both + agree_one_side >= 85% of found pairs")
    v = share(c["agree_one_side"], found)
    put("P3", v, v is not None and v <= 0.03, "agree_one_side <= 3% of found pairs")
    v = c["n_targets_other"]
    put("P4", v, 20 <= v <= 600, "n_targets_other pairs in 20-600")
    dd = [a for a in adj if a["by_doi"] != "undetermined"]
    dt = [a for a in adj if a["by_title"] != "undetermined"]
    if len(dd) >= 5 and len(dt) >= 5:
        v1 = share(sum(1 for a in dd if a["by_doi"] == "rw_pmid_wrong"), len(dd))
        v2 = share(sum(1 for a in dt if a["by_title"] == "rw_pmid_wrong"), len(dt))
        put("P5", [v1, v2], v1 >= 0.5 and v2 >= 0.5,
            "rw_pmid_wrong >= 50% of decided n_targets_other pairs, by DOI AND by title")
    else:
        put("P5", [len(dd), len(dt)], None, "inconclusive: fewer than 5 decided pairs by a rule")
    v = sum(1 for a in adj if a["by_doi"] == "pubmed_link_suspect")
    put("P6", v, v >= 5, "pubmed_link_suspect (DOI rule) >= 5 pairs")
    v = share(c["unlinked"], found)
    put("P7", v, v is not None and v >= 0.01, "unlinked >= 1% of found pairs")
    if c["unlinked"] >= 10:
        v = share(unlinked_o_unflagged, c["unlinked"])
        put("P8", v, v >= 0.30, "unlinked pairs whose paper PubMed does not flag >= 30%")
    else:
        put("P8", c["unlinked"], None, "inconclusive: fewer than 10 unlinked pairs")
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
                pairs, st = rw_pairs(f)
            if st["header_ok"]:
                return pairs, st, u
            STATS["rw_badheader"] += 1
        except Exception as e:
            STATS["rw_error"] += 1
            print("RW download failed from %s: %s" % (u, e), file=sys.stderr, flush=True)
    return {}, collections.Counter(), ""


def fetch(pmids, recs):
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
            print("esummary %d/%d" % (i + len(b), len(todo)), flush=True)
    return failed


# ---------------------------------------------------------------- main
FIELDS = ["o", "n", "class", "others", "by_doi", "by_title", "sim_o", "sim_t", "rw_record_id",
          "rw_rows", "rw_doi", "o_doi", "t_dois", "rw_title", "o_title", "t_titles",
          "rw_notice_doi", "n_doi", "n_title", "n_is_notice", "n_pubtype", "o_flagged",
          "rw_journal", "rw_publisher", "rw_retraction_date", "grade", "note"]


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

    pairs, rst, src = load_rw(a.tmp)
    s["rw_source"], s["rw_counts"] = src, dict(rst)
    print("RW %d rows, %d eligible pairs from %s" % (rst["rows"], len(pairs), src), flush=True)

    recs = {}
    want = sorted({p for k in pairs for p in k} | set(CONTROL), key=int)
    failed = fetch(want, recs)
    rows, c, adj = [], collections.Counter(), []
    need_t = {}
    for (o, n), p in pairs.items():
        cl, others = classify(o, n, recs)
        p["class"], p["others"] = cl, others
        c[cl] += 1
        if cl == "n_targets_other":
            need_t[(o, n)] = others
    failed_t = fetch(sorted({t for v in need_t.values() for t in v}, key=int), recs)
    unl_unflagged = 0
    for (o, n), p in pairs.items():
        ro, rn = recs.get(o), recs.get(n)
        p["o_flagged"] = o_flagged(ro) if ro else ""
        p["n_is_notice"] = is_notice(rn) if rn else ""
        p["n_doi"] = (rn or {}).get("doi", "")
        p["n_title"] = (rn or {}).get("title", "")[:120]
        p["n_pubtype"] = ";".join((rn or {}).get("pubtype", []))
        if p["class"] == "n_targets_other":
            j = adjudicate(p, p["others"], recs)
            p.update(j)
            adj.append(j)
        else:
            p["o_title"] = (ro or {}).get("title", "")[:120]
            p["o_doi"] = (ro or {}).get("doi", "")
        if p["class"] == "unlinked" and p["o_flagged"] is False:
            unl_unflagged += 1
        p["others"] = ";".join(p["others"])
        rows.append(p)

    ctl_class, _ = classify(CONTROL[0], CONTROL[1], recs)
    n_ids = len(want)
    gates = {
        "G1_rw_rows": {"value": rst["rows"], "ok": rst["rows"] >= 60000 and bool(rst["header_ok"])},
        "G2_pairs": {"value": len(pairs), "ok": len(pairs) >= 5000},
        "G3_esummary_failed": {"value": failed + failed_t,
                               "ok": (failed + failed_t) <= 0.02 * max(n_ids, 1)},
        "G4_control_pair": {"value": ctl_class, "ok": ctl_class == "agree_both"},
        "G5_plan_live_first": {"value": s["plan_live_at"], "ok": bool(s["plan_live_at"])},
    }
    preds = grade(c, adj, unl_unflagged, len(pairs), gates)

    rows.sort(key=lambda r: (r["class"], int(r["o"]), int(r["n"])))
    for cl in ("n_targets_other", "o_linked_other", "linked_other_type", "agree_one_side",
               "unlinked", "o_missing", "n_missing"):
        write_csv(os.path.join(a.out_dir, "pairs_%s.csv" % cl), [r for r in rows if r["class"] == cl])
    nto = [r for r in rows if r["class"] == "n_targets_other"]
    write_csv(os.path.join(a.out_dir, "grade20_n_targets_other.csv"),
              sorted(nto, key=lambda r: sha_key("a10", r["o"], r["n"]))[:GRADE_N])
    unl = [r for r in rows if r["class"] == "unlinked"]
    write_csv(os.path.join(a.out_dir, "grade20_unlinked.csv"),
              sorted(unl, key=lambda r: sha_key("a10u", r["o"], r["n"]))[:GRADE_N])

    found = sum(c[k] for k in FOUND_CLASSES)
    s.update({
        "n_pairs": len(pairs), "classes": {k: c[k] for k in CLASSES}, "n_found_pairs": found,
        "n_pmids_requested": n_ids, "esummary_failed_ids": failed, "target_failed_ids": failed_t,
        "found_o_flagged": sum(1 for r in rows if r["class"] in FOUND_CLASSES and r["o_flagged"] is True),
        "unlinked_o_unflagged": unl_unflagged,
        "unlinked_n_not_notice": sum(1 for r in unl if r["n_is_notice"] is False),
        "adjudication_by_doi": dict(collections.Counter(j["by_doi"] for j in adj)),
        "adjudication_by_title": dict(collections.Counter(j["by_title"] for j in adj)),
        "n_targets_other_by_publisher": collections.Counter(r["rw_publisher"] for r in nto).most_common(20),
        "unlinked_by_publisher": collections.Counter(r["rw_publisher"] for r in unl).most_common(20),
        "gates": gates, "all_gates_ok": all(g["ok"] for g in gates.values()),
        "predictions": preds, "http": dict(STATS), "elapsed_s": round(time.monotonic() - t0, 1),
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({"pairs": len(pairs), "classes": s["classes"], "gates_ok": s["all_gates_ok"],
                      "predictions": {k: v["held"] for k, v in preds.items()}}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
