# Pre-registration 5: does PubMed agree with every retraction that publishers deposit in Crossref?

Written 2026-11-09 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before the audit job ran and
before any of its output existed. Made with AI agents working in MV2's name; no human has
reviewed it. Code: [pubmed_link_audit.py](pubmed_link_audit.py) (Apache-2.0), tests:
[test_pubmed_link_audit.py](test_pubmed_link_audit.py). Text CC BY 4.0.

## Why

[findings/corrections-deposited-as-retractions.md](findings/corrections-deposited-as-retractions.md)
found 17 papers that Crossref and OpenAlex show as retracted although they only got a correction:
the publisher deposited a correction notice with update type `retraction`. Those 17 were found
with a title rule (notice titled "Correction"/"Erratum"), which cannot see notices with other
titles ("Retractions and Errata", "Notice", the article's own title, no title).

This audit uses an independent curator instead of titles. PubMed's records carry their own
comment/correction links: a paper's record says "Retraction in <notice>" or "Erratum in
<notice>", and the citation text usually gives the notice DOI. For every publisher-deposited
retractive relation (notice N, target T) in Crossref, the job asks whether PubMed links the same
N to T, and how.

## Nearest prior work and the delta

- Tesseract Semantics, "Retraction register ontology" (August 2026): 20,458 DOIs that Crossref
  marks retracted are absent from Retraction Watch; the cause of that gap is not broken down,
  and no title or notice-level type check is made.
- Hauschke & Nazarovets, arXiv:2403.13339: OpenAlex flagged papers as retracted when Crossref's
  metadata was correct (an OpenAlex bug). Here the question is whether Crossref's own deposit is
  wrong.
- Si, Salami & Schneider (STI 2026): retraction notices indexed as retracted papers.
- Our audits 1-4 (this repo) and the 17-paper finding: title rules only.
- Delta: first notice-level, census-wide comparison of Crossref retractive update types with
  PubMed's typed links to the same notice. We searched for prior counts of corrections deposited
  as retractions on 2026-11-09 and found none.

## Population and method

- Crossref: every record matched by `filter=update-type:X` for X in retraction, withdrawal,
  partial_retraction, removal (deduplicated by DOI). Keep `update-to` entries whose type is one
  of those four and whose `source` is `publisher`, with target != notice (self-loops counted
  separately). Relations with `source` `retraction-watch` are only used to mark targets that
  Retraction Watch retracts.
- PubMed: each target DOI (only DOIs made of `a-z 0-9 . _ ( ) / -` are queried) is searched with
  `<doi>[doi]` in batches of 100 (E-utilities esearch, POST, tool and email set); then esummary.
  A PubMed link points at N when its citation text carries N's DOI, or when the linked PMID's
  own esummary DOI is N.
- Verdict per relation (first that applies): `not_in_pubmed`; `agree` (PubMed links N as
  "Retraction in" or "Partial retraction in"); `erratum_but_retracted` (PubMed links N as
  "Erratum in" but T is retracted in PubMed anyway); **`contradict`** (PubMed links N as "Erratum
  in", and T has no retraction link and no "Retracted Publication" type); `eoc`; `other_link`;
  `pm_retracted_elsewhere`; `pm_corrected_only` (N not linked, T has an "Erratum in" link and no
  retraction); `pm_silent`.
- For `contradict` targets: OpenAlex `is_retracted` and `cited_by_count`, and the Crossref title
  of T (is it retitled "RETRACTED"?).
- Outputs: summary.json, contradictions.csv, grade_contradictions20.csv (first 20 by
  sha256("a5"|notice|target), excluding the 10 known papers), erratum_but_retracted.csv,
  agree_sample20.csv.

## What we read before writing this (disclosed)

- Crossref counts on 2026-11-09: 81,485 records match `update-type:retraction` (largest
  publishers: Elsevier 20,551, Wiley 16,753, IEEE 12,184, Springer 11,876), 3,420 match
  `update-type:withdrawal`, 2 match `update-type:partial_retraction`.
- PubMed esummary for three of the 10 known papers: kjo.2022.0089 links its notice
  kjo.2022.0089.e1 as "Erratum in" with the DOI in the citation (will be `contradict`);
  fj.13-246579 links fj.13-246579ERR the same way; fj.09-135467's "Erratum in FASEB J 2010;
  24(2):648" has neither DOI nor PMID (will be `pm_corrected_only`, not `contradict`). And the
  retracted Lancet COVID-19 paper (PMID 32450107), which carries "Retraction in" links with DOIs.
  These reads shaped the validation gate (G2) and the field rules; no population-level PubMed
  result was seen.

## Gates (if a gate fails, P1-P8 are reported descriptively, not graded)

- G1: both the retraction and withdrawal walks complete, >= 80,000 records,
  `pubmed_phase_aborted` false and esearch failures <= 2% of queryable targets.
- G2 (instrument check): of the 10 known corrected-not-retracted papers, >= 8 get `contradict`
  or `pm_corrected_only`, and >= 5 get `contradict`.

## Predictions (blind to the job's output)

- P1: 40,000-70,000 publisher-deposited, non-self retractive relations.
- P2: between 25% and 60% of those relations have a target found in PubMed.
- P3: of relations where PubMed links the same notice (agree + contradict +
  erratum_but_retracted + eoc + other_link), at least 95% are `agree`.
- P4: 20-400 `contradict` relations.
- P5: at least 25% of `contradict` relations have a notice title that audit 4's correction rule
  does not catch (title class other than `correction`): the PubMed check finds cases titles miss.
- P6: Wiley is the publisher with the most `contradict` relations.
- P7: OpenAlex `is_retracted` is true for at least 90% of `contradict` targets it returns.
- P8: at most 25% of `contradict` relations have a Retraction Watch retraction of the target.
- P9 (hand grading, next step): of the 20 sampled `contradict` relations (all, if fewer), at
  least 14 are judged corrected-not-retracted (Crossref wrong) and at most 3 are judged real
  retractions that PubMed mislinked. Evidence per case: notice text where readable, PubMed
  record, Retraction Watch, target title.

Grading will report every prediction as held, failed or not graded, with the numbers, including
failures, and will label anything found afterwards as post hoc.
