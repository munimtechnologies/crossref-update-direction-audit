# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Offline unit tests for pt_correction_audit.py (no network)."""
import datetime
import unittest

import pt_correction_audit as A

D = datetime.date


def item(doi, y, m, vol, iss, created="2007-03-13T10:51:18Z", targets=(), issn=("0031-9228",),
         title="Corrections", container="Physics Today"):
    return {"DOI": doi, "issued": {"date-parts": [[y, m, 1]] if m else [[y]]},
            "created": {"date-time": created}, "volume": vol, "issue": iss,
            "title": [title], "ISSN": list(issn), "container-title": [container],
            "update-to": [{"DOI": t, "type": "correction"} for t in targets],
            "is-referenced-by-count": 2, "page": "77-77"}


class Helpers(unittest.TestCase):
    def test_date_range_month(self):
        self.assertEqual(A.date_range([2000, 7, 1]), (D(2000, 7, 1), D(2000, 7, 1)))
        self.assertEqual(A.date_range([2000, 7]), (D(2000, 7, 1), D(2000, 7, 31)))
        self.assertEqual(A.date_range([2000]), (D(2000, 1, 1), D(2000, 12, 31)))
        self.assertIsNone(A.date_range([]))

    def test_created(self):
        self.assertEqual(A.created_date({"created": {"date-time": "2007-03-13T10:51:18Z"}}),
                         D(2007, 3, 13))
        self.assertIsNone(A.created_date({}))

    def test_strict_int_and_vol_issue(self):
        self.assertEqual(A.strict_int("53"), 53)
        self.assertIsNone(A.strict_int("S1"))
        self.assertIsNone(A.strict_int("5-6"))
        self.assertEqual(A.vol_issue({"volume": "53", "issue": "7"}), (53, 7))
        self.assertIsNone(A.vol_issue({"volume": "53"}))

    def test_later_vi(self):
        self.assertTrue(A.later_vi((53, 7), (53, 12)))
        self.assertTrue(A.later_vi((52, 12), (53, 1)))
        self.assertFalse(A.later_vi((53, 7), (53, 7)))
        self.assertFalse(A.later_vi((53, 7), (52, 12)))
        self.assertIsNone(A.later_vi(None, (53, 1)))

    def test_later_date(self):
        jul = (D(2000, 7, 1), D(2000, 7, 31))
        aug = (D(2000, 8, 1), D(2000, 8, 31))
        self.assertTrue(A.later_date(jul, aug))
        self.assertFalse(A.later_date(jul, aug, 31))
        self.assertFalse(A.later_date(aug, jul))
        self.assertIsNone(A.later_date(None, jul))

    def test_is_pt(self):
        self.assertTrue(A.is_pt({"ISSN": ["1945-0699"]}))
        self.assertTrue(A.is_pt({"container-title": ["Physics Today"]}))
        self.assertFalse(A.is_pt({"ISSN": ["0021-8979"], "container-title": ["J. Appl. Phys."]}))

    def test_era(self):
        jul2000 = (D(2000, 7, 1), D(2000, 7, 31))
        self.assertEqual(A.era(jul2000, D(2007, 3, 13)), "backfile")
        nov2009 = (D(2009, 11, 1), D(2009, 11, 30))
        self.assertEqual(A.era(nov2009, D(2009, 11, 2)), "contemporaneous")
        jan2006 = (D(2006, 1, 1), D(2006, 1, 31))
        self.assertEqual(A.era(jan2006, D(2007, 3, 13)), "other")
        self.assertEqual(A.era(None, D(2007, 3, 13)), "unknown")

    def test_rec_dedupes_targets(self):
        r = A.rec(item("10.1063/N", 2000, 7, "53", "7", targets=("10.1063/A", "10.1063/a",
                                                                   "10.1063/B")))
        self.assertEqual([t for t, _ in r["targets"]], ["10.1063/a", "10.1063/b"])
        self.assertEqual(r["doi"], "10.1063/n")
        self.assertEqual(r["vi"], (53, 7))
        self.assertTrue(r["pt"])

    def test_clean_text(self):
        self.assertEqual(A.clean_text("<i>New</i>  Books &amp; more"), "New Books & more")

    def test_batch_url(self):
        u = A.batch_url(["10.1063/1.1", "10.1063/1.2"], 7)
        self.assertIn("filter=doi:10.1063/1.1,doi:10.1063/1.2", u)
        self.assertIn("rows=7", u)
        self.assertFalse(A.batchable("10.1/a,b"))


def fixture():
    """A July 2000 back-file notice with targets: later (Dec), earlier (May), same issue,
    itself, missing, a non-PT target; a 2009 contemporaneous notice with one earlier target;
    a Jan 2000 back-file notice sharing target 10.1063/may."""
    notices = [A.rec(item("10.1063/jul", 2000, 7, "53", "7",
                          targets=("10.1063/dec", "10.1063/may", "10.1063/jul2", "10.1063/jul",
                                   "10.1063/gone", "10.1063/jap"))),
               A.rec(item("10.1063/c09", 2009, 11, "62", "11", created="2009-11-02T18:02:24Z",
                          targets=("10.1063/sep09",))),
               A.rec(item("10.1063/jan", 2000, 1, "53", "1", targets=("10.1063/may",)))]
    targets = {d: A.rec(it) for d, it in {
        "10.1063/dec": item("10.1063/dec", 2000, 12, "53", "12", title="Lights out at LEP"),
        "10.1063/may": item("10.1063/may", 2000, 5, "53", "5", title="Chandra"),
        "10.1063/jul2": item("10.1063/jul2", 2000, 7, "53", "7", title="Ins & Outs"),
        "10.1063/sep09": item("10.1063/sep09", 2009, 9, "62", "9", title="X"),
        "10.1063/jap": item("10.1063/jap", 2000, 9, "88", "6", issn=("0021-8979",),
                            container="Journal of Applied Physics", title="Y"),
    }.items()}
    return notices, targets


class Relations(unittest.TestCase):
    def test_classify(self):
        notices, targets = fixture()
        rels = A.build_relations(notices, targets)
        got = {(r["notice"], r["target"]): r["cls"] for r in rels}
        self.assertEqual(got[("10.1063/jul", "10.1063/dec")], "later")
        self.assertEqual(got[("10.1063/jul", "10.1063/may")], "earlier")
        self.assertEqual(got[("10.1063/jul", "10.1063/jul2")], "same_issue")
        self.assertEqual(got[("10.1063/jul", "10.1063/jul")], "self")
        self.assertEqual(got[("10.1063/jul", "10.1063/gone")], "missing")
        self.assertEqual(got[("10.1063/jul", "10.1063/jap")], "not_pt")
        self.assertEqual(got[("10.1063/c09", "10.1063/sep09")], "earlier")
        self.assertEqual(got[("10.1063/jan", "10.1063/may")], "later")
        listing = {(r["notice"], r["target"]): r["n_listing"] for r in rels}
        self.assertEqual(listing[("10.1063/jul", "10.1063/may")], 2)
        self.assertEqual(listing[("10.1063/jul", "10.1063/dec")], 1)

    def test_classify_date_fallback(self):
        n = A.rec(item("10.1063/n", 1990, 3, "43", "", targets=("10.1063/t",)))
        t = A.rec(item("10.1063/t", 1990, 6, "43", "6"))
        self.assertEqual(A.classify(n, t, "10.1063/t"), "later")
        t2 = A.rec(item("10.1063/t", 1990, 3, "43", ""))
        self.assertEqual(A.classify(n, t2, "10.1063/t"), "same_issue")
        t3 = A.rec(item("10.1063/t", 1989, 11, "", ""))
        self.assertEqual(A.classify(n, t3, "10.1063/t"), "earlier")

    def test_pt_stats(self):
        notices, targets = fixture()
        rels = A.build_relations(notices, targets)
        s = A.pt_stats(notices, rels)
        self.assertEqual(s["n_notices"], 3)
        self.assertEqual(s["n_relations"], 8)
        self.assertEqual(s["notices_by_era"], {"backfile": 2, "contemporaneous": 1})
        self.assertAlmostEqual(s["back_mean_targets"], 3.5)
        self.assertEqual(s["contemp_mean_targets"], 1.0)
        self.assertEqual(s["n_self"], 1)
        self.assertEqual(s["n_later"], 2)
        self.assertEqual(s["n_later_vi_def"], 2)
        self.assertEqual(s["n_later_both"], 2)
        self.assertEqual(s["back_rel_judged"], 4)
        self.assertEqual(s["back_later"], 2)
        self.assertEqual(s["contemp_later"], 0)
        self.assertEqual(s["back_notices3"], 1)
        self.assertEqual(s["back_notices3_with_later"], 1)
        self.assertEqual(s["back_distinct_targets"], 5)
        self.assertEqual(s["back_shared_targets"], 1)
        self.assertEqual((s["h1_n"], s["h1_later"]), (1, 1))
        self.assertEqual((s["h2_n"], s["h2_later"]), (3, 1))
        self.assertEqual(s["distinct_targets"], 6)
        self.assertEqual(s["distinct_targets_found"], 5)
        self.assertEqual(s["items_only_later"], 1)
        self.assertEqual(s["items_judged"], 4)

    def test_aip_stats(self):
        n = A.rec(item("10.1063/e1", 2001, 1, "89", "1", issn=("0021-8979",),
                       container="Journal of Applied Physics", created="2001-01-05T00:00:00Z",
                       targets=("10.1063/t1", "10.1063/t2", "10.1063/e1")))
        t1 = A.rec(item("10.1063/t1", 2000, 6, "87", "11", issn=("0021-8979",)))
        t2 = A.rec(item("10.1063/t2", 2001, 4, "89", "7", issn=("0021-8979",)))
        s, table = A.aip_stats([n], {"10.1063/t1": t1, "10.1063/t2": t2})
        self.assertEqual(s["aip_other_judged"], 2)
        self.assertEqual(s["aip_other_later"], 1)
        self.assertEqual(table[("Journal of Applied Physics", "contemporaneous")], [2, 1])


class Predictions(unittest.TestCase):
    def base(self):
        return {"complete": True, "n_notices": 278, "target_coverage": 0.99,
                "n_contemp_notices": 40, "contemp_later": 0, "contemp_mean_targets": 1.0,
                "back_mean_targets": 4.0, "back_rel_judged": 1000, "back_later": 350,
                "back_notices3": 100, "back_notices3_with_later": 70,
                "back_distinct_targets": 900, "back_shared_targets": 60,
                "h1_n": 500, "h1_later": 250, "h2_n": 500, "h2_later": 100,
                "aip_complete": True, "aip_other_judged": 8000, "aip_other_later": 20,
                "n_later_vi_def": 300}

    def test_all_hold(self):
        p = A.compute_predictions(self.base())
        self.assertEqual(set(p.values()), {True})

    def test_failures_and_nones(self):
        s = self.base()
        s.update(n_notices=200, contemp_later=2, back_mean_targets=2.9, back_later=299,
                 back_notices3_with_later=59, back_shared_targets=44, h2_later=200,
                 aip_other_later=81, n_later_vi_def=249)
        p = A.compute_predictions(s)
        self.assertEqual(set(p.values()), {False})
        s = self.base()
        s.update(n_contemp_notices=9, h1_n=29, aip_complete=False)
        p = A.compute_predictions(s)
        self.assertIsNone(p["P2"])
        self.assertIsNone(p["P7"])
        self.assertIsNone(p["P8"])


if __name__ == "__main__":
    unittest.main()
