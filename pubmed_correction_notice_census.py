#!/usr/bin/env python3
# Copyright 2026 MV2, Munim, Inc. (mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Audit 9: PubMed records typed 'Retraction Notice' whose title names a corrigendum, erratum
or correction. Which ones does PubMed link ('Retraction of') to the paper itself rather than to
the correction, and how many papers does PubMed show as retracted only because of such
notices? See PREREG-9.md."""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request

EU = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
UA = "mv2-audit9/1.0 (mailto:mv2@munimtech.com)"
QUERY = ('"retraction notice"[pt] AND (corrigendum[ti] OR erratum[ti] OR correction[ti])')
PREREG_URL = ("https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/"
              "main/PREREG-9.md")
STATS = {"ok": 0, "err": 0, "bad": 0}

# G3 instrument: withdrawn corrigenda read by hand on 2026-11-10 (disclosed in PREREG-9.md)
G3_NOTICES = {"27852510": "27633722", "30449593": "26319650", "39645442": "29852306",
              "41422828": "41110921", "42420052": "38364746", "42441098": "33948439"}

CORR = (r"(corrigend(?:um|a)|errat(?:um|a)|corrections?(?=\s*(?::|to\b|for\b|notice\b|,|-|–|$)))")
WC_RE = re.compile(r"^(?:withdrawn|retracted)\s*[:.\-–—]?\s*" + CORR)
RNC_RE = re.compile(r"^(?:notice of retraction|retraction notice|retraction note|retraction statement|"
                    r"retraction|withdrawal notice|withdrawal)\b\s*(?:of|to|for|from)?\s*[:.\-–—]?\s*"
                    r"(?:of|to|for)?\s*" + CORR)
C_RE = re.compile(r"^" + CORR)
_STRIP = re.compile(r"[\"“”‘’'`\[\]«»]")


def norm_title(t):
    t = _STRIP.sub(" ", (t or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def notice_class(title):
    """WC = the record is itself a withdrawn/retracted correction ('WITHDRAWN: Corrigendum to X');
    RNC = a retraction/withdrawal notice of a correction ('Retraction notice to "Corrigendum to X"');
    C = titled as a bare correction ('Erratum: X'); OTHER = anything else."""
    t = norm_title(title)
    if WC_RE.match(t):
        return "WC"
    if RNC_RE.match(t):
        return "RNC"
    if C_RE.match(t):
        return "C"
    return "OTHER"


def is_corr_record(doc):
    if "Published Erratum" in doc.get("pubtype", []):
        return True
    t = norm_title(doc.get("title", ""))
    return bool(WC_RE.match(t) or C_RE.match(t))


def norm_doi(d):
    d = (d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d


def summary_doc(doc):
    doi = ""
    for a in doc.get("articleids", []) or []:
        if a.get("idtype") == "doi":
            doi = norm_doi(a.get("value"))
    refs = [(x.get("reftype", ""), str(x.get("pmid", ""))) for x in (doc.get("references") or [])]
    return {"uid": str(doc.get("uid", "")), "doi": doi, "pubtype": list(doc.get("pubtype") or []),
            "title": doc.get("title", ""), "source": doc.get("source", ""),
            "pubdate": doc.get("pubdate", ""), "refs": refs}


def parse_esummary(js):
    try:
        res = json.loads(js)["result"]
        uids = res["uids"]
    except Exception:
        return None
    return {u: summary_doc(res[u]) for u in uids if u in res}


def parse_esearch(js):
    try:
        r = json.loads(js)["esearchresult"]
        return int(r["count"]), [str(x) for x in r["idlist"]]
    except Exception:
        return None


def refs_of(doc, reftype):
    return [p for t, p in doc["refs"] if t == reftype and p]


def analyse(notices, docs):
    """notices: list of notice PMIDs from the query. docs: {pmid: summary} covering the notices,
    their 'Retraction of' targets and those targets' 'Retraction in' notices.
    Returns (notice_rows, paper_rows)."""
    cls = {}

    def klass(pmid):
        if pmid not in cls:
            cls[pmid] = notice_class(docs[pmid]["title"]) if pmid in docs else "UNREAD"
        return cls[pmid]

    nrows = []
    paper_targets = {}
    for n in notices:
        if n not in docs:
            continue
        d = docs[n]
        k = klass(n)
        tg = refs_of(d, "Retraction of")
        read = [t for t in tg if t in docs]
        papers = [t for t in read if not is_corr_record(docs[t])]
        corrs = [t for t in read if is_corr_record(docs[t])]
        nrows.append({"notice": n, "class": k, "doi": d["doi"], "title": d["title"][:200],
                      "targets": ";".join(tg), "targets_read": len(read),
                      "paper_targets": ";".join(papers), "corr_targets": ";".join(corrs)})
        if k in ("WC", "RNC", "C"):
            for p in papers:
                paper_targets.setdefault(p, set()).add(n)
    prows = []
    for p in sorted(paper_targets):
        d = docs[p]
        rin = refs_of(d, "Retraction in")
        rin_cls = [klass(r) for r in rin]
        only_via = ("Retracted Publication" in d["pubtype"] and bool(rin)
                    and all(c in ("WC", "RNC", "C") for c in rin_cls))
        prows.append({"paper": p, "doi": d["doi"], "title": d["title"][:200], "source": d["source"],
                      "retracted_type": "Retracted Publication" in d["pubtype"],
                      "via_notices": ";".join(sorted(paper_targets[p])),
                      "retraction_in": ";".join(rin), "retraction_in_classes": ";".join(rin_cls),
                      "erratum_in": ";".join(refs_of(d, "Erratum in")),
                      "only_via_correction": only_via, "elsevier": d["doi"].startswith("10.1016/"),
                      "openalex_is_retracted": None})
    return nrows, prows


def share(a, b):
    return round(a / b, 4) if b else None


def summarize(nrows, prows, n_ids, count):
    cc = {k: sum(1 for r in nrows if r["class"] == k) for k in ("WC", "RNC", "C", "OTHER")}
    S = [r for r in nrows if r["class"] in ("WC", "RNC")]
    s_t = [r for r in S if r["targets_read"]]
    wc_t = [r for r in s_t if r["class"] == "WC"]
    rnc_t = [r for r in s_t if r["class"] == "RNC"]
    only = [r for r in prows if r["only_via_correction"]]
    only_doi = [r for r in only if r["doi"]]
    oa = [r for r in only if r["openalex_is_retracted"] is not None]
    return {
        "query": QUERY, "query_count": count, "n_ids": n_ids, "n_notices_read": len(nrows),
        "class_counts": cc, "n_S": len(S), "share_S": share(len(S), len(nrows)),
        "n_S_with_target": len(s_t),
        "n_S_paper_target": sum(1 for r in s_t if r["paper_targets"]),
        "share_S_paper_target": share(sum(1 for r in s_t if r["paper_targets"]), len(s_t)),
        "n_WC_with_target": len(wc_t),
        "share_WC_paper_target": share(sum(1 for r in wc_t if r["paper_targets"]), len(wc_t)),
        "n_RNC_with_target": len(rnc_t),
        "share_RNC_paper_target": share(sum(1 for r in rnc_t if r["paper_targets"]), len(rnc_t)),
        "n_C_paper_target": sum(1 for r in nrows if r["class"] == "C" and r["paper_targets"]),
        "n_paper_targets": len(prows),
        "n_only_via": len(only),
        "n_only_via_with_doi": len(only_doi),
        "share_only_via_elsevier": share(sum(1 for r in only_doi if r["elsevier"]), len(only_doi)),
        "n_only_via_openalex_found": len(oa),
        "share_only_via_openalex_retracted": share(sum(1 for r in oa if r["openalex_is_retracted"]),
                                                   len(oa)),
        "only_via_by_source": _top([r["source"] for r in only]),
    }


def _top(xs, n=15):
    c = {}
    for x in xs:
        c[x] = c.get(x, 0) + 1
    return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:n])


def grade(s, nrows, prows, target_fail):
    nby = {r["notice"]: r for r in nrows}
    only = {r["paper"] for r in prows if r["only_via_correction"]}
    g1 = (s["query_count"] >= 250 and s["n_ids"] == s["query_count"]
          and s["n_notices_read"] >= 0.98 * s["n_ids"])
    g2 = target_fail <= 0.02 * max(1, sum(len(r["targets"].split(";")) for r in nrows if r["targets"]))
    g3 = all(n in nby and nby[n]["class"] == "WC" and p in nby[n]["paper_targets"].split(";")
             and p in only for n, p in G3_NOTICES.items())
    gates = {"G1_census_complete": g1, "G2_targets_read": g2, "G3_instrument": g3}
    p = {}
    p["P1"] = s["share_S"] is not None and s["share_S"] >= 0.75
    p["P2"] = s["share_S_paper_target"] is not None and s["share_S_paper_target"] >= 0.50
    p["P3"] = (s["share_WC_paper_target"] >= 0.90) if s["n_WC_with_target"] >= 5 else "not graded"
    p["P4"] = s["n_only_via"] >= 20
    p["P5"] = s["share_only_via_elsevier"] is not None and s["share_only_via_elsevier"] >= 0.60
    p["P6"] = ((s["share_only_via_openalex_retracted"] >= 0.30)
               if s["n_only_via_openalex_found"] >= 10 else "not graded")
    p["P7"] = "graded by hand from grade20.csv"
    return gates, p


# ---------------- network ----------------

def get(url, check=None, tries=5, data=None):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA}, data=data)
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = r.read().decode("utf-8")
            if check is None or check(txt) is not None:
                STATS["ok"] += 1
                return txt
            STATS["bad"] += 1
        except Exception:
            STATS["err"] += 1
        time.sleep(3 * (i + 1))
    return None


def fetch_docs(pmids, docs):
    fail = []
    todo = [p for p in pmids if p not in docs]
    for i in range(0, len(todo), 100):
        chunk = todo[i:i + 100]
        body = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "id": ",".join(chunk)})
        js = get(EU + "esummary.fcgi", check=parse_esummary, data=body.encode())
        d = parse_esummary(js) if js else None
        if d is None:
            fail.extend(chunk)
        else:
            docs.update(d)
            fail.extend(p for p in chunk if p not in d)
        time.sleep(0.5)
    return fail


def openalex(prows):
    rows = [r for r in prows if r["only_via_correction"] and r["doi"] and "," not in r["doi"]
            and "|" not in r["doi"]]
    for i in range(0, len(rows), 40):
        chunk = rows[i:i + 40]
        q = urllib.parse.urlencode({"filter": "doi:" + "|".join(r["doi"] for r in chunk),
                                    "select": "doi,is_retracted", "per-page": "50",
                                    "mailto": "mv2@munimtech.com"})
        js = get("https://api.openalex.org/works?" + q, check=lambda t: json.loads(t)["results"])
        if not js:
            continue
        got = {norm_doi(w.get("doi")): bool(w.get("is_retracted")) for w in json.loads(js)["results"]}
        for r in chunk:
            if r["doi"] in got:
                r["openalex_is_retracted"] = got[r["doi"]]
        time.sleep(0.3)


def write_csv(path, rows):
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-prereg-min", type=int, default=40)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()
    prereg_live = None
    deadline = time.monotonic() + 60 * a.wait_prereg_min
    while time.monotonic() < deadline:
        txt = get(PREREG_URL, tries=1)
        if txt and "Pre-registration 9" in txt:
            prereg_live = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            break
        time.sleep(60)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "retmax": "10000", "term": QUERY})
    js = get(EU + "esearch.fcgi?" + q, check=parse_esearch)
    if not js:
        print("esearch failed", file=sys.stderr)
        return 2
    count, ids = parse_esearch(js)
    docs = {}
    f0 = fetch_docs(ids, docs)
    targets = sorted({p for n in ids if n in docs for p in refs_of(docs[n], "Retraction of")})
    f1 = fetch_docs(targets, docs)
    rin = sorted({p for t in targets if t in docs for p in refs_of(docs[t], "Retraction in")})
    f2 = fetch_docs(rin, docs)
    nrows, prows = analyse(ids, docs)
    openalex(prows)
    s = summarize(nrows, prows, len(ids), count)
    gates, preds = grade(s, nrows, prows, len(f1))
    only = sorted((r for r in prows if r["only_via_correction"]), key=lambda r: int(r["paper"]))
    sample = random.Random(9).sample(only, min(20, len(only)))
    s.update({"preregistered": "PREREG-9.md", "prereg_live_at": prereg_live, "census_started": started,
              "gates": gates, "all_gates_ok": all(gates.values()), "predictions": preds,
              "fail_notices": len(f0), "fail_targets": len(f1), "fail_rin": len(f2),
              "http": dict(STATS), "elapsed_s": round(time.monotonic() - t0, 1)})
    write_csv(os.path.join(a.out_dir, "notices.csv"), nrows)
    write_csv(os.path.join(a.out_dir, "papers.csv"), prows)
    write_csv(os.path.join(a.out_dir, "grade20.csv"), sorted(sample, key=lambda r: int(r["paper"])))
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: s[k] for k in ("query_count", "n_notices_read", "n_only_via", "all_gates_ok")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
