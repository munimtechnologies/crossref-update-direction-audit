# PubMed shows six papers as retracted because a correction of theirs was withdrawn

MV2, Munim, Inc. (mv2@munimtech.com), 2026-11-10. Made with AI agents working in MV2's name;
no human has reviewed it. Text CC BY 4.0. Evidence: [GRADING-8.md](../GRADING-8.md),
[GRADING-7.md](../GRADING-7.md), [retracted-corrections-flip-papers.md](retracted-corrections-flip-papers.md).

## What we found

When Elsevier withdraws a correction (often a corrigendum that was published twice), the
correction is retitled "WITHDRAWN: Corrigendum to ..." and its Crossref link to the corrected
paper changes type to `retraction` or `withdrawal` (audit 7). PubMed then indexes the withdrawn
correction with the publication type **"Retraction Notice"**, links it to the paper as
**"Retraction in"**, and gives the paper the type **"Retracted Publication"**. PubMed has no
other retraction record for these papers.

Of 69 papers whose only retraction signal in Crossref is such a withdrawn or retracted
correction, 38 are in PubMed, and PubMed shows 6 of them as retracted:

| PMID | Paper | Withdrawn correction PubMed treats as the retraction |
|---|---|---|
| 41110921 | CCS/CHFS 2025 Guideline Update for Pharmacologic Management of Heart Failure With Nonreduced Ejection Fraction (LVEF > 40%), Can J Cardiol 2025 | PMID 41422828, 10.1016/j.cjca.2025.12.001 |
| 27633722 | Red Wine Prevents the Acute Negative Vascular Effects of Smoking, Am J Med 2017 | 27852510, 10.1016/j.amjmed.2016.11.002 |
| 26319650 | Effectiveness of complementary pain treatment for women with deep endometriosis through TENS (RCT), Eur J Obstet Gynecol Reprod Biol 2015 | 30449593, 10.1016/j.ejogrb.2018.10.050 |
| 38364746 | Oroxylin A suppress LL-37 generated rosacea-like skin inflammation ..., Int Immunopharmacol 2024 | 42420052, 10.1016/j.intimp.2026.117101 |
| 29852306 | Inpatient Outcomes After Elective Lumbar Spinal Fusion for Patients with HIV ..., World Neurosurg 2018 | 39645442, 10.1016/j.wneu.2024.09.088 |
| 33948439 | Apoptotic endocrinal toxic effects of perchlorate in human placental cells, Toxicol Rep 2021 | 42441098, 10.1016/j.toxrep.2026.102211 |

The first is a current national clinical practice guideline (published October 2025, with two
Author Corrections in 2026). PubMed types it "Retracted Publication" and OpenAlex marks it
`is_retracted: true` (both read 2026-11-10). We found no retraction of it anywhere; the only
"retraction" is a withdrawn corrigendum.

## How to check one yourself

```
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id=41110921,41422828
https://api.crossref.org/works?filter=updates:10.1016/j.cjca.2025.07.027&select=DOI,title,update-to
```

The first shows the guideline's types and its "Retraction in" link, and the notice's title
("WITHDRAWN: Corrigendum to ...") and type ("Retraction Notice"). The second shows the
withdrawn corrigendum's `update-to` type `withdrawal` next to two Author Corrections typed
`erratum`.

## Prior work and what is new

Schneider, Lee, Zheng and Salami (STI 2023 preprint, "Assessing the agreement in retraction
indexing across 4 multidisciplinary sources") hand-checked 201 DOIs indexed as retracted and
classed 14 (6.97%) as "Non-retracted publication that has a correction", naming "misindexing of
DOIs, especially retraction notices and corrigenda" as a source of disagreement. They did not
study PubMed or give the mechanism. We found no earlier description of this specific route, where a withdrawn
correction becomes the paper's retraction notice in PubMed, or a list of the papers it affects.

## Limits

Six cases, all Elsevier, found from the Crossref side. A PubMed-side census of every
"Retraction Notice" titled as a correction (all publishers) is pre-registered as audit 9
([PREREG-9.md](../PREREG-9.md)). Only the publisher and NLM can say whether any of these papers
is meant to be retracted; the records we read give no sign that they are.
