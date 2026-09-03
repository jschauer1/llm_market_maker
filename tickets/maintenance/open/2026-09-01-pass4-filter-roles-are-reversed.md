---
title: Pass 4's filter has its two conditions backwards: spread is load-bearing, open_interest is not
lane: maintenance
study: 2026-08-29-series-bias-mining
created: 2026-09-01
created_by: fleet-w1-g2
author_lane: study
author_focus: 2026-09-01-liquidity-filtered-side-split
author_context: Found while running the completion re-run of the liquidity-filtered-side-split study at 100% backfill coverage; mechanism.py re-run reversed this study's own pre-registered premise.
status: open
---
READ THIS BEFORE RUNNING PASS 4. This study's STUDY.md section 'Correction to pass 4's filter, made before pass 4 runs' fixes the test on open_interest -- 'a level, and therefore meaningful at a point in time the way a per-period volume is not' -- with spread <= 0.07 kept as 'a second, independent, explicitly NOT load-bearing condition'. The reasoning given was: 'a one-cent quote on a market nobody holds is still a quote.'

That reasoning is intuitive and it is empirically FALSE on this corpus.

EVIDENCE, at 99.95% backfill coverage (72,010 obs / 659 series / 61 close days), reproduce with:
    python theories/no_side_premium/studies/answer/2026-09-01-liquidity-filtered-side-split/mechanism.py <copy.db>

Band 0.90-0.97, net edge in points, day-clustered:
    spread<=0.07 AND oi==0      n=3930   net=-1.46  t=-1.24
    spread<=0.07 AND oi>=100    n=3054   net=-1.14  t=-1.64
A 0.3-point gap. Rows with a tight spread and NOBODY HOLDING THEM price about as well as held ones.

And the open-interest ladder inside the band is not monotone in any direction:
    oi 0-1        n=3974  net=-1.44
    oi 1-100      n=1943  net=+0.16
    oi 100-500    n=1045  net=-1.23
    oi 500-2000   n= 939  net=-3.15
    oi >=2000     n=1070  net=-1.81

Meanwhile the unfiltered-to-filtered improvement in that band is -7.64 -> -1.14, i.e. 6.5 points. Essentially all of it is the SPREAD condition and almost none is open interest.

WHY THE CORRECTION GOT IT BACKWARDS. It was written against the same 37% alphabetical backfill prefix that misled run 1 of the liquidity study. On that prefix the oi==0 vs oi>=100 gap measured 2.9 points (-2.47 vs +0.44) and open_interest genuinely looked load-bearing. At 2.7x the series it is 0.3 points. The prefix is disproportionately soccer and combat-sport totals, which are exactly the families whose books are thin and whose spreads are wide.

WHAT TO DO -- and the point is NOT to retune anything:
 (1) Pass 4 may run with the filter exactly as pre-registered. It is still a defensible tradeable-quote filter and nothing here says it selects the wrong rows. What must change is how its RESULT is read and reported: do not attribute the filter's effect to open interest, and do not repeat the '55% of the NO side is quoted into an empty book' explanation, which explains nothing at full coverage.
 (2) Append a dated note to the 'Correction to pass 4's filter' section pointing at this ticket and at theories/no_side_premium/studies/answer/2026-09-01-liquidity-filtered-side-split/STUDY.md 'Correction 2'. Do NOT edit the correction's original text -- it was a pre-registration and the repo's pattern is to supersede, not rewrite.
 (3) If a future pass wants to change the filter, that is a new pre-registration on a stated collection state, not an edit to this one. A larger family is a harsher Holm divisor and two runs over two collection states are two different tests; this study's own one-run rule already says so.

WIDER CAUTION worth carrying out of this: an alphabetical prefix of Kalshi's series list is NOT a random sample of the board -- it is a sample of a few sports families. Three separate conclusions in this repo were drawn on the 37% prefix and two of them reversed at completion. Any measurement taken while a series-ordered collection is partway through should either wait or state the prefix bias as a first-order caveat, not a footnote.

---

## Lane change, 2026-09-02 — this was a `mention_family` theory ticket

`mention_family` was retired by the user on 2026-08-27 and migrated to
`theories/retired/mention_family/` on 2026-09-02. This ticket lived in
that theory's own `tickets/open/` folder until then, which is why its
`author_lane` and history read the way they do.

It is a **maintenance** ticket now, and it has no owning theory. The
study it concerns did not retire with the theory: it was still in
`investigation`, other studies read its corpus, and it is now ownerless
at

    tickets/study/investigation/2026-08-29-series-bias-mining/

Every path in the body above has been repointed to that home. Nothing
about the work asked for here changed with the move.
