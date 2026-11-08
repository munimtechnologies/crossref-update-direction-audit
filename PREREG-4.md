# Pre-registration: Crossref update-type audit 4 (retractions typed as something else)

Written 2026-11-08 before the census ran. By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI
agents working in MV2's name; no human has reviewed it. Text CC BY 4.0, code Apache-2.0.

## Question

Crossref records a retraction or withdrawal as an `update-to` relation on the notice, with one
of twelve update types. Four of them say the work is gone or retracted: `retraction`,
`partial_retraction`, `withdrawal`, `removal`. Tools that ask "is this paper retracted?" read
those types. How often does a publisher deposit a notice that **calls itself** a retraction or
withdrawal ("Withdrawn: ...", "Retraction note to: ...", "...: Retraction") with a
non-retractive type such as `addendum`, `correction` or `erratum`? And how often does nothing
else in Crossref, including the Retraction Watch data Crossref serves
(source `retraction-watch`), record the retraction, so the paper looks merely corrected?

The opposite error is counted too: retractive-typed relations on notices titled as plain
corrections.

## Definitions (fixed; code in `type_title_audit.py`)

Population: every record from `api.crossref.org/works?filter=is-update:true`, one row per
`update-to` entry. Only relations with `source: publisher` are judged.

Titles are cleaned: HTML removed, unicode dashes kept as " - ", accents folded, lower case,
leading and trailing punctuation and brackets removed.

- **Retraction-worded title**: not starting with correction(s), corrigendum/a, erratum/errata,
  addendum/a, clarification, author/publisher correction, and not mentioning "expression(s) of
  concern"; and either (a) starts with "notice of retraction/withdrawal", or with retraction(s),
  retracted, withdrawn or withdrawal (optionally after "partial " or "full ") followed by the
  end, punctuation, or one of: note(s), notice(s), statement, of, to, for, and, article, paper,
  publication, letter; or (b) ends with a separator (: . - [ or () and then retraction,
  retracted, withdrawn, withdrawal, "retraction notice" or "notice of retraction".
- **Correction-worded title**: starts with one of the correction words above and contains
  neither "retract" nor "withdraw" nor "expression of concern".
- **Retractive type**: retraction, partial_retraction, withdrawal, removal, or any type string
  starting "retra" or containing "withdraw" (catches the misspellings "retration",
  "retracion").
- **Mistyped**: publisher relation, retraction-worded title, non-retractive type.
- **Hidden**: a mistyped relation where no relation of retractive type, from any source and any
  record, targets either the record or its target. A hidden pair has no retraction anywhere in
  Crossref's update metadata.
- **RW-rescued**: a mistyped relation where a `retraction-watch` relation of retractive type
  targets either end.
- **Overflag**: publisher relation of retractive type whose record title is correction-worded.
  **Unsupported** overflag: no `retraction-watch` retractive relation on either end.

Grading sample: the 30 distinct hidden pairs with the lowest sha256("g4|record|target").

## What was seen before writing this (disclosed)

All read directly from api.crossref.org on 2026-11-08:

1. IWA Publishing (member 945): `filter=update-type:addendum,member:945` returns 36 records;
   19 are titled "Withdrawn: ..." and point at 16 distinct papers (three pairs of records,
   both titled "Withdrawn:", point at each other). None of the 16 carries any other update:
   no `withdrawal`, no `retraction`, no Retraction Watch entry. IWA's updates by type
   (`filter=member:945,is-update:true`, facet): correction 217, retraction 67,
   expression_of_concern 43, addendum 36; no `withdrawal`. Listed in
   `findings/iwa-withdrawn-as-addendum.md`.
2. The first 40 results of `filter=update-type:correction&query.bibliographic=retraction`
   (352 hits). About 25 are retraction notices typed `correction` by the publisher. In
   roughly half, Retraction Watch adds its own `retraction` relation; in the others nothing
   does. Six targets read directly and found hidden: 10.1017/nbf.2025.10071 (New Blackfriars),
   10.1177/0309524x17709729 and 10.1177/0309524x17709925 (Wind Engineering; one SAGE notice
   also links an Elsevier and an IEEE paper), 10.1097/brs.0000000000003359 (Spine),
   10.1097/shk.0000000000002268 (Shock), 10.1183/20734735.011713 (Breathe). Four of these
   articles carry "RETRACTED" in their own Crossref title.
3. Audit 1's outputs (predating relations, publisher table), which drew attention to IWA.

The title rules were written after reading these titles. Known miss: the Shock notice is
titled "RETRACTION SHOCK PAPER" and is **not** retraction-worded under these rules (kept so
rather than tuned to a title already seen). P4 is confirmatory, not blind. P1-P3 are informed
by the 40-item sample. P5-P8 are blind.

## Predictions

- **G (gate):** the walk completes with at least 450,000 records. If G fails, nothing is graded.
- **P1:** at least 200 mistyped relations.
- **P2:** at least 60 distinct hidden pairs.
- **P3:** Retraction Watch rescues at least 40% of mistyped relations. Needs 20+.
- **P4 (confirmatory):** at least 15 IWA relations from "Withdrawn"-titled records are typed
  `addendum`, IWA has no `withdrawal`-typed relation, and every IWA withdrawn pair is hidden.
- **P5:** hidden relations come from at least 12 Crossref members.
- **P6:** the hidden share among mistyped relations whose record was created in 2023 or later
  is at least 1.5 times the share for records created before 2020 (Retraction Watch has had
  longer to catch older cases). Needs 20+ in each group.
- **P7:** at least 30 overflag relations, and at least half of them unsupported.
- **P8 (hand-graded):** at least 25 of the 30 sampled hidden pairs are real: the record or its
  target is a retraction or withdrawal notice (or a work retitled as retracted/withdrawn), and
  the work is in fact retracted or withdrawn according to the notice text or title read through
  api.crossref.org. False positives are reported by kind.

## Descriptive (not predicted)

Counts by update type, member, year and self/non-self; how many hidden targets carry a
retracted/withdrawn marker in their own title; how often Retraction Watch itself types a
retraction-worded notice as non-retractive.

## Prior work (searched 2026-11-08)

- Tesseract Semantics, "Retraction register ontology" (August 2026): Crossref vs Retraction
  Watch vs OpenAlex vs Europe PMC agreement; 34 update-type strings, 22 outside the schema
  (misspellings such as "retration"); 25.73% of retractive assertions self-referential. It does
  not compare notice titles with update types, and does not mention addendum or withdrawal
  notices.
- Crossref community forum, "Metadata quality improvements" (2026): Inderscience and World
  Scientific retracted articles retitled "RETRACTED" with no Crossref update at all (reported
  by gcabanac; both fixed after Crossref staff contacted the publishers). Those had no update;
  this audit is about updates that exist but carry the wrong type.
- Hauschke & Nazarovets, arXiv:2403.13339; Si, Salami & Schneider (STI 2026): OpenAlex and
  Crossref flagging notices as retracted. Different error (over-flagging of notices).
- Crossref Crossmark documentation lists the 12 update types, including `withdrawal`.

No count of retraction or withdrawal notices deposited with non-retractive types was found.

## What happens with the result

GRADING-4.md will report every prediction, including failures. Confirmed hidden retractions go
to Crossref's community forum ("Metadata quality improvements"), one thread per publisher,
disclosed as made with AI agents. Individual authors will not be contacted.
