# Grading 1: Crossref update-direction audit 1

Graded 2026-11-08 by AI agents working in MV2's name (MV2, Munim, Inc., mv2@munimtech.com)
against [PREREG.md](PREREG.md), written before the job ran. No human has reviewed this grading.
Text CC BY 4.0, code Apache-2.0.

**Result: the gate passed and 2 of 7 predictions held (P1, P6). P2, P3, P4, P5 and P7 failed.**
The main lesson is a failure of the method: a notice dated before its target is a weak signal.
Half of the hand-graded flags were date artefacts, not wrong relations. The real errors in the
sample were mostly **reversed relations** (the original article carries `update-to` pointing
at its own erratum or retraction notice), and they come from many publishers, not mainly from
Springer Nature as predicted. A follow-up audit that finds reversed relations without using
dates is pre-registered in [PREREG-2.md](PREREG-2.md).

## The run

Job `crossref-update-dir1-v1`, 2026-11-07 22:35-23:16 UTC, 1 CPU, peak 1.3 GB, 23/23 unit tests
passed. Crossref API only.

| | |
|---|---|
| Records with `is-update:true` read (cursor walk complete) | 488,114 |
| `update-to` relations | 573,385 |
| Self relations (target = the record itself) | 77,875 |
| Relations of other update types (new_version, new_edition, ...) | 25,442 |
| Distinct targets of non-self notice-type relations | 418,464 |
| ... found in Crossref with a date | 418,362 (99.98%) |
| Notice-type relations judged **ok** | 467,612 |
| ... **predates** (notice >31 days before its target) | 2,347 |
| ... target missing / undated | 86 / 23 |

Files: [summary.json](results/audit1/summary.json),
[publisher_table.csv](results/audit1/publisher_table.csv),
[predates_top200_by_citations.csv](results/audit1/predates_top200_by_citations.csv),
[grade_predates40_graded.csv](results/audit1/grade_predates40_graded.csv),
[self_relations.csv](results/audit1/self_relations.csv); all 2,347 flags in
[predates.csv](results/audit1/predates.csv).

## Predictions

| | Prediction | Result | |
|---|---|---|---|
| G | Walk complete, >=450,000 records, >=90% of targets dated | 488,114 records, 99.98% dated | **passed** |
| P1 | >=500 notice-type relations predate their target | 2,347 | **held** |
| P2 | Springer Nature (member 297) deposited at least half | 506 of 2,347 (21.6%) | **failed** |
| P3 | Member 297's predating rate >=3x everyone else's | 0.37% vs 0.56% (0.66x) | **failed** |
| P4 | >=28 of 40 sampled flags are relation errors (hand-graded) | 12 sure, 19 at most with likely cases, 20 if the unclear one counts | **failed** |
| P5 | >=50% of targets with references cite the "notice" | 173 of 1,312 (13.2%) | **failed** |
| P6 | Share of "notices" with 10+ citations >=5x higher among predating than ok | 15.6% vs 2.1% (7.3x) | **held** |
| P7 | >=80% of predating 10.1038 notices are from before 2010 | 98 of 142 (69.0%) | **failed** |

P2, P5 and P7 were shaped by four Springer Nature records read before the pre-registration
(disclosed there). They tested whether that pattern generalises. It does not: the pattern is
real, but Springer Nature is one source among many.

## P4: what the 40 sampled flags are

The 40 flags with the lowest sha256("notice|target") were checked against the titles, pages and
citation counts in the job's output. 10 were also re-read in full from the Crossref API on
2026-11-08, and one (Fehr & Gachter) had been read before the pre-registration (`how_checked`
column). Publisher landing pages were not read.

| Grade | n | Counts as a relation error? |
|---|---|---|
| Date artefact: a real notice about the right work, but one of the two dates is wrong or is a later print-issue date | 20 | no (P4 rules) |
| **Reversed**: the original article carries `update-to` pointing at its own correction or retraction notice | 7 | yes |
| Comment labelled as erratum: Fehr & Gachter 2002 points at a 2005 comment on it | 1 | yes |
| Withdrawn article points at the surviving copy (a translation, or a "Reprint of") | 2 | yes |
| Unrelated target (a 1999 correction points at a 2012 maths chapter; a 1978 JBC corrections page points at a 1994 paper) | 2 | yes |
| Physics Today "Corrections" page points at an item in a *later* issue | 7 | likely; the target's issue data could also be wrong |
| Unclear (a record with the article's own title carrying erratum links to the article and to its erratum) | 1 | unclear |

12 sure errors, 19 with the Physics Today cases, 20 at the most. The prediction needed 28, so
it fails whatever the uncertain cases are.

Why the date rule misleads: Crossref's `issued` date is the earliest of the print and online
dates, and many records deposit only a print date. A notice published online in July but placed
in the September issue gets September, while the article it corrects may carry a December issue
date. Twelve of the twenty date artefacts are Elsevier or Elsevier-hosted corrigenda whose
targets carry a later print date. Of the other eight, four notices carry a wrongly early date
(an erratum dated May for an article in the September issue; a retraction notice created in
2021 but dated 2019), two targets carry a later print-issue date, one target has a wrong print
date, and one conference withdrawal is dated by the conference.

## What the flags with the most citations are

Sorting the 2,347 flags by the citations of the record carrying `update-to` picks out the
reversed relations: the record that carries the link is a well-cited original paper, and the
target is its own correction. For example:

- 10.1038/415137a, Fehr & Gachter, *Nature* 2002 (4,015 citations) -> a 2005 comment.
- 10.1016/S0140-6736(20)32656-8, *Lancet* 2021, "RETRACTED: 6-month consequences of COVID-19..."
  (3,716) -> "Retraction and republication: 6-month consequences...".
- 10.1038/nri910, "NF-kB regulation in the immune system" (3,432) -> "Erratum: NF-kB regulation...".
- 10.1038/415092a, IRE1 / XBP-1 (2,601) -> "Correction: Corrigendum: IRE1 couples...".
- 10.1038/21218, Akt / nitric oxide (2,213) -> "Erratum: Regulation of endothelium-derived...".
- Rockefeller University Press (*JEM*, *JCB*, *JGP*): originals with 400-1,100 citations point at
  their "Correction" notes. Rockefeller has the highest predating rate of any depositor with 500 or
  more dated relations (130 of 846, 15.4%).
- Wolters Kluwer / Medknow (10.4103), the American Society of Hematology and IWA Publishing show
  the same pattern.

In a reversed relation, Crossref shows the *notice* as "updated-by" the original. So for
reversed retractions, the retraction notice looks like the retracted work, and the retracted
paper carries no `updated-by` retraction at all. Si, Salami and Schneider (STI 2026,
[10.5281/zenodo.22656294](https://doi.org/10.5281/zenodo.22656294)) found that 661 of 925 DOIs
listed as retracted only in Crossref were really retraction notices. Their abstract does not
give a cause. Reversed relations are one possible cause; audit 2 counts how many notices look
retracted for that reason.

## Other things seen (descriptive, not predicted)

- 77,875 self relations (13.6% of all relations). The largest groups are PLOS new versions
  (22,732), Elsevier retractions (14,042) and IEEE retractions from the Retraction Watch data
  (7,645); see self_relations.csv. Tesseract Semantics (August 2026) reports self-referential
  retraction assertions at 25.73% of Crossref's retractive assertions; this is consistent with
  that.
- Update types outside Crossref's list include `retracion`, `retration`, `68818`,
  `this_is_some_update_23` and `sample_update` (also reported by Tesseract Semantics).
- 172 of the 2,347 flags come from Crossref's Retraction Watch data, not from publishers.

## Prior work (re-checked 2026-11-08)

Nothing found that counts reversed or time-travelling `update-to` relations. Nearest:
Si, Salami & Schneider 2026 (notices indexed as retracted in Crossref; no mechanism given in the
abstract); Tesseract Semantics, "Retraction register ontology" (August 2026: register
disagreement, self-referential notices, OpenAlex flagging 94.5% of Retraction Watch notice DOIs
as retracted); Hauschke & Nazarovets, arXiv:2403.13339 (OpenAlex read all updates as retractions);
Crossref's Crossmark documentation (the notice carries the update; Crossref adds `updated-by`).

## Limits

- `issued` dates only; `created` or online dates would have avoided most date artefacts.
- P4 used titles, pages and citation counts for 29 of 40 rows and the full Crossref record for 11.
  No landing pages or PDFs were read, so the Physics Today cases stay "likely".
- Reversed relations where the correction came within 31 days of the original are invisible to
  this audit. Audit 2 is built to find them.
