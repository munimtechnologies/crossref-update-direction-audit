# Pre-registration 7: papers shown as retracted because their correction was retracted

Written 2026-11-09 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before the audit job ran and
before any of its output existed. Made with AI agents working in MV2's name; no human has
reviewed it. Code: [retracted_correction_audit.py](retracted_correction_audit.py) (Apache-2.0),
tests: [test_retracted_correction_audit.py](test_retracted_correction_audit.py). Text CC BY 4.0.

## Why

Hand grading of audit 5 ([GRADING-5.md](GRADING-5.md)) turned up a mechanism we had not looked
for. Sometimes a publisher retracts or withdraws a **correction**: a corrigendum published twice
by mistake, or a corrigendum that is itself retracted. The correction's Crossref record is then
retitled "RETRACTED: Corrigendum to ..." or "WITHDRAWN: Corrigendum to ...". Its own
`update-to` link to the corrected paper changes type at the same time, from a correction to
`retraction` or `withdrawal`. Crossref then lists the **paper** as retracted or withdrawn
(`updated-by`), and so do tools that read Crossref. Only the correction was.

Examples checked by hand against live api.crossref.org records on 2026-11-09:

- `10.1016/j.lfs.2008.11.017` (Life Sciences 2009, 98 Crossref citations) is `updated-by`
  `10.1016/j.lfs.2022.120407` with type `retraction`. That record is "RETRACTED: Corrigendum to
  ...". The notice that retracts the corrigendum, `10.1016/j.lfs.2024.122455` ("Retraction notice
  to Corrigendum to ..."), is deposited with type `erratum`. Retraction Watch types the same
  link `retraction`. The two types look **swapped**.
- `10.1016/j.ijpx.2023.100203`: the same swap. The corrigendum `10.1016/j.ijpx.2025.100319`
  carries `retraction`; its retraction notice `10.1016/j.ijpx.2025.100388` carries `erratum` (to
  both the corrigendum and the paper).
- `10.1016/j.clnu.2016.12.027`, the ESPEN guideline on clinical nutrition in inflammatory
  bowel disease (561 Crossref citations), is `updated-by` `10.1016/j.clnu.2019.01.017`
  ("WITHDRAWN: Corrigendum to ...") with type `withdrawal`, next to the erratum
  `10.1016/j.clnu.2019.03.004` that replaced it.
- `10.1016/j.neuro.2020.12.005` and `10.1016/j.neuroscience.2022.11.029`: the same pattern
  (a withdrawn corrigendum carries `withdrawal`, and a later erratum replaced it).

## Nearest prior work and the delta

- Crossref community forum, "[Elsevier] Metadata errors: 18 articles (wrongly?) marked
  retracted" (G. Cabanac, 2025-11-24; Crossref staff replied up to 2026-06-05). The thread
  gives no cause, and its DOI list is in a PubPeer report we could not read. Our census may
  explain some of those 18. We will say so only if we can match DOIs.
- Hauschke & Nazarovets (arXiv:2403.13339): OpenAlex showed corrected papers as retracted
  between December 2023 and March 2024 because of an OpenAlex bug. Crossref was right in their
  cases. Here, Crossref itself is wrong.
- Tesseract Semantics, "Retraction register ontology" (2026): invalid update types and how far
  Crossref and Retraction Watch disagree. It has no notice-level mechanism.
- Our audits 4, 4b and 5 and findings/corrections-deposited-as-retractions.md: correction notices
  typed `retraction`. Here the notice is a correction that was **itself** retracted or withdrawn.
- Delta: the first census of retracted or withdrawn corrections whose links make the corrected
  paper look retracted, and the first check of whether the notices retracting those corrections
  are typed as errata. Web searches on 2026-11-09 found no earlier description.

## Population and method

- Crossref: every record matched by `filter=update-type:X` for X in retraction, withdrawal,
  partial_retraction and removal, deduplicated by DOI. Keep `update-to` entries with one of those
  types, `source` publisher, and target != record (self-loops are kept only as evidence that
  the target retracts itself).
- Notice title classes (code: `notice_class`): **rc** is a retracted, withdrawn or removed
  correction (title starts with RETRACTED/WITHDRAWN/RETRACTED ARTICLE/REMOVED/TEMPORARY REMOVAL,
  then Corrigendum/Erratum/Correction/Addendum); **rn** is a retraction notice of a correction
  ("Retraction notice to Corrigendum", "Retraction: Corrigendum:", "Retraction Note: Correction
  to:"); **correction** is any other title with errat/corrig/correction/addend; **empty** and
  **plain** cover the rest.
- For each rc relation N -> T, the code looks for independent evidence that T really is retracted:
  `rw` (Retraction Watch has a retractive relation to T), `self` (T's own record carries a
  retractive update to itself), `notice` (a plain or untitled notice has a retractive publisher
  relation to T) or `title` (T's Crossref title starts with RETRACTED/WITHDRAWN or ends with
  "(Retracted)"). If there is any, the verdict is `also_retracted`; otherwise `only_via_rc`.
- For each rc notice N: `filter=updates:N` (10 per request). The status is `retractive_notice`
  (a publisher record updates N with a retractive type), `swap` (none does, but a publisher
  record titled as a retraction or withdrawal notice updates N with another type), `rw_only` or
  `none`.
- OpenAlex `is_retracted` and `cited_by_count` for only_via_rc targets. A target is in the
  "retraction" group if any of its rc relations has type `retraction`; otherwise it is in the
  "other" group (withdrawal/removal/partial).
- Descriptive only (no prediction): rn relations, and how many point at a target whose title
  is not a correction.
- Outputs: summary.json, rc_relations.csv, only_via_rc.csv, grade20.csv (first 20 only_via_rc
  relations by sha256("a7"|notice|target), excluding the 6 G2 targets) and rn_relations.csv.

## What we read before writing this (disclosed)

- Audit 5 output (job crossref-pubmed-link-a5-v1, finished 2026-11-09 14:13 UTC): its 30
  `contradict` relations include 13 notices whose titles hold both a retraction word and a
  correction word, all from Elsevier; most are "RETRACTED: Corrigendum to ..." or "WITHDRAWN:
  Corrigendum to ...". Its 32 `erratum_but_retracted` relations are mostly "RETRACTED:
  Corrigendum to ..." notices whose papers PubMed also lists as retracted. Audit 5 covers only
  targets indexed in PubMed (48%).
- About 20 live Crossref records read by hand for GRADING-5, listed there; the 8 G2 checks below
  come from them.
- No census-level count of rc relations, no updates-filter result beyond the two swap cases and
  no OpenAlex result for any rc target was seen.

## Gates (if a gate fails, P1-P8 are reported descriptively, not graded)

- G1: the retraction and withdrawal walks both complete, with at least 80,000 records.
- G2 (instrument check): all 5 ONLY_CASES get `only_via_rc`; heliyon.2021.e06952 (via
  heliyon.2023.e23950) gets `also_retracted`; lfs.2022.120407 and ijpx.2025.100319 get status
  `swap`.
- G3: updates lookups fail for at most 5% of rc notices. OpenAlex not aborted (P4 and P7 only).

## Predictions (blind to the job's output)

- P1: 150 to 2,000 rc relations.
- P2: Elsevier BV deposited at least 80% of rc relations.
- P3: at least 60 rc relations are `only_via_rc`, and that is between 15% and 70% of rc relations.
- P4: OpenAlex marks as retracted at least 90% of checked only_via_rc targets in the
  "retraction" group, and at most 10% of those in the "other" group (each group needs at least
  5 checked targets, or that part is not graded). This repeats on new cases a post-hoc split
  seen in audit 5: 23 of 23 vs 0 of 7.
- P5: of only_via_rc relations typed `retraction` with a known status, at least 40% have status
  `swap`.
- P6: of only_via_rc relations typed withdrawal or removal with a known status, at least 70%
  have status `none` (Elsevier's in-press withdrawals have no separate notice).
- P7: the distinct only_via_rc targets have at least 1,500 OpenAlex citations in total.
- P8 (hand grading, next step): of the 20 sampled only_via_rc relations (all of them, if fewer),
  at least 16 are judged "paper not retracted or withdrawn; only its correction was", and at
  most 2 are judged "paper really retracted or withdrawn". Evidence for each case: T's Crossref
  record (`updated-by`, title), the notice titles, Retraction Watch, and PubMed or the publisher
  page where readable.

Grading will report each prediction as held, failed or not graded, with the numbers, failures
included. Anything found after the job runs will be labelled post hoc.
