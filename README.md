# crossref-update-direction-audit

Do Crossref's correction and retraction links point the right way, and do they say what they are?

Crossref records an erratum, correction or retraction as a link on the **notice**: the
notice's record says `update-to: <the work it corrects>`, and Crossref then shows the work as
`updated-by` the notice. Tools that flag corrected or retracted papers read these links.
Each audit here is pre-registered before it runs, and every prediction is graded, including
the ones that fail.

| Audit | Question | Graded | Predictions held |
|---|---|---|---|
| 1 | notices dated before their targets | [GRADING-1.md](GRADING-1.md) | 2 of 7 |
| 2 | reversed links (article points at its own notice), found from titles | [GRADING-2.md](GRADING-2.md) | 2 of 5 |
| 3 | *Physics Today* back-file correction links | [GRADING-3.md](GRADING-3.md) | 6 of 8 |
| 4 | retraction and withdrawal notices typed as something else | [GRADING-4.md](GRADING-4.md) | 6 of 8 |

## Main findings so far

- **Hidden retractions (audit 4).** Across all 488,117 Crossref records with `update-to`,
  9,314 publisher links come from notices titled as retractions or withdrawals but typed
  `erratum`, `correction`, `addendum` or `new_edition`. Most are still recorded as retracted
  some other way. About 220-320 pairs (25 publishers) have no retraction anywhere in Crossref's
  update metadata. IWA Publishing's 16 withdrawn papers, typed `addendum`, are one example:
  [findings/iwa-withdrawn-as-addendum.md](findings/iwa-withdrawn-as-addendum.md). Elsevier's
  "Retraction notice to Corrigendum ..." notices and SAGE's "Administrative Duplicate
  Publication" withdrawals are others. A notice-level recount (post-hoc, not pre-registered)
  is queued.
- **Reversed links (audits 1-2).** 876 links run from an article to its own notice. About 65%
  of a hand sample are true reversals (*Nature* journals, Rockefeller UP, Medknow, IWA, AIP and
  others). Most of Elsevier's share is a different pattern: a republished corrected copy. OpenAlex
  still marks every sampled original as retracted.
- **Scrambled back file (audit 3).** In the 2007-2009 *Physics Today* back-file deposit, 26.5%
  of correction links point at items printed **after** the correction column. That never
  happens in the notices deposited when printed, nor (0.27%) elsewhere in AIP Publishing.

## Files

- `PREREG.md`, `PREREG-2.md`, `PREREG-3.md`, `PREREG-4.md`: pre-registrations.
- `GRADING-1.md` ... `GRADING-4.md`: gradings.
- `results/audit1/` ... `results/audit4/`: outputs and hand-graded samples.
- `update_direction_audit.py`, `reversed_relation_audit.py`, `pt_correction_audit.py`,
  `type_title_audit.py`, `notice_audit.py`: the audits (Python standard library only; read
  api.crossref.org, no keys), each with a `test_*.py` unit-test file.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has reviewed this work. Code Apache-2.0; text and data CC BY 4.0.
