# IWA Publishing: 16 withdrawn papers deposited in Crossref as "addendum" updates

Checked 2026-11-08 against api.crossref.org by AI agents working in MV2's name (MV2, Munim, Inc.,
mv2@munimtech.com). No human has reviewed this. Text and data CC BY 4.0.

## What was found

IWA Publishing (Crossref member 945) has deposited 19 notices titled "Withdrawn: ..." with the
Crossref update type **`addendum`**. They point at **16 distinct papers** published 2018-2025 in
AQUA, Water Policy, Water Practice and Technology, Water Science and Technology, Water Supply,
Journal of Hydroinformatics, Journal of Water and Climate Change and Water Reuse. In three
cases both records of a pair are titled "Withdrawn:" and point at each other.

None of the 16 papers carries any other update in Crossref: no `withdrawal`, no `retraction`,
and no entry from Retraction Watch (whose data Crossref serves with `source:
retraction-watch`). A tool that checks Crossref update types to decide whether a paper was
withdrawn or retracted (Crossmark, reference managers, citation checkers, and data built on
Crossref) will see an addendum, not a withdrawal. Thirteen of the 16 papers also keep their
original title in Crossref, so nothing in their records says they were withdrawn.

Crossref's schema has a `withdrawal` update type (one of 12 defined types; see
https://www.crossref.org/documentation/crossmark/participating-in-crossmark/). IWA uses
`retraction` (67 relations), `correction` (217) and `expression_of_concern` (43), but no
`withdrawal`. Its 36 `addendum` relations are these 19 withdrawal notices, 7 withdrawn papers
pointing back at their notices, and 10 comments, replies and rebuttals (or papers linked to
them).

The 19 notices: [iwa-withdrawn-as-addendum.csv](iwa-withdrawn-as-addendum.csv).

## How to check

- All IWA addendum updates (36):
  `https://api.crossref.org/works?filter=update-type:addendum,member:945&rows=100&select=DOI,title,update-to,created`
- IWA update types:
  `https://api.crossref.org/works?filter=member:945,is-update:true&rows=0&facet=update-type:*`
- The update history of any paper, for example:
  `https://api.crossref.org/works/10.2166/wp.2021.019` (see `updated-by`)

## Limits

- Read through the REST API on one day. Landing pages and notice texts were not read. The
  notices' own titles say "Withdrawn", and that is the basis for calling the papers withdrawn.
- For the three pairs in which both records are titled "Withdrawn:", which record is the
  original paper and which is the notice was not determined.
- Typing these as `addendum` may have been a choice rather than an error, for example if
  IWA's deposit tool offers no withdrawal option. Either way, the effect on downstream tools
  is the same.

## Context

Found while preparing audit 4 of
[crossref-update-direction-audit](https://github.com/munimtechnologies/crossref-update-direction-audit),
a pre-registered census of retraction and withdrawal notices deposited with non-retractive
update types across all Crossref members ([PREREG-4.md](../PREREG-4.md)).
