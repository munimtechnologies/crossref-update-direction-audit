# EVAL-2B plan: does retraction-crosscheck 0.2.0 stop trusting withdrawn corrections, without losing real retractions?

Written 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before job
`rcc-eval2b-pubmed-wc-v1` ran. Made with AI agents working in MV2's name; no human has reviewed
it. Code: [eval_skill_pubmed_b.py](../eval_skill_pubmed_b.py) (Apache-2.0), offline tests in
[test_eval_skill_pubmed_b.py](../test_eval_skill_pubmed_b.py). Text CC BY 4.0. The job waits until
this file and skill version 0.2.0 are both live on GitHub, records when it saw each, and only then
runs the skill.

## Why

[EVAL-2](EVAL-2-GRADING.md) confirmed that version 0.1.1 calls all 9 papers in set M `retracted`
although PubMed's only "Retraction in" notice for each is a withdrawn correction ("WITHDRAWN:
Corrigendum to ..."). Version 0.2.0 ([CHANGELOG](../skills/retraction-crosscheck/CHANGELOG.md))
reads the PubMed titles of those notices and counts PubMed's flag only if at least one notice is
not titled as a withdrawn or retracted correction. This plan tests that fix on the same 40 DOIs.

**How blind this is:** not blind. The same agents wrote 0.2.0, its offline tests (built from live
records of three M papers) and these predictions, and EVAL-2's raw output for all 40 DOIs was
read before writing them. What is not yet known is whether the fix works against live PubMed,
Crossref and OpenAlex for all 40, and whether the new rule touches any real retraction.

## Sets (unchanged from EVAL-2-PLAN.md)

- **M (9):** papers shown retracted in PubMed only via a withdrawn correction.
- **R (30):** real retractions reached through PubMed notices titled as an erratum or correction
  (13 "Retraction note. Erratum to: ..." and 17 from audit 9's random sample).
- **U (1, reported only):** 10.2174/1573405620666230809105544.

## Method

As in EVAL-2: download the live skill files from the main branch, run the repository's tests once,
run `retraction_crosscheck.py --file dois.txt --json --max 200` once on the 40 DOIs, and read each
verdict and `pubmed.flag_from_withdrawn_correction`.

## Gates

- G1: at least 36 of the 39 M+R DOIs come back with a verdict other than `not_found`,
  `lookup_failed` or empty, including at least 8 of the 9 M papers.
- G2: the live script reports version 0.2.0 and the repository's tests pass in the job.

If a gate fails, the predictions are reported but not graded.

## Predictions (version 0.2.0)

- F1: at least 8 of the assessed M papers get `disputed`.
- F2: at least 27 of the assessed R papers get `retracted`.
- F3: at most 1 assessed R paper gets `disputed`.
- F4: at least 8 of the assessed M papers have `flag_from_withdrawn_correction` true.
- F5: at most 1 assessed R paper has `flag_from_withdrawn_correction` true.

## Limits

One run on one day against live services; a PubMed request that fails for a notice title makes
the script fall back to the old rule for that paper, which would show up as an M paper staying
`retracted`. The sets come from our own audits, so this tests the fix on the cases that motivated
it, not on a random sample of papers.

MV2, Munim, Inc., mv2@munimtech.com
