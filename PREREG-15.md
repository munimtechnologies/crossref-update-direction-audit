# Pre-registration 15: how many "withdrawn" Crossref items are duplicate DOIs, and does the metadata say where the article went?

Written 2026-11-11 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before the audit job ran and
before any of its output existed. The job waits until this file is live on GitHub before it
downloads any data, and records the time it saw it (`plan_live_at`, `data_started`). Made with AI
agents working in MV2's name; no human has reviewed it. Code:
[duplicate_withdrawal_audit.py](duplicate_withdrawal_audit.py) (Apache-2.0), tests:
[test_duplicate_withdrawal_audit.py](test_duplicate_withdrawal_audit.py). Text CC BY 4.0.

## Why

Audit 13 ([GRADING-13.md](GRADING-13.md)) found 1,204 items that Crossref shows as withdrawn in
place. A publisher `withdrawal` link on the item's own record is the only retractive link
pointing at each of them, and Retraction Watch does not list them. OpenAlex flags only 4.7% of
them as retracted. In a hand check of 20 unflagged ones, 12 were Elsevier "WITHDRAWN:" records
whose article is live under a second DOI. Elsevier's policy allows an Article in Press to be
withdrawn when it is "discovered to be a duplicate of another published article due to an
editorial or production error". Crossref's documented remedy for duplicate DOIs is different: alias the duplicate to the
primary DOI, so that the old link resolves to the kept copy. If many `withdrawal` records are
really duplicates, two things follow. Readers and tools that treat `withdrawal` as "this work was
withdrawn" over-flag. And unless the metadata links the two DOIs, anyone who cites the withdrawn
DOI is not told where the article went.

## Nearest prior work and the delta

- Elsevier, Article withdrawal policy (elsevier.com/about/policies-and-standards/article-withdrawal):
  names duplication as a reason, with no counts.
- Retraction Watch, 2010 and 2013 posts on opaque Elsevier "Article in Press" withdrawals: examples,
  no counts.
- Crossref documentation on conflicts and aliasing (crossref.org/documentation/reports/conflict-report/)
  and the community post "The problem with duplicate DOIs": the remedy, with no census of
  withdrawn duplicates.
- Ortega & Delgado-Quiros, Scientometrics 2024: coverage of withdrawn literature across databases.
  It does not ask whether a withdrawal is a duplicate DOI.
- Searched 2026-11-11. We found no count of how many Crossref `withdrawal` records are duplicate
  DOIs, and no check of whether either record links the other.
- Delta: the first census of duplicate-DOI withdrawals in Crossref, and of whether the metadata
  points from the withdrawn DOI to the live copy.

## Population and method

- Input: [results/audit13/w_only.csv](results/audit13/w_only.csv), rows with `self_w` True
  (1,204 expected). For each target T, read its Crossref record (DOI batches of 20).
- Search: api.crossref.org/works?query.bibliographic=<T's title without the status mark, T's
  first author family name, T's journal>&rows=10. Judge each hit H. H is excluded if it is T, has
  a title marked retracted or withdrawn, carries any retractive `update-to`, or is a
  `peer-review` or `component` record. Otherwise it is a candidate if its normalised title equals
  T's (`exact`) or shares at least 80% of the title words (Jaccard >= 0.8).
- A candidate is a copy if the two author lists share a family name. If neither record lists
  authors, an exact title of 4 or more words is enough.
- Classes: `later_version` (a copy whose DOI is T's DOI plus a suffix, e.g. Cochrane `.pub2`);
  `duplicate` (a copy of the same Crossref type); `other_version` (a copy of another type, e.g. a
  preprint or proceedings paper); `title_clash` (an exact title but not a copy); `none`.
  "Duplicate" here means that the same work is live under another DOI of the same type. It
  includes superseded drafts whose final version keeps the title, and the results are reported by
  publisher.
- For each duplicate pair: `linked` (T's `relation` or `update-to` names H, or H's names T),
  `same_journal` (same normalised container title), and OpenAlex `is_retracted` for H.
- Outputs: summary.json, w_self_copies.csv (every target),
  grade20_duplicate.csv (the first 20 duplicates by sha256("a15g"|T)), and
  grade20_marked_none.csv (the first 20 title-marked targets with no copy found, by
  sha256("a15n"|T)).

## What we read before writing this (disclosed)

- The 20 hand-graded items in GRADING-13: 15 title-marked (11 duplicates, 1 probable, 3 genuine),
  5 not marked (3 NIST drafts, 2 unresolved). For 8 of the 11 duplicates the copy is in the same
  journal.
- Two test API calls made while writing the code. One was a bare title search for "pharmacogenetics
  of osteoporosis": its top 3 hits did not include the live copy, which is why the query adds author
  and journal. The other fetched the two control records, which carry no `relation`.
- **So P1, P2 and P5 are informed by about 20 items. P3, P4 and P6 are blind.**

## Gates (if a gate fails, P1-P6 are reported descriptively, not graded)

- G1: the input file downloads and has exactly 1,204 `self_w` rows.
- G2 (instrument check): 10.1016/j.beem.2014.05.003 is classed `duplicate` with copy
  10.1016/j.beem.2014.07.004, and 10.1016/j.matpr.2021.04.483 with copy 10.1016/j.matpr.2021.04.451.
- G3: at most 2% of record requests, of searches and of OpenAlex batches fail (each counted
  separately).
- G4: this file was live on GitHub before data were downloaded.

10.1016/j.jinf.2005.11.080 (graded genuine in GRADING-13) is reported as a check, not a gate.

## Predictions

- P1 (informed): 50-90% of title-marked w_self targets are `duplicate` (inconclusive below 30).
- P2 (informed): at least 60% of title-marked Elsevier BV w_self targets are `duplicate`.
- P3 (blind): at most 40% of w_self targets without a status mark are `duplicate`.
- P4 (blind): in at least 80% of duplicate pairs, neither record links the other.
- P5 (informed): in at least 50% of duplicate pairs, the copy is in the same journal.
- P6 (blind): OpenAlex `is_retracted` is true for at most 2% of the live copies it finds.
- P7 (hand grading, next step): of the 20 sampled duplicates, at least 18 are the same article
  (same or near-same title, a shared author, same or sister journal), as read from both Crossref
  records.
- P8 (hand grading, descriptive): of the 20 sampled title-marked targets with no copy found, how
  many have a copy that a manual title search does find. This measures the search's misses.

Grading will report every prediction as held, failed or not graded, with the numbers, including
failures. Anything found afterwards will be labelled post hoc. If P7 holds, the duplicate pairs
will be offered to Crossref as a list of aliasing candidates, through support@crossref.org.
