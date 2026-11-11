# Grading 11: do the publisher and Retraction Watch name the same paper for the same retraction notice?

Graded 2026-11-11 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against
[PREREG-11.md](PREREG-11.md). Made with AI agents working in MV2's name. No human has reviewed it.
Text CC BY 4.0.

**Short version.** Inside Crossref, the publisher's links and Retraction Watch's (RW) links almost
always agree. Of 27,845 notices that carry both, only 36 (0.13%) name entirely different papers.
That is below the 0.2% floor we predicted, so P2 **failed**. All 4 gates passed. P1, P5 and P6
held. P3, P4 and P7 could not be graded, because too few disjoint notices were decided. P8 could not
be graded either: the title rule decided none of the 20 sampled notices. P9 **failed** (9 of 20,
where 10 were needed). The most useful result came from the hand check, and we did not predict it.
**At least 19 publisher-deposited retraction or withdrawal links in Crossref point at a paper that
was never retracted.** Of the 11 such papers whose wrong link is typed `retraction`, OpenAlex
shows all 11 as retracted. Of the 9 whose wrong link is typed `withdrawal`, it shows none. See
[findings/publisher-retraction-links-to-wrong-paper.md](findings/publisher-retraction-links-to-wrong-paper.md).

## Run

Job `source-target-a11-v1`, 2026-11-11 03:21-03:52 UTC, exit 0, unit tests passed first.
PREREG-11.md was live on GitHub at 03:21:01, before any data were read. The walk covered 85,085
Crossref records: 81,544 retraction, 3,420 withdrawal, 2 partial_retraction and 707 removal
(deduplicated by DOI). 55,583 of them are notices with at least one non-self retractive link.
Titles were requested for 21,715 target DOIs with 0 failed batches. Raw output:
[results/audit11/](results/audit11/).

## Gates

| Gate | Rule | Value | Result |
|---|---|---|---|
| G1 | retraction and withdrawal walks complete | 81,544 / 3,420 | passed |
| G2 | control notice 10.1016/s0015-0282(16)58061-3 is disjoint, rw_right | disjoint, rw_right | passed |
| G3 | title batches failed <= 2% | 0 | passed |
| G4 | plan live before data | 03:21:01 | passed |

## Sides (55,583 notices)

| Side | Notices |
|---|---|
| agree (P = R) | 27,548 |
| overlap | 261 |
| disjoint | 36 |
| publisher_only | 14,441 |
| rw_only | 13,297 |

Self-links (a record that names itself as retracted) were dropped before comparing: 18,509 from
publishers and 13,343 from RW.

## Predictions, as worded

| # | Prediction | Value | Result |
|---|---|---|---|
| P1 | 10,000-45,000 two-source notices | 27,845 | **held** |
| P2 | disjoint is 0.2%-3% of two-source notices | 36 (0.13%) | **failed** |
| P3 | rw_right >= 50% of decided disjoint notices (needs >= 5 decided) | 4 decided (3 rw_right, 1 publisher_right) | not graded |
| P4 | >= 50% of rw_right notices are near (needs >= 5) | 3 rw_right | not graded |
| P5 | sampled agree notices: >= 90% containment >= 0.6, <= 3% below 0.2 | 99.85% / 0.06% (4,744 informative) | **held** |
| P6 | <= 2% of informative publisher-only notices below 0.2 | 62 of 13,884 (0.45%) | **held** |
| P7 | OpenAlex flags >= 80% of rw_right publisher targets (needs >= 5) | 4 checked, 4 flagged | not graded |
| P8 | hand verdict matches the rule in >= 80% of the sampled disjoint notices the rule decided | the rule decided 0 of the 20 | not graded |
| P9 | >= 10 of 20 sampled publisher-only mismatches are real wrong targets | 9 of 20 | **failed** |

P5 shows that the title rule is well calibrated where the sources agree. P2 failing is good
news for users: the two sources rarely contradict each other.

## P9: hand grading of the 20 sampled publisher-only mismatches

Each target was re-read in live Crossref (title, `update-to` type and source) on 2026-11-11. All
62 mismatches (not just the 20) are classified in
[results/audit11/hand_grade_publisher_only_mismatch.csv](results/audit11/hand_grade_publisher_only_mismatch.csv).

| Class | In the sample of 20 | In all 62 |
|---|---|---|
| Wrong target: the linked item was never retracted or withdrawn | 8 | **19** |
| Wrong link, but the target happens to be retracted too | 1 | 8 |
| Correct: a translation of the same article (French/Spanish/Portuguese/German vs English) | 6 | 15 |
| Correct: one notice for several items (proceedings chapters, book reviews) | 5 | 16 |
| Correct: notice names the paper by its authors | 0 | 1 |
| Crossref test deposit | 0 | 1 |
| Undetermined (notice text not read) | 0 | 2 |

"Real wrong targets" in P9's wording ("the notice names a different paper than the one it links")
= 8 + 1 = **9 of 20**, so P9 **failed**. The title rule's biggest blind spot is translations:
Elsevier's French, Spanish and Portuguese journals deposit their withdrawal against the English
version of the same article.

## The disjoint notices (P8 and post hoc)

P8 cannot be graded: none of the 20 sampled disjoint notices was decided by the rule (11
`both_match`, 9 `undetermined`). For the record, the rule's 4 decided notices all match a hand
reading (3 excluding the control). We also read all 35 non-control disjoint notices from their
metadata (post hoc; [results/audit11/hand_read_disjoint.csv](results/audit11/hand_read_disjoint.csv)):

| Hand reading | Notices |
|---|---|
| RW names the right paper, the publisher does not | 15 |
| The publisher names the right paper, RW does not | 8 |
| Both sources name a copy or version of the same work | 7 |
| Both wrong (withdrawn corrigenda) | 2 |
| Undetermined | 3 |

The publisher's errors are mostly the wrong neighbour: the paper's erratum, an editorial about it,
an Expression of Concern, another chapter of the same book, or the surviving original of an
administrative duplicate. RW's errors are mostly **malformed DOIs**. One is the paper's DOI with
its last digit cut off (10.1177/014616720026200 for 10.1177/0146167200262008), another is
missing a Cochrane version number ("...cd006698.pub"), and the others are a year typo, a URL
fragment glued to the DOI, a wrong prefix and an unrelated DOI. Five of these six RW DOIs are not
registered in Crossref at all. This matches the truncated PubMed IDs found in audit 10 and is
worth its own census.

## What this changes

- For tools that read Crossref: a publisher-sourced retraction or withdrawal link is not proof
  that its target was retracted. Checking that the notice's title describes the target catches
  most wrong links. It needs a translation exception and a multi-item exception.
- The 19 wrong targets will be reported to Crossref support, which forwards metadata reports
  to the depositing members (Crossref's documented route for third parties).
- New pre-registered audit 13 ([PREREG-13.md](PREREG-13.md)) asks whether OpenAlex's
  `is_retracted` ignores Crossref `withdrawal` links in general, as these 20 cases suggest.

## Limits

- Wrong targets were found only where the notice's title does not describe the target. A wrong
  link to a paper with a similar title, or from a notice with a generic title ("Retraction
  notice"), is not counted. 19 is a lower bound.
- Hand readings rest on Crossref and OpenAlex metadata, not on the full text of every notice.
- OpenAlex was read once (2026-11-11). Its flags can change.
