# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Unit tests for pubmed_link_audit.py (no network)."""
import unittest

import pubmed_link_audit as pa


def item(doi, title, updates, member="311", year=2024):
    return {"DOI": doi, "title": [title], "member": member, "publisher": "P" + member,
            "created": {"date-parts": [[year, 1, 1]]}, "container-title": ["J"],
            "update-to": [{"DOI": d, "type": t, "source": s} for d, t, s in updates]}


class TitleClass(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(pa.title_class("Correction to: Paper T1"), "correction")
        self.assertEqual(pa.title_class("Erratum"), "correction")
        self.assertEqual(pa.title_class("Retractions and Errata"), "mixed")
        self.assertEqual(pa.title_class("Correction to retraction of W"), "mixed")
        self.assertEqual(pa.title_class("Retraction notice to X"), "retraction")
        self.assertEqual(pa.title_class("Expression of Concern: Y"), "eoc")
        self.assertEqual(pa.title_class("Notice of Violation of IEEE Publication Principles: Z"),
                         "other")
        self.assertEqual(pa.title_class(""), "empty")


class Helpers(unittest.TestCase):
    def test_ref_doi(self):
        self.assertEqual(pa.ref_doi("Korean J Ophthalmol. 2023 Apr;37(2):200. "
                                    "doi: 10.3341/kjo.2022.0089.e1."), "10.3341/kjo.2022.0089.e1")
        self.assertEqual(pa.ref_doi("FASEB J. 2010 Feb;24(2):648"), "")
        self.assertEqual(pa.ref_doi("Lancet. 2020 Jun 13;395(10240):1820. "
                                    "doi: 10.1016/S0140-6736(20)31324-6."),
                         "10.1016/s0140-6736(20)31324-6")

    def test_safe_doi(self):
        self.assertTrue(pa.safe_doi("10.1016/S0140-6736(20)31180-6"))
        self.assertFalse(pa.safe_doi("10.1002/(sici)1097-0258(19990115)18:1<1::aid-sim1>3.0.co;2-x"))
        self.assertFalse(pa.safe_doi("10.1111/a b"))
        self.assertTrue(pa.safe_doi("https://doi.org/10.1111/X"))

    def test_esearch_term(self):
        self.assertEqual(pa.esearch_term(["10.1111/a", "10.1111/b"]),
                         "10.1111/a[doi] OR 10.1111/b[doi]")


class WalkerTest(unittest.TestCase):
    def test_walker(self):
        w = pa.Walker()
        a = item("10.1111/N1", "Correction to: Paper T1", [("10.1111/T1", "retraction", "publisher")])
        w.add(a)
        w.add(item("10.1111/N2", "Retraction: T2", [("10.1111/T2", "retraction", "publisher"),
                                                    ("10.1111/T2", "retraction", "retraction-watch")]))
        w.add(item("10.1111/S", "Retracted article", [("10.1111/S", "retraction", "publisher")]))
        w.add(item("10.1111/N3", "Erratum", [("10.1111/T3", "erratum", "publisher")]))
        w.add(a)  # seen again in a second walk: ignored
        w.add(item("10.1111/N4", "Withdrawn", [("10.1111/T4", "withdrawal", "publisher"),
                                               ("10.1111/T4", "withdrawal", "publisher")]))
        self.assertEqual(w.n_records, 5)
        self.assertEqual([(r["notice"], r["target"]) for r in w.rels],
                         [("10.1111/n1", "10.1111/t1"), ("10.1111/n2", "10.1111/t2"),
                          ("10.1111/n4", "10.1111/t4")])
        self.assertEqual(w.self_rels, 1)
        self.assertEqual(w.rw_retracted, {"10.1111/t2"})
        self.assertEqual(w.sources["publisher"], 5)
        self.assertEqual(w.sources["retraction-watch"], 1)
        self.assertEqual(w.rels[0]["title_class"], "correction")
        self.assertEqual(w.rels[2]["utype"], "withdrawal")


ESUMMARY = {"result": {
    "uids": ["1", "2", "3"],
    "1": {"uid": "1", "pubtype": ["Journal Article"],
          "articleids": [{"idtype": "pubmed", "value": "1"}, {"idtype": "doi", "value": "10.1111/T1"}],
          "references": [{"refsource": "J. 2023. doi: 10.1111/N1.", "reftype": "Erratum in",
                          "pmid": 11, "note": ""}]},
    "2": {"uid": "2", "pubtype": ["Journal Article", "Retracted Publication"],
          "articleids": [{"idtype": "doi", "value": "10.1111/T2"}],
          "references": [{"refsource": "J. 2020;5:1", "reftype": "Retraction in", "pmid": 22}]},
    "3": {"error": "cannot get document summary"}}}


class PubMed(unittest.TestCase):
    def setUp(self):
        self.pm = pa.parse_esummary(ESUMMARY)
        self.ra = {"notice": "10.1111/n1", "target": "10.1111/t1"}
        self.rb = {"notice": "10.1111/n2", "target": "10.1111/t2"}

    def test_parse(self):
        self.assertEqual(sorted(self.pm), ["10.1111/t1", "10.1111/t2"])
        self.assertEqual(self.pm["10.1111/t1"]["refs"],
                         [("erratum in", "11", "J. 2023. doi: 10.1111/N1.")])
        self.assertEqual(self.pm["10.1111/t2"]["pmid"], "2")

    def test_classify(self):
        t1, t2 = self.pm["10.1111/t1"], self.pm["10.1111/t2"]
        self.assertEqual(pa.classify(self.ra, t1, {}), "contradict")
        self.assertEqual(pa.classify(self.rb, t2, {"22": "10.1111/n2"}), "agree")
        self.assertEqual(pa.classify(self.rb, t2, {}), "pm_retracted_elsewhere")
        self.assertEqual(pa.classify(self.ra, None, {}), "not_in_pubmed")
        other = {"notice": "10.1111/n9", "target": "10.1111/t1"}
        self.assertEqual(pa.classify(other, t1, {}), "pm_corrected_only")
        empty = {"pmid": "9", "pubtype": [], "refs": [], "title": ""}
        self.assertEqual(pa.classify(self.ra, empty, {}), "pm_silent")
        both = {"pmid": "5", "pubtype": ["Retracted Publication"],
                "refs": [("erratum in", "11", "doi: 10.1111/N1")], "title": ""}
        self.assertEqual(pa.classify(self.ra, both, {}), "erratum_but_retracted")
        eoc = {"pmid": "6", "pubtype": [], "refs": [("expression of concern in", "7", "doi: 10.1111/n1.")],
               "title": ""}
        self.assertEqual(pa.classify(self.ra, eoc, {}), "eoc")
        com = {"pmid": "7", "pubtype": [], "refs": [("comment in", "8", "doi: 10.1111/n1")], "title": ""}
        self.assertEqual(pa.classify(self.ra, com, {}), "other_link")

    def test_shared_doi_keeps_paper(self):
        paper = {"pubtype": ["Journal Article"], "articleids": [{"idtype": "doi", "value": "10.1111/X"}]}
        notice = {"pubtype": ["Published Erratum"], "articleids": [{"idtype": "doi", "value": "10.1111/X"}]}
        a = pa.parse_esummary({"result": {"uids": ["1", "2"], "1": paper, "2": notice}})
        self.assertEqual(a["10.1111/x"]["pmid"], "1")
        b = pa.parse_esummary({"result": {"uids": ["2", "1"], "1": paper, "2": notice}})
        self.assertEqual(b["10.1111/x"]["pmid"], "1")

    def test_needs_lookup(self):
        self.assertEqual(pa.needs_pmid_lookup(self.pm["10.1111/t2"]), ["22"])
        self.assertEqual(pa.needs_pmid_lookup(self.pm["10.1111/t1"]), [])
        self.assertEqual(pa.needs_pmid_lookup(None), [])


class Summary(unittest.TestCase):
    def test_summarize(self):
        w = pa.Walker()
        rels = [
            dict(notice="n1", target="10.1096/fj.09-135467", verdict="contradict", publisher="Wiley",
                 title_class="correction", utype="retraction", year=2010, rw_retracted=False,
                 oa_is_retracted=True, oa_cited_by=442, t_title_marked=False),
            dict(notice="n2", target="t2", verdict="agree", publisher="Elsevier",
                 title_class="retraction", utype="retraction", year=2020, rw_retracted=True),
            dict(notice="n3", target="t3", verdict="not_in_pubmed", publisher="IEEE",
                 title_class="other", utype="retraction", year=2021, rw_retracted=False),
            dict(notice="n4", target="t4", verdict="pm_silent", publisher="IEEE",
                 title_class="other", utype="retraction", year=2021, rw_retracted=False),
        ]
        s = pa.summarize(w, rels, True)
        self.assertEqual(s["n_publisher_relations"], 4)
        self.assertEqual(s["n_targets"], 4)
        self.assertEqual(s["n_pubmed_indexed"], 3)
        self.assertEqual(s["n_linked"], 2)
        self.assertEqual(s["share_agree_of_linked"], 0.5)
        self.assertEqual(s["n_contradict"], 1)
        self.assertEqual(s["known_recovered"], ["10.1096/fj.09-135467"])
        self.assertEqual(s["known_verdicts"], [("10.1096/fj.09-135467", "n1", "contradict")])
        self.assertEqual(s["contradict_oa_retracted"], 1)
        self.assertEqual(s["contradict_oa_citations"], 442)
        self.assertEqual(s["contradict_correction_worded"], 1)
        self.assertEqual(s["silent_by_publisher"], [("IEEE", 1)])
        self.assertEqual(s["contradict_by_year"], [(2010, 1)])


if __name__ == "__main__":
    unittest.main()
