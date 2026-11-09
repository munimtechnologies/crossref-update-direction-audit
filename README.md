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
| 5 | does PubMed agree with every publisher-deposited retraction? | [PREREG-5.md](PREREG-5.md), job queued | pending |

## Check one paper: the retraction-crosscheck agent skill

[`skills/retraction-crosscheck`](skills/retraction-crosscheck/SKILL.md) turns these findings into
a check that coding agents (Claude Code, Codex, Cursor and others that read `SKILL.md` files) or
people can run on a DOI, a reference list or a `.bib` file:

```
python skills/retraction-crosscheck/scripts/retraction_crosscheck.py 10.1096/fj.09-135467
```

It reads the Crossref record and cross-checks any retraction against the notice's own title,
Retraction Watch's entries for the same notice, PubMed and the paper's title, then says
`retracted`, `retracted_unconfirmed`, `disputed`, `possibly_withdrawn` (and others) with the
reasons. A correction deposited as a retraction comes out `disputed` rather than retracted.
Python standard library only, read-only, no keys. Its live evaluation is pre-registered in
[eval/EVAL-1-PLAN.md](eval/EVAL-1-PLAN.md).

## Main findings so far

- **Corrections shown as retractions (audit 4 follow-up, post-hoc).** 17 papers that only
  received a correction are shown as retracted in Crossref and OpenAlex because the publisher
  deposited the correction notice with the update type `retraction`:
  [findings/corrections-deposited-as-retractions.md](findings/corrections-deposited-as-retractions.md).
  Audit 5 tests how common this is against PubMed.
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

- `PREREG.md`, `PREREG-2.md` ... `PREREG-5.md`: pre-registrations.
- `GRADING-1.md` ... `GRADING-4.md`: gradings.
- `results/audit1/` ... `results/audit4/`: outputs and hand-graded samples.
- `findings/`: write-ups of specific errors, each with a CSV.
- `update_direction_audit.py`, `reversed_relation_audit.py`, `pt_correction_audit.py`,
  `type_title_audit.py`, `notice_audit.py`, `pubmed_link_audit.py`: the audits (Python standard
  library only; read api.crossref.org, and for audit 5 PubMed and OpenAlex, no keys), each with
  a `test_*.py` unit-test file.
- `skills/retraction-crosscheck/`: the agent skill (`SKILL.md`, `scripts/`, `data/known_errors.csv`),
  tested by `test_retraction_crosscheck.py`; `eval/`: its live evaluation.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has reviewed this work. Code Apache-2.0; text and data CC BY 4.0.
