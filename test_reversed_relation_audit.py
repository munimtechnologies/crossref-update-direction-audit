# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Unit tests for reversed_relation_audit (no network)."""
import datetime
import unittest

import reversed_relation_audit as U

D = datetime.date

# Titles copied from Crossref records read on 2026-11-07/08.
FEHR = {"DOI": "10.1038/415137a", "title": ["Altruistic punishment in humans"],
        "issued": {"date-parts": [[2002, 1]]}, "member": "297",
        "publisher": "Springer Science and Business Media LLC", "is-referenced-by-count": 4013,
        "type": "journal-article", "container-title": ["Nature"],
        "update-to": [{"DOI": "10.1038/nature03256", "type": "erratum", "source": "publisher"}]}


class TitleTests(unittest.TestCase):
    def test_clean_title(self):
        self.assertEqual(
            U.clean_title("<i>Retracted</i>\n                    : Trinitarian Roots of Francis "
                          "Bacon’s Pragmatism"),
            "retracted : trinitarian roots of francis bacons pragmatism")
        self.assertEqual(U.clean_title("“Quoted” title"), "quoted title")
        self.assertEqual(U.clean_title(None), "")

    def test_dash_splits_words(self):
        self.assertTrue(U.clean_title("Retraction—Cardiac stem cells").startswith(
            "retraction cardiac"))

    def test_notice_titled(self):
        for t in ["Erratum: Regulation of endothelium-derived nitric oxide production by the "
                  "protein kinase Akt",
                  "Correction to: Analysis of food and fluid intake in elite ultra-endurance runners",
                  "Retraction:\n   <i>Water Supply (2023) 23 (7): 2907–2918</i>\n : Evaluation",
                  "Sample size estimation and power analysis for clinical research studies: Retraction",
                  "Corrections", "Retraction Notice", "Expression of concern: the SCIPIO trial",
                  "Publisher’s Note", "Additions and Corrections",
                  "Retraction—Cardiac stem cells in patients with ischaemic cardiomyopathy"]:
            self.assertTrue(U.notice_titled(t), t)
        for t in ["Altruistic punishment in humans",
                  "RETRACTED: 6-month consequences of COVID-19 in patients discharged from hospital",
                  "Dual role for the ADP/ATP translocator?",
                  "Atmospheric correction of satellite data", "Corrective surgery outcomes", ""]:
            self.assertFalse(U.notice_titled(t), t)

    def test_retracted_marked(self):
        self.assertTrue(U.retracted_marked("RETRACTED: 6-month consequences of COVID-19"))
        self.assertTrue(U.retracted_marked("WITHDRAWN: Audit committee member busyness"))
        self.assertTrue(U.retracted_marked("Some title (Retracted article)"))
        self.assertFalse(U.retracted_marked("Altruistic punishment in humans"))

    def test_plain_title(self):
        self.assertTrue(U.plain_title("Altruistic punishment in humans"))
        self.assertFalse(U.plain_title(""))
        self.assertFalse(U.plain_title("Atmospheric correction of satellite data"))
        self.assertFalse(U.plain_title("Corrections"))


class DirectionTests(unittest.TestCase):
    def test_neither(self):
        self.assertEqual(U.direction_class("Altruistic punishment in humans",
                                           "Egalitarian motive and altruistic punishment"),
                         "neither")

    def test_reversed_plain(self):
        self.assertEqual(U.direction_class(
            "Regulation of endothelium-derived nitric oxide production by the protein kinase Akt",
            "Erratum: Regulation of endothelium-derived nitric oxide production by the protein "
            "kinase Akt"), "reversed_plain")

    def test_reversed_marked(self):
        self.assertEqual(U.direction_class(
            "RETRACTED: Cardiac stem cells in patients with ischaemic cardiomyopathy (SCIPIO): "
            "initial results of a randomised phase 1 trial",
            "Retraction—Cardiac stem cells in patients with ischaemic cardiomyopathy (SCIPIO)"),
            "reversed_marked")

    def test_forward(self):
        self.assertEqual(U.direction_class(
            "Retraction notice to “Simultaneous removal of Cu2+ and Pb2+ ions”",
            "RETRACTED: Simultaneous removal of Cu2+ and Pb2+ ions by unmodified apple pomace"),
            "forward")

    def test_notice_to_notice(self):
        self.assertEqual(U.direction_class("Erratum", "Erratum: Something"), "notice_to_notice")

    def test_reversed_other(self):
        self.assertEqual(U.direction_class("Atmospheric correction of satellite data",
                                           "Correction: Atmospheric correction of satellite data"),
                         "reversed_other")


class RecordTests(unittest.TestCase):
    def test_relations_of(self):
        rels = U.relations_of(FEHR)
        self.assertEqual(len(rels), 1)
        r = rels[0]
        self.assertEqual((r["source"], r["target"], r["utype"]),
                         ("10.1038/415137a", "10.1038/nature03256", "erratum"))
        self.assertFalse(r["self"])
        self.assertEqual((r["r_min"], r["r_max"]), (D(2002, 1, 1), D(2002, 1, 31)))
        self.assertEqual(r["r_cites"], 4013)

    def test_self(self):
        item = {"DOI": "10.1/X", "update-to": [{"DOI": "10.1/x", "type": "Retraction"}]}
        r = U.relations_of(item)[0]
        self.assertTrue(r["self"])
        self.assertEqual(r["utype"], "retraction")

    def test_norm_doi(self):
        self.assertEqual(U.norm_doi("https://doi.org/10.1038/NATURE03256"), "10.1038/nature03256")
        self.assertEqual(U.norm_doi(None), "")

    def test_dates(self):
        self.assertEqual(U.date_range([2004]), (D(2004, 1, 1), D(2004, 12, 31)))
        self.assertEqual(U.date_range([2004, 2, 30]), (D(2004, 2, 1), D(2004, 2, 29)))
        self.assertIsNone(U.date_range([]))

    def test_predates(self):
        self.assertTrue(U.predates((D(2002, 1, 1), D(2002, 1, 31)), (D(2005, 1, 5), D(2005, 1, 5))))
        self.assertFalse(U.predates((D(2004, 8, 1), D(2004, 8, 31)),
                                    (D(2004, 9, 15), D(2004, 9, 15))))
        self.assertIsNone(U.predates(None, (D(2004, 9, 15), D(2004, 9, 15))))


class OpenAlexTests(unittest.TestCase):
    def test_parse(self):
        body = (b'{"results":[{"doi":"https://doi.org/10.1/A","is_retracted":true},'
                b'{"doi":"https://doi.org/10.1/a","is_retracted":false},'
                b'{"doi":null,"is_retracted":true}]}')
        self.assertEqual(U.parse_openalex(body), {"10.1/a": True})

    def test_url(self):
        u = U.openalex_url(["10.1/a", "10.2/b(1)"])
        self.assertIn("filter=doi:https://doi.org/10.1/a|https://doi.org/10.2/b%281%29", u)
        self.assertIn("select=doi,is_retracted", u)

    def test_batchable(self):
        self.assertTrue(U.batchable("10.1/a"))
        self.assertFalse(U.batchable("10.1/a|b"))
        self.assertFalse(U.batchable("10.1/a,b"))
        self.assertFalse(U.batchable(""))


class PredictionTests(unittest.TestCase):
    BASE = {"complete": True, "n_records": 488000, "coverage": 0.99, "n_reversed": 2000,
            "n_rev_dated": 1000, "n_rev_not_predating": 500, "n_rev_members": 30,
            "top_member_share": 0.3, "oa_n_source": 50, "oa_source_not_retracted": 10}

    def test_all_hold(self):
        p = U.compute_predictions(dict(self.BASE))
        for k in ("G", "R1", "R2", "R3", "R5"):
            self.assertIs(p[k], True, k)

    def test_untestable_and_failures(self):
        s = dict(self.BASE, n_rev_dated=5, oa_n_source=3, coverage=None)
        p = U.compute_predictions(s)
        self.assertIsNone(p["R2"])
        self.assertIsNone(p["R5"])
        self.assertIs(p["G"], False)
        s = dict(self.BASE, n_reversed=0, top_member_share=None)
        p = U.compute_predictions(s)
        self.assertIs(p["R1"], False)
        self.assertIsNone(p["R3"])

    def test_concentrated(self):
        p = U.compute_predictions(dict(self.BASE, top_member_share=0.6))
        self.assertIs(p["R3"], False)


if __name__ == "__main__":
    unittest.main()
