# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Offline tests for cochrane_withdrawal_rw_audit.py (no network)."""
import datetime
import io
import unittest

import cochrane_withdrawal_rw_audit as m

D = datetime.date
P = "10.1002/14651858."


class Helpers(unittest.TestCase):
    def test_cd_and_kind(self):
        self.assertEqual(m.cd_id("10.1002/14651858.CD012271.pub2"), "cd012271")
        self.assertEqual(m.target_kind("10.1002/14651858.CD012271.pub2"), "review")
        self.assertEqual(m.target_kind("https://doi.org/10.1002/14651858.cd012271"), "bare")
        self.assertEqual(m.target_kind("10.1016/j.x.2020.1"), "other")

    def test_dates(self):
        self.assertEqual(m.date_from_parts({"date-parts": [[2021, 11, 30]]}), D(2021, 11, 30))
        self.assertEqual(m.date_from_parts({"date-parts": [[2020]]}), D(2020, 1, 1))
        self.assertIsNone(m.date_from_parts(None))
        self.assertEqual(m.parse_rw_date("11/30/2021 0:00"), D(2021, 11, 30))
        self.assertEqual(m.parse_rw_date("2021-11-30"), D(2021, 11, 30))
        self.assertIsNone(m.parse_rw_date(""))
        self.assertIsNone(m.parse_rw_date("13/45/2020 0:00"))
        self.assertEqual(m.period(D(2019, 7, 1)), "post")
        self.assertEqual(m.period(D(2019, 6, 30)), "pre")
        self.assertEqual(m.period(D(2005, 1, 1)), "early")
        self.assertEqual(m.period(None), "undated")

    def test_reason(self):
        self.assertEqual(m.reason_class("Errors were identified in the data extraction process"),
                         "integrity")
        self.assertEqual(m.reason_class("it has been superceded by the Cochrane Review of Competitions"),
                         "currency")
        self.assertEqual(m.reason_class("it does not include recent evidence and does not reflect "
                                        "up-to-date Cochrane methodological standards"), "currency")
        self.assertEqual(m.reason_class("The Cochrane review is out of date and included a retracted "
                                        "article in the analysis."), "integrity")
        self.assertEqual(m.reason_class("Serious breach of Cochrane's conflict of interest policy."),
                         "integrity")
        self.assertEqual(m.reason_class("The authors requested it"), "other")
        self.assertEqual(m.reason_class(""), "no_text")

    def test_reason_sentence(self):
        a = ("<p>Background text here. This review has been withdrawn. Errors were identified in "
             "the data. More.</p>")
        r = m.reason_sentence(a)
        self.assertTrue(r.startswith("This review has been withdrawn."))
        self.assertIn("Errors were identified", r)
        self.assertEqual(m.reason_sentence(""), "")


ITEMS = [
    {"DOI": "10.1002/14651858.CD006581.pub3", "issued": {"date-parts": [[2015, 5, 20]]},
     "update-to": [
         {"DOI": P + "cd006581", "type": "retraction", "source": "retraction-watch",
          "record-id": 32233, "updated": {"date-parts": [[2015, 5, 20]]}},
         {"DOI": P + "cd006581.pub2", "type": "retraction", "source": "retraction-watch",
          "record-id": 32229, "updated": {"date-parts": [[2015, 5, 20]]}},
         {"DOI": P + "cd006581.pub2", "type": "withdrawal", "source": "publisher",
          "updated": {"date-parts": [[2015, 5, 20]]}}]},
    {"DOI": P + "cd012271.pub3", "issued": {"date-parts": [[2020, 3, 25]]},
     "update-to": [{"DOI": P + "cd012271.pub2", "type": "withdrawal", "source": "publisher",
                    "updated": {"date-parts": [[2020, 3, 25]]}}]},
    {"DOI": "10.1016/j.x.1",
     "update-to": [{"DOI": "10.1016/j.x.1", "type": "withdrawal", "source": "publisher"}]},
]


class Events(unittest.TestCase):
    def test_collapse(self):
        raw = m.events_from_items(ITEMS + ITEMS[:1])
        events, xr = m.collapse(raw)
        self.assertEqual([e["target"] for e in events], [P + "cd006581.pub2", P + "cd012271.pub2"])
        self.assertEqual(xr, {P + "cd006581", P + "cd006581.pub2"})
        self.assertEqual(events[0]["kind"], "review")
        self.assertEqual(events[0]["notices"], P + "cd006581.pub3")
        self.assertEqual(events[1]["date"], D(2020, 3, 25))
        self.assertEqual(events[1]["cd"], "cd012271")


CSV = ("Record ID,Title,Journal,RetractionDate,RetractionDOI,OriginalPaperDOI,RetractionNature,Reason\n"
       "25814,Yttrium,Cochrane Database of Systematic Reviews,11/16/2020 0:00,"
       "10.1002/14651858.CD011313.pub4,10.1002/14651858.CD011313.pub3,Retraction,+Withdrawal;\n"
       "1,Other,Journal X,1/1/2020 0:00,10.1/x,10.1/y,Retraction,\n"
       "2,Cochrane old,Cochrane Database of Systematic Reviews,6/1/2012 0:00,unavailable,"
       "10.1002/14651858.CD000001.pub2,Retraction,\n"
       "3,Corr,Cochrane Database of Systematic Reviews,6/1/2021 0:00,,"
       "10.1002/14651858.CD000002.pub2,Correction,\n")


class RW(unittest.TestCase):
    def setUp(self):
        self.by_doi, self.by_cd, self.st = m.rw_index(io.StringIO(CSV))

    def test_index(self):
        self.assertEqual(self.st["rows"], 4)
        self.assertEqual(self.st["cochrane_rows"], 3)
        self.assertEqual(self.st["header_ok"], 1)

    def test_match(self):
        a = m.match({"target": P + "cd011313.pub3", "cd": "cd011313", "date": D(2020, 11, 16)},
                    self.by_doi, self.by_cd)
        self.assertTrue(a["rw_exact"])
        self.assertTrue(a["rw_near"])
        self.assertEqual(a["rw_ids"], "25814")
        b = m.match({"target": P + "cd000001.pub3", "cd": "cd000001", "date": D(2020, 6, 1)},
                    self.by_doi, self.by_cd)
        self.assertFalse(b["rw_exact"])
        self.assertFalse(b["rw_near"])
        c = m.match({"target": P + "cd000001.pub3", "cd": "cd000001", "date": D(2012, 9, 1)},
                    self.by_doi, self.by_cd)
        self.assertFalse(c["rw_exact"])
        self.assertTrue(c["rw_near"])
        d = m.match({"target": P + "cd000002.pub2", "cd": "cd000002", "date": D(2021, 6, 1)},
                    self.by_doi, self.by_cd)
        self.assertFalse(d["rw_exact"])
        self.assertFalse(d["rw_near"])


class Parse(unittest.TestCase):
    def test_epmc(self):
        obj = {"resultList": {"result": [
            {"doi": "10.1002/14651858.CD012271.PUB3", "pmid": "32212387",
             "pubTypeList": {"pubType": ["Retraction of Publication", "Review"]},
             "abstractText": "Serious breach."}]}}
        r = m.parse_epmc(obj, P + "cd012271.pub3")
        self.assertTrue(r["found"])
        self.assertEqual(r["pmid"], "32212387")
        self.assertEqual(r["pubtypes"], "Retraction of Publication;Review")
        self.assertFalse(m.parse_epmc({}, P + "cd1")["found"])


class Grade(unittest.TestCase):
    def test_grade(self):
        post = [{"period": "post", "kind": "review", "rw_exact": i == 0, "rw_near": i == 0,
                 "epmc_found": True, "reason_class": "integrity" if i < 4 else "currency"}
                for i in range(19)]
        res = m.grade(post, post, {"g": {"ok": True}})
        self.assertIs(res["P1"]["held"], True)
        self.assertIs(res["P2"]["held"], True)
        self.assertIs(res["P3"]["held"], True)
        self.assertIsNone(res["P4"]["held"])
        self.assertIsNone(res["P5"]["held"])
        self.assertIs(res["P6"]["held"], True)


if __name__ == "__main__":
    unittest.main()
