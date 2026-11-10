# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Offline tests for rw_pubmed_link_census.py (no network)."""
import collections
import io
import unittest

import rw_pubmed_link_census as m

HEADER = ("Record ID,Title,Subject,Institution,Journal,Publisher,Country,Author,URLS,ArticleType,"
          "RetractionDate,RetractionDOI,RetractionPubMedID,OriginalPaperDate,OriginalPaperDOI,"
          "OriginalPaperPubMedID,RetractionNature,Reason,Paywalled,Notes\n")


def row(rid, title, ndoi, npmid, odoi, opmid, nature="Retraction"):
    return ('%s,"%s",,,J,Pub,,,,,1/1/2020 0:00,%s,%s,1/1/2019 0:00,%s,%s,%s,,No,\n'
            % (rid, title, ndoi, npmid, odoi, opmid, nature))


def rec(pmid, doi, title, pubtype, refs):
    """esummary-like entry; refs = [(reftype, pmid, doi or '')]."""
    return {"uid": pmid, "title": title, "pubtype": pubtype,
            "articleids": [{"idtype": "pubmed", "value": pmid}, {"idtype": "doi", "value": doi}],
            "references": [{"refsource": ("J. 2020. doi: %s." % d) if d else "J. 2020.",
                            "reftype": rt, "pmid": p} for rt, p, d in refs]}


class Helpers(unittest.TestCase):
    def test_parse_pmid(self):
        self.assertEqual(m.parse_pmid("31662796"), ("31662796", "ok"))
        self.assertEqual(m.parse_pmid(" 123.0 "), ("123", "ok"))
        self.assertEqual(m.parse_pmid("0"), ("", "none"))
        self.assertEqual(m.parse_pmid(""), ("", "none"))
        self.assertEqual(m.parse_pmid(None), ("", "none"))
        self.assertEqual(m.parse_pmid("123;456"), ("", "malformed"))

    def test_first_doi_and_ref_doi(self):
        self.assertEqual(m.first_doi("https://doi.org/10.1177/ABC.1"), "10.1177/abc.1")
        self.assertEqual(m.first_doi("unavailable"), "")
        self.assertEqual(m.first_doi("10.1/x;10.1000/y"), "10.1000/y")
        self.assertEqual(m.ref_doi("Ther Adv. 2019. doi: 10.1177/1758835919878347."),
                         "10.1177/1758835919878347")
        self.assertEqual(m.ref_doi("J. 2010;24:648."), "")

    def test_jaccard(self):
        self.assertEqual(m.jaccard("RETRACTED: The effect of cellfood", "The effect of CELLFOOD"), 1.0)
        self.assertEqual(m.jaccard("", "x y z"), 0.0)
        self.assertLess(m.jaccard("tumour growth in mice", "a survey of dentists"), 0.3)

    def test_is_retr_link(self):
        for t in ("Retraction of", "retraction in", "Partial retraction in",
                  "Retracted and republished in"):
            self.assertTrue(m.is_retr_link(t), t)
        for t in ("Erratum in", "Comment on", "Expression of concern for", ""):
            self.assertFalse(m.is_retr_link(t), t)


class RW(unittest.TestCase):
    def test_rw_pairs(self):
        text = (HEADER
                + row(1, "Paper A", "10.1000/na", "200", "10.1000/a", "100")
                + row(2, "Paper A again", "10.1000/na", "200", "10.1000/a", "100")
                + row(3, "Paper B", "10.1000/nb", "0", "10.1000/b", "101")
                + row(4, "Paper C", "10.1000/c", "102", "10.1000/c", "102")
                + row(5, "Paper D", "10.1000/nd", "203", "10.1000/d", "103", "Correction")
                + row(6, "Paper E", "10.1000/ne", "204", "10.1000/e", "1;2"))
        pairs, st = m.rw_pairs(io.StringIO(text))
        self.assertEqual(list(pairs), [("100", "200")])
        p = pairs[("100", "200")]
        self.assertEqual(p["rw_rows"], 2)
        self.assertEqual(p["rw_record_id"], "1")
        self.assertEqual(p["rw_doi"], "10.1000/a")
        self.assertEqual(p["rw_title"], "Paper A")
        self.assertEqual(st["rows"], 6)
        self.assertEqual(st["retraction_rows"], 5)
        self.assertEqual(st["same_pmid"], 1)
        self.assertEqual(st["eligible_rows"], 2)
        self.assertEqual(st["n_none"], 1)
        self.assertEqual(st["o_malformed"], 1)
        self.assertEqual(st["header_ok"], 1)


def recs_of(*entries):
    return {e["uid"]: m.compact(e["uid"], e) for e in entries}


class Classify(unittest.TestCase):
    def test_compact(self):
        c = m.compact("1", rec("1", "10.1000/A", "T", ["Journal Article"],
                               [("Retraction in", "2", "10.1000/n")]))
        self.assertEqual(c["doi"], "10.1000/a")
        self.assertEqual(c["refs"], [("retraction in", "2", "10.1000/n")])
        self.assertEqual(c["pubtype"], ["journal article"])
        self.assertIsNone(m.compact("9", {"uid": "9", "error": "cannot get document summary"}))
        self.assertIsNone(m.compact("9", None))

    def test_agree_both_and_control_shape(self):
        r = recs_of(rec("31662796", "10.1177/1758835919878347", "CELLFOOD",
                        ["Journal Article", "Retracted Publication"],
                        [("Retraction in", "34422117", "10.1177/17588359211029757")]),
                    rec("34422117", "10.1177/17588359211029757", "Retraction notice.",
                        ["Retraction Notice"],
                        [("Retraction of", "31662796", "10.1177/1758835919878347")]))
        self.assertEqual(m.classify("31662796", "34422117", r), ("agree_both", []))
        self.assertTrue(m.o_flagged(r["31662796"]))
        self.assertTrue(m.is_notice(r["34422117"]))

    def test_missing(self):
        r = recs_of(rec("1", "10.1000/a", "A", ["Journal Article"], []))
        r["2"] = None
        self.assertEqual(m.classify("1", "2", r)[0], "n_missing")
        self.assertEqual(m.classify("3", "1", r)[0], "o_missing")

    def test_one_side_by_doi_only(self):
        r = recs_of(rec("1", "10.1000/a", "A", ["Journal Article"], []),
                    rec("2", "10.1000/n", "Notice", ["Retraction Notice"],
                        [("Retraction of", "", "10.1000/a")]))
        self.assertEqual(m.classify("1", "2", r)[0], "agree_one_side")

    def test_other_type(self):
        r = recs_of(rec("1", "10.1000/a", "A", ["Journal Article"], [("Erratum in", "2", "")]),
                    rec("2", "10.1000/n", "Erratum", ["Published Erratum"],
                        [("Erratum for", "1", "")]))
        self.assertEqual(m.classify("1", "2", r)[0], "linked_other_type")

    def test_targets_other_and_adjudicate(self):
        r = recs_of(rec("1", "10.1000/a", "Liver enzymes in rats", ["Journal Article"], []),
                    rec("2", "10.1000/n", "Retraction notice", ["Retraction Notice"],
                        [("Retraction of", "3", "")]),
                    rec("3", "10.1000/t", "Tumour growth in nude mice",
                        ["Journal Article", "Retracted Publication"], [("Retraction in", "2", "")]))
        cl, others = m.classify("1", "2", r)
        self.assertEqual((cl, others), ("n_targets_other", ["3"]))
        pair = {"o": "1", "n": "2", "rw_doi": "10.1000/t", "rw_title": "Tumour growth in nude mice"}
        j = m.adjudicate(pair, others, r)
        self.assertEqual(j["by_doi"], "rw_pmid_wrong")
        self.assertEqual(j["by_title"], "rw_pmid_wrong")
        pair = {"o": "1", "n": "2", "rw_doi": "10.1000/a", "rw_title": "Liver enzymes in rats"}
        j = m.adjudicate(pair, others, r)
        self.assertEqual(j["by_doi"], "pubmed_link_suspect")
        self.assertEqual(j["by_title"], "pubmed_link_suspect")
        pair = {"o": "1", "n": "2", "rw_doi": "", "rw_title": ""}
        j = m.adjudicate(pair, others, r)
        self.assertEqual((j["by_doi"], j["by_title"]), ("undetermined", "undetermined"))

    def test_o_linked_other_and_unlinked(self):
        r = recs_of(rec("1", "10.1000/a", "A", ["Journal Article", "Retracted Publication"],
                        [("Retraction in", "5", "")]),
                    rec("2", "10.1000/n", "Notice", ["Retraction Notice"], []),
                    rec("4", "10.1000/b", "B", ["Journal Article"], []))
        self.assertEqual(m.classify("1", "2", r), ("o_linked_other", ["5"]))
        self.assertEqual(m.classify("4", "2", r), ("unlinked", []))
        self.assertFalse(m.o_flagged(r["4"]))


class Grade(unittest.TestCase):
    def test_grade_all_hold(self):
        c = collections.Counter({"agree_both": 9000, "agree_one_side": 100, "n_targets_other": 50,
                                 "unlinked": 200, "o_linked_other": 20, "linked_other_type": 10})
        adj = ([{"by_doi": "rw_pmid_wrong", "by_title": "rw_pmid_wrong"}] * 30
               + [{"by_doi": "pubmed_link_suspect", "by_title": "pubmed_link_suspect"}] * 6
               + [{"by_doi": "undetermined", "by_title": "undetermined"}] * 14)
        gates = {"G1": {"ok": True}}
        g = m.grade(c, adj, 100, 9380, gates)
        for k in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"):
            self.assertTrue(g[k]["held"], k)
        self.assertEqual(g["P5"]["value"], [0.8333, 0.8333])

    def test_grade_fail_and_inconclusive(self):
        c = collections.Counter({"agree_both": 100, "unlinked": 5})
        g = m.grade(c, [], 0, 105, {"G1": {"ok": False}})
        self.assertFalse(g["P1"]["held"])
        self.assertFalse(g["P4"]["held"])
        self.assertIsNone(g["P5"]["held"])
        self.assertIsNone(g["P8"]["held"])
        self.assertIn("gate failed", g["P2"]["note"])


if __name__ == "__main__":
    unittest.main()
