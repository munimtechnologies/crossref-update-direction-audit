# Pre-registration 14: which DOIs in the Retraction Watch database are not DOIs at all?

Written 2026-11-11 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before the audit job ran and
before any of its output existed. The job waits until this file is live on GitHub before it
downloads any data, and records the time it saw it (`plan_live_at`, `data_started`). Made with AI
agents working in MV2's name; no human has reviewed it. Code:
[rw_doi_registration_census.py](rw_doi_registration_census.py) (Apache-2.0), tests:
[test_rw_doi_registration_census.py](test_rw_doi_registration_census.py). Text CC BY 4.0.

## Why

The Retraction Watch database (RW), published openly by Crossref, is the reference list that
most retraction checkers, reference managers and studies match on, and they match on its DOIs.
If a row's `OriginalPaperDOI` is not a registered DOI, no DOI match can ever find that retracted
paper, and the row silently drops out. While grading audit 11 we hand-read 35 cases and found
six RW DOIs that doi.org does not know: one with its last digit cut off
(10.1177/014616720026200 for 10.1177/0146167200262008), a Cochrane DOI with its version number
cut off, a year typo (10.18388/abp.2018_6398 for 10.18388/abp.2023_6398), a URL fragment left in
(`#.us5z4lssxk0`), a wrong prefix, and a DOI not registered with Crossref but with mEDRA. Audit 12
counts the same kind of error in RW's PubMed IDs. This audit counts it for every DOI in RW.

## Nearest prior work and the delta

- Schneider et al., "Assessing the agreement in retraction indexing across 4 multidisciplinary
  sources" (STI 2023): DOI-level agreement of Crossref, RW, Scopus and Web of Science; counts RW
  records without a DOI (5,928). It does not check whether RW's DOIs exist.
- Tesseract Semantics, retraction register ontology (Aug 2026): Crossref and RW agree on 72.42%
  of retracted DOIs. It compares assertions; it does not test whether the DOIs resolve.
- "Do published reference lists still cite retracted papers? A dated OpenAlex audit" (DEV,
  2026-10-01): Crossref found 117 of 120 sampled RW retractions (no cause given for the 3).
- Published cleaning recipes (lower-casing, stripping `https://doi.org/`, dropping `unavailable`)
  treat any string that looks like a DOI as valid.
- The two open issues on gitlab.com/crossref/retraction-watch-data (checked 2026-11-11) are about
  a date format and an empty template, not DOIs.
- Searched 2026-11-11 for RW DOI validity, unregistered, malformed, truncated or typo DOIs:
  nothing found.
- Delta: the first census of whether every RW DOI is registered with any DOI agency, why the
  unregistered ones fail, and which registered DOI was meant.

## Population and method

- Every row of the RW CSV from gitlab.com/crossref/retraction-watch-data (fallback: Crossref's
  Labs endpoint), every `RetractionNature`. Both fields: `OriginalPaperDOI` (paper side) and
  `RetractionDOI` (notice side). Placeholders (blank, `unavailable`, `0`, `n/a` ...) are skipped.
  URL and `doi:` prefixes are removed and case is ignored. A field holding two DOIs is cut to the
  first (counted). Anything else that is not `10.<4-9 digits>/<non-space>` is `invalid_syntax`.
- Each distinct DOI is asked at doi.org (`doiRA`, 25 per request; one at a time, with the handle
  API as fallback, for DOIs with characters that cannot go in a list). Status: `registered` (with
  its agency), `not_exist`, `invalid`, `unknown` (lookup failed). Unregistered =
  `not_exist` + `invalid` + `invalid_syntax`. Rates are per distinct (side, DOI).
- Repair, for each unregistered DOI: first mechanical clean-ups (URL fragment or query, trailing
  punctuation or unbalanced bracket, URL tails such as `/full` or `.pdf`, HTML entities,
  %-escapes, spaces, a DOI embedded in text), each checked at doi.org (`cleanup`). Otherwise one
  Crossref bibliographic search for RW's `Title` (top 5, at most 4,000 searches, paper side
  first): `repaired` if exactly one result is near the unregistered DOI (the result extends it by
  1-3 characters = `truncated`; it is 1-3 characters shorter = `extra_chars`; same suffix, other
  prefix = `prefix_swap`; edit distance <= 2 = `typo`), is not the row's other DOI, and shares
  >= 50% of its title words with RW's title; `ambiguous` if more than one; `unrepaired` if none.
- Outputs: summary.json, unregistered.csv, non_crossref_ra.csv, grade20_repaired_paper.csv,
  grade20_unrepaired_paper.csv.

## What we read before writing this (disclosed)

- The 35 audit-11 cases above (6 unregistered RW DOIs), and doi.org answers for 7 of those DOIs
  and their fixes, plus 24 neighbours of 10.1177/0146167200262008 (the one-digit extensions
  ...2001 to ...2009 of the truncated DOI are all registered, so only the title tells which one
  was meant; that is why repair goes through the title).
- The DEV audit's figure (3 of 120 not found in Crossref).
- One Crossref bibliographic search by hand, for the title of 10.1177/0146167200262008: it was the
  top result, and the second was its retraction notice (C1 should therefore hold for that control).
- No row of the current RW CSV was read for this audit.
- **So P5 (repair classes) and P6 (other agencies) are informed by those six cases. P1-P4 are
  blind.**

## Gates (if a gate fails, P1-P6 are reported descriptively, not graded)

- G1: the RW CSV has at least 60,000 rows and the expected columns.
- G2: at most 2% of distinct DOIs asked end as `unknown`.
- G3 (instrument check): 10.1177/014616720026200 and 10.18388/abp.2018_6398 are in RW and
  `not_exist`; 10.1080/09645292.2010.545518#.us5z4lssxk0 is in RW and is repaired by clean-up to
  10.1080/09645292.2010.545518; 10.26355/eurrev_202101_24355 is in RW and registered with mEDRA.
- G4: this file was live on GitHub before data were downloaded.
- Reported but not a gate (C1): whether the title search repairs the first two controls to
  10.1177/0146167200262008 and 10.18388/abp.2023_6398.

## Predictions

- P1 (blind): 0.3%-3% of distinct paper-side DOIs are unregistered.
- P2 (blind): the unregistered share on the notice side is at least the paper-side share.
- P3 (blind): notice DOIs whose RetractionDate is in the 60 days before the run are unregistered
  at least 3 times as often as older ones (a registration lag; inconclusive if fewer than 200
  recent notice DOIs).
- P4 (blind): at least 40% of processed unregistered paper DOIs get a unique repair (`cleanup` or
  `repaired`; inconclusive if fewer than 30 processed).
- P5 (informed): `truncated` is the single most common repair class on the paper side
  (inconclusive if fewer than 10 repairs).
- P6 (informed): at least 0.5% of registered paper-side DOIs are held by an agency other than
  Crossref (so a Crossref-only lookup cannot see them).
- P7 (hand grading, next step): of the 20 sampled repaired paper DOIs, at least 17 are right: the
  repaired DOI's Crossref record is the paper RW describes (same title and journal).

Grading will report every prediction as held, failed or not graded, with the numbers, including
failures. Anything found afterwards will be labelled post hoc. Confirmed repairs will be reported
to Crossref, which publishes the RW data (support@crossref.org), and offered as a public list.
