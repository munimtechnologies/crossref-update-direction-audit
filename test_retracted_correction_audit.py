# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Unit tests for retracted_correction_audit.py (no network)."""
import unittest

import retracted_correction_audit as ra


def item(doi, title, updates, member="78", publisher="Elsevier BV", year=2022):
    return {"DOI": doi, "title": [title], "member": member, "publisher": publisher,
            "created": {"date-parts": [[year, 1, 1]]}, "container-title": ["J"],
            "update-to": [{"DOI": d, "type": t, "source": s} for d, t, s in updates]}


class Titles(unittest.TestCase):
    def test_notice_class(self):
        nc = ra.notice_class
        self.assertEqual(nc("RETRACTED: Corrigendum to “Paper one” [J 1 (2020) 1]"), "rc")
        self.assertEqual(nc("WITHDRAWN: Erratum"), "rc")
        self.assertEqual(nc("Withdrawn: Corrigendum to Withdrawn: “De novo lipogenesis”"), "rc")
        self.assertEqual(nc("TEMPORARY REMOVAL: Corrigendum to “LPI alleviates”"), "rc")
        self.assertEqual(nc("RETRACTED ARTICLE: Correction to: A study"), "rc")
        self.assertEqual(nc("Retraction notice to “Corrigendum to “Smooth muscle””"), "rn")
        self.assertEqual(nc("Retraction: Corrigendum: CMTM6 as a candidate risk gene"), "rn")
        self.assertEqual(nc("Retraction Note: Correction to: A study"), "rn")
        self.assertEqual(nc("RETRACTED: Personality traits among PhD students [Acta 239 (2023) 1]"),
                         "plain")
        self.assertEqual(nc("Retraction notice to “Paper two”"), "plain")
        self.assertEqual(nc("Retractions and Errata"), "correction")
        self.assertEqual(nc("Corrigendum"), "correction")
        self.assertEqual(nc("Partial Retraction: yadBC of Yersinia pestis"), "plain")
        self.assertEqual(nc(""), "empty")

    def test_notice_worded(self):
        self.assertTrue(ra.notice_worded("Retraction notice to “Corrigendum to X”"))
        self.assertTrue(ra.notice_worded("Notice of Retraction: X"))
        self.assertTrue(ra.notice_worded("Withdrawal notice to X"))
        self.assertFalse(ra.notice_worded("Retractions and Errata"))
        self.assertFalse(ra.notice_worded("Erratum"))
        self.assertFalse(ra.notice_worded("RETRACTED: Corrigendum to X"))

    def test_t_marked(self):
        self.assertTrue(ra.t_marked("RETRACTED: Impact of Nigeria's industrial sector"))
        self.assertTrue(ra.t_marked("Retracted article: X"))
        self.assertTrue(ra.t_marked("[Retracted] X"))
        self.assertTrue(ra.t_marked("A study of X (Retracted)"))
        self.assertTrue(ra.t_marked("WITHDRAWN: A study"))
        self.assertFalse(ra.t_marked("Smooth muscle 22 alpha maintains the phenotype"))
        self.assertFalse(ra.t_marked("Retraction of the uterus in surgery"))
        self.assertFalse(ra.t_marked(""))

    def test_t_is_correction(self):
        self.assertTrue(ra.t_is_correction("Corrigendum to “X”"))
        self.assertTrue(ra.t_is_correction("RETRACTED: Corrigendum to “X”"))
        self.assertFalse(ra.t_is_correction("Smooth muscle 22 alpha"))


class WalkerTest(unittest.TestCase):
    def test_walker(self):
        w = ra.Walker()
        a = item("10.1/N1", "RETRACTED: Corrigendum to “Paper one” [J 1 (2020) 1]",
                 [("10.1/T1", "retraction", "publisher")])
        w.add(a)
        w.add(item("10.1/N2", "Retraction notice to “Paper two”",
                   [("10.1/T2", "retraction", "publisher"), ("10.1/T2", "retraction", "retraction-watch")]))
        w.add(item("10.1/S", "RETRACTED: Paper three", [("10.1/S", "retraction", "publisher")]))
        w.add(item("10.1/N4", "WITHDRAWN: Erratum", [("10.1/T4", "withdrawal", "publisher"),
                                                     ("10.1/T4", "withdrawal", "publisher")]))
        w.add(item("10.1/N5", "Retraction: Corrigendum: Paper five", [("10.1/C5", "retraction", "publisher")]))
        w.add(item("10.1/N6", "Erratum", [("10.1/T6", "erratum", "publisher")]))
        w.add(a)  # seen again in a later walk: ignored
        self.assertEqual(w.n_records, 6)
        self.assertEqual([(r["notice"], r["target"], r["nclass"]) for r in w.rels],
                         [("10.1/n1", "10.1/t1", "rc"), ("10.1/n2", "10.1/t2", "plain"),
                          ("10.1/n4", "10.1/t4", "rc"), ("10.1/n5", "10.1/c5", "rn")])
        self.assertEqual(w.self_retracted, {"10.1/s"})
        self.assertEqual(w.rw_retracted, {"10.1/t2"})
        self.assertEqual(w.sources["publisher"], 6)
        self.assertEqual(w.sources["retraction-watch"], 1)
        self.assertEqual(w.rels[2]["utype"], "withdrawal")

    def test_evidence(self):
        w = ra.Walker()
        w.rw_retracted = {"t2"}
        w.self_retracted = {"t3"}
        plain = {"t4"}
        self.assertEqual(ra.evidence("t1", w, plain, "Smooth muscle 22 alpha"), [])
        self.assertEqual(ra.evidence("t2", w, plain, ""), ["rw"])
        self.assertEqual(ra.evidence("t3", w, plain, "RETRACTED: X"), ["self", "title"])
        self.assertEqual(ra.evidence("t4", w, plain, "X"), ["notice"])


class Updates(unittest.TestCase):
    def test_add_updates_and_status(self):
        out = {}
        wanted = {"10.1/n1", "10.1/n2"}
        ra.add_updates(out, item("10.1/R1", "Retraction notice to “Corrigendum to X”",
                                 [("10.1/N1", "erratum", "publisher"), ("10.1/T1", "erratum", "publisher"),
                                  ("10.1/N1", "retraction", "retraction-watch")]), wanted)
        ra.add_updates(out, item("10.1/R2", "Retraction notice to “Corrigendum to Y”",
                                 [("10.1/N2", "retraction", "publisher")]), wanted)
        ra.add_updates(out, item("10.1/N2", "self", [("10.1/N2", "retraction", "publisher")]), wanted)
        self.assertEqual(out["10.1/n1"], [
            ("10.1/r1", "erratum", "publisher", "Retraction notice to “Corrigendum to X”"),
            ("10.1/r1", "retraction", "retraction-watch", "Retraction notice to “Corrigendum to X”")])
        self.assertEqual(len(out["10.1/n2"]), 1)
        self.assertEqual(ra.notice_status(out["10.1/n1"]), "swap")
        self.assertEqual(ra.notice_status(out["10.1/n2"]), "retractive_notice")
        self.assertEqual(ra.notice_status([]), "none")
        self.assertEqual(ra.notice_status([("r", "erratum", "publisher", "Erratum")]), "none")
        self.assertEqual(ra.notice_status([("r", "retraction", "retraction-watch", "x")]), "rw_only")


class Summary(unittest.TestCase):
    def test_summarize(self):
        w = ra.Walker()
        rc = [
            dict(notice="n1", target="t1", utype="retraction", publisher="Elsevier BV", year=2022,
                 verdict="only_via_rc", evidence="", n_status="swap", oa_is_retracted=True,
                 oa_cited_by=100),
            dict(notice="n2", target="t2", utype="withdrawal", publisher="Elsevier BV", year=2019,
                 verdict="only_via_rc", evidence="", n_status="none", oa_is_retracted=False,
                 oa_cited_by=50),
            dict(notice="n3", target="t3", utype="retraction", publisher="Wiley", year=2021,
                 verdict="also_retracted", evidence="rw;title", n_status="retractive_notice"),
            dict(notice="n4", target="t1", utype="withdrawal", publisher="Elsevier BV", year=2023,
                 verdict="only_via_rc", evidence="", n_status="unknown", oa_is_retracted=True,
                 oa_cited_by=100),
        ]
        rn = [dict(notice="m1", target="p1", publisher="Elsevier BV", t_title="A paper"),
              dict(notice="m2", target="c2", publisher="Elsevier BV", t_title="Corrigendum to X"),
              dict(notice="m3", target="c3", publisher="Wiley", t_title="")]
        s = ra.summarize(w, rc, rn, True)
        self.assertEqual(s["n_rc_relations"], 4)
        self.assertEqual(s["n_rc_notices"], 4)
        self.assertEqual(s["n_rc_targets"], 3)
        self.assertEqual(s["share_elsevier"], 0.75)
        self.assertEqual(s["n_only"], 3)
        self.assertEqual(s["n_only_targets"], 2)
        self.assertEqual(s["share_only"], 0.75)
        self.assertEqual(s["oa_only_targets"], {"retraction": [1, 1], "other": [1, 0]})
        self.assertEqual(s["oa_only_citations"], 150)
        self.assertEqual(s["only_status"], {"retraction": {"swap": 1},
                                            "other": {"none": 1, "unknown": 1}})
        self.assertEqual(s["swap_share_retraction"], 1.0)
        self.assertEqual(s["none_share_other"], 1.0)
        self.assertEqual(s["also_evidence"], {"rw": 1, "title": 1})
        self.assertEqual(s["n_rn_relations"], 3)
        self.assertEqual(s["n_rn_target_titles"], 2)
        self.assertEqual(s["rn_points_at_non_correction"], 1)
        self.assertFalse(s["g2_pass"])
        self.assertEqual(set(s["g2_only"].values()), {"missing"})

    def test_g2_cases(self):
        self.assertEqual(len(ra.ONLY_CASES), 5)
        self.assertEqual(len(ra.G2_TARGETS), 6)
        for n, t in ra.ONLY_CASES + ra.ALSO_CASES:
            self.assertEqual(n, n.lower())
            self.assertNotEqual(n, t)
        for n in ra.SWAP_CASES:
            self.assertIn(n, {p[0] for p in ra.ONLY_CASES})


if __name__ == "__main__":
    unittest.main()
