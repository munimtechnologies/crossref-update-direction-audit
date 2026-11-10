# Pre-registration 8: does PubMed also show these papers as retracted?

Written 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before job
`pubmed-propagation-a8-v1` ran. Made with AI agents working in MV2's name; no human has
reviewed it. Code: [pubmed_propagation_audit.py](pubmed_propagation_audit.py) (Apache-2.0), 8 offline
tests in [test_pubmed_propagation_audit.py](test_pubmed_propagation_audit.py). Text CC BY 4.0.

## Question

Audit 7 ([GRADING-7.md](GRADING-7.md)) found 69 papers whose **only** retractive Crossref link
comes from a correction of theirs that was itself retracted, withdrawn or removed (a "WITHDRAWN:
Corrigendum to ..." record whose `update-to` now says `retraction` or `withdrawal`). OpenAlex
marks 48 of them as retracted. A hand check of 20 found no sign that any of the papers was
really retracted.

Does PubMed repeat the error? For each of the 69 papers (`results/audit7/only_via_rc.csv`), the
job finds the PubMed record by DOI and reads its publication types and its comment/correction
links. "Flagged" means the publication type "Retracted Publication" or a "Retraction in" link.
For each "Retraction in" or "Erratum in" link, it reads the linked record's DOI and asks whether
that record is the retracted or withdrawn correction itself.

## What we read before writing this (disclosed)

While hand-grading audit 7 on 2026-11-10 we looked up 13 of the 69 papers in PubMed by DOI and
found 12 of them. Two are flagged:
`10.1016/j.amjmed.2016.08.025` ("Red Wine Prevents the Acute Negative Vascular Effects of
Smoking") and `10.1016/j.toxrep.2021.04.002`. In both, PubMed's "Retraction in" record is the
withdrawn corrigendum (PMID 27852510, DOI 10.1016/j.amjmed.2016.11.002; PMID 42441098, DOI
10.1016/j.toxrep.2026.102211), which PubMed indexes with the publication type "Retraction Notice".
The other 10 (`bbadis.2026.168188`, `pathol.2025.02.011`, `abb.2024.110176`,
`jhazmat.2023.133313`, `neuroscience.2021.11.026`, `gendis.2020.07.005`, `vas.2018.06.001`,
`vas.2017.04.001`, `scr.2014.07.005`, `trsl.2011.10.004`) are not flagged. These cases are used
as the G3 instrument check, and the predictions below are written knowing them, so the sample
counts toward every prediction. The other 56 papers have not been looked up in PubMed.

## Gates (if one fails, the predictions are reported descriptively, not graded)

- G1: the input has at least 60 distinct papers.
- G2: PubMed searches fail for at most 5% of papers.
- G3: amjmed.2016.08.025 and toxrep.2021.04.002 come out flagged with the "Retraction in" record
  being the correction itself; scr.2014.07.005 comes out found and not flagged.

## Predictions

- P1: at least 30 of the papers are found in PubMed by DOI.
- P2: between 5% and 40% of the papers found are flagged as retracted by PubMed.
- P3: of the flagged papers with a readable "Retraction in" record (at least 3 needed), at least
  90% have the retracted or withdrawn correction itself as that record.
- P4: among papers found, at most 10% of the withdrawal/removal group are flagged, and the
  retraction group's flag rate is higher (each group needs at least 5 found papers).
- P5: at least 5 found papers list the retracted or withdrawn correction as "Erratum in".
- P6: at most 2 found papers have a "Retraction in" record that is **not** the correction
  (which would be evidence of a real, separate retraction).

`grade()` in the code grades P1 to P6 exactly as worded and writes them to summary.json.

## Prior work

Audit 7 and the sources it cites. We found no study of PubMed indexing a withdrawn or retracted
correction as the retraction of the paper. PubMed's retraction data come from publishers, so
this asks whether the same deposit error travels to a second index by a second route.

## Limits

DOI matching only; a paper indexed without a DOI counts as not found. One reading on one day.
