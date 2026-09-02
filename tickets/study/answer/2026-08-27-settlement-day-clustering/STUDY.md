# Settlement-day clustering is a first-order confound in the ledger

**Date:** 2026-08-27 · **Tier:** A (no model in the measurement path)

## Question

On 2026-08-27 both live theories posted their first settled scores, and
both looked strong:

| theory | disposition | n | calibration_edge_net |
|---|---|---|---|
| `insider_judgment` v3 | screened | 17 | **+11.85** |
| `no_side_premium` v1 | rejected (cell B) | 12 | **+14.59** |

They disagree about the thing they measure. `insider_judgment`'s 17 rows
are all **NO** favorites; `no_side_premium`'s cell B is 12 **YES**
favorites, recorded as an *avoid* list that pre-registration says should
lose (−3.9 net). Both came out strongly positive. Two theories betting
opposite sides of the same screen cannot both have found edge in the same
rows — so what did they find?

Every one of those 29 rows settled on **2026-08-27**.

## Method

Reconstruct the whole population both theories draw from, at a price
recorded *before* any of it settled, and see how the population did.

- Point-in-time board: the `market_snapshots` capture at
  **2026-08-27T01:06:07Z** (110,590 markets) — earlier than the first
  settlement in the sample (02:30Z) and ~16 min before `insider_judgment`
  recorded its rows (01:22Z). For close-days 08-25/08-26, the capture at
  **2026-08-24T22:34:54Z**.
- Population: `theories.insider_bias.screen.screen()` at its pinned
  defaults — the exact shared screen — restricted to markets whose
  `close_time` falls on the day in question. No cherry-picking: this is
  every favorite either theory could have drawn that day.
- Outcome: each market's `result` fetched now.
- Edge: `(win_rate − mean favorite ask) × 100`, net of
  `min(0.07·P·(1−P), 0.035)`, exactly as `tools/score.py` computes it.

Data: `data/close-2026-08-27.json` (n=99 settled of 109),
`data/close-2026-08-25-26.json` (n=116 of 116).

## Result

Whole-population favorite edge, by settlement day:

| close day | n | win rate | implied | edge | **net** |
|---|---|---|---|---|---|
| 2026-08-25 | 96 | 0.917 | 0.867 | +5.00 | **+4.26** |
| 2026-08-26 | 20 | 0.750 | 0.813 | −6.30 | **−7.29** |
| 2026-08-27 | 99 | 0.929 | 0.868 | +6.14 | **+5.40** |
| pooled | 215 | 0.907 | 0.862 | +4.47 | **+3.71** |

Split by side, the reversal is total:

| close day | YES favorites | NO favorites |
|---|---|---|
| 2026-08-25 | n=38, **−1.42** net | n=58, **+7.98** net |
| 2026-08-26 | n=3, −11.50 net | n=17, −6.55 net |
| 2026-08-27 | n=55, **+12.15** net | n=44, **−3.05** net |

On 2026-08-27 **every one of the 55 YES favorites in the population won**
(55/55), and every one of the 52 favorites priced 0.90–0.98 won (52/52).

## What this explains

- **`no_side_premium` cell B's 12/12 is not evidence of anything.** Its 12
  rows are a subset of a day on which all 55 YES favorites in the same
  population won. The cell's +14.59 net is *below* the day's own YES-favorite
  baseline (+12.15) once you account for its price mix. Information content
  about the optimism tax: nil.
- **`insider_judgment` v3's +11.85 net is a day artifact too**, though a
  less flattering one: its rows are NO favorites, and NO favorites that day
  ran **−3.05** net population-wide. Its 16/17 beats that baseline by ~+10
  pts — mildly interesting, entirely inside one day's noise, and drawn from
  unjudged stage-1 screen output rather than the theory's product (its
  `endorsed` tier still has n=0 settled).

## The generalizable finding

The day-level edge on this screen swung **+4.26 / −7.29 / +5.40** over three
consecutive days — a range wider than any edge any theory in this repo
claims. Kalshi's near-term board settles in day-clumps, so a theory drawing
from one screen resolves most of a scan within hours of itself. Rows that
settle together are **not independent draws**, and `compute_score`'s `n`
silently assumes they are.

Consequences:

1. **`n` overstates evidence by roughly the clump size.** 17 rows on one day
   is one draw, not 17. The naive row-level SE at n=17 is ~5.7 pts; the true
   between-day spread is on the order of ±6 pts *per day*.
2. **Any two theories scanning the same board on the same day have
   correlated scores** — they will look good together and bad together,
   which is exactly what happened here.
3. **Side-level claims are the most vulnerable**, because the YES/NO split
   is what reverses between days. `no_side_premium` measures precisely that
   quantity, so its pre-registered bars must count days, not rows.

## What was done about it

- `tools/score.settlement_day_clusters()` — per-day breakdown, `n_days` as
  the effective sample size, and a between-day clustered SE that is `None`
  below two days rather than a falsely narrow row-level number. Wired into
  `python -m tools.cli score report` under `settlement_days`, reported
  *alongside* the row-level figures, never instead of them.
  Tests: `tests/test_settlement_days.py` (6).
- `no_side_premium` THEORY.md: pre-registered bars amended to require
  settlement-day spread as well as row count (2026-08-27 amendment; makes
  confirmation strictly harder, never easier — see that file for the
  honesty argument and why it is not a version bump).
- Both theories' `NOTES.md` carry the dated caveat against their first
  scores.

## Limits

- Three days is not a base rate for the day effect itself; it establishes
  that the effect is large, not what its distribution is.
- Lead times differ (08-27's population was priced 0–23h before close;
  08-25/26's 1–2 days), so the levels are not perfectly comparable across
  days. The *within-day* side split, which is the finding that matters, is
  unaffected.
- Much of the population is sports, and a favorite priced at 01:06Z on a
  game already in progress is close to settled. That inflates the pooled
  favorite edge but is common to both theories and to the control, so it
  does not explain the day-to-day reversal.
- Pooled +3.71 net over 215 rows across 3 days is **not** a tradeable
  finding and is not recorded as one — with `n_days=3` the clustered SE on
  it is ±3.9 pts, i.e. indistinguishable from zero.

## Follow-on

The pooled number is interesting enough to be worth a properly powered
look someday — "are near-term screened favorites systematically
underpriced" is a real question — but it needs weeks of settlement days,
not three, and a design that handles the in-progress-sports contamination.
Recorded as idea `favorite-day-effect`.

---

## Addendum, same day — applying the lens to the repo's historical evidence

Every historical backtest initially returned `n_days=0`: the replays
recorded settlements with **no `resolved_at` at all**, so the repo's entire
body of tier-A evidence — including the numbers `mention_family` was
retired on — could not be day-clustered.

The date turned out to be recoverable with no API call: every backtest row
carries `entry_day_iso` and `days_to_close_at_entry` in `extra_json`, and
their sum is the close date. `backfill_resolved_at.py` (in this folder,
idempotent, never overwrites a real timestamp) filled 6,636 of them.

### The good news first

| run | n | days | row net | day net | row SE | day SE | inflation |
|---|---|---|---|---|---|---|---|
| mention fullcov | 3,441 | 67 | −1.53 | −0.82 | 0.69 | 0.79 | 1.15× |
| insider fullcov | 3,195 | 66 | −1.15 | −1.16 | 0.63 | 1.12 | 1.77× |
| insider judged s200 | 704 | 58 | **+0.67** | **−0.35** | 1.27 | 2.50 | 1.97× |
| insider judged s200b | 644 | 63 | −0.02 | +0.35 | 1.37 | 2.33 | 1.70× |
| insider judged s57 | 216 | 30 | **+1.90** | **−1.36** | 2.02 | 4.78 | 2.37× |

**The historical tier-A evidence survives.** These runs span 30–67
settlement days, so clustering widens their error bars by 1.15×–2.37× —
not the collapse the live one-day samples suffered. Backtests that walk
months of history are largely protected from this confound *by* spanning
many days. The acute problem is a live theory reading one day's rows.

### What it does change

**`mention_family`'s retirement rationale was stated more strongly than
the data supports.** It cited −1.53 net at n=3,441 as showing the family
"priced essentially fairly, so favorites lose the fee." Day-weighted the
same rows give **−0.82 ± 0.79** — about one standard error from zero, and
29 of 67 days were positive. The *conclusion* stands (a family with no
measurable edge is not worth running, and retirement was the user's call
on that basis), but the honest phrasing is **"no measurable edge"**, not
"measurably negative". Nothing here argues for un-retiring it.

**The judged tier-B runs say nothing, and their sign is not stable.**
s200 goes **+0.67 row-weighted → −0.35 day-weighted**; s57 goes **+1.90 →
−1.36**. Both flip sign purely from how the days are weighted, and their
clustered SEs (2.50, 4.78) swamp either estimate. Row-weighting
over-counts busy days, so a few heavy good days lift the row-weighted
number — which is exactly the confound this study is about, showing up in
the evidence that was meant to validate `insider_judgment` v3's buckets.

Consequence for that theory: it stays `testing`, which already means
"claims not demonstrated" — but **it must not be promoted to `active` on
these runs**, and the live endorsed tier (first settlements due
2026-08-28) now carries the weight its backtests cannot.

### A caveat on the arithmetic, stated rather than hidden

Row-weighted and day-weighted point estimates answer different questions,
and the day-clustered SE reported here is the SE *of the day-weighted
mean* — so pairing it with a row-weighted point estimate is not strictly
valid. A cluster-robust SE for the row-weighted estimate was not computed.
For `mention_family` the two readings differ enough to matter (−1.53 vs
−0.82), and both are small and non-positive; the responsible summary is
that its edge is somewhere around zero to slightly negative, and no
weighting makes it positive. The sign instability in the judged runs is
the sharper warning, and it needs no such caveat: an estimate that flips
sign under reweighting is not evidence in either direction.
