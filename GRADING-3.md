# Grading, audit 3: Physics Today correction links

Graded 2026-11-08 (about 23:00 UTC) against [PREREG-3.md](PREREG-3.md). By MV2, Munim, Inc.
(mv2@munimtech.com). Made with AI agents working in MV2's name; no human has reviewed it.
Text and data CC BY 4.0, code Apache-2.0.

The audit (`pt_correction_audit.py`, job `crossref-pt-corrections3-v1`) ran on 2026-11-08 at
19:27-19:37 UTC. It read all 278 *Physics Today* records with `update-to` (1,484 relations;
all 1,361 distinct targets found). It also read 8,901 other AIP Publishing notices.

## Result: gate held; 6 of 8 predictions held

| | Prediction | Result | Held? |
|---|---|---|---|
| G | >= 270 notices, >= 95% of targets found | 278 notices, 100% | yes |
| P1 | >= 250 relations `later` by volume/issue | 386 (all 386 also later by issued date) | yes (seen) |
| P2 | contemporaneous notices: <= 1 `later`, mean targets <= 1.3 | 16 notices: 0 later, mean 1.19 | yes |
| P3 | back-file notices average >= 3 targets | 5.66 | yes (seen) |
| P4 | >= 30% of judged back-file relations `later` | 386 of 1,459 = 26.5% | **no** |
| P5 | >= 60% of back-file notices with 3+ targets have a `later` target | 101 of 159 = 63.5% | yes |
| P6 | >= 5% of distinct back-file targets listed by 2+ notices | 109 of 1,337 = 8.2% | yes (seen) |
| P7 | `later` share for issues 1-6 >= 1.5x issues 7-12 | 229/727 = 31.5% vs 157/732 = 21.4%: 1.47x | **no** (narrowly) |
| P8 | AIP control: <= 1% of other judged AIP relations later | 23 of 8,616 = 0.27% | yes |

## What it shows

*Physics Today*'s Crossmark correction links from the 2007-2009 back-file deposit (258 notices
created two or more years after print) are **scrambled**. A one-page "Corrections" column
typically links 5 or 6 items, and 386 of these links (26.5%) point at items printed in a
**later** issue than the column. A correction cannot correct something not yet printed. 101 of
the 159 back-file columns with three or more links have at least one such impossible link, and
109 items are claimed by two or more different columns.

The 16 notices deposited within 120 days of print link about one item each, and none
points forward. In the rest of AIP Publishing, only 0.27% of 8,616 notice links point forward.
The problem is confined to the *Physics Today* back file. It is not an AIP-wide deposit fault.

The `later` links are only the provably impossible part. Earlier-issue links in the same
columns were drawn the same way. Because the notices' text (PDF only) was not read, nothing
here says which of those are right. A plausible mechanism is that the back-file deposit linked
each column to items from around the same volume. P7 (earlier-in-year columns have more
forward links) points that way at 1.47x, but missed its pre-registered 1.5x threshold.

## Hand check of 20 `later` links

Every notice and target in [results/audit3/grade_later20.csv](results/audit3/grade_later20.csv)
was re-read through api.crossref.org on 2026-11-08. All 20 targets are *Physics Today*
`journal-article` records in the same volume as their column, printed 1 to 9 issues later.
Examples: the May 1972 "Corrections" (10.1063/1.3043315, vol. 25 no. 5) links the book review
"Color and Symmetry" (vol. 25 no. 12), and the March 1995 "Correction" (10.1063/1.2807966)
links "What Future Will We Choose for Physics?" (vol. 48 no. 12). None is a reprint, index or
duplicate record. 20 of 20 are confirmed impossible. One notice, the 1967 "Errata"
10.1063/1.3043295, lists each of its 8 targets twice.

## Data

[results/audit3/](results/audit3/): `summary.json`, `pt_notices.csv` (278), `pt_relations.csv`
(1,484, with class and era), `aip_table.csv` (AIP journals by era) and the hand-check sample.
