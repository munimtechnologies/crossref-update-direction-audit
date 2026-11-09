# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Crossref update audit 5 (pre-registered in PREREG-5.md): do PubMed's own links agree with
every retraction or withdrawal that publishers deposit in Crossref?

A publisher deposits a notice N with `update-to` = {target T, type retraction|withdrawal|
partial_retraction|removal}. Crossref, and tools that read it (OpenAlex is_retracted, reference
managers), then show T as retracted. PubMed curates its own comment/correction links: T's record
says "Retraction in <N>" or "Erratum in <N>". This script walks every Crossref notice with a
retractive update type, looks every non-self target up in PubMed, finds PubMed's link to the
SAME notice N (by the DOI in PubMed's citation text, or by the linked PMID's DOI), and counts:

- agree:            PubMed links N to T as "Retraction in" / "Partial retraction in";
- contradict:       PubMed links N to T as "Erratum in", and T has no retraction link and no
                    "Retracted Publication" type in PubMed (PubMed says T was only corrected);
- erratum_but_retracted: PubMed links N as "Erratum in" but T is retracted in PubMed elsewhere;
- eoc / other_link: PubMed links N with another type (expression of concern, comment, ...);
- pm_retracted_elsewhere: T is in PubMed, N is not linked, and T is retracted in PubMed;
- pm_corrected_only: N is not linked, T has an "Erratum in" link and is not retracted;
- pm_silent:        T is in PubMed, N is not linked, T is not retracted in PubMed;
- not_in_pubmed:    no PubMed record carries T's DOI (or the DOI could not be queried).

No API keys. api.crossref.org, eutils.ncbi.nlm.nih.gov (tool/email set, <= 2.5 requests/s) and
api.openalex.org. Usage: python pubmed_link_audit.py --out-dir /out
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
UA = "crossref-pubmed-link-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
CROSSREF = "https://api.crossref.org/works"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
OPENALEX = "https://api.openalex.org/works"
TOOL = "mv2-crossref-pubmed-link-audit"
SELECT = "DOI,update-to,title,type,publisher,member,created,container-title"
TARGET_SELECT = "DOI,title,type,member,publisher"
UPDATE_TYPES = ["retraction", "withdrawal", "partial_retraction", "removal"]
RETRACTIVE = set(UPDATE_TYPES)
PM_RETRACT_LINKS = {"retraction in", "partial retraction in"}
PM_ERRATUM_LINKS = {"erratum in"}
PM_EOC_LINKS = {"expression of concern in"}
SEARCH_BATCH = 100
SUMMARY_BATCH = 200
GRADE_N = 20

DASHES = "‐‑‒–—―−"
QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"'}
_KEY = r"(?:retractions|retraction|retracted|withdrawn|withdrawal)"
_NEXT = (r"(?:$|\s*[:.\-\])(,;]|\s+(?:note|notes|notice|notices|statement|of|to|for|and|"
         r"article|paper|publication|letter)\b)")
START = re.compile(r"^(?:notice of (?:retraction|withdrawal)\b|(?:partial |full )?" + _KEY + _NEXT + ")")
END = re.compile(r"[:.\-\[(]\s*[\[(]?\s*(?:retraction notice|notice of retraction|" + _KEY + r")$")
CORRECTION_START = re.compile(
    r"^(?:author correction|publisher correction|correction|corrections|corrigendum|corrigenda|"
    r"erratum|errata|addendum|addenda|clarification)\b")
RETRACT_WORD = re.compile(r"retract|withdraw")
CORRECT_WORD = re.compile(r"errat|corrig|correction")
EOC = re.compile(r"expressions? of concern")
SAFE_DOI = re.compile(r"^10\.\d{4,9}/[a-z0-9._()/\-]+$")
REF_DOI = re.compile(r"doi:\s*(10\.\d{4,9}/\S+)", re.I)

# validation set: the 10 PubMed-indexed papers of findings/corrections-deposited-as-retractions.md
# (target, notice); hand-graded 2026-11-09 as corrected, not retracted
KNOWN = [
    ("10.1096/fj.09-135467", "10.1096/fj.09-135467err"),
    ("10.1016/j.lfs.2005.07.038", "10.1016/j.lfs.2013.01.014"),
    ("10.1096/fj.08-114363", "10.1096/fj.08-114363err"),
    ("10.1096/fj.13-246579", "10.1096/fj.13-246579err"),
    ("10.1096/fj.11-196709", "10.1096/fj.11-196709err"),
    ("10.11005/jbm.2022.29.4.225", "10.11005/jbm.2023.30.1.115"),
    ("10.1042/bsr20181233", "10.1042/bsr-20181233_cor"),
    ("10.3341/kjo.2022.0089", "10.3341/kjo.2022.0089.e1"),
    ("10.1042/bsr20203727", "10.1042/bsr-20203727_cor"),
    ("10.1096/fj.09-0601ufm", "10.1096/fj.09-0601ufmerr"),
]
KNOWN_TARGETS = {t for t, _ in KNOWN}


# ---------------------------------------------------------------- pure helpers
def clean_title(s):
    s = str(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    for ch in DASHES:
        s = s.replace(ch, " - ")
    for k, v in QUOTES.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", s).strip()


def core_title(s):
    return clean_title(s).strip(" \"'[]().*:;,-")


def retraction_worded(title):
    c = core_title(title)
    if not c:
        return False
    if CORRECTION_START.match(c) or EOC.search(c):
        return False
    return bool(START.match(c) or END.search(c))


def correction_worded(title):
    c = core_title(title)
    if not c or RETRACT_WORD.search(c) or EOC.search(c):
        return False
    return bool(CORRECTION_START.match(c))


def title_class(title):
    """'correction' | 'mixed' | 'retraction' | 'eoc' | 'empty' | 'other' for a notice title."""
    c = core_title(title)
    if not c:
        return "empty"
    if correction_worded(title):
        return "correction"
    if RETRACT_WORD.search(c) and CORRECT_WORD.search(c):
        return "mixed"
    if retraction_worded(title):
        return "retraction"
    if EOC.search(c):
        return "eoc"
    return "other"


def norm_doi(d):
    d = str(d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
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


def safe_doi(d):
    return bool(SAFE_DOI.match(norm_doi(d)))


def ref_doi(refsource):
    """DOI quoted in a PubMed reference citation ('... doi: 10.1/x.e1.'), lower case, or ''."""
    m = REF_DOI.search(str(refsource or ""))
    if not m:
        return ""
    d = m.group(1).rstrip(".,;").lower()
    return d


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return round(num / den, 4) if den else None


# ---------------------------------------------------------------- Crossref walk
class Walker:
    """Collects retractive relations from notice records (deduplicated by notice DOI)."""

    def __init__(self):
        self.seen = set()
        self.rels = []            # publisher-sourced retractive relations, notice != target
        self.self_rels = 0
        self.rw_retracted = set()  # targets with a retraction-watch retractive relation
        self.sources = collections.Counter()
        self.n_records = 0

    def add(self, item):
        rec = norm_doi(item.get("DOI"))
        if not rec or rec in self.seen:
            return
        self.seen.add(rec)
        self.n_records += 1
        title = first(item.get("title"))
        keep = set()
        for u in item.get("update-to") or []:
            if not isinstance(u, dict):
                continue
            t, ut, src = norm_doi(u.get("DOI")), norm_type(u.get("type")), str(u.get("source") or "")
            if ut not in RETRACTIVE or not t:
                continue
            self.sources[src] += 1
            if src == "retraction-watch":
                self.rw_retracted.add(t)
                continue
            if src != "publisher":
                continue
            if t == rec:
                self.self_rels += 1
                continue
            if (t, ut) in keep:
                continue
            keep.add((t, ut))
            self.rels.append({
                "notice": rec, "target": t, "utype": ut, "member": str(item.get("member") or ""),
                "publisher": str(item.get("publisher") or ""), "year": created_year(item),
                "notice_title": title[:200], "title_class": title_class(title),
                "container": first(item.get("container-title"))[:80]})


# ---------------------------------------------------------------- PubMed parsing
def parse_esummary(obj):
    """{doi: {"pmid", "pubtype": [..], "refs": [(reftype_lower, pmid_str, refsource)]}}"""
    res = (obj or {}).get("result") or {}
    out = {}
    for uid in res.get("uids") or []:
        d = res.get(uid) or {}
        if not isinstance(d, dict) or d.get("error"):
            continue
        dois = [norm_doi(a.get("value")) for a in d.get("articleids") or []
                if isinstance(a, dict) and a.get("idtype") == "doi" and a.get("value")]
        refs = []
        for r in d.get("references") or []:
            if not isinstance(r, dict):
                continue
            refs.append((str(r.get("reftype") or "").strip().lower(),
                         str(r.get("pmid") or ""), str(r.get("refsource") or "")))
        rec = {"pmid": str(uid), "pubtype": [str(p) for p in d.get("pubtype") or []],
               "refs": refs, "title": str(d.get("title") or "")[:160]}
        for x in dois:
            # two PubMed records can share a DOI (a notice indexed with the paper's DOI):
            # keep the one that is not itself a notice
            if x in out and is_notice_record(rec) and not is_notice_record(out[x]):
                continue
            out[x] = rec
    return out


NOTICE_PUBTYPES = {"published erratum", "retraction of publication", "expression of concern"}


def is_notice_record(rec):
    return any(p.lower() in NOTICE_PUBTYPES for p in rec["pubtype"])


def pm_retracted(rec):
    if not rec:
        return False
    if any(p.lower() == "retracted publication" for p in rec["pubtype"]):
        return True
    return any(rt in PM_RETRACT_LINKS for rt, _, _ in rec["refs"])


def link_types_to(rec, notice, pmid_doi):
    """Set of PubMed reftypes on rec that point at the notice DOI."""
    out = set()
    if not rec:
        return out
    for rt, pmid, src in rec["refs"]:
        d = ref_doi(src) or pmid_doi.get(pmid, "")
        if d and d == notice:
            out.add(rt)
    return out


def classify(rel, rec, pmid_doi):
    if rec is None:
        return "not_in_pubmed"
    lt = link_types_to(rec, rel["notice"], pmid_doi)
    if lt & PM_RETRACT_LINKS:
        return "agree"
    if lt & PM_ERRATUM_LINKS:
        return "erratum_but_retracted" if pm_retracted(rec) else "contradict"
    if lt & PM_EOC_LINKS:
        return "eoc"
    if lt:
        return "other_link"
    if pm_retracted(rec):
        return "pm_retracted_elsewhere"
    if any(rt in PM_ERRATUM_LINKS for rt, _, _ in rec["refs"]):
        return "pm_corrected_only"
    return "pm_silent"


def needs_pmid_lookup(rec):
    """PMIDs of correction/retraction-type links whose citation text has no DOI."""
    want = PM_RETRACT_LINKS | PM_ERRATUM_LINKS | PM_EOC_LINKS
    return [p for rt, p, src in (rec or {}).get("refs", []) if rt in want and p and not ref_doi(src)]


def esearch_term(dois):
    return " OR ".join("%s[doi]" % d for d in dois)


# ---------------------------------------------------------------- network
STATS = collections.Counter()
_LAST = {}


def http(url, data=None, tries=6, timeout=120, gap=0.5, host="x"):
    delay = 5
    last = -1
    for _ in range(tries):
        wait = _LAST.get(host, 0.0) + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST[host] = time.monotonic()
        body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
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
    except (ValueError, UnicodeDecodeError):
        return None


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


def pubmed_search(dois):
    """PMIDs for a batch of DOIs; splits the batch if PubMed refuses it."""
    data = {"db": "pubmed", "retmode": "json", "retmax": str(3 * len(dois) + 10),
            "term": esearch_term(dois), "tool": TOOL, "email": MAILTO}
    st, body = http(EUTILS + "esearch.fcgi", data=data, host="ncbi", gap=0.4)
    obj = jload(body) if st == 200 else None
    er = (obj or {}).get("esearchresult") or {}
    ids = er.get("idlist")
    try:
        count = int(er.get("count", -1))
    except (TypeError, ValueError):
        count = -1
    # a term PubMed misparses can match far more records than DOIs asked for: split then
    if isinstance(ids, list) and 0 <= count <= 2 * len(dois) + 5:
        return [str(i) for i in ids], 0
    if st not in (200, 400, 414) or len(dois) == 1:
        # server/network failure (already retried): do not split, count the DOIs as failed
        return [], len(dois)
    h = len(dois) // 2
    a, fa = pubmed_search(dois[:h])
    b, fb = pubmed_search(dois[h:])
    return a + b, fa + fb


def pubmed_summary(pmids):
    out = {}
    for i in range(0, len(pmids), SUMMARY_BATCH):
        b = pmids[i:i + SUMMARY_BATCH]
        data = {"db": "pubmed", "retmode": "json", "id": ",".join(b), "tool": TOOL, "email": MAILTO}
        st, body = http(EUTILS + "esummary.fcgi", data=data, host="ncbi", gap=0.4)
        obj = jload(body) if st == 200 else None
        if obj is None:
            STATS["esummary_batch_failed"] += 1
            continue
        out.update(parse_esummary(obj))
    return out


def pmid_dois(pmids):
    """{pmid: doi} for linked notice PMIDs (via esummary articleids)."""
    out = {}
    for i in range(0, len(pmids), SUMMARY_BATCH):
        b = pmids[i:i + SUMMARY_BATCH]
        data = {"db": "pubmed", "retmode": "json", "id": ",".join(b), "tool": TOOL, "email": MAILTO}
        st, body = http(EUTILS + "esummary.fcgi", data=data, host="ncbi", gap=0.4)
        obj = jload(body) if st == 200 else None
        res = (obj or {}).get("result") or {}
        for uid in res.get("uids") or []:
            d = res.get(uid) or {}
            for a in d.get("articleids") or []:
                if isinstance(a, dict) and a.get("idtype") == "doi" and a.get("value"):
                    out[str(uid)] = norm_doi(a["value"])
                    break
    return out


def openalex(dois):
    out = {}
    ok = [d for d in dois if "|" not in d and "," not in d]
    for i in range(0, len(ok), 50):
        b = ok[i:i + 50]
        url = ("%s?filter=doi:%s&select=doi,is_retracted,cited_by_count&per-page=100&mailto=%s"
               % (OPENALEX, "|".join(urllib.parse.quote(d, safe="/()") for d in b), MAILTO))
        st, body = http(url, host="openalex", gap=0.2)
        for r in ((jload(body) or {}).get("results") or []) if st == 200 else []:
            out[norm_doi(r.get("doi"))] = (r.get("is_retracted"), r.get("cited_by_count"))
    return out


def crossref_titles(dois):
    out = {}
    for i in range(0, len(dois), 20):
        b = [d for d in dois[i:i + 20] if "," not in d]
        f = ",".join("doi:" + urllib.parse.quote(d, safe="/") for d in b)
        st, body = http("%s?filter=%s&rows=%d&select=%s&mailto=%s"
                        % (CROSSREF, f, len(b) + 5, TARGET_SELECT, MAILTO), host="crossref", gap=0.3)
        for it in (((jload(body) or {}).get("message") or {}).get("items") or []) if st == 200 else []:
            out[norm_doi(it.get("DOI"))] = first(it.get("title"))[:160]
    return out


# ---------------------------------------------------------------- main
FIELDS = ["notice", "target", "utype", "verdict", "title_class", "member", "publisher", "year",
          "container", "notice_title", "pmid", "pm_pubtype", "pm_links_to_notice", "rw_retracted",
          "t_title", "t_title_marked", "oa_is_retracted", "oa_cited_by", "known", "grade", "note"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def tally(rels, key):
    c = collections.Counter(r[key] for r in rels)
    return c.most_common()


def summarize(w, rels, walk_ok):
    v = collections.Counter(r["verdict"] for r in rels)
    linked = v["agree"] + v["contradict"] + v["erratum_but_retracted"] + v["eoc"] + v["other_link"]
    indexed = sum(n for k, n in v.items() if k != "not_in_pubmed")
    con = [r for r in rels if r["verdict"] == "contradict"]
    known_hit = sorted({r["target"] for r in con if r["target"] in KNOWN_TARGETS})
    oa = [r for r in con if r.get("oa_is_retracted") in (True, False)]
    return {
        "walk_complete": walk_ok, "n_records": w.n_records, "sources": dict(w.sources),
        "n_publisher_relations": len(rels), "n_self_relations": w.self_rels,
        "n_targets": len({r["target"] for r in rels}),
        "verdicts": dict(v), "n_pubmed_indexed": indexed, "n_linked": linked,
        "share_indexed": share(indexed, len(rels)),
        "share_agree_of_linked": share(v["agree"], linked),
        "n_contradict": len(con), "n_contradict_targets": len({r["target"] for r in con}),
        "contradict_by_publisher": tally(con, "publisher")[:30],
        "contradict_by_title_class": tally(con, "title_class"),
        "contradict_by_utype": tally(con, "utype"),
        "contradict_by_year": sorted(collections.Counter(r["year"] for r in con).items(),
                                     key=lambda x: str(x[0])),
        "contradict_correction_worded": sum(1 for r in con if r["title_class"] == "correction"),
        "contradict_rw_retracted": sum(1 for r in con if r["rw_retracted"]),
        "contradict_oa_checked": len(oa),
        "contradict_oa_retracted": sum(1 for r in oa if r["oa_is_retracted"] is True),
        "contradict_oa_citations": sum(int(r.get("oa_cited_by") or 0) for r in con),
        "contradict_target_title_marked": sum(1 for r in con if r.get("t_title_marked") is True),
        "known_recovered": known_hit, "n_known_recovered": len(known_hit),
        "known_verdicts": sorted({(r["target"], r["notice"], r["verdict"])
                                  for r in rels if r["target"] in KNOWN_TARGETS}),
        "agree_by_title_class": tally([r for r in rels if r["verdict"] == "agree"], "title_class"),
        "silent_by_publisher": tally([r for r in rels if r["verdict"] == "pm_silent"], "publisher")[:20],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-pages", type=int, default=400)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()

    w = Walker()
    walk_ok, totals = True, {}
    for ut in UPDATE_TYPES:
        ok, tot = walk(w, ut, a.max_pages)
        totals[ut] = tot
        if ut in ("retraction", "withdrawal"):
            walk_ok = walk_ok and ok
    rels = w.rels
    for r in rels:
        r["rw_retracted"] = r["target"] in w.rw_retracted
        r["known"] = r["target"] in KNOWN_TARGETS
    print("walk done: %d records, %d publisher relations, %.0fs"
          % (w.n_records, len(rels), time.monotonic() - t0), flush=True)

    targets = sorted({r["target"] for r in rels})
    queryable = [d for d in targets if safe_doi(d)]
    pmids, failed, run_fail, aborted = [], 0, 0, False
    for i in range(0, len(queryable), SEARCH_BATCH):
        batch = queryable[i:i + SEARCH_BATCH]
        ids, f = pubmed_search(batch)
        pmids.extend(ids)
        failed += f
        run_fail = run_fail + 1 if f == len(batch) else 0
        if run_fail >= 5:
            aborted = True
            print("esearch: 5 batches in a row failed, stopping PubMed phase", file=sys.stderr)
            break
        if (i // SEARCH_BATCH) % 50 == 0:
            print("esearch %d/%d, pmids %d" % (i, len(queryable), len(pmids)), flush=True)
    pmids = sorted(set(pmids))
    pm = pubmed_summary(pmids)
    need = sorted({p for d in targets for p in needs_pmid_lookup(pm.get(d))})
    pdoi = pmid_dois(need)
    print("pubmed: %d pmids, %d target records, %d linked pmids looked up, %.0fs"
          % (len(pmids), len(pm), len(need), time.monotonic() - t0), flush=True)

    for r in rels:
        rec = pm.get(r["target"])
        r["verdict"] = classify(r, rec, pdoi)
        r["pmid"] = rec["pmid"] if rec else ""
        r["pm_pubtype"] = ";".join(rec["pubtype"]) if rec else ""
        r["pm_links_to_notice"] = ";".join(sorted(link_types_to(rec, r["notice"], pdoi)))

    con = [r for r in rels if r["verdict"] == "contradict"]
    ctargets = sorted({r["target"] for r in con})[:5000]
    oa = openalex(ctargets)
    tt = crossref_titles(ctargets)
    for r in con:
        r["oa_is_retracted"], r["oa_cited_by"] = oa.get(r["target"], ("", ""))
        r["t_title"] = tt.get(r["target"], "")
        r["t_title_marked"] = retraction_worded(r["t_title"]) if r["t_title"] else ""

    order = sorted(con, key=lambda r: (r["publisher"], r["target"], r["notice"]))
    write_csv(os.path.join(a.out_dir, "contradictions.csv"), order)
    pool = [r for r in con if not r["known"]]
    write_csv(os.path.join(a.out_dir, "grade_contradictions20.csv"),
              sorted(pool, key=lambda r: sha_key("a5", r["notice"], r["target"]))[:GRADE_N])
    ebr = [r for r in rels if r["verdict"] == "erratum_but_retracted"]
    write_csv(os.path.join(a.out_dir, "erratum_but_retracted.csv"),
              sorted(ebr, key=lambda r: (r["publisher"], r["target"])))
    agree = [r for r in rels if r["verdict"] == "agree"]
    write_csv(os.path.join(a.out_dir, "agree_sample20.csv"),
              sorted(agree, key=lambda r: sha_key("a5agree", r["notice"], r["target"]))[:GRADE_N])

    s = summarize(w, rels, walk_ok)
    s.update({"preregistered": "PREREG-5.md", "crossref_totals": totals,
              "n_queryable_targets": len(queryable), "esearch_failed_dois": failed,
              "pubmed_phase_aborted": aborted,
              "n_pmids": len(pmids), "n_pubmed_target_records": len(pm),
              "n_linked_pmids_looked_up": len(need), "http": dict(STATS),
              "elapsed_s": round(time.monotonic() - t0, 1)})
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: s[k] for k in ("n_records", "n_publisher_relations", "verdicts",
                                        "n_contradict", "n_known_recovered")}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
