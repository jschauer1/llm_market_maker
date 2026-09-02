---
title: Mid-band favorites (0.50-0.80) stay net-negative with a tradeable book -- the half of the series-bias negativity that is real
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-b3
author_lane: new-theory
author_focus: no-favorite-high-band
author_context: Found while running the deciding experiment that killed idea 33 (no-favorite-high-band); the liquidity filter that dissolved the high-band effect left the mid-band one standing. Measured on 37% backfill coverage, NOT yet composition-controlled.
status: done
closed: 2026-09-01
resolution: Killed by its own item (1), run before release. The composition control PASSED -- buying the mid-band favorite really does lose -3.90 (t=-3.30), LOO negative in 171/171 -- but the mirrored trade is not +3.90. Favorite ask and underdog ask sum to 1+spread, so fav_net + dog_net == -(spread + fees) exactly (-3.8989 + -1.0411 = -4.9400, verified to 1e-6). The underdog leg measures -1.04: BOTH SIDES LOSE. Mid-relative mispricing is only -1.45 (t=-1.23, not significant) against a 4.94 round-trip cost, so ~3/4 of the headline was toll rather than error. Idea 36 recorded dead. Generalizable lesson kept in the study and the registry: a one-sided net edge of -N does not imply +N on the other side, it implies -(round_trip - N).
---
MECHANISM AND MEASUREMENT. theories/no_side_premium/studies/answer/2026-09-01-liquidity-filtered-side-split/mechanism.py applied the series-bias study's own pre-registered tradeable-book filter (spread<=0.07 AND open_interest>=100 -- the correction in that study's STUDY.md, which makes open_interest load-bearing and spread explicitly not) to the WHOLE price range rather than just the 0.90-0.97 cell. The population splits cleanly in two, day-clustered over 61 close days:

  band        ALL rows          TRADEABLE only
  0.50-0.65   -4.90 t=-2.59     -4.21 t=-1.65  n=1285   <- SURVIVES
  0.65-0.80   -3.30 t=-3.65     -3.65 t=-2.57  n=1324   <- SURVIVES
  0.80-0.90   -3.58 t=-3.59     +1.73 t=+1.10  n= 939   <- dissolves
  0.90-0.97   -4.50 t=-4.50     +0.44 t=+0.45  n=1079   <- dissolves
  0.97-0.98   -6.76 t=-3.84     -1.66 t=-0.80  n= 271   <- dissolves
  0.98-1.01  -14.03 t=-7.37     +0.45 t=+1.32  n= 793   <- dissolves

Above 0.80 the famous negativity is entirely an empty-book artifact. Below 0.80 it is not: it survives the filter essentially unchanged, on markets with a real book, at t=-2.57 in the 0.65-0.80 band. That asymmetry is the finding.

THE CANDIDATE TRADE is the mirror -- buy the UNDERDOG at roughly 0.20-0.50. Classic favorite-longshot bias predicts this sign, which is a point in its favour (pre-existing mechanism, not a mined pattern) and also a warning (it is the most-published effect in this literature and the most likely to be already arbitraged where it is tradeable).

WHY IT IS WORTH A SESSION. It is measured on the liquidity-filtered population rather than on quotes nobody could fill, which is what killed every previous version of this claim in this repo. n=1,324 in the strongest band over 61 close days. And it is tier A, mechanical, edge_basis='model' -- a ticker-and-arithmetic screen with no model in the decision path, so it replays over all reachable history and re-runs free.

WHAT MUST BE PRE-REGISTERED BEFORE BUILDING -- four things, and (4) is the one that killed the last thesis:

  1. THE MIRRORED TRADE IS NOT SIMPLY +3.65. The favorite's net edge is (win rate - ask) - fee. The underdog leg pays its own fee on its own price; you cannot negate the number. Recompute from the underdog side directly.
  2. The sweep is SIZE-TRUNCATED toward lower-frequency series (collect.py's eligible_series walks ascending by settled count), so the high-frequency tail is unmeasured and the theory must not claim it.
  3. Coverage when this was measured was 37% and ALPHABETICAL (A-E complete, F partial, ~nothing after). Whole families are absent -- 72 series under L, 58 under U, 50 under S. RE-MEASURE ON THE COMPLETED BACKFILL FIRST.
  4. THE WITHIN-SERIES WITHIN-DAY COMPOSITION CONTROL HAS NOT BEEN RUN ON THIS BAND, and it is mandatory. It is exactly what dissolved idea 33: that thesis had a pooled +3.95 (t=3.03) and a within-series control of -1.85, and out of sample -5.44 (t=-2.13). A pooled level over a population whose series mix varies is not an effect. theories/no_side_premium/studies/answer/2026-09-01-liquidity-filtered-side-split/measure.py::control does this and can be pointed at the mid band directly -- it is a short change, and it is the FIRST thing to run, not the last.

Also check for subsumption before building: idea 25 favorite-day-effect and idea 2 calibration-harvest both look at favorite pricing over overlapping populations, and calibration_harvest's whole thesis is signed calibration cells by (domain x horizon x price). If this is just calibration_harvest's price axis measured on a different population, it belongs there as evidence rather than here as a theory.

Registered as idea 36 (mid-band-favorite-fade). Source: own measurement, 2026-09-01.

---

## UPDATE, same session: item (4)'s control WAS run, and this passes where idea 33 failed

Filed above as "mandatory, and the FIRST thing to run". Rather than hand
over a ticket that might die in ten minutes the way idea 33 did, it was
run before release. **It passes.** Same data (37% coverage), same
tradeable-book filter.

An important distinction first, because it changes which control applies.
Idea 33 was a **side-gap** claim (NO beats YES), so its control was
NO-minus-YES differenced within (series, close day). This is a **level**
claim (buying the mid-band favorite loses), and the matching composition
control is whether the level is driven by *which series are present*:
series-equal weighting and leave-one-series-out, on top of the
day-clustering `day_stat` already applies.

```
band 0.50-0.80, tradeable, n=2,609 over 171 series, 61 close days
  POOLED day-clustered      -3.90   t=-3.30   18/61 days positive
  SERIES-EQUAL (>=5 rows)   -2.51   median -1.38   61/112 series negative
  LEAVE-ONE-SERIES-OUT      -4.64 .. -3.01   NEGATIVE IN 171/171

band 0.50-0.65   pooled -4.21 (t=-1.65)   series-equal -1.39   LOO neg 151/151
band 0.65-0.80   pooled -3.65 (t=-2.57)   series-equal -2.47   LOO neg 150/150
```

**This is the exact opposite of idea 33's signature.** There, pooled and
series-equal disagreed in sign (−1.02 vs +9.11) and the positive side was
carried by 23 series contributing one noisy pair each. Here pooled,
series-equal and median all agree in sign, in both sub-bands, and **every
one of 171 leave-one-out estimates is negative**. No single series, and
no weighting choice, is producing it.

Sports concentration, since the parent ticket for idea 33 flagged
sports-heavy populations as a level-inflating risk:

```
sport lines (GAME)   n=1160   -2.90  (t=-1.65)   60 days
non-sport ("other")  n= 667   -3.30  (t=-1.14)   61 days
```

Present in both at similar size, so it is not a sports artifact.

**What this does and does not license.** It removes the composition
objection that killed idea 33; it does **not** make the thesis bettable.
Still outstanding, and (1)–(3) of the parent list are untouched:

- **The mirrored trade has still not been priced from the underdog side.**
  This measures that buying the favorite loses ~3.9 pts net. It does NOT
  measure that buying the underdog wins 3.9 — the underdog leg pays its
  own fee on its own price. **Do this first**; it is arithmetic, it needs
  no new data, and it is what decides whether there is a trade at all.
- Coverage is still 37% and alphabetical (A–E complete). Re-measure on
  the completed backfill.
- The out-of-sample split (before/after 2026-08-20) has not been run on
  this band.
- Favorite-longshot bias is the most-published effect in this literature.
  A real edge that survives a liquidity filter on a US exchange in 2026
  deserves the question "who is on the other side, and why do they keep
  being wrong" answered before anything is built.

Scripts: `theories/no_side_premium/studies/answer/2026-09-01-liquidity-filtered-side-split/measure.py`
(filter, `day_stat`, `control`) and `mechanism.py` (the band table). The
control above was ad hoc against those helpers and is reproducible from
them; it is not yet checked in as its own file.

---

## CLOSED, same session: both sides lose. Do not spend a session on this.

Item (1) of the parent list — "the mirrored trade is not simply +3.65,
recompute from the underdog side directly" — was run before release,
because it is arithmetic over data already on disk. **It kills the
thesis.**

The composition control passed, so the −3.90 is real: buying the mid-band
favorite genuinely loses, and it is not composition. But the mirror is
not +3.90, because the favorite's ask and the underdog's ask sum to
**1 + spread**, not 1 — taking either side crosses the book:

```
underdog_ask = 1 - favorite_ask + spread

  =>  fav_net + dog_net  ==  -(spread + fee_fav + fee_dog)
  measured: -3.8989 + -1.0411 = -4.9400  vs round trip 4.9400  (1e-6)
```

```
favorite ask   BUY FAVORITE      naive mirror     BUY UNDERDOG
0.50-0.65      -4.21 (t=-1.65)      +4.21           -1.08 (t=-0.42)
0.65-0.80      -3.65 (t=-2.57)      +3.65           -1.01 (t=-0.70)
0.50-0.80      -3.90 (t=-3.30)      +3.90           -1.04 (t=-0.88)
```

And separating the market's error from the toll for acting on it —
`mid = ask − spread/2`, gross of fees — shows there was not much error to
begin with: **the mid-relative mispricing in 0.50–0.80 is −1.45, t=−1.23,
not significant**, against a round-trip cost of 4.94. About
three-quarters of the headline was never mispricing.

**Idea 36 recorded `dead`.** Nothing here changes with more data: the
round-trip cost is structural and the residual was insignificant before
any multiple-comparison penalty.

**What to take from it instead** — the trap is repo-wide and worth more
than the thesis was:

> A one-sided net edge of **−N** does not imply **+N** on the other side.
> It implies the other side sits at **−(round_trip − N)**. Both sides
> lose whenever the mispricing is smaller than the round trip, which on
> this population is 2.2–5.3 points depending on price.

Every theory that reports a signed cell edge is one step from making it —
the step from "do not buy this" to "so buy the other one".

Full working: `theories/no_side_premium/studies/answer/2026-09-01-liquidity-filtered-side-split/STUDY.md`,
"Addendum, same session".
