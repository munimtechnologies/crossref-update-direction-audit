# Corrections deposited as retractions: 17 papers shown as retracted that only got a correction

Checked by hand 2026-11-09 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents
working in MV2's name; no human has reviewed it. Text and data CC BY 4.0.

**Status: post-hoc follow-up, not pre-registered.** In audit 4 ([GRADING-4.md](../GRADING-4.md)),
P7 counted 55 "overflags": notices titled as a correction or erratum but deposited with update
type `retraction` or `withdrawal`. 22 of them had no Retraction Watch support and were left
ungraded. This file grades all 22 and adds two FASEB J cases found afterwards with one
exploratory query. Data: [corrections-deposited-as-retractions.csv](corrections-deposited-as-retractions.csv).

## Result

Of the 22 unsupported overflags (relations):

| Verdict | Relations | What it means |
|---|---|---|
| Corrected, not retracted | 14 | the publisher's own Crossref deposit says `retraction`, but the notice is a correction |
| Wrong target (off by one DOI) | 1 | a real retraction pointed at the neighbouring article |
| Typed `withdrawal`, target not withdrawn | 2 | Elsevier errata/corrigenda typed `withdrawal` |
| Self-loop "Erratum" marked as retracting itself | 3 (2 notices) | low harm: only the notice record is affected |
| Real retraction | 2 | the target is retitled "RETRACTED" (Global Health Action, Gynecological Surgery) |

Adding the two FASEB J papers found later (fj.08-114363 and fj.09-0601ufm, both corrected in a
"Retractions and Errata" column), **17 papers are shown as retracted in Crossref and in OpenAlex
although they received only a correction** (16 corrected and 1 off-by-one target). OpenAlex's
`is_retracted` is `true` for all 17 (read 2026-11-09). Together they have 893 OpenAlex
citations. The best-cited one is *Genetic requirements for Staphylococcus aureus abscess formation
and persistence in host tissues* (FASEB J 2009, 10.1096/fj.09-135467, 442 citations).

By publisher, 9 of the 17 are Wiley (6 *FASEB Journal* errata, plus *Int J Quantum Chem*,
*Int J Tourism Research* and *Theoria*). The others are Elsevier (2), Portland Press (2),
Korean Ophthalmological Society, Korean Society for Bone and Mineral Research, Taylor & Francis
and Springer (1 each).

## Evidence, strongest first

- **Notice text read (2):** *Korean J Ophthalmol* 10.3341/kjo.2022.0089.e1 fixes one grant number
  in the funding statement ("This article has been corrected."). *Biosci Rep*
  10.1042/bsr-20181233_cor fixes a duplicated image panel, and the authors state that this does not
  change the paper's conclusions. Both are deposited as `retraction`.
- **PubMed / Europe PMC (10, including the two above):** the target carries "Erratum in", the notice is typed "Published
  Erratum", and no target has the "Retracted Publication" type.
- **Retraction Watch contradicts the publisher (4):** for *Life Sciences*, both *Biosci Rep*
  papers and *Survival*, the Retraction Watch relation on the same notice is `correction`,
  while the publisher's relation is `retraction`.
- **Title only (5):** Wiley (3), Springer (1), and the FASEB book-review erratum. These have no
  retraction in Retraction Watch, no "RETRACTED" title and no PubMed record, and their notices
  are titled "Correction to ..." or "Erratum". We could not open the publishers' pages (HTTP
  403), so we have not read the notice text.
- **Off by one:** the *Fertility and Sterility* notice 10.1016/s0015-0282(16)58061-3 retracts
  Friedman and Hornstein 1993 (10.1016/s0015-0282(16)56090-7, Retraction Watch record 3505).
  Elsevier's deposit points at 10.1016/s0015-0282(16)56091-9, the next article in the issue
  (a clomiphene challenge-test study), which OpenAlex now shows as retracted.

A FASEB detail shows how one of these happened. Page 648 of FASEB J 24(2) holds both the
abscess paper's erratum (10.1096/fj.09-135467err) and an unrelated retraction notice
(10.1096/fj.09-142067, which PubMed says retracts itself, an online-first paper). The publisher
deposited the erratum as a `retraction` of the abscess paper, and the retraction notice as a
`retraction` of the erratum.

## Why this matters, and how it differs from earlier work

Hauschke and Nazarovets ("(Non-)retracted academic papers in OpenAlex", arXiv:2403.13339) showed
that OpenAlex flagged papers as retracted when Crossref's metadata was **correct**, because
OpenAlex collapsed every kind of update into one flag (22 Dec 2023 to 19 Mar 2024). Here the
error is upstream: **the publisher's own Crossref deposit says `retraction`.** Any tool that
reads update types correctly still inherits it. One public safeguard, trusting a retraction only
when Retraction Watch confirms it or the title says "RETRACTED" (emah-maker/lumen PR #335),
would have avoided all 17. The trade-off is that the same rule misses real retractions that
only the publisher records.

## Limits

- The 22 come from audit 4's title rule, which only catches notices whose title says
  "Correction", "Corrigendum" or "Erratum". Combined columns such as FASEB's "Retractions and
  Errata" escape it: that is how the two extra FASEB cases were found, by listing all 59
  FASEB-prefix `retraction` deposits. A full census needs a better rule and is not done.
- OpenAlex changes over time. The flags were read on 2026-11-09.
- The two `withdrawal` cases may be withdrawals of the corrigendum itself. The *Research in Autism
  Spectrum Disorders* corrigendum was deposited under *Research in Developmental Disabilities*,
  and another erratum followed. Either way, Crossref shows the original article as withdrawn.
- For five cases the notice text has not been read (see above).

## How to check one

```
https://api.crossref.org/works?filter=doi:10.3341/kjo.2022.0089&select=DOI,title,updated-by
https://api.openalex.org/works/doi:10.3341/kjo.2022.0089?select=doi,is_retracted
```
