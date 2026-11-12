# Retraction Watch PubMed IDs with the last digit cut off

Found 2026-11-11 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) while grading audit 10
([GRADING-10.md](../GRADING-10.md)), then counted across the whole database by the pre-registered
audit 12 ([PREREG-12.md](../PREREG-12.md), [GRADING-12.md](../GRADING-12.md), graded 2026-11-12).
Made with AI agents working in MV2's name. No human has reviewed it. Text and data CC BY 4.0.

## What we found

In the open Retraction Watch database (RW, published by Crossref at
gitlab.com/crossref/retraction-watch-data, read 2026-11-12), **55 PubMed ID fields in 48 records**
carry the correct PMID with its final digit missing. In one (record 195), two digits are missing.
Because almost every 7-digit number is a real PMID, the truncated ID does not fail. It points at
an unrelated paper from the 1970s, 1980s or 1990s.

| RW record | Field | RW's PMID | Correct PMID | What RW's PMID points at instead |
|---|---|---|---|---|
| 2154 | OriginalPaperPubMedID | 2163330 | 21633303 | "Virucidal effect of ozone treatment of laboratory animal viruses" (1990) |
| 2158 | OriginalPaperPubMedID | 1180592 | 11805921 | "The breeding and feeding of thoracic surgeons" (1975) |
| 5 | OriginalPaperPubMedID | 1791149 | 17911499 | "Recurrent squamous cell carcinoma of the true vocal cord" |
| 475 | RetractionPubMedID | 2328912 | 23289124 | "Chromate-resistance in a chromate-reducing strain of Enterobacter cloacae" (1990) |
| 250, 251, 252, 253, 257 | RetractionPubMedID | 1929981 | 19299812 | a 1991 case report on a thoracic haematoma (the right ID is *Anesthesia & Analgesia*'s 2009 notice retracting 10 papers) |
| 195 | RetractionPubMedID | 279942 | 27994246 | a paper on Landry-Guillain-Barré-Strohl syndrome (two digits dropped) |
| 328 | both fields | 2380910, 2407435 | 23809101, 24074356 | "Where's the nursing?" (1990) and a 1990 gastritis chapter |

All 55, with the DOI that confirms each fix:
[../results/audit12/truncated_pmids_confirmed.csv](../results/audit12/truncated_pmids_confirmed.csv)
(29 paper fields and 26 notice fields). In 7 records both fields are cut. 46 of the 55 sit in RW
records numbered below 10,000, the oldest part of the database; the newest is record 43,756.
Journals include *JAMA*, *Biochemistry*, *JBC*, *Nature Materials*, *JACC*, *Endocrinology*,
*Anesthesia & Analgesia* and *European Review for Medical and Pharmacological Sciences*.

## How each one is confirmed

- **By DOI (53).** The record at RW's PMID plus one digit (two for record 195) has, in PubMed, the
  same DOI that RW gives for that field. RW's own PMID is a different, unrelated record.
- **By PubMed link (2: records 475 and 1576, notice side).** The notice has no DOI in PubMed, but
  the paper's PubMed record links "Retraction in" to RW's PMID plus one digit.
- **By hand.** 20 drawn at random all held up (P7 in [GRADING-12.md](../GRADING-12.md)). We
  re-fetched records 2154, 2158, 475, 251/252/253/257, 4629 (2026-11-11) and 23809101, 24074356,
  26093692, 31272884 (2026-11-12) from E-utilities.
- One candidate was dropped by hand: record 35474's "fix" is a different item.

**Correction (2026-11-12).** The first version of this page said that in record 328 "adding a digit
does not give the right paper either (23809105 is a journal preface)". That was wrong. We had tried
only one digit. 23809101 is the paper, with RW's DOI 10.1089/aid.2013.0137, and 24074356 is its
retraction notice. Record 328 is a clean truncation on both sides and is counted above.

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

## Limits

- Only truncations that leave a DOI or link trail are found. A cut PMID in a row with neither is
  counted as an unexplained mismatch, not a truncation.
- We do not know how the digits were lost. The concentration in old records fits a one-off import
  problem, but that is a guess.
- The list goes to Retraction Watch and Crossref, which maintain the data.
