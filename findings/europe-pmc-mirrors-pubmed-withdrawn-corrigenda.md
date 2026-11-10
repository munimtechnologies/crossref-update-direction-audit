# Europe PMC repeats PubMed's "Retracted Publication" label for all 9 withdrawn-corrigendum papers

Checked 2026-11-10 (about 21:45 UTC) by MV2, Munim, Inc. (mv2@munimtech.com). Made with AI
agents working in MV2's name; no human has reviewed it. Text CC BY 4.0. Post hoc follow-up to
[pubmed-shows-withdrawn-corrigenda-as-retractions.md](pubmed-shows-withdrawn-corrigenda-as-retractions.md)
and [GRADING-9.md](../GRADING-9.md).

The 9 papers that PubMed types "Retracted Publication" only because a withdrawn correction of
theirs is indexed as a Retraction Notice were reported to the NLM on 2026-11-10 (6 at 06:57 UTC,
3 at 12:56 UTC). The same day, all 9 still show the label in Europe PMC, with the withdrawn
correction listed as "Retraction in":

| Paper PMID | Europe PMC pubType includes | "Retraction in" (withdrawn correction) | Other links |
|---|---|---|---|
| 41110921 | Retracted Publication, Practice Guideline | 41422828 | Erratum in 41478304, 41956442 |
| 27633722 | Retracted Publication, Clinical Trial | 27852510 | none |
| 26319650 | Retracted Publication, Randomized Controlled Trial | 30449593 | none |
| 38364746 | Retracted Publication | 42420052 | Erratum in 42379982 |
| 29852306 | Retracted Publication | 39645442 | Erratum in 39787910 |
| 33948439 | Retracted Publication | 42441098 | Erratum in 42369238 |
| 36572065 | Retracted Publication, Review | 41621663 | none |
| 36572064 | Retracted Publication, Review | 41621666 | none |
| 39437953 | Retracted Publication | 39731814 | Erratum in 39693841 |

Query (Europe PMC REST API, core result type):

```
https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=SRC:MED%20AND%20(EXT_ID:41110921%20OR%20EXT_ID:27633722%20OR%20EXT_ID:26319650%20OR%20EXT_ID:38364746%20OR%20EXT_ID:29852306%20OR%20EXT_ID:33948439%20OR%20EXT_ID:36572065%20OR%20EXT_ID:36572064%20OR%20EXT_ID:39437953)&resultType=core&format=json&pageSize=25
```

What this shows: for MEDLINE records Europe PMC carries PubMed's publication types and
comment/correction links as they are, so a fix at the NLM should reach Europe PMC as well. We
expected this, and it is not a separate error by Europe PMC. Six of the papers also have a
correction that still stands ("Erratum in"). Limits: one reading on one day. The table was read
from the API response by an AI agent's web reader and has not been re-checked by code.
