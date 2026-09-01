---
title: NO favorites at 0.90-0.97 across the whole screen (cell A without the mention-family restriction)
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-57
author_lane: theory
author_focus: no_side_premium
author_context: Found while extending the paired within-day series to its n_days>=8 bar; the pooled claim came back null but the band split showed the mention restriction is what starves cell A.
status: open
---
The 8-day within-day measurement of no_side_premium's population
(studies/2026-08-29-side-asymmetry-extension/, "Pass 2", 2026-09-01)
says the signal such as it is lives in a PRICE BAND, and that
no_side_premium's cell A cannot test it because its family restriction
starves the population.

WHAT WAS MEASURED. Day-clustered over 8 complete close-days, 868 settled
favorites drawn from theories.insider_bias.screen at pinned defaults:

  NO 0.90-0.97, whole screen : n=275  days=8  +1.70 +/- 1.99  7/8 days +
  NO 0.90-0.97, mention only : n=15   days=2  +3.72 +/- 1.42  2/2 days +
  every other side x band cell: |t| < 0.75, SE 3.7 to 11.5

The wide band is 18x the population at a comparable point estimate, and
it is the tightest cell on the board by a factor of two. It is also the
cell BOTH fullcov backtests measured (+2.25 net on the mention
population, backtest-2026-08-25-mention-fullcov) and the mechanism idea
14's revisit angle named, so it is pre-registered structure rather than
something the mining pass invented.

THE THESIS. NO favorites at 0.90-0.97 across the whole insider_bias
screen population are underpriced by roughly +2 pts net. Same optimism-tax
mechanism as no_side_premium (retail flow buys YES; nobody's hope pushes
into NO), with the mention-family restriction dropped.

WHY IT NEEDS ITS OWN THEORY RATHER THAN A CELL-A WIDENING. Cell A is
pre-registered as mention-family NO favorites at ask >= 0.85, with kill
bars at n>=150. Widening it now -- after seeing that the narrow cell is
thin and the wide one looks better -- is exactly the move the
pre-registration exists to prevent. Per CLAUDE.md a subset needing its
own population and entry rule is a SIBLING theory, not a slice. This is
the same split by which no_side_premium itself came off mention_family:
start at n=0, CITE the measurements above as founding evidence, never
inherit them as a track record.

WHY IT IS WORTH A SESSION. It is the only cell in this repo's non-insider
population where effect size, sign and day-to-day stability all agree
with a prior fixed before the data -- and, uniquely, it is REACHABLE:
between-day SD 5.64 pts means 62 settlement days to detect +2.0 at 80%
power, against 477 days for the paired statistic no_side_premium is
currently read on. Roughly two months of accrual, or an afternoon of
tier-A replay over settled history, which is fetchable for this
population.

WHAT TO PRE-REGISTER BEFORE COLLECTING ANYTHING. (1) the band, closed at
both ends, and whether 0.97 stays the cap (it is insider_bias.screen's);
(2) single-side NO net edge as the statistic -- NOT paired: pass 2
measured that differencing against YES imports variance rather than
cancelling it, because the two sides are different markets on different
subjects; (3) n_days >= 8 as well as a row bar, per the 2026-08-27 day
amendment, which applies here for the same reason; (4) a decision on the
sports-heavy population, which inflates every level (a favorite priced
hours before a game in progress is near-settled).

CHECK FIRST: idea 25 favorite-day-effect asks a neighbouring question
(are near-term screened favorites underpriced at all, day-clustered) over
the same population, and notes its own overlap with idea 2
calibration-harvest. Establish whether either subsumes this before
building. The distinguishing claim here is SIDE x BAND, not favorites in
general.

---

## Addendum, same session: two more things that MUST be pre-registered

Found in the robustness pass after the ticket was first written
(`studies/2026-08-29-side-asymmetry-extension/STUDY.md`, "Robustness").

**(5) A minimum rows-per-day for a day to count, fixed before collecting.**
The cell's per-day row count runs **6 to 71** across the 8 days, so the
weighting choice moves it a long way:

    row-pooled (n=275)              +3.32
    day-equal weighted              +1.70   SE 1.99   t=0.85   <- the honest one
    days with >= 10 rows (7 days)   +3.59   SE 0.73   t=4.93

The third line is **not evidence** and must not be carried into this
theory as motivation: the >=10 floor drops exactly one day, the only
negative one, and the only reason to reach for that floor is having
already seen which day it was. Same failure as the calibration_harvest
gradient review of 2026-08-29. Pick a floor on power grounds before any
collection, state it, and never revisit it after seeing a number.

**(6) The cell's single negative day is one loss on six markets.** Per-day
net runs +1.00 to +5.80 on seven days and -11.53 on 2026-08-26, which had
n=6 and 5 wins. So "7/8 days positive" and "not weighting-robust" are the
same fact seen twice. Do not treat the 7/8 sign test (p=0.070) as
independent corroboration of the +1.70 mean; it is the same eight numbers.

**Founding evidence to cite (never to inherit):** day-equal +1.70 +/- 1.99
over 8 close-days, n=275; the +2.25 net fullcov measurement on the mention
subset (`backtest-2026-08-25-mention-fullcov`); idea 14's revisit angle.
Start at n=0.

---

## Addendum 2, same session: a MANDATORY control this thesis has never had

`studies/2026-09-01-side-split-60day-obs/` split a 61-close-day,
72,010-observation out-of-population dataset by side. The pooled gap in
this exact band replicated hard — **+3.95 pts, t=3.03, 41/61 days**,
identical out-of-sample (+3.94 on 51 clean days), stronger in the on-time
stratum (+8.62), larger at an independent 24h decision point (+11.02),
monotone in price.

**All of it was composition.** NO favorites outnumber YES 5:2 there and the
two sides are largely different series. Differencing within (series, close
day):

    all series, pooled by day              +3.95   t +3.03
    both-sides series only                 +1.92
    WITHIN SERIES, WITHIN DAY              -1.85   t -1.40    29/61 days+
    series-equal / pair-equal              -1.04 / -1.68
    leave-one-series-out range             -2.58 .. -1.23

**(7) So the within-series within-day control is REQUIRED before this
theory is pre-registered, not after.** The +1.70 that motivates it was
measured over the insider_bias screen pooled across series and has never
had this control applied. That population is narrower than the sweep's, so
the artifact may well be smaller — but "may well be" is what the control
exists to replace. If the +1.70 is composition too, this theory should not
be built, and that is a cheap thing to find out first:
`studies/2026-08-29-side-asymmetry-extension/data/close-*.json` carry
`ticker`, so the series is derivable and the control is a short script.

**UPDATE, same session: the control WAS run on the screen population, and
it does NOT reverse there.** Within (series, close day), band 0.90-0.97:
+7.69 (SE 4.38, t +1.75, 5/7 days) at >=1 row/side, +11.44 (t +2.03) at
>=3 -- but on 30 and **5** series respectively over 6-7 days, which is far
too thin to read as a magnitude. "The control does not kill it here" is
the entire claim.

So the sweep and the screen disagree about the same question, and the
obvious candidate reason is testable: `insider_bias.screen` filters on
`spread <= 0.07` and `volume >= 500`; the board-wide sweep filters on
neither, which is why every level in it runs -3.7 to -40. The sweep's gap
may be composition among quotes nobody would fill, while the screen's is
not.

**THE DECIDING EXPERIMENT IS SOMEONE ELSE'S JOB FINISHING.** When
`2026-09-01-series-bias-backfill-liquidity` completes,
`spread`/`open_interest` exist across all 659 series (today: 59, reached in
collection order, which is why the current liquidity control is unusable).
Then filter the sweep to the screen's own liquidity bar and re-run the
composition control -- `studies/2026-09-01-side-split-60day-obs/measure.py`
section 7 already does it, it just needs the columns. That one run decides:

  * composition everywhere, screen result is small-sample noise
    -> DO NOT BUILD this theory; record the negative against idea 33.
  * gap survives within series once quotes are fillable
    -> the screen result is real, on 61 days instead of 8 -> build it.

Do not pre-register anything until that is known. The cost of waiting is a
few hours of a job that is already running.
