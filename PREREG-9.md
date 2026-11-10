# Pre-registration 9: PubMed retraction notices that are really about corrections

Written 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before job
`pubmed-corr-notices-a9-v1` ran. Made with AI agents working in MV2's name; no human has
reviewed it. Code: [pubmed_correction_notice_census.py](pubmed_correction_notice_census.py)
(Apache-2.0), offline tests in
[test_pubmed_correction_notice_census.py](test_pubmed_correction_notice_census.py). Text CC BY 4.0.
The job waits until this file is live on GitHub before it reads PubMed and records when it saw it.

## Question

Audit 8 ([GRADING-8.md](GRADING-8.md)) found six papers that PubMed types "Retracted
Publication" only because a withdrawn corrigendum of theirs is indexed as a "Retraction Notice"
and linked to the paper as "Retraction in". Those six were found from the Crossref side and are
all Elsevier. How common is this across PubMed, for every publisher?

## Method

1. PubMed E-utilities search, run once:
   `"retraction notice"[pt] AND (corrigendum[ti] OR erratum[ti] OR correction[ti])`.
2. Read every hit's summary. Class each notice by its title (lower-cased, quotes and brackets
   removed):
   - **WC**: the record is itself a withdrawn or retracted correction ("WITHDRAWN: Corrigendum to ...").
   - **RNC**: a retraction or withdrawal notice of a correction ("Retraction notice to
     'Corrigendum to ...'", "Retraction: Correction: ...").
   - **C**: titled as a bare correction ("Erratum: ...").
   - **OTHER**: anything else (for example a paper titled "Correction of ...").
   S = WC + RNC.
3. Read every "Retraction of" target. A target is a **correction record** if PubMed types it
   "Published Erratum" or its title starts like a correction; otherwise it is a **paper**.
4. For each paper reached from an S or C notice, read all of its "Retraction in" notices. The
   paper is **only via correction** if PubMed types it "Retracted Publication" and every one of its
   "Retraction in" notices is WC, RNC or C (a notice we could not read counts against).
5. OpenAlex `is_retracted` for the only-via-correction papers with a DOI.
6. A seeded sample (Python `random.Random(9)`) of 20 only-via-correction papers goes to
   grade20.csv for a hand check.

## What we read before writing this (disclosed)

- On 2026-11-10 the search above returned 279 records; we saw the first 200 PMIDs.
- We read the titles, types and "Retraction of" PMIDs (not the targets) of 10 of them: PMIDs
  42953414, 42837705, 42810896, 42707976, 42665524, 42660801, 42632799, 42620807, 42583177,
  42527287. By our rules 9 are RNC (Frontiers "Retraction: Correction/Corrigendum: ...", Elsevier
  "Retraction/Withdrawal notice to 'Corrigendum to ...'") and 1 is C.
- The six audit-8 notices (PMIDs 27852510, 30449593, 39645442, 41422828, 42420052, 42441098)
  are in the result. All six are WC and link to the paper; they are the G3 instrument check.
- We have not looked at the targets of any other notice.

## Gates (if one fails, the predictions are reported descriptively, not graded)

- G1: the search returns at least 250 records, all IDs are returned, and at least 98% are read.
- G2: at most 2% of "Retraction of" targets cannot be read.
- G3: each of the six instrument notices comes out WC, linked to its paper, and the paper comes
  out only via correction.

## Predictions

- P1: at least 75% of the notices read are S (WC or RNC).
- P2: of S notices with at least one readable target, at least 50% link at least one paper
  (not the correction) as "Retraction of".
- P3: of WC notices with a readable target (at least 5 needed), at least 90% link a paper.
- P4: at least 20 distinct papers are only via correction.
- P5: at least 60% of only-via-correction papers with a DOI have an Elsevier DOI (10.1016/).
- P6: of only-via-correction papers found in OpenAlex (at least 10 needed), at least 30% have
  `is_retracted: true`.
- P7 (hand-graded from grade20.csv): at least 15 of the 20 sampled papers show no sign of a real
  retraction (no retraction notice of their own in PubMed or Crossref, no "RETRACTED" title, no
  Retraction Watch entry).

`grade()` in the code grades the gates and P1-P6 exactly as worded; P7 is graded by hand.

## Prior work

Schneider, Lee, Zheng and Salami (STI 2023 preprint) hand-checked 201 DOIs indexed as retracted
across Crossref, Retraction Watch, Scopus and Web of Science and found 14 (6.97%) to be
non-retracted papers with a correction; they did not study PubMed or the mechanism. Our audits
7 and 8 found the mechanism from the Crossref side. We found no PubMed-side census of retraction
notices that are about corrections.

## Limits

Title search only: notices titled "Corrigenda", "Errata" or "Correcting ..." without the three
words, and correction notices PubMed did not type "Retraction Notice", are missed. Titles are
classed by rule, not read. One reading on one day. Being "only via correction" is a signal, not
proof, that a paper is not retracted; P7 checks it by hand.
