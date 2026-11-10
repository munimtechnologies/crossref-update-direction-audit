#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""retraction-crosscheck: is a paper's retraction flag real?

Most retraction checkers read one field: a Crossref `updated-by` entry of type retraction (or
OpenAlex `is_retracted`, which follows it). Publishers sometimes deposit a correction notice with
the update type `retraction`, deposit a withdrawal notice as an `addendum`, or list a notice as
its own retraction. This script reads the same Crossref record and then checks it against
independent sources:

- the title of every notice (is the "retraction" notice titled "Erratum" or "Correction"?);
- Retraction Watch's own entries in Crossref (source `retraction-watch`) for the same notice;
- PubMed: is the paper typed "Retracted Publication", does it link the same notice as
  "Retraction in" or as "Erratum in", and what are its "Retraction in" notices titled?
- the paper's own title ("RETRACTED: ...", "Withdrawn: ...");
- OpenAlex `is_retracted` (reported, so you can see what downstream tools show);
- a small offline table of graded errors from MV2's open Crossref audits (data/known_errors.csv).

Verdicts: retracted, retracted_unconfirmed, disputed, possibly_withdrawn, concern,
self_loop_notice, corrected, no_notice, not_found, lookup_failed (offline: known_error,
not_in_table).

0.2.0: a withdrawn or retracted *correction* ("WITHDRAWN: Corrigendum to ...") no longer
confirms a retraction of the paper. PubMed indexes some of these as the paper's "Retraction in"
notice and types the paper "Retracted Publication"; 0.1.1 counted that as confirmation and called
9 such papers retracted (EVAL-2). PubMed's flag now counts only if at least one "Retraction in"
notice is not titled as a withdrawn or retracted correction. Notices titled "Erratum to: ..." or
"Retraction: Erratum to ..." are not affected: audit 9 found they are mostly real retractions.

0.1.1: titles that only name a topic ("Withdrawal of antihypertensive drugs in older people",
"Withdrawal and Belonging: ...") are no longer read as retraction or withdrawal notices.

No API keys; read-only HTTPS GETs to api.crossref.org, eutils.ncbi.nlm.nih.gov and
api.openalex.org. Python 3.8+, standard library only.

    python retraction_crosscheck.py 10.1096/fj.09-135467
    python retraction_crosscheck.py --file refs.bib --json
    python retraction_crosscheck.py --offline 10.3341/kjo.2022.0089

Exit codes: 0 = nothing flagged; 1 = at least one DOI flagged (retracted, unconfirmed, disputed,
possibly withdrawn, concern, self-loop, or a known error offline); 2 = a DOI could not be
checked (not in Crossref, network failure) or bad input.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.2.0"
MAILTO = "mv2@munimtech.com"
UA = "retraction-crosscheck/%s (MV2, Munim, Inc.; mailto:%s)" % (VERSION, MAILTO)
CROSSREF = "https://api.crossref.org/works"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
OPENALEX = "https://api.openalex.org/works"
TOOL = "retraction-crosscheck"
HERE = os.path.dirname(os.path.abspath(__file__))
KNOWN_PATH = os.path.normpath(os.path.join(HERE, os.pardir, "data", "known_errors.csv"))
REPO = "https://github.com/munimtechnologies/crossref-update-direction-audit"

RETRACTIVE = {"retraction", "withdrawal", "partial_retraction", "removal"}
EOC_TYPES = {"expression_of_concern"}
PM_RETRACT_LINKS = {"retraction in", "partial retraction in"}
PM_ERRATUM_LINKS = {"erratum in"}
PM_EOC_LINKS = {"expression of concern in"}
NOTICE_PUBTYPES = {"published erratum", "retraction of publication", "expression of concern"}
KNOWN_NOT_RETRACTED = {"corrected_not_retracted", "corrected_not_retracted_title_only",
                       "wrong_target_off_by_one", "shown_withdrawn_in_crossref_only",
                       "self_loop_notice_marked_retracted"}
KNOWN_WITHDRAWN = {"withdrawn_typed_addendum"}
KNOWN_PUBMED_WC = {"pubmed_flag_from_withdrawn_correction"}
FLAGGED = {"retracted", "retracted_unconfirmed", "disputed", "possibly_withdrawn", "concern",
           "self_loop_notice", "known_error"}
FAILED = {"not_found", "lookup_failed", "bad_doi"}

SUMMARY = {
    "retracted": "Retracted, and at least one source independent of the publisher's Crossref "
                 "update type confirms it.",
    "retracted_unconfirmed": "Shown as retracted only by the publisher's Crossref deposit; no "
                             "independent source confirms or contradicts it. Read the notice.",
    "disputed": "Crossref or PubMed shows a retraction, but the evidence says the notice is "
                "probably a correction (or a withdrawn correction, or points at the wrong paper). "
                "Read the notice before treating the paper as retracted.",
    "possibly_withdrawn": "Not shown as retracted in Crossref, but a linked notice is titled as a "
                          "withdrawal or retraction while typed as something else. Tools that "
                          "read the update type will miss it. Read the notice.",
    "concern": "An expression of concern is linked; the paper is not shown as retracted.",
    "self_loop_notice": "The record lists itself as its own retraction notice. It is most likely "
                        "the notice, not a retracted paper, though tools may show it as retracted.",
    "corrected": "Corrections or other updates are linked; no retraction found.",
    "no_notice": "No retraction, correction or concern found in Crossref or PubMed.",
    "not_found": "Crossref has no record for this DOI; nothing was checked (it may be a DataCite "
                 "DOI or mistyped).",
    "lookup_failed": "Crossref could not be reached; nothing was checked.",
    "bad_doi": "This is not a DOI.",
    "known_error": "Offline: listed in MV2's table of graded Crossref and PubMed errors.",
    "not_in_table": "Offline: not in the table of graded errors (this says nothing about its "
                    "status; run without --offline).",
}

# ---------------------------------------------------------------- text helpers
DASHES = "‐‑‒–—―−"
QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"'}
_KEY = r"(?:retractions|retraction|retracted|withdrawn|withdrawal)"
_NEXT = (r"(?:$|\s*[:.\-\])(,;]|\s+(?:note|notes|notice|notices|statement|of|to|for|and|"
         r"article|paper|publication|letter)\b)")
START = re.compile(r"^(?:notice of (?:retraction|withdrawal)\b|(?:partial |full )?" + _KEY + _NEXT + ")")
END = re.compile(r"[:.\-\[(]\s*[\[(]?\s*(?:retraction notice|notice of retraction|" + _KEY + r")$")
# "Retraction of ..." / "Withdrawal of ..." is a notice only when a quoted title or a word for a
# publication follows within four words; otherwise it is a topic ("Withdrawal of antihypertensive
# drugs in older people", "Withdrawal of life-sustaining treatment").
OF_START = re.compile(r"^(?:partial |full )?(?:retraction|withdrawal) of\s+(.*)$")
OF_OK = re.compile(r"^(?:['\"\[(]|(?:\S+\s+){0,3}(?:articles?|papers?|publications?|abstracts?|"
                   r"manuscripts?|chapters?|letters?|notices?)\b)")
# "Retraction and replacement" is a notice; "Withdrawal and Belonging" is a topic.
AND_START = re.compile(r"^(?:partial |full )?" + _KEY + r"\s+and\s+(\w+)")
AND_OK = {"republication", "replacement", "replace", "reissue", "correction", "corrections",
          "withdrawal", "retraction", "apology", "notice", "notices", "erratum", "errata"}
CORRECTION_START = re.compile(
    r"^(?:author correction|publisher correction|correction|corrections|corrigendum|corrigenda|"
    r"erratum|errata|addendum|addenda|clarification)\b")
# 0.2.0: the notice is itself a withdrawn or retracted correction ("WITHDRAWN: Corrigendum to X",
# "RETRACTED: Correction to X"). Same rule as audit 9's class WC.
_CORR = r"(?:corrigend(?:um|a)|errat(?:um|a)|corrections?(?=\s*(?::|to\b|for\b|notice\b|,|-|$)))"
WC_TITLE = re.compile(r"^(?:withdrawn|retracted)\s*[\]):.\-]*\s*" + _CORR)
RETRACT_WORD = re.compile(r"retract|withdraw")
CORRECT_WORD = re.compile(r"errat|corrig|correction")
EOC = re.compile(r"expressions? of concern")
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>{}]+")
REF_DOI = re.compile(r"doi:\s*(10\.\d{4,9}/\S+)", re.I)


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


def withdrawn_correction(title):
    """True if a notice title says the notice is itself a withdrawn or retracted correction
    ('WITHDRAWN: Corrigendum to ...', 'RETRACTED: Correction to ...'). Withdrawing a correction
    does not retract the paper it corrected."""
    return bool(WC_TITLE.match(core_title(title)))


def retraction_worded(title):
    """True if a title announces a retraction or withdrawal ('RETRACTED: ...', 'Withdrawn: ...',
    'Notice of retraction', '... [Retracted]', 'Retraction of "Title"'), False for topic titles
    such as 'Withdrawal of antihypertensive drugs in older people'."""
    c = core_title(title)
    if not c:
        return False
    if CORRECTION_START.match(c) or EOC.search(c):
        return False
    if END.search(c):
        return True
    m = OF_START.match(c)
    if m:
        return bool(OF_OK.match(m.group(1)))
    m = AND_START.match(c)
    if m:
        return m.group(1) in AND_OK
    return bool(START.match(c))


def correction_worded(title):
    c = core_title(title)
    if not c or RETRACT_WORD.search(c) or EOC.search(c):
        return False
    return bool(CORRECTION_START.match(c))


def title_class(title):
    """'withdrawn_correction' | 'correction' | 'mixed' | 'retraction' | 'eoc' | 'empty' | 'other'
    for a notice title."""
    c = core_title(title)
    if not c:
        return "empty"
    if withdrawn_correction(title):
        return "withdrawn_correction"
    if correction_worded(title):
        return "correction"
    if RETRACT_WORD.search(c) and CORRECT_WORD.search(c):
        return "mixed"
    if retraction_worded(title):
        return "retraction"
    if EOC.search(c):
        return "eoc"
    return "other"


def ws(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s or ""))).strip()


def short(s, n=90):
    s = ws(s)
    return s if len(s) <= n else s[:n - 3].rstrip() + "..."


def norm_doi(d):
    d = str(d or "").strip()
    low = d.lower()
    for p in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/",
              "doi:"):
        if low.startswith(p):
            d = d[len(p):]
            break
    return d.strip().lower()


def is_doi(d):
    return bool(re.match(r"^10\.\d{4,9}/\S+$", norm_doi(d)))


def norm_type(t):
    return re.sub(r"[\s\-]+", "_", str(t or "").strip().lower())


def first(v):
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


def strip_doi_tail(d):
    d = d.rstrip(".,;:")
    while d.endswith(")") and d.count(")") > d.count("("):
        d = d[:-1].rstrip(".,;:")
    return d


def extract_dois(text):
    """Unique DOIs in order of first appearance (BibTeX, RIS, plain lists, doi.org URLs)."""
    out, seen = [], set()
    for m in DOI_RE.finditer(text or ""):
        d = norm_doi(strip_doi_tail(m.group(0)))
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def load_known(path=KNOWN_PATH):
    """{target_doi: [row, ...]} from the graded-errors table; {} if it is missing."""
    out = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                t = norm_doi(row.get("target_doi"))
                if t:
                    out.setdefault(t, []).append(row)
    except OSError:
        pass
    return out


# ---------------------------------------------------------------- PubMed helpers
def ref_doi(refsource):
    """DOI quoted in a PubMed comment/correction citation ('... doi: 10.1/x.e1.'), or ''."""
    m = REF_DOI.search(str(refsource or ""))
    return m.group(1).rstrip(".,;").lower() if m else ""


def parse_pm_record(uid, d):
    refs = []
    for r in d.get("references") or []:
        if isinstance(r, dict):
            refs.append((str(r.get("reftype") or "").strip().lower(), str(r.get("pmid") or ""),
                         str(r.get("refsource") or "")))
    dois = [norm_doi(a.get("value")) for a in d.get("articleids") or []
            if isinstance(a, dict) and a.get("idtype") == "doi" and a.get("value")]
    return {"pmid": str(uid), "pubtype": [str(p) for p in d.get("pubtype") or []],
            "refs": refs, "dois": dois}


def is_notice_record(rec):
    return any(p.lower() in NOTICE_PUBTYPES for p in rec.get("pubtype") or [])


def pick_pm_record(doi, esummary):
    """The PubMed record carrying this DOI that is not itself a notice (else any), or None."""
    res = (esummary or {}).get("result") or {}
    found = []
    for uid in res.get("uids") or []:
        d = res.get(uid)
        if not isinstance(d, dict) or d.get("error"):
            continue
        rec = parse_pm_record(uid, d)
        if doi in rec["dois"]:
            found.append(rec)
    if not found:
        return None
    papers = [r for r in found if not is_notice_record(r)]
    return (papers or found)[0]


def pm_retracted(rec):
    if not rec:
        return False
    if any(p.lower() == "retracted publication" for p in rec["pubtype"]):
        return True
    return any(rt in PM_RETRACT_LINKS for rt, _, _ in rec["refs"])


def pm_retraction_notices(rec, pmid_doi=None, crossref_titles=None):
    """[(pmid, doi, title or None)] for each PubMed 'Retraction in' link of rec. The title comes
    from PubMed (rec['notice_titles'], filled by Net.pubmed) or, failing that, from the Crossref
    title of the same DOI."""
    out = []
    if not rec:
        return out
    pt = rec.get("notice_titles") or {}
    for rt, pmid, src in rec["refs"]:
        if rt not in PM_RETRACT_LINKS:
            continue
        d = ref_doi(src) or (pmid_doi or {}).get(pmid, "")
        t = pt.get(pmid) or ((crossref_titles or {}).get(d) if d else None)
        out.append((pmid, d, t))
    return out


def link_types_to(rec, notice, pmid_doi):
    """PubMed reftypes on rec whose linked item is the given notice DOI."""
    out = set()
    if not rec:
        return out
    for rt, pmid, src in rec["refs"]:
        d = ref_doi(src) or (pmid_doi or {}).get(pmid, "")
        if d and d == notice:
            out.add(rt)
    return out


def linked_pmids_without_doi(rec):
    want = PM_RETRACT_LINKS | PM_ERRATUM_LINKS | PM_EOC_LINKS
    return [p for rt, p, src in (rec or {}).get("refs", []) if rt in want and p and not ref_doi(src)]


# ---------------------------------------------------------------- the assessment (pure)
def blank(doi):
    return {"doi": doi, "title": "", "verdict": "", "summary": "", "evidence_for": [],
            "evidence_against": [], "notes": [], "relations": [], "pubmed": None,
            "openalex_is_retracted": None, "openalex_cited_by": None, "known_errors": []}


def assess(doi, work, notice_titles=None, pm=None, pmid_doi=None, oa=None, known=None):
    """Combine one Crossref work record with notice titles, a PubMed record, OpenAlex and the
    known-errors table into a verdict. Pure function: no network."""
    doi = norm_doi(doi)
    res = blank(doi)
    krows = list((known or {}).get(doi, []))
    res["known_errors"] = [{k: r.get(k, "") for k in ("notice_doi", "crossref_shows", "graded_as",
                                                      "evidence", "finding")} for r in krows]
    if work is None:
        res["verdict"] = "not_found"
        res["summary"] = SUMMARY["not_found"]
        return res
    title = first(work.get("title"))
    res["title"] = short(title, 300)
    titles = dict(notice_titles or {})
    titles.setdefault(doi, title)
    fo, ag, notes = res["evidence_for"], res["evidence_against"], res["notes"]

    rels = []
    for u in work.get("updated-by") or []:
        if not isinstance(u, dict):
            continue
        n = norm_doi(u.get("DOI"))
        if not n:
            continue
        nt = titles.get(n)
        rels.append({"notice": n, "type": norm_type(u.get("type")),
                     "source": str(u.get("source") or "publisher"),
                     "record_id": str(u.get("record-id") or ""),
                     "notice_title": short(nt, 200) if nt is not None else "",
                     "title_class": title_class(nt) if nt is not None else "unknown"})
    res["relations"] = rels

    retr_all = [r for r in rels if r["type"] in RETRACTIVE]
    self_loops = [r for r in retr_all if r["notice"] == doi]
    retr = [r for r in retr_all if r["notice"] != doi]
    pub_retr = [r for r in retr if r["source"] != "retraction-watch"]
    rw_retr = [r for r in retr if r["source"] == "retraction-watch"]
    marked = retraction_worded(title)
    pm_ret = pm_retracted(pm)
    # 0.2.0: PubMed's flag confirms a retraction unless every "Retraction in" notice is titled
    # as a withdrawn or retracted correction (then the flag comes from the withdrawn correction).
    rnotices = pm_retraction_notices(pm, pmid_doi, titles) if pm_ret else []
    pm_wc = bool(rnotices) and all(t and withdrawn_correction(t) for _, _, t in rnotices)
    pm_conf = pm_ret and not pm_wc
    if pm:
        res["pubmed"] = {"pmid": pm["pmid"], "retracted": pm_ret, "pubtype": pm["pubtype"],
                         "links": sorted({rt for rt, _, _ in pm["refs"]}),
                         "retraction_notices": [{"pmid": p, "doi": d, "title": short(t, 200) if t else ""}
                                                for p, d, t in rnotices],
                         "flag_from_withdrawn_correction": pm_wc}

    for r in rw_retr:
        fo.append("Retraction Watch lists notice %s as a %s%s." % (
            r["notice"], r["type"].replace("_", " "),
            " (record %s)" % r["record_id"] if r["record_id"] else ""))
    if marked:
        fo.append("The paper's own Crossref title is marked: '%s'." % short(title, 70))
    if pm_conf:
        fo.append("PubMed (PMID %s) marks the paper as retracted." % pm["pmid"])
    elif pm_wc:
        ag.append("PubMed (PMID %s) marks the paper retracted only because it links %s, titled "
                  "'%s', as 'Retraction in'. That notice withdraws a correction, not the paper." % (
                      pm["pmid"], ", ".join("PMID %s" % p for p, _, _ in rnotices),
                      short(rnotices[0][2], 70)))

    pm_against = False
    for r in pub_retr:
        tc = r["title_class"]
        kind = r["type"].replace("_", " ")
        if tc == "retraction":
            fo.append("The publisher's notice %s is titled '%s'." % (r["notice"], short(r["notice_title"], 70)))
        elif tc == "correction":
            ag.append("The publisher typed notice %s as a %s, but it is titled '%s'." % (
                r["notice"], kind, short(r["notice_title"], 70)))
        elif tc == "withdrawn_correction":
            ag.append("The publisher typed notice %s as a %s, but it is titled '%s': it withdraws "
                      "or retracts a correction, which does not retract the paper." % (
                          r["notice"], kind, short(r["notice_title"], 70)))
        elif tc == "mixed":
            notes.append("Notice %s is titled '%s', a mixed column: its title cannot say whether "
                         "this paper was retracted or corrected." % (r["notice"], short(r["notice_title"], 70)))
        rw_same = [x for x in rels if x["notice"] == r["notice"] and x["source"] == "retraction-watch"]
        if rw_same and not any(x["type"] in RETRACTIVE for x in rw_same):
            ag.append("Retraction Watch lists the same notice %s as a %s, not a %s." % (
                r["notice"], rw_same[0]["type"].replace("_", " "), kind))
        if pm and not pm_ret and (link_types_to(pm, r["notice"], pmid_doi) & PM_ERRATUM_LINKS):
            ag.append("PubMed (PMID %s) links the same notice %s as 'Erratum in' and does not mark "
                      "the paper retracted." % (pm["pmid"], r["notice"]))
            pm_against = True
    if pub_retr and pm and not pm_ret and not pm_against:
        if any(rt in PM_ERRATUM_LINKS for rt, _, _ in pm["refs"]):
            ag.append("PubMed (PMID %s) lists an erratum for the paper and does not mark it "
                      "retracted." % pm["pmid"])
        else:
            notes.append("PubMed (PMID %s) indexes the paper but does not mark it retracted "
                         "(PubMed can lag behind)." % pm["pmid"])

    pub_notices = {r["notice"] for r in pub_retr}
    for k in krows:
        g = k.get("graded_as", "")
        link = "%s/blob/main/%s" % (REPO, k.get("finding", ""))
        if g in KNOWN_NOT_RETRACTED:
            if norm_doi(k.get("notice_doi")) in pub_notices or g == "self_loop_notice_marked_retracted":
                ag.append("MV2's graded audit lists this as '%s': %s (%s)." % (g, k.get("evidence", ""), link))
            else:
                notes.append("MV2's audit listed notice %s as a mistyped %s; Crossref no longer "
                             "shows it as a retraction for this paper, so it may have been fixed."
                             % (k.get("notice_doi", ""), k.get("crossref_shows", "")))
        elif g in KNOWN_PUBMED_WC:
            if pm_wc or (pub_retr and not pm_conf):
                ag.append("MV2's graded audit lists this as '%s': %s (%s)." % (g, k.get("evidence", ""), link))
            elif pm_conf:
                notes.append("MV2's audit listed this paper as shown retracted only via a withdrawn "
                             "correction, but PubMed now links a retraction notice not titled that "
                             "way: the paper may since have been retracted. Read the notice.")
            elif pm:
                notes.append("MV2's audit listed this paper as shown retracted in PubMed only via a "
                             "withdrawn correction; PubMed no longer marks it retracted, so it may "
                             "have been fixed.")

    for r in self_loops:
        notes.append("The record lists itself (%s) as its own %s notice." % (r["notice"], r["type"].replace("_", " ")))
    ut = [norm_doi(u.get("DOI")) for u in work.get("update-to") or [] if isinstance(u, dict)]
    ut = sorted({x for x in ut if x and x != doi})
    if ut:
        listed = ", ".join(ut[:5]) + (" and %d more" % (len(ut) - 5) if len(ut) > 5 else "")
        notes.append("This record also carries update-to links (it says it updates %s). If it is "
                     "a research article and not a notice, those links are probably reversed."
                     % listed)

    indep_for = bool(rw_retr or marked or pm_conf or any(r["title_class"] == "retraction" for r in pub_retr))
    if retr or pm_ret or marked:
        if indep_for:
            verdict = "retracted"
            if ag:
                notes.append("Some records disagree (see evidence against); the independent "
                             "evidence of retraction outweighs them, but read the notice.")
            if not retr:
                notes.append("Crossref links no retraction notice to this record, so tools that "
                             "read only Crossref update types will miss it.")
        elif ag:
            verdict = "disputed"
        else:
            verdict = "retracted_unconfirmed"
    elif self_loops:
        verdict = "self_loop_notice"
    else:
        mistyped = [r for r in rels if r["type"] not in RETRACTIVE and r["title_class"] == "retraction"]
        kwd = [k for k in krows if k.get("graded_as") in KNOWN_WITHDRAWN]
        for r in mistyped:
            fo.append("Notice %s is titled '%s' but typed '%s', so tools that read the update type "
                      "do not show this paper as withdrawn or retracted." % (
                          r["notice"], short(r["notice_title"], 70), r["type"]))
        for k in kwd:
            fo.append("MV2's audit lists this paper as withdrawn but deposited as an addendum (%s/blob/main/%s)."
                      % (REPO, k.get("finding", "")))
        pm_links = {rt for rt, _, _ in pm["refs"]} if pm else set()
        if mistyped or kwd:
            verdict = "possibly_withdrawn"
        elif any(r["type"] in EOC_TYPES for r in rels) or (pm_links & PM_EOC_LINKS):
            verdict = "concern"
        elif rels or (pm_links & PM_ERRATUM_LINKS):
            verdict = "corrected"
        else:
            verdict = "no_notice"

    if oa is not None:
        res["openalex_is_retracted"], res["openalex_cited_by"] = oa
        if oa[0] is True and verdict in ("disputed", "self_loop_notice"):
            if retr_all:
                notes.append("OpenAlex shows it as retracted (is_retracted true), following the "
                             "Crossref deposit.")
            else:
                notes.append("OpenAlex shows it as retracted (is_retracted true), although Crossref "
                             "links no retraction notice to it; PubMed's flag is the only other "
                             "source checked here that does.")
        elif oa[0] is True and verdict in ("corrected", "no_notice", "concern"):
            notes.append("OpenAlex marks it retracted, but no source checked here does; check "
                         "where OpenAlex took that from.")
        elif oa[0] is False and verdict == "retracted":
            notes.append("OpenAlex does not mark it retracted (is_retracted false).")
        elif oa[0] is False and verdict == "possibly_withdrawn":
            notes.append("OpenAlex does not mark it retracted either (is_retracted false).")
    res["verdict"] = verdict
    res["summary"] = SUMMARY[verdict]
    return res


def assess_offline(doi, known):
    doi = norm_doi(doi)
    res = blank(doi)
    krows = (known or {}).get(doi, [])
    res["known_errors"] = [{k: r.get(k, "") for k in ("notice_doi", "crossref_shows", "graded_as",
                                                      "evidence", "finding")} for r in krows]
    res["verdict"] = "known_error" if krows else "not_in_table"
    res["summary"] = SUMMARY[res["verdict"]]
    for k in krows:
        res["notes"].append("Crossref shows a %s from notice %s; graded as %s: %s." % (
            k.get("crossref_shows", ""), k.get("notice_doi", ""), k.get("graded_as", ""),
            k.get("evidence", "")))
    return res


# ---------------------------------------------------------------- network
class LookupFailed(Exception):
    pass


class Net:
    """Read-only JSON GETs with polite pacing and a few retries."""

    def __init__(self, gap=0.4, timeout=30, tries=3):
        self.gap, self.timeout, self.tries = gap, timeout, tries
        self.last = {}

    def get(self, url, host):
        delay = 2
        for _ in range(self.tries):
            wait = self.last.get(host, 0.0) + self.gap - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last[host] = time.monotonic()
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (400, 404, 410):
                    return None
            except (urllib.error.URLError, OSError, ValueError):
                pass
            time.sleep(delay)
            delay *= 2
        raise LookupFailed(url)

    def crossref_work(self, doi):
        obj = self.get("%s/%s?mailto=%s" % (CROSSREF, urllib.parse.quote(doi, safe="/()"), MAILTO), "crossref")
        msg = (obj or {}).get("message")
        return msg if isinstance(msg, dict) else None

    def crossref_titles(self, dois):
        out = {}
        dois = [d for d in dois if "," not in d]
        for i in range(0, len(dois), 20):
            b = dois[i:i + 20]
            f = ",".join("doi:" + urllib.parse.quote(d, safe="/()") for d in b)
            obj = self.get("%s?filter=%s&rows=%d&select=DOI,title&mailto=%s" % (CROSSREF, f, len(b) + 5, MAILTO),
                           "crossref")
            for it in ((obj or {}).get("message") or {}).get("items") or []:
                out[norm_doi(it.get("DOI"))] = first(it.get("title"))
        return out

    def esummary(self, pmids):
        q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "id": ",".join(pmids),
                                    "tool": TOOL, "email": MAILTO})
        return self.get(EUTILS + "esummary.fcgi?" + q, "ncbi")

    def pubmed(self, doi):
        """(record or None, {pmid: doi} for linked notices). The record carries
        'notice_titles' = {pmid: title} for its 'Retraction in' notices (0.2.0)."""
        q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "retmax": "5",
                                    "term": "%s[doi]" % doi, "tool": TOOL, "email": MAILTO})
        obj = self.get(EUTILS + "esearch.fcgi?" + q, "ncbi")
        ids = ((obj or {}).get("esearchresult") or {}).get("idlist") or []
        if not ids:
            return None, {}
        rec = pick_pm_record(doi, self.esummary([str(i) for i in ids[:5]]))
        if rec is None:
            return None, {}
        need = linked_pmids_without_doi(rec)[:10]
        rin = [p for rt, p, _ in rec["refs"] if rt in PM_RETRACT_LINKS and p][:10]
        ask = list(dict.fromkeys(need + rin))
        pmid_doi, ntitles = {}, {}
        if ask:
            res = (self.esummary(ask) or {}).get("result") or {}
            for uid in res.get("uids") or []:
                d = res.get(uid)
                if not isinstance(d, dict) or d.get("error"):
                    continue
                r = parse_pm_record(uid, d)
                if r["dois"]:
                    pmid_doi[str(uid)] = r["dois"][0]
                if d.get("title"):
                    ntitles[str(uid)] = str(d.get("title"))
        rec["notice_titles"] = ntitles
        return rec, pmid_doi

    def openalex(self, doi):
        if "|" in doi or "," in doi:
            return None
        obj = self.get("%s?filter=doi:%s&select=doi,is_retracted,cited_by_count&mailto=%s"
                       % (OPENALEX, urllib.parse.quote(doi, safe="/()"), MAILTO), "openalex")
        for r in (obj or {}).get("results") or []:
            if norm_doi(r.get("doi")) == doi:
                return (r.get("is_retracted"), r.get("cited_by_count"))
        return None


def check(doi, net, known, use_pubmed=True, use_openalex=True):
    doi = norm_doi(doi)
    if not is_doi(doi):
        r = blank(doi)
        r["verdict"], r["summary"] = "bad_doi", SUMMARY["bad_doi"]
        return r
    try:
        work = net.crossref_work(doi)
    except LookupFailed:
        r = blank(doi)
        r["verdict"], r["summary"] = "lookup_failed", SUMMARY["lookup_failed"]
        return r
    extra = []
    titles, pm, pmid_doi, oa = {}, None, {}, None
    if work is not None:
        notices = sorted({norm_doi(u.get("DOI")) for u in work.get("updated-by") or []
                          if isinstance(u, dict) and u.get("DOI")} - {doi})
        if notices:
            try:
                titles = net.crossref_titles(notices)
            except LookupFailed:
                extra.append("Notice titles could not be read from Crossref.")
        if use_pubmed:
            try:
                pm, pmid_doi = net.pubmed(doi)
                if pm is None:
                    extra.append("Not found in PubMed.")
            except LookupFailed:
                extra.append("PubMed could not be reached; PubMed was not checked.")
        if use_openalex:
            try:
                oa = net.openalex(doi)
            except LookupFailed:
                extra.append("OpenAlex could not be reached.")
    res = assess(doi, work, titles, pm, pmid_doi, oa, known)
    res["notes"].extend(extra)
    return res


# ---------------------------------------------------------------- output
def render(res):
    lines = ["%s  %s" % (res["doi"], res["verdict"].upper().replace("_", " "))]
    if res["title"]:
        lines.append("  " + short(res["title"], 110))
    lines.append("  " + res["summary"])
    for r in res["relations"]:
        t = (" titled '%s'" % short(r["notice_title"], 60)) if r["notice_title"] else ""
        lines.append("  crossref: %s from %s (%s%s)%s" % (
            r["type"].replace("_", " "), r["notice"], r["source"],
            ", record %s" % r["record_id"] if r["record_id"] else "", t))
    if res["pubmed"]:
        p = res["pubmed"]
        lines.append("  pubmed: PMID %s, %s; links: %s" % (
            p["pmid"], "retracted" if p["retracted"] else "not marked retracted",
            ", ".join(p["links"]) or "none"))
        for n in p.get("retraction_notices") or []:
            if n.get("title"):
                lines.append("  pubmed: retraction in PMID %s titled '%s'" % (n["pmid"], short(n["title"], 60)))
    if res["openalex_is_retracted"] is not None:
        lines.append("  openalex: is_retracted %s, cited by %s" % (
            str(res["openalex_is_retracted"]).lower(), res["openalex_cited_by"]))
    for x in res["evidence_for"]:
        lines.append("  for: " + x)
    for x in res["evidence_against"]:
        lines.append("  against: " + x)
    for x in res["notes"]:
        lines.append("  note: " + x)
    return "\n".join(lines)


def exit_code(results):
    if any(r["verdict"] in FAILED for r in results):
        return 2
    if any(r["verdict"] in FLAGGED for r in results):
        return 1
    return 0


def main(argv=None, net=None, out=None):
    out = out or sys.stdout
    ap = argparse.ArgumentParser(prog="retraction_crosscheck.py",
                                 description="Cross-check whether papers are really retracted.")
    ap.add_argument("dois", nargs="*", help="DOIs or doi.org URLs")
    ap.add_argument("--file", help="read DOIs from a file (BibTeX, RIS, plain text); '-' = stdin")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--offline", action="store_true", help="only look DOIs up in the known-errors table")
    ap.add_argument("--known", action="store_true", help="print the known-errors table and exit")
    ap.add_argument("--no-pubmed", action="store_true")
    ap.add_argument("--no-openalex", action="store_true")
    ap.add_argument("--max", type=int, default=200, help="most DOIs to check (default 200)")
    ap.add_argument("--version", action="version", version=VERSION)
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    known = load_known()
    if a.known:
        rows = [dict(r, target_doi=t) for t, rs in sorted(known.items()) for r in rs]
        if a.json:
            out.write(json.dumps(rows, indent=1) + "\n")
        else:
            for r in rows:
                out.write("%s\t%s\t%s\t%s\n" % (r["target_doi"], r.get("crossref_shows", ""),
                                                r.get("graded_as", ""), r.get("notice_doi", "")))
            out.write("%d graded errors from %s\n" % (len(rows), REPO))
        return 0 if rows else 2
    text = " ".join(a.dois)
    if a.file:
        try:
            if a.file == "-":
                text += "\n" + sys.stdin.read()
            else:
                with open(a.file, encoding="utf-8", errors="replace") as f:
                    text += "\n" + f.read()
        except OSError as e:
            out.write("cannot read %s: %s\n" % (a.file, e))
            return 2
    dois = extract_dois(text)
    if not dois:
        out.write("no DOI given\n")
        return 2
    if len(dois) > a.max:
        out.write("checking the first %d of %d DOIs (raise --max to check more)\n" % (a.max, len(dois)))
        dois = dois[:a.max]
    if a.offline:
        results = [assess_offline(d, known) for d in dois]
    else:
        net = net or Net()
        results = [check(d, net, known, not a.no_pubmed, not a.no_openalex) for d in dois]
    if a.json:
        out.write(json.dumps({"version": VERSION, "results": results}, indent=1, ensure_ascii=False) + "\n")
    else:
        for r in results:
            out.write(render(r) + "\n\n")
        counts = {}
        for r in results:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        out.write("checked %d: %s\n" % (len(results), ", ".join("%s %d" % kv for kv in sorted(counts.items()))))
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
