# Copyright 2026 MV2, Munim, Inc. (mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Offline tests for eval_skill_pubmed_b.py (EVAL-2B)."""
import json
import unittest

import eval_skill_pubmed_b as e


def rows(verdicts, wc=None):
    return {d: {"verdict": v, "wc": (wc or {}).get(d)} for d, v in verdicts.items()}


class Sets(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(len(e.M), 9)
        self.assertEqual(len(e.R_RNC), 13)
        self.assertEqual(len(e.R_C), 17)
        self.assertEqual(len(e.R), 30)
        self.assertEqual(len(set(e.M + e.R + e.U)), 40)
        for d in e.M + e.R + e.U:
            self.assertEqual(d, e.norm(d))


class Parse(unittest.TestCase):
    def test_index_rows(self):
        js = json.dumps({"version": "0.2.0", "results": [
            {"doi": "10.1016/J.JAAD.2022.12.023", "verdict": "disputed",
             "pubmed": {"pmid": "36572064", "flag_from_withdrawn_correction": True}},
            {"doi": "10.1/x", "verdict": "retracted", "pubmed": None},
            {"input": "10.1/y", "status": "no_notice", "pubmed": {"pmid": "1"}}, "junk"]})
        self.assertEqual(e.index_rows(js), {
            "10.1016/j.jaad.2022.12.023": {"verdict": "disputed", "wc": True},
            "10.1/x": {"verdict": "retracted", "wc": None},
            "10.1/y": {"verdict": "no_notice", "wc": None}})

    def test_bad(self):
        self.assertIsNone(e.index_rows("not json"))
        self.assertIsNone(e.index_rows('{"results": 3}'))


class Grade(unittest.TestCase):
    def test_fix_works(self):
        v = {d: "disputed" for d in e.M}
        v.update({d: "retracted" for d in e.R})
        wc = {d: True for d in e.M}
        g = e.grade(rows(v, wc), "0.2.0", 0)
        self.assertTrue(g["G1_assessed"] and g["G2_version_and_tests"])
        self.assertEqual((g["M_disputed"], g["R_retracted"], g["R_disputed"]), (9, 30, 0))
        self.assertEqual((g["M_flag_from_wc"], g["R_flag_from_wc"]), (9, 0))
        self.assertEqual([g[k] for k in ("F1", "F2", "F3", "F4", "F5")], [True] * 5)

    def test_old_version_fails_gate_and_f1(self):
        v = {d: "retracted" for d in e.M + e.R}
        g = e.grade(rows(v), "0.1.1", 0)
        self.assertTrue(g["G1_assessed"])
        self.assertFalse(g["G2_version_and_tests"])
        self.assertEqual(g["M_retracted"], 9)
        self.assertFalse(g["F1"])
        self.assertFalse(g["F4"])
        self.assertTrue(g["F5"])

    def test_failed_tests_fail_gate(self):
        self.assertFalse(e.grade({}, "0.2.0", 1)["G2_version_and_tests"])
        self.assertFalse(e.grade({}, "0.2.0", None)["G2_version_and_tests"])

    def test_overreach_on_r(self):
        v = {d: "disputed" for d in e.M}
        v.update({d: "disputed" for d in e.R[:2]})
        v.update({d: "retracted" for d in e.R[2:]})
        wc = {e.R[0]: True, e.R[1]: True}
        g = e.grade(rows(v, wc), "0.2.0", 0)
        self.assertEqual((g["R_retracted"], g["R_disputed"], g["R_flag_from_wc"]), (28, 2, 2))
        self.assertTrue(g["F2"])
        self.assertFalse(g["F3"])
        self.assertFalse(g["F5"])

    def test_unassessed_not_counted(self):
        v = {d: "lookup_failed" for d in e.M[:2]}
        v.update({d: "disputed" for d in e.M[2:]})
        v.update({d: "retracted" for d in e.R})
        g = e.grade(rows(v), "0.2.0", 0)
        self.assertEqual(g["n_M_assessed"], 7)
        self.assertFalse(g["G1_assessed"])
        self.assertEqual(g["M_disputed"], 7)
        self.assertFalse(g["F1"])


if __name__ == "__main__":
    unittest.main()
