# Grading 7: papers shown as retracted because their correction was retracted or withdrawn

Graded 2026-11-10 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against [PREREG-7.md](PREREG-7.md).
Made with AI agents working in MV2's name; no human has reviewed it. Text CC BY 4.0.
Results: [results/audit7/](results/audit7/). The list of affected papers is
[results/audit7/only_via_rc.csv](results/audit7/only_via_rc.csv).

**Score: 7 of 8 predictions held (P5 failed). All three gates passed.**

## Timing

PREREG-7.md and the code were committed at 2026-11-09 20:45 UTC (commit 41ddda5). Job
`retracted-correction-a7-v1` started at 2026-11-10 02:07 UTC and finished at 02:11 UTC. Its 9 unit
tests passed after the data step.

## Gates

| Gate | Result |
|---|---|
| G1: both walks complete, at least 80,000 records | passed: 85,056 records |
| G2: instrument cases | passed: all 5 ONLY cases `only_via_rc`, heliyon `also_retracted`, lfs and ijpx `swap` |
| G3: updates lookups fail for at most 5%; OpenAlex not aborted | passed: 0 failures; OpenAlex found 69 of 69 |

## Predictions

| | Prediction | Result | |
|---|---|---|---|
| P1 | 150 to 2,000 rc relations | 160 (150 notices, 155 papers) | held |
| P2 | Elsevier at least 80% | 159 of 160 (99.4%); 1 Informa | held |
| P3 | at least 60 `only_via_rc`, 15% to 70% | 69 of 160 (43.1%) | held |
| P4 | OpenAlex flags at least 90% of the retraction group and at most 10% of the other group | 46 of 46 (100%) and 2 of 23 (8.7%) | held |
| P5 | at least 40% of retraction-typed only_via_rc relations have status `swap` | 6 of 46 (13.0%) | **failed** |
| P6 | at least 70% of withdrawal/removal-typed ones have status `none` | 22 of 23 (95.7%) | held |
| P7 | the only_via_rc papers have at least 1,500 OpenAlex citations | 2,831 | held |
| P8 | hand check of 20: at least 16 "paper not retracted, only its correction", at most 2 "really retracted" | 20 and 0 | held |

Why P5 failed: we expected most retraction-typed cases to be "RETRACTED: Corrigendum" records with a
separate retraction notice. In fact only 8 of the 46 are titled RETRACTED; 38 are titled
WITHDRAWN. A withdrawn corrigendum has no separate notice, so it cannot show a swap. Among the
8 "RETRACTED: Corrigendum" records, 6 have a swap: the notice that retracts the corrigendum is
deposited as `erratum` (post hoc, not pre-registered).

## Hand check (P8)

Each of the 20 sampled relations ([grade20_graded.csv](results/audit7/grade20_graded.csv)) was read
on 2026-11-10 in live Crossref (the paper's `updated-by` list and the titles of every notice that
updates it), and in PubMed by DOI for 13 of the papers (12 found). In 11 of the 20 a valid
corrigendum or erratum exists next to the withdrawn or retracted one. In none is there a separate
retraction notice, a RETRACTED title on the paper, or a Retraction Watch retraction. In the other
9 the withdrawn or retracted correction is the only update, so the grade rests on the absence of
any retraction signal; Elsevier retitles the papers it retracts ("RETRACTED: ..."), and none of
these papers is retitled. One paper (cegh.2024.101559) also has an expression of concern, which
is not a retraction.

## What we found that we did not predict (post hoc, not pre-registered)

1. **The error has reached PubMed.** Two of the 12 papers found in PubMed are marked "Retracted
   Publication": the American Journal of Medicine paper "Red Wine Prevents the Acute Negative
   Vascular Effects of Smoking" (10.1016/j.amjmed.2016.08.025, PMID 27633722) and a Toxicology
   Reports paper (10.1016/j.toxrep.2021.04.002, PMID 33948439). In both, PubMed's "Retraction in"
   link points at the **withdrawn corrigendum** (PMIDs 27852510 and 42441098), which PubMed indexes
   with the publication type "Retraction Notice". Audit 8 ([PREREG-8.md](PREREG-8.md)) measures
   this on all 69 papers.
2. **When the type changes.** The Toxicology Reports corrigendum 10.1016/j.toxrep.2026.102211 carries
   three `update-to` entries to the paper: `erratum` and `withdrawal` dated 2026-02-03, and
   `retraction` dated 2026-06-01. The American Journal of Medicine corrigendum, first online in
   2016, was placed in volume 138 issue 5 (May 2025) with `retraction` dated 2025-05-01. So the
   `retraction` type seems to appear when a withdrawn corrigendum is assigned to an issue. Two
   cases do not establish a rule.
3. **One notice, ten papers.** The withdrawn erratum 10.1016/j.vas.2019.100088 (Veterinary and Animal
   Science) is about a rainbow trout diet paper, but it carries `update-to` type `retraction` to
   10 papers of the journal, 9 of them unrelated (water buffaloes, goats, cats, Nepalese sheep,
   E. coli, catfish oocytes and others). It accounts for 10 of the 69 papers, and OpenAlex marks
   all 10 as retracted.
4. **Notices pointing at the wrong paper.** In at least two more cases the corrigendum's title
   names one paper and its link points at another (cej.2026.178956 names an H2S hydrogel
   paper and points at a uranium-extraction paper; ijhydene.2021.02.076 names a RuPtNi
   dimethylamine-borane paper and points at a hydrazine-borane paper). Not checked further.
5. **Highly cited papers affected.** OpenAlex marks as retracted, among others, "Major Advances in
   Particle Swarm Optimization: Theory, Analysis, and Application" (10.1016/j.swevo.2021.100868,
   491 citations) and a Physics Letters B measurement paper (10.1016/j.physletb.2016.08.019, 186).
   The ESPEN guideline on clinical nutrition in IBD (10.1016/j.clnu.2016.12.027, 660 citations)
   is shown as withdrawn in Crossref but not flagged by OpenAlex.

## Prior art, searched again 2026-11-10

The Crossref community forum topic "[Elsevier] Metadata errors: 18 articles (wrongly?) marked
retracted" (G. Cabanac, 2025-11-24; Crossref staff said on 2026-06-05 that Elsevier is
investigating) gives no cause. Its DOI list is in a PubPeer comment we could not read, so we
cannot say whether these cases overlap with it. Nothing else we found describes this mechanism.

## Limits

One reading of live data on one day. The hand check reads metadata, not publisher web pages (we
could not open ScienceDirect). "Not retracted" is judged from the absence of any retraction
notice, title change or Retraction Watch entry, plus the presence of a replacement correction
where there is one. 160 relations is a small census; it covers only notices whose titles say
what they are.
