# Publisher retraction links in Crossref that point at the wrong paper

MV2, Munim, Inc. (mv2@munimtech.com), 2026-11-11. Found while hand grading audit 11
([GRADING-11.md](../GRADING-11.md)), so this is a post hoc finding, not a pre-registered one. Made
with AI agents working in MV2's name. No human has reviewed it. Text CC BY 4.0.

## What we found

A retraction or withdrawal notice in Crossref carries an `update-to` link that names the item it
retracts. In at least **19 notices**, the link the publisher deposited names an item that was
never retracted or withdrawn. Every link was re-read in live Crossref on 2026-11-11.

| Mechanism | Notices | Examples (notice -> wrongly linked item) |
|---|---|---|
| A withdrawn or retracted letter links the article it comments on | 6 | 10.1053/j.gastro.2024.08.050 -> 10.1053/j.gastro.2024.07.040; 10.1016/j.jhep.2025.08.034 -> 10.1016/j.jhep.2025.07.003; 10.1016/j.jsams.2025.10.015 -> 10.1016/j.jsams.2025.08.020; 10.1016/j.plrev.2023.05.004 -> 10.1016/j.plrev.2022.07.005; 10.1016/j.taap.2025.117617 -> 10.1016/j.taap.2025.117598; 10.1016/j.ijrobp.2009.09.017 -> .09.013 and .09.014 |
| Unrelated item | 6 | 10.1016/j.ajp.2020.102052 -> 10.1016/j.bbadis.2015.08.015; 10.3389/fpubh.2026.1867302 -> 10.3389/fnins.2024.1451060; 10.1177/14604582231184983 -> 10.1177/2047487317692194; 10.1016/j.dld.2025.05.016 -> 10.1016/j.dld.2024.12.014 and 10.1016/j.dld.2025.04.040; 10.6028/nist.ir.8427.ipd -> 10.6028/nist.ir.8425a.ipd; 10.6028/nist.ir.8459.ipd -> 10.6028/nist.sp.800-233.ipd |
| DOI typo: one digit or the year | 3 | 10.2514/6.2018-4148.c1 -> 10.2514/6.2018-4158; 10.2514/6.2019-2374.c1 -> 10.2514/6.2018-2374; 10.2514/6.2022-2472.c1 -> 10.2514/6.2021-2472 |
| Article number used as a DOI | 1 | 10.1016/j.cej.2026.178956 (withdrawn corrigendum citing "Chem. Eng. J. 469 (2023) 143398") -> 10.1016/j.cej.2023.143398, a uranium-extraction paper |
| The special issue's Expression of Concern | 2 | 10.1016/j.est.2021.103553 and 10.1016/j.est.2021.103621 -> 10.1016/j.est.2023.108949 |
| Front matter | 1 | 10.1016/j.annder.2012.06.003 -> 10.1016/j.annder.2011.12.002 (list of authors) |

The depositing publishers are Elsevier (12 notices), AIAA (3), NIST (2), Frontiers (1) and
SAGE (1). Another 8 notices link the wrong item, but that item happens to be retracted itself
(for example 10.1111/iwj.70557 -> 10.1111/iwj.13795).

## Does it reach users?

We checked OpenAlex `is_retracted` for every innocent target on 2026-11-11. **All 11 whose wrong
link is typed `retraction` are shown as retracted. None of the 9 whose wrong link is typed
`withdrawal` are.** Among the 11: a Gastroenterology study of diet and colorectal cancer, a
Journal of Hepatology review of AI uptake, a UK Biobank study of physical activity and kidney
disease, a randomized trial of edaravone dexborneol, the ASTRO consensus statement on partial
breast irradiation, and an Expression of Concern. None of the 19 notices carries a Retraction Watch link in
Crossref, so the wrong flag comes from the publisher's deposit alone.

The split by link type is our own observation from 20 papers. It suggests that OpenAlex ignores
`withdrawal` links. If that is true, OpenAlex would also miss real withdrawals that only Crossref
records: in a quick look at 13 recent `withdrawal` targets, OpenAlex flagged 1. Audit 13
([PREREG-13.md](../PREREG-13.md)) tests this across all of Crossref.

## Why it is new

Earlier work documents other ways a Crossref-based retraction flag goes wrong. Hauschke &
Nazarovets (J. Inf. Sci., arXiv 2403.13339) show OpenAlex flagging corrected papers and
expressions of concern. Tesseract Semantics' retraction register ontology (Aug 2026) covers
notices flagged as retracted and self-referential deposits. Our audits 1-9 cover corrections typed
as retractions, reversed links and withdrawn corrigenda. We found no earlier list of publisher
retraction links that point at an unrelated or neighbouring paper, and no description of these
mechanisms (searched 2026-11-11).

## How to check one

```
https://api.crossref.org/works/10.1016/j.ajp.2020.102052        (update-to -> the BBA paper)
https://api.openalex.org/works/doi:10.1016/j.bbadis.2015.08.015  (is_retracted: true)
```

## Limits

- Lower bound: only links whose target title shares few words with the notice title were read.
- We read metadata, not every notice's full text. A notice with a generic title could hide more.
- Crossref and OpenAlex are live databases. These records may be corrected after 2026-11-11.
