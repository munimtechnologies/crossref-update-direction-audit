# Pre-registration 12: how many Retraction Watch PubMed IDs have their last digit cut off?

Written 2026-11-11 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before the census job ran and
before any of its output existed. The job waits until this file is live on GitHub before it
downloads any data, and records when it saw it (`plan_live_at`, `data_started`). Made with AI
agents working in MV2's name. No human has reviewed it. Code:
[rw_truncated_pmid_census.py](rw_truncated_pmid_census.py) (Apache-2.0); tests:
[test_rw_truncated_pmid_census.py](test_rw_truncated_pmid_census.py). Text CC BY 4.0.

## Why

Grading audit 10 ([GRADING-10.md](GRADING-10.md)) found 34 rows in the Retraction Watch database
(RW) whose PubMed ID is the correct PMID with its final digit (once, two digits) missing:
[findings/rw-truncated-pubmed-ids.md](findings/rw-truncated-pubmed-ids.md). Audit 10 could only see
this in rows typed "Retraction" that give both PMIDs, and only where PubMed's links led to the
right record. This census checks every RW row and both PMID fields, so the full list can be sent to
the maintainers and the rate measured.

## Nearest prior work and the delta

- Schneider et al., "Analyzing the consistency of retraction indexing" (Illinois data, Appendix
  10): duplicated PMIDs in a union list built by DOI augmentation. Not truncation, and not RW's
  own PMID fields.
- Sebo & Sebo (Account Res 2025) and its preliminary study: coverage and a few metadata errors
  (authors, years). Arjomandi (arXiv:2611.10474): PubMed flag coverage of RW. Tesseract
  Semantics register ontology: DOI-level agreement.
- Our audit 10: pairwise PubMed link check, both PMIDs required.
- Delta: the first check of every RW PMID against the PubMed record it names, with a test for
  truncation. Searched 2026-11-11; we found no report of truncated RW PMIDs.

## Method

- RW CSV from gitlab.com/crossref/retraction-watch-data (fallback: Crossref Labs API), read on
  the job's day. Every row, any `RetractionNature`. Each PMID field with a positive integer is
  one **row-side**: paper side (`OriginalPaperPubMedID`) or notice side (`RetractionPubMedID`).
- PubMed: E-utilities esummary (JSON, POST, batches of 200, tool and email set) for every PMID.
- A record **fits** a row-side when any of these holds:
  - `doi`: PubMed's DOI equals RW's DOI for that side.
  - `link`: the record and the row's other PMID are linked in PubMed (either direction, any
    link type), or the record's links quote RW's DOI for the other side (ignored when RW gives
    the same DOI for both sides).
  - `title` (paper side only): word-set Jaccard of RW's `Title` and PubMed's title >= 0.6.
- An unfit PMID with <= 7 digits is tested against its extensions: PMID x 10 + d (d = 0-9), and,
  for <= 6 digits, PMID x 100 + dd. Status: `truncated` (exactly one extension fits by doi or
  link), `ambiguous` (more than one), `truncated_probable` (none by doi or link, exactly one by
  title), `unfit_other` (unfit, no extension fits, or 8 digits already). Also `missing` (no PubMed
  record), `no_basis` (RW gives nothing to check against) and `fit`.
- "Impossible" paper PMIDs: `OriginalPaperDate` in 2001 or later and PMID below 10,000,000.
  PubMed passed PMID 10,000,000 in about 1999, so a 2001 paper cannot have such an ID.
- Outputs: summary.json, truncated.csv (truncated, probable, ambiguous), unfit_other.csv,
  missing.csv, impossible.csv, grade20_truncated.csv and grade20_unfit_other.csv (first 20 by
  sha256("a12"|record|side) and sha256("a12u"|record|side)).

## What we knew before writing this (disclosed)

- Audit 10's output: 34 truncations in its subset (18 paper side, 16 notice side), 33 of them
  one digit and 1 two digits, and 31 of 34 in RW records with ID below 10,000. P1, P2 and P3 are
  informed by these numbers, so they are **not blind**. P4, P5 and P6 are blind: we have not
  counted impossible PMIDs, overall fit or other mismatches anywhere.
- Controls read by hand on 2026-11-11 became gate G3.

## Gates (if one fails, P1-P6 are reported descriptively, not graded)

- G1: RW CSV has >= 60,000 rows and the needed columns.
- G2: esummary failures <= 2% of PMIDs requested (base and extensions).
- G3 (instrument check): RW record 2154, paper side -> `truncated`, fix 21633303 (by DOI);
  record 475, notice side -> `truncated`, fix 23289124 (by link: that notice has no DOI in
  PubMed); record 2154, notice side -> `fit`. If RW corrects these rows before the job runs, G3
  fails and we say so.
- G4: this file was live on GitHub before data were downloaded.

## Predictions

- P1 (informed): 40-1,000 `truncated` row-sides.
- P2 (informed): >= 80% of them are an 8-digit PMID missing one digit.
- P3 (informed): the truncation rate (truncated / judged row-sides) for RW record IDs below 10,000
  is at least 5 times the rate for IDs of 10,000 and up.
- P4 (blind): >= 70% of impossible paper PMIDs are `truncated` (inconclusive if fewer than 10).
- P5 (blind): `fit` is >= 97% of row-sides that PubMed returns and RW gives a basis for.
- P6 (blind): `unfit_other` row-sides are at least as many as `truncated` ones.
- P7 (hand, next step): of 20 sampled `truncated` row-sides, >= 19 hold up. The fix record is the
  paper or notice RW describes, and RW's PMID names an unrelated record.
- P8 (hand, next step): of 20 sampled `unfit_other` row-sides, >= 10 are wrong PMIDs in RW (the
  record is a different paper or notice from the one RW's DOI and title describe). The rest:
  PubMed or RW DOI errors, versions, or undecidable.

Grading will report every prediction as held, failed or not graded, with the numbers. Anything
found afterwards will be labelled post hoc. After grading, the confirmed list goes to Crossref
and Retraction Watch, which maintain the data.
