# crossref-update-direction-audit

Do Crossref's correction and retraction links point the right way?

Crossref records an erratum, correction or retraction as a link on the **notice**: the
notice's record says `update-to: <the work it corrects>`, and Crossref then shows the work as
`updated-by` the notice. Tools that flag corrected or retracted papers read these links.

## Audit 1 (graded): notices dated before their targets

Audit 1 read all 488,114 Crossref records that carry `update-to` and flagged the 2,347 links
where the "notice" is dated more than a month **before** its target. The gate passed and 2 of
7 predictions held. In a hand-graded sample of 40 flags, only 12 were sure relation errors
(19 at most), and half were date artefacts, such as print-issue dates later than the online
date. The sure errors were mostly **reversed** links: the original paper carries `update-to`
pointing at its own erratum or retraction notice. These came from many publishers, not mainly
from Springer Nature as predicted. Examples include *Nature* 2002 "Altruistic punishment in
humans" (10.1038/415137a), and a *Lancet* COVID-19 paper whose retracted record points at its
own "Retraction and republication" notice.

- [PREREG.md](PREREG.md): the pre-registration of audit 1.
- [GRADING-1.md](GRADING-1.md): the grading, including the failed predictions.
- [results/audit1/](results/audit1/): summary, publisher table, the top 200 flags by citations,
  the graded sample, self relations, and all 2,347 flags.
- `update_direction_audit.py`, `test_update_direction_audit.py`: the audit 1 code and tests.

## Audit 2 (pre-registered, running): reversed links found from titles

Audit 2 finds reversed links without dates. A link is reversed when the record that carries
`update-to` has an ordinary title (or a "RETRACTED:" title, which marks the retracted article
itself), while its target is titled as a notice ("Erratum: ...", "Correction to: ...",
"Retraction notice"). It also counts how many retraction notices Crossref shows as retracted
because of reversed links, and checks OpenAlex for a sample.

- [PREREG-2.md](PREREG-2.md): definitions, what was seen first, prior work and five
  predictions, written before the audit ran.
- `reversed_relation_audit.py`: the audit (Python standard library only; reads api.crossref.org
  and api.openalex.org, no keys). `python reversed_relation_audit.py --out-dir out`
- `test_reversed_relation_audit.py`: unit tests (`python -m unittest -v`).

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has reviewed this work. Code Apache-2.0; text and data CC BY 4.0.
