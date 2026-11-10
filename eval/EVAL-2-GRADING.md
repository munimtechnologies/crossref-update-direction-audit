# EVAL-2 grading: retraction-crosscheck 0.1.1 trusts PubMed's flag from withdrawn corrections

Graded 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against
[EVAL-2-PLAN.md](EVAL-2-PLAN.md). Made with AI agents working in MV2's name; no human has reviewed
it. Text CC BY 4.0. Raw output: [results/eval2/](../results/eval2/).

## Timing

The plan, code and tests were committed at 12:55:30 UTC
([611b7a4](https://github.com/munimtechnologies/crossref-update-direction-audit/commit/611b7a4c8d805d50c3b11681f2ab0d6cdaf9761d);
the publish lane ran the eval's offline tests first and they passed). Job `rcc-eval2-pubmed-wc-v1`
started at 13:41:14, saw the plan live at 13:41:16 and only then downloaded and ran the skill. It
finished at 13:43:52. The repository's own 31 skill tests passed inside the job.

## Gate

| Gate | Result |
|---|---|
| G1: at least 36 of 39 M+R DOIs assessed, including at least 8 of 9 M | 39 of 39 assessed, 9 of 9 M: **passed** |

## Predictions (version 0.1.1 as published)

| | Prediction | Result | Graded |
|---|---|---|---|
| E1 | at least 7 of the assessed M papers get `retracted` (the suspected flaw) | 9 of 9 | **held** |
| E2 | at least 27 of the assessed R papers get `retracted` | 30 of 30 | **held** |
| E3 | at most 1 assessed R paper gets `disputed` | 0 | **held** |

The U paper (*Curr Med Imaging*, 10.2174/1573405620666230809105544) came out `retracted`, because
its own Crossref title starts "Retracted:" and PubMed marks it; reported only.

## Why (from the raw output)

For every one of the 9 M papers, the only "for" line is "PubMed (PMID ...) marks the paper as
retracted.", and there are no "against" lines. 0.1.1 read the withdrawn corrections' titles in
Crossref ("WITHDRAWN: Corrigendum to ...") but classed them as "mixed" and only noted them. It
never read the titles of PubMed's own "Retraction in" notices. So the flaw was exactly the one the
plan suspected: PubMed's "Retracted Publication" type was counted as independent confirmation
even when it comes from a withdrawn correction. For the three papers with no Crossref retraction
link at all (the two *J Am Acad Dermatol* chronic graft-versus-host disease reviews and the
*Int J Biol Macromol* paper), 0.1.1 also added "Crossref links no retraction notice to this
record, so tools that read only Crossref update types will miss it.". That advice is backwards for
these papers.

## What changes

[Version 0.2.0](../skills/retraction-crosscheck/CHANGELOG.md) reads the PubMed titles of a paper's
"Retraction in" notices. PubMed's flag now confirms a retraction only if at least one of those
notices is not titled as a withdrawn or retracted correction; otherwise it counts against. A
Crossref retraction or withdrawal from a notice titled as a withdrawn correction also counts
against. Notices titled "Erratum to: ..." are not touched (audit 9: they are mostly real
retractions). [EVAL-2B-PLAN.md](EVAL-2B-PLAN.md) pre-registers a re-run of the same 40 DOIs on
0.2.0.

## Limits

One run on one day against live services. The sets were chosen from our own audits and are not
random samples. This evaluation shows the old rule's failure on 9 known cases; it does not
measure how often the failure occurs among all papers checked by users. Our audits found 9 such
papers in PubMed in all, so it is rare, but the papers involved include a national clinical
guideline and a widely cited review.

MV2, Munim, Inc., mv2@munimtech.com
