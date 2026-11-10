# When a correction is withdrawn, the paper is shown as retracted

By MV2, Munim, Inc. (mv2@munimtech.com), 2026-11-10. Made with AI agents working in MV2's name;
no human has reviewed it. Text CC BY 4.0. Pre-registered as audit 7 ([PREREG-7.md](../PREREG-7.md),
graded in [GRADING-7.md](../GRADING-7.md): 7 of 8 predictions held).

## The mechanism

A publisher sometimes withdraws or retracts a **correction** (a corrigendum published twice, or
one that was wrong). Its Crossref record is retitled "WITHDRAWN: Corrigendum to ..." or
"RETRACTED: Corrigendum to ...", and at the same time the correction's link to the paper it
corrected changes type, from `erratum` to `retraction` or `withdrawal`. Crossref then lists the
**paper** as retracted or withdrawn, and so does anything that reads Crossref.

## How often

Among the 85,056 Crossref records with a retraction, withdrawal or removal update (read on
2026-11-10), 160 links come from retracted, withdrawn or removed corrections. 159 of them are
Elsevier's. For **69 papers**, such a link is the only sign of a retraction: no retraction notice,
no RETRACTED title, no Retraction Watch entry. OpenAlex marks **48 of the 69 as retracted** (all
46 whose link is typed `retraction`). Together the 69 papers have 2,831 OpenAlex citations. A
hand check of 20 found none that was really retracted.

The full list: [results/audit7/only_via_rc.csv](../results/audit7/only_via_rc.csv).

## Examples

| Paper | Shown as | Why |
|---|---|---|
| Major Advances in Particle Swarm Optimization (Swarm Evol. Comput. 2021, 10.1016/j.swevo.2021.100868), 491 citations | retracted (Crossref, OpenAlex) | withdrawn corrigendum 10.1016/j.swevo.2021.100905 |
| Red Wine Prevents the Acute Negative Vascular Effects of Smoking (Am J Med 2017, 10.1016/j.amjmed.2016.08.025) | retracted (Crossref, OpenAlex, **PubMed**) | withdrawn corrigendum 10.1016/j.amjmed.2016.11.002, which PubMed indexes as a "Retraction Notice" |
| ESPEN guideline: clinical nutrition in IBD (Clin Nutr 2017, 10.1016/j.clnu.2016.12.027), 660 citations | withdrawn (Crossref) | withdrawn corrigendum 10.1016/j.clnu.2019.01.017; a valid erratum replaced it |
| 10 papers in Veterinary and Animal Science | retracted (Crossref, OpenAlex) | one withdrawn erratum (10.1016/j.vas.2019.100088) about a single trout-diet paper links to all 10 |

When a "RETRACTED: Corrigendum" record has its own retraction notice, that notice is usually
deposited as an `erratum` (6 of 8 cases): the two types look swapped.

## Check one yourself

```
https://api.crossref.org/works/10.1016/j.amjmed.2016.08.025      (see "updated-by")
https://api.crossref.org/works/10.1016/j.amjmed.2016.11.002      (see "title" and "update-to")
```

## What would fix it

The correction's `update-to` should keep its correction type, and the withdrawal or retraction of
the correction should be expressed as an update to the **correction's** DOI, not the paper's.
Tools that flag retractions can guard against this by checking whether the updating record's
title is a correction (see the `retraction-crosscheck` skill in this repository).

## Limits

Metadata only; publisher web pages were not read. "Not retracted" rests on the absence of any
retraction signal and, for 11 of the 20 checked, on a valid replacement correction. One day's
reading; records change.
