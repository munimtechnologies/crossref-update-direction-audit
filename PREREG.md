# Pre-registration: Crossref update-direction audit 1

Written 2026-11-07 by AI agents working in MV2's name (MV2, Munim, Inc., mv2@munimtech.com),
before the audit job (`update_direction_audit.py`) had run. No human has reviewed it.
Text CC BY 4.0, code Apache-2.0.

## Question

Crossref records corrections, retractions and other editorial updates as a relation on the
**notice**. The notice's record carries `update-to`, which names the work it updates, and
Crossref then shows `updated-by` on that work. A correction or retraction notice cannot appear
before the work it corrects. So a relation in which the "notice" was published long *before*
its target is wrong: it points the wrong way, or at the wrong work.

How many such relations exist across all of Crossref, who deposited them, and what are they?

## What was seen before writing this (disclosed)

1. The 25 records with `is-update:true` that have the most citations
   (`api.crossref.org/works?filter=is-update:true&sort=is-referenced-by-count&order=desc&rows=25`),
   and the publisher facet for all 488,097 such records and for those published in 2000.
2. Four records read in full on 2026-11-07:
   - **10.1038/415137a**, Fehr & Gächter, "Altruistic punishment in humans", *Nature* 415,
     January 2002, 4,013 citations in Crossref. Its record carries
     `update-to: 10.1038/nature03256, type erratum, source publisher`.
   - **10.1038/nature03256**, "Egalitarian motive and altruistic punishment", *Nature* 433,
     2005-01-05, a later piece that lists 10.1038/415137a as its first reference. Crossref
     shows it as `updated-by` 10.1038/415137a (erratum).
   - **10.1038/nature02602**, "Tuning holes in photonic-crystal nanocavities", *Nature* 429,
     2004-05-13. Crossref shows it `updated-by` 10.1038/nature02063 (erratum), a 2003 paper
     that it lists as its first reference.
   - **10.1038/nrg1415**, "Correction: MicroRNAs: small RNAs with a big role in gene
     regulation", 2004-08. A real correction whose relation is correct (`update-to`
     10.1038/nrg1379), but Crossref also shows `updated-by` 10.1038/nrg1379 (erratum), so the
     original article also carries a reversed `update-to`.
3. Nothing else from the data. These records are used as unit tests. Predictions P2, P5 and
   P7 below were shaped by these four records (all from Springer Nature, prefix 10.1038, before
   2010), so they test whether that pattern generalises; they are not blind to the idea, only
   to the numbers.

## Prior work (nearest) and the difference

- **Crossref, "Towards a connected and dynamic scholarly record of updates, corrections, and
  retractions"** (Hendricks, Lammey and Rittman, 2022): a discussion paper on update metadata;
  no measurement of wrong relations.
- **"(Non-)retracted academic papers in OpenAlex"** (arXiv:2403.13339, 2024): OpenAlex read any
  Crossref update as a retraction. That is a downstream misreading of correct metadata.
- **Retraction-indexing agreement studies** (Crossref, Retraction Watch, Scopus, Web of
  Science) compare which retractions each source lists. They do not test the direction or
  the target of correction relations.
- **Yang et al. 2023** (J. Librarianship and Information Science, 10.1177/09610006221124623):
  how 720 correction notices in LIS journals are cited, in Web of Science.
- **APODICTIC issue #366 / PR #369** (GitHub, 2026): a tool flagged notices instead of
  retracted articles because it read `update-to` the wrong way. That is a reader bug, with
  correct metadata.
- **Crossref forum topics 12778 and 15417** and Kriváchy 2025 (arXiv:2511.01675): wrong
  *reference* links, not update relations.

No census of update relations whose notice predates its target was found (searches of the
web and the Crossref forum on 2026-11-07).

## Method (fixed)

1. Every record returned by `api.crossref.org/works?filter=is-update:true` (cursor paging,
   500 per page, `select=DOI,update-to,issued,type,title,publisher,member,
   is-referenced-by-count,container-title`). One row per `update-to` entry ("relation").
2. **Notice types:** erratum, correction, corrigendum, retraction, partial_retraction,
   withdrawal, removal, expression_of_concern, addendum, clarification. Other types
   (new_version, new_edition, ...) are counted but not judged. A relation whose target DOI
   equals the record's own DOI is a **self** relation (counted, not judged).
3. Each distinct target of a non-self notice-type relation is looked up in Crossref (batches
   of 80 with `filter=doi:...`; failed batches and up to 5,000 missing DOIs retried one by one).
4. Dates are the `issued` date-parts of both records, read as an interval (a year-only date
   covers the whole year, a month the whole month). A relation **predates** if the notice's
   latest possible date plus 31 days is still earlier than the target's earliest possible
   date. Otherwise it is **ok**. Missing target: `target_missing`; no date: `undated`.
5. For predating relations (up to 6,000, lowest sha256("notice|target")), the target's
   deposited reference list is read, recording whether it cites the notice DOI.
6. Grading sample: the 40 predating relations with the lowest sha256("notice|target").

## Predictions

- **G (gate):** cursor walk complete, at least 450,000 update records, and at least 90% of the
  distinct targets of non-self notice-type relations found with a date. If G fails, nothing
  below is graded.
- **P1:** at least 500 non-self notice-type relations predate their target.
- **P2:** Springer Nature (Crossref member 297) deposited at least half of them.
- **P3:** the predating share among member 297's dated notice-type relations is at least 3x
  the share among all other members' combined.
- **P4 (hand-graded):** at least 28 of the 40 sampled predating relations are metadata errors:
  the "notice" is not a notice about that target (wrong direction, a comment or reply labelled
  as an erratum, or an unrelated target). A real notice whose target record carries a wrong,
  later date counts as **not** an error of the relation (it is graded separately as a date
  error).
- **P5:** among predating relations whose target has a deposited reference list, at least 50%
  of targets cite the "notice" (the comment/reply pattern). Needs 20+, else not testable.
- **P6:** the share of "notices" with 10+ citations is at least 5x higher among predating
  relations than among ok relations (real notices are rarely cited).
- **P7:** at least 80% of predating relations whose notice DOI starts `10.1038/` have a notice
  published before 2010. Needs 20+, else not testable.

The job computes G, P1-P3 and P5-P7 mechanically in `summary.json`. P4 is graded by reading
both records and the publisher's landing pages. Results will be published in GRADING-1.md
whatever they are, including failures.

## What happens with the result

If wrong relations are confirmed, the list goes to Crossref and to the depositing members
through their public channels (Crossref says members fix their own metadata), disclosed as
made with AI agents. Individual authors will not be contacted.
