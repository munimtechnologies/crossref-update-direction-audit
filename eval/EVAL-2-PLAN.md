# EVAL-2 plan: does retraction-crosscheck trust PubMed's flag when it comes from a withdrawn correction?

Written 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before job
`rcc-eval2-pubmed-wc-v1` ran. Made with AI agents working in MV2's name; no human has reviewed
it. Code: [eval_skill_pubmed.py](../eval_skill_pubmed.py) (Apache-2.0), offline tests in
[test_eval_skill_pubmed.py](../test_eval_skill_pubmed.py). Text CC BY 4.0. The job waits until this
file is live on GitHub before it runs the skill, and records when it saw it.

## Why

Audits 8 and 9 ([GRADING-8.md](../GRADING-8.md), [GRADING-9.md](../GRADING-9.md)) found nine papers
that PubMed types "Retracted Publication" only because a withdrawn correction of theirs
("WITHDRAWN: Corrigendum to ...") is indexed as a "Retraction Notice" and linked as "Retraction in".
Three of them (the two-part *J Am Acad Dermatol* chronic graft-versus-host disease review and an
*Int J Biol Macromol* paper) have no retraction link to the paper in Crossref at all; PubMed's
flag is the only source, and OpenAlex also shows them as retracted.

The skill's published rules (SKILL.md, version 0.1.1) count a PubMed retraction flag as
independent confirmation of a retraction. If so, the skill will call these nine papers
`retracted`. Audit 9 also found the opposite trap: PubMed "Retraction Notice" records titled
"Erratum to: ..." are, in every case we checked, real retractions (Retraction Watch lists them as
retractions). A fix must not turn those into `disputed`.

## Sets (fixed now, from GRADING-9.md)

- **M (9, mechanism):** 10.1016/j.cjca.2025.07.027, 10.1016/j.amjmed.2016.08.025,
  10.1016/j.ejogrb.2015.07.009, 10.1016/j.intimp.2024.111636, 10.1016/j.wneu.2018.05.128,
  10.1016/j.toxrep.2021.04.002, 10.1016/j.jaad.2022.12.023, 10.1016/j.jaad.2022.12.024,
  10.1016/j.ijbiomac.2024.136739. No retraction notice of their own in PubMed, Crossref or
  Retraction Watch on 2026-11-10; PubMed's only "Retraction in" is a withdrawn correction.
- **R (30, real retractions reached through correction-titled notices):** the 13 papers of the
  "Retraction note. Erratum to: ..." notices and the 17 papers from audit 9's random sample whose
  notice is titled as an erratum or correction. Each has a Retraction Watch retraction entry in
  Crossref and/or a RETRACTED/WITHDRAWN title or publisher withdrawal (listed in the code).
- **U (1, unclear, reported only):** 10.2174/1573405620666230809105544.

## Method

The job downloads the live skill (script, known-errors table, SKILL.md, CHANGELOG.md and the
repository's test_retraction_crosscheck.py) from the main branch, runs the repository tests once,
then runs `retraction_crosscheck.py --file dois.txt --json --max 200` once on the 40 DOIs (one per
line) and reads each verdict. Copies of every downloaded file and the raw output are kept.

## Gate

- G1: at least 36 of the 39 M+R DOIs come back with a verdict other than `not_found` or
  `lookup_failed` (or empty), including at least 8 of the 9 M papers.

## Predictions (version 0.1.1 as it is)

- E1: at least 7 of the assessed M papers get the verdict `retracted` (the suspected flaw).
- E2: at least 27 of the assessed R papers get `retracted`.
- E3: at most 1 assessed R paper gets `disputed`.

`grade()` in the code grades them as worded. If E1 holds, version 0.2.0 will stop counting a
PubMed flag as confirmation when every PubMed "Retraction in" notice of the paper is titled as a
withdrawn or retracted correction, and will be re-run on the same 40 DOIs.

## Limits

One run on one day against live services. The sets were chosen by us from audits 8 and 9; R is
not a random sample of all retractions. The skill reads more sources than this plan names, so a
verdict can move for reasons other than the PubMed rule; the raw output is kept to show why.
