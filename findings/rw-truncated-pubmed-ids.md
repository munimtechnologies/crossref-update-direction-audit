# Retraction Watch PubMed IDs with the last digit cut off

Found 2026-11-11 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) while grading audit 10
([GRADING-10.md](../GRADING-10.md)). This is **post hoc**: no prediction was made about it, so the
full count is pre-registered separately as audit 12 ([PREREG-12.md](../PREREG-12.md)). Made with AI
agents working in MV2's name. No human has reviewed it. Text and data CC BY 4.0.

## What we found

In the open Retraction Watch database (RW, published by Crossref at
gitlab.com/crossref/retraction-watch-data, read 2026-11-10), 34 rows carry a PubMed ID that is
the correct PMID with its final digit missing. In one row, two digits are missing. Because almost
every 7-digit number is a real PMID, the truncated ID does not fail: it points at an unrelated paper
from the 1970s, 1980s or 1990s.

| RW record | Field | RW's PMID | Correct PMID | What RW's PMID points at instead |
|---|---|---|---|---|
| 2154 | OriginalPaperPubMedID | 2163330 | 21633303 | "Virucidal effect of ozone treatment of laboratory animal viruses" (1990) |
| 2158 | OriginalPaperPubMedID | 1180592 | 11805921 | "The breeding and feeding of thoracic surgeons" (1975) |
| 5 | OriginalPaperPubMedID | 1791149 | 17911499 | "Recurrent squamous cell carcinoma of the true vocal cord" |
| 475 | RetractionPubMedID | 2328912 | 23289124 | "Chromate-resistance in a chromate-reducing strain of Enterobacter cloacae" (1990) |
| 251, 252, 253, 257 | RetractionPubMedID | 1929981 | 19299812 | a 1991 case report on a thoracic haematoma (the right ID is *Anesthesia & Analgesia*'s 2009 notice retracting 10 papers) |
| 195 | RetractionPubMedID | 279942 | 27994246 | a paper on Landry-Guillain-Barré-Strohl syndrome (two digits dropped) |

All 34 rows, with the evidence for each, are in
[../results/audit10/truncated_pmids_a10.csv](../results/audit10/truncated_pmids_a10.csv): 18 paper
PMIDs and 16 notice PMIDs, covering 31 distinct truncated values. Journals include *JAMA*,
*Biochemistry*, *JBC*, *Nature Materials*, *JACC*, *Endocrinology* and *Anesthesia & Analgesia*.

## How each one is confirmed

- **Paper side (18).** PubMed's own retraction notice (the PMID RW gives) links "Retraction of"
  to an 8-digit PMID. That record's DOI equals RW's `OriginalPaperDOI`, and its PMID is RW's
  PMID plus one digit. RW's 7-digit PMID is a different, unrelated record.
- **Notice side (16).** The paper's PubMed record (the PMID RW gives) links "Retraction in" to an
  8-digit notice PMID, which is RW's notice PMID plus one digit (two for record 195).
- Rechecked by hand in E-utilities on 2026-11-11: records 2154, 2158, 475, 251/252/253/257 and
  4629.

Not every 7-digit PMID in a recent row is a clean truncation. In record 328 (a 2013 *AIDS Res Hum
Retroviruses* retraction), both PMIDs, 2380910 and 2407435, point at unrelated papers. Adding a
digit does not give the right paper either (23809105 is a journal preface). That row is wrong in
another way and is not counted above.

## Why it matters

Tools that join RW to PubMed by PMID attach these retractions to the wrong paper. A 1990
virology paper "gets" a 2015 retraction, while the retracted paper's PMID is never found. Joins by
DOI are not affected, because RW's DOIs in these rows are right.

## Prior work

We found no report of truncated or shifted PMIDs in RW. The nearest work: Schneider et al.,
"Analyzing the consistency of retraction indexing" (Illinois data, Appendix 10: duplicated PMIDs
in a union list); Sebo & Sebo (Account Res 2025, doi:10.1080/08989621.2025.2484555) on coverage;
Arjomandi (arXiv:2611.10474) on flag coverage; the Tesseract Semantics register ontology (DOI
level). Searched 2026-11-11.

## Limits and next step

- These 34 come only from audit 10's subset: rows typed "Retraction" with both PMIDs present.
  Audit 12 checks every row and both fields, including rows where the truncation leaves no
  PubMed link to follow.
- We do not know how the digits were lost. 31 of the 34 rows have RW record IDs below 10,000
  (the older part of the database), which fits a one-off import problem, but that is a guess.
- After audit 12 is graded, the full list goes to Crossref and Retraction Watch, which maintain
  the data.
