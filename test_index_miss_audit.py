# Copyright 2026 Munim, Inc. Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Offline tests for index_miss_audit.py (audit 6). Made with AI agents working in MV2's name.
import io
import unittest

import index_miss_audit as m


class Helpers(unittest.TestCase):
    def test_title_marked(self):
        self.assertTrue(m.title_marked("RETRACTED: Perspectives and Commentary"))
        self.assertTrue(m.title_marked("5 Abstract withdrawn"))
        self.assertTrue(m.title_marked("Retraction note to: X"))
        self.assertFalse(m.title_marked("Does Second Impact Syndrome Exist?"))
        self.assertFalse(m.title_marked("Withdrawal of antihypertensive drugs in older people"))
        self.assertFalse(m.title_marked("Retractable roof design"))
        self.assertFalse(m.title_marked(None))

    def test_norm_doi_and_types(self):
        self.assertEqual(m.norm_doi("https://doi.org/10.1097/ABC"), "10.1097/abc")
        self.assertEqual(m.norm_doi(" DOI:10.1/X "), "10.1/x")
        for t in ("retraction", "partial_retraction", "Withdrawal", "removal"):
            self.assertTrue(m.is_retractive(t), t)
        for t in ("correction", "erratum", "expression_of_concern", "addendum"):
            self.assertFalse(m.is_retractive(t), t)

    def test_openalex_url_keeps_parentheses(self):
        u = m.openalex_url(["10.1061/(asce)mt.1943-5533.0004415", "10.1/a"])
        self.assertIn("filter=doi:10.1061/(asce)mt.1943-5533.0004415|10.1/a", u)


class Papers(unittest.TestCase):
    def test_papers_from_notices(self):
        rows = [
            {"record": "10.1/N1", "targets": "10.1/P1", "publisher": "Pub A", "year": "2020"},
            {"record": "10.1/N2", "targets": "10.1/N2", "publisher": "Pub B", "year": "2021"},
            {"record": "10.1/N3", "targets": "10.1/N3;10.1/P1;10.1/P3", "publisher": "Pub A",
             "year": "2022"},
            {"record": "10.1002/14651858.CD012572.pub2",
             "targets": "10.1002/14651858.cd012572.pub1", "publisher": "Wiley", "year": "2020"},
            {"record": "", "targets": "10.1/x"},
        ]
        papers, excluded = m.papers_from_notices(rows)
        self.assertEqual(sorted(papers), ["10.1/n2", "10.1/p1", "10.1/p3"])
        self.assertEqual(papers["10.1/p1"]["notices"], ["10.1/n1", "10.1/n3"])
        self.assertTrue(papers["10.1/n2"]["self_paper"])
        self.assertFalse(papers["10.1/p1"]["self_paper"])
        self.assertEqual(papers["10.1/p1"]["publisher"], "Pub A")
        self.assertEqual(excluded, ["10.1002/14651858.cd012572.pub2"])


class Sources(unittest.TestCase):
    def test_crossref_status(self):
        msg = {"title": ["Does X?"], "type": "journal-article",
               "updated-by": [{"DOI": "10.1/n", "type": "correction", "source": "publisher"}]}
        s = m.crossref_status(msg)
        self.assertFalse(s["cr_flagged"])
        self.assertTrue(s["cr_has_updated_by"])
        self.assertEqual(s["cr_update_types"], "correction")
        self.assertEqual(s["cr_flag_sources"], "")
        msg["updated-by"].append({"DOI": "10.1/r", "type": "retraction",
                                  "source": "retraction-watch"})
        s = m.crossref_status(msg)
        self.assertTrue(s["cr_flagged"])
        self.assertEqual(s["cr_flag_sources"], "retraction-watch")
        self.assertEqual(s["cr_update_types"], "correction;retraction")
        s = m.crossref_status({})
        self.assertFalse(s["cr_has_updated_by"])
        self.assertFalse(s["cr_flagged"])
        self.assertEqual(s["cr_title"], "")

    def test_retraction_watch(self):
        text = ("Record ID,Title,RetractionDOI,OriginalPaperDOI,RetractionNature\n"
                "1,A,10.1/N1,10.1/P1,Retraction\n"
                "2,B,unavailable,10.1/P2,Correction\n"
                "3,C,10.1/N9,10.1/P2,Expression of concern\n")
        orig, notice, n = m.rw_index(io.StringIO(text))
        self.assertEqual(n, 3)
        s = m.rw_status({"doi": "10.1/p1", "notices": ["10.1/n1"]}, orig, notice)
        self.assertEqual(s, {"rw_natures": "Retraction", "rw_flagged": True,
                             "rw_notice_known": True})
        s = m.rw_status({"doi": "10.1/p2", "notices": ["10.1/n2"]}, orig, notice)
        self.assertEqual(s["rw_natures"], "Correction;Expression of concern")
        self.assertFalse(s["rw_flagged"])
        self.assertFalse(s["rw_notice_known"])
        s = m.rw_status({"doi": "10.1/p3", "notices": []}, orig, notice)
        self.assertEqual(s, {"rw_natures": "", "rw_flagged": False, "rw_notice_known": False})

    def test_openalex_parse(self):
        got = m.openalex_parse({"results": [
            {"doi": "https://doi.org/10.1097/ABC", "is_retracted": True, "cited_by_count": 5},
            {"doi": None, "is_retracted": False}]})
        self.assertEqual(got, {"10.1097/abc": {"oa_found": True, "oa_retracted": True,
                                               "oa_cites": 5}})
        self.assertEqual(m.openalex_parse(None), {})

    def test_pubmed(self):
        rec = {"uid": "11495318", "pubtype": ["Journal Article", "Review"], "references": [],
               "articleids": [{"idtype": "pubmed", "value": "11495318"},
                              {"idtype": "doi", "value": "10.1097/00042752-200107000-00004"}]}
        self.assertEqual(m.pubmed_doi(rec), "10.1097/00042752-200107000-00004")
        s = m.pubmed_flag(rec)
        self.assertFalse(s["pm_flagged"])
        self.assertTrue(s["pm_found"])
        self.assertEqual(s["pm_pmid"], "11495318")
        rec2 = {"uid": "1", "pubtype": ["Journal Article", "Retracted Publication"],
                "references": [{"reftype": "Retraction in", "pmid": "2"}]}
        s = m.pubmed_flag(rec2)
        self.assertTrue(s["pm_retracted_type"])
        self.assertTrue(s["pm_retraction_in"])
        self.assertEqual(m.pubmed_doi(rec2), "")
        rec3 = {"uid": "3", "pubtype": ["Journal Article"],
                "references": [{"reftype": "Erratum in"}, {"reftype": "Partial retraction in"}]}
        s = m.pubmed_flag(rec3)
        self.assertFalse(s["pm_retracted_type"])
        self.assertTrue(s["pm_flagged"])
        self.assertEqual(s["pm_reftypes"], "Erratum in;Partial retraction in")


def make(i, marked, oa_ret, pm=False, cites=0):
    return m.judge({"doi": "10.1/%d" % i, "cr_found": True, "cr_flagged": False,
                    "title_marked": marked, "rw_flagged": False, "oa_found": True,
                    "oa_retracted": oa_ret, "pm_found": pm,
                    "pm_flagged": False if pm else None, "oa_cites": cites})


class Judgement(unittest.TestCase):
    def test_judge(self):
        p = m.judge({"cr_found": True, "cr_flagged": False, "rw_flagged": False,
                     "oa_found": True, "oa_retracted": False, "pm_found": False})
        self.assertEqual(p["n_flags"], 0)
        self.assertTrue(p["missed_by_all"])
        self.assertTrue(p["missed_by_all_held"])
        p = m.judge({"cr_found": True, "cr_flagged": False, "rw_flagged": False,
                     "oa_found": True, "oa_retracted": True})
        self.assertEqual(p["n_flags"], 1)
        self.assertFalse(p["missed_by_all"])
        self.assertFalse(p["missed_by_all_held"])
        p = m.judge({"cr_found": True, "cr_flagged": False})
        self.assertTrue(p["missed_by_all"])
        self.assertFalse(p["missed_by_all_held"])

    def test_grade(self):
        papers = [make(i, True, i < 12, pm=i < 5) for i in range(15)]
        papers += [make(i, False, False, pm=i < 20, cites=25) for i in range(15, 30)]
        papers += [m.judge({"doi": "10.1/f%d" % i, "cr_found": True, "cr_flagged": True})
                   for i in range(2)]
        r = m.grade(papers, {"G1": {"ok": True}})
        self.assertAlmostEqual(r["P1"]["value"], 30 / 32)
        self.assertTrue(r["P1"]["held"])
        self.assertEqual(r["P2"]["value"], 0)
        self.assertTrue(r["P2"]["held"])
        self.assertAlmostEqual(r["P3"]["value"], 0.6)
        self.assertTrue(r["P3"]["held"])
        self.assertAlmostEqual(r["P4"]["value"], 0.8)
        self.assertTrue(r["P4"]["held"])
        self.assertAlmostEqual(r["P5"]["value"], 10 / 30)
        self.assertTrue(r["P5"]["held"])
        self.assertAlmostEqual(r["P6"]["value"], 1.0)
        self.assertTrue(r["P6"]["held"])
        self.assertEqual(r["P7"]["value"], 18)
        self.assertFalse(r["P7"]["held"])
        self.assertEqual(r["P8"]["value"], 15)
        self.assertTrue(r["P8"]["held"])
        self.assertNotIn("gate failed", r["P1"]["note"])
        r = m.grade(papers, {"G1": {"ok": False}})
        self.assertTrue(r["P1"]["note"].endswith("(a gate failed: the audit is inconclusive)"))

    def test_grade_small_groups_inconclusive(self):
        papers = [make(i, True, True) for i in range(5)] + [make(9, False, False)]
        r = m.grade(papers, {})
        self.assertIsNone(r["P4"]["held"])
        self.assertIsNone(r["P6"]["held"])


if __name__ == "__main__":
    unittest.main()
