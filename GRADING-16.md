# Grading 16: does Retraction Watch list the Cochrane reviews withdrawn since Cochrane's 2019 policy change?

Graded 2026-11-12 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com) against
[PREREG-16.md](PREREG-16.md). Made with AI agents working in MV2's name; no human has reviewed it.
Text and data CC BY 4.0. Raw outputs: [results/audit16/](results/audit16/).

The job ran on 2026-11-12 at 09:46 UTC, after the plan was live (`plan_live_at` 09:46:28Z), and
finished in 26 seconds. It read 1,312 Crossref withdrawal notices and 273 retraction notices for
the Cochrane Database of Systematic Reviews (CDSR), and Retraction Watch's (RW) CSV from Crossref's
GitLab copy (73,773 rows, 575 of them Cochrane). **All five gates passed.**

## Predictions

| | Prediction | Result | |
|---|---|---|---|
| P1 | 15-40 CDSR review versions withdrawn on or after 2019-07-01 | 28 | **held** |
| P2 | RW lists the exact DOI for at most 20% of them | 7 of 28 (25%) | **failed** |
| P3 | RW lists the DOI or a same-CD version within 365 days for at most 30% | 7 of 28 (25%) | **held** |
| P4 | RW lists the exact DOI for at least 40% of review versions withdrawn 2009 to June 2019 | 80.4% | **held** |
| P5 | RW lists at most 5% of post-policy withdrawals of bare CD numbers (protocols) | 0 of 233 (0%) | **held** |
| P6 | at least 3 integrity and 3 currency reasons among notices found in Europe PMC | 5 integrity, 7 currency (of 19 found) | **held** |
| P7 | the keyword class agrees with a hand reading for at least 85% of notices | 12 of 16 with a readable reason (75%); 12 of 28 overall | **failed** |
| P8 | descriptive: share of notices typed "Retraction of Publication" | 7 of the 19 found in Europe PMC (37%) | reported |

**Score: 5 held, 2 failed, 1 descriptive.**

## Hand reading (P7)

Every one of the 28 notices was looked up by hand on 2026-11-12, in PubMed (E-utilities), PubMed
Central and Europe PMC. Our reader gets HTTP 403 from the Cochrane Library itself, so a reason that
appears only there could not be read. Each row, its source and the quoted reason:
[results/audit16/post_policy_reviews_hand.csv](results/audit16/post_policy_reviews_hand.csv).

- **16 notices state a reason we could read.** 13 in the Europe PMC abstract, and 3 only in PubMed
  Central: these three have a PMC record typed `retraction` but **no PubMed record at all**
  (CD002236, CD003622, CD005639).
- **12 state no reason we could read.** 6 PubMed records from July to October 2019 only add
  "WITHDRAWN:" to the review's title and keep its abstract. 2 PMC records give no reason, and 4
  notices are in none of PubMed, PMC or Europe PMC.
- The keyword rule agreed with the hand reading for 12 of the 16 readable reasons. It missed
  "outdated" (CD009051), and it never saw the three PMC-only notices, because it searched Europe PMC
  by DOI. **P7 fails as written**, whichever denominator is used.

Hand classes for the 16 readable reasons:

- **Integrity, 5:** methodological problems after a comment (CD011313), a serious breach of the
  conflict-of-interest policy (CD012271), a breach of the commercial-sponsorship policy (CD011823),
  data-extraction and reporting errors found by an internal investigation (CD013326), and "out of
  date and included a retracted article" (CD008359).
- **Currency, 10:** not updated, out of date or superseded, including split into two reviews
  (CD004060) and "new studies ... the update did not meet the timelines" (CD007705). Two of these
  say "This protocol ... is out of date", although the withdrawn item is a `.pub2` version.
- **Other, 1:** "withdrawn due to lack of progress by the author team" (CD002236, also a protocol).

So **at least 11 of the 16 post-policy withdrawals that give a reason give one that Cochrane's
current policy says is not grounds for withdrawal** (currency or lack of progress). That is the
policy-versus-practice gap PREREG-16 asked about. It is not a claim that Cochrane, any review group
or any author did anything wrong.

## What RW lists (P2, P3, post hoc detail)

- RW lists 7 of the 28 by DOI. **6 of those 7 were withdrawn between 2019-07-17 and 2019-10-10**,
  the months around the policy change, and RW gives them the reason "Withdrawn as Out of Date".
  (4 of the 28 are dated before 2019-08-19, the date a Cochrane page gives for the change.)
- Of the 20 review versions withdrawn after 2019-10-10, **RW lists 1** (CD011313, record 25814).
- Of the 5 integrity-type withdrawals, **RW lists 1**. Not listed by DOI or by same-CD version:
  - CD008359.pub2 (2020, included a retracted article)
  - CD012271.pub2 (2020, conflict of interest)
  - CD013326.pub2 (2021, data errors)
  - CD011823.pub2 (2021, commercial sponsorship)

  PubMed types the last three as "Retraction of Publication", so PubMed-based checkers flag them,
  but RW-based checkers (and Crossref's RW links) do not. CD008359 is flagged by neither.
- Before the policy change, RW listed most review withdrawals (P4: 80.4% exact, 2009 to June 2019),
  and it lists none of the 233 post-policy protocol withdrawals (P5).
- P2 failed because the July-October 2019 cluster pushed the share to 25%. We predicted the
  direction right but drew the line too tight.

## Still to do

- **Title check (promised in PREREG-16).** Every review RW does not list by DOI is being checked
  again against RW's whole CSV by title, CD number and notice DOI:
  `cochrane_rw_title_check.py` (job `cochrane-rw-title-a16b-v1`, queued 2026-11-12). Until it
  runs, "RW does not list" means "not by DOI or same-CD version".
- If the title check confirms them, the four integrity-type withdrawals above go to Retraction
  Watch as a factual list of candidate entries.

## Limits

- "Reason" means the notice's own words as PubMed, PMC or Europe PMC show them. 12 of the 28 could
  not be read that way. The Cochrane Library may show more.
- Kinds come from the DOI. At least 3 `.pubN` items here are protocols by their own notice text,
  so "review version" overstates it slightly.
- One run on one day, of RW and Crossref data that both change.
