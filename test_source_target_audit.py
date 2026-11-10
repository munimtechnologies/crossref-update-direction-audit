# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Offline tests for source_target_audit.py (audit 11). No network."""
import collections
import unittest

import source_target_audit as m

# Titles of the control notice and its two targets, as read in live Crossref on 2026-11-10
# (the notice title is cut before its citation; the cut does not change the result).
CTL_NOTICE = ('Correction to: "Friedman AJ, Hornstein MD: Gonadotropin-releasing hormone agonist '
              'plus estrogen-progestin “add-back” therapy for endometriosis-related pelvic pain"')
CTL_RW = ("Gonadotropin-releasing hormone agonist plus estrogen-progestin “add-back” "
          "therapy for endometriosis-related pelvic pain")
CTL_PUB = ("Evaluation of the significance of the estradiol response during the clomiphene "
           "citrate challenge test")


class Words(unittest.TestCase):
    def test_boilerplate_digits_and_short_words_dropped(self):
        t = 'Retraction notice to “The effect of X-ray on Bone” [J Bone 12 (2019) 100–110]'
        self.assertEqual(m.words(t), {"effect", "ray", "bone"})

    def test_accents_folded_and_tags_removed(self):
        self.assertEqual(m.words("<i>Café</i> résumé data"), {"cafe", "resume", "data"})

    def test_containment_control(self):
        self.assertEqual(m.containment(CTL_RW, CTL_NOTICE), 1.0)
        self.assertEqual(m.containment(CTL_PUB, CTL_NOTICE), 0.0)

    def test_containment_too_short(self):
        self.assertIsNone(m.containment(CTL_RW, "Retraction notice"))
        self.assertIsNone(m.containment("Short title", CTL_NOTICE))


class Classes(unittest.TestCase):
    def test_sides(self):
        self.assertEqual(m.side_class(["a", "b"], ["b", "a"]), "agree")
        self.assertEqual(m.side_class(["a", "b"], ["a"]), "overlap")
        self.assertEqual(m.side_class(["a"], ["b"]), "disjoint")
        self.assertEqual(m.side_class(["a"], []), "publisher_only")
        self.assertEqual(m.side_class([], ["b"]), "rw_only")

    def test_verdict_control_is_rw_right(self):
        titles = {"p": CTL_PUB, "r": CTL_RW}
        self.assertEqual(m.verdict(CTL_NOTICE, ["p"], ["r"], titles), ("rw_right", 0.0, 1.0))

    def test_verdict_publisher_right_both_and_undetermined(self):
        titles = {"p": CTL_PUB, "r": CTL_RW}
        self.assertEqual(m.verdict(CTL_NOTICE, ["r"], ["p"], titles)[0], "publisher_right")
        self.assertEqual(m.verdict(CTL_NOTICE, ["r"], ["r2"], {"r": CTL_RW, "r2": CTL_RW})[0],
                         "both_match")
        self.assertEqual(m.verdict(CTL_NOTICE, ["p"], ["missing"], titles),
                         ("undetermined", 0.0, None))
        self.assertEqual(m.verdict("Retraction", ["p"], ["r"], titles)[0], "undetermined")

    def test_levenshtein(self):
        self.assertEqual(m.levenshtein("10.1016/s0015-0282(16)56090-7",
                                       "10.1016/s0015-0282(16)56091-9"), 2)
        self.assertEqual(m.levenshtein("abc", "abc"), 0)
        self.assertEqual(m.levenshtein("", "ab"), 2)
        self.assertEqual(m.min_distance(["abc", "xyz"], ["abd"]), 1)
        self.assertIsNone(m.min_distance([], ["abd"]))

    def test_t_marked(self):
        self.assertTrue(m.t_marked("RETRACTED: Something about cells"))
        self.assertTrue(m.t_marked("Something about cells (Retracted article)"))
        self.assertFalse(m.t_marked("Something about retracted cells"))


class WalkerTests(unittest.TestCase):
    ITEM = {"DOI": "10.1/N", "title": ["Retraction note"], "publisher": "Pub", "member": "1",
            "created": {"date-parts": [[2020, 1, 2]]},
            "update-to": [
                {"DOI": "10.1/N", "type": "retraction", "source": "retraction-watch"},
                {"DOI": "10.1/A", "type": "Retraction", "source": "publisher"},
                {"DOI": "10.1/B", "type": "retraction", "source": "retraction-watch"},
                {"DOI": "10.1/C", "type": "erratum", "source": "publisher"},
                "junk"]}

    def test_add(self):
        w = m.Walker()
        w.add(self.ITEM)
        w.add(self.ITEM)
        self.assertEqual(w.n_records, 1)
        n = w.notices["10.1/n"]
        self.assertEqual((n["P"], n["R"]), (["10.1/a"], ["10.1/b"]))
        self.assertTrue(n["rw_self"])
        self.assertEqual(n["year"], 2020)
        self.assertEqual(w.self_src["retraction-watch"], 1)
        self.assertIn("10.1/n", w.self_any)
        self.assertEqual((w.pub_count["10.1/a"], w.rw_count["10.1/b"]), (1, 1))

    def test_self_only_record_not_a_notice(self):
        w = m.Walker()
        w.add({"DOI": "10.1/S", "update-to": [{"DOI": "10.1/s", "type": "retraction",
                                               "source": "publisher"}]})
        self.assertEqual((w.n_records, len(w.notices)), (1, 0))
        self.assertFalse(w.notices.get("10.1/s"))

    def test_evidence(self):
        w = m.Walker()
        w.add(self.ITEM)
        self.assertEqual(m.evidence_p("10.1/a", w, {}), [])
        self.assertEqual(m.evidence_p("10.1/a", w, {"10.1/a": "RETRACTED: X"}), ["title"])
        self.assertEqual(m.evidence_r("10.1/b", w, {}), [])
        w.add({"DOI": "10.1/M", "update-to": [{"DOI": "10.1/b", "type": "retraction",
                                               "source": "publisher"}]})
        self.assertEqual(m.evidence_r("10.1/b", w, {}), ["publisher"])
        self.assertEqual(m.evidence_p("10.1/b", w, {}), ["rw"])


class Grade(unittest.TestCase):
    def test_grade(self):
        c = collections.Counter(agree=9000, overlap=500, disjoint=500)
        v = collections.Counter(rw_right=6, publisher_right=2)
        g = {"G1": {"ok": True}}
        r = m.grade(c, v, 3, (200, 190, 4), (100, 3), (4, 4), g)
        self.assertEqual(r["P1"]["value"], 10000)
        self.assertTrue(r["P1"]["held"])
        self.assertEqual(r["P2"]["value"], 0.05)
        self.assertFalse(r["P2"]["held"])
        self.assertEqual(r["P3"]["value"], 0.75)
        self.assertTrue(r["P3"]["held"])
        self.assertEqual(r["P4"]["value"], 0.5)
        self.assertTrue(r["P4"]["held"])
        self.assertEqual(r["P5"]["value"], [0.95, 0.02])
        self.assertTrue(r["P5"]["held"])
        self.assertEqual(r["P6"]["value"], 0.03)
        self.assertFalse(r["P6"]["held"])
        self.assertIsNone(r["P7"]["held"])

    def test_gate_failure_noted(self):
        c = collections.Counter(agree=10)
        r = m.grade(c, collections.Counter(), 0, (0, 0, 0), (0, 0), (0, 0), {"G1": {"ok": False}})
        self.assertFalse(r["P1"]["held"])
        self.assertIsNone(r["P3"]["held"])
        self.assertIn("a gate failed", r["P1"]["note"])


if __name__ == "__main__":
    unittest.main()
