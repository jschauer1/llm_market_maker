# Calibration Harvest — lab notebook

Raw, dated, append-only. Distilled findings graduate to `THEORY.md`.

## 2026-08-27 — built; the repo's existing settled data cannot serve this theory

Built from the backlog spec
(`docs/superpowers/specs/theories/2026-08-24-theory-calibration-harvest-design.md`,
priority 1 of 22). Registered `proposed`, deliberately not `testing`: no
cell is measured, so the theory records nothing on the board yet.

**The first thing I checked, and the reason this took longer than "S".**
The repo holds 6,636 settled full-coverage backtest rows
(`backtest-2026-08-25-mention-fullcov` 3,441 +
`backtest-2026-08-25-insider-fullcov` 3,195), all with point-in-time asks
and settlements. Reusing them would have made this a one-hour build. They
are unusable here, for two independent reasons:

1. That population was **fetch-scoped by `replay.NO_CATEGORIES`**, which
   excludes Sports, Crypto, **Climate and Weather**, Commodities,
   Economics, **Elections** and Financials. This theory's central claim is
   that politics and weather have *opposite* signs. The one dataset on
   disk excludes both.
2. It inherits `insider_bias.screen`'s **14-day cap** on days-to-close, so
   every horizon bin beyond two weeks is empty — and Le 2026's horizon
   component is strongest at 1mo+.

Confirmed by inspection rather than assumed: the 461 distinct series in
those runs are mention/entertainment-heavy (KXWCMENTION 855, KXTRUMPMENTION
350, KXRT 242, KXALBUMEQUIV 234...), and the horizon split is
2,219 / 2,331 / 2,086 across `<=2d` / `2d-1w` / `1w-2w` with nothing beyond.

So this theory needs its own collection. Hence `collect.py` rather than a
one-shot `backtest.py`.

**Sizing the campaign** (measured 2026-08-27 against `/series`, 13,578
series total): Politics 2,240 (1,060 touched in 60d), Elections 1,606
(1,444), Climate and Weather 360 (154). The two pre-registered domains are
~2,650 series of per-series settled walks plus a candlestick call per
settled market. That is a multi-session campaign, which is why the
collector checkpoints per series and writes every observation to the DB as
the series completes.

**Design decisions worth recording:**

- *One observation per (market, horizon bin).* The rows share an outcome
  and are not independent — but every row of one market settles on the
  same day, so the day-clustered SE this theory already mandates absorbs
  that dependence for free. The residual bias (markets contributing
  unequal row counts tilt the point estimate) is in THEORY.md's known
  biases and is the reason `n_days`, not `n`, gates `measured`.
- *Entry offsets 1 / 4 / 14 / 45 days* sit comfortably inside their bins
  so a one-candle timing slip cannot move an observation across a cell
  boundary.
- *No import from `theories/insider_bias/`.* Forbidden as a sibling
  import, and wrong on the merits — the 14-day cap is exactly the
  parameter this theory must not have. The overlapping spread/volume
  numbers are coincidence of both wanting tradeable markets.
- *Wilson lower bounds everywhere.* `mention_family` computed edges
  against a raw 41/41 = 1.000 and died at full coverage; its own NOTES had
  flagged the unshrunk rate as a defect. A grid of cells guarantees some
  cell looks golden, so the pessimistic end of the interval is the only
  honest reading.

**Smoke test (NOT a result).** Ran the collector over the first 4 weather
series by API order — 218 observations, 58 settlement days:

```
weather|<=2d|0.65-0.75   30/41   days=37
weather|<=2d|0.75-0.85   39/50   days=33
weather|<=2d|0.85-0.92   40/42   days=32
weather|<=2d|0.92-0.97   76/81   days=49
```

Overall +0.58 pts net with a day-clustered SE of 1.7 — indistinguishable
from zero, which is the correct thing for a smoke test to show.

**These numbers must not be read as evidence** and are recorded only to
show the pipeline works: 4 of 154 series, taken in API order, is exactly
the thin non-random slice that killed `mention_family`. The theory's own
rule is full coverage of a population before any cell publishes a rate.

One genuinely encouraging structural fact did come out of it, and it is
about the *method* rather than the result: weather cells reach 32–49
distinct settlement days at n≈41–81, because weather markets settle every
single day. That is the opposite of the day-clustering problem found in
`studies/2026-08-27-settlement-day-clustering/`, and it means the weather
domain can clear the `n_days >= 8` floor easily. The politics domain,
whose markets cluster on event dates, will be much harder — worth watching
when that collection runs.

**Next:** full weather collection (154 series) started in the background
tonight against `--run-id backtest-2026-08-27-calharvest-weather`,
checkpoint at `backtests/weather.json`. Politics+Elections
(~2,504 series) is the larger job and has not been started. The theory
moves to `testing` only once a population is complete and a cell clears
both floors under full coverage.

## 2026-08-27 (later) — collector was measuring a population the screen would never trade

Caught while watching the first full weather run: **`collect.py` applied no
volume floor at all**, while `screen.py` requires `volume >= 500`. The
replay was therefore reconstructing decisions on markets the live theory
could never have surfaced, and every cell rate it produced would have
described an untradeable population. That is the exact failure the
backtest rule in CLAUDE.md is written to prevent — "call the same
functions the live path calls" — and I had reimplemented the screen's
conditions in the collector while dropping one of them.

The 417 observations already collected were discarded (rows deleted;
settlements kept, since those are facts about the world rather than
decisions) and the checkpoint reset. Nothing was published from them.

Fixed in two places, both mirroring `insider_bias.replay`:

- `_candle_at` now returns `(candle, running_volume)`, accumulating volume
  over exactly the candles at or before the entry moment. Kalshi's candle
  volume is per-period, not cumulative, so the running sum is what the
  live screen's `volume` field would have shown — and summing only to the
  entry candle is what keeps it lookahead-free. An entry below the floor
  yields no observation for that bin.
- `worth_fetching(volume)` skips a settled market before any candlestick
  call when its *final* volume is under the floor. Cumulative volume only
  grows, so a market that ends below the floor was below it at every
  earlier moment — a safe, conservative pre-filter, and the same argument
  `replay.is_candidate` makes.

The second one is also the fix for a practical problem: the first run was
managing ~80s per series (11 of 154 in ~15 minutes, a ~3.5h projection)
because it fetched 60 days of daily candles for *every* settled market
including low-volume husks. `below_floor` is now reported per series so
the skip rate is visible rather than assumed.

**No version bump.** The theory is `proposed`, has never run live, and has
published no measurement — this is fixing the procedure before it has a
track record, not changing one that has. Had a single cell been published
from the old rule, this would have been a v2.

Lesson worth carrying: a collector that *reimplements* the screen's
predicates instead of calling `screen.screen()` will drift from it, and
the drift is invisible until someone diffs the two by eye. The sibling
`insider_bias.replay.replay_market` avoids this by running the real
`screen.screen()` against a reconstructed `Market`. This collector cannot
do quite the same thing — it needs an observation *per horizon bin*
rather than the first day that clears — but the next revision should
reconstruct a `Market` and call the real screen per bin rather than
re-checking spread/volume/price by hand.
