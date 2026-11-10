# Pre-registration 10: does PubMed link each retraction notice to the paper Retraction Watch names?

Written 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before the audit job ran and
before any of its output existed. The job waits until this file is live on GitHub before it
downloads any data, and records the time it saw it (`plan_live_at`, `data_started`). Made with AI
agents working in MV2's name; no human has reviewed it. Code:
[rw_pubmed_link_census.py](rw_pubmed_link_census.py) (Apache-2.0), tests:
[test_rw_pubmed_link_census.py](test_rw_pubmed_link_census.py). Text CC BY 4.0.

## Why

Two curated sources say which notice retracts which paper. The Retraction Watch database (RW,
published openly by Crossref since 2023) gives each retraction's `OriginalPaperPubMedID` (O) and
`RetractionPubMedID` (N). PubMed links the same two records itself: the notice says "Retraction
of" the paper, and the paper says "Retraction in" the notice. If the two sources name different
records, one of them is wrong. If RW's PMID is wrong, tools that join on it attach the retraction
to the wrong paper or miss it. If PubMed's link is wrong, a retracted paper can be left without
PubMed's "Retracted Publication" flag, while an unrelated paper gets it.

## Nearest prior work and the delta

- Schmidt (JASIST 2018, doi:10.1002/asi.23913): validity of retraction annotation in PubMed and
  Web of Science; found PubMed notices with no PMID link to the paper. Before RW was open data;
  no comparison of RW's PMID pairs with PubMed's links.
- Sebo & Sebo (Account Res 2025, doi:10.1080/08989621.2025.2484555) and the preliminary
  metadata study (PMID 39973475): coverage of RW, PubMed and Web of Science per field, and
  metadata errors (years, authors) in 35 retractions. Not link targets.
- Arjomandi, arXiv:2611.10474 (7 Nov 2026): 88.8% of RW papers with a PMID are flagged retracted
  in PubMed; compares flags, not which notice is linked to which paper.
- Tesseract Semantics, "Retraction register ontology" (Aug 2026): DOI-level agreement of
  Crossref, RW, OpenAlex and Europe PMC; no PMID-level link check.
- Our audit 5 (PREREG-5.md): publisher-deposited Crossref relations against PubMed, by DOI.
  Audit 10 uses RW's curated PMID pairs instead, which audit 5 never read.
- Delta: first census of whether PubMed links each RW notice PMID to the same paper PMID RW
  names, with a per-disagreement check of which source RW's own DOI and title support. Searched
  2026-11-10 (web search on PubMed/RW link mismatches; the four works above); none found.

## Population and method

- RW CSV from gitlab.com/crossref/retraction-watch-data (fallback: Crossref Labs API), read on
  the job's day. Rows with `RetractionNature` = "Retraction" (case-insensitive) whose two PMID
  fields are both a positive integer ("123" or "123.0"; blank and 0 mean none; anything else is
  counted as malformed and dropped). Rows with O = N are counted (`same_pmid`) and dropped. The
  unit is the distinct (O, N) pair.
- PubMed: E-utilities esummary (JSON, POST, batches of 200, tool and email set) for every O and
  N. A record links another when one of its `references` has the other's PMID, or quotes the
  other's DOI in its citation text. A link is retractive when its type starts "Retraction" or
  "Partial retraction", or says "Retracted and republished".
- Classes per pair, first that applies: `o_missing`, `n_missing`, `agree_both`,
  `agree_one_side`, `linked_other_type`, `n_targets_other` (N has retractive links, but only to
  other PMIDs), `o_linked_other` (O has retractive links only to other notices), `unlinked`.
  "Found pairs" are pairs with both records returned.
- For `n_targets_other`, the other target records T are fetched and two rules ask which paper
  RW's own `OriginalPaperDOI` and `Title` describe. DOI rule: T's DOI equals RW's DOI and O's
  does not => `rw_pmid_wrong`; O's equals and no T's does => `pubmed_link_suspect`; else
  `undetermined`. Title rule (word-set Jaccard, words of 3+ letters, "retracted/retraction/
  withdrawn/notice of" removed): T >= 0.6 and O < 0.3 => `rw_pmid_wrong`; O >= 0.6 and T < 0.3
  => `pubmed_link_suspect`; else `undetermined`.
- Outputs: summary.json; pairs_<class>.csv for every class except agree_both;
  grade20_n_targets_other.csv and grade20_unlinked.csv (first 20 by sha256("a10"|O|N) and
  sha256("a10u"|O|N)).

## What we read before writing this (disclosed)

- The RW column names and definitions on Crossref's documentation page.
- One control pair in PubMed, read by hand on 2026-11-10: paper 31662796 (Ther Adv Med Oncol
  2019, CELLFOOD) has "Retraction in" 34422117, and notice 34422117 has "Retraction of"
  31662796, both with DOIs in the citation. It became gate G4. Whether this pair is in RW is
  not known to us.
- No RW row was read and no RW-to-PubMed comparison was run. Audit 6 downloaded the RW CSV on
  2026-11-09 (73,688 rows), but used only its DOI fields. Every prediction below is blind: we had
  no pilot data and no idea of the rates beyond the prior work above.

## Gates (if a gate fails, P1-P8 are reported descriptively, not graded)

- G1: the RW CSV has >= 60,000 rows and the three needed columns.
- G2: >= 5,000 eligible pairs.
- G3: esummary failures (PMIDs in failed batches) <= 2% of PMIDs requested.
- G4 (instrument check): the control pair (31662796, 34422117) is classed `agree_both`.
- G5: this file was live on GitHub before data were downloaded.

## Predictions (blind to the job's output)

- P1: 8,000-30,000 eligible distinct pairs.
- P2: `agree_both` + `agree_one_side` >= 85% of found pairs.
- P3: `agree_one_side` <= 3% of found pairs (PubMed's links are nearly always two-way).
- P4: 20-600 `n_targets_other` pairs.
- P5: of `n_targets_other` pairs that a rule decides, `rw_pmid_wrong` is at least half, under
  the DOI rule AND under the title rule (inconclusive if either rule decides fewer than 5).
  Reason: RW's PMIDs are entered by curators, and earlier work found more metadata errors in RW
  than in PubMed.
- P6: >= 5 `pubmed_link_suspect` pairs under the DOI rule (PubMed's notice points at a paper
  that neither RW's DOI nor its PMID names).
- P7: `unlinked` >= 1% of found pairs.
- P8: of `unlinked` pairs, >= 30% have a paper that PubMed does not flag as retracted (no
  "Retracted Publication" type and no retractive "... in" link); inconclusive if fewer than 10.
- P9 (hand grading, next step): of the 20 sampled `n_targets_other` pairs (all, if fewer), at
  least 12 are judged "RW's PMID is wrong" (PubMed links the paper RW describes). Evidence per
  case: both PubMed records, the other target, RW's DOI and title, and the notice text where it
  can be read.

Grading will report every prediction as held, failed or not graded, with the numbers, including
failures. Anything found afterwards will be labelled post hoc. Disagreements found here will be
reported to the source that looks wrong (Crossref for RW data, NLM for PubMed) only after they
have been checked by hand.
