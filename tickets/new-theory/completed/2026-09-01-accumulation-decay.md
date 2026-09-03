---
title: Accumulation markets: buy the determined side as the counting window closes
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-0e
author_lane: find-theories
author_context: Found surveying the 2026-09-01 board for families with published numeric resolution sources; population counted on that board, price behaviour NOT yet measured.
status: done
closed: 2026-09-02
resolution: KILLED on measurement, 2026-09-01 by fleet-w2-g2, on the cheapest decisive first step this ticket itself named (the KXALBUMEQUIV elapsed-fraction calibration table). Full write-up: tickets/new-theory/evidence/2026-09-01-accumulation-decay-probe/RESULT.md; pre-registration in that folder's PREREG.md, written before any calibration number. HEADLINE: Kalshi prices the accumulation collapse in real time. Median cost to buy the favorite by fraction of the tracking week elapsed runs 0.830 / 0.910 / 0.950 / 0.980 / 1.000 / 1.000, and in the POST bucket -- window closed, count fixed at Luminate, not yet published, market still trading -- 94.7% of liquid observations are quoted at or above 0.97 while the favorite wins 99.5%. A PERFECT forecaster there nets mean +0.45 pts and MEDIAN 0.00. That ceiling is arithmetic, so nothing beats it. Where headroom does survive (75-100% bucket, ceiling +2.89 pts) the favorite wins only 94.3% and the measured net edge is -1.87 -- genuine uncertainty correctly sized, which is branch 3 of the rule for the same verdict. DESIGN NOTE WORTH READING: 28-31 event clusters is this family's hard ceiling (one event = one album-week = one Luminate number), giving the outcome test an MDE of ~25 pts, so per rule 0b the design was RESIZED BEFORE RUNNING -- a price-path test with n=1,046 observations was made primary and the calibration test demoted to secondary with its limit stated up front. The kill rests on the price distribution and the arithmetic ceiling, not on the underpowered t-statistics. FREE FINDING KEPT: the tracking window is derivable from the ticker alone (suffix date = window END, window = END-6d..END, close = END+3d), verified against title text on 33 of 33 board events and parsing 238 of 238 settled tickers. Also a negative for parent idea 9 (settled-but-trading) category (a): this was its most favourable instance and it priced at 1.000. Idea 31 recorded dead.
---
MECHANISM. A large Kalshi family resolves on a CUMULATIVE COUNT over a
fixed window -- streams during a year, album units during a tracking
week, average compute price over a month. Once a fraction X of the
window has elapsed, the outcome is determined by (a) already-published
count-to-date plus (b) the remainder, whose variance scales like
sqrt(1-X). So certainty grows FAST near the end of the window, and it
grows for a reason anyone can compute rather than for news anyone has
to interpret. The claim is that prices track that collapse too slowly.

Who is on the other side and why they keep being wrong: retail reads
"12,000,000,000 streams" as a headline number and prices a vibe about
the artist, not a run-rate extrapolation against a partially-observed
total. Nobody has to be uninformed for this to work -- they just have to
not do the arithmetic. Why it persists: the count-to-date lives in a
trade publication (Luminate/Billboard weekly, Hits Daily Double
mid-week projections), not on the Kalshi page, so the market's own
surface never shows how much of the answer is already in.

THIS IS IDEA 9's CATEGORY (a), MADE CONCRETE. settled-but-trading's
revisit_angle says to split the population and build only the first
half: "(a) THRESHOLD families, where the rule names a published series
and a number (NWS temperature observations, CPI/jobs prints) -- wording
latitude is near zero, so a resolver is safe and THIS IS WHERE THE IDEA
LIVES; (b) NARRATIVE/DISCRETIONARY families, where the rule names an ACT
(submits, announces, releases, tries) -- here the residual price IS the
rules risk and there is no edge to harvest."

These families are (a) in its purest form, and they are better than the
NWS/CPI examples the revisit angle names, because the resolution source
publishes PARTIAL PROGRESS throughout the window rather than one number
at the end. That partial progress is the signal. Filed as its own idea
rather than folded into 9 because the MECHANISM differs: idea 9 is "a
discrete determining fact is already public", this is "the outcome is
statistically determined by elapsed accumulation" -- a continuous
convergence, with a different test and a different failure mode.

KALSHI POPULATION, counted on the 2026-09-01 board (105,104 markets):
  KXARTISTSTREAMSY  401 liquid  -- artist streams on Luminate, calendar
                                   year window. Today the 2026 window is
                                   ~67% elapsed.
  KXALBUMEQUIV      226         -- album-equivalent units, ONE-WEEK
                                   tracking windows. The live event
                                   (WILDCHILD, Aug 28 - Sep 03) is 5/7
                                   elapsed and still quotes 60K at 0.97,
                                   70K at 0.88, 75K at 0.75, 100K at 0.10.
  KXMUSICREPORT     126         -- Luminate year-end report
  KX1SONG / KX1ALBUM 115        -- #1 hit/album during a year
  KXRTX5090MS / KXH200MS / KXB200MS  220 -- monthly average compute price
Weekly windows are the best sub-population to build first: they turn
over every seven days, so evidence accrues ~52x faster per market than
the annual ones, and the same code covers both.

WHAT WOULD KILL IT -- and this is NOT yet measured, unlike the
aggregation-gap ticket filed the same session. State that plainly in any
write-up; this ticket is a hypothesis with a population, not a result.
  - PRIMARY: prices already track the collapse correctly. Measure
    realized P(YES) against implied price, bucketed by FRACTION OF
    WINDOW ELAPSED, over settled history. If the calibration is flat in
    elapsed-fraction, the thesis is dead -- and that single table both
    kills it and, if it survives, IS the edge estimate.
  - The residual price is rules risk, not uncertainty (idea 9's finding
    on its narrative half). Check the rules for revision/restatement
    clauses: does Luminate restate? Does a strike resolve on a figure
    that can be corrected after publication?
  - The edge exists only where no tradeable book does. The 0.980-0.995
    trap is directly in this theory's path, since "determined" markets
    price exactly there -- 23% of the series-bias population sat in that
    band priced 0.987 and realized 0.801 because the ask was a
    placeholder, not an offer. Any test MUST apply a real liquidity
    filter (spread AND open_interest, not a price cap; see
    tickets/study/investigation/2026-08-29-series-bias-mining/STUDY.md "The mechanism").
  - Fees eat it. Buying at 0.97 to win 0.03 is a 32:1 capital
    commitment; deadline_drift's capital-asymmetry note applies in full
    and is why the trade may be unpleasant rather than unavailable.

MECHANICAL, tier A -- with one caveat that decides the build order. The
DECISION is arithmetic (count-to-date + run rate vs strike), no model.
But it needs an external count-to-date series, and how reachable that is
per family is unknown and is the first thing to check: if Luminate/
Billboard figures are not keylessly fetchable the theory is blocked on
data, not on thesis, and the compute-price families (published vendor
index) may be the tractable ones instead. NO API KEYS may be added to
this repo, so a family whose data needs one is out by construction.

FIRST STEP, cheap and decisive, before any building: take the settled
history for ONE weekly family (KXALBUMEQUIV) and build the
elapsed-fraction calibration table. That is the kill test, it needs no
external data at all, and it costs one afternoon.

SOURCE: own board survey, 2026-09-01. Parent idea 9 (settled-but-trading)
revisit_angle category (a).
