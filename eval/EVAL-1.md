# retraction-crosscheck: live evaluation 1 (graded)

Graded 2026-11-09 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against
[EVAL-1-PLAN.md](EVAL-1-PLAN.md). Made with AI agents working in MV2's name; no human has
reviewed it. Text CC BY 4.0. Job `retraction-crosscheck-eval1-v1` ran skill v0.1.0 on
2026-11-09 15:28-15:30 UTC: 50 DOIs, each fetched once and assessed blind and with the
known-errors table. All 26 unit tests passed in the same job. Raw output:
[results/](results/) (eval.txt, eval.csv, eval.json, summary.json).

**Result: 7 of 8 predictions held.**

| # | Prediction | Result | Held? |
|---|---|---|---|
| P1 | >= 15 of 17 corrected / wrong-target papers `disputed` | 17 of 17 | **held** |
| P2 | OpenAlex is_retracted true for >= 15 of those 17 | 17 of 17 | **held** |
| P3 | both `shown_withdrawn_in_crossref_only` papers `disputed` | 2 of 2 | **held** |
| P4 | both self-loop records `self_loop_notice` | 2 of 2 | **held** |
| P5 | >= 17 of 19 IWA targets `possibly_withdrawn`, OpenAlex true for <= 2 | 13 of 19; OpenAlex 0 of 19 | **failed** (first part) |
| P6 | >= 5 of 6 genuine retractions `retracted`, none `disputed` | 6 of 6, none disputed | **held** |
| P7 | none of 4 clean papers flagged | 4 of 4 `no_notice` | **held** |
| P8 | <= 3 lookup problems | 0 | **held** |

The blind and with-table verdicts were identical for all 50 DOIs. Every one of the 40 known
targets was flagged.

## The miss (P5)

The six IWA records that got `retracted` instead of `possibly_withdrawn` come in three pairs:
10.2166/aqua.2024.007 and aqua.2024.063, aqua.2024.106 and aqua.2024.111, ws.2024.102 and
ws.2024.119. In each pair **both** records carry the title "Withdrawn: <same title>" and each one
lists the other as an `addendum`. The checker reads a paper title marked "Withdrawn:" as
independent evidence and says `retracted` (withdrawn). The plan expected the weaker
`possibly_withdrawn`. Both verdicts warn the user, so the miss changes the wording, not the
warning. Still, the rules were written from these cases and the prediction failed as worded.

## What it shows, and what it does not

- P1-P5 are not blind (the rules came from these cases). They show that live Crossref, PubMed and
  Retraction Watch still showed the pattern on 2026-11-09 and that the code reads them as
  intended.
- A one-field checker (OpenAlex `is_retracted`) called all 17 corrected papers retracted and
  missed all 19 IWA withdrawals. retraction-crosscheck flagged all 36.
- P6-P7 (10 famous DOIs) are a small, easy out-of-sample check. A real out-of-sample test needs
  cases the rules never saw. The 13 corrected papers found by hand in
  [GRADING-5.md](../GRADING-5.md) are the next test set.
- Not re-run under v0.1.1. Its one rule change concerns topic titles that start "Retraction of"
  or "Withdrawal of". One notice title in this set is affected: "Retraction of an
  interpretation", on the Wakefield paper (10.1016/s0140-6736(97)11096-0). That verdict also
  rests on a Retraction Watch retraction, the paper's own title and PubMed, so we expect no
  change, but this is untested.
