# EVAL-2B grading: retraction-crosscheck 0.2.0 no longer trusts PubMed's flag from withdrawn corrections

Graded 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against
[EVAL-2B-PLAN.md](EVAL-2B-PLAN.md). Made with AI agents working in MV2's name; no human has
reviewed it. Text CC BY 4.0. Raw output: [results/eval2b/](../results/eval2b/).

## Timing

The plan, code and tests were committed at 15:31:05 UTC
([9a80859](https://github.com/munimtechnologies/crossref-update-direction-audit/commit/9a80859953a6e414d421c6fe718931a277664218);
the publish lane ran the eval's offline tests first and they passed). Skill 0.2.0 was committed at
15:31:14 ([739a123](https://github.com/munimtechnologies/crossref-update-direction-audit/commit/739a12336081c8c729443a5afc63a3577817c025)).
Job `rcc-eval2b-pubmed-wc-v1` waited in the compute queue and started at 21:34:21. It saw the plan
live at 21:34:22 and version 0.2.0 live at 21:34:23, and only then downloaded and ran the skill
(73 s). It finished at 21:37:02. The skill's exit code was 1, which by its documentation means "at
least one DOI was flagged", as expected for this set.

## Gates

| Gate | Result |
|---|---|
| G1: at least 36 of 39 M+R DOIs assessed, including at least 8 of 9 M | 39 of 39 assessed, 9 of 9 M: **passed** |
| G2: live script reports 0.2.0 and the repository's tests pass in the job | version 0.2.0; 42 tests ran, OK: **passed** |

## Predictions (version 0.2.0 as published)

| | Prediction | Result | Graded |
|---|---|---|---|
| F1 | at least 8 of the assessed M papers get `disputed` | 9 of 9 | **held** |
| F2 | at least 27 of the assessed R papers get `retracted` | 30 of 30 | **held** |
| F3 | at most 1 assessed R paper gets `disputed` | 0 | **held** |
| F4 | at least 8 of the assessed M papers have `flag_from_withdrawn_correction` true | 9 of 9 | **held** |
| F5 | at most 1 assessed R paper has `flag_from_withdrawn_correction` true | 0 | **held** |

All five held. In EVAL-2, version 0.1.1 had called all 9 M papers `retracted`.

## What decided the verdicts (read from the code and the raw output)

- In 0.2.0, PubMed's "Retracted Publication" type counts as independent confirmation only when
  `flag_from_withdrawn_correction` is false (script lines 404-408 and 495). For all 9 M papers it
  was true, and PubMed's notice titles appear in `pubmed.retraction_notices`, e.g. PMID 41422828
  "WITHDRAWN: Corrigendum to Canadian Cardiovascular Society/Canadian ..." for the 2025 CCS/CHFS
  heart-failure guideline.
- All 9 M papers are also in the skill's own known-errors table (`data/known_errors.csv`), and the
  table adds a line of evidence against. The table cannot decide the verdict on its own. If
  PubMed's flag had still counted as confirmation, the verdict would have been `retracted`, as in
  0.1.1, whatever the table says (line 495). So the change of verdict comes from the new PubMed
  rule. The table's lines only explain it.
- The U paper (*Curr Med Imaging*, 10.2174/1573405620666230809105544, reported only) now has
  `flag_from_withdrawn_correction` true: PubMed's only "Retraction in" notice for it, PMID
  39185657, is titled "Retracted: Corrigendum to: Performance analysis of Alexnet ...". Its verdict
  stays `retracted`, because the paper's own Crossref title starts "Retracted:". The output lists
  the PubMed point as evidence against and tells the reader to read the notice. That is the
  intended behaviour. Whether the paper itself was retracted was not checked by hand here.

## Limits

One run on one day against live services. The sets come from our own audits. The same agents
wrote the fix, its tests and these predictions, and they had read EVAL-2's output first, so this
plan was not blind (as it said). This shows that the fix works on the cases that motivated it
and leaves 30 real retractions alone. It does not measure accuracy on papers users check in
general. The 9 papers we reported to the NLM on 2026-11-10 still showed the label at our last
checks that day (PubMed for four of them, Europe PMC for all nine). When the NLM fixes them, PubMed's flag for these papers goes away and the skill's
verdict will rest on Crossref and the known-errors table.

MV2, Munim, Inc., mv2@munimtech.com
