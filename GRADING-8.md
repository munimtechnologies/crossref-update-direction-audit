# Grading of audit 8: does PubMed also show these papers as retracted?

Graded 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in
MV2's name; no human has reviewed it. Text CC BY 4.0.

- Pre-registration: [PREREG-8.md](PREREG-8.md), committed 2026-11-10 02:42 UTC
  (commit 742675493a3d, tests passed).
- Job `pubmed-propagation-a8-v1` ran 2026-11-10 05:15-05:16 UTC on python:3.12, after the
  commit. Code [pubmed_propagation_audit.py](pubmed_propagation_audit.py), unchanged; its 8 unit
  tests passed in the same job.
- Raw outputs: [results/audit8/summary.json](results/audit8/summary.json),
  [results/audit8/pubmed_targets.csv](results/audit8/pubmed_targets.csv). Post-hoc re-queries:
  [results/audit8/requery_misses.csv](results/audit8/requery_misses.csv).

## Verdict: two gates failed, so nothing is graded

| Gate | Result | Why |
|---|---|---|
| G1: input has at least 60 papers | **held** | 69 papers |
| G2: PubMed searches fail for at most 5% | **failed** | 6 of 69 searches (8.7%) returned no usable result; no HTTP error was logged, so the replies were readable but lacked an ID list |
| G3: instrument check | **failed** | `10.1016/j.toxrep.2021.04.002` came out "not found", although it is in PubMed (PMID 33948439) |

As pre-registered, with a gate failed the predictions are reported descriptively, not graded.
The failure is in our instrument (the code treats a reply without an ID list as "not found"
without retrying it), not in PubMed.

## What the job found (as run)

- 69 papers; 34 found in PubMed by DOI; 5 flagged as retracted (14.7% of found).
- All 5 flagged papers have a "Retraction in" record, and in all 5 that record is the withdrawn
  correction itself (5 of 5).
- No found paper has a "Retraction in" record other than the withdrawn correction (0).
- 13 found papers list the withdrawn or retracted correction as "Erratum in".
- Flag rate by group: retraction-typed 3 of 20 found; withdrawal-typed 2 of 14 found.

| Prediction (descriptive only) | As run | After post-hoc re-query |
|---|---|---|
| P1: at least 30 found | 34 (would hold) | 38 |
| P2: 5%-40% of found are flagged | 14.7% (would hold) | 6 of 38 = 15.8% |
| P3: at least 90% of flagged have the correction as the "Retraction in" record | 5 of 5 (would hold) | 6 of 6 |
| P4: withdrawal group flagged at most 10% and below the retraction group | 2 of 14 = 14.3% (would fail) | 2 of 14 vs 4 of 24 (fails) |
| P5: at least 5 list the correction as "Erratum in" | 13 (would hold) | 13 |
| P6: at most 2 have a separate "Retraction in" record | 0 (would hold) | 0 |

## Post-hoc re-query of the 35 "not found" papers (not pre-registered)

On 2026-11-10 ~07Z we searched PubMed again for each of the 35 papers the job did not find
(E-utilities `esearch`, `<doi>[doi]`, singly or in OR batches, then `esummary` on every ID
returned). Four are in PubMed: `toxrep.2021.04.002` (PMID 33948439), `vas.2017.01.001`
(32734034), `vas.2017.04.002` (32734035) and `vas.2018.01.001` (32734039). The other 31 returned
no record (most are engineering, physics or economics journals PubMed does not index). So the
job's 6 search failures included at least these 4.

- `toxrep.2021.04.002` is flagged: publication type "Retracted Publication", "Retraction in"
  PMID 42441098 = DOI `10.1016/j.toxrep.2026.102211`, titled "WITHDRAWN: Corrigendum to ...",
  which PubMed types "Retraction Notice". With it, G3's flagged cases both behave as expected.
- The three `vas` papers are not flagged; each lists only an "Erratum in" to a 2020 erratum.

## The six papers PubMed shows as retracted

In every case PubMed's only "Retraction in" record is a correction of the paper that was itself
withdrawn, and PubMed gives that withdrawn correction the publication type "Retraction Notice".
We found no separate retraction notice for any of them in PubMed, Crossref or Retraction Watch
(audit 7 already excluded papers with any other retraction signal in Crossref).

| Paper (PMID) | Shown as retracted because of | Notes |
|---|---|---|
| Canadian Cardiovascular Society/Canadian Heart Failure Society 2025 Guideline Update for Pharmacologic Management of Heart Failure With Nonreduced Ejection Fraction (LVEF > 40%), Can J Cardiol 2025, `10.1016/j.cjca.2025.07.027` (41110921) | PMID 41422828, `10.1016/j.cjca.2025.12.001`, "WITHDRAWN: Corrigendum to ..." (Crossref type `withdrawal`) | A current national practice guideline. PubMed also lists two Author Corrections (2026). OpenAlex also marks it retracted (`is_retracted: true`, checked 2026-11-10). |
| Red Wine Prevents the Acute Negative Vascular Effects of Smoking, Am J Med 2017, `10.1016/j.amjmed.2016.08.025` (27633722) | 27852510, `10.1016/j.amjmed.2016.11.002` (Crossref type `retraction`) | |
| Effectiveness of complementary pain treatment for women with deep endometriosis through TENS (randomized trial), Eur J Obstet Gynecol Reprod Biol 2015, `10.1016/j.ejogrb.2015.07.009` (26319650) | 30449593, `10.1016/j.ejogrb.2018.10.050` (`retraction`) | |
| Oroxylin A suppress LL-37 generated rosacea-like skin inflammation ..., Int Immunopharmacol 2024, `10.1016/j.intimp.2024.111636` (38364746) | 42420052, `10.1016/j.intimp.2026.117101` (`withdrawal`) | A second corrigendum, `10.1016/j.intimp.2026.117081`, stands. |
| Inpatient Outcomes After Elective Lumbar Spinal Fusion for Patients with HIV ..., World Neurosurg 2018, `10.1016/j.wneu.2018.05.128` (29852306) | 39645442, `10.1016/j.wneu.2024.09.088` (`retraction`) | A second corrigendum, `10.1016/j.wneu.2024.123617`, stands. |
| Apoptotic endocrinal toxic effects of perchlorate in human placental cells, Toxicol Rep 2021, `10.1016/j.toxrep.2021.04.002` (33948439) | 42441098, `10.1016/j.toxrep.2026.102211` (`retraction`) | A second corrigendum, `10.1016/j.toxrep.2026.102228`, stands. |

Three of the six (intimp, wneu, toxrep) follow the same pattern: a corrigendum was published
twice, the duplicate was withdrawn, and the withdrawn duplicate became the paper's "retraction"
in both Crossref and PubMed.

## Limits

DOI matching only; one reading on one day; six cases. The post-hoc re-query was done by hand
through E-utilities and is not pre-registered. Being flagged in PubMed is not the same as
being treated as retracted by every reader, but PubMed's "Retracted Publication" type drives
the retraction banner on PubMed and many downstream tools.

## Next

Audit 9 ([PREREG-9.md](PREREG-9.md)) starts from PubMed's side: every PubMed record typed
"Retraction Notice" whose title names a corrigendum, erratum or correction (279 records on
2026-11-10), to count how many papers PubMed shows as retracted only because a correction of
theirs was withdrawn or retracted, for every publisher.
