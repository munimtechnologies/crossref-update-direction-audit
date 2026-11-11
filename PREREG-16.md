# Pre-registration 16: does Retraction Watch list the Cochrane reviews withdrawn since Cochrane's 2019 policy change?

Written 2026-11-11 (UTC) by MV2, Munim, Inc. (mv2@munimtech.com), before the audit job ran and
before any of its output existed. The job waits until this file is live on GitHub before it
downloads any data, and records the time it saw it (`plan_live_at`, `data_started`). Made with AI
agents working in MV2's name; no human has reviewed it. Code:
[cochrane_withdrawal_rw_audit.py](cochrane_withdrawal_rw_audit.py) (Apache-2.0), tests:
[test_cochrane_withdrawal_rw_audit.py](test_cochrane_withdrawal_rw_audit.py). Text CC BY 4.0.

## Why

For years the Cochrane Database of Systematic Reviews (CDSR) "withdrew" reviews simply because
they were out of date. Retraction Watch (RW) counted many of these as retractions. In mid-2019
Cochrane changed its policy. Its editorial policy now says reviews "should be withdrawn only under
exceptional circumstances": serious error, scientific misconduct or a serious breach of its
conflict-of-interest policy, in line with COPE's retraction guidelines. It also says that
"questions related to the usage and currency of the review" are not such circumstances. Under that
policy, a withdrawal since mid-2019 is the CDSR's equivalent of a retraction. Reference managers
and checkers that rely on RW (directly or through Crossref) would then miss it if RW does not list
it.

## Nearest prior work and the delta

- Retraction Watch, 2015-10-07 ("Cochrane withdraws review on zinc for colds") and 2025-01-23
  (the ME/CFS exercise review). These give RW's count of "over 500" Cochrane reviews and versions
  retracted or withdrawn since 2009, and a Cochrane spokesperson's account of the July 2019 policy
  change. They give no year-by-year coverage.
- RW Database User Guide, Appendix D: the reason code "Withdrawn (out of date)" was added on
  2021-06-29. So RW does catalogue withdrawals made for currency.
- Research Square preprint rs-45086 (characteristics of retracted systematic reviews): most
  Cochrane withdrawals were for updating, and MEDLINE often did not tag them as retractions. Its
  data predate the policy change.
- A 2025 study of 50 years of medical retractions (PMC12669648) counts 571 CDSR entries in RW.
- Cochrane, "Withdrawing articles published in the CDSR" (documentation.cochrane.org): the current
  criteria. A Cochrane page dated 2019-10-15 gives 19 August 2019 as the date the policy changed.
- Searched 2026-11-11. We found no measure of RW's coverage of Cochrane withdrawals by year, and
  no check of what reasons the post-2019 withdrawal notices actually give.
- Delta: the first year-by-year count of CDSR withdrawals in Crossref against RW's own CSV, and a
  reason-by-reason reading of every review withdrawn since the policy change.

## Population and method

- Crossref: every CDSR notice (ISSN 1465-1858) with an `update-to` of type `withdrawal` or
  `retraction` (cursor walk, rows=1000). Publisher-deposited links give one event per withdrawn
  item (the target DOI), dated by the earliest notice's update date. Self-links are dropped.
  Links Crossref marks `source: retraction-watch` are kept only as the flag `crossref_rw`.
- Kinds: `review` = a CDSR version DOI ending `.pubN`, and `bare` = the bare CD number (usually
  the protocol; for some 1990s reviews, the first review version).
- Periods: `post` = on or after 2019-07-01 (we also report how many fall before 2019-08-19), and
  `pre` = 2009-01-01 to 2019-06-30.
- RW: the CSV from gitlab.com/crossref/retraction-watch-data (the api.labs.crossref.org copy as
  fallback). Its Cochrane rows are those whose OriginalPaperDOI has the CDSR prefix or whose
  Journal names Cochrane. Rows whose RetractionNature is a correction, expression of concern or
  reinstatement are ignored. `rw_exact`: RW lists the target DOI. `rw_near` (looser): RW lists
  the target DOI, or any version with the same CD number dated within 365 days of the notice.
- Europe PMC (REST search by notice DOI), for each `post` `review` event: the publication types
  (is "Retraction of Publication" among them?) and the abstract sentence that says the review was
  withdrawn, plus the next two sentences. A keyword rule classes the reason as `integrity`
  (error, misconduct, conflict of interest, breach, retracted data, unreliable), `currency` (out
  of date, superseded, split, not updated, new studies) or `other`. When both match, integrity
  wins.
- Outputs: summary.json (a year-by-kind table with counts n, rw_exact, rw_near and crossref_rw),
  events.csv (every event), and post_policy_reviews.csv (every post-policy review withdrawal).

## What we read before writing this (disclosed)

- Crossref: the CDSR has 1,312 notices with a `withdrawal` update (by year: 151-190 a year in
  2015-2018, 104 in 2019, 77 in 2020, 138 in 2021, 4 in 2022, none since). 273 CDSR notices carry
  a `retraction` update. These are dated 2009-2020 and appear to come from RW.
- We listed all 219 withdrawal notices dated 2020 or later. 200 point at a bare CD number and 19
  at a review version. Of those 219, only one has an RW link in Crossref (CD011313.pub3,
  yttrium-90 radioembolisation, RW record 25814).
- We read the Europe PMC records for 12 of the 19 review withdrawals. Reasons:
  - Integrity-type (5): data-extraction and reporting errors (CD013326); a serious
    conflict-of-interest breach (CD012271); a commercial-sponsorship breach (CD011823); methodological
    problems (CD011313); and "out of date and included a retracted article" (CD008359).
  - Currency-type (7): out of date or not updated (CD009325, CD009046, CD001024, CD005160),
    new studies with the update overdue (CD007705), superseded (CD004986), and split into two
    reviews (CD004060).
  - 7 of the 12 carry the publication type "Retraction of Publication" in Europe PMC. Two notices
    published on the same day (2021-11-30) give the same out-of-date reason (CD009325, CD009046),
    yet only one carries that type.
- Crossref's RW links come from RW's data, but we have **not** read RW's CSV for any of these.
- **So P1, P5 and P6 are informed. P2 and P3 are informed by Crossref's copy of RW's links but
  blind to RW's own CSV. P4 is blind.**

## Gates (if a gate fails, P1-P6 are reported descriptively, not graded)

- G1: both Crossref walks complete (at least 98% of total-results), with at least 1,300 withdrawal
  notices.
- G2: the RW CSV has at least 60,000 rows and the expected columns.
- G3 (instrument check): `rw_exact` is true for 10.1002/14651858.cd011313.pub3 and
  10.1002/14651858.cd006581.pub2 (Crossref already shows RW links for both).
- G4: this file was live on GitHub before data were downloaded.
- G5: at most 10% of Europe PMC lookups fail.

## Predictions

- P1 (informed): 15-40 CDSR review versions were withdrawn on or after 2019-07-01.
- P2 (blind to the RW CSV): RW lists the exact DOI for at most 20% of them.
- P3 (blind to the RW CSV, second definition): `rw_near` is true for at most 30% of them.
- P4 (blind): RW lists the exact DOI for at least 40% of review versions withdrawn in 2009 to
  June 2019.
- P5 (informed): RW lists (`rw_near`) at most 5% of post-policy withdrawals of bare CD numbers
  (protocols).
- P6 (informed): among post-policy review notices found in Europe PMC, at least 3 give an
  integrity reason and at least 3 give a currency reason.
- P7 (hand grading, next step): we will read every post-policy review notice's reason by hand.
  P7 holds if the keyword class agrees with the hand class for at least 85% of them. For every
  one RW does not list, we will check RW's CSV again by title.
- P8 (descriptive): the share of post-policy review notices that carry the "Retraction of
  Publication" type.

Grading will report every prediction as held, failed or not graded, with the numbers, including
failures. Anything found afterwards will be labelled post hoc. If P2 holds and P7 confirms the
list, the reviews that RW does not list will be sent to Retraction Watch as a factual list of
candidate entries, and the policy-versus-practice finding (currency withdrawals after the
policy change) will be written up. Neither is a claim that any review or author did anything
wrong.
