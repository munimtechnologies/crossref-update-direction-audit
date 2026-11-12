# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
"""Offline tests for cochrane_rw_title_check.py (no network)."""
import unittest

import cochrane_rw_title_check as m

P = "10.1002/14651858."


class TestTitles(unittest.TestCase):
    def test_norm_strips_prefix_and_punctuation(self):
        self.assertEqual(m.norm_title("WITHDRAWN: Omentoplasty for the <i>prevention</i>, of leakage."),
                         "omentoplasty for the prevention of leakage")

    def test_norm_double_prefix_and_entities(self):
        self.assertEqual(m.norm_title("Retraction: Withdrawn &amp; Co"), "co")

    def test_norm_empty(self):
        self.assertEqual(m.norm_title(None), "")

    def test_jaccard(self):
        self.assertEqual(m.jaccard("a b c d", "a b c d"), 1.0)
        self.assertEqual(m.jaccard("a b", ""), 0.0)
        self.assertAlmostEqual(m.jaccard("a b c d e", "a b c d f"), 4 / 6)

    def test_cd_of(self):
        self.assertEqual(m.cd_of("cd011313.pub3"), "cd011313")
        self.assertEqual(m.cd_of("x"), "")


class TestMatch(unittest.TestCase):
    T = m.norm_title("Surgery for complicated diverticular disease: primary or secondary anastomosis")

    def row(self, **kw):
        r = {"Record ID": "1", "Title": "", "OriginalPaperDOI": "", "RetractionDOI": "",
             "RetractionNature": "Retraction", "RetractionDate": "1/1/2020 0:00", "Journal": "J",
             "Reason": ""}
        r.update(kw)
        return r

    def test_title_exact(self):
        r = self.row(Title="WITHDRAWN: Surgery for complicated diverticular disease - primary or "
                           "secondary anastomosis")
        self.assertEqual(m.row_matches(r, self.T, "cd006141", P + "cd006141.pub3"), ["title_exact"])

    def test_title_close(self):
        r = self.row(Title="Surgery for complicated diverticular disease: primary or secondary anastomoses")
        self.assertEqual(m.row_matches(r, self.T, "", ""), ["title_close"])

    def test_short_title_needs_exact(self):
        self.assertEqual(m.row_matches(self.row(Title="a b c x"), "a b c d", "", ""), [])

    def test_cd_and_notice(self):
        r = self.row(OriginalPaperDOI="10.1002/14651858.CD006141.pub2",
                     RetractionDOI="10.1002/14651858.CD006141.pub3")
        self.assertEqual(m.row_matches(r, "", "cd006141", P + "cd006141.pub3"), ["cd", "notice"])

    def test_cd_not_prefix_of_longer_number(self):
        r = self.row(OriginalPaperDOI="10.1002/14651858.CD0061410")
        self.assertEqual(m.row_matches(r, "", "cd006141", ""), [])

    def test_unrelated(self):
        r = self.row(Title="Something else entirely here", OriginalPaperDOI="10.1/x")
        self.assertEqual(m.row_matches(r, self.T, "cd006141", P + "cd006141.pub3"), [])

    def test_scan(self):
        rows = [self.row(**{"Record ID": "7", "OriginalPaperDOI": P + "CD006141.pub2"}),
                self.row(**{"Record ID": "8", "Title": "other"})]
        out, n = m.scan(iter(rows), {"cd006141.pub2": (self.T, "cd006141", P + "cd006141.pub3")})
        self.assertEqual(n, 2)
        self.assertEqual([x["id"] for x in out["cd006141.pub2"]], ["7"])
        self.assertEqual(out["cd006141.pub2"][0]["how"], "cd")

    def test_targets_well_formed(self):
        self.assertEqual(len(m.TARGETS), 28)
        self.assertEqual(sum(1 for t in m.TARGETS if t[2]), 7)
        self.assertIn(m.CONTROL, [t[0] for t in m.TARGETS])
        for v, notice, _ in m.TARGETS:
            self.assertEqual(m.cd_of(v), m.cd_of(notice))


if __name__ == "__main__":
    unittest.main()
