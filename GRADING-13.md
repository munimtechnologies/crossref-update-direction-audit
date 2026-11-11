# Grading 13: does OpenAlex flag items that Crossref records only as withdrawn?

Graded 2026-11-11 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against
[PREREG-13.md](PREREG-13.md). Made with AI agents working in MV2's name. No human has reviewed it.
Text CC BY 4.0.

**Short version.** All 4 gates passed and P1-P6 held. OpenAlex's `is_retracted` is true for 99.9%
of sampled items that only a publisher `retraction` link touches, for 100% of withdrawn items that
Retraction Watch also lists, and for only 3.1% of items that only a publisher `withdrawal` link
touches. The flag gap is real. **But the hand check (P7) failed, and it changes what the gap
means.** Of 20 sampled unflagged items that were withdrawn in place, only 3 are clearly genuine
withdrawals. 12 are Elsevier "WITHDRAWN:" records whose article is live under a second DOI, in the
same journal or a sister journal (11 certain, 1 probable). 3 are NIST public drafts replaced by
a later version, and 2 are unresolved. Most of the time, leaving these items unflagged is the
right call. So we are **not** reporting a gap to OpenAlex. The useful lesson is about Crossref:
its `withdrawal` update type mixes real withdrawals with duplicate-DOI clean-ups and superseded
drafts, and a reader that treats every `withdrawal` link as a retraction will over-flag.

## Run

Job `withdrawal-flag-a13-v1`, 2026-11-11 13:52-14:00 UTC, exit 0, unit tests passed first. The
job saw PREREG-13.md live on GitHub at 13:52:06 and only then downloaded data. Crossref walk:
85,097 records (81,556 retraction, 3,420 withdrawal, 2 partial_retraction, 707 removal) with
85,602 retractive-link targets. OpenAlex was asked about 6,436 DOIs in 129 batches, with 0 failed
batches and 0 DOIs that could not be asked. Raw output: [results/audit13/](results/audit13/).

## Gates

| Gate | Rule | Value | Result |
|---|---|---|---|
| G1 | retraction and withdrawal walks complete | 81,556 / 3,420 | passed |
| G2 | 10.1016/j.cgh.2026.10.001 is w_only and self-linked; 10.1053/j.gastro.2024.07.040 is r_only; OpenAlex returns both | as stated (flags: false / true) | passed |
| G3 | OpenAlex batches failed <= 2% | 0 of 129 | passed |
| G4 | plan live before data | 13:52:06 | passed |

## Groups

| Group | Targets | Found in OpenAlex | `is_retracted` true |
|---|---|---|---|
| w_only (publisher `withdrawal` links only, no RW link) | 2,836 | 2,564 | 79 (3.1%) |
| of which w_self (withdrawn in place) | 1,204 | 1,177 | 55 (4.7%) |
| r_only sample (publisher `retraction` links only; 3,000 of 22,960) | 3,000 | 2,990 | 2,986 (99.9%) |
| w_rw (publisher `withdrawal` link plus an RW link) | 599 | 592 | 592 (100%) |

## Predictions

| | Prediction | Value | Result |
|---|---|---|---|
| P1 | 200-4,000 w_only targets | 2,836 | **held** |
| P2 | OpenAlex finds >= 90% of w_only | 90.4% | **held** (narrowly) |
| P3 (informed) | flag true for <= 20% of found w_self | 4.7% (55 / 1,177) | **held** |
| P4 (informed) | flag true for >= 90% of found r_only sample | 99.9% (2,986 / 2,990) | **held** |
| P5 | r_only share minus w_only share >= 50 points | 96.8 points | **held** |
| P6 (blind) | flag true for >= 80% of found w_rw | 100% (592 / 592) | **held** |
| P7 (hand) | >= 15 of 20 sampled unflagged w_self are genuinely withdrawn | 3 of 20 | **failed** |

P3 and P4 were informed by about 33 items read before the plan was written (disclosed in
PREREG-13). P6 was blind: a Retraction Watch record makes OpenAlex set the flag every time.

## P7: how the 20 were graded

The sample is the first 20 unflagged w_self targets found, in sha256("a13g"|DOI) order
([grade20_w_self_unflagged.csv](results/audit13/grade20_w_self_unflagged.csv)). The prediction
counts an item as genuinely withdrawn if its Crossref title is marked "WITHDRAWN" or its notice
says so. It excludes version changes and duplicate DOIs. For every title-marked item, we ran a
Crossref bibliographic search on the title (api.crossref.org/works?query.bibliographic=...) and
read the top four hits. We call an item a duplicate DOI when the same article, with the same or
nearly the same title, is live under another DOI in the same journal, a sister journal or the
same journal under its new publisher. Every DOI and reason is in
[hand_grade_p7.csv](results/audit13/hand_grade_p7.csv).

| Grade | Count | Examples |
|---|---|---|
| duplicate DOI (article live under another DOI) | 11 | 10.1016/j.matpr.2021.04.483 -> 10.1016/j.matpr.2021.04.451; 10.1016/j.rcrx.2020.100043 -> 10.1016/j.resconrec.2020.105117; 10.1016/j.gmg.2024.100016 -> 10.1055/s-0044-1788614 |
| duplicate DOI, probable | 1 | 10.1016/j.clindermatol.2020.04.013 (near-identical reply 10.1016/j.clindermatol.2020.04.012) |
| genuine withdrawal | 3 | 10.1016/j.jinf.2005.11.080 (no other version found); 10.1016/j.jinf.2005.11.039; 10.1016/j.jfds.2019.04.002 (earlier versions only as a preprint and a conference paper) |
| NIST public draft replaced by a later version | 3 | 10.6028/nist.cswp.39.2pd (Crossref `new_version` + `replaces` links), nist.sp.1303.ipd, nist.ir.8441.ipd |
| unresolved (title not marked, notice not read) | 2 | 10.1002/14651858.cd000132 (Cochrane), 10.35940/ijeat.c3984.0212323 |

The failure does not depend on the judgement calls. If both unresolved items and all three NIST
drafts counted as genuine, the total would be 8 of 20, still short of 15. The duplicates match
Elsevier's own withdrawal policy, which lists Articles in Press "discovered to be a duplicate of
another published article due to an editorial or production error" as a reason to withdraw
(https://www.elsevier.com/about/policies-and-standards/article-withdrawal). Its current wording
says an Article in Press "may only be withdrawn" for that reason or because it is "an early
version of an article that was published prematurely due to an editorial or production error".
Older withdrawals, such as the two 2006 Journal of Infection items, may predate that wording. We
did not predict how common duplicates would be.

## What it means (post hoc, labelled as such)

- In this sample, 12 of 20 (60%; Wilson 95% interval 39-78%) of the unflagged, withdrawn-in-place
  items are duplicate-DOI clean-ups, and only 3 of 20 (15%; 5-36%) are clearly genuine withdrawals.
  Scaled to the 1,122 unflagged w_self items OpenAlex returned, that is very roughly 60-400 genuine
  withdrawals without the flag. The range is wide because the sample is 20.
- OpenAlex's flag tracks Retraction Watch closely for withdrawals: 100% of w_rw items are flagged,
  and 3% of w_only items are. We did not test whether OpenAlex reads RW directly or only uses
  whatever links RW deposits in Crossref.
- For anyone building a retraction check on Crossref: a `withdrawal` link on an item's own record
  often means "this DOI was a duplicate; the article lives at another DOI", not "this work was
  withdrawn". A same-title search finds the live copy. The retraction-crosscheck skill in this
  repository does not know this yet. Reading the 0.2.0 code (a hand trace, not a test run) shows
  that a "WITHDRAWN:" title counts as independent evidence, so such a record gets the answer
  `retracted`, with no pointer to the live copy. Fixing that is planned, and the fix gets its own
  pre-registered test.
- Audit 15 ([PREREG-15.md](PREREG-15.md)) counts duplicate DOIs across all 1,204 items withdrawn in
  place, and checks whether either record links the other.
- Nothing is reported to OpenAlex. PREREG-13 planned a report only "if the gap holds", and on
  inspection most of the gap is correct behaviour.

## Limits

- The sample has 20 items, 15 of them from Elsevier, which dominates w_self (951 of the
  unflagged items). Other publishers' withdrawals may behave differently: Wiley's are mostly
  Cochrane reviews, and NIST's are drafts.
- A title search can miss a re-registered copy whose title changed a lot, so
  some of the 3 items graded "genuine" could still be duplicates.
- We read Crossref metadata, not the publishers' withdrawal notices (journal sites block our
  fetcher).
