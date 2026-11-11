# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Offline unit tests for duplicate_withdrawal_audit.py (no network)."""
import unittest

import duplicate_withdrawal_audit as m


T = "10.1/old"
T_ITEM = {"DOI": "10.1/OLD", "type": "journal-article", "container-title": ["J &amp; K"],
          "author": [{"given": "A", "family": "Lee", "sequence": "first"}]}
T_TITLE = "WITHDRAWN: Big new results on things"


def hit(doi, title, **kw):
    h = {"DOI": doi, "type": "journal-article", "title": [title], "container-title": ["J & K"],
         "author": [{"family": "Lee"}]}
    h.update(kw)
    return h


class Titles(unittest.TestCase):
    def test_clean_title(self):
        self.assertEqual(m.clean_title("WITHDRAWN: Pharmacogenetics of osteoporosis"),
                         "pharmacogenetics of osteoporosis")
        self.assertEqual(m.clean_title("WITHDRAWN:Investor's anticipation"), "investor's anticipation")
        self.assertEqual(m.clean_title("Some study (Retracted)"), "some study")
        self.assertEqual(m.clean_title("Plain  title"), "plain title")

    def test_title_key(self):
        self.assertEqual(m.title_key("WITHDRAWN: X-ray study"), m.title_key("X-ray Study"))
        self.assertEqual(m.title_key("Hall-Williamson and x-ray"), "hall williamson and x ray")
        self.assertEqual(m.title_key("Computers &amp; Graphics"), "computers graphics")

    def test_t_marked(self):
        self.assertTrue(m.t_marked("WITHDRAWN: Something"))
        self.assertFalse(m.t_marked("Withdrawal of antihypertensive drugs"))

    def test_jaccard(self):
        self.assertAlmostEqual(m.jaccard("a b c d", "a b c e"), 0.6)
        self.assertEqual(m.jaccard("", "a"), 0.0)


class Authors(unittest.TestCase):
    def test_author_match(self):
        self.assertTrue(m.author_match([{"family": "Müller"}], [{"given": "A", "family": "Muller"}]))
        self.assertIsNone(m.author_match([], [{"family": "X"}]))
        self.assertFalse(m.author_match([{"family": "A"}], [{"family": "B"}]))

    def test_first_family(self):
        self.assertEqual(m.first_family([{"family": "B"}, {"family": "A", "sequence": "first"}]), "A")
        self.assertEqual(m.first_family([{"family": "B"}]), "B")
        self.assertEqual(m.first_family(None), "")


class Links(unittest.TestCase):
    def test_linked_dois(self):
        item = {"relation": {"is-identical-to": [{"id-type": "doi", "id": "https://doi.org/10.1/ABC"}],
                             "cites": [{"id-type": "uri", "id": "x"}]},
                "update-to": [{"DOI": "10.1/Self", "type": "withdrawal"}]}
        self.assertEqual(m.linked_dois(item), {"10.1/abc", "10.1/self"})
        self.assertEqual(m.linked_dois(None), set())

    def test_query_text(self):
        self.assertEqual(m.query_text(T_TITLE, T_ITEM), "big new results on things lee j k")


class Judge(unittest.TestCase):
    def test_exact_copy(self):
        c = m.judge(T, T_ITEM, T_TITLE, hit("10.1/NEW", "Big new results on things"))
        self.assertEqual(c["doi"], "10.1/new")
        self.assertTrue(c["exact"])
        self.assertTrue(c["author_match"])
        self.assertTrue(c["same_type"])
        self.assertTrue(c["same_journal"])
        self.assertFalse(c["later_version"])
        self.assertFalse(c["linked"])
        self.assertEqual(c["ntok"], 5)

    def test_excluded_hits(self):
        self.assertIsNone(m.judge(T, T_ITEM, T_TITLE, hit("10.1/old", "Big new results on things")))
        self.assertIsNone(m.judge(T, T_ITEM, T_TITLE, hit("10.1/x", "WITHDRAWN: Big new results on things")))
        self.assertIsNone(m.judge(T, T_ITEM, T_TITLE, hit(
            "10.1/x", "Big new results on things", **{"update-to": [{"DOI": "10.1/old", "type": "retraction"}]})))
        self.assertIsNone(m.judge(T, T_ITEM, T_TITLE, hit("10.1/x", "Big new results on things",
                                                          type="peer-review")))
        self.assertIsNone(m.judge(T, T_ITEM, T_TITLE, hit("10.1/x", "Something else entirely")))

    def test_near_and_linked(self):
        h = hit("10.1/near", "Big new results on things today",
                relation={"is-identical-to": [{"id-type": "doi", "id": "10.1/OLD"}]})
        c = m.judge(T, T_ITEM, T_TITLE, h)
        self.assertFalse(c["exact"])
        self.assertAlmostEqual(c["jaccard"], 0.833)
        self.assertTrue(c["linked"])


def cand(**kw):
    c = {"doi": "10.1/new", "exact": True, "author_match": True, "ntok": 5, "same_type": True,
         "later_version": False, "same_journal": True}
    c.update(kw)
    return c


class Classify(unittest.TestCase):
    def test_duplicate(self):
        self.assertEqual(m.classify([cand()])[0], "duplicate")

    def test_prefers_exact(self):
        cls, best = m.classify([cand(doi="a", exact=False), cand(doi="b")])
        self.assertEqual((cls, best["doi"]), ("duplicate", "b"))

    def test_later_version(self):
        self.assertEqual(m.classify([cand(later_version=True)])[0], "later_version")

    def test_other_version(self):
        self.assertEqual(m.classify([cand(same_type=False)])[0], "other_version")

    def test_short_title_without_authors_is_clash(self):
        self.assertEqual(m.classify([cand(author_match=None, ntok=1)])[0], "title_clash")

    def test_no_author_exact_long_title_counts(self):
        self.assertEqual(m.classify([cand(author_match=None)])[0], "duplicate")

    def test_different_authors(self):
        self.assertEqual(m.classify([cand(author_match=False)])[0], "title_clash")
        self.assertEqual(m.classify([cand(author_match=False, exact=False)])[0], "none")
        self.assertEqual(m.classify([cand(author_match=None, exact=False)])[0], "none")

    def test_empty(self):
        self.assertEqual(m.classify([]), ("none", None))


class Input(unittest.TestCase):
    def test_read_input(self):
        body = ("target,group,self_w,crossref_title\n"
                "10.1/a,w_only,True,\"WITHDRAWN: A, b\"\n"
                "10.1/b,w_only,False,\n").encode("utf-8")
        rows = m.read_input(body)
        self.assertEqual([r["target"] for r in rows], ["10.1/a"])
        self.assertEqual(rows[0]["crossref_title"], "WITHDRAWN: A, b")


class Grade(unittest.TestCase):
    def counts(self, **kw):
        c = {"m_n": 100, "m_dup": 80, "e_n": 90, "e_dup": 70, "u_n": 50, "u_dup": 10,
             "d_n": 100, "d_unlinked": 95, "d_same_journal": 60, "h_found": 100, "h_flag": 1}
        c.update(kw)
        return c

    def test_all_hold(self):
        res = m.grade(self.counts(), {"G1": {"ok": True}})
        self.assertEqual({k: v["held"] for k, v in res.items()},
                         {"P1": True, "P2": True, "P3": True, "P4": True, "P5": True, "P6": True})

    def test_fail_and_inconclusive(self):
        res = m.grade(self.counts(m_dup=95, u_n=10, h_flag=5), {"G1": {"ok": True}})
        self.assertFalse(res["P1"]["held"])
        self.assertIsNone(res["P3"]["held"])
        self.assertFalse(res["P6"]["held"])

    def test_gate_note(self):
        res = m.grade(self.counts(), {"G1": {"ok": False}})
        self.assertIn("a gate failed", res["P1"]["note"])


if __name__ == "__main__":
    unittest.main()
