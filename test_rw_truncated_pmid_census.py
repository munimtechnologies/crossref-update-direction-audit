# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Offline tests for rw_truncated_pmid_census.py (audit 12). No network."""
import io
import unittest

import rw_truncated_pmid_census as m


def rec(pmid, doi="", title="", refs=()):
    return {"pmid": pmid, "doi": doi, "title": title, "pubtype": [], "refs": list(refs)}


def side(side, pmid, o="", n="", o_doi="", n_doi="", title="", record_id="1", o_year=None):
    return {"side": side, "pmid": pmid, "o": o, "n": n, "o_doi": o_doi, "n_doi": n_doi,
            "title": title, "record_id": record_id, "o_year": o_year, "nature": "Retraction",
            "journal": "", "publisher": ""}


class HelperTests(unittest.TestCase):
    def test_parse_pmid(self):
        self.assertEqual(m.parse_pmid("21633303"), ("21633303", "ok"))
        self.assertEqual(m.parse_pmid("2163330.0"), ("2163330", "ok"))
        self.assertEqual(m.parse_pmid("0"), ("", "none"))
        self.assertEqual(m.parse_pmid(""), ("", "none"))
        self.assertEqual(m.parse_pmid("abc"), ("", "malformed"))

    def test_candidates(self):
        c = m.candidates("2163330")
        self.assertEqual(len(c), 10)
        self.assertEqual(c[0], "21633300")
        self.assertIn("21633303", c)
        c6 = m.candidates("279942")
        self.assertEqual(len(c6), 110)
        self.assertIn("2799420", c6)
        self.assertIn("27994246", c6)
        self.assertEqual(m.candidates("21633303"), [])

    def test_year_of(self):
        self.assertEqual(m.year_of("3/1/2023 0:00"), 2023)
        self.assertEqual(m.year_of("12/18/1998 0:00"), 1998)
        self.assertIsNone(m.year_of(""))

    def test_rw_sides(self):
        text = ("Record ID,Title,OriginalPaperPubMedID,RetractionPubMedID,OriginalPaperDOI,"
                "RetractionDOI,RetractionNature,OriginalPaperDate\n"
                "2154,Effects of bufalin,2163330,25902282,10.1097/IGC.0b013e318218730e,"
                "10.1097/igc.0000000000000425,Retraction,8/1/2011 0:00\n"
                "9,Other paper,0,,unavailable,,Correction,\n")
        sides, st = m.rw_sides(io.StringIO(text))
        self.assertEqual(st["rows"], 2)
        self.assertEqual(st["header_ok"], 1)
        self.assertEqual(len(sides), 2)
        self.assertEqual(sides[0]["side"], "O")
        self.assertEqual(sides[0]["o_doi"], "10.1097/igc.0b013e318218730e")
        self.assertEqual(sides[0]["o_year"], 2011)
        self.assertEqual(sides[1]["side"], "N")
        self.assertEqual(st["O_none"], 1)
        self.assertEqual(st["N_none"], 1)


class JudgeTests(unittest.TestCase):
    def setUp(self):
        # Paper-side truncation, as in RW record 2154.
        self.recs = {
            "2163330": rec("2163330", "10.1538/expanim1978.39.2_223",
                           "Virucidal effect of ozone treatment of laboratory animal viruses."),
            "21633303": rec("21633303", "10.1097/igc.0b013e318218730e",
                            "Effects of bufalin on the proliferation of human choriocarcinoma cells.",
                            [("retraction in", "25902282", "10.1097/igc.0000000000000425")]),
            "25902282": rec("25902282", "10.1097/igc.0000000000000425", "Retraction.",
                            [("retraction of", "21633303", "10.1097/igc.0b013e318218730e")]),
        }
        self.o = side("O", "2163330", o="2163330", n="25902282",
                      o_doi="10.1097/igc.0b013e318218730e", n_doi="10.1097/igc.0000000000000425",
                      title="Effects of bufalin on the proliferation of human choriocarcinoma cells",
                      record_id="2154", o_year=2011)
        self.n = dict(self.o, side="N", pmid="25902282")

    def test_fit_by_doi(self):
        self.assertEqual(m.judge(self.n, self.recs)["status"], "fit")
        self.assertEqual(m.judge(self.n, self.recs)["evidence"], "doi")

    def test_paper_side_truncation_by_doi(self):
        self.assertTrue(m.needs_candidates(self.o, self.recs))
        j = m.judge(self.o, self.recs)
        self.assertEqual((j["status"], j["fix"], j["evidence"]), ("truncated", "21633303", "doi"))

    def test_notice_side_truncation_by_link(self):
        recs = {
            "9549743": rec("9549743", "10.1046/j.1460-9592.1998.00761.x", "Prophylactic granisetron",
                           [("retraction in", "23289124", "")]),
            "2328912": rec("2328912", "10.1016/0378-1097(90)90173-n", "Chromate-resistance"),
            "23289124": rec("23289124", "", "Retraction. Prophylactic granisetron",
                            [("retraction of", "9549743", "")]),
        }
        s = side("N", "2328912", o="9549743", n="2328912",
                 o_doi="10.1046/j.1460-9592.1998.00761.x", n_doi="10.1111/pan.12063",
                 title="Prophylactic therapy with granisetron", record_id="475")
        j = m.judge(s, recs)
        self.assertEqual((j["status"], j["fix"], j["evidence"]), ("truncated", "23289124", "link"))
        self.assertEqual(m.judge(dict(s, side="O", pmid="9549743"), recs)["status"], "fit")

    def test_missing_and_unfit_other(self):
        self.assertEqual(m.judge(side("O", "999", o="999", o_doi="10.1/x"), {})["status"], "missing")
        recs = {"12345678": rec("12345678", "10.1/other", "Something else entirely here")}
        s = side("O", "12345678", o="12345678", o_doi="10.1/x", title="A quite different title words")
        self.assertFalse(m.needs_candidates(s, recs))
        self.assertEqual(m.judge(s, recs)["status"], "unfit_other")

    def test_no_basis(self):
        recs = {"1234567": rec("1234567", "", "Unrelated")}
        s = side("N", "1234567", n="1234567")
        self.assertEqual(m.judge(s, recs)["status"], "no_basis")

    def test_ambiguous_and_title_only(self):
        recs = {"1234567": rec("1234567", "", "Unrelated old paper"),
                "12345671": rec("12345671", "10.1/x", "A"),
                "12345672": rec("12345672", "10.1/x", "B")}
        s = side("O", "1234567", o="1234567", o_doi="10.1/x", title="Alpha beta gamma delta")
        self.assertEqual(m.judge(s, recs)["status"], "ambiguous")
        recs = {"1234567": rec("1234567", "", "Unrelated old paper"),
                "12345675": rec("12345675", "", "Alpha beta gamma delta.")}
        s = side("O", "1234567", o="1234567", title="Alpha beta gamma delta")
        j = m.judge(s, recs)
        self.assertEqual((j["status"], j["fix"]), ("truncated_probable", "12345675"))

    def test_notice_doi_equal_to_paper_doi_is_not_a_link(self):
        recs = {"2437847": rec("2437847", "10.1111/old", "Platelet calcium",
                               [("x", "", "10.1007/s00267-013-0225-3")])}
        s = side("N", "2437847", n="2437847", o_doi="10.1007/s00267-013-0225-3",
                 n_doi="10.1007/s00267-013-0225-3")
        self.assertEqual(m.fit(s, recs["2437847"], recs), "")


class GradeTests(unittest.TestCase):
    def test_grade(self):
        sides = []
        for i in range(50):
            sides.append(dict(side("O", "1234567", record_id=str(100 + i), o_year=2005),
                              status="truncated", fix="12345670"))
        for i in range(5000):
            sides.append(dict(side("O", "22222222", record_id=str(20000 + i)),
                              status="fit", fix=""))
        for i in range(60):
            sides.append(dict(side("O", "33333333", record_id=str(30000 + i)),
                              status="unfit_other", fix=""))
        gates = {"G": {"ok": True}}
        r = m.grade(sides, gates)
        self.assertTrue(r["P1"]["held"])
        self.assertTrue(r["P2"]["held"])
        self.assertTrue(r["P3"]["held"])
        self.assertTrue(r["P4"]["held"])
        self.assertEqual(r["P4"]["value"], 1.0)
        self.assertTrue(r["P5"]["held"])
        self.assertTrue(r["P6"]["held"])
        r = m.grade(sides, {"G": {"ok": False}})
        self.assertIn("a gate failed", r["P1"]["note"])


if __name__ == "__main__":
    unittest.main()
