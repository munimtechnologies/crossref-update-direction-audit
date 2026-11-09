# Pre-registration, audit 6: do other indexes catch the retractions Crossref's metadata hides?

By MV2, Munim, Inc. (mv2@munimtech.com). Written 2026-11-09, before any of the lookups below
were run on this set. Made with AI agents working in MV2's name; no human has reviewed it.
Text CC BY 4.0, code Apache-2.0.

## Question

Audit 4b ([NOTE-4b.md](results/audit4b/NOTE-4b.md), post-hoc) found **294 notices** from 24
publishers that are titled as retractions or withdrawals but were deposited in Crossref with a
non-retractive update type (`correction`, `erratum`, `addendum`, ...). On 2026-11-09 the papers
they point at had no retractive update from any source in Crossref, Retraction Watch's relations
included. A reference checker that reads Crossref sees those papers as merely corrected.

Do the other places such tools read catch them? For every paper, audit 6 asks four sources:

| | Source | "Flagged" means |
|---|---|---|
| cr | Crossref REST API, read live | any `updated-by` entry of a retractive type, from any source |
| rw | Retraction Watch CSV (Crossref's GitLab copy, read directly, not through Crossref relations) | a row with this OriginalPaperDOI and RetractionNature "Retraction" |
| oa | OpenAlex | `is_retracted` true |
| pm | PubMed, looked up by DOI | publication type "Retracted Publication" or a "Retraction in" link |

The output is the first open list of retracted or withdrawn papers that **none** of these four
flags. A paper's "own title is marked" when it contains *retracted*, *retraction* or *withdrawn*.

## Population

The input is `results/audit4b/notices_hidden.csv` at commit `f1f5aef` (294 rows). The papers
are every target of each notice other than the notice itself; when a notice points only at
itself, the notice record is the paper. Four notices are excluded in advance because their
titles are topics, not notices (found when grading 4b): the Cochrane reviews
`10.1002/14651858.cd012540.pub2`, `.cd012572.pub2` and `.cd012572.pub3` ("Withdrawal of ...") and
the CUP erratum `10.1017/apj.2026.10053` ("Withdrawal and Belonging"). **A** is the set of
papers that Crossref still does not flag when the job runs.

## Gates (if any fails, the audit is reported as inconclusive)

- G1: the input has exactly 294 rows. G2: at least 280 papers.
- G3: at least 95% of papers resolve in Crossref. G4: at least 80% of those carry `updated-by`
  (each paper is the target of its own mistyped notice, so this checks that the field is read).
- G5: the Retraction Watch CSV has at least 50,000 rows.
- G6: at least 70% of A are found in OpenAlex. G7: PubMed lookups fail for at most 5%.

## Predictions

Each has a threshold that is fixed now. How blind each one is: the only papers from this set
already looked up outside Crossref are the ones named under "Already seen".

- **P1.** At least 90% of papers are still unflagged in live Crossref (publishers and
  Retraction Watch rarely fix these within days).
- **P2.** Fewer than 20% of A are listed as retracted in the Retraction Watch CSV. (Crossref
  imports that CSV as relations, so it should mostly agree with Crossref. This tests lag and
  DOI mismatches.)
- **P3.** Of A found in OpenAlex, at least 40% have `is_retracted` false.
- **P4.** OpenAlex's flag rate is at least 30 points higher for papers whose own title is
  marked than for papers whose title is not. Inconclusive if either group has fewer than 10.
  (All three OpenAlex flags seen so far were on retitled papers.)
- **P5.** Fewer than 40% of A are in PubMed by DOI (most of the set is engineering and
  chemistry).
- **P6.** Of A found in PubMed, at least 30% carry neither flag. Inconclusive below 10 papers.
- **P7.** At least 60 papers are missed by all four sources while being held by both Crossref
  and OpenAlex.
- **P8.** At least 10 of those missed-by-all papers have 20 or more OpenAlex citations.
- **P9 (hand-graded).** Of 20 missed-by-all papers drawn by hash (`grade20.csv`), at least 15 are
  real retractions or withdrawals of research papers (not topic titles, retired standards or
  duplicate-record clean-ups), judged by reading the notice's title and metadata.

P1 to P8 are graded by `grade()` in `index_miss_audit.py`, exactly as worded, with the numbers
written to `summary.json`. P9 is graded by hand and reported in GRADING-6.md with every grade.

## Already seen (disclosed)

- *Clin J Sport Med* 10.1097/00042752-200107000-00004 (McCrory 2001): unflagged in Crossref,
  OpenAlex (193 citations) and PubMed (PMID 11495318) on 2026-11-09. It is expected among the
  missed-by-all papers.
- OpenAlex flags 10.1016/j.compbiomed.2012.06.008, 10.1192/bjo.2024.752 and
  10.1111/j.1471-0528.1994.tb13145.x, all retitled.
- The 16 IWA Publishing papers ([findings/iwa-withdrawn-as-addendum.md](findings/iwa-withdrawn-as-addendum.md))
  were checked only against Crossref's own relations.
- No other paper in the set has been looked up in OpenAlex, PubMed or the Retraction Watch CSV.

## Prior work, searched 2026-11-09

- Ortega & Delgado-Quirós (Scientometrics 2024, 10.1007/s11192-024-05034-y) compare how seven
  databases index retracted literature. They searched each database for what it labels as
  retracted, as a retraction notice or as withdrawn, so a retraction no database labels cannot
  appear in their counts.
- fabio-rovai/scholarly-record-ontology (2026) measures disagreement between Retraction Watch,
  Crossref, OpenAlex and Europe PMC. It is seeded from those same registers.
- Hauschke & Nazarovets (arXiv:2403.13339) and Si, Salami & Schneider (2026) study OpenAlex and
  Crossref flagging notices or corrections as retracted, which is the opposite error.

The delta: these papers are found from the publisher's own notice title, so the set is exactly
the one that register-seeded comparisons cannot see. We found no list of retracted papers that
Crossref, Retraction Watch, OpenAlex and PubMed all fail to flag.

## Limits stated in advance

- A notice title is evidence of a retraction, not proof. P9 checks a sample.
- PubMed is matched by DOI only, so a paper indexed without its DOI counts as not in PubMed.
- The Retraction Watch CSV is matched by OriginalPaperDOI only.
- This is one reading on one day; publishers and indexes fix records.
- Timing: this file and the code are committed before job `index-miss-a6-v1` runs. GRADING-6
  will compare the commit time with the job's start time.

## Files

`index_miss_audit.py` (with 11 offline tests in `test_index_miss_audit.py`). The job writes
`papers.csv`, `missed_by_all.csv`, `grade20.csv` and `summary.json`, to be published under
`results/audit6/`.
