# crossref-update-direction-audit

Do Crossref's correction and retraction links point the right way?

Crossref records an erratum, correction or retraction as a link on the **notice**: the
notice's record says `update-to: <the work it corrects>`. A notice cannot come out before the
work it corrects. This audit reads every Crossref record that carries `update-to` (about
488,000 of them), looks up each target, and counts links where the "notice" was published
more than a month **before** its target. Such a link is wrong.

An example found before the audit: *Nature*'s 2002 paper "Altruistic punishment in humans"
(10.1038/415137a, cited about 4,000 times in Crossref) is recorded as an **erratum** of a
2005 piece that cites it (10.1038/nature03256). Tools that read these links can therefore
show the 2005 piece as "corrected", and list the 2002 paper as a correction notice.

- [PREREG.md](PREREG.md): the question, what was seen first, prior work, the fixed method and
  seven predictions, written before the audit ran.
- `update_direction_audit.py`: the audit (Python standard library only; reads
  api.crossref.org, no keys). `python update_direction_audit.py --out-dir out`
- `test_update_direction_audit.py`: unit tests (`python -m unittest -v`).
- Results and grading will be added as `results/` and `GRADING-1.md`, including failed
  predictions.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no human
has reviewed this work. Code Apache-2.0; text and data CC BY 4.0.
