# retraction-crosscheck changelog

Made with AI agents working in MV2's (Munim, Inc.) name. Apache-2.0.

## 0.1.1 (2026-11-09)

- Fixed: titles that only name a topic were read as retraction or withdrawal notices. "Withdrawal
  of antihypertensive drugs in older people" (a Cochrane review, 10.1002/14651858.cd012572) was
  called **retracted** by 0.1.0, because its own title starts "Withdrawal of". Now "Retraction
  of ..." or "Withdrawal of ..." counts only when a quoted title or a word for a publication
  (article, paper, publication, abstract, manuscript, chapter, letter, notice) follows within
  four words. "Retraction and ..." or "Withdrawal and ..." counts only before republication,
  replacement, correction, apology, notice or erratum. Found while hand-grading audit 4b
  ([results/audit4b/NOTE-4b.md](../../results/audit4b/NOTE-4b.md)).
- New: when a paper comes out `possibly_withdrawn` and OpenAlex does not mark it retracted, the
  output says so.
- Tests: topic titles, real notice titles (quoted, "Retraction and republication",
  "[RETRACTED]"), the Cochrane review, and the *Clin J Sport Med* notice titled "[RETRACTED]" but
  deposited as a `correction` (10.1097/00042752-200107000-00004 comes out `possibly_withdrawn`).

## 0.1.0 (2026-11-09)

First release: Crossref, Retraction Watch-in-Crossref, PubMed, notice titles, OpenAlex and a
graded-errors table. Evaluation plan: [eval/EVAL-1-PLAN.md](../../eval/EVAL-1-PLAN.md); the
evaluation job runs 0.1.0.

MV2, Munim, Inc., mv2@munimtech.com
