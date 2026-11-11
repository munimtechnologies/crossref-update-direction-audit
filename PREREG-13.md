# Pre-registration 13: does OpenAlex flag items that Crossref records only as withdrawn?

Written 2026-11-11 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before the audit job ran and
before any of its output existed. The job waits until this file is live on GitHub before it
downloads any data, and records the time it saw it (`plan_live_at`, `data_started`). Made with AI
agents working in MV2's name; no human has reviewed it. Code:
[withdrawal_flag_audit.py](withdrawal_flag_audit.py) (Apache-2.0), tests:
[test_withdrawal_flag_audit.py](test_withdrawal_flag_audit.py). Text CC BY 4.0.

## Why

Crossref has four retractive update types: `retraction`, `withdrawal`, `partial_retraction` and
`removal`. Retraction Watch counts withdrawals as retractions. Elsevier, for example, withdraws
articles in press and retitles them "WITHDRAWN: ...". OpenAlex exposes one boolean,
`is_retracted`. While grading audit 11 we noticed that OpenAlex flagged all 11 wrongly linked
papers whose wrong link is typed `retraction`, but none of the 9 whose wrong link is typed
`withdrawal` ([GRADING-11.md](GRADING-11.md)). If OpenAlex ignores `withdrawal` links in general,
then users who filter OpenAlex by `is_retracted` miss genuinely withdrawn items, unless Retraction
Watch also lists them.

## Nearest prior work and the delta

- Hauschke & Nazarovets, "(Non-)retracted academic papers in OpenAlex" (J. Inf. Sci.; arXiv
  2403.13339): OpenAlex over-flags. Corrections and expressions of concern become `is_retracted`.
  They do not report withdrawals going unflagged.
- Ortega & Delgado-Quiros, Scientometrics 2024 (s11192-024-05034-y): a coverage comparison of
  retracted literature across seven databases. OpenAlex and Scilit identify the most withdrawn
  literature. Their seed list is not restricted to items that only Crossref records.
- Tesseract Semantics, retraction register ontology (Aug 2026): of Retraction Watch DOIs found in
  OpenAlex, 0.11% are unflagged. That covers RW-listed items only.
- A DEV recall audit (2026) of 120 RW retractions: 115 of 120 flagged.
- Searched 2026-11-11 for OpenAlex withdrawals and unflagged Crossref withdrawals. Nothing found on
  items that only Crossref, and not Retraction Watch, records as withdrawn.
- Delta: the first census of OpenAlex's flag on Crossref-only withdrawals, compared with
  Crossref-only retractions as a control group.

## Population and method

- Every Crossref record matched by filter=update-type:X, X = retraction, withdrawal,
  partial_retraction, removal (cursor walk, deduplicated by DOI). For every target T of a
  retractive `update-to` link, collect the (type, source) pairs pointing at T, self-links
  included. Also note whether any Retraction Watch link of any type points at T.
- Groups: `w_only` (every retractive link to T is a publisher `withdrawal`, and no RW link);
  `w_self` (w_only targets whose own record carries that withdrawal link to itself, i.e. withdrawn
  in place); `r_only` (every retractive link is a publisher `retraction`, no RW link); `w_rw` (a
  publisher withdrawal link plus an RW link).
- OpenAlex `is_retracted` for every w_only and w_rw target, and for the first 3,000 r_only
  targets by sha256("a13r"|T), in batches of 50 DOIs. DOIs with characters that break the filter
  syntax are not asked; their number is reported.
- Outputs: summary.json, w_only.csv, w_rw.csv, r_only_sample.csv, and
  grade20_w_self_unflagged.csv (the first 20 found, unflagged w_self targets by
  sha256("a13g"|T)).

## What we read before writing this (disclosed)

- The 20 wrongly linked targets from audit 11 (11 typed retraction, all flagged; 9 typed
  withdrawal, none flagged).
- 15 `withdrawal` records from Crossref (most recently updated, read 2026-11-11) and OpenAlex for
  13 of their targets: 1 of 13 flagged. Seven of those 13 were withdrawn in place
  (self-linked), and none of those 7 was flagged.
- The two control records below.
- **So P3 and P4 are informed by about 33 items. P1, P2 and P6 are blind.**

## Gates (if a gate fails, P1-P6 are reported descriptively, not graded)

- G1: the walks for retraction and withdrawal complete.
- G2 (instrument check): 10.1016/j.cgh.2026.10.001 is `w_only` and self-linked,
  10.1053/j.gastro.2024.07.040 is `r_only`, and OpenAlex returns both.
- G3: at most 2% of OpenAlex batches fail.
- G4: this file was live on GitHub before data were downloaded.

## Predictions

- P1: 200-4,000 w_only targets.
- P2: OpenAlex finds at least 90% of w_only targets.
- P3 (informed): `is_retracted` is true for at most 20% of found w_self targets (inconclusive if
  fewer than 30 are found).
- P4 (informed): `is_retracted` is true for at least 90% of found sampled r_only targets
  (inconclusive if fewer than 100).
- P5: the r_only flag share minus the w_only flag share is at least 50 percentage points
  (inconclusive if P4 is, or if fewer than 30 w_only targets are found).
- P6 (blind): `is_retracted` is true for at least 80% of found w_rw targets: an RW record restores
  the flag (inconclusive if fewer than 30).
- P7 (hand grading, next step): of the 20 sampled unflagged w_self targets, at least 15 are
  genuinely withdrawn. That means their Crossref title is marked "WITHDRAWN" or their withdrawal
  notice says so. It does not count items whose "withdrawal" is really a version change or a
  duplicate DOI.

Grading will report every prediction as held, failed or not graded, with the numbers, including
failures. Anything found afterwards will be labelled post hoc. If the gap holds, it will be
reported to OpenAlex through its documented support channel.
