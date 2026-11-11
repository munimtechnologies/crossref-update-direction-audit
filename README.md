# crossref-update-direction-audit

Do the scholarly record's correction and retraction links point at the right paper, and do they say what they are?

Crossref records an erratum, correction or retraction as a link on the **notice**: the
notice's record says `update-to: <the work it corrects>`, and Crossref then shows the work as
`updated-by` the notice. PubMed and the Retraction Watch database (RW, now published openly by
Crossref) keep their own links. Tools that flag corrected or retracted papers read all three.
Each audit here is pre-registered before it runs, and every prediction is graded, including the
ones that fail.

| Audit | Question | Plan | Grading |
|---|---|---|---|
| 1 | notices dated before their targets | [PREREG.md](PREREG.md) | [GRADING-1.md](GRADING-1.md): 2 of 7 held |
| 2 | reversed links (article points at its own notice) | [PREREG-2.md](PREREG-2.md) | [GRADING-2.md](GRADING-2.md): 2 of 5 held |
| 3 | *Physics Today* back-file correction links | [PREREG-3.md](PREREG-3.md) | [GRADING-3.md](GRADING-3.md): 6 of 8 held |
| 4 | retraction and withdrawal notices typed as something else | [PREREG-4.md](PREREG-4.md) | [GRADING-4.md](GRADING-4.md): 6 of 8 held |
| 5 | does PubMed agree with publisher-deposited retractions? | [PREREG-5.md](PREREG-5.md) | [GRADING-5.md](GRADING-5.md) |
| 6 | retractions that no index flags | [PREREG-6.md](PREREG-6.md) | [GRADING-6.md](GRADING-6.md): 7 of 9 held |
| 7 | papers shown as retracted because a correction of theirs was withdrawn | [PREREG-7.md](PREREG-7.md) | [GRADING-7.md](GRADING-7.md): 7 of 8 held |
| 8 | does PubMed repeat audit 7's error? | [PREREG-8.md](PREREG-8.md) | [GRADING-8.md](GRADING-8.md): descriptive (two gates failed) |
| 9 | PubMed retraction notices titled as corrections | [PREREG-9.md](PREREG-9.md) | [GRADING-9.md](GRADING-9.md) |
| 10 | does PubMed link each notice to the paper RW names? | [PREREG-10.md](PREREG-10.md) | [GRADING-10.md](GRADING-10.md): 6 of 9 held |
| 11 | do the publisher and RW name the same paper for the same Crossref notice? | [PREREG-11.md](PREREG-11.md) | [GRADING-11.md](GRADING-11.md): 3 held, 2 failed, 4 not graded |
| 12 | how many RW PubMed IDs have their last digit cut off? | [PREREG-12.md](PREREG-12.md) | job queued |
| 13 | does OpenAlex flag items that Crossref records only as withdrawn? | [PREREG-13.md](PREREG-13.md) | job queued |
| 14 | which RW DOIs are not registered DOIs at all, and which DOI was meant? | [PREREG-14.md](PREREG-14.md) | job queued |

## Main findings so far

- **Publisher retraction links that point at the wrong paper (audit 11, post hoc).** At least 19
  publisher-deposited retraction or withdrawal links in Crossref name an item that was never
  retracted. Examples: a withdrawn letter linking the article it comments on, a one-digit DOI
  typo, an Expression of Concern, and an unrelated paper. OpenAlex shows all 11 whose wrong link
  is typed `retraction` as retracted, and none of the 9 typed `withdrawal`:
  [findings/publisher-retraction-links-to-wrong-paper.md](findings/publisher-retraction-links-to-wrong-paper.md).
  Publisher and RW otherwise almost always agree: only 36 of 27,845 notices that carry both
  sources name different papers.
- **Retraction Watch PubMed IDs with the last digit cut off (audit 10, post hoc).** 34 RW rows
  carry the correct PMID minus its final digit, so they point at unrelated papers from the 1970s
  to the 1990s: [findings/rw-truncated-pubmed-ids.md](findings/rw-truncated-pubmed-ids.md).
  Audit 12 counts them across the whole database. Audit 11 found the same kind of error in RW
  DOIs, for example 10.1177/014616720026200 for 10.1177/0146167200262008, and audit 14 counts
  unregistered RW DOIs across the whole database.
- **PubMed notices linked to the wrong record (audit 10).** In at least three cases PubMed links a
  retraction notice to another paper or to an Expression of Concern, so the retracted paper is not
  flagged ([GRADING-10.md](GRADING-10.md)). Across 28,365 pairs, RW and PubMed agree 97.7% of the
  time.
- **Withdrawn corrections make papers look retracted (audits 7-8).** 69 papers, almost all
  Elsevier, are shown as retracted or withdrawn in Crossref only because a correction of theirs
  was withdrawn. OpenAlex repeats it for 48 of them, and PubMed shows 9 papers as retracted
  for the same reason (a withdrawn correction indexed as the retraction notice)
  ([findings/retracted-corrections-flip-papers.md](findings/retracted-corrections-flip-papers.md),
  [findings/pubmed-shows-withdrawn-corrigenda-as-retractions.md](findings/pubmed-shows-withdrawn-corrigenda-as-retractions.md)).
  Europe PMC mirrors PubMed here. The 9 records were reported to the NLM on 2026-11-10.
- **Corrections shown as retractions (audit 4 follow-up).** 17 papers that only received a
  correction are shown as retracted, because the correction was deposited with the type
  `retraction`
  ([findings/corrections-deposited-as-retractions.md](findings/corrections-deposited-as-retractions.md)).
- **Hidden retractions (audit 4).** 9,314 publisher links come from notices titled as
  retractions or withdrawals but typed `erratum`, `correction`, `addendum` or `new_edition`, for
  example IWA Publishing's withdrawn papers
  ([findings/iwa-withdrawn-as-addendum.md](findings/iwa-withdrawn-as-addendum.md)).
- **Reversed links (audits 1-2)** and a **scrambled back file (audit 3)**: see the gradings.

## Check one paper: the retraction-crosscheck agent skill

[`skills/retraction-crosscheck`](skills/retraction-crosscheck/SKILL.md) turns these findings into
a check that coding agents (Claude Code, Codex, Cursor and others that read `SKILL.md` files) or
people can run on a DOI, a reference list or a `.bib` file:

```
python skills/retraction-crosscheck/scripts/retraction_crosscheck.py 10.1096/fj.09-135467
```

It reads the Crossref record and cross-checks any retraction against the notice's own title,
Retraction Watch's entries for the same notice, PubMed and the paper's title. It then answers
`retracted`, `retracted_unconfirmed`, `disputed`, `possibly_withdrawn` and others, with the
reasons. Version 0.2.0 no longer trusts PubMed's flag when PubMed's only "retraction" is a
withdrawn correction. Its pre-registered live evaluations are in [eval/](eval/), and
[eval/EVAL-2B-GRADING.md](eval/EVAL-2B-GRADING.md) confirmed the fix (all 5 predictions held).

## Files

- `PREREG.md`, `PREREG-2.md` ... `PREREG-14.md`: pre-registrations. `GRADING-1.md` ...
  `GRADING-11.md`: gradings. `results/auditN/`: raw outputs and hand-graded samples.
- `findings/`: write-ups of specific errors, each with its evidence.
- One Python script per audit (standard library only; reads api.crossref.org, doi.org, PubMed
  E-utilities, OpenAlex or the RW CSV, no keys), each with a `test_*.py` unit-test file.
- `skills/retraction-crosscheck/`: the agent skill; `eval/`: its evaluations.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has reviewed this work. Code Apache-2.0; text and data CC BY 4.0.
