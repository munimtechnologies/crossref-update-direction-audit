# Audit 4b: retraction and withdrawal notices that leave their papers unflagged in Crossref

**Post-hoc, NOT pre-registered.** This note corrects the "hidden" count in
[GRADING-4.md](../../GRADING-4.md). By MV2, Munim, Inc. (mv2@munimtech.com), 2026-11-09. Made
with AI agents working in MV2's name; no human has reviewed it. Text and data CC BY 4.0, code
Apache-2.0.

## What was run

`notice_audit.py` (job `crossref-notice-level4b-v1`, 2026-11-09 05:10-05:17 UTC) walked every
Crossref record that carries `update-to`: 488,130 records and 573,403 relations, all that the
API reported. It used the same title rules as audit 4. A **mistyped** relation is one where a
publisher deposited a notice titled as a retraction or withdrawal with a non-retractive update
type (`erratum`, `correction`, `addendum`, `new_version` and so on). Audit 4 judged each pair
(notice, paper) separately. Hand grading then showed that a notice record can carry a second,
correct relation (usually from Retraction Watch) that retracts the real paper. So 4b judges
each **notice** as a whole:

- **hidden**: no retractive relation from any source (publisher or Retraction Watch) targets any
  of the notice's papers, and the notice record carries no retractive relation either;
- **partly hidden**: some of its papers are flagged elsewhere and some are not;
- **covered on notice**: the notice record itself carries a retractive relation;
- **visible**: every paper is flagged as retracted by some other relation.

The consistency gate held: 350 hidden pairs, the same as audit 4.

## Result

| | Notices |
|---|---|
| Notices with at least one mistyped relation | 8,424 |
| visible (the retraction is recorded anyway) | 8,093 |
| covered on notice (audit 4's self-loop correction) | 37 |
| **hidden** | **288** |
| **partly hidden** | **6** |

**294 notices from 24 publishers** leave at least one paper with no retraction or withdrawal
update anywhere in Crossref, including Retraction Watch's relations. Largest: Elsevier 153,
SAGE 46, Wiley 19, IWA Publishing 19, Wolters Kluwer 11, Peertechz 6, BMJ 5, and 4 each from
Springer Nature, IOP Publishing, ASCE and Heighten Science. For 194 of the 294, the paper's own
title already says RETRACTED or WITHDRAWN. The title says it, but the metadata that tools read
does not.

The count grows with time: 41 hidden notices created in 2024, 64 in 2025 and 90 so far in 2026
(to 9 November). As a share, it is flat: 215 of 5,528 notices created since 2023 (3.9%) vs 48 of
1,472 created before 2020 (3.3%). Audit 4's failed prediction P6 (newer notices hidden more often)
used relations, not notices; at notice level the difference is small and not tested.

## Hand grading of 20 hidden notices

The 20 notices in `grade_notices20.csv` were drawn by hash and exclude audit 4's 30. Grades are
in [grade_notices20_graded.csv](grade_notices20_graded.csv). Six were re-read live through
api.crossref.org on 2026-11-09; the other 14 were graded from their titles and the census's
own relation check.

- **18 of 20 are real retraction or withdrawal notices** whose papers carry no retractive update:
  12 retractions (four are retracted Elsevier corrigenda), 4 withdrawals, and 2 SAGE
  "Administrative Duplicate Publication" withdrawals of duplicate records.
- **1 ambiguous**: Wiley's *EPPO Bulletin* notice withdrawing a 1990 EPPO standard from use. A
  standard was retired; no research was retracted.
- **1 false positive of the title rule**: the Cochrane review "Withdrawal of antihypertensive
  drugs in older people" (10.1002/14651858.cd012572.pub2), linked to its earlier version as
  `new_version`. The review is about stopping drugs; it is not a notice.

18/20 = 90% (Wilson 95% interval 70-97%), which suggests about **265 (205-286)** of the 294 are
real. Counting only retracted or withdrawn research papers (dropping the duplicates and the
standard), 16/20 = 80% (58-92%), about 235 (172-270).

### The title rule's false positives, and a fix

The grep of all 294 titles finds four clear topic titles: the three Cochrane reviews titled
"Withdrawal of ..." (`cd012540.pub2`, `cd012572.pub2`, `cd012572.pub3`) and the Cambridge
University Press erratum "Withdrawal and Belonging: ... – ERRATUM" (10.1017/apj.2026.10053).
The same rule is used in MV2's agent skill `retraction-crosscheck`. Version 0.1.0 would have
called that Cochrane review **retracted**, because the review's own title starts "Withdrawal of".
Version 0.1.1 fixes the rule. "Retraction of ..." or "Withdrawal of ..." now counts only when a
quoted title or a word for a publication follows within four words. "Retraction and ..." or
"Withdrawal and ..." counts only before words such as republication, replacement or correction.
The new tests cover each case above. This census was not re-run with the new rule.

## A clear example: a 2023 retraction that every index misses

*Clinical Journal of Sport Medicine* published a notice titled "Does Second Impact Syndrome
Exist? [RETRACTED]" (10.1097/jsm.0000000000001119, July 2023, p. e111). Its only Crossref link
to Paul McCrory's 2001 paper of that name (10.1097/00042752-200107000-00004) is typed
`correction`. Read on 2026-11-09:

- Crossref: the 2001 paper's only `updated-by` entry is that notice, typed `correction`. Neither
  the publisher nor Retraction Watch has a retraction relation.
- OpenAlex: `is_retracted` false, 193 citations.
- PubMed (PMID 11495318): types it "Journal Article; Review", with no "Retraction in" link.
  PubMed does index the 2023 notice (PMID 36989494), but types it "Journal Article", not
  "Retraction of Publication", and does not link the two records.

So a reference checker that reads Crossref, OpenAlex or PubMed shows this paper as not
retracted. We read only the notice's title and metadata (the record has no abstract), not its
text.

Other sources sometimes catch what Crossref misses. OpenAlex marks three graded or quoted
targets as retracted: 10.1016/j.compbiomed.2012.06.008, 10.1192/bjo.2024.752 and
10.1111/j.1471-0528.1994.tb13145.x. All three are retitled "RETRACTED" or "Retraction:". So
"hidden" here means hidden in Crossref's update metadata, not hidden from every index.

## The other side: retractive types on correction-titled notices

The census found 55 overflags (a retractive type on a notice titled as a correction), 22 of them
with no Retraction Watch support, the same as audit 4. Those 22 were graded in
[findings/corrections-deposited-as-retractions.md](../../findings/corrections-deposited-as-retractions.md).
A census-wide PubMed test of this direction (audit 5, [PREREG-5.md](../../PREREG-5.md)) is
queued.

## Prior work, searched 2026-11-09

The nearest work is unchanged: Tesseract Semantics' retraction-register analysis (August 2026)
counts invalid type strings and disagreement between registers. Crossref forum threads report
retracted articles with no update at all. Studies of OpenAlex measure notices wrongly flagged as
retracted. We found no count of retraction notices that publishers deposit under
non-retractive types, judged at the notice level against every source in Crossref.

## Limits

- Post-hoc; the definitions were fixed after audit 4's grading, before this job ran.
- The title rules are English-only and miss untitled notices ("Statement", "Notice").
- "Hidden" is judged on Crossref's metadata on 2026-11-09 05:10 UTC; publishers fix deposits.
- 14 of the 20 grades rely on titles plus the census's relation check, not a fresh read.

## Files

`summary.json`, `notices_hidden.csv` (294 rows), `notices_covered_on_notice.csv`,
`overflag_unsupported.csv`, `grade_notices20.csv` (as drawn) and `grade_notices20_graded.csv` are in this folder. The code is
[notice_audit.py](../../notice_audit.py) at the repository root; its 7 tests in
`test_notice_audit.py` passed in the job.
