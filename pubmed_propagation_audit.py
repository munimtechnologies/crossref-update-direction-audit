#!/usr/bin/env python3
# Copyright 2026 MV2, Munim, Inc. (mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Audit 8: does PubMed show as retracted the papers whose only 'retraction' in Crossref is a
retracted or withdrawn correction (audit 7's only_via_rc list)? See PREREG-8.md."""
import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

SRC = ("https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/"
       "main/results/audit7/only_via_rc.csv")
EU = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
UA = "mv2-audit8/1.0 (mailto:mv2@munimtech.com)"
STATS = {"ok": 0, "err": 0}

# G3 instrument cases, read by hand on 2026-11-10 (disclosed in PREREG-8.md)
G3_FLAGGED_VIA_RC = ["10.1016/j.amjmed.2016.08.025", "10.1016/j.toxrep.2021.04.002"]
G3_NOT_FLAGGED = ["10.1016/j.scr.2014.07.005"]


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                STATS["ok"] += 1
                return r.read().decode("utf-8")
        except Exception:  # network errors are counted, not fatal
            STATS["err"] += 1
            time.sleep(2 * (i + 1))
    return None


def norm(d):
    d = (d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d


def load_targets(text):
    """only_via_rc.csv text -> {target: {"target", "notices", "utypes"}}."""
    targets = {}
    for r in csv.DictReader(io.StringIO(text)):
        t = norm(r.get("target"))
        if not t:
            continue
        g = targets.setdefault(t, {"target": t, "notices": set(), "utypes": set()})
        g["notices"].add(norm(r.get("notice")))
        g["utypes"].add((r.get("utype") or "").strip())
    return targets


def group(utypes):
    return "retraction" if "retraction" in utypes else "other"


def esearch_ids(js):
    try:
        return [str(x) for x in json.loads(js)["esearchresult"]["idlist"]]
    except Exception:
        return None


def summary_doc(doc):
    doi = ""
    for a in doc.get("articleids", []) or []:
        if a.get("idtype") == "doi":
            doi = norm(a.get("value"))
    refs = [(x.get("reftype", ""), str(x.get("pmid", ""))) for x in (doc.get("references") or [])]
    return {"uid": str(doc.get("uid", "")), "doi": doi, "pubtype": list(doc.get("pubtype") or []),
            "title": doc.get("title", ""), "refs": refs}


def esummary_docs(js):
    try:
        res = json.loads(js)["result"]
    except Exception:
        return None
    return {u: summary_doc(res[u]) for u in res.get("uids", []) if u in res}


def classify(info, doc, linked):
    """One target. doc: its PubMed summary or None. linked: {pmid: summary} of linked notices."""
    notices = info["notices"]
    row = {"target": info["target"], "group": group(info["utypes"]),
           "notices": ";".join(sorted(notices)), "pm_found": doc is not None, "pmid": "",
           "retracted_type": False, "rin_pmids": "", "rin_dois": "", "ein_dois": "",
           "flagged": False, "rin_is_rc": False, "rin_other": False, "ein_is_rc": False}
    if doc is None:
        return row
    rin = [p for t, p in doc["refs"] if t == "Retraction in"]
    ein = [p for t, p in doc["refs"] if t == "Erratum in"]
    rin_dois = [linked[p]["doi"] for p in rin if p in linked]
    ein_dois = [linked[p]["doi"] for p in ein if p in linked]
    row.update({
        "pmid": doc["uid"],
        "retracted_type": "Retracted Publication" in doc["pubtype"],
        "rin_pmids": ";".join(rin), "rin_dois": ";".join(rin_dois), "ein_dois": ";".join(ein_dois),
        "rin_is_rc": any(d in notices for d in rin_dois),
        "rin_other": any(d and d not in notices for d in rin_dois),
        "ein_is_rc": any(d in notices for d in ein_dois),
    })
    row["flagged"] = row["retracted_type"] or bool(rin)
    return row


def share(a, b):
    return round(a / b, 4) if b else None


def summarize(rows, n_search_fail):
    found = [r for r in rows if r["pm_found"]]
    flagged = [r for r in found if r["flagged"]]
    with_rin = [r for r in flagged if r["rin_dois"]]
    by_group = {}
    for g in ("retraction", "other"):
        f = [r for r in found if r["group"] == g]
        by_group[g] = [len(f), sum(1 for r in f if r["flagged"])]
    s = {
        "n_targets": len(rows), "n_search_fail": n_search_fail, "n_found": len(found),
        "n_flagged": len(flagged), "share_flagged_found": share(len(flagged), len(found)),
        "found_flagged_by_group": by_group,
        "n_flagged_with_rin_doi": len(with_rin),
        "n_rin_is_rc": sum(1 for r in with_rin if r["rin_is_rc"]),
        "share_rin_is_rc": share(sum(1 for r in with_rin if r["rin_is_rc"]), len(with_rin)),
        "n_rin_other": sum(1 for r in found if r["rin_other"]),
        "n_ein_is_rc": sum(1 for r in found if r["ein_is_rc"]),
        "flagged_targets": sorted(r["target"] for r in flagged),
    }
    return s


def grade(s, rows):
    by_t = {r["target"]: r for r in rows}
    g1 = s["n_targets"] >= 60
    g2 = s["n_search_fail"] <= 0.05 * max(s["n_targets"], 1)
    g3 = (all(by_t.get(t, {}).get("flagged") and by_t[t]["rin_is_rc"] for t in G3_FLAGGED_VIA_RC)
          and all(by_t.get(t, {}).get("pm_found") and not by_t[t]["flagged"] for t in G3_NOT_FLAGGED))
    gates = {"G1_targets_ge_60": g1, "G2_search_fail_le_5pct": g2, "G3_instrument": bool(g3)}
    rg, og = s["found_flagged_by_group"]["retraction"], s["found_flagged_by_group"]["other"]
    p = {}
    p["P1"] = s["n_found"] >= 30
    sf = s["share_flagged_found"]
    p["P2"] = sf is not None and 0.05 <= sf <= 0.40
    p["P3"] = (s["share_rin_is_rc"] >= 0.90) if s["n_flagged_with_rin_doi"] >= 3 else "not graded"
    if og[0] >= 5 and rg[0] >= 5:
        p["P4"] = (og[1] <= 0.10 * og[0]) and (rg[1] / rg[0] > og[1] / og[0])
    else:
        p["P4"] = "not graded"
    p["P5"] = s["n_ein_is_rc"] >= 5
    p["P6"] = s["n_rin_other"] <= 2
    return gates, p


def fetch_docs(pmids):
    docs, fail = {}, 0
    for i in range(0, len(pmids), 100):
        chunk = pmids[i:i + 100]
        js = get(EU + "esummary.fcgi?" + urllib.parse.urlencode(
            {"db": "pubmed", "retmode": "json", "id": ",".join(chunk)}))
        d = esummary_docs(js) if js else None
        if d is None:
            fail += len(chunk)
        else:
            docs.update(d)
        time.sleep(0.4)
    return docs, fail


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--src", default=SRC)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()
    text = None
    for _ in range(12):  # the input is published in the same batch as PREREG-8; wait for it
        text = get(a.src)
        if text and text.startswith("notice,"):
            break
        text = None
        time.sleep(120)
    if not text:
        print("could not read input " + a.src, file=sys.stderr)
        return 2
    targets = load_targets(text)
    cand, n_fail = {}, 0
    for t in sorted(targets):
        js = get(EU + "esearch.fcgi?" + urllib.parse.urlencode(
            {"db": "pubmed", "retmode": "json", "retmax": "20", "term": t + "[doi]"}))
        ids = esearch_ids(js) if js else None
        if ids is None:
            n_fail += 1
            ids = []
        cand[t] = ids
        time.sleep(0.4)
    docs, f1 = fetch_docs(sorted({i for ids in cand.values() for i in ids}))
    match = {}
    for t, ids in cand.items():
        m = [docs[i] for i in ids if i in docs and docs[i]["doi"] == t]
        match[t] = m[0] if m else None
    linked_ids = sorted({p for d in match.values() if d for t_, p in d["refs"]
                         if t_ in ("Retraction in", "Erratum in")})
    linked, f2 = fetch_docs(linked_ids)
    rows = [classify(targets[t], match[t], linked) for t in sorted(targets)]
    s = summarize(rows, n_fail)
    gates, preds = grade(s, rows)
    s.update({"preregistered": "PREREG-8.md", "input": a.src, "gates": gates,
              "all_gates_ok": all(gates.values()), "predictions": preds,
              "esummary_failed_ids": f1 + f2, "http": dict(STATS),
              "elapsed_s": round(time.monotonic() - t0, 1)})
    cols = list(rows[0].keys()) if rows else []
    with open(os.path.join(a.out_dir, "pubmed_targets.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: s[k] for k in ("n_targets", "n_found", "n_flagged", "all_gates_ok")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
