# Grading 5: does PubMed agree with the retractions that publishers deposit in Crossref?

Graded 2026-11-09 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against [PREREG-5.md](PREREG-5.md)
(committed 2026-11-09 02:39 UTC, commit 8af407a; the job ran 14:01-14:13 UTC the same day).
Made with AI agents working in MV2's name; no human has reviewed it. Text CC BY 4.0.

**Result: 6 of 9 predictions held.** Both gates passed. PubMed agrees with 97.5% of the
retraction links it can be compared with. Of 30 publisher retractions or withdrawals that PubMed
links as errata only, the hand grading found that in 13 of 20 sampled cases the paper was
only corrected. A post-hoc finding: Elsevier **corrections that were themselves retracted or
withdrawn** make the corrected paper look retracted or withdrawn in Crossref. The follow-up census is
pre-registered as [PREREG-7.md](PREREG-7.md).

Files: [results/audit5/](results/audit5/) (summary.json, contradictions.csv,
erratum_but_retracted.csv, agree_sample20.csv, grade_contradictions20.csv as produced, and
grade_contradictions20_graded.csv with the hand grades).

## Gates

| Gate | Rule | Result |
|---|---|---|
| G1 | walks complete, >= 80,000 records, PubMed phase not aborted, esearch failures <= 2% | **passed**: 85,042 records; 41 of 44,559 queryable targets failed (0.09%) |
| G2 | of 10 known corrected-not-retracted papers, >= 8 contradict or pm_corrected_only, >= 5 contradict | **passed**: 10 of 10 (6 contradict, 4 pm_corrected_only) |

## Predictions

| # | Prediction | Result | Held? |
|---|---|---|---|
| P1 | 40,000-70,000 publisher non-self retractive relations | 44,693 | **held** |
| P2 | 25-60% have a target found in PubMed | 21,489 (48.1%) | **held** |
| P3 | >= 95% of same-notice links are `agree` | 20,425 of 20,955 (97.5%) | **held** |
| P4 | 20-400 `contradict` | 30 | **held** |
| P5 | >= 25% of `contradict` not correction-titled | 22 of 30 (73%) | **held** |
| P6 | Wiley has the most `contradict` | Elsevier 16, Wiley 3, Informa 3 | **failed** |
| P7 | OpenAlex is_retracted true for >= 90% of `contradict` targets | 23 of 30 (76.7%) | **failed** |
| P8 | <= 25% of `contradict` have a Retraction Watch retraction | 3 of 30 (10%) | **held** |
| P9 | hand grade of 20: >= 14 corrected-not-retracted and <= 3 real retractions PubMed mislinked | 13 and 4 | **failed** (both parts) |

Blindness: P1-P8 come from the job. P9 is a hand grade done after reading the job output, using
the evidence listed in PREREG-5 plus live api.crossref.org records read on 2026-11-09.

## Hand grade (P9), all 20 sampled `contradict` relations

| Grade | n | Cases (target DOI) |
|---|---|---|
| corrected, not retracted (Crossref wrong) | 13 | pi.2022.0200, neuroscience.2021.11.026, neuro.2020.12.005, ijpx.2023.100203, neuroscience.2022.11.029, neuroscience.2026.06.035, meegid.2021.104737, gendis.2020.07.005, jacr.2021.09.036, lfs.2008.11.017, ane.0000000000005558, clnu.2016.12.027, ejpt.v4i0.21892 |
| really retracted; PubMed lists the retraction notice as an erratum | 4 | pnas.86.13.5141, gha.v7.21783, anie.201510712, actpsy.2023.104004 |
| really retracted; Crossref's retraction link comes from a retracted corrigendum | 2 | heliyon.2021.e06952, ab.2025.115927 |
| partial retraction deposited as a full retraction | 1 | iai.00219-07 |

Evidence for each case is in grade_contradictions20_graded.csv. Two are weaker. For
neuroscience.2026.06.035 we read only the titles and PubMed, not the live records. For
meegid.2021.104737 we did not read the withdrawn item's text. Both are counted as
corrected-not-retracted.

So 13 papers that were only corrected show as retracted or withdrawn in Crossref, besides the 17
in [findings/corrections-deposited-as-retractions.md](findings/corrections-deposited-as-retractions.md),
whose 10 PubMed-indexed papers this audit found again (6 as `contradict`, 4 as
`pm_corrected_only`). Together the 13 have 926 OpenAlex citations;
660 of those are for the ESPEN guideline on clinical nutrition in inflammatory bowel disease
(10.1016/j.clnu.2016.12.027), which Crossref lists as withdrawn.

## Post hoc (not pre-registered)

1. **Retracted or withdrawn corrections make the paper look retracted or withdrawn.** 9 of the 13
   are Elsevier records titled "RETRACTED: Corrigendum to ...", "WITHDRAWN: Corrigendum to ...",
   "WITHDRAWN: Erratum" or "TEMPORARY REMOVAL: Corrigendum to ...". In each, the correction
   itself was retracted, withdrawn or removed (often a corrigendum published twice by mistake).
   But its `update-to` link to the paper carries `retraction`, `withdrawal` or `removal`, so
   Crossref's `updated-by` on the **paper** says it was retracted or withdrawn.
2. **The types look swapped.** For lfs.2008.11.017 and ijpx.2023.100203, the notice that retracts
   the corrigendum ("Retraction notice to Corrigendum to ...", 10.1016/j.lfs.2024.122455 and
   10.1016/j.ijpx.2025.100388) is deposited as `erratum`. The corrigendum carries `retraction`
   instead. Retraction Watch types the lfs link correctly (`retraction`, notice to corrigendum).
   For gendis.2020.07.005, Retraction Watch types the corrigendum's link `correction` where
   Elsevier deposited `retraction`.
3. **OpenAlex follows the type word.** All 23 `contradict` targets typed `retraction` are
   is_retracted true in OpenAlex; none of the 7 typed `withdrawal` or `removal` are. So papers
   wrongly listed as withdrawn are not repeated as retracted by OpenAlex, but Crossref's own
   metadata (and any tool reading `updated-by`) still shows them withdrawn.
4. The other 4 non-sampled, non-known `contradict` relations (abb.2024.110176,
   jacr.2021.10.018, jhazmat.2023.133313, gha.v6i0.19305) were not graded; the first three have
   the same title pattern as point 1.
5. 25 of the 32 `erratum_but_retracted` relations are "RETRACTED: Corrigendum to ..." notices on
   papers that PubMed also lists as retracted. There the paper's status is right, but Crossref's
   retraction link points at the corrigendum instead of the retraction notice.

Prior work checked again on 2026-11-09: the Crossref forum thread "[Elsevier] Metadata errors:
18 articles (wrongly?) marked retracted" (G. Cabanac, 2025-11-24) reports papers wrongly marked
retracted, gives no cause, and keeps its DOI list in a PubPeer report we could not read. We found
no description of retracted corrections as a cause. Audit 7 ([PREREG-7.md](PREREG-7.md)) counts
the pattern across all of Crossref, with predictions written before it runs.

## Limits

- PubMed-indexed targets only (48% of relations). Notices that PubMed links by neither DOI nor
  PMID are not compared.
- The hand grades rest on public metadata, journal pages and PubMed, not on correspondence with
  publishers. Publishers can change these records at any time.
- "Crossref wrong" means the metadata disagrees with the publisher's own notices. It does not
  claim anything about the research.
