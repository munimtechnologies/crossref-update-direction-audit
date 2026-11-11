# Grading 10: does PubMed link each retraction notice to the paper Retraction Watch names?

Graded 2026-11-11 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against
[PREREG-10.md](PREREG-10.md). Made with AI agents working in MV2's name. No human has reviewed it.
Text CC BY 4.0.

**Short version.** For 27,699 of 28,365 retraction pairs (97.7%), the Retraction Watch database
(RW) and PubMed name the same paper for the same notice, and both links run both ways. All 5 gates
passed. 6 of the 8 automatic predictions held: P5 (RW's PMID is the wrong one in most
disagreements, under both rules) and P7 (at least 1% of pairs unlinked) failed. The hand-graded
P9 failed too: 10 of 20, where 12 were needed. The biggest single finding was not predicted.
**In 34 RW rows, the PubMed ID is the correct one with its last digit (once, two digits) cut
off**, so it points at an unrelated paper from the 1970s to the 1990s. See
[findings/rw-truncated-pubmed-ids.md](findings/rw-truncated-pubmed-ids.md). PubMed has errors of
its own as well: in at least three cases its notice is linked to the wrong record, so a retracted
paper carries no retraction flag there.

## Run

Job `rw-pubmed-link-a10-v1`, 2026-11-10 23:28-23:37 UTC, exit 0, unit tests passed first. Raw
output: [results/audit10/](results/audit10/). The RW CSV (gitlab.com/crossref/retraction-watch-data)
had 73,747 rows, and 28,404 distinct (paper PMID O, notice PMID N) pairs were eligible. 55,968
PMIDs were requested from E-utilities with 0 failures. PREREG-10.md was committed at 17:17 UTC,
six hours before the job read any data.

## Gates

| Gate | Rule | Value | Result |
|---|---|---|---|
| G1 | RW CSV >= 60,000 rows with the 3 columns | 73,747 | passed |
| G2 | >= 5,000 eligible pairs | 28,404 | passed |
| G3 | esummary failures <= 2% | 0 | passed |
| G4 | control pair 31662796 / 34422117 is `agree_both` | agree_both | passed |
| G5 | plan live before data | live at 23:28:08, committed 17:17 | passed |

## Classes (28,404 pairs)

| Class | Pairs |
|---|---|
| agree_both | 27,699 |
| linked_other_type | 359 |
| unlinked | 217 |
| n_targets_other | 57 |
| o_missing | 21 |
| o_linked_other | 19 |
| n_missing | 18 |
| agree_one_side | 14 |

## Predictions, as worded

| # | Prediction | Value | Result |
|---|---|---|---|
| P1 | 8,000-30,000 eligible pairs | 28,404 | **held** |
| P2 | agree_both + agree_one_side >= 85% of found pairs | 97.7% | **held** |
| P3 | agree_one_side <= 3% of found pairs | 0.05% | **held** |
| P4 | 20-600 n_targets_other pairs | 57 | **held** |
| P5 | rw_pmid_wrong >= half of decided n_targets_other, by DOI AND by title | DOI 22 of 54 (40.7%); title 20 of 30 (66.7%) | **failed** |
| P6 | >= 5 pubmed_link_suspect (DOI rule) | 32 | **held** |
| P7 | unlinked >= 1% of found pairs | 217 (0.77%) | **failed** |
| P8 | >= 30% of unlinked pairs have a paper PubMed does not flag | 210 of 217 (96.8%) | **held** |
| P9 | hand: >= 12 of 20 sampled n_targets_other are "RW's PMID is wrong" | 10 of 20 | **failed** |

**Why P5 split.** The two rules disagree because many of PubMed's "other targets" are records
*about* the same paper: an Expression of Concern, a corrigendum, an erratum or a republished
copy. They have their own DOI, so the DOI rule calls the pair `pubmed_link_suspect`. But their
titles repeat the paper's title, so the title rule leaves them `undetermined`. Neither rule was
built for this case, so the 32 `pubmed_link_suspect` calls in P6 overstate PubMed's errors. The
hand grading below is the better guide.

## P9: hand grading of the 20 sampled n_targets_other pairs

Evidence for each pair: the job's esummary records for O, N and every other target T, Crossref's
`update-to` entries on the notice (publisher and RW sources, with record-id), and RW's DOI and
title. 12 of the 20 were re-read from E-utilities and api.crossref.org on 2026-11-11. Per-pair
notes are in [results/audit10/hand_grade_p9.csv](results/audit10/hand_grade_p9.csv).

| Judgement | Pairs |
|---|---|
| RW's paper PMID is wrong (PubMed links the paper RW describes) | **10** (9 of them truncated PMIDs, 1 an unrelated PMID) |
| PubMed links the notice to a different record (another paper, an Expression of Concern, a corrigendum) | 4 |
| PubMed's link is incomplete for a notice that retracts several papers | 2 |
| RW pairs the paper with another notice (the erratum's notice, or another paper's) | 2 |
| Duplicate publication: the sources name different copies | 1 |
| Undetermined (needs the notice text) | 1 |

10 of 20, so P9 **failed**. RW's side is wrong in 12 of the 20 (including the 2 wrong
notices), and PubMed's in 6.

## PubMed linking errors confirmed by hand (post hoc)

In each case, the notice's own title and both Crossref sources (publisher and RW) name the
paper, yet PubMed links the notice to something else. The paper itself carries no retraction flag
in PubMed (checked 2026-11-11):

- **Transplantation.** Notice PMID 31348441, "Prevention and risk factors of the HBV recurrence
  after orthotopic liver transplantation: 160 cases follow up study: Retraction", is linked to
  PMID 19461488 (a hepatorenal-syndrome paper that has its own notice, 31348442). The HBV paper,
  PMID 20703179, is not flagged.
- **Metallomics.** Notice PMID 39275946, "Retraction of: Characterising the spatial and temporal
  brain metal profile in a mouse model of tauopathy", is linked to the paper's Expression of
  Concern, PMID 38109887, which PubMed now types "Retracted Publication". The paper, PMID
  31904058, is not flagged.
- **Prehospital and Disaster Medicine.** Notice PMID 35437139 is linked to PMID 26555957, a 2015
  editorial with a similar title and a different DOI, which is now typed "Retracted Publication".
  The retracted article, PMID 24667033 (doi 10.1017/S1049023X14000260), is flagged only through a
  "Retraction in" entry without a PMID.

## The unlinked pairs (P7, P8; post hoc reading of grade20_unlinked.csv)

Most of the 217 are Cochrane reviews (120 of them have Wiley as RW's publisher). RW records a
superseded version as "withdrawn" and pairs it with the later "WITHDRAWN:" version. PubMed treats
that as a new version of the review, not as a retraction, so neither record links the other.
That is a difference in definitions, not an error on either side. The sample also holds two
more RW PMID errors: the truncated notice PMID 2437847 (record 4629, see the findings file) and
a 2013 *AIDS Res Hum Retroviruses* row whose two PMIDs, 2380910 and 2407435, are 7-digit numbers
that belong to unrelated papers. Adding one digit to 2380910 gives 23809105, which is also a
different paper, so that row is not counted as a truncation.

## What this changes

- RW's PubMed IDs carry a specific, checkable error: dropped final digits. Audit 12
  ([PREREG-12.md](PREREG-12.md)) measures it across every RW row and both PMID fields before we
  report it.
- PubMed's errors are rarer but have a cost: a retracted paper goes unflagged. The 3 confirmed
  cases above will be reported to the NLM.
- In this sample, the disagreements split about 2:1 between RW and PubMed errors.

## Limits

- Only pairs where RW gives both PMIDs and RetractionNature is "Retraction" were checked.
  Truncations in rows with one PMID missing, or in corrections and expressions of concern, are
  not counted here (audit 12 covers them).
- The hand grades rest on records and metadata, not on reading every notice's full text.
- The 34 truncations come from three classes of this audit. A truncated PMID that happens to
  land on another retracted paper would look different and could be missed.
