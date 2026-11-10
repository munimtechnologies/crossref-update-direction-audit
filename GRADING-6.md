# Grading 6: do other indexes catch the retractions Crossref's metadata hides?

Graded 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against [PREREG-6.md](PREREG-6.md).
Made with AI agents working in MV2's name; no human has reviewed it. Text CC BY 4.0.
Results: [results/audit6/](results/audit6/).

**Score: 7 of 9 predictions held (P6 and P9 failed). All seven gates passed.** The headline list
is smaller than the job's count: about half of the "missed by every index" papers are not real
retractions (mostly SAGE duplicate-record clean-ups and two reversed links).

## Timing

PREREG-6.md and the code were committed at 2026-11-09 11:29 UTC (commit a494f5f). Job
`index-miss-a6-v1` ran from 21:40 to 21:46 UTC the same day; its 11 unit tests passed.

## Gates

All passed: 294 input rows; 312 papers; 100% found in Crossref; 99.7% carry `updated-by`; the
Retraction Watch CSV has 73,688 rows; OpenAlex found 99.3% of set A; 0 PubMed errors.

## Predictions (P1 to P8 graded by the code as worded)

| | Prediction | Result | |
|---|---|---|---|
| P1 | at least 90% still unflagged in live Crossref | 300 of 312 (96.2%) | held |
| P2 | under 20% of A listed as retracted in the Retraction Watch CSV | 17 of 300 (5.7%) | held |
| P3 | at least 40% of A in OpenAlex not flagged | 41.9% | held |
| P4 | OpenAlex flag rate at least 30 points higher for retitled papers | +63 points | held |
| P5 | under 40% of A in PubMed | 114 of 300 (38.0%) | held |
| P6 | at least 30% of A in PubMed carry neither flag | 25 of 114 (21.9%) | **failed** |
| P7 | at least 60 papers missed by all four sources | 125 | held |
| P8 | at least 10 of them with 20+ OpenAlex citations | 14 | held |
| P9 | hand check: at least 15 of 20 sampled missed-by-all papers are real retractions or withdrawals of research papers | 10 of 20 | **failed** |

## Hand check (P9)

Every notice title and link was read in live Crossref on 2026-11-10
([grade20_graded.csv](results/audit6/grade20_graded.csv)). Counted as real (10): a retraction note
(Akadémiai Kiadó), an ERS "Retraction", four IWA Publishing withdrawals, a Wiley withdrawal, a
Wiley withdrawal statement, an IOP conference-paper withdrawal and the Lancet Oncology "Retraction
and republication" of the BYLieve trial paper. Not counted (10): five SAGE "Administrative
Duplicate Publication" withdrawals and one SAGE book review (record clean-ups, which the
pre-registration excluded), two reversed links where the audited DOI is the notice or erratum and
not the paper (Wiley J Futures Markets; ASME J Fluids Eng), a withdrawn *notice* about a paper that
stands (Renewable and Sustainable Energy Reviews; Retraction Watch lists a reinstatement), and a
retired EPPO standard.

## What this changes

- SAGE's duplicate-record clean-ups are typed `correction`, and arguably that is fine: no research
  paper is being retracted. They make up a large part of the 125 (21 of the papers' own titles
  say "Administrative Duplicate Publication"). Audit 4b counted them as hidden retractions; that
  count was too high.
- With half of the sample real, roughly 60 of the 125 papers are likely real retractions or
  withdrawals that Crossref, Retraction Watch, OpenAlex and PubMed all fail to flag. This is an
  estimate from 20 cases, not a count.
- PubMed flags more than we expected (P6): of the papers it holds, 78% carry a retraction flag.
  PubMed is the most complete of the four for biomedical papers; the misses are mostly outside
  biomedicine.

## Limits

One reading on one day. DOI matching only. The hand check reads notice titles and links, not
publisher pages.
