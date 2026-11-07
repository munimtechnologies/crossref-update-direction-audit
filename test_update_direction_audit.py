# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Unit tests for update_direction_audit (no network)."""
import datetime
import unittest

import update_direction_audit as U

D = datetime.date

# Shapes copied from Crossref records read on 2026-11-07 (trimmed to the fields used).
FEHR = {"DOI": "10.1038/415137a", "title": ["Altruistic punishment in humans"],
        "issued": {"date-parts": [[2002, 1]]}, "member": "297",
        "publisher": "Springer Science and Business Media LLC", "is-referenced-by-count": 4013,
        "type": "journal-article", "container-title": ["Nature"],
        "update-to": [{"DOI": "10.1038/nature03256", "type": "erratum", "label": "Erratum",
                       "source": "publisher", "updated": {"date-parts": [[2002, 1, 10]]}}]}
COMMENT = {"DOI": "10.1038/nature03256", "title": ["Egalitarian motive and altruistic punishment"],
           "issued": {"date-parts": [[2005, 1, 5]]}, "member": "297", "type": "journal-article",
           "is-referenced-by-count": 79}
NRG_CORR = {"DOI": "10.1038/nrg1415",
            "title": ["Correction: MicroRNAs: small RNAs with a big role in gene regulation"],
            "issued": {"date-parts": [[2004, 8]]}, "member": "297",
            "update-to": [{"DOI": "10.1038/nrg1379", "type": "correction", "source": "publisher"}]}


class DateTests(unittest.TestCase):
    def test_year_only(self):
        self.assertEqual(U.date_range([2004]), (D(2004, 1, 1), D(2004, 12, 31)))

    def test_month(self):
        self.assertEqual(U.date_range([2004, 8]), (D(2004, 8, 1), D(2004, 8, 31)))
        self.assertEqual(U.date_range([2003, 12]), (D(2003, 12, 1), D(2003, 12, 31)))

    def test_day(self):
        self.assertEqual(U.date_range([2005, 1, 5]), (D(2005, 1, 5), D(2005, 1, 5)))

    def test_invalid_day_falls_back_to_month(self):
        self.assertEqual(U.date_range([2004, 2, 30]), (D(2004, 2, 1), D(2004, 2, 29)))

    def test_invalid_month_falls_back_to_year(self):
        self.assertEqual(U.date_range([2004, 13, 2]), (D(2004, 1, 1), D(2004, 12, 31)))

    def test_missing(self):
        self.assertIsNone(U.date_range([None]))
        self.assertIsNone(U.date_range([]))
        self.assertIsNone(U.date_range(None))
        self.assertIsNone(U.date_range("2004"))

    def test_issued_range(self):
        self.assertEqual(U.issued_range(FEHR), (D(2002, 1, 1), D(2002, 1, 31)))
        self.assertIsNone(U.issued_range({}))


class PredatesTests(unittest.TestCase):
    def test_clear_case(self):
        self.assertTrue(U.predates((D(2002, 1, 1), D(2002, 1, 31)), (D(2005, 1, 5), D(2005, 1, 5))))

    def test_within_slack(self):
        # year-only 2004 ends 2004-12-31; +31 days = 2005-01-31, not before 2005-01-05
        self.assertFalse(U.predates((D(2004, 1, 1), D(2004, 12, 31)), (D(2005, 1, 5), D(2005, 1, 5))))

    def test_normal_notice(self):
        self.assertFalse(U.predates((D(2004, 8, 1), D(2004, 8, 31)), (D(2004, 6, 1), D(2004, 6, 1))))

    def test_unknown(self):
        self.assertIsNone(U.predates(None, (D(2005, 1, 5), D(2005, 1, 5))))


class TextTests(unittest.TestCase):
    def test_notice_titles(self):
        self.assertTrue(U.notice_like_title(NRG_CORR["title"][0]))
        self.assertTrue(U.notice_like_title("Erratum: Hybrid functionals"))
        self.assertTrue(U.notice_like_title("RETRACTED ARTICLE: Amyloid"))
        self.assertTrue(U.notice_like_title("Corrigendum"))
        self.assertTrue(U.notice_like_title("Expression of Concern: X"))
        self.assertFalse(U.notice_like_title("Altruistic punishment in humans"))
        self.assertFalse(U.notice_like_title("Correctional facilities and health"))

    def test_norm_type(self):
        self.assertEqual(U.norm_type("Expression of Concern"), "expression_of_concern")
        self.assertEqual(U.norm_type("partial-retraction"), "partial_retraction")
        self.assertEqual(U.norm_type(None), "")

    def test_batchable_and_url(self):
        self.assertTrue(U.batchable("10.1038/nature02602"))
        self.assertFalse(U.batchable("10.1000/a,b"))
        self.assertFalse(U.batchable("10.1000/a b"))
        self.assertFalse(U.batchable(""))
        url = U.batch_url(["10.1038/nature02602", "10.1038/nrg1415"], "DOI,issued", 7)
        self.assertIn("filter=doi:10.1038/nature02602,doi:10.1038/nrg1415&rows=7", url)
        url2 = U.batch_url(["10.1175/1520-0485(1997)027<1849:aevpmf>2.0.co;2"], "DOI", 6)
        self.assertNotIn("<", url2)
        self.assertNotIn(";", url2)


class RelationTests(unittest.TestCase):
    def test_relations_of(self):
        rels = U.relations_of(FEHR)
        self.assertEqual(len(rels), 1)
        r = rels[0]
        self.assertEqual(r["notice"], "10.1038/415137a")
        self.assertEqual(r["target"], "10.1038/nature03256")
        self.assertEqual(r["utype"], "erratum")
        self.assertFalse(r["self"])
        self.assertFalse(r["r_notice_title"])
        self.assertEqual(r["r_cites"], 4013)
        self.assertEqual(r["member"], "297")

    def test_self_relation(self):
        it = {"DOI": "10.1371/Journal.pcbi.1005595", "update-to": [
            {"DOI": "10.1371/journal.pcbi.1005595", "type": "new_version"}]}
        r = U.relations_of(it)[0]
        self.assertTrue(r["self"])
        self.assertEqual(U.classify(r, None), "self")

    def test_no_update_to(self):
        self.assertEqual(U.relations_of(COMMENT), [])

    def test_classify(self):
        r = U.relations_of(FEHR)[0]
        self.assertEqual(U.classify(r, U.target_summary(COMMENT)), "predates")
        self.assertEqual(U.classify(r, None), "target_missing")
        self.assertEqual(U.classify(r, U.target_summary({"DOI": "x"})), "undated")
        n = U.relations_of(NRG_CORR)[0]
        orig = {"DOI": "10.1038/nrg1379", "issued": {"date-parts": [[2004, 6]]}}
        self.assertEqual(U.classify(n, U.target_summary(orig)), "ok")
        other = dict(r, utype="new_version")
        self.assertEqual(U.classify(other, U.target_summary(COMMENT)), "other_type")

    def test_target_summary_mutual(self):
        t = U.target_summary(NRG_CORR)
        self.assertEqual(t["upd"], ("10.1038/nrg1379",))
        self.assertEqual(t["min"], D(2004, 8, 1))


class PredictionTests(unittest.TestCase):
    BASE = {"complete": True, "n_records": 488000, "coverage": 0.95, "n_predates": 1000,
            "n_predates_297": 600, "rate_297": 0.03, "rate_other": 0.005, "n_pred_refs": 100,
            "n_pred_cites": 60, "share10_pred": 0.5, "share10_ok": 0.05, "n_1038": 100,
            "n_1038_pre2010": 90}

    def test_all_hold(self):
        p = U.compute_predictions(dict(self.BASE))
        for k in ("G", "P1", "P2", "P3", "P5", "P6", "P7"):
            self.assertIs(p[k], True, k)

    def test_failures_and_untestable(self):
        s = dict(self.BASE, coverage=0.5, n_predates=400, n_predates_297=100, rate_297=0.01,
                 n_pred_refs=10, share10_ok=0.2, n_1038=5)
        p = U.compute_predictions(s)
        self.assertIs(p["G"], False)
        self.assertIs(p["P1"], False)
        self.assertIs(p["P2"], False)
        self.assertIs(p["P3"], False)
        self.assertIsNone(p["P5"])
        self.assertIs(p["P6"], False)
        self.assertIsNone(p["P7"])

    def test_zero_baselines(self):
        s = dict(self.BASE, rate_other=0.0, share10_ok=0.0, n_predates=0, n_predates_297=0)
        p = U.compute_predictions(s)
        self.assertIs(p["P3"], True)
        self.assertIs(p["P6"], True)
        self.assertIsNone(p["P2"])

    def test_median(self):
        self.assertIsNone(U.median([]))
        self.assertEqual(U.median([3, 1, 2]), 2)
        self.assertEqual(U.median([1, 2, 3, 4]), 2.5)


if __name__ == "__main__":
    unittest.main()
