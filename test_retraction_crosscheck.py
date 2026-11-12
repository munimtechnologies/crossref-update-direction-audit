# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Offline tests for skills/retraction-crosscheck (no network).

Crossref fixtures copy the fields of the live records read on 2026-11-09 (updated-by entries,
notice titles). PubMed fixtures for 10.1096/fj.09-135467 copy its live esummary (PMID 19525403);
the other PubMed records and every OpenAlex count are synthetic, except the Cochrane and Clin J
Sport Med fixtures (0.1.1), which copy live Crossref records read on 2026-11-09, and the J Am Acad
Dermatol and Int J Biol Macromol fixtures (0.2.0), which copy live PubMed esummary records and
Crossref titles read on 2026-11-10. The 0.2.1 test uses PubMed's current notice type name
"Retraction Notice" (as in live esummary replies of 2026-11-11).
"""
import csv
import importlib.util
import io
import json
import os
import re
import shlex
import tempfile
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(ROOT, "skills", "retraction-crosscheck")
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
SCRIPT = os.path.join(SKILL_DIR, "scripts", "retraction_crosscheck.py")
KNOWN = os.path.join(SKILL_DIR, "data", "known_errors.csv")


def load():
    spec = importlib.util.spec_from_file_location("retraction_crosscheck", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rc = load()

FJ = "10.1096/fj.09-135467"
FJ_N = "10.1096/fj.09-135467err"
BSR = "10.1042/bsr20181233"
BSR_N = "10.1042/bsr-20181233_cor"
LAN = "10.1016/s0140-6736(20)31180-6"
IWA = "10.2166/wp.2021.019"
IWA_N = "10.2166/wp.2022.000"
LOOP = "10.1111/aos.14512"
COCH = "10.1002/14651858.cd012572"
COCH_N = "10.1002/14651858.cd012572.pub2"
SIS = "10.1097/00042752-200107000-00004"
SIS_N = "10.1097/jsm.0000000000001119"
# 0.2.0: J Am Acad Dermatol chronic GVHD review Part I; its withdrawn correction
JAAD = "10.1016/j.jaad.2022.12.024"
JAAD_N = "10.1016/j.jaad.2026.01.065"
JAAD_WC = ("WITHDRAWN: Correction to Chronic graft-versus-host disease. Part I: Epidemiology, "
           "pathogenesis, and clinical manifestations [Journal of the American Academy of "
           "Dermatology 2024 Jan;90(1)1-16]")
# 0.2.0: Int J Biol Macromol paper; its standing corrigendum and its withdrawn duplicate
IJBM = "10.1016/j.ijbiomac.2024.136739"
IJBM_E = "10.1016/j.ijbiomac.2024.138563"
IJBM_W = "10.1016/j.ijbiomac.2024.138635"
IJBM_T = ("Preparation, characterization, stability and application of the H-type aggregates "
          "lutein/whey protein/chitosan nanoparticles")

WORKS = {
    FJ: {"title": ["Genetic requirements for <i>Staphylococcus aureus</i> abscess formation and "
                   "persistence in host tissues"],
         "updated-by": [{"DOI": FJ_N, "type": "retraction", "source": "publisher", "label": "Retraction"}]},
    BSR: {"title": ["Systematic identification of Celastrol-binding proteins reveals that Shoc2 is "
                    "inhibited by Celastrol"],
          "updated-by": [
              {"DOI": BSR_N, "type": "correction", "source": "retraction-watch", "record-id": 41012},
              {"DOI": BSR_N, "type": "retraction", "source": "publisher"}]},
    LAN: {"title": ["RETRACTED: Hydroxychloroquine or chloroquine with or without a macrolide for "
                    "treatment of COVID-19: a multinational registry analysis"],
          "updated-by": [
              {"DOI": "10.1016/s0140-6736(20)31290-3", "type": "expression_of_concern",
               "source": "retraction-watch", "record-id": 23527},
              {"DOI": "10.1016/s0140-6736(20)31249-6", "type": "correction",
               "source": "retraction-watch", "record-id": 23528},
              {"DOI": "10.1016/s0140-6736(20)31324-6", "type": "retraction",
               "source": "retraction-watch", "record-id": 23529},
              {"DOI": "10.1016/s0140-6736(20)31174-0", "type": "retraction", "source": "publisher"},
              {"DOI": "10.1016/s0140-6736(20)31324-6", "type": "erratum", "source": "publisher"},
              {"DOI": "10.1016/s0140-6736(20)31528-2", "type": "erratum", "source": "publisher"},
              {"DOI": "10.1016/s0140-6736(20)31249-6", "type": "erratum", "source": "publisher"}],
          "update-to": [{"DOI": "10.1016/s0140-6736(20)31174-0", "type": "retraction", "source": "publisher"},
                        {"DOI": "10.1016/s0140-6736(20)31290-3", "type": "retraction", "source": "publisher"},
                        {"DOI": "10.1016/s0140-6736(20)31324-6", "type": "retraction", "source": "publisher"},
                        {"DOI": "10.1016/s0140-6736(20)31528-2", "type": "retraction", "source": "publisher"}]},
    IWA: {"title": ["Estimating the economic impact of large hydropower projects: a dynamic "
                    "multi-regional computable general equilibrium analysis"],
          "updated-by": [{"DOI": IWA_N, "type": "addendum", "source": "publisher"}],
          "update-to": [{"DOI": IWA_N, "type": "addendum", "source": "publisher"}]},
    LOOP: {"title": ["Erratum"],
           "updated-by": [{"DOI": LOOP, "type": "retraction", "source": "publisher"}]},
    COCH: {"title": ["Withdrawal of antihypertensive drugs in older people"],
           "updated-by": [{"DOI": COCH_N, "type": "new_version", "source": "publisher",
                           "label": "New version"}]},
    SIS: {"title": ["Does Second Impact Syndrome Exist?"],
          "updated-by": [{"DOI": SIS_N, "type": "correction", "source": "publisher",
                          "label": "Correction"}]},
    JAAD: {"title": ["Chronic graft-versus-host disease. Part I: Epidemiology, pathogenesis, and "
                     "clinical manifestations"],
           "updated-by": [{"DOI": JAAD_N, "type": "erratum", "source": "publisher"}]},
}
TITLES = {
    FJ_N: "Erratum",
    BSR_N: "Correction: Systematic identification of celastrol-binding proteins reveals that Shoc2 "
           "is inhibited by celastrol",
    IWA_N: "Withdrawn: Estimating the economic impact of large hydropower projects: a dynamic "
           "multi-regional computable general equilibrium analysis",
    COCH_N: "Withdrawal of antihypertensive drugs in older people",
    SIS_N: "Does Second Impact Syndrome Exist? [RETRACTED]",
    JAAD_N: JAAD_WC,
}


def pm_rec(uid, pubtype, refs, doi):
    return rc.parse_pm_record(uid, {
        "pubtype": pubtype, "articleids": [{"idtype": "doi", "value": doi}],
        "references": [{"reftype": t, "pmid": p, "refsource": s} for t, p, s in refs]})


PUBMED = {
    FJ: (pm_rec("19525403", ["Journal Article", "Research Support, N.I.H., Extramural"],
                [("Erratum in", "", "FASEB J. 2010 Feb;24(2):648")], FJ), {}),
    BSR: (pm_rec("900001", ["Journal Article"],
                 [("Erratum in", "900002", "Biosci Rep. 2021;41(4). doi: 10.1042/BSR-20181233_COR.")], BSR), {}),
    LAN: (pm_rec("900003", ["Journal Article", "Retracted Publication"],
                 [("Retraction in", "900004", "Lancet. 2020;395:1820. doi: 10.1016/S0140-6736(20)31324-6.")], LAN), {}),
    SIS: (pm_rec("11495318", ["Journal Article", "Review"], [], SIS), {}),
    # live esummary of PMID 36572065 (2026-11-10); no notice_titles: the title comes from Crossref
    JAAD: (pm_rec("36572065", ["Journal Article", "Review", "Retracted Publication"],
                  [("Retraction in", "41621663", "J Am Acad Dermatol. 2026 Jan 30:S0190-9622(26)00117-9. "
                                                 "doi: 10.1016/j.jaad.2026.01.065.")], JAAD), {}),
}
OA = {FJ: (True, 442), BSR: (True, 19), LAN: (True, 1000), IWA: (False, 3), LOOP: (True, 0),
      COCH: (False, 50), SIS: (False, 193), JAAD: (True, 61)}


class FakeNet:
    def __init__(self, fail=False):
        self.fail = fail

    def crossref_work(self, doi):
        if self.fail:
            raise rc.LookupFailed(doi)
        return WORKS.get(doi)

    def crossref_titles(self, dois):
        return {d: TITLES[d] for d in dois if d in TITLES}

    def pubmed(self, doi):
        return PUBMED.get(doi, (None, {}))

    def openalex(self, doi):
        return OA.get(doi)


class GetNet(rc.Net):
    """The real Net with get() answered from copies of live replies (IJBM, read 2026-11-10)."""

    def __init__(self):
        rc.Net.__init__(self)
        self.urls = []

    def get(self, url, host):
        self.urls.append(url)
        if host == "crossref":
            if "filter=" in url:
                return {"message": {"items": [{"DOI": IJBM_E, "title": [
                    "Corrigendum to “" + IJBM_T + "” [Int. J. Biol. Macromol., volume 282, "
                    "part 32, page 136739]"]}]}}
            return {"message": {"title": [IJBM_T], "updated-by": [
                {"DOI": IJBM_E, "type": "erratum", "source": "publisher"}]}}
        if host == "ncbi":
            if "esearch.fcgi" in url:
                return {"esearchresult": {"idlist": ["39437953"]}}
            if "id=39731814" in url:
                return {"result": {"uids": ["39731814"], "39731814": {
                    "title": "WITHDRAWN: Corrigendum to \"" + IJBM_T + "\" [Int J Biol Macromol 282 "
                             "(2024) 136739].",
                    "pubtype": ["Journal Article", "Retraction Notice"],
                    "articleids": [{"idtype": "doi", "value": IJBM_W}],
                    "references": [{"reftype": "Retraction of", "pmid": "39437953",
                                    "refsource": "Int J Biol Macromol. 2024 Dec;282(Pt 2):136739. "
                                                 "doi: 10.1016/j.ijbiomac.2024.136739."}]}}}
            return {"result": {"uids": ["39437953"], "39437953": {
                "title": IJBM_T + ".",
                "pubtype": ["Journal Article", "Retracted Publication"],
                "articleids": [{"idtype": "doi", "value": IJBM}],
                "references": [
                    {"reftype": "Erratum in", "pmid": "39693841",
                     "refsource": "Int J Biol Macromol. 2025 Feb;288:138563. doi: 10.1016/j.ijbiomac.2024.138563."},
                    {"reftype": "Retraction in", "pmid": "39731814",
                     "refsource": "Int J Biol Macromol. 2025 Feb;289:138635. doi: 10.1016/j.ijbiomac.2024.138635."}]}}}
        if host == "openalex":
            return {"results": [{"doi": "https://doi.org/" + IJBM, "is_retracted": True,
                                 "cited_by_count": 11}]}
        return None


def run(argv):
    out = io.StringIO()
    code = rc.main(argv, net=FakeNet(), out=out)
    return code, out.getvalue()


class SkillFile(unittest.TestCase):
    def setUp(self):
        with open(SKILL_MD, encoding="utf-8") as f:
            self.text = f.read()

    def test_frontmatter(self):
        m = re.match(r"^---\n(.*?)\n---\n", self.text, re.S)
        self.assertIsNotNone(m)
        fm = dict(line.split(": ", 1) for line in m.group(1).splitlines())
        self.assertEqual(fm["name"], "retraction-crosscheck")
        self.assertEqual(fm["license"], "Apache-2.0")
        self.assertLess(len(fm["description"]), 1024)
        self.assertIn("retracted", fm["description"])

    def test_disclosure_and_licence(self):
        self.assertIn("Made with AI agents", self.text)
        self.assertIn("MV2, Munim, Inc., mv2@munimtech.com", self.text)
        with open(SCRIPT, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("Apache-2.0", src)
        self.assertIn("Made with AI agents", src)
        self.assertNotIn("MIT License", self.text + src)

    def test_documented_commands_run(self):
        cmds = [l.strip() for l in self.text.splitlines()
                if l.strip().startswith("python scripts/retraction_crosscheck.py")]
        self.assertGreaterEqual(len(cmds), 5)
        ran = 0
        for c in cmds:
            args = shlex.split(c)[2:]
            if "--file" in args:
                continue
            code, out = run(args)
            self.assertIn(code, (0, 1), c)
            self.assertTrue(out.strip(), c)
            ran += 1
        self.assertGreaterEqual(ran, 4)

    def test_every_verdict_documented(self):
        for v in ("retracted", "retracted_unconfirmed", "disputed", "possibly_withdrawn", "concern",
                  "self_loop_notice", "corrected", "no_notice", "not_found", "lookup_failed"):
            self.assertIn("`%s`" % v, self.text)
            self.assertIn(v, rc.SUMMARY)


class KnownTable(unittest.TestCase):
    def test_table(self):
        with open(KNOWN, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 49)
        allowed = rc.KNOWN_NOT_RETRACTED | rc.KNOWN_WITHDRAWN | rc.KNOWN_PUBMED_WC
        for r in rows:
            self.assertIn(r["graded_as"], allowed)
            self.assertTrue(rc.is_doi(r["target_doi"]) and rc.is_doi(r["notice_doi"]), r)
            self.assertEqual(r["target_doi"], r["target_doi"].lower())
            self.assertIn(r["finding"], ("findings/corrections-deposited-as-retractions.md",
                                         "findings/iwa-withdrawn-as-addendum.md",
                                         "findings/pubmed-shows-withdrawn-corrigenda-as-retractions.md",
                                         "findings/pubmed-withdrawn-corrigenda-update-audit9.md"))
        self.assertEqual(sum(r["graded_as"] == "withdrawn_typed_addendum" for r in rows), 19)
        self.assertEqual(sum(r["graded_as"] == "pubmed_flag_from_withdrawn_correction" for r in rows), 9)
        known = rc.load_known()
        self.assertIn(FJ, known)
        self.assertIn(JAAD, known)
        self.assertEqual(rc.load_known(os.path.join(ROOT, "no-such-file.csv")), {})


class Helpers(unittest.TestCase):
    def test_extract_dois(self):
        text = ("@article{a, doi = {10.1096/fj.09-135467},}\n"
                "see https://doi.org/10.1016/S0140-6736(20)31180-6). and doi:10.1042/BSR20181233.\n"
                "again 10.1096/fj.09-135467")
        self.assertEqual(rc.extract_dois(text), [FJ, LAN, BSR])
        self.assertEqual(rc.extract_dois("no dois here"), [])

    def test_title_classes(self):
        self.assertEqual(rc.title_class("Erratum"), "correction")
        self.assertEqual(rc.title_class("Correction to: Fractal Dimension"), "correction")
        self.assertEqual(rc.title_class("Retractions and Errata"), "mixed")
        self.assertEqual(rc.title_class(TITLES[IWA_N]), "retraction")
        self.assertEqual(rc.title_class("Retraction notice to: A study of mice"), "retraction")
        self.assertEqual(rc.title_class("Expression of Concern: A study"), "eoc")
        self.assertEqual(rc.title_class(""), "empty")
        self.assertTrue(rc.retraction_worded(WORKS[LAN]["title"][0]))
        self.assertFalse(rc.retraction_worded(WORKS[FJ]["title"][0]))

    def test_withdrawn_correction_titles(self):
        # 0.2.0: titles of the withdrawn corrections behind audits 8 and 9 (live, 2026-11-10)
        for t in (JAAD_WC,
                  "WITHDRAWN: Corrigendum to “Red Wine Prevents the Acute Negative Vascular "
                  "Effects of Smoking”",
                  "WITHDRAWN: corrigendum to “Effectiveness of complementary pain treatment”",
                  "[WITHDRAWN: Corrigendum to A study]",
                  "RETRACTED: Corrigendum to X",
                  "Retracted - Erratum to: X"):
            self.assertTrue(rc.withdrawn_correction(t), t)
            self.assertEqual(rc.title_class(t), "withdrawn_correction", t)
        # audit 9: these are real retraction notices and must not be read as withdrawn corrections
        for t in ("Retraction: Erratum to \"The effectiveness of Korean number naming\"",
                  "Retraction note. Erratum to: Pulmonary function in children",
                  "Erratum to: A study of mice",
                  "Withdrawn: Estimating the economic impact of large hydropower projects",
                  "RETRACTED: Corrections in surgery: a cohort study",
                  "Retractions and Errata"):
            self.assertFalse(rc.withdrawn_correction(t), t)
        self.assertEqual(rc.title_class("RETRACTED: Corrections in surgery: a cohort study"), "mixed")

    def test_topic_titles_are_not_notices(self):
        # 0.1.1: titles that name a topic, found among audit 4b's "hidden" notices
        for t in ("Withdrawal of antihypertensive drugs in older people",
                  "Withdrawal of immunosuppressant or biologic therapy for patients with quiescent "
                  "Crohn's disease",
                  "Withdrawal of life-sustaining treatment in the intensive care unit",
                  "Withdrawal and Belonging: Ethnographic Insights from a Hikikomori Rehabilitation "
                  "Center in Japan – ERRATUM",
                  "Withdrawal and relapse after stopping biologics"):
            self.assertFalse(rc.retraction_worded(t), t)
            self.assertNotEqual(rc.title_class(t), "retraction", t)

    def test_real_notice_titles_still_match(self):
        for t in ("Retraction of “Recent advance in hepatic insulin gene therapy” [Diabetes Res. "
                  "Clin. Pract. 66 (Suppl. 1) (2004) S3–S10]",
                  "Retraction of APS Meeting Abstracts",
                  "RETRACTION OF ARTICLES",
                  "Withdrawal of ‘Precision Neoantigen Discovery Using Large-scale Immunopeptidomes’",
                  "Withdrawal of the article by Smith et al.",
                  "Retraction and republication—De-escalation of adjuvant radiotherapy in "
                  "HPV-associated oropharyngeal cancer",
                  "Notice of Retraction and Replacement: A trial",
                  "Does Second Impact Syndrome Exist? [RETRACTED]",
                  "WITHDRAWAL – Administrative Duplicate Publication: A study",
                  "Retraction note to: Characterization of coconut oil flow behavior",
                  TITLES[IWA_N]):
            self.assertTrue(rc.retraction_worded(t), t)

    def test_norm_and_ref_doi(self):
        self.assertEqual(rc.norm_doi("https://doi.org/10.1042/BSR20181233"), BSR)
        self.assertEqual(rc.norm_doi("doi:10.1042/BSR20181233 "), BSR)
        self.assertTrue(rc.is_doi(LAN))
        self.assertFalse(rc.is_doi("hello"))
        self.assertEqual(rc.ref_doi("Biosci Rep. doi: 10.1042/BSR-20181233_COR."), BSR_N)
        self.assertEqual(rc.ref_doi("FASEB J. 2010 Feb;24(2):648"), "")

    def test_pick_pm_record_prefers_paper(self):
        es = {"result": {"uids": ["1", "2"],
                         "1": {"pubtype": ["Published Erratum"], "articleids": [{"idtype": "doi", "value": FJ}]},
                         "2": {"pubtype": ["Journal Article"], "articleids": [{"idtype": "doi", "value": FJ}]}}}
        self.assertEqual(rc.pick_pm_record(FJ, es)["pmid"], "2")
        self.assertIsNone(rc.pick_pm_record(BSR, es))

    def test_pick_pm_record_skips_retraction_notice(self):
        # 0.2.1: PubMed renamed "Retraction of Publication" to "Retraction Notice" (MeSH 2025).
        # 0.2.0 knew only the old name, so a notice listed first was picked as the paper.
        es = {"result": {"uids": ["1", "2"],
                         "1": {"pubtype": ["Journal Article", "Retraction Notice"],
                               "articleids": [{"idtype": "doi", "value": FJ}]},
                         "2": {"pubtype": ["Journal Article"], "articleids": [{"idtype": "doi", "value": FJ}]}}}
        self.assertEqual(rc.pick_pm_record(FJ, es)["pmid"], "2")
        es["result"]["1"]["pubtype"] = ["Retraction of Publication"]
        self.assertEqual(rc.pick_pm_record(FJ, es)["pmid"], "2")
        self.assertTrue(rc.is_notice_record({"pubtype": ["Retraction Notice"]}))
        self.assertFalse(rc.is_notice_record({"pubtype": ["Journal Article", "Retracted Publication"]}))


class Assess(unittest.TestCase):
    def setUp(self):
        self.known = rc.load_known()

    def full(self, doi):
        return rc.check(doi, FakeNet(), self.known)

    def test_correction_typed_retraction_is_disputed(self):
        r = self.full(FJ)
        self.assertEqual(r["verdict"], "disputed")
        self.assertEqual(len(r["evidence_for"]), 0)
        joined = " ".join(r["evidence_against"])
        self.assertIn("titled 'Erratum'", joined)
        self.assertIn("lists an erratum", joined)
        self.assertIn("graded audit", joined)
        self.assertTrue(any("OpenAlex shows it as retracted" in n for n in r["notes"]))
        self.assertEqual(r["pubmed"]["pmid"], "19525403")

    def test_retraction_watch_and_pubmed_disagree_with_publisher(self):
        r = self.full(BSR)
        self.assertEqual(r["verdict"], "disputed")
        joined = " ".join(r["evidence_against"])
        self.assertIn("Retraction Watch lists the same notice", joined)
        self.assertIn("'Erratum in'", joined)
        self.assertEqual(len(r["evidence_against"]), 4)

    def test_genuine_retraction(self):
        r = self.full(LAN)
        self.assertEqual(r["verdict"], "retracted")
        self.assertGreaterEqual(len(r["evidence_for"]), 3)
        self.assertEqual(r["evidence_against"], [])
        self.assertTrue(any("update-to links" in n for n in r["notes"]))
        self.assertFalse(r["pubmed"]["flag_from_withdrawn_correction"])

    def test_withdrawn_typed_addendum(self):
        r = self.full(IWA)
        self.assertEqual(r["verdict"], "possibly_withdrawn")
        self.assertTrue(any("typed 'addendum'" in x for x in r["evidence_for"]))
        self.assertTrue(any("withdrawn but deposited as an addendum" in x for x in r["evidence_for"]))
        self.assertIn("Not found in PubMed.", r["notes"])

    def test_cochrane_topic_review_is_not_retracted(self):
        # 0.1.0 said "retracted" because the review's own title starts "Withdrawal of"
        r = self.full(COCH)
        self.assertEqual(r["verdict"], "corrected")
        self.assertEqual(r["evidence_for"], [])

    def test_retraction_typed_correction(self):
        # Clin J Sport Med: notice titled "[RETRACTED]", deposited as a correction (audit 4b)
        r = self.full(SIS)
        self.assertEqual(r["verdict"], "possibly_withdrawn")
        self.assertTrue(any("typed 'correction'" in x for x in r["evidence_for"]))
        self.assertTrue(any("OpenAlex does not mark it retracted either" in n for n in r["notes"]))

    def test_self_loop(self):
        r = self.full(LOOP)
        self.assertEqual(r["verdict"], "self_loop_notice")
        self.assertTrue(any("lists itself" in n for n in r["notes"]))

    def test_confirmed_by_notice_title_only(self):
        w = {"title": ["A study of mice"],
             "updated-by": [{"DOI": "10.1/n", "type": "retraction", "source": "publisher"}]}
        r = rc.assess("10.1/p", w, {"10.1/n": "Retraction notice to: A study of mice"})
        self.assertEqual(r["verdict"], "retracted")

    def test_unconfirmed(self):
        w = {"title": ["A study of mice"],
             "updated-by": [{"DOI": "10.1/n", "type": "retraction", "source": "publisher"}]}
        r = rc.assess("10.1/p", w, {"10.1/n": "Statement"})
        self.assertEqual(r["verdict"], "retracted_unconfirmed")

    def test_pubmed_only_retraction(self):
        pm = pm_rec("5", ["Journal Article", "Retracted Publication"], [], "10.1/p")
        r = rc.assess("10.1/p", {"title": ["A study"]}, {}, pm)
        self.assertEqual(r["verdict"], "retracted")
        self.assertTrue(any("Crossref links no retraction notice" in n for n in r["notes"]))

    def test_corrected_and_no_notice(self):
        w = {"title": ["A study"], "updated-by": [{"DOI": "10.1/c", "type": "correction", "source": "publisher"}]}
        self.assertEqual(rc.assess("10.1/p", w, {"10.1/c": "Correction to: A study"})["verdict"], "corrected")
        r = rc.assess("10.1/q", {"title": ["Another"]}, oa=(True, 5))
        self.assertEqual(r["verdict"], "no_notice")
        self.assertTrue(any("no source checked here does" in n for n in r["notes"]))

    def test_concern(self):
        w = {"title": ["A study"],
             "updated-by": [{"DOI": "10.1/e", "type": "expression_of_concern", "source": "publisher"}]}
        self.assertEqual(rc.assess("10.1/p", w)["verdict"], "concern")

    def test_fixed_known_error(self):
        w = {"title": ["Protein arginine hypomethylation"],
             "updated-by": [{"DOI": "10.1096/fj.13-246579err", "type": "correction", "source": "publisher"}]}
        r = rc.assess("10.1096/fj.13-246579", w, {"10.1096/fj.13-246579err": "Errata"}, known=self.known)
        self.assertEqual(r["verdict"], "corrected")
        self.assertTrue(any("may have been fixed" in n for n in r["notes"]))

    def test_failures(self):
        self.assertEqual(rc.assess("10.1/x", None)["verdict"], "not_found")
        self.assertEqual(rc.check("10.9999/none", FakeNet(), {})["verdict"], "not_found")
        self.assertEqual(rc.check("hello", FakeNet(), {})["verdict"], "bad_doi")
        self.assertEqual(rc.check(FJ, FakeNet(fail=True), {})["verdict"], "lookup_failed")


class WithdrawnCorrection(unittest.TestCase):
    """0.2.0 (EVAL-2): a withdrawn correction does not confirm a retraction."""

    def setUp(self):
        self.known = rc.load_known()

    def test_jaad_pubmed_flag_from_withdrawn_correction_is_disputed(self):
        r = rc.check(JAAD, FakeNet(), self.known)
        self.assertEqual(r["verdict"], "disputed")
        self.assertEqual(r["evidence_for"], [])
        joined = " ".join(r["evidence_against"])
        self.assertIn("only because it links PMID 41621663", joined)
        self.assertIn("graded audit", joined)
        self.assertTrue(r["pubmed"]["retracted"])
        self.assertTrue(r["pubmed"]["flag_from_withdrawn_correction"])
        self.assertEqual(r["pubmed"]["retraction_notices"][0]["doi"], JAAD_N)
        self.assertTrue(any("although Crossref links no retraction notice" in n for n in r["notes"]))
        self.assertEqual(r["relations"][0]["title_class"], "withdrawn_correction")

    def test_jaad_without_known_table(self):
        r = rc.check(JAAD, FakeNet(), {})
        self.assertEqual(r["verdict"], "disputed")
        self.assertEqual(len(r["evidence_against"]), 1)

    def test_crossref_withdrawal_from_withdrawn_corrigendum(self):
        # Can J Cardiol pattern: Crossref withdrawal + PubMed retraction, both from one
        # "WITHDRAWN: Corrigendum to ..." notice
        w = {"title": ["A guideline"],
             "updated-by": [{"DOI": "10.1000/wc", "type": "withdrawal", "source": "publisher"},
                            {"DOI": "10.1000/wc", "type": "erratum", "source": "publisher"}]}
        pm = pm_rec("7", ["Journal Article", "Retracted Publication"],
                    [("Retraction in", "8", "Can J. 2026. doi: 10.1000/wc.")], "10.1000/p")
        r = rc.assess("10.1000/p", w, {"10.1000/wc": "WITHDRAWN: Corrigendum to A guideline"}, pm)
        self.assertEqual(r["verdict"], "disputed")
        self.assertEqual(r["evidence_for"], [])
        self.assertEqual(len(r["evidence_against"]), 2)
        self.assertTrue(any("withdraws or retracts a correction" in x for x in r["evidence_against"]))

    def test_crossref_only_withdrawn_corrigendum_without_pubmed(self):
        w = {"title": ["A guideline"],
             "updated-by": [{"DOI": "10.1/wc", "type": "retraction", "source": "publisher"}]}
        r = rc.assess("10.1/p", w, {"10.1/wc": "WITHDRAWN: Corrigendum to A guideline"}, oa=(True, 3))
        self.assertEqual(r["verdict"], "disputed")
        self.assertTrue(any("following the Crossref deposit" in n for n in r["notes"]))

    def test_erratum_titled_pubmed_notice_still_confirms(self):
        # audit 9: "Retraction: Erratum to ..." notices are real retractions (Res Dev Disabil 2011)
        pm = pm_rec("9", ["Journal Article", "Retracted Publication"],
                    [("Retraction in", "10", "Res Dev Disabil. 2012. doi: 10.1/rn.")], "10.1/q")
        pm["notice_titles"] = {"10": "Retraction: Erratum to \"The effectiveness of Korean number naming\""}
        r = rc.assess("10.1/q", {"title": ["The effectiveness of Korean number naming"]}, {}, pm)
        self.assertEqual(r["verdict"], "retracted")
        self.assertEqual(r["evidence_against"], [])
        self.assertFalse(r["pubmed"]["flag_from_withdrawn_correction"])

    def test_one_real_notice_is_enough(self):
        pm = pm_rec("11", ["Journal Article", "Retracted Publication"],
                    [("Retraction in", "12", "J. 2025."), ("Retraction in", "13", "J. 2026.")], "10.1/r")
        pm["notice_titles"] = {"12": "WITHDRAWN: Corrigendum to X", "13": "Retraction notice to: X"}
        r = rc.assess("10.1/r", {"title": ["X"]}, {}, pm)
        self.assertEqual(r["verdict"], "retracted")
        self.assertEqual(len(r["pubmed"]["retraction_notices"]), 2)

    def test_unknown_notice_title_still_confirms(self):
        pm = pm_rec("14", ["Journal Article", "Retracted Publication"],
                    [("Retraction in", "15", "J. 2025.")], "10.1/s")
        r = rc.assess("10.1/s", {"title": ["Y"]}, {}, pm)
        self.assertEqual(r["verdict"], "retracted")

    def test_marked_title_outweighs_withdrawn_correction(self):
        # Life Sci 2008 pattern: "RETRACTED:" title plus a withdrawn corrigendum
        pm = pm_rec("16", ["Journal Article", "Retracted Publication"],
                    [("Retraction in", "17", "J. 2025.")], "10.1/t")
        pm["notice_titles"] = {"17": "WITHDRAWN: Corrigendum to Z"}
        r = rc.assess("10.1/t", {"title": ["RETRACTED: Z"]}, {}, pm)
        self.assertEqual(r["verdict"], "retracted")
        self.assertTrue(any("Some records disagree" in n for n in r["notes"]))

    def test_known_row_but_now_really_retracted(self):
        pm = pm_rec("36572065", ["Journal Article", "Retracted Publication"],
                    [("Retraction in", "41621663", "J. doi: 10.1016/j.jaad.2026.01.065."),
                     ("Retraction in", "50000000", "J. 2027.")], JAAD)
        pm["notice_titles"] = {"41621663": JAAD_WC, "50000000": "Retraction notice to: Chronic GVHD"}
        r = rc.assess(JAAD, WORKS[JAAD], {JAAD_N: JAAD_WC}, pm, known=self.known)
        self.assertEqual(r["verdict"], "retracted")
        self.assertTrue(any("may since have been retracted" in n for n in r["notes"]))

    def test_net_reads_pubmed_notice_titles(self):
        # IJBM: the withdrawn duplicate corrigendum is not in Crossref's updated-by, so only
        # PubMed's own notice title can show where the flag comes from
        net = GetNet()
        r = rc.check(IJBM, net, rc.load_known())
        self.assertEqual(r["verdict"], "disputed")
        self.assertTrue(r["pubmed"]["flag_from_withdrawn_correction"])
        self.assertEqual(r["pubmed"]["retraction_notices"][0]["pmid"], "39731814")
        self.assertEqual(r["pubmed"]["retraction_notices"][0]["doi"], IJBM_W)
        self.assertTrue(any("id=39731814" in u for u in net.urls))
        self.assertEqual(r["openalex_is_retracted"], True)
        self.assertIn("RETRACTION IN PMID 39731814".lower(), rc.render(r).lower())


class Cli(unittest.TestCase):
    def test_text_and_exit_codes(self):
        code, out = run([FJ])
        self.assertEqual(code, 1)
        self.assertIn("DISPUTED", out)
        self.assertIn("against:", out)
        code, out = run(["10.9999/none"])
        self.assertEqual(code, 2)
        code, out = run([])
        self.assertEqual(code, 2)

    def test_clean_doi_exits_0(self):
        WORKS["10.1234/clean"] = {"title": ["Fine paper"]}
        try:
            code, out = run(["10.1234/clean", "--no-pubmed", "--no-openalex"])
        finally:
            del WORKS["10.1234/clean"]
        self.assertEqual(code, 0)
        self.assertIn("NO NOTICE", out)

    def test_topic_review_exits_0(self):
        code, out = run([COCH, "--no-pubmed"])
        self.assertEqual(code, 0)
        self.assertIn("CORRECTED", out)

    def test_json(self):
        code, out = run(["--json", "https://doi.org/" + BSR])
        self.assertEqual(code, 1)
        obj = json.loads(out)
        self.assertEqual(obj["version"], rc.VERSION)
        self.assertEqual(obj["version"], "0.2.1")
        self.assertEqual(obj["results"][0]["verdict"], "disputed")

    def test_offline_and_known(self):
        code, out = run(["--offline", "10.3341/kjo.2022.0089"])
        self.assertEqual(code, 1)
        self.assertIn("KNOWN ERROR", out)
        code, out = run(["--offline", JAAD])
        self.assertEqual(code, 1)
        self.assertIn("pubmed_flag_from_withdrawn_correction", out)
        code, out = run(["--offline", "10.1000/xyz"])
        self.assertEqual(code, 0)
        self.assertIn("NOT IN TABLE", out)
        code, out = run(["--known"])
        self.assertEqual(code, 0)
        self.assertIn("49 graded errors", out)

    def test_file_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "refs.bib")
            with open(p, "w", encoding="utf-8") as f:
                f.write("@article{x, doi={%s}}\n@article{y, doi={%s}}\n" % (LAN, IWA))
            code, out = run(["--file", p])
            self.assertEqual(code, 1)
            self.assertIn("checked 2:", out)
            self.assertIn("possibly_withdrawn 1", out)
            self.assertIn("retracted 1", out)
            code, out = run(["--file", os.path.join(d, "missing.bib")])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
