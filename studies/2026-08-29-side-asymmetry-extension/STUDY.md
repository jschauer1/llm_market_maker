# The paired within-day estimator, and two more close-days for it

**Date:** 2026-08-29 · **Status:** complete · **Tier:** A (no model in the
measurement path)

## Question

`no_side_premium` is scored on `calibration_edge_net` per disposition. On
2026-08-29 that read **−10.44 net at n=46** for cell B, which looks like a
theory failing. But cell B is an *avoid* list — rows recorded as `rejected`
precisely because the theory predicts they lose — so a negative number is the
prediction coming true, not a failure. Two questions follow:

1. Is cell B's −10.44 a measurement of the cell, or of the days it settled on?
2. Is there a sharper estimator for the thing the theory actually claims?

## Method

Unchanged from `studies/2026-08-27-settlement-day-clustering/`, so the days
compose into one series: population is `theories.insider_bias.screen.screen()`
at pinned defaults over a point-in-time board snapshot captured **before** the
day's settlements, restricted to markets closing that day; outcome fetched now;
edge is `(win_rate − mean favorite ask) × 100` net of
`min(0.07·P·(1−P), 0.035)`, exactly as `tools/score.py` computes it.

Two close-days added, both from snapshots that precede their settlements:

| close day | snapshot | population | settled |
|---|---|---|---|
| 2026-08-28 | `2026-08-27T23:18:30Z` | 175 | 158 |
| 2026-08-29 | `2026-08-29T00:06:13Z` | 70 | **24 (partial)** |

`measure.py` builds these; `compose.py` joins them to the earlier study's
three days and reports the paired statistic. The composed `all` column
reproduces the original study's +4.26 / −7.29 / +5.40 exactly, which is the
check that the method really is the same one.

**One implementation trap, recorded because it fails silently:** `screen()`
filters on days-to-close and defaults `now` to the wall clock, so run against
a historical snapshot without `now=<capture time>` it drops every market that
has since closed — the entire settled population — and returns ~0 rows without
erroring.

## The estimator

The theory's claim is a *side* claim: NO favorites beat YES favorites at
comparable prices. `compute_score` measures each side against its own price,
so it inherits the whole day swing — which the earlier study measured at
+4.26 / −7.29 / +5.40, wider than any edge any theory here claims.

The day effect is a **common shock to both sides**, so it cancels in the
within-day difference. `NO_net − YES_net`, computed per day and averaged over
days, is therefore the same claim measured with the dominant noise term
removed.

## Result

| close day | all | YES | NO | **NO − YES** |
|---|---|---|---|---|
| 2026-08-25 | n=96 +4.26 | n=38 −1.42 | n=58 +7.98 | **+9.40** |
| 2026-08-26 | n=20 −7.29 | n=3 −11.50 | n=17 −6.55 | **+4.95** |
| 2026-08-27 | n=99 +5.40 | n=55 +12.15 | n=44 −3.05 | **−15.20** |
| 2026-08-28 | n=158 −5.82 | n=58 −26.45 | n=100 +6.15 | **+32.60** |
| 2026-08-29 † | n=24 +9.46 | n=13 +5.11 | n=11 +14.60 | **+9.49** |

† partial day — 24 of 70 settled at measurement time, skewed toward markets
that settle early (finished sports). Re-measure and replace.

```
n_days = 5                      (theory's amended bar: >= 8)
mean NO-YES      = +8.25 pts
day-clustered SE =  7.60   t = +1.08 on 4 df
sign test        = 4/5 days positive, two-sided p = 0.375
```

Per-side day-equal-weighted means, against what the theory pre-registered:

| | measured (5 days) | pre-registered claim |
|---|---|---|
| YES side | **−4.42** | −3.9 (cell B) |
| NO side | **+3.83** | +2.0 (cell A, narrower slice) |

## What this says

**Unconfirmed, right sign, and the point estimates are close.** Both sides land
within ~1.8 pts of their pre-registered values, and 4 of 5 days carry the
predicted sign — but with `n_days=5` against an amended bar of 8, and
`t=1.08`, none of that is a result yet. The agreement of two independent point
estimates with their priors is encouraging and is *not* significance.

**Cell B's −10.44 is not evidence about cell B.** Its three settlement days
ran +14.18 / −29.74 / −4.93 net; the day-clustered SE is **12.73**, larger
than the point estimate. Under the theory's own amendment this is `n_days=3`
— unmeasured, exactly as the 12/12 on a single day was in the other direction.

**A contaminated control, recorded so nobody repeats it.** An intermediate
pass in this session compared cell B against *other YES favorites in the
ledger* on the same day and found the deltas +7.32 / +0.25 / +19.27 (mean
+14.84) — cell B never underperforming. That control is worthless twice over:
the comparison population is the very population the thesis indicts, and
ledger rows are theory picks rather than a sample of the board. The clean
population gives +8.25, not +14.84. Use the snapshot population, never the
ledger, for anything population-level.

## Recommendation (evidentiary, not a version bump)

Read `no_side_premium` on the paired within-day statistic as the primary
figure, with `compute_score`'s per-disposition numbers kept alongside. This
changes nothing about the decision procedure — population, cells, sides,
bands and recording are untouched — so it is the same kind of change as the
2026-08-27 day amendment, and like that one it makes confirmation *harder*:
the pooled −10.44 flatters the cell-B claim, while the paired estimator says
there is not yet a result either way.

Cell A still has **0 settled rows**. Its rows are `KXTRUMPSAY-26AUG31`
strikes closing 08-31, so its first evidence arrives in two days.

## Limits

- Five days is still not a distribution for the day effect; it establishes
  that the paired estimator is *stable in sign*, not what its spread is.
- 08-29 is partial and will move.
- Much of the population is sports, and a favorite priced hours before a
  game already in progress is close to settled. Common to both sides, so it
  does not explain the side split, but it inflates every level.
- Lead times differ by day (0–24h here, 1–2 days for 08-25/26), so levels are
  not perfectly comparable across days. The within-day difference is
  unaffected, which is the point of using it.

## Follow-on

Re-run `measure.py` each session with a new `(close day, snapshot)` pair; the
series reaches the theory's `n_days >= 8` bar around 2026-09-01 if days keep
accruing at one per session.
