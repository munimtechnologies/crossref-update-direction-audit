# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Offline tests for rw_doi_registration_census.py (audit 14). No network."""
import io
import json
import unittest

import rw_doi_registration_census as m


def E(side, status, ra="", repair="", rc="", rdate="2020-01-01"):
    return {"side": side, "status": status, "ra": ra, "repair": repair, "repair_class": rc,
            "rdate": rdate}


class HelperTests(unittest.TestCase):
    def test_parse_doi_field(self):
        self.assertEqual(m.parse_doi_field(""), ("", "none", False))
        self.assertEqual(m.parse_doi_field("Unavailable"), ("", "none", False))
        self.assertEqual(m.parse_doi_field(None), ("", "none", False))
        self.assertEqual(m.parse_doi_field("10.1097/IGC.0b013e318218730e"),
                         ("10.1097/igc.0b013e318218730e", "ok", False))
        self.assertEqual(m.parse_doi_field("https://doi.org/10.1000/ABC"),
                         ("10.1000/abc", "ok", False))
        self.assertEqual(m.parse_doi_field("10.1000/a; 10.2000/b"), ("10.1000/a", "ok", True))
        self.assertEqual(m.parse_doi_field("PMID 1234"), ("pmid 1234", "malformed", False))
        self.assertEqual(m.parse_doi_field("10.1000/a."), ("10.1000/a.", "ok", False))

    def test_parse_date(self):
        self.assertEqual(m.parse_date("3/1/2023 0:00"), "2023-03-01")
        self.assertEqual(m.parse_date("6/24/1756 12:00:00 AM"), "1756-06-24")
        self.assertEqual(m.parse_date("2026-10-05"), "2026-10-05")
        self.assertEqual(m.parse_date(""), "")
        self.assertEqual(m.days_before("2026-11-12", 60), "2026-09-13")

    def test_lev(self):
        self.assertEqual(m.lev("kitten", "sitting"), 3)
        self.assertEqual(m.lev("abc", "abc"), 0)
        self.assertEqual(m.lev("a", "abcdef", 2), 3)
        self.assertEqual(m.lev("2018", "2023"), 2)

    def test_cleanups(self):
        self.assertEqual(m.cleanups("10.1080/09645292.2010.545518#.us5z4lssxk0"),
                         ["10.1080/09645292.2010.545518"])
        self.assertEqual(m.cleanups("10.1016/j.x.2020.01.001."), ["10.1016/j.x.2020.01.001"])
        self.assertEqual(m.cleanups("10.1002/abc.123/full"), ["10.1002/abc.123"])
        self.assertEqual(m.cleanups("doi.org/10.1000/xyz"), ["10.1000/xyz"])
        self.assertEqual(m.cleanups("10.1000/abc (retracted)"),
                         ["10.1000/abc(retracted)", "10.1000/abc"])
        self.assertEqual(m.cleanups("10.1000/(sici)1&lt;2::aid&gt;3.0.co;2-#"),
                         ["10.1000/(sici)1<2::aid>3.0.co;2-#"])
        self.assertEqual(m.cleanups("10.1000/abc"), [])
        self.assertEqual(m.cleanups("pmid 1234"), [])

    def test_relation(self):
        self.assertEqual(m.relation("10.1177/014616720026200", "10.1177/0146167200262008"),
                         "truncated")
        self.assertEqual(m.relation("10.1000/abc.x1", "10.1000/abc"), "extra_chars")
        self.assertEqual(m.relation("10.1080/16484142.2012.725632",
                                    "10.3846/16484142.2012.725632"), "prefix_swap")
        self.assertEqual(m.relation("10.18388/abp.2018_6398", "10.18388/abp.2023_6398"), "typo")
        self.assertEqual(m.relation("10.26355/eurrev_202101_24355", "10.1097/md.0000000000033332"),
                         "")
        self.assertEqual(m.relation("10.1000/a", "10.1000/a"), "")

    def test_pick(self):
        items = [("10.1177/0146167200262008", "Some title words here"),
                 ("10.1177/01461672231179476", "Other paper entirely")]
        st, hits = m.pick("10.1177/014616720026200", items, "Some Title Words Here")
        self.assertEqual(st, "repaired")
        self.assertEqual(hits[0][0], "10.1177/0146167200262008")
        self.assertEqual(hits[0][1], "truncated")
        self.assertEqual(hits[0][2], 1.0)
        coch = [("10.1002/14651858.cd006698.pub2", "Drug for disease"),
                ("10.1002/14651858.cd006698.pub3", "Drug for disease")]
        st, hits = m.pick("10.1002/14651858.cd006698.pub", coch, "Drug for disease")
        self.assertEqual(st, "ambiguous")
        self.assertEqual(len(hits), 2)
        st, _ = m.pick("10.1177/014616720026200", items, "Some title words here",
                       exclude={"10.1177/0146167200262008"})
        self.assertEqual(st, "unrepaired")
        st, _ = m.pick("10.1177/014616720026200", items, "Completely different heading text")
        self.assertEqual(st, "unrepaired")
        st, _ = m.pick("10.1000/x", None, "anything")
        self.assertEqual(st, "unrepaired")

    def test_notice_title_jaccard(self):
        j = m.jaccard("Some title words here", "Retraction notice to “Some title words here”")
        self.assertAlmostEqual(j, 0.8)

    def test_ra_parse(self):
        b = ["10.1016/j.ajp.2020.102052", "10.1177/014616720026200", "notadoi"]
        obj = [{"DOI": "10.1016/j.ajp.2020.102052", "RA": "Crossref"},
               {"DOI": "10.1177/014616720026200", "status": "DOI does not exist"},
               {"DOI": "notadoi", "status": "Invalid DOI"}]
        self.assertEqual(m.ra_parse(b, obj), {"10.1016/j.ajp.2020.102052": ("registered", "Crossref"),
                                              "10.1177/014616720026200": ("not_exist", ""),
                                              "notadoi": ("invalid", "")})
        self.assertIsNone(m.ra_parse(b, {"error": 1}))
        self.assertIsNone(m.ra_parse(b, obj[:2]))
        self.assertIsNone(m.ra_parse(b, None))
        up = [{"DOI": "10.1000/ABC", "RA": "mEDRA"}]
        self.assertEqual(m.ra_parse(["10.1000/abc"], up), {"10.1000/abc": ("registered", "mEDRA")})


class EntriesTests(unittest.TestCase):
    def test_rw_entries(self):
        text = ("Record ID,Title,Journal,Publisher,RetractionDate,RetractionDOI,"
                "OriginalPaperDOI,RetractionNature\n"
                "1,Paper one,J,P,3/1/2023 0:00,10.1000/n1,10.1000/P1,Retraction\n"
                "2,Paper one again,J,P,4/1/2024 0:00,unavailable,10.1000/p1,Retraction\n"
                "3,Paper three,J,P,,,,Correction\n"
                "4,Paper four,J,P,1/2/2020 0:00,PMID 55,10.1000/a; 10.2000/b,Retraction\n")
        ents, st = m.rw_entries(io.StringIO(text))
        self.assertEqual(st["rows"], 4)
        self.assertEqual(st["header_ok"], 1)
        self.assertEqual(st["rows_no_doi"], 1)
        self.assertEqual(st["O_ok"], 3)
        self.assertEqual(st["O_none"], 1)
        self.assertEqual(st["O_multi"], 1)
        self.assertEqual(st["N_none"], 2)
        self.assertEqual(st["N_malformed"], 1)
        self.assertEqual(set(ents), {("O", "10.1000/p1"), ("N", "10.1000/n1"), ("O", "10.1000/a"),
                                     ("N", "pmid 55")})
        p1 = ents[("O", "10.1000/p1")]
        self.assertEqual(p1["n_rows"], 2)
        self.assertEqual(p1["record_ids"], ["1", "2"])
        self.assertEqual(p1["rdate"], "2024-04-01")
        self.assertEqual(p1["other_doi"], "10.1000/n1")
        self.assertEqual(p1["raw"], "10.1000/P1")
        self.assertEqual(ents[("N", "pmid 55")]["syntax"], "malformed")

    def test_controls(self):
        ents = {("O", "10.1177/014616720026200"): {"doi": "10.1177/014616720026200",
                                                   "status": "not_exist"},
                ("O", "10.26355/eurrev_202101_24355"): {"doi": "10.26355/eurrev_202101_24355",
                                                        "status": "registered", "ra": "mEDRA"}}
        c = m.check_controls(ents)
        self.assertTrue(c["10.1177/014616720026200"]["ok"])
        self.assertTrue(c["10.26355/eurrev_202101_24355"]["ok"])
        self.assertFalse(c["10.18388/abp.2018_6398"]["ok"])


class GradeTests(unittest.TestCase):
    G = {"G": {"ok": True}}

    def test_grade_rates(self):
        ev = ([E("O", "registered", "Crossref")] * 989 + [E("O", "registered", "mEDRA")] * 6
              + [E("O", "not_exist")] * 5 + [E("N", "registered", "Crossref")] * 190
              + [E("N", "not_exist")] * 10)
        g = m.grade(ev, "2026-11-12", self.G)
        self.assertEqual(g["P1"]["value"], 0.005)
        self.assertTrue(g["P1"]["held"])
        self.assertEqual(g["P2"]["value"], [0.05, 0.005])
        self.assertTrue(g["P2"]["held"])
        self.assertIsNone(g["P3"]["held"])
        self.assertIsNone(g["P4"]["held"])
        self.assertIsNone(g["P5"]["held"])
        self.assertEqual(g["P6"]["value"], 0.006)
        self.assertTrue(g["P6"]["held"])

    def test_grade_repairs(self):
        ev = ([E("O", "registered", "Crossref")] * 960
              + [E("O", "not_exist", repair="repaired", rc="truncated")] * 20
              + [E("O", "not_exist", repair="cleanup", rc="cleanup")] * 10
              + [E("O", "not_exist", repair="unrepaired")] * 10)
        g = m.grade(ev, "2026-11-12", self.G)
        self.assertEqual(g["P1"]["value"], 0.04)
        self.assertFalse(g["P1"]["held"])
        self.assertFalse(g["P2"]["held"])
        self.assertEqual(g["P4"]["value"], 0.75)
        self.assertTrue(g["P4"]["held"])
        self.assertEqual(g["P5"]["value"], {"truncated": 20, "cleanup": 10})
        self.assertTrue(g["P5"]["held"])
        self.assertEqual(g["P6"]["value"], 0.0)
        self.assertFalse(g["P6"]["held"])

    def test_grade_recent(self):
        ev = ([E("N", "registered", "Crossref", rdate="2026-11-01")] * 180
              + [E("N", "not_exist", rdate="2026-11-01")] * 20
              + [E("N", "registered", "Crossref")] * 990 + [E("N", "not_exist")] * 10
              + [E("O", "registered", "Crossref")] * 10)
        g = m.grade(ev, "2026-11-12", self.G)
        self.assertEqual(g["P3"]["value"], [0.1, 0.01])
        self.assertTrue(g["P3"]["held"])

    def test_gate_note(self):
        g = m.grade([E("O", "registered", "Crossref")], "2026-11-12", {"G": {"ok": False}})
        self.assertIn("a gate failed", g["P1"]["note"])


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.orig = m.http

    def tearDown(self):
        m.http = self.orig

    def test_lookup_batch_and_single(self):
        calls = []

        def fake(url, **kw):
            calls.append(url)
            if url == m.DOIRA + "10.1000/a,10.1000/b":
                return 200, json.dumps([{"DOI": "10.1000/a", "RA": "Crossref"},
                                        {"DOI": "10.1000/b", "status": "DOI does not exist"}]
                                       ).encode("utf-8")
            if url == m.DOIRA + "10.1000/a%23x":
                return 200, b'[{"DOI": "10.1000/a#x", "status": "DOI does not exist"}]'
            return 500, b""

        m.http = fake
        res = {}
        failed = m.lookup(["10.1000/a", "10.1000/b", "10.1000/a#x"], res)
        self.assertEqual(failed, 0)
        self.assertEqual(res, {"10.1000/a": ("registered", "Crossref"),
                               "10.1000/b": ("not_exist", ""),
                               "10.1000/a#x": ("not_exist", "")})
        self.assertEqual(len(calls), 2)

    def test_lookup_fallback(self):
        def fake(url, **kw):
            if url.startswith(m.HANDLE):
                return 404, b""
            return 500, b""

        m.http = fake
        res = {}
        failed = m.lookup(["10.1000/a", "10.1000/b"], res)
        self.assertEqual(failed, 4)
        self.assertEqual(res, {"10.1000/a": ("not_exist", ""), "10.1000/b": ("not_exist", "")})


if __name__ == "__main__":
    unittest.main()
