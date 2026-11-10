# Pre-registration 11: do the publisher and Retraction Watch name the same paper for the same retraction notice?

Written 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before the audit job ran and
before any of its output existed. The job waits until this file is live on GitHub before it
downloads any data, and records the time it saw it (`plan_live_at`, `data_started`). Made with AI
agents working in MV2's name; no human has reviewed it. Code:
[source_target_audit.py](source_target_audit.py) (Apache-2.0), tests:
[test_source_target_audit.py](test_source_target_audit.py). Text CC BY 4.0.

## Why

Since 2023 Crossref has added the Retraction Watch database (RW) to its API. A notice's Crossref
record can therefore carry two kinds of retractive `update-to` link: the links its publisher
deposited (`source: publisher`) and the links Crossref added from RW (`source:
retraction-watch`). Both say "this notice retracts that paper". When the two name different
papers, at least one is wrong, and every tool that reads it shows an innocent paper as retracted
or misses the retracted one.

One case we read by hand on 2026-11-10: the Fertility and Sterility notice
10.1016/s0015-0282(16)58061-3 ("Correction to: Friedman AJ, Hornstein MD: Gonadotropin-releasing
hormone agonist plus estrogen-progestin 'add-back' therapy ...", RW record 3505) has a publisher
`retraction` link to 10.1016/s0015-0282(16)56091-9, the next article in the issue (a clomiphene
challenge-test study), and an RW `retraction` link to 10.1016/s0015-0282(16)56090-7, the paper the
notice names. Crossref, and tools that read it, show the clomiphene study as retracted. This case
is the instrument check (G2) and is excluded from the hand-graded samples.

## Nearest prior work and the delta

- Tesseract Semantics, "Retraction register ontology" (data from Aug 2026): Crossref publisher
  deposits and RW "agree on 72.42 per cent of the retracted DOIs"; set overlap of flagged DOIs,
  notices mislabelled as research, self-referential deposits (25.73%). It does not compare which
  paper each source links to the same notice.
- Our audit 6 (PREREG-6.md): matched RW only by OriginalPaperDOI, at the paper level.
- Our audit 10 (PREREG-10.md, queued): RW's PubMed ID pairs against PubMed's own links; no
  Crossref links.
- hherb/bmlib issue #504 (GitHub, Oct 2026): notes that the same retraction can arrive from
  several sources under different notice DOIs; no census of target disagreement.
- Searched 2026-11-10: web searches on publisher versus RW targets of the same notice, wrong-target
  retraction deposits and DOI typos in retraction links. None found.
- Delta: first census of notice-level target disagreement between publisher deposits and RW
  inside Crossref, with a title check of which side the notice describes, a DOI edit-distance
  check of the typo mechanism, and a check of whether the other paper is retracted at all.

## Population and method

- Every Crossref record matched by filter=update-type:X, X = retraction, withdrawal,
  partial_retraction, removal (cursor walk, deduplicated by DOI). For each record N: P = targets of
  its publisher-sourced retractive links, R = targets of its RW-sourced retractive links, both
  without N itself. Records with neither are not notices here.
- Sides: `agree` (P = R), `overlap` (share a target, differ otherwise), `disjoint` (share none),
  `publisher_only`, `rw_only`. "Two-source notices" = agree + overlap + disjoint.
- Titles of every target of overlap, disjoint and publisher-only notices, and of a sample of 5,000
  agree notices (first by sha256("a11a"|N)), from Crossref (filter=doi batches of 20).
- Title rule: words of 3+ characters, ASCII-folded, lower case, tags, digits-only words and a
  fixed list of boilerplate and function words removed (in the code). Containment of target T in
  notice N = share of T's words found in N's title; undefined if either has fewer than 4 words.
- Verdict for a disjoint notice (best containment over P = cp, over R = cr): `rw_right` if
  cr >= 0.6 and cp < 0.3; `publisher_right` if cp >= 0.6 and cr < 0.3; `both_match` if both
  >= 0.6; else `undetermined` (also when either is undefined).
- `near`: the closest P and R DOIs differ by at most 2 edits (Levenshtein).
- Other evidence for the target the title does not describe: an RW link to it from any notice, a
  publisher link from another notice, a self-link, or a title marked RETRACTED/WITHDRAWN.
- OpenAlex `is_retracted` for the P targets of rw_right notices and the R targets of
  publisher_right notices.
- Outputs: summary.json, disjoint.csv, overlap.csv, grade20_disjoint.csv (first 20 by
  sha256("a11"|N)), publisher_only_mismatch.csv (informative publisher-only notices with
  containment < 0.2), grade20_publisher_only_mismatch.csv (sha256("a11p"|N)),
  agree_sample_mismatch.csv.

## What we read before writing this (disclosed)

- The control notice and its two targets in live Crossref (titles, update-to), 2026-11-10.
- Totals from our audit 7 job (2026-11-09): 85,056 records in the same walk, with 63,743
  publisher and 59,407 RW retractive update-to entries, and 18,500 records with a publisher
  self-link. We never split those entries by notice or compared P with R.
- Crossref's blog example 10.1177/17588359231172420, whose RW entry appears to point at the notice
  itself (not checked live). No other notice was read. Every prediction below is blind.

## Gates (if a gate fails, P1-P7 are reported descriptively, not graded)

- G1: the walks for retraction and withdrawal complete.
- G2 (instrument check): the control notice is `disjoint` with verdict `rw_right`.
- G3: titles could not be requested for at most 2% of the target DOIs (failed batches).
- G4: this file was live on GitHub before data were downloaded.

## Predictions (blind to the job's output)

- P1: 10,000-45,000 two-source notices.
- P2: `disjoint` is 0.2%-3% of two-source notices.
- P3: of disjoint notices decided as rw_right or publisher_right, rw_right is at least 50%
  (inconclusive if fewer than 5 are decided). Reason: RW curators read the notice; a publisher
  deposit can carry a typo.
- P4: at least 50% of rw_right notices are `near` (inconclusive if fewer than 5): the typical
  error is a mistyped or neighbouring DOI.
- P5 (calibration of the title rule): among informative sampled agree notices, at least 90% have
  containment >= 0.6 and at most 3% below 0.2 (inconclusive if fewer than 100 are informative).
- P6: at most 2% of informative publisher-only notices have containment < 0.2 (inconclusive if
  fewer than 100).
- P7: OpenAlex marks at least 80% of rw_right publisher targets as retracted (inconclusive if
  fewer than 5 are found): an innocent paper is flagged downstream too.
- P8 (hand grading, next step): of the 20 sampled disjoint notices (all, if fewer), the hand
  verdict (which paper the notice really retracts, from both targets' records and the notice
  text where it can be read) matches the automated verdict in at least 80% of those the rule
  decided.
- P9 (hand grading): of the 20 sampled publisher-only mismatches, at least 10 are real wrong
  targets (the notice names a different paper than the one it links).

Grading will report every prediction as held, failed or not graded, with the numbers, including
failures. Anything found afterwards will be labelled post hoc. Confirmed wrong targets will be
reported, after a hand check, to the source that looks wrong: the publisher or Crossref for
publisher deposits, and Crossref's Retraction Watch team for RW data.
