# Grading, audit 2: reversed correction and retraction links, found from titles

Graded 2026-11-08 (about 23:00 UTC) against [PREREG-2.md](PREREG-2.md). By MV2, Munim, Inc.
(mv2@munimtech.com). Made with AI agents working in MV2's name; no human has reviewed it.
Text and data CC BY 4.0, code Apache-2.0.

The audit (`reversed_relation_audit.py`, job `crossref-reversed-rel2-v1`) ran on 2026-11-08
from 15:33 to 17:31 UTC. It read 488,049 of the 488,114 records with `update-to` (99.98%),
573,318 relations and 418,327 of 418,411 distinct targets (99.98%).

## Result: gate held; 2 of 5 predictions held

| | Prediction | Result | Held? |
|---|---|---|---|
| G | walk complete, >= 450,000 records, >= 95% of targets found | 488,049 records, 99.98% of targets | yes |
| R1 | >= 1,500 reversed relations | 876 (710 plain + 166 retracted-marked) | **no** |
| R2 | >= 40% of dated reversed relations not caught by audit 1's date rule | 456 of 876 = 52% | yes |
| R3 | >= 25 members, none with half or more | 49 members; largest (Elsevier) 37.6% | yes |
| R4 | >= 34 of 40 sampled reversed relations confirmed (hand-graded) | 26 of 40 | **no** |
| R5 | >= 10% of originals known to OpenAlex not marked `is_retracted` | 0 of 199 | **no** |

## R4: what the 40 sampled links really are

Each pair was read through api.crossref.org. The grades are in
[results/audit2/grade_reversed40_graded.csv](results/audit2/grade_reversed40_graded.csv).

- **26 confirmed reversed links.** The original article (or the retracted article itself)
  carries `update-to` pointing at its own erratum, correction or retraction notice. They come
  from Springer Nature (*Nature*, *Nature Medicine*, *Nature Genetics*, *Nature Neuroscience*,
  *Nature Reviews MCB*), Rockefeller University Press (*JGP*, *JEM*, *JCB*), Wolters Kluwer /
  Medknow, IWA, AIP, MIT Press, Brieflands, Wiley, Elsevier (*Lancet Oncology*) and others. In
  two of the 26, the reversed link was deposited by Retraction Watch, not the publisher.
- **11 are a different Elsevier pattern: a republished corrected copy.** The corrected article
  is published again under a new DOI, next to a corrigendum. The new copy carries `update-to`
  pointing at both the original and the corrigendum. Example: 10.1016/j.nedt.2025.106695
  updates the withdrawn original 10.1016/j.nedt.2025.106658 and the corrigendum
  10.1016/j.nedt.2025.106696. The corrigendum cites 106658 and has no `update-to` of its own.
  The original is not left without `updated-by`, so this is not the harm the audit was
  looking for. The title rule could not tell these apart. All 11 fall in the "not predating"
  group, which explains much of R2.
- **3 are title-rule misses.** An IWA "Expression of Concerns:" notice (the plural escaped the
  notice-title rule) points at an article retitled "Expression of Concern:". A SAGE "Revise and
  Republish Notice" points at a retraction notice. A French-language version points at the
  English erratum.

The confirmed rate is 26/40 = 65% (Wilson 95% interval 50-78%), so roughly 430-680 of the 876
flagged links are true reversals. 448 of the 876 are **mutual**: the notice also points at
the article. In those cases the correct link exists too, and the extra reversed link makes the
notice itself look corrected or retracted. 274 notices are shown as retracted only because an
original points at them.

## R1 and R5

- **R1 failed:** 876, not 1,500 or more. Reversed links are rarer than the 2,347 date flags in
  audit 1 suggested. Most of those flags were date artefacts.
- **R5 failed, and this is good news for users of OpenAlex.** All 199 originals in the
  reversed-retraction sample that OpenAlex knows are marked `is_retracted: true`, and so are
  all 200 notices. OpenAlex does not lose the retraction when the Crossref link is reversed.
  It over-flags the notice instead, the error that Hauschke & Nazarovets and Si, Salami &
  Schneider describe. The forward control sample: 195 of 197 notices and 198 of 198 targets are
  marked retracted.

## Who deposits reversed links

The largest depositors are Elsevier (member 78) with 329, Springer Nature (297) with 145,
Rockefeller UP (291) with 95, Wolters Kluwer (276) with 81, IWA (945) with 38, Taylor & Francis
(301) with 33, Wiley (311) with 30, AIP (317) with 29 and SAGE (179) with 17. The sample
suggests that most of Elsevier's 329 are the republished-copy pattern rather than true
reversals. The top prefixes are 10.1016 (309), 10.1038 (126), 10.4103 (77) and 10.2166 (38). By
decade: 81 in the 1990s, 163 in the 2000s, 268 in the 2010s and 356 in the 2020s. 401 of the
originals have 10+ citations and 172 have 100+.

Retractive self-relations (a notice pointing at itself) number 31,843. This agrees with the
Tesseract Semantics finding that about a quarter of retractive assertions are self-referential.

## Lessons

- Titles alone cannot separate a reversed link from a republished corrected copy. A next
  version would need the target's own `update-to` and its citation of the original.
- The plural "Expression of Concerns" and "Revise and Republish Notice" should be in the
  notice-title rule.

## Data

[results/audit2/](results/audit2/): `summary.json`, `member_table.csv`, `reversed_part01.csv`
(all 876 reversed relations), `reversed_top300_by_citations.csv`, `reversed_other_sample200.csv`,
the OpenAlex samples and the graded sample.
