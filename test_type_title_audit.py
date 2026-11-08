# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Unit tests for type_title_audit.py (no network)."""
import unittest

import type_title_audit as t


def item(doi, title, updates, member="945", publisher="IWA Publishing", year=2022):
    return {"DOI": doi, "title": [title], "member": member, "publisher": publisher,
            "created": {"date-parts": [[year, 3, 10]]},
            "update-to": [{"DOI": d, "type": ty, "source": src} for d, ty, src in updates]}


class TestTitles(unittest.TestCase):
    def test_clean_title_dashes_and_html(self):
        self.assertEqual(t.clean_title("Treatment of Recurrent Concussion—RETRACTION"),
                         "treatment of recurrent concussion - retraction")
        self.assertEqual(t.clean_title("<i>SPQ</i> Retraction Statement"),
                         "spq retraction statement")

    def test_retraction_worded_true(self):
        for s in ["Withdrawn: Estimating the economic impact of large hydropower projects",
                  "Retraction Note: Produktionsausfallzeiten reduzieren",
                  "Retraction Notice",
                  "Retraction",
                  "Partial retraction notice",
                  "RETRACTED ARTICLE: Produktionsausfallzeiten reduzieren",
                  "Notice of Retraction\nA novel method",
                  "Feasibility and Outcomes of Tubular Decompression in Extreme Stenosis: Retraction",
                  "Feasibility and Outcomes of Tubular Decompression in Extreme Stenosis: [RETRACTED]",
                  "Treatment of Recurrent Concussion—RETRACTION",
                  "Aristotelian Feminism and Thumos: A Thomistic Proposal – Retraction",
                  "Retraction of <i>Medically Fit for Commercial Spaceflight</i>"]:
            self.assertTrue(t.retraction_worded(s), s)

    def test_retraction_worded_false(self):
        for s in ["Correction to: Brain retraction injury: systematic literature review",
                  "Correction: Retraction",
                  "Withdrawal syndrome in neonates",
                  "Withdrawal of expression of concern",
                  "Brain retraction",
                  "RETRACTION SHOCK PAPER",
                  "Retraction Controversy",
                  "Erratum",
                  ""]:
            self.assertFalse(t.retraction_worded(s), s)

    def test_correction_worded(self):
        self.assertTrue(t.correction_worded("Erratum"))
        self.assertTrue(t.correction_worded("Corrections"))
        self.assertTrue(t.correction_worded("Correction to: A study of things"))
        self.assertFalse(t.correction_worded("Correction to: Retraction note"))
        self.assertFalse(t.correction_worded("Retraction"))
        self.assertFalse(t.correction_worded("Correctional facilities and health"))

    def test_is_retractive(self):
        for ty in ["retraction", "partial_retraction", "Withdrawal", "retration", "removal",
                   "partial retraction"]:
            self.assertTrue(t.is_retractive(ty), ty)
        for ty in ["correction", "addendum", "expression_of_concern", "new_version", "erratum"]:
            self.assertFalse(t.is_retractive(ty), ty)


class TestRelations(unittest.TestCase):
    def test_relations_of_and_classify(self):
        it = item("10.2166/WP.2022.000", "Withdrawn: Estimating the economic impact",
                  [("10.2166/wp.2021.019", "addendum", "publisher")])
        it["update-to"].insert(0, "junk")
        rels = t.relations_of(it)
        self.assertEqual(len(rels), 1)
        r = rels[0]
        self.assertEqual(r["record"], "10.2166/wp.2022.000")
        self.assertEqual(r["target"], "10.2166/wp.2021.019")
        self.assertEqual(r["year"], 2022)
        self.assertEqual(t.classify(r), "mistyped")
        r2 = dict(r, source="retraction-watch")
        self.assertEqual(t.classify(r2), "")
        r3 = dict(r, title="Erratum", utype="retraction")
        self.assertEqual(t.classify(r3), "overflag")
        r4 = dict(r, title="Retraction", utype="retraction")
        self.assertEqual(t.classify(r4), "")

    def test_created_year_and_pair_key(self):
        self.assertEqual(t.created_year({"created": {"date-parts": [[2024, 5, 1]]}}), 2024)
        self.assertIsNone(t.created_year({}))
        self.assertEqual(t.pair_key({"record": "b", "target": "a"}), ("a", "b"))


class TestWalker(unittest.TestCase):
    def setUp(self):
        w = t.Walker()
        w.add(item("n1", "Withdrawn: Something", [("t1", "addendum", "publisher")], year=2022))
        w.add(item("n2", "Retraction notice", [("t2", "correction", "publisher"),
                                                ("t2", "retraction", "retraction-watch")],
                   member="297", publisher="Springer", year=2024))
        w.add(item("n3", "Erratum", [("t3", "retraction", "publisher")],
                   member="78", publisher="Elsevier", year=2010))
        self.w = w
        self.flagged = w.finish()

    def test_walker_sets(self):
        w = self.w
        self.assertEqual(w.n_records, 3)
        self.assertEqual(w.n_relations, 4)
        self.assertEqual(w.retr_any, {"t2", "t3"})
        self.assertEqual(w.retr_rw, {"t2"})
        self.assertEqual(w.retr_pub, {"t3"})
        self.assertEqual([r["class"] for r in self.flagged], ["mistyped", "mistyped", "overflag"])
        a, b, c = self.flagged
        self.assertFalse(a["visible"])
        self.assertTrue(b["visible"] and b["visible_rw"])
        self.assertTrue(c["visible"])
        self.assertFalse(c["visible_rw"])

    def test_tally_and_predictions(self):
        s = t.tally(self.flagged, self.w, True, 3)
        self.assertEqual(s["n_mistyped"], 2)
        self.assertEqual(s["n_mistyped_rw"], 1)
        self.assertEqual(s["n_hidden_pairs"], 1)
        self.assertEqual(s["hidden_members"], 1)
        self.assertEqual(s["iwa_withdrawn_addendum"], 1)
        self.assertEqual(s["iwa_withdrawn_pairs"], 1)
        self.assertEqual(s["iwa_withdrawn_hidden"], 1)
        self.assertEqual(s["iwa_withdrawal_typed"], 0)
        self.assertEqual((s["recent_n"], s["recent_hidden"], s["old_n"]), (1, 0, 0))
        self.assertEqual((s["n_overflag"], s["n_overflag_unsupported"]), (1, 1))
        p = t.compute_predictions(s)
        self.assertEqual(p["G"], False)
        self.assertEqual(p["P1"], False)
        self.assertIsNone(p["P3"])
        self.assertEqual(p["P4"], False)
        self.assertIsNone(p["P6"])
        self.assertEqual(p["P7"], False)

    def test_predictions_all_hold(self):
        s = {"complete": True, "n_records": 488000, "n_mistyped": 300, "n_mistyped_rw": 150,
             "n_hidden_pairs": 80, "iwa_withdrawn_addendum": 19, "iwa_withdrawal_typed": 0,
             "iwa_withdrawn_pairs": 16, "iwa_withdrawn_hidden": 16, "hidden_members": 15,
             "recent_n": 40, "recent_hidden": 20, "old_n": 100, "old_hidden": 10,
             "n_overflag": 40, "n_overflag_unsupported": 25}
        p = t.compute_predictions(s)
        for k in ["G", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
            self.assertTrue(p[k], k)
        s2 = dict(s, old_hidden=0)
        self.assertTrue(t.compute_predictions(s2)["P6"])
        s3 = dict(s, iwa_withdrawn_hidden=15)
        self.assertFalse(t.compute_predictions(s3)["P4"])


if __name__ == "__main__":
    unittest.main()
