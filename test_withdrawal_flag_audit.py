# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Offline tests for withdrawal_flag_audit.py (no network)."""
import unittest

import withdrawal_flag_audit as m


def item(doi, links, title="T", publisher="Pub"):
    return {"DOI": doi, "title": [title], "publisher": publisher,
            "update-to": [{"DOI": d, "type": t, "source": s} for d, t, s in links]}


class Helpers(unittest.TestCase):
    def test_norm_doi(self):
        self.assertEqual(m.norm_doi("https://doi.org/10.1/AB"), "10.1/ab")
        self.assertEqual(m.norm_doi(" doi:10.1/x "), "10.1/x")
        self.assertEqual(m.norm_doi(None), "")

    def test_norm_type(self):
        self.assertEqual(m.norm_type("Partial Retraction"), "partial_retraction")
        self.assertEqual(m.norm_type("withdrawal"), "withdrawal")

    def test_t_marked(self):
        self.assertTrue(m.t_marked("WITHDRAWN: Janus Kinase Inhibitors"))
        self.assertTrue(m.t_marked("Some title (Retracted)"))
        self.assertFalse(m.t_marked("Withdrawal of life support in the ICU"))
        self.assertFalse(m.t_marked(""))

    def test_askable(self):
        self.assertTrue(m.askable("10.1016/j.cgh.2026.10.001"))
        self.assertTrue(m.askable("10.1016/s2213-8587(21)00263-1"))
        self.assertFalse(m.askable("10.1080/09645292.2010.545518#.us5z4lssxk0"))
        self.assertFalse(m.askable("10.1002/(sici)1097-0134(19970201)27:2<1::aid>3.0.co;2-x"))
        self.assertFalse(m.askable("10.1/a|b"))
        self.assertFalse(m.askable("11.1/a"))

    def test_share(self):
        self.assertEqual(m.share(1, 3), 0.3333)
        self.assertIsNone(m.share(1, 0))


class Classify(unittest.TestCase):
    def test_groups(self):
        self.assertEqual(m.classify({("withdrawal", "publisher")}, False), "w_only")
        self.assertEqual(m.classify({("retraction", "publisher")}, False), "r_only")
        self.assertEqual(m.classify({("withdrawal", "publisher")}, True), "w_rw")
        self.assertEqual(m.classify({("retraction", "publisher")}, True), "other")
        self.assertEqual(m.classify({("withdrawal", "publisher"), ("retraction", "publisher")}, False),
                         "other")
        self.assertEqual(m.classify({("removal", "publisher")}, False), "other")
        self.assertEqual(m.classify({("withdrawal", "")}, False), "other")


class Walk(unittest.TestCase):
    def test_targets(self):
        tg = m.Targets()
        # withdrawn in place
        tg.add(item("10.1/self", [("10.1/self", "withdrawal", "publisher")], "WITHDRAWN: X"))
        # duplicate record is ignored
        tg.add(item("10.1/self", [("10.1/other", "retraction", "publisher")]))
        # notice retracting a paper, with an RW link too
        tg.add(item("10.1/n1", [("10.1/p1", "retraction", "publisher"),
                                ("10.1/p1", "retraction", "retraction-watch")]))
        # publisher withdrawal plus an RW expression of concern on the same target
        tg.add(item("10.1/n2", [("10.1/p2", "withdrawal", "publisher"),
                                ("10.1/p2", "expression_of_concern", "retraction-watch")]))
        # publisher retraction only; a non-retractive publisher link is ignored
        tg.add(item("10.1/n3", [("10.1/p3", "retraction", "publisher"),
                                ("10.1/p4", "correction", "publisher")]))
        self.assertEqual(tg.n_records, 4)
        self.assertEqual(tg.self_w, {"10.1/self"})
        self.assertEqual(tg.rw_any, {"10.1/p1", "10.1/p2"})
        g = tg.groups()
        self.assertEqual(g, {"10.1/self": "w_only", "10.1/p1": "other", "10.1/p2": "w_rw",
                             "10.1/p3": "r_only"})
        self.assertNotIn("10.1/other", g)
        self.assertNotIn("10.1/p4", g)
        r = m.row("10.1/self", "w_only", tg, {"10.1/self": (False, "X")})
        self.assertTrue(r["self_w"])
        self.assertTrue(r["title_marked"])
        self.assertTrue(r["oa_found"])
        self.assertIs(r["is_retracted"], False)
        self.assertEqual(r["links"], "withdrawal/publisher")
        r = m.row("10.1/p3", "r_only", tg, {})
        self.assertFalse(r["oa_found"])
        self.assertEqual(r["is_retracted"], "")
        self.assertEqual(r["title_marked"], "")


class Grade(unittest.TestCase):
    OK = {"g": {"ok": True}}

    def test_rate(self):
        self.assertEqual(m.rate([(True, True), (True, False), (False, None), (True, None)]), (3, 1))

    def test_all_held(self):
        r = m.grade(1000, 950, 50, 400, 20, 2900, 2800, 500, 450, self.OK)
        self.assertTrue(r["P1"]["held"])
        self.assertTrue(r["P2"]["held"])          # 0.95
        self.assertTrue(r["P3"]["held"])          # 0.05
        self.assertTrue(r["P4"]["held"])          # 0.9655
        self.assertTrue(r["P5"]["held"])          # 0.9655 - 0.0526 = 0.9129
        self.assertEqual(r["P5"]["value"], 0.9129)
        self.assertTrue(r["P6"]["held"])          # 0.9

    def test_failures_and_bounds(self):
        r = m.grade(150, 120, 100, 100, 30, 2000, 1500, 100, 50, self.OK)
        self.assertFalse(r["P1"]["held"])         # 150 < 200
        self.assertFalse(r["P2"]["held"])         # 0.8
        self.assertFalse(r["P3"]["held"])         # 0.3
        self.assertFalse(r["P4"]["held"])         # 0.75
        self.assertFalse(r["P5"]["held"])         # 0.75 - 0.8333 < 0.5
        self.assertFalse(r["P6"]["held"])         # 0.5
        r = m.grade(4000, 3600, 0, 30, 6, 100, 90, 30, 24, self.OK)
        self.assertTrue(r["P1"]["held"])          # upper bound inclusive
        self.assertTrue(r["P2"]["held"])          # exactly 0.9
        self.assertTrue(r["P3"]["held"])          # exactly 0.2
        self.assertTrue(r["P4"]["held"])          # exactly 0.9
        self.assertTrue(r["P6"]["held"])          # exactly 0.8

    def test_inconclusive(self):
        r = m.grade(0, 0, 0, 29, 0, 99, 99, 29, 29, self.OK)
        self.assertIsNone(r["P3"]["held"])
        self.assertIsNone(r["P4"]["held"])
        self.assertIsNone(r["P5"]["held"])
        self.assertIsNone(r["P6"]["held"])
        self.assertIsNone(r["P2"]["value"])
        self.assertFalse(r["P2"]["held"])

    def test_gate_note(self):
        r = m.grade(1000, 950, 50, 400, 20, 2900, 2800, 500, 450, {"g": {"ok": False}})
        self.assertIn("a gate failed", r["P1"]["note"])


if __name__ == "__main__":
    unittest.main()
