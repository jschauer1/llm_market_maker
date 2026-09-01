# Does the NO-favorite side gap survive a tradeable book? — the deciding experiment for `no-favorite-high-band`

**Date:** 2026-09-01 · **Status:** pre-registration written before any
effect was computed · **Tier:** A (no model in the measurement path) ·
**Session:** `llm-market-identifier-b3`, new-theory lane, focus
`no-favorite-high-band`

## Why this study exists

Ticket `tickets/research/open/2026-09-01-no-favorite-high-band.md` ends by
naming one experiment as the thing that decides whether that theory is
built at all, and forbids pre-registering the theory until it has run:

> filter the sweep to the screen's own liquidity bar and re-run the
> composition control. That one run decides:
>   * composition everywhere, screen result is small-sample noise
>     -> DO NOT BUILD this theory; record the negative against idea 33.
>   * gap survives within series once quotes are fillable
>     -> the screen result is real, on 61 days instead of 8 -> build it.

The disagreement it resolves is between two measurements of the same
question:

| population | pooled NO−YES, band 0.90–0.97 | within (series, close day) |
|---|---|---|
| board-wide sweep, no liquidity filter (`2026-09-01-side-split-60day-obs`) | **+3.95** t=3.03, 41/61 days | **−1.85** t=−1.40 — all composition |
| `insider_bias.screen` population, liquidity-filtered | +1.70 ± 1.99 (8 days) | **+7.69** t=1.75 — but 30 series, 6–7 days |

The obvious candidate reason is testable and is the whole design here:
`insider_bias.screen` filters on `spread <= 0.07` and lifetime
`volume >= 500`; the board-wide sweep filters on neither. **If the sweep's
gap is composition among quotes nobody could fill, the screen's is not
contradicted by it.**

## What supersedes what

`studies/2026-09-01-side-split-60day-obs/measure.py` is left exactly as
run — its numbers are cited in the ticket and in the 2026-09-01 floor
report, and the repo's pattern is to supersede rather than edit in place.
Its section 7 runs the composition control on the *whole* cell; the
missing piece is running that control **inside** the liquidity filter,
which is what `measure.py` here adds.

## Pre-registration — fixed before any effect number was computed

The filter is not chosen here. It is the one
`studies/2026-08-29-series-bias-mining/STUDY.md` restated under
"Correction to pass 4's filter, made before pass 4 runs": the test is on
**`open_interest`** — a level, and therefore meaningful at a point in
time the way a per-period `volume` is not — with `spread <= 0.07` kept as
a second, independent, explicitly **not** load-bearing condition, and
per-period volume reported alongside rather than thresholded.

That correction left the threshold itself to be "set from the
population's own distribution *before* any per-series number is computed,
and the chosen value recorded here with the count of observations it
removes." This section is that record.

### The distribution the threshold was set from

Cell rows (`ask ∈ [0.90, 0.97)`) carrying backfilled columns at the time
of writing — **4,904 rows over 200 series**, backfill 227/659 series
complete:

```
open_interest   p0     p5    p10    p25    p50     p75      p90      p95       p99
                0.00   0.00   0.00   0.00   0.00  110.48  1201.15  3846.78  30949.21

spread          p0    p25    p50    p75    p90    p95    p99
              0.010  0.010  0.020  0.060  0.660  0.800  0.910
```

**More than half of this cell has zero open interest at the decision
point,** and the median spread is one cent. Those two facts together are
the whole reason the correction was made: a one-cent quote on a market
nobody holds is still a quote.

### The threshold

> **PRIMARY: `spread <= 0.07` AND `open_interest >= 100`.**

Chosen on two grounds, both visible in the distribution above and neither
requiring an outcome:

1. **It is where the book starts existing.** The mass below p75 is
   essentially zero (p50 = 0, p75 = 110), so 100 is the first round level
   that separates "somebody holds this" from "nobody does" rather than
   cutting into a continuum.
2. **It is the highest bar the deciding control can afford.** The control
   differences within (series, close day) and needs series carrying rows
   on *both* sides. Survivors by threshold, cell rows:

   | T | rows kept | % of cell | series | close days |
   |---|---|---|---|---|
   | spread only | 3,836 | 78.2% | 178 | 61 |
   | **100** | **1,079** | **22.0%** | **137** | **61** |
   | 250 | 864 | 17.6% | 123 | 59 |
   | 500 | 674 | 13.7% | 112 | 59 |
   | 1000 | 493 | 10.1% | 97 | 58 |
   | 2000 | 326 | 6.6% | 68 | 54 |
   | 5000 | 202 | 4.1% | 34 | 43 |

   Above 100 the series count — which *is* the control's sample size —
   falls away fast, and by T=5000 there are 34 series left and the
   control cannot be run at all.

**Removal count, as the correction requires: T=100 removes 3,825 of 4,904
cell rows (78.0%).** Of that removal, the great majority is the
zero-open-interest mass rather than the spread condition (spread alone
removes 1,068; the open-interest condition removes a further 2,757).

### Sensitivity ladder, also fixed in advance

T ∈ {250, 500, 1000, 2000} is reported alongside as robustness. **The
primary is the one that decides**; the ladder exists so that a result
that lives at exactly one threshold is visible as such. A ladder entry is
never promoted to the headline after the fact — that is the failure mode
the `>= 10 rows/day` floor in the parent ticket's addendum was filed
against.

### The control's minimum rows per side — fixed here, before any effect

The composition control pairs NO against YES **within (series, close
day)**, so it needs a minimum row count per side to form a pair. That
minimum is a real design knob: raising it buys cleaner pairs and spends
series, and the parent ticket's addendum (5) is an explicit warning about
picking such a floor *after* seeing which value helps.

> **PRIMARY: `>= 1` row per side per (series, close day).** Ladder:
> `>= 2`, `>= 3`.

`>= 1` is primary because after the liquidity filter the binding
constraint is series coverage, not within-pair noise: 1,079 rows spread
over 137 series and 61 days averages well under one row per side per
series-day, so any higher floor is spending the sample the control is
made of. The parent ticket's own screen-population control was read at
`>= 1` and `>= 3` for the same reason, and reported that the `>= 3`
version rested on **five series** — which is the failure this ordering
avoids.

### Statistic

Single-side NO net edge, day-clustered, per the parent ticket's item (2):
**not** paired against YES for the pooled headline, because pass 2 found
that differencing imports the YES side's variance rather than cancelling
a shared shock. The **composition control is necessarily paired** within
(series, close day) — that is what makes it a control — and is read as a
control, not as the effect estimate.

### The decision rule, fixed before the numbers

* Within-series within-day difference **positive and not explained away**
  under the primary filter → the screen result is real on 61 days instead
  of 8 → **build the theory** (`propose-theory`).
* Within-series within-day difference **≈ 0 or negative** under the
  primary filter → composition everywhere → **do not build**; record the
  negative against idea 33 and close the ticket.
* Filter leaves too few both-sided series to run the control at all →
  **not measured**; say so, and do not read the pooled number as a
  substitute.

## Caveat carried into the result

The backfill was 227/659 series complete when this was written and is
still running. Series are backfilled in **alphabetical order**, so the
covered subset is not a random sample of the board. The threshold above
is a filter definition rather than an estimate, so this biases it only
mildly — but every *effect* number is reported twice: once on the
coverage available when it was run, and again on completion. The source
study's one-run rule applies: **a number belongs to the collection state
that produced it.**

---

# RESULT — run 1, on 37% backfill coverage

`python studies/2026-09-01-liquidity-filtered-side-split/measure.py <copy.db>`
against collection state **26,941 backfilled rows over 227 series** (of
72,010 / 659), 61 close days. Per the pre-registered caveat this is
reported as a number belonging to *this* coverage, and re-run on
completion below.

## The verdict: DO NOT BUILD

Pre-registered primary statistic — NO minus YES **within (series, close
day)**, inside `spread <= 0.07 AND open_interest >= 100`:

```
within-series within-day  = -1.02 pts   t=-0.35   16/35 days +   40 series, 100 pairs
```

Not positive, so by the decision rule fixed before the numbers existed:
**composition here too → do not build; record the negative against idea 33.**

Three independent checks say the verdict is not an artifact:

**1. The open-interest ladder is monotone in the wrong direction.** The
harder the liquidity bar, the *more* negative the within-series gap:

| T | rows | series | pairs | WITHIN, day-clustered |
|---|---|---|---|---|
| 100 (primary) | 1,079 | 40 | 100 | **−1.02** (t=−0.35) |
| 250 | 864 | 36 | 71 | −1.66 (t=−0.54) |
| 500 | 674 | 30 | 57 | −1.90 (t=−0.57) |
| 1000 | 493 | 18 | 37 | −2.11 (t=−1.15) |
| 2000 | 326 | 13 | 29 | −2.81 (t=−1.29) |

A thesis that survives only where the book is thinnest is not a thesis.

**2. Out of sample it is significantly negative.** Split on the
2026-08-25 fullcov runs the cells were mined from:

```
close <  2026-08-20  (clean)     WITHIN = -5.44   t=-2.13   11/28 days +   30 series
close >= 2026-08-20  (overlaps)  WITHIN = +16.68  t=+2.29    5/7  days +   21 series
```

The window that suggested the cells is strongly positive; the window
clear of it is significantly negative. That is the in-sample shine the
split exists to expose, and it is the single most damaging line here —
the clean number is not merely null, it is negative with t=−2.13.

**3. No single series carries it.** Leave-one-series-out over all 137
series in the filtered cell: range **−2.34 .. +0.31**, and **134 of 137
LOO estimates are negative**.

## The one piece of counter-evidence, and why it does not survive

Series-equal weighting gives **+9.11** (t=1.93) where day-clustering
gives −1.02, and it stays positive in both coverage halves (+7.07,
+11.87). Taken at face value that is the result the theory wanted.

It is an artifact of weighting, and the decomposition is unambiguous:

```
series with exactly 1 pair   n=23   mean=+15.73   median=+0.94
series with >1 pair          n=17   mean= +0.16   median=-0.47
median over all 40 series           +0.46
```

**23 of the 40 series contribute a single (series, close day) pair** —
one NO market against one YES market on one day, which can only take
values near 0 or near ±100. The top six series-level values are
+100.9, +96.2, +94.4, +64.8 (all k=1), +49.5 (k=2), +31.9 (k=3). Series
equal-weighting up-weights precisely those cells. Restricted to series
that pair more than once, the effect is **+0.16, median −0.47** — i.e.
gone. Day-clustering is the pre-registered statistic and it is also the
one that is not dominated by 23 coin flips.

## Coverage caveat, stated honestly

Backfill order is alphabetical and coverage is a near-complete prefix
plus strays:

```
A 37/37  B 40/40  C 57/57  D 22/22  E 60/60  F 4/26  ...  Y 4/6   (rest ~0)
```

So the "alphabetical halves agree" check above (−1.09 vs −2.82) is really
*A–C vs C–E*, which is a weaker check than the phrasing suggests, and it
is reported that way. **Whole categories are absent** — 72 series under
L, 58 under U, 50 under S, 45 under N, 33 under T — and many of those are
sports-league families. The LOO check is the stronger evidence that the
verdict is not one series; the completion re-run below is what settles
the population question.

---

# The finding that outranks the verdict: the negativity was never about calibration

`mechanism.py` (post-hoc and descriptive, kept out of `measure.py` so the
pre-registration stays clean) asked what the filter does to the whole
price range, not just the cell. It changes the population's headline
conclusion:

```
band          ALL rows              TRADEABLE (spread<=0.07, oi>=100)
0.50-0.65     -4.90  t=-2.59        -4.21  t=-1.65   n=1285
0.65-0.80     -3.30  t=-3.65        -3.65  t=-2.57   n=1324
0.80-0.90     -3.58  t=-3.59        +1.73  t=+1.10   n= 939
0.90-0.97     -4.50  t=-4.50        +0.44  t=+0.45   n=1079
0.97-0.98     -6.76  t=-3.84        -1.66  t=-0.80   n= 271
0.98-1.01    -14.03  t=-7.37        +0.45  t=+1.32   n= 793
```

**The series-bias study's headline reading — "every level is deeply
negative" — is a statement about quotes nobody could fill, and only above
0.80.** Require a book and the negativity at 0.80+ vanishes entirely; the
0.98–1.01 artifact that made pass 3 unreadable goes from **−14.03 to
+0.45**. Below 0.80 the negativity *survives* the filter essentially
unchanged (−4.90→−4.21, −3.30→−3.65), so that half is real.

Two corollaries worth carrying:

- **The pass-3 artifact was never confined to 0.980–0.995.** It pervaded
  0.80 upward, and `insider_bias.screen`'s 0.97 cap did not exclude it —
  the 0.90–0.97 cell was −4.50 unfiltered and is +0.44 filtered.
- **`open_interest` is the load-bearing field, exactly as the correction
  predicted.** Rows passing `spread <= 0.07` but holding *zero* open
  interest are **−2.47** (n=1,929); the same spread test with `oi >= 100`
  is **+0.44**. A one-cent quote on a market nobody holds is still a
  quote, and 55% of the NO side of this cell is exactly that.

That last number is the answer to why the sweep and the screen disagreed:
the sweep's population is majority-untradeable, the screen's is not.

---

# Addendum, same session: the successor thesis was priced, and it is not a trade either

*Reproduce with `mirror.py <copy.db>` — it regenerates every table in this
section and **asserts** the identity below rather than printing it, so the
file fails loudly if the book-side arithmetic is ever changed to something
that violates it.*

Idea 36 (`mid-band-favorite-fade`) came out of the band table above:
buying the favorite at 0.50–0.80 loses **−3.90 pts net (t=−3.30)** even
with a real book, and unlike the 0.80+ bands that number survives every
composition control (series-equal −2.51, **leave-one-series-out negative
in 171/171**). The obvious trade is the mirror — buy the underdog.

**It is not.** The mirror was priced before the ticket was handed over,
because it is arithmetic and needs no new data.

## The favorite's ask and the underdog's ask do not sum to 1

They sum to **1 + spread**, because taking either side crosses the book:

```
favorite_bid  = favorite_ask - spread
underdog_ask  = 1 - favorite_bid = 1 - favorite_ask + spread
```

So the two legs' net edges are bound by an identity, not by symmetry:

```
fav_net + dog_net  ==  -(spread + fee_fav + fee_dog)

measured, 0.50-0.80, n=2,609:
  -3.8989 + -1.0411 = -4.9400   vs  -4.9400    (agreement to 1e-6)
```

**Both sides lose, and they must.** The naive mirror of −3.90 is +3.90;
the real underdog leg is **−1.04**, and the 4.94-point gap is the
round-trip cost (1.68 of spread plus 1.59 + 1.67 of fees).

```
favorite ask   BUY FAVORITE      naive mirror     BUY UNDERDOG
0.50-0.65      -4.21 (t=-1.65)      +4.21           -1.08 (t=-0.42)
0.65-0.80      -3.65 (t=-2.57)      +3.65           -1.01 (t=-0.70)
0.50-0.80      -3.90 (t=-3.30)      +3.90           -1.04 (t=-0.88)
0.80-0.90      +1.73 (t=+1.10)      -1.73           -5.43 (t=-3.39)
0.90-0.97      +0.44 (t=+0.45)      -0.44           -3.06 (t=-3.17)
```

## How much of the "favorites lose" headline is mispricing at all

Separating the market's error from the toll for acting on it —
`mid = ask − spread/2`, gross of fees:

```
fav ask       GROSS @ mid          round-trip cost
0.50-0.65     -1.57  (t=-0.62)          5.29
0.65-0.80     -1.35  (t=-0.95)          4.66
0.50-0.80     -1.45  (t=-1.23)          4.94
0.80-0.90     +3.54  (t=+2.23)          3.69
0.90-0.97     +1.70  (t=+1.77)          2.62
0.97-1.01     +0.90  (t=+1.61)          2.15
```

**In the mid band the market is close to efficient.** The true
mid-relative mispricing is −1.45 and *not significant* (t=−1.23); roughly
three-quarters of the −3.90 headline is the round trip. Idea 36's
mechanism claim — a favorite-longshot bias big enough to fade — is not
supported once the toll is separated out, and no side of it is bettable.

**Idea 36 is recorded dead.** It cost about fifteen minutes to kill,
against the session it would have cost a peer who took the ticket at
face value.

## The generalizable trap, which is why this is in the study and not only the ticket

> **A one-sided net edge of −N does NOT imply an edge of +N on the other
> side.** It implies the other side is at −(round trip − N). Both sides
> lose whenever the mispricing is smaller than the round-trip cost, which
> on this population is ~2.2–5.3 points depending on price.

`net = (win rate − ask) − fee` is the right decision quantity for a bet
that is actually placed, and nothing above changes that. What is wrong is
reading a *negative* cell as an *opportunity on the complement* — the
step from "do not buy this" to "so buy the other one". On this dataset
that step is worth −4.94 points in the mid band, and it is available to
make anywhere a theory reports a signed cell edge.

The one cell where the sign is genuinely favourable is **0.80–0.90**,
underpriced at mid by +3.54 (t=+2.23) — the *opposite* of
favorite-longshot bias. That is noted, deliberately, as an observation
and **not** promoted to a thesis: it was found by looking at a table of
six bands after the fact, its at-ask net is +1.73 (t=+1.10, not
significant), and pre-registering it on the same data that suggested it
is the exact failure this repo has already made twice.
