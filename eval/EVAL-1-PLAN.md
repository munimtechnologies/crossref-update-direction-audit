# retraction-crosscheck: live evaluation 1 (plan, written before the run)

Written 2026-11-09 by AI agents working in MV2's (Munim, Inc.) name, before the evaluation job
(`retraction-crosscheck-eval1-v1`) ran. Licence: text CC BY 4.0, code Apache-2.0.

## What is tested

`skills/retraction-crosscheck` (v0.1.0) reads a DOI's Crossref record and cross-checks any
retraction against the notice title, Retraction Watch's own entries in Crossref, PubMed and the
paper's title. `eval/eval_live.py` fetches each DOI once and assesses it twice: **blind** (the
graded known-errors table switched off, so only live sources decide) and **with the table**.
It also records OpenAlex `is_retracted`, which is what a one-field checker would report.

DOIs (50): the 40 targets in `skills/retraction-crosscheck/data/known_errors.csv` (graded in
`findings/corrections-deposited-as-retractions.md` and `findings/iwa-withdrawn-as-addendum.md`),
6 widely reported genuine retractions and 4 widely cited papers not known to be retracted
(`eval/eval_dois.txt`).

## How blind this is

- P1 to P5 are **not blind**: the checker's rules were written from these very cases. They test
  whether live Crossref, PubMed and Retraction Watch still show the pattern on the day, and whether
  the code reads them correctly, not whether it generalises.
- P6 and P7 are the out-of-sample check, and they are small (10 DOIs, chosen by hand as famous
  cases, so they are easy ones).
- Before writing this plan, three live records were read by hand on 2026-11-09:
  10.1096/fj.09-135467 (Crossref, PubMed, OpenAlex), 10.1042/bsr20181233 and
  10.3341/kjo.2022.0089 (Crossref notice records, OpenAlex), 10.1016/s0140-6736(20)31180-6 and
  10.2166/wp.2021.019 (Crossref). Their fields are the test fixtures.

## Predictions (blind verdicts unless stated)

| # | Prediction |
|---|---|
| P1 | Of the 17 targets graded corrected (or wrong target), at least 15 are `disputed`. |
| P2 | OpenAlex `is_retracted` is true for at least 15 of those 17. |
| P3 | Both targets graded `shown_withdrawn_in_crossref_only` are `disputed`. |
| P4 | Both self-loop records are `self_loop_notice`. |
| P5 | At least 17 of the 19 IWA targets are `possibly_withdrawn`, and OpenAlex `is_retracted` is true for at most 2 of the 19. |
| P6 | At least 5 of the 6 genuine retractions are `retracted`, and none is `disputed`. |
| P7 | None of the 4 clean papers is flagged (verdict `corrected` or `no_notice`). |
| P8 | At most 3 of the 50 DOIs have a lookup problem. |

With the table switched on, every one of the 40 known targets should be flagged unless Crossref
has changed; any that is not will be reported by name.

Grading: each prediction as worded, every miss named with its record, in `eval/EVAL-1.md`.

MV2, Munim, Inc., mv2@munimtech.com
