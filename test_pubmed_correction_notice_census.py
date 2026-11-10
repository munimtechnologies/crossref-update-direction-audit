# Copyright 2026 MV2, Munim, Inc. (mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Offline tests for pubmed_correction_notice_census.py (no network)."""
import unittest

import pubmed_correction_notice_census as m


def doc(uid, title, pubtype, refs, doi=None):
    return {"uid": uid, "doi": doi if doi is not None else "10.1016/x." + uid, "pubtype": pubtype,
            "title": title, "source": "J", "pubdate": "", "refs": refs}


class Classify(unittest.TestCase):
    def test_real_titles(self):
        cases = {
            'WITHDRAWN: Corrigendum to "Red Wine Prevents the Acute Negative Vascular Effects of Smoking".': "WC",
            "RETRACTED: Corrigendum to X": "WC",
            "WITHDRAWN: corrigendum to “Effectiveness of complementary pain treatment": "WC",
            "Retraction: Correction: Emotional regulation self-efficacy": "RNC",
            "Retraction: Corrigendum: Exosomal CD44 transmits": "RNC",
            "Retraction notice to \"Corrigendum to 'Cellular prion protein modulates": "RNC",
            'Withdrawal notice to "Corrigendum to Complement activation sustains': "RNC",
            "Retraction notice to Corrigendum to ''Analysis of the Application Value": "RNC",
            "[Retraction of: Corrigendum to X]": "RNC",
            "Retraction Note: Correction to: X": "RNC",
            "Erratum: Hydatid Cysts of Parotid Glands- Diagnosis, Treatment and Recurrences: Retraction.": "C",
            'Retraction notice to "Correction of hyperopia by laser"': "OTHER",
            'Retraction notice to "Y study"': "OTHER",
        }
        for t, want in cases.items():
            self.assertEqual(m.notice_class(t), want, t)

    def test_norm_title(self):
        self.assertEqual(m.norm_title("“A”  [b]"), "a b")

    def test_is_corr_record(self):
        self.assertTrue(m.is_corr_record(doc("1", "x", ["Published Erratum"], [])))
        self.assertTrue(m.is_corr_record(doc("1", "Corrigendum to X", ["Journal Article"], [])))
        self.assertTrue(m.is_corr_record(doc("1", "WITHDRAWN: Erratum to X", ["Journal Article"], [])))
        self.assertFalse(m.is_corr_record(doc("1", "Red wine", ["Journal Article"], [])))


class Parse(unittest.TestCase):
    def test_esearch(self):
        self.assertEqual(m.parse_esearch('{"esearchresult": {"count": "2", "idlist": ["1", "2"]}}'),
                         (2, ["1", "2"]))
        self.assertIsNone(m.parse_esearch('{"esearchresult": {"ERROR": "x"}}'))
        self.assertIsNone(m.parse_esearch("not json"))

    def test_esummary(self):
        js = ('{"result": {"uids": ["5"], "5": {"uid": "5", "title": "T", "pubtype": ["Journal Article"],'
              ' "articleids": [{"idtype": "doi", "value": "10.1/X"}],'
              ' "references": [{"reftype": "Retraction in", "pmid": 7}]}}}')
        d = m.parse_esummary(js)
        self.assertEqual(d["5"]["doi"], "10.1/x")
        self.assertEqual(d["5"]["refs"], [("Retraction in", "7")])
        self.assertIsNone(m.parse_esummary('{"error": "x"}'))


def fixture():
    docs, notices = {}, []
    for n, p in m.G3_NOTICES.items():
        docs[n] = doc(n, 'WITHDRAWN: Corrigendum to "Paper %s"' % p, ["Retraction Notice"],
                      [("Retraction of", p)])
        docs[p] = doc(p, "Paper " + p, ["Journal Article", "Retracted Publication"],
                      [("Retraction in", n)], doi="10.1016/p." + p)
        notices.append(n)
    docs["900"] = doc("900", 'Retraction notice to "Corrigendum to Y"', ["Retraction Notice"],
                      [("Retraction of", "901")])
    docs["901"] = doc("901", "Corrigendum to Y", ["Published Erratum"], [("Retraction in", "900")])
    docs["910"] = doc("910", "Retraction: Correction: Z", ["Retraction Notice"], [("Retraction of", "911")])
    docs["911"] = doc("911", "Z", ["Journal Article", "Retracted Publication"],
                      [("Retraction in", "910"), ("Retraction in", "912")])
    docs["912"] = doc("912", 'Retraction notice to "Z"', ["Retraction Notice"], [("Retraction of", "911")])
    docs["920"] = doc("920", 'Retraction notice to "Correction of scoliosis"', ["Retraction Notice"],
                      [("Retraction of", "921")])
    docs["921"] = doc("921", "Correction of scoliosis", ["Journal Article", "Retracted Publication"],
                      [("Retraction in", "920")])
    notices += ["900", "910", "920"]
    return notices, docs


class Analyse(unittest.TestCase):
    def test_analyse_summary_grade(self):
        notices, docs = fixture()
        nrows, prows = m.analyse(notices, docs)
        s = m.summarize(nrows, prows, n_ids=9, count=9)
        self.assertEqual(s["class_counts"], {"WC": 6, "RNC": 2, "C": 0, "OTHER": 1})
        self.assertEqual(s["n_S"], 8)
        self.assertEqual(s["n_S_with_target"], 8)
        self.assertEqual(s["n_S_paper_target"], 7)
        self.assertEqual(s["share_WC_paper_target"], 1.0)
        self.assertEqual(s["share_RNC_paper_target"], 0.5)
        self.assertEqual(s["n_paper_targets"], 7)
        self.assertEqual(s["n_only_via"], 6)
        self.assertEqual(s["share_only_via_elsevier"], 1.0)
        self.assertEqual(s["n_only_via_openalex_found"], 0)
        p911 = [r for r in prows if r["paper"] == "911"][0]
        self.assertFalse(p911["only_via_correction"])
        self.assertEqual(p911["retraction_in_classes"], "RNC;OTHER")
        self.assertNotIn("921", [r["paper"] for r in prows])
        gates, p = m.grade(s, nrows, prows, target_fail=0)
        self.assertFalse(gates["G1_census_complete"])
        self.assertTrue(gates["G2_targets_read"])
        self.assertTrue(gates["G3_instrument"])
        self.assertTrue(p["P1"])
        self.assertTrue(p["P2"])
        self.assertTrue(p["P3"])
        self.assertFalse(p["P4"])
        self.assertTrue(p["P5"])
        self.assertEqual(p["P6"], "not graded")

    def test_unread_rin_not_only_via(self):
        notices, docs = fixture()
        docs["38364746"]["refs"].append(("Retraction in", "999"))  # unread notice
        nrows, prows = m.analyse(notices, docs)
        r = [x for x in prows if x["paper"] == "38364746"][0]
        self.assertFalse(r["only_via_correction"])
        self.assertIn("UNREAD", r["retraction_in_classes"])


if __name__ == "__main__":
    unittest.main()
