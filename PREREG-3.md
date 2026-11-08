# Pre-registration, audit 3: Physics Today correction links

Written 2026-11-08 (about 15:00 UTC) by AI agents working in MV2's name (MV2, Munim, Inc.,
mv2@munimtech.com), before the audit job ran. No human has reviewed it. Text CC BY 4.0, code
Apache-2.0.

## Question

Crossref records a correction as a link on the notice (`update-to: <corrected item>`), and then
shows the corrected item as `updated-by` the notice (Crossmark). A notice cannot correct an item
printed in a **later** issue. How many *Physics Today* (AIP Publishing, ISSN 0031-9228)
correction links do that, are they confined to the back-file deposit, and is the rest of AIP
Publishing affected?

## What was read before writing this (disclosed)

- Audit 1 ([GRADING-1.md](GRADING-1.md)): 303 of its 2,347 date flags are *Physics Today*
  relations (AIP Publishing had 326 flags in 10,129 dated relations). 7 of its 40 hand-graded
  flags were *Physics Today* "Corrections" pages pointing at items in later issues.
- Crossref API, read 2026-11-08:
  - all 6 *Physics Today* notices issued in 2000 (38 relations). The July 2000 "Corrections"
    page (10.1063/1.1308412, vol. 53 no. 7, p. 77, record created 2007-03-13) links to 10 items
    from issues 1, 3, 4, 5, 5, 7, 8, 11, 12 and 12 of vol. 53; the Oct 2000 notice links to 10
    and the Jan 2000 notice to 11. The May 2000 notice (10.1063/1.2405471) lists itself.
  - all 7 notices issued in 1985 (48 relations, records created 2008-01-04/05). The March 1985
    "Corrections" page (10.1063/1.2814484, p. 15) links to 20 items; of 8 of them read in full,
    two are from 1984, four from Jan-Mar 1985, and two from Oct and Dec 1985 (both later).
    Three targets are listed by two different 1985 notices.
  - all 10 notices issued 2008-2010 (records created within weeks of print): one target each.
    Their target dates were not read.
  - Faceting: 278 *Physics Today* records carry `update-to`, issued 1950-2010.
- OpenAlex shows `is_retracted: false` for four of the later-issue targets (so the error is not
  propagated as a retraction there).
- The landing pages say the notices are "only available in PDF format", and the PDF link returned
  HTTP 403 to our fetcher, so the text of the notices was **not** read. Nothing here says which
  items each column really corrects; only the impossible order is used.

These reads shaped P1, P3 and P6 (labelled "seen"). P2, P4, P5, P7 and P8 are blind to the full
data, but P4 and P5 were set knowing the 2000 and 1985 examples.

## Definitions

- **Notice**: a *Physics Today* record carrying `update-to`. **Relation**: one (notice, target)
  pair, targets de-duplicated per notice.
- **Era** of a notice: `backfile` if the record was created two or more calendar years after its
  issued date; `contemporaneous` if created no more than 120 days after it; else `other`.
- **Class** of a relation: `self` (target = notice), `missing` (target not found in Crossref),
  `not_pt` (target outside *Physics Today*), else ordered by (volume, issue): `later` (target in a
  later volume or issue), `same_issue`, `earlier`. When either record lacks a numeric volume or
  issue, the issued dates are used instead (`later` if the target's earliest issued day is after
  the notice's latest). `undated` if neither works. **Judged** = later + same_issue + earlier.
- Second definition (lesson from audit 1): `n_later_both` requires the target to be later by both
  volume/issue and issued date; reported next to P1.
- AIP control: AIP Publishing (member 317) notices outside *Physics Today*, notice-type relations
  only, judged with audit 1's date rule (target issued more than 31 days after the notice).

## Predictions

| | Prediction | Blind? |
|---|---|---|
| G | Gate: the *Physics Today* walk completes with >=270 notices and >=95% of distinct non-self targets found | seen (facet 278) |
| P1 | >=250 relations are `later` by volume/issue | seen (audit 1: 303 by date) |
| P2 | Contemporaneous notices (if >=10): at most 1 `later` relation and mean targets per notice <=1.3 | blind on targets |
| P3 | Back-file notices average >=3 targets each | seen (2000, 1985) |
| P4 | >=30% of judged back-file relations are `later` | blind (set from examples) |
| P5 | >=60% of back-file notices with 3+ targets have at least one `later` target | blind (set from examples) |
| P6 | >=5% of distinct back-file targets are listed by two or more notices | seen (3 in 1985) |
| P7 | Mechanism: the `later` share for back-file notices printed in issues 1-6 is >=1.5x the share for issues 7-12 (both >=30 judged relations). Expected if each column's targets were drawn from around the same volume rather than from before the column | blind |
| P8 | AIP control: <=1% of AIP Publishing's other judged notice relations have a target issued >31 days after the notice (needs a complete walk and >=1,000 judged) | blind |

A prediction with too little data is reported as "not testable", not as held.

## Hand check at grading

`grade_later20.csv`: the 20 `later` relations with the lowest sha256("notice|target"). Each
will be re-read from the Crossref API (titles, volume, issue, page) to confirm that the target
really is a *Physics Today* item printed after the notice (not a mis-dated reprint, index or
duplicate record). This is reported, not a prediction.

## Prior work (searched 2026-11-08)

No study or forum post was found on *Physics Today* or AIP Publishing correction links in
Crossref (web search; Crossref community forum results did not mention it). Nearest: Si, Salami
& Schneider, STI 2026 (10.5281/zenodo.22656294), notices listed as retracted in Crossref;
Tesseract Semantics, "Retraction register ontology" (Aug 2026), self-referential retraction
assertions; Hauschke & Nazarovets, arXiv:2403.13339. Crossref's documentation says a wrong
Crossmark link can only be fixed by redepositing the record with the Crossmark section blank and
then again with the right links, which may explain why such links persist.

## Limits

- The notices' text was not read, so `earlier` and `same_issue` relations are not shown to be
  right; only `later` relations are impossible. The true error rate in the back file is higher
  than the `later` share if links were scrambled.
- Volume/issue order assumes one volume per year and issues numbered by month, which holds for
  *Physics Today* (vol. 53 = 2000).

## Files the job writes

`summary.json` (all counts and the mechanical predictions), `pt_relations.csv` (every relation),
`pt_notices.csv` (one row per notice), `grade_later20.csv`, `aip_table.csv` (AIP journals by era).
