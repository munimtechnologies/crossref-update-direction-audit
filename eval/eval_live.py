# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Live evaluation 1 of skills/retraction-crosscheck (plan: eval/EVAL-1-PLAN.md).

Checks every target in data/known_errors.csv plus the genuine/clean controls in
eval/eval_dois.txt. Each DOI is fetched once and assessed twice: BLIND (known-errors table
switched off, so only live sources decide) and WITH the table. Writes eval.json, eval.csv,
summary.json and eval.txt to --out-dir. Always exits 0 (results are graded by hand).
"""
import collections
import csv
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "skills", "retraction-crosscheck", "scripts",
                      "retraction_crosscheck.py")


def load():
    spec = importlib.util.spec_from_file_location("retraction_crosscheck", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def items(rc):
    out = []
    for t, rows in sorted(rc.load_known().items()):
        out.append(("known:" + rows[0]["graded_as"], t))
    with open(os.path.join(HERE, "eval_dois.txt"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                g, d = line.split(None, 1)
                out.append((g, rc.norm_doi(d)))
    return out


def fetch(rc, net, doi):
    """(work, titles, pm, pmid_doi, oa, problems)"""
    probs = []
    try:
        work = net.crossref_work(doi)
    except rc.LookupFailed:
        return None, {}, None, {}, None, ["crossref_failed"]
    titles, pm, pmid_doi, oa = {}, None, {}, None
    if work is not None:
        notices = sorted({rc.norm_doi(u.get("DOI")) for u in work.get("updated-by") or []
                          if isinstance(u, dict) and u.get("DOI")} - {doi})
        try:
            titles = net.crossref_titles(notices) if notices else {}
        except rc.LookupFailed:
            probs.append("titles_failed")
        try:
            pm, pmid_doi = net.pubmed(doi)
        except rc.LookupFailed:
            probs.append("pubmed_failed")
        try:
            oa = net.openalex(doi)
        except rc.LookupFailed:
            probs.append("openalex_failed")
    return work, titles, pm, pmid_doi, oa, probs


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = argv[argv.index("--out-dir") + 1] if "--out-dir" in argv else "."
    os.makedirs(out, exist_ok=True)
    rc = load()
    known = rc.load_known()
    net = rc.Net()
    t0 = time.monotonic()
    rows, full, text = [], [], []
    for g, d in items(rc):
        work, titles, pm, pmid_doi, oa, probs = fetch(rc, net, d)
        if "crossref_failed" in probs:
            blind = rc.blank(d)
            blind["verdict"] = "lookup_failed"
            withk = dict(blind)
        else:
            blind = rc.assess(d, work, titles, pm, pmid_doi, oa, {})
            withk = rc.assess(d, work, titles, pm, pmid_doi, oa, known)
        rows.append({"group": g, "doi": d, "blind_verdict": blind["verdict"],
                     "with_table_verdict": withk["verdict"],
                     "openalex_is_retracted": blind.get("openalex_is_retracted"),
                     "openalex_cited_by": blind.get("openalex_cited_by"),
                     "pmid": (blind.get("pubmed") or {}).get("pmid", ""),
                     "pubmed_retracted": (blind.get("pubmed") or {}).get("retracted", ""),
                     "n_for": len(blind["evidence_for"]), "n_against": len(blind["evidence_against"]),
                     "problems": ";".join(probs)})
        full.append({"group": g, "blind": blind, "with_table": withk, "problems": probs})
        text.append("[%s] blind\n%s\n" % (g, rc.render(blind)))
        print("%-40s %-28s %s" % (d, g, blind["verdict"]), flush=True)
    by = collections.defaultdict(collections.Counter)
    byk = collections.defaultdict(collections.Counter)
    oa_true = collections.Counter()
    for r in rows:
        by[r["group"]][r["blind_verdict"]] += 1
        byk[r["group"]][r["with_table_verdict"]] += 1
        if r["openalex_is_retracted"] is True:
            oa_true[r["group"]] += 1
    summary = {"version": rc.VERSION, "n": len(rows), "elapsed_s": round(time.monotonic() - t0, 1),
               "blind_by_group": {k: dict(v) for k, v in sorted(by.items())},
               "with_table_by_group": {k: dict(v) for k, v in sorted(byk.items())},
               "openalex_true_by_group": dict(oa_true),
               "group_sizes": dict(collections.Counter(r["group"] for r in rows)),
               "lookup_problems": sum(1 for r in rows if r["problems"])}
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    with open(os.path.join(out, "eval.json"), "w", encoding="utf-8") as f:
        json.dump(full, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out, "eval.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(out, "eval.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(text))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
