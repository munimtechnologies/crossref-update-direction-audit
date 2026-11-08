# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Unit tests for notice_audit.py (no network)."""
import unittest

import notice_audit as na


def item(doi, title, updates, member="1", year=2024):
    return {"DOI": doi, "title": [title], "member": member, "publisher": "P" + member,
            "created": {"date-parts": [[year, 1, 1]]}, "container-title": ["J"],
            "update-to": [{"DOI": d, "type": t, "source": s} for d, t, s in updates]}


class TitleRules(unittest.TestCase):
    def test_retraction_worded(self):
        self.assertTrue(na.retraction_worded("Retraction notice to X"))
        self.assertTrue(na.retraction_worded("Withdrawn: Y"))
        self.assertTrue(na.retraction_worded("Retraction note: Z"))
        self.assertFalse(na.retraction_worded("Correction to: W"))
        self.assertFalse(na.retraction_worded("Retractable roofs"))

    def test_correction_worded(self):
        self.assertTrue(na.correction_worded("Correction to: W"))
        self.assertFalse(na.correction_worded("Correction to retraction of W"))


class NoticeLevel(unittest.TestCase):
    def setUp(self):
        w = na.Walker()
        # A: self-loop erratum plus a Retraction Watch retraction of the real article X
        w.add(item("10.1/A", "Retraction notice to X",
                   [("10.1/A", "erratum", "publisher"), ("10.1/X", "retraction", "retraction-watch")]))
        # B: withdrawal typed addendum, nothing else anywhere
        w.add(item("10.1/B", "Withdrawn: Y", [("10.1/Y", "addendum", "publisher")], member="945"))
        # C: retraction typed correction, but D retracts the same target Z
        w.add(item("10.1/C", "Retraction note: Z", [("10.1/Z", "correction", "publisher")]))
        w.add(item("10.1/D", "Retraction: Z", [("10.1/Z", "retraction", "publisher")]))
        # E: correction typed retraction, no Retraction Watch support
        w.add(item("10.1/E", "Correction to: W", [("10.1/W", "retraction", "publisher")]))
        # F: two targets, one retracted by G, one not
        w.add(item("10.1/F", "Retraction notice", [("10.1/P", "erratum", "publisher"),
                                                   ("10.1/Q", "erratum", "publisher")], year=2018))
        w.add(item("10.1/G", "Retraction: P", [("10.1/P", "retraction", "publisher")]))
        self.w = w
        self.mistyped, self.overflag = w.finish()
        self.notices = na.notices_from(self.mistyped)

    def test_counts(self):
        self.assertEqual(self.w.n_records, 7)
        self.assertEqual(len(self.mistyped), 5)   # A->A, B->Y, C->Z, F->P, F->Q
        self.assertEqual(len(self.overflag), 1)   # E->W

    def test_pair_flags(self):
        by = {(r["record"], r["target"]): r for r in self.mistyped}
        self.assertTrue(by[("10.1/a", "10.1/a")]["pair_hidden"])
        self.assertTrue(by[("10.1/a", "10.1/a")]["notice_covered"])
        self.assertTrue(by[("10.1/b", "10.1/y")]["pair_hidden"])
        self.assertFalse(by[("10.1/c", "10.1/z")]["pair_hidden"])
        self.assertFalse(by[("10.1/f", "10.1/p")]["pair_hidden"])
        self.assertTrue(by[("10.1/f", "10.1/q")]["pair_hidden"])

    def test_notice_status(self):
        s = {k: v["status"] for k, v in self.notices.items()}
        self.assertEqual(s, {"10.1/a": "covered_on_notice", "10.1/b": "hidden",
                             "10.1/c": "visible", "10.1/f": "partly_hidden"})
        self.assertTrue(self.notices["10.1/a"]["self_only"])
        self.assertFalse(self.notices["10.1/f"]["self_only"])

    def test_overflag_unsupported(self):
        self.assertFalse(self.overflag[0]["rw_either"])

    def test_status_function(self):
        self.assertEqual(na.notice_status(2, 0, False), "visible")
        self.assertEqual(na.notice_status(2, 0, True), "visible")
        self.assertEqual(na.notice_status(2, 2, True), "covered_on_notice")
        self.assertEqual(na.notice_status(2, 2, False), "hidden")
        self.assertEqual(na.notice_status(2, 1, False), "partly_hidden")


if __name__ == "__main__":
    unittest.main()
