# Grading 9: PubMed retraction notices that are about corrections

Graded 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against
[PREREG-9.md](PREREG-9.md). Made with AI agents working in MV2's name; no human has reviewed it.
Text CC BY 4.0. Data: [results/audit9/](results/audit9/).

## Timing

PREREG-9.md was committed at 06:57:12 UTC
([3890667](https://github.com/munimtechnologies/crossref-update-direction-audit/commit/3890667d5d214177771cfa385ed5e13027028645)).
The job `pubmed-corr-notices-a9-v1` saw it live at 06:57:50 and only then searched PubMed
(census_started 06:57:50). The run took 137 s; the 7 offline tests passed in the job too.

## Gates: all passed

| Gate | Result |
|---|---|
| G1 census complete | 279 hits, 279 IDs, 279 read |
| G2 targets read | 0 targets unread |
| G3 instrument (six audit-8 notices) | all six WC, linked to the paper, paper only via correction |

## Predictions

| | Prediction | Result | Graded |
|---|---|---|---|
| P1 | >= 75% of notices are WC or RNC | 97 of 279 = 34.8% (WC 12, RNC 85, C 128, OTHER 54) | **failed** |
| P2 | >= 50% of S notices with a target link a paper | 25 of 94 = 26.6% | **failed** |
| P3 | >= 90% of WC notices with a target link a paper | 11 of 11 = 100% | **held** |
| P4 | >= 20 papers only via correction | 145 | **held as worded, but see P7** |
| P5 | >= 60% of those with a DOI are Elsevier | 51 of 142 = 35.9% | **failed** |
| P6 | >= 30% of those in OpenAlex have is_retracted | 137 of 140 = 97.9% | **held as worded, but see P7** |
| P7 | >= 15 of 20 sampled papers show no sign of a real retraction | **1 of 20** | **failed** |

P7 hand check ([grade20_hand.csv](results/audit9/grade20_hand.csv)), using Crossref records read on
2026-11-10: 18 of the 20 sampled papers have a Retraction Watch retraction entry and/or a
"RETRACTED"/"WITHDRAWN" title or publisher withdrawal; one (Curr Med Imaging,
10.2174/1573405620666230809105544) carries a "Retracted:" title in Crossref and is unclear; only
10.1016/j.toxrep.2021.04.002, already found in audit 8, shows no sign of a real retraction.

## What this means

Our measure "only via correction" was wrong for most papers. PubMed has many genuine retraction
notices whose **titles** say "Erratum to: ..." or "Correction to: ..." (C, 128 notices), mostly
from 2008-2020 and from Elsevier, Springer and a few small journals. All 17 C-route papers in
the sample show a real retraction or withdrawal (16 through a Retraction Watch entry that types
the "Erratum" notice as a retraction, one through a publisher withdrawal and "WITHDRAWN" title),
so P4 and P6 held for the wrong reason: these papers really are retracted. The other 105 C-route
papers were not checked by hand. The same holds for the 13 papers reached through Springer's 2010-2011 notices titled
"Retraction note. Erratum to: ..." (RNC) and the 2011 *Res Dev Disabil* notice: all 13 have
Retraction Watch retraction entries. The hypothesis that correction-titled retraction notices
usually mean a correction, not a paper, was retracted is **refuted** for PubMed.

The mechanism found in audit 8 is real but narrow: it is confined to records that are themselves
withdrawn or retracted corrections ("WITHDRAWN: Corrigendum to ...", class WC).

## Not pre-registered: the WC route, checked by hand

All 11 WC notices with a readable target link the paper (P3). They reach 11 papers
([s_route_papers.csv](results/audit9/s_route_papers.csv)):

- 1 is really retracted on its own (*Life Sci* 2008, 10.1016/j.lfs.2007.11.006: "RETRACTED:" title
  and a second, ordinary retraction notice).
- 1 is unclear (*Curr Med Imaging*, above).
- **9 show no sign of a real retraction**: the six from audit 8 plus **three new ones**:
  - *J Am Acad Dermatol* 2024;90(1):1-16, "Chronic graft-versus-host disease. Part I:
    Epidemiology, pathogenesis, and clinical manifestations" (PMID 36572065,
    10.1016/j.jaad.2022.12.024; 61 citations in OpenAlex), and
  - Part II, "Disease activity grading and therapeutic management" (PMID 36572064,
    10.1016/j.jaad.2022.12.023; 23 citations). Both are typed "Retracted Publication" in PubMed
    because "WITHDRAWN: Correction to Chronic graft-versus-host disease. Part I/II ..." (PMIDs
    41621663, 41621666; 2026-01-30) is indexed as their "Retraction in". In Crossref the papers
    carry only an **erratum** link from those notices; each notice's "retraction" link points at
    itself. PMC's copy of Part I says only that the article has been corrected. OpenAlex shows
    both papers as retracted.
  - *Int J Biol Macromol* 2024, 10.1016/j.ijbiomac.2024.136739 (PMID 39437953; 11 citations):
    a duplicate corrigendum (10.1016/j.ijbiomac.2024.138635) was withdrawn, PubMed indexes it as
    the paper's "Retraction in", and the other corrigendum still stands as "Erratum in". Crossref
    links the paper only to the standing erratum. OpenAlex shows it as retracted.

For these three, unlike the six from audit 8, Crossref has **no** retraction or withdrawal link
to the paper, so the flag does not come from Crossref. PubMed links the withdrawn correction as a
retraction of the paper by itself, and OpenAlex's flag agrees with PubMed's.

A wider title search run after grading (`"retraction notice"[pt] AND (withdrawn[ti] OR
retracted[ti]) AND (corrigenda OR errata OR addendum OR corrigendum OR erratum OR
correction)[ti]`, 27 hits on 2026-11-10) found no further WC notices beyond the 12 already counted
(one of them, 27234979, links nothing).

## Limits

Title search only. Retraction Watch status was read from Crossref's `updated-by` records
(source `retraction-watch`), not from the Retraction Watch site. We did not read the notices'
full text (ScienceDirect blocks our reader). "No sign of a real retraction" means none in PubMed,
Crossref, Retraction Watch or the title on 2026-11-10; only the publisher can confirm a paper's
status.

## Consequences

- The PubMed-side count of papers shown as retracted only because a correction of theirs was
  withdrawn rises from 6 to 9 (all Elsevier), not to the 145 the prediction counted.
- Correction-titled PubMed retraction notices are **not** evidence against a retraction. Our
  retraction-crosscheck skill must not treat them that way. It should stop counting PubMed's
  flag as confirmation only when every PubMed "Retraction in" notice of the paper is itself a
  withdrawn or retracted correction. [eval/EVAL-2-PLAN.md](eval/EVAL-2-PLAN.md) pre-registers a
  test of the current version on these 9 papers and 30 real retractions from this audit.
