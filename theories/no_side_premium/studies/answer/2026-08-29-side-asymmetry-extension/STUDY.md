# The paired within-day estimator, and two more close-days for it

**Date:** 2026-08-29 · **Tier:** A (no model in the measurement path) ·
**Verdict:** the bar is met and nothing is there - at 8 close days NO-YES is +2.91 (t=0.53, 5/8 days), and the paired estimator is measured as the worst of four (477 days to detect +2.0); pairing was the wrong instrument ·
**Code:** the investigation was deleted 2026-09-03; it lives at git rev `38028e6` - `git ls-tree -r --name-only 38028e6 theories/no_side_premium/studies/answer/2026-08-29-side-asymmetry-extension` lists it, `git show 38028e6:<path>` returns any file

## Question

`no_side_premium` is scored on `calibration_edge_net` per disposition. On
2026-08-29 that read **−10.44 net at n=46** for cell B, which looks like a
theory failing. But cell B is an *avoid* list — rows recorded as `rejected`
precisely because the theory predicts they lose — so a negative number is the
prediction coming true, not a failure. Two questions follow:

1. Is cell B's −10.44 a measurement of the cell, or of the days it settled on?
2. Is there a sharper estimator for the thing the theory actually claims?

## Method

Unchanged from `tickets/study/answer/2026-08-27-settlement-day-clustering/`, so the days
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

Note (2026-08-30): re-running this probe against post-compression snapshot rows requires routing raw_json/event_json reads through tools.snapshot.payload_text (spec 5.2 phase 3).

---

# Pass 2 — 2026-09-01: the bar is reached, the answer is null, and the estimator was the wrong one

**Date:** 2026-09-01 · **Tier:** A (no model in the
measurement path)

This is the pre-registered follow-on above ("re-run `measure.py` with a new
(close day, snapshot) pair each session; the series reaches the `n_days >= 8`
bar around 2026-09-01"). It reaches it.

## What was added, and one rule fixed before any number was computed

| | |
|---|---|
| new close-days | 2026-08-30, 2026-08-31 |
| re-measured | 2026-08-29 (was 24-of-70 settled), 08-28, and the 2026-08-27 study's 08-25/26/27, each with **its own** original snapshot pair |
| added to reach 8 | **2026-08-24**, from the earliest capture in the DB (`2026-08-24T01:34:44Z`) |
| excluded | 2026-09-01 — 27 of 148 settled (18%) |

**Inclusion rule, fixed before the numbers: a close day enters the series at
>= 90% settled.** The 08-29 day is why. It entered pass 1 at 24-of-70 and
read **+9.49**; complete, it reads **+4.10**. Early settlers are finished
sports, so a partial day is a biased draw, not merely a small one.

That rule left 7 days against a bar of 8, and the temptation was to admit
2026-09-01 at 18% to reach the bar. Instead close-day **2026-08-24** was
added — a complete day (155 of 156 settled) the series had simply never
used, measurable by the identical method from the earliest capture on disk.
**The decision to add it was taken and written down before its value was
computed** (+14.11, as it turned out).

**Every day is now measured at one vintage.** Re-measurement is not
cosmetic: 08-28 moved +32.60 -> **+28.97** and 08-27 -15.20 -> **-19.56**
as their remaining markets settled. A series whose early days are frozen at
an older settlement state is not one series.

## A defect this pass had to fix first — and it is not local to this study

`measure.py` rebuilt its point-in-time board with
`SELECT ... WHERE captured_at = ?`. **Dedup-on-write (spec 5.2 phase 2,
shipped 2026-08-30) makes that wrong**: a pull now writes *no row* for a
market whose payload did not change, so an exact-stamp filter returns "the
markets that moved at this pull" — a subset correlated with liquidity, and
therefore with price and side, which is precisely what this study measures.
It fails silently, returning a plausible board of the wrong markets.

Measured on the live DB:

| capture | rows at that stamp | actual board |
|---|---|---|
| 2026-08-29T13:14:32Z | 110,628 | 110,628 (pre-dedup) |
| 2026-08-30T17:41:41Z | 81,827 | 105,346 |
| **2026-08-31T00:38:34Z** | **53,613** | **99,064 (46% missing)** |
| 2026-09-01T02:06:51Z | 79,961 | 105,104 |

The 105,104 figure is exactly the board size the 2026-09-01 floor reported
pulling, which is the check that the reconstruction is right.

Fixed by `tools.snapshot.board_as_of(conn, platform, at)` — the row per
market whose `[captured_at, last_seen_at]` interval contains the instant.
Promoted to `tools/` under the normal caller-count rule: three study probes
had already open-coded the broken query. Pinned by six tests in
`tests/test_snapshot_store.py`, including the deliberate semantic that a
market whose price *changed* across a gap is absent mid-gap rather than
reported stale — an interval is known validity, not assumed validity.

The two remaining callers are ticketed, not fixed here (other studies, other
lanes): `theories/structural_arb/studies/answer/2026-08-29-structural-arb-violation-liquidity/probe.py` and
`tickets/study/answer/2026-08-27-calendar-arb-firing-rate/probe.py`. Both produced their
recorded results against pre-dedup captures, so **their published numbers
stand**; only a re-run would be wrong.

## Result — the bar is met and nothing is there

```
close day     settled              all              YES               NO    NO-YES
2026-08-24        99%     n=155  -4.59     n=61  -13.14     n=94   +0.97     14.11
2026-08-25       100%     n=96   +4.26     n=38   -1.42     n=58   +7.98      9.40
2026-08-26       100%     n=20   -7.29     n=3   -11.50     n=17   -6.55      4.95
2026-08-27       100%     n=109  +3.32     n=60  +12.11     n=49   -7.45    -19.56
2026-08-28       100%     n=175  -4.60     n=63  -23.14     n=112  +5.83     28.97
2026-08-29       100%     n=70   +8.31     n=32   +6.08     n=38  +10.18      4.10
2026-08-30       100%     n=63   +1.75     n=10   +5.61     n=53   +1.02     -4.59
2026-08-31        91%     n=180  +0.04     n=77   +8.10     n=103  -5.98    -14.08
2026-09-01        18%  EXCLUDED, partial

n_days = 8  (bar: >= 8)      mean NO-YES = +2.91 pts
day-clustered SE = 5.51      t = +0.53 on 7 df     95% CI [-7.89, +13.72]
sign test: 5/8 days positive (two-sided p = 0.727)

day-equal-weighted YES side = -2.16  (cell B claims -3.9)
day-equal-weighted NO  side = +0.75  (cell A claims +2.0)
```

Pass 1 read +8.25 at 5 days with the sides at -4.42 / +3.83, and called that
"right sign, not significant". **Three more days moved every one of those
numbers toward zero.** The agreement of two point estimates with their
priors, which pass 1 was careful to call encouraging rather than
significant, did not survive.

## The finding: pairing was the wrong instrument, and that is measured

Pass 1 adopted the paired `NO - YES` statistic on the reasoning that the day
effect is *a common shock to both sides*, so it cancels in the difference.
Eight days let that premise be tested rather than assumed, and **it is false
in this population**:

```
paired NO-YES, all bands : between-day SD 15.59 pts ->  477 days to detect +2.0
NO 0.90-0.97, single side: between-day SD  5.64 pts ->   62 days
NO all bands,  single side: between-day SD  6.90 pts ->   93 days
YES all bands, single side: between-day SD 12.46 pts ->  304 days
```

(80% power, two-sided 5%.) The paired estimator is the **worst of the
four**. If the sides were merely independent the difference would carry
SD sqrt(6.90^2 + 12.46^2) = 14.24; the observed 15.59 is larger still, so
day to day the two sides are if anything *negatively* correlated.
Differencing imports the YES side's variance instead of cancelling it.

The mechanism is plain in hindsight and worth stating, because the premise
looked obviously true: the YES favorites and the NO favorites in this screen
are **different markets on different subjects**, not two sides of one
contract. There is no shared shock to cancel. Pass 1's reasoning would have
been right for a paired long/short on the same market.

Consequence: **the pooled paired claim is unresolvable on any practical
horizon** — 477 settlement days is ~1.3 years of daily accrual, against a
Kalshi archive window of ~60 days.

## Where the structure actually is

Day-clustered, on the 8 complete days (868 settled favorites):

```
BY SIDE x PRICE BAND
  YES 0.65-0.80     n=97  days=8  mean= -0.09  SE= 6.96  t=-0.01  4/8+
  NO  0.65-0.80     n=124 days=8  mean= +1.31  SE= 5.73  t=+0.23  4/8+
  YES 0.80-0.90     n=90  days=7  mean= -0.86  SE= 5.64  t=-0.15  4/7+   <- cell-B mechanism (-3.89 fullcov)
  NO  0.80-0.90     n=125 days=8  mean= -8.30  SE=11.48  t=-0.72  5/8+
  YES 0.90-0.97     n=157 days=8  mean= -0.80  SE= 3.69  t=-0.22  5/8+
  NO  0.90-0.97     n=275 days=8  mean= +1.70  SE= 1.99  t=+0.85  7/8+   <- cell-A mechanism (+2.25 fullcov)

BY SIDE, MENTION FAMILY vs REST
  YES mention-family   (no rows in 8 days)
  NO  mention-family  n=15  days=2  mean= +3.72  SE=1.42  t=+2.63  2/2+
  NO  rest            n=509 days=8  mean= +0.59  SE=2.50  t=+0.24  5/8+
  YES rest            n=344 days=8  mean= -2.16  SE=4.40  t=-0.49  4/8+
```

Two things to read here, and the second matters more than the first.

**1. `NO 0.90-0.97` is the only cell that looks like anything.** +1.70
against a +2.25 fullcov measurement and a +2.0 prior, 7/8 days positive
(sign test two-sided p = 0.070), and by far the tightest SE on the board.
It is **not significant** (t = 0.85) and it is one of 13 cells inspected
here — but unlike the other 12 it was *pre-registered*, being idea 14's
mechanism and the cell both fullcov backtests measured. Its interest is
that it is the one place where the effect's size, sign and stability all
agree with a prior fixed before the data.

**2. Cell A's actual population is 15 rows on 2 of 8 days.** The mention
family barely appears in this screen: 15 NO rows total, zero YES rows. Its
`n >= 40` / `n_days >= 8` bars are therefore a long way off, and the +3.72
at 2 days is the same one-cluster non-result the 08-27 amendment exists to
refuse. **The band carries the signal; the family restriction is what
starves it** — `NO 0.90-0.97` across the whole screen is 275 rows over 8
days, 18x the population, at a comparable point estimate.

That is a finding about the theory's design, not a licence to widen cell A
mid-test. Widening a pre-registered cell because the narrow one is thin,
after seeing the data, is the exact move the pre-registration exists to
prevent. It is filed instead as a **new pre-registered theory** (ticket and
idea `no-favorite-high-band`), which is how `no_side_premium` itself came
off `mention_family`.

## Limits

- 13 cells were inspected. Only `NO 0.90-0.97` and `YES 0.80-0.90` were
  pre-registered; the other 11 carry no multiple-comparison protection, and
  none of them cleared |t| = 1 anyway.
- 8 days is enough to reject "large effect", not to establish "no effect".
  The 95% CI on the pooled paired statistic is [-7.89, +13.72]; a +2 effect
  sits comfortably inside it. **Unconfirmed, not disproven.**
- The population stays sports-heavy, and a favorite priced hours before a
  game in progress is near-settled. Common to both sides, so it does not
  explain a side split, but it inflates every level.
- The power figures assume the between-day SD estimated from 8 days is the
  true one. On 7 df that estimate is itself loose.

## Follow-on

- Read `no_side_premium` on the **single-side NO 0.90+** figure, not the
  paired one. Same claim, ~8x less data needed.
- Keep re-running `measure.py` each session; it is one command and the only
  cost is the quote fetch.
- 2026-09-01 must be re-measured once settled — it is written to disk and
  excluded by the 90% rule, so it enters by itself when it completes.

### Robustness, run after the headline — and it matters in both directions

**1. The day added to reach the bar was not carrying the result.** 08-24 was
added to reach `n_days=8` without admitting a partial day, and it is also the
one day that could overlap the window the founding fullcov backtests were run
over (they ran 2026-08-25). Dropping it makes the result **more** null, not
less:

| | 8 days | without 08-24 |
|---|---|---|
| paired NO-YES | +2.91, SE 5.51, t=0.53 | **+1.31, SE 6.09, t=0.22** |
| NO 0.90+ single side | +1.70, SE 1.99, t=0.85 | **+1.22, SE 2.23, t=0.55** |

So the null conclusion does not depend on it, and if anything 08-24 flattered
the thesis. (The overlap is in any case at most a handful of rows — the
mention family supplies 15 NO rows across all 8 days.)

**2. Leave-one-out says the paired statistic is one day.** Drop 08-28
(+28.97) and the pooled paired mean goes **negative**, -0.81. Nothing else
moves it much. An 8-day mean that flips sign on one day is not a measurement,
which is the same thing the power calculation says in another language.

**3. The NO 0.90+ cell, per day — and a weighting trap caught in the act.**

| close day | n | wins | win rate | mean ask | net |
|---|---|---|---|---|---|
| 2026-08-24 | 47 | 47 | 1.000 | 0.946 | +5.05 |
| 2026-08-25 | 29 | 28 | 0.966 | 0.950 | +1.19 |
| **2026-08-26** | **6** | **5** | 0.833 | 0.945 | **-11.53** |
| 2026-08-27 | 26 | 26 | 1.000 | 0.945 | +5.18 |
| 2026-08-28 | 71 | 70 | 0.986 | 0.944 | +3.82 |
| 2026-08-29 | 24 | 24 | 1.000 | 0.938 | +5.80 |
| 2026-08-30 | 27 | 26 | 0.963 | 0.950 | +1.00 |
| 2026-08-31 | 45 | 44 | 0.978 | 0.943 | +3.10 |

Seven of eight days sit between +1.00 and +5.80. The single negative day is
a **6-row day** whose whole deficit is one loss.

Day sizes run 6 to 71, so the weighting choice moves this cell a lot:

```
row-pooled (n=275)              +3.32
day-equal weighted              +1.70   SE 1.99   t=0.85     <- reported
days with >= 10 rows (7 days)   +3.59   SE 0.73   t=4.93
```

**The third line is not a finding and must not be quoted as one.** A >=10
rows/day floor drops exactly one day — the only negative one — and the only
reason to reach for that floor is having already seen that the negative day
was the small one. That is precisely the failure the calibration_harvest
gradient review caught on 2026-08-29
(`theories/retired/calibration_harvest/studies/answer/2026-08-29-calibration-harvest-gradient-review/`,
peer review by llm-market-identifier-4f): **the inclusion
rule was the result.** It is recorded here because it was tempting, not
because it is evidence.

The honest reading: **+1.70 +/- 1.99 is the number**, and this cell is *not
yet weighting-robust* — a spread of +1.70 to +3.59 across defensible
weightings, driven by one thin day. The correct response is to fix a
minimum-rows-per-day rule **before** collecting more, which is now part of
what `no-favorite-high-band` must pre-register.
