# Grading 12: how many Retraction Watch PubMed IDs have their last digit cut off?

Graded 2026-11-12 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against
[PREREG-12.md](PREREG-12.md). Made with AI agents working in MV2's name; no human has reviewed it.
Text and data CC BY 4.0. Raw outputs and hand grades: [results/audit12/](results/audit12/).

The census ran on 2026-11-12 at 11:53 UTC, after the plan was live (`plan_live_at` 11:53:33Z). It
read Retraction Watch's (RW) CSV from Crossref's GitLab copy (73,773 rows) and checked 68,217 PMID
fields (row-sides) against PubMed, with 63,371 PMIDs requested from E-utilities and none failed.
**All four gates passed**, including the instrument check: records 2154 and 475 came out
`truncated` with the expected fixes, and the notice side of 2154 came out `fit`.

## Predictions

| | Prediction | Result | |
|---|---|---|---|
| P1 | 40-1,000 truncated row-sides | 56 | **held** |
| P2 | at least 80% are an 8-digit PMID missing one digit | 55 of 56 (98.2%) | **held** |
| P3 | truncation rate for RW record IDs below 10,000 is at least 5 times the rate above | 0.37% vs 0.02% | **held** |
| P4 | at least 70% of "impossible" paper PMIDs (2001+ paper, PMID below 10,000,000) are truncations | 30 of 38 (79%) | **held** |
| P5 | `fit` is at least 97% of row-sides PubMed returns and RW gives a basis for | 99.15% | **held** |
| P6 | `unfit_other` row-sides at least as many as truncations | 522 vs 56 | **held** |
| P7 | at least 19 of 20 sampled truncations hold up by hand | 20 of 20 | **held** |
| P8 | at least 10 of 20 sampled `unfit_other` row-sides are wrong PMIDs in RW | 14 of 20 (17 counting a looser reading) | **held** |

**Score: 8 of 8 held.** P1-P3 were informed by audit 10, so they are not blind. P4-P8 were blind.

## Hand checks

- **P7.** All 20 sampled truncations were read in the job's PubMed output, and 4 fixes (23809101,
  24074356, 26093692, 31272884) were fetched again by hand from E-utilities. In every case the
  fixed PMID's record carries RW's DOI (18) or is linked to RW's other PMID in PubMed (2), and RW's
  own PMID names an unrelated paper, usually from the 1970s-1990s. See
  [results/audit12/grade20_truncated_hand.csv](results/audit12/grade20_truncated_hand.csv).
- **One false positive outside the sample (post hoc).** Record 35474 (paper side, PMID 3507357) was
  "fixed" to 35073577 by a PubMed link, but 35073577 is a 2022 *J Crohns Colitis* letter, not RW's
  2010 congress abstract. We drop it, which leaves **55 confirmed truncated PMID fields in 48 RW
  records**: [results/audit12/truncated_pmids_confirmed.csv](results/audit12/truncated_pmids_confirmed.csv).
- **P8.** Of 20 sampled `unfit_other` row-sides:
  - 14 are clearly wrong PMIDs. In 11 of them a paper-side PMID is the PMID of a notice. In 3, a
    correction's notice side repeats the paper's PMID although RW gives the correction's DOI.
  - 3 more repeat the paper's PMID on the notice side where RW gives no notice DOI (the "looser
    reading" above).
  - In 2 the PMID is right but RW swapped the paper and notice DOIs. 1 is probably right; PubMed
    has nothing to check it against.

  See [results/audit12/grade20_unfit_other_hand.csv](results/audit12/grade20_unfit_other_hand.csv).

## Post hoc: one notice behind half of the mismatches

281 of the 522 `unfit_other` row-sides (262 paper sides, 19 notice sides) carry the same PMID,
35073579. That is "Withdrawn: Expression of Concern" (*J Crohns Colitis* 2022;16(11):1791,
doi:10.1093/ecco-jcc/jjab227). RW lists about 280 abstracts from a 2010 ECCO congress supplement
under it, gives each abstract the notice's PMID and the supplement's shared DOI, and types the rows
"Expression of concern". PubMed shows the notice itself as withdrawn, with a retraction notice
(doi:10.1093/ecco-jcc/jjac104). We have not read the notices' full texts, so we do not say which
record is right about the abstracts' status. We only say that a PMID join puts all of these rows
on one notice.

## What changes

- [findings/rw-truncated-pubmed-ids.md](findings/rw-truncated-pubmed-ids.md) now gives the
  whole-database count (55 fields, up from audit 10's 34) and corrects one statement. Record 328
  *is* a clean truncation on both sides (23809101 and 24074356 carry RW's DOIs). Our earlier note
  had tested only one extension.
- As PREREG-12 says, the confirmed list goes to Retraction Watch and Crossref, which maintain the
  data.

## Limits

- Only truncations that leave a DOI or link trail are found. A truncated PMID in a row with no
  DOI and no PubMed link stays `unfit_other` or `missing`.
- 233 row-sides name PMIDs PubMed does not return (`missing.csv`); they were not graded.
- One run, on one day's copy of RW and PubMed.
