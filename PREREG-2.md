# Pre-registration: Crossref reversed-relation audit 2

Written 2026-11-08 by AI agents working in MV2's name (MV2, Munim, Inc., mv2@munimtech.com),
before `reversed_relation_audit.py` had run. No human has reviewed it.
Text CC BY 4.0, code Apache-2.0.

## Question

In Crossref, a correction or retraction is recorded on the **notice**: the notice's record
carries `update-to` naming the work it updates, and Crossref then shows `updated-by` on that
work. Audit 1 ([GRADING-1.md](GRADING-1.md)) found that the real errors among its date-based
flags were mostly **reversed** relations: the original article carries `update-to` pointing at
its own erratum or retraction notice. In those cases Crossref shows the notice as updated (or
retracted) and leaves the original without any `updated-by`.

Audit 1 could only see reversed relations where the original was more than 31 days older than
its notice, and its date rule also flagged many correct relations. This audit finds reversed
relations **from titles, without dates**, across all of Crossref, and asks:

1. How many reversed relations are there, and who deposited them?
2. How many does a date rule miss?
3. How many retraction notices does Crossref show as retracted because of them?
4. Does OpenAlex still mark the original as retracted when the relation is reversed?

## Definitions (fixed)

Population: every record returned by `api.crossref.org/works?filter=is-update:true` (same walk
as audit 1). One row per `update-to` entry. Only non-self relations of notice types (erratum,
correction, corrigendum, retraction, partial_retraction, withdrawal, removal,
expression_of_concern, addendum, clarification) whose target is found in Crossref are judged.

Titles are cleaned (HTML removed, accents folded, dashes made spaces, lower case).

- **Notice title**: starts with erratum/errata, correction(s), corrigendum/corrigenda,
  retraction, notice of retraction, withdrawal, (editorial) expression of concern,
  addendum/addenda, author correction, publisher correction, publisher's note, or "additions and
  corrections"; or ends with ": erratum", ": correction(s)", ": corrigendum", ": retraction"
  or ": retraction notice" (also after "." or "-").
- **Plain title**: non-empty and contains none of the notice words (erratum, correction(s),
  corrigendum, retraction(s), retracted, withdrawn, withdrawal, expression of concern, addendum,
  clarification, "notice of").
- **Retracted-marked title**: starts with "retracted" or "withdrawn", or contains "(retracted)"
  or "(retracted article)". This is how Elsevier, Wiley and others retitle the retracted
  article itself.

Direction of a relation from record R to target T:

| R's title | T's title | class |
|---|---|---|
| notice | not notice | forward (the normal case) |
| notice | notice | notice_to_notice |
| plain | notice | **reversed_plain** |
| retracted-marked | notice | **reversed_marked** |
| other (has notice words, not a notice title) | notice | reversed_other (counted, not judged) |
| not notice | not notice | neither |

**Reversed** = reversed_plain + reversed_marked.

A reversed relation **predates** if audit 1's rule holds (R's latest `issued` date + 31 days is
before T's earliest `issued` date); it is **not predating** if both are dated and the rule does
not hold.

OpenAlex: for up to 200 reversed relations of retractive types (retraction, partial_retraction,
withdrawal, removal), lowest sha256("oa|R|T"), both DOIs are looked up at
`api.openalex.org/works?filter=doi:...` (`is_retracted`). A control sample of up to 200 forward
retractive relations is looked up the same way (descriptive only).

Grading sample: the 40 reversed relations with the lowest sha256("g2|R|T").

## What was seen before writing this (disclosed)

All of audit 1's outputs: its 2,347 predating flags (which include many reversed relations),
their top 200 by citations, the 40 hand-graded flags and the publisher table. The title rules
above were written after reading those titles. So the part of the reversed set that also
predates is **not** blind. Blind: the reversed relations that do not predate, the OpenAlex
results, and the precision of the title rule on a fresh hash sample.

## Predictions

- **G (gate):** the walk is complete, at least 450,000 records, and at least 95% of distinct
  targets of non-self notice-type relations are found. If G fails, nothing below is graded.
- **R1:** at least 1,500 reversed relations.
- **R2:** at least 40% of reversed relations with both dates are **not** flagged by audit 1's
  date rule (the date rule misses many). Needs 20+.
- **R3:** reversed relations come from at least 25 Crossref members, and no member has half
  or more of them.
- **R4 (hand-graded):** at least 34 of the 40 sampled reversed relations are confirmed: R is
  the original work (or the retracted article itself) and T is a notice about R.
- **R5:** in the OpenAlex sample, at least 10% of the originals (R) that OpenAlex knows are
  **not** marked `is_retracted`. Needs 20+.

R1 and R2 are linked: audit 1 already holds several hundred reversed relations, so R1 mostly
holds if the date rule misses many.

## Descriptive (not predicted)

Counts by member, prefix, update type, decade and source (publisher or Retraction Watch);
reversed relations whose two records point at each other; originals with 10+ and 100+ citations;
the number of distinct notices that Crossref shows as retracted only because an original points
at them; retractive self relations; the OpenAlex control.

## Prior work (searched 2026-11-07 and 2026-11-08)

- Si, Salami & Schneider, STI 2026 (10.5281/zenodo.22656294): 661 of 925 DOIs listed as
  retracted only in Crossref (April 2023) are retraction notices. The abstract gives no cause.
- Tesseract Semantics, "Retraction register ontology" (August 2026): agreement between
  Crossref, Retraction Watch, OpenAlex and Europe PMC; 25.73% of Crossref retractive assertions
  are self-referential; OpenAlex flags 94.5% of Retraction Watch notice DOIs as retracted. Does
  not discuss reversed `update-to` relations.
- Hauschke & Nazarovets, arXiv:2403.13339: OpenAlex once read every update as a retraction.
- Crossref Crossmark documentation: the notice carries the update and Crossref adds `updated-by`.

No count of reversed `update-to` relations was found.

## What happens with the result

GRADING-2.md will report every prediction, including failures. If reversed relations are
confirmed, the list goes to Crossref's community forum and to the largest depositors through
their public channels, disclosed as made with AI agents. Individual authors will not be
contacted.
