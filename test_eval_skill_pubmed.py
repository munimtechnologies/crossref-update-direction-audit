# Copyright 2026 MV2, Munim, Inc. (mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Offline tests for eval_skill_pubmed.py (EVAL-2)."""
import json
import unittest

import eval_skill_pubmed as e


class Sets(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(len(e.M), 9)
        self.assertEqual(len(e.R_RNC), 13)
        self.assertEqual(len(e.R_C), 17)
        self.assertEqual(len(e.R), 30)
        self.assertEqual(len(set(e.M + e.R + e.U)), 40)

    def test_lower_case(self):
        for d in e.M + e.R + e.U:
            self.assertEqual(d, e.norm(d))


class Parse(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(e.norm(" https://doi.org/10.1016/J.CJCA.2025.07.027 "),
                         "10.1016/j.cjca.2025.07.027")
        self.assertEqual(e.norm("doi:10.1/X"), "10.1/x")

    def test_index_dict(self):
        js = json.dumps({"version": "0.1.1", "results": [
            {"doi": "10.1016/J.JAAD.2022.12.023", "verdict": "retracted"},
            {"input": "10.1/x", "status": "no_notice"}, "junk"]})
        self.assertEqual(e.index_results(js),
                         {"10.1016/j.jaad.2022.12.023": "retracted", "10.1/x": "no_notice"})

    def test_index_list_and_bad(self):
        self.assertEqual(e.index_results('[{"doi": "10.1/a", "verdict": "disputed"}]'),
                         {"10.1/a": "disputed"})
        self.assertIsNone(e.index_results("not json"))
        self.assertIsNone(e.index_results('{"results": 3}'))


class Grade(unittest.TestCase):
    def test_flaw_present(self):
        v = {d: "retracted" for d in e.M + e.R}
        v[e.R[0]] = "disputed"
        g = e.grade(v)
        self.assertTrue(g["G1_assessed"])
        self.assertEqual((g["M_retracted"], g["R_retracted"], g["R_disputed"]), (9, 29, 1))
        self.assertEqual((g["E1"], g["E2"], g["E3"]), (True, True, True))

    def test_flaw_absent_and_gate(self):
        v = {d: "disputed" for d in e.M}
        v.update({d: "retracted" for d in e.R[:27]})
        v[e.M[0]] = "lookup_failed"
        g = e.grade(v)
        self.assertEqual((g["n_M_assessed"], g["n_R_assessed"]), (8, 27))
        self.assertFalse(g["G1_assessed"])
        self.assertEqual((g["E1"], g["E2"], g["E3"]), (False, True, True))

    def test_unassessed_not_counted(self):
        g = e.grade({})
        self.assertEqual((g["n_M_assessed"], g["n_R_assessed"]), (0, 0))
        self.assertFalse(g["E1"])
        self.assertTrue(g["E3"])
        self.assertEqual(g["U_verdicts"], {e.U[0]: ""})


if __name__ == "__main__":
    unittest.main()
