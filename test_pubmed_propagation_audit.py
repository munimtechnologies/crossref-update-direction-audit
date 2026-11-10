# Copyright 2026 MV2, Munim, Inc. Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Offline tests for pubmed_propagation_audit.py (no network).
import json
import unittest

import pubmed_propagation_audit as m

CSV = ('notice,target,utype,nclass,t_title\n'
       '10.1016/J.A.2,10.1016/j.a.1,retraction,rc,"Title with\nnewline, comma"\n'
       '10.1016/j.b.2,https://doi.org/10.1016/j.b.1,withdrawal,rc,x\n'
       '10.1016/j.b.3,10.1016/j.b.1,retraction,rc,y\n'
       '10.1016/j.c.2,10.1016/j.c.1,withdrawal,rc,z\n')


def esum(docs):
    res = {"uids": [d["uid"] for d in docs]}
    for d in docs:
        res[d["uid"]] = d
    return json.dumps({"result": res})


class Parse(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(m.norm(" https://doi.org/10.1/AbC "), "10.1/abc")
        self.assertEqual(m.norm("doi:10.1/x"), "10.1/x")
        self.assertEqual(m.norm(None), "")

    def test_load_targets(self):
        t = m.load_targets(CSV)
        self.assertEqual(sorted(t), ["10.1016/j.a.1", "10.1016/j.b.1", "10.1016/j.c.1"])
        self.assertEqual(t["10.1016/j.a.1"]["notices"], {"10.1016/j.a.2"})
        self.assertEqual(t["10.1016/j.b.1"]["notices"], {"10.1016/j.b.2", "10.1016/j.b.3"})
        self.assertEqual(m.group(t["10.1016/j.b.1"]["utypes"]), "retraction")
        self.assertEqual(m.group(t["10.1016/j.c.1"]["utypes"]), "other")

    def test_esearch(self):
        self.assertEqual(m.esearch_ids('{"esearchresult": {"idlist": ["1", "2"]}}'), ["1", "2"])
        self.assertIsNone(m.esearch_ids("not json"))

    def test_esummary(self):
        js = esum([{"uid": "11", "articleids": [{"idtype": "pubmed", "value": "11"},
                                                {"idtype": "doi", "value": "10.1016/J.A.1"}],
                    "pubtype": ["Journal Article", "Retracted Publication"],
                    "references": [{"reftype": "Retraction in", "pmid": 22, "note": ""}]}])
        d = m.esummary_docs(js)["11"]
        self.assertEqual(d["doi"], "10.1016/j.a.1")
        self.assertEqual(d["refs"], [("Retraction in", "22")])
        self.assertIsNone(m.esummary_docs("{}"))


class Classify(unittest.TestCase):
    def setUp(self):
        self.t = m.load_targets(CSV)
        self.linked = {"22": {"doi": "10.1016/j.a.2"}, "33": {"doi": "10.1016/j.b.9"},
                       "44": {"doi": "10.1016/j.b.3"}}

    def test_flagged_via_rc(self):
        doc = {"uid": "11", "doi": "10.1016/j.a.1", "pubtype": ["Retracted Publication"],
               "refs": [("Retraction in", "22")]}
        r = m.classify(self.t["10.1016/j.a.1"], doc, self.linked)
        self.assertTrue(r["flagged"] and r["rin_is_rc"])
        self.assertFalse(r["rin_other"])

    def test_other_notice_and_erratum(self):
        doc = {"uid": "12", "doi": "10.1016/j.b.1", "pubtype": ["Journal Article"],
               "refs": [("Retraction in", "33"), ("Erratum in", "44")]}
        r = m.classify(self.t["10.1016/j.b.1"], doc, self.linked)
        self.assertTrue(r["flagged"])
        self.assertFalse(r["rin_is_rc"])
        self.assertTrue(r["rin_other"])
        self.assertTrue(r["ein_is_rc"])

    def test_not_found(self):
        r = m.classify(self.t["10.1016/j.c.1"], None, self.linked)
        self.assertFalse(r["pm_found"] or r["flagged"])


class Grade(unittest.TestCase):
    def test_summary_and_grade(self):
        rows = []
        for i in range(30):
            rows.append({"target": "10.9/r%d" % i, "group": "retraction", "pm_found": True,
                         "flagged": i < 4, "rin_dois": "x" if i < 4 else "", "rin_is_rc": i < 4,
                         "rin_other": False, "ein_is_rc": 4 <= i < 10})
        for i in range(30):
            rows.append({"target": "10.9/o%d" % i, "group": "other", "pm_found": i < 10,
                         "flagged": False, "rin_dois": "", "rin_is_rc": False,
                         "rin_other": False, "ein_is_rc": False})
        s = m.summarize(rows, 0)
        self.assertEqual((s["n_targets"], s["n_found"], s["n_flagged"]), (60, 40, 4))
        self.assertEqual(s["found_flagged_by_group"], {"retraction": [30, 4], "other": [10, 0]})
        self.assertEqual(s["share_rin_is_rc"], 1.0)
        self.assertEqual(s["n_ein_is_rc"], 6)
        gates, p = m.grade(s, rows)
        self.assertTrue(gates["G1_targets_ge_60"] and gates["G2_search_fail_le_5pct"])
        self.assertFalse(gates["G3_instrument"])  # G3 DOIs are absent from this toy set
        self.assertEqual(p, {"P1": True, "P2": True, "P3": True, "P4": True, "P5": True,
                             "P6": True})


if __name__ == "__main__":
    unittest.main()
