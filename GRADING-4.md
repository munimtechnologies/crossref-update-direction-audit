# Grading, audit 4: retraction and withdrawal notices deposited with non-retractive update types

Graded 2026-11-08 (about 23:00 UTC) against [PREREG-4.md](PREREG-4.md). By MV2, Munim, Inc.
(mv2@munimtech.com). Made with AI agents working in MV2's name; no human has reviewed it.
Text and data CC BY 4.0, code Apache-2.0.

The census (`type_title_audit.py`, job `crossref-type-title4-v1`) ran on 2026-11-08 from 20:25
to 20:32 UTC. It walked every Crossref record with `update-to`: 488,117 records and 573,388
relations, all 488,117 that the API reported.

## Result: gate held; 6 of 8 predictions held (P6 and P7 failed)

| | Prediction | Result | Held? |
|---|---|---|---|
| G | walk complete, >= 450,000 records | complete, 488,117 | yes |
| P1 | >= 200 mistyped relations | 9,314 | yes |
| P2 | >= 60 distinct hidden pairs | 350 (about 280 after the correction below) | yes |
| P3 | Retraction Watch rescues >= 40% of mistyped | 5,406 of 9,314 = 58.0% | yes |
| P4 | IWA: >= 15 "Withdrawn" relations typed `addendum`, no `withdrawal`, all pairs hidden | 19 relations, 0 `withdrawal`, 16 of 16 pairs hidden | yes (confirmatory, not blind) |
| P5 | hidden relations from >= 12 members | 25 members | yes |
| P6 | hidden share for records created 2023+ >= 1.5x the share before 2020 | 233/6,364 = 3.7% vs 88/1,513 = 5.8% (0.63x) | **no**, the opposite |
| P7 | >= 30 overflags and at least half unsupported | 55 overflags, 22 unsupported (40%) | **no** |
| P8 | >= 25 of 30 sampled hidden pairs real (hand-graded) | 28 of 30 as worded; 24 (25 at most) under a stricter reading | yes as worded, see below |

## What the numbers mean

**Mistyped is common and mostly harmless.** 9,314 publisher relations come from notices
titled as retractions or withdrawals but typed otherwise. 8,762 of them are Elsevier notices
typed `erratum` ("Retraction notice to ..."). For 8,573 of those 8,762, the retraction is
recorded anyway, by a second publisher relation of type `retraction` or by Retraction Watch.
So the type is wrong but the paper still shows as retracted.

**Hidden is rarer and spread out.** 350 distinct pairs (362 relations) have no retractive
relation on either end anywhere in Crossref. By publisher: Elsevier 189 relations, SAGE 63,
Wiley 25, IWA Publishing 19, Wolters Kluwer 14, Springer Nature 6, ASCE 6, Peertechz 6, BMJ 5,
IOP 4, Heighten Science 4, and 14 more members with 1 to 3 each. By update type: `erratum`
218, `correction` 110, `addendum` 20, `new_edition` 10, `new_version` 3, `err` 1. 204 of the
330 targets looked up are themselves retitled "RETRACTED"/"WITHDRAWN". The title says
retracted, but the metadata a tool reads does not.

Recurring patterns in the hand sample:
- **Elsevier "Retraction notice to Corrigendum to ..."** (6 of 30): the corrigendum itself
  was retracted, and the notice is typed `erratum`. All six are from 2023-2026.
- **SAGE "WITHDRAWN - Administrative Duplicate Publication"** (5 of 30): withdrawals of
  duplicate records, typed `correction`.
- **IWA "Withdrawn:" notices typed `addendum`** (2 of 30; all 16 papers, see
  [findings/iwa-withdrawn-as-addendum.md](findings/iwa-withdrawn-as-addendum.md)).
- **Retitled works with only a self-pointing `new_edition`** (Peertechz, Heighten Science).

## P8 hand grading, and a correction to "hidden"

Every one of the 30 sampled pairs was read through api.crossref.org. Grades are in
[results/audit4/grade_hidden30_graded.csv](results/audit4/grade_hidden30_graded.csv).

- **As worded in PREREG-4 (28 of 30 real):** two pairs are false positives of one kind,
  an **extra target**. The SAGE *Wind Engineering* "Retraction Notice" 10.1177/0309524x18767745
  links two retracted *Wind Engineering* papers and also an Elsevier paper and an IEEE paper
  that are not marked retracted. The *European Urology* notice 10.1016/j.eururo.2014.07.015
  retracts an authors' reply but also links the editorial that the reply answered.
- **Stricter reading (24 of 30, 25 at most):** three more pairs are real retraction notices,
  but the retraction is **not** missing from Crossref. These are self-loops: the publisher's
  `erratum` points at the notice itself, while the **same record** carries a Retraction Watch
  `retraction` of the real article. Examples: 10.1016/j.bja.2018.11.005 retracts 10.1093/bja/74.3.293,
  and 10.1016/s1526-5900(03)00777-6 retracts 10.1054/jpai.2001.23140. Audit 4's rule checked
  only whether something retracts the pair's two ends, so it missed these. One more pair is
  ambiguous: a "Notice of Retraction and Replacement" (10.3352/jeehp.2024.21.41) typed
  `correction`.

We read all 14 Elsevier self-loop notices among the hidden pairs: **12 carry a Retraction
Watch retraction of the real article** (seven *British Journal of Anaesthesia* notices from
2018, plus *Chest*, *J Mol Biol*, *J Neurol Sci*, *Acta Orthop Traumatol Turc* and *J Pain*).
Only 10.1016/j.abd.2026.501462 and 10.1016/j.nbd.2026.107432 have nothing. None of the
Wiley, Peertechz or Heighten self-loops we read has a second relation.

So the headline "350 hidden pairs" is too high. The strict sample rate is 24/30 = 80% (Wilson
95% interval 63-91%), which gives roughly 220-320 pairs that are really absent from Crossref's
update metadata. P2 and P5 hold either way. A post-hoc rerun that judges each notice as a whole
(**not pre-registered**; `notice_audit.py`, job `crossref-notice-level4b-v1`) is queued. It
will report the corrected count and list the hidden notices by publisher.

## The two failed predictions

- **P6 failed, and the result is the opposite of the prediction.** We expected newer mistyped
  notices to be hidden more often, because Retraction Watch has had less time to catch them.
  Instead, older ones are hidden more often: 5.8% before 2020 vs 3.7% from 2023 on. The raw
  count of hidden relations still rises steeply (2024: 47, 2025: 69, 2026: 95), but so does the
  number of mistyped notices. The prediction was wrong, and we did not replace it with a new
  claim.
- **P7 failed.** Most "overflags" (retractive type on a correction-titled notice) are real
  retractions with a misleading title, not wrong types. 25 of 55 are PLoS annotations titled
  "Correction: ..." on papers that Retraction Watch also records as retracted (for example the
  XMRV paper 10.1371/journal.ppat.0020025). The 22 unsupported overflags matter more. They may
  be **papers that Crossref shows as retracted when only a correction was issued**, for example
  10.3341/kjo.2022.0089 ("Correction to: ..." typed `retraction`). They have not been
  hand-checked yet. The rerun lists them with their target titles for grading.

## Descriptive

- Update types across all 573,388 relations include 22 values outside Crossref's schema (for
  example `err` 201, `corrected` 54, `article` 21, `retration`, `retracion`, `68818`). This
  agrees with the Tesseract Semantics count of invalid strings.
- On 43 mistyped records, Retraction Watch itself attached a non-retractive relation.
- Retraction Watch-rescued share of mistyped relations: 58%.

## Prior work, searched again at grading (2026-11-08)

Nothing new was found that compares notice titles with update types. The nearest work is
still Tesseract Semantics' "Retraction register ontology" (Aug 2026: invalid type strings,
disagreement between registers), and the Crossref forum's Inderscience and World Scientific
threads (retracted articles with no update at all). APODICTIC issue #366 (Oct 2026) notes that
tools reading `update-to` can flag the notice rather than the article. That is a consequence of
reversed and self-loop links like those here.

## Data

[results/audit4/](results/audit4/): `summary.json`, `member_table.csv`, `hidden.csv` (all 362
hidden relations), `overflag.csv` (55), the graded sample. `mistyped.csv` (9,314 rows, about
4 MB) is too large for this repository's file limit; `type_title_audit.py` rebuilds it in
about six minutes.
