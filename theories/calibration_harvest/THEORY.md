# Calibration Harvest

## Hypothesis

Kalshi prices are systematically miscalibrated as a function of
**price × horizon × domain**, and the *direction* of the miscalibration
depends on the cell. Bet the side each cell's own measured realized rate
says is cheap, when the gap exceeds the ask plus fees.

This is the favorite-longshot bias (Griffith 1949), measured on Kalshi
specifically and twice at scale:

- **Whelan, "Makers and Takers"** (300,000+ contracts): low-price
  contracts win far less often than break-even requires after fees;
  high-price contracts win more often and return slightly positive.
- **Le 2026** (353M trades, 429k contracts; arXiv:2602.19520): calibration
  slopes by domain × horizon. **Politics compressed toward 50% at nearly
  every horizon** (slopes 1.32–1.83 beyond 3h; at a raw price of 0.75 the
  isotonic estimate is 0.886 — a ~13-point gross gap on the favorite
  side). **Weather is the opposite inside 12h** (slopes 0.69–0.87; a 75¢
  weather contract is really 69.1% — the favorite is *rich*). The
  universal horizon component rises 0.99 (0–1h) → 1.32 (1mo+).

**Why it persists.** The mechanism is structural preference, not a
mispricing anyone can see on a single market: lottery-ticket appetite on
the cheap side, capital-lockup aversion on the expensive side. Neither is
arbitrageable — collecting the favorite premium means locking capital at
a low percentage return per contract, which is exactly the thing the
people creating the bias will not do. It should therefore decay slowly if
at all.

**What would falsify it.** No cell clears fees out-of-sample at n ≥ 30
*and* n_days ≥ 8. That is the kill criterion, and it is a real
possibility: the bias is well documented in *gross* terms and Kalshi's
fee (`min(0.07·P·(1−P), 0.035)`) is worst exactly in the mid band where
compression is largest.

**The mention_family precedent, which governs this theory's design.**
A sibling theory ran this same mechanism — price bins → measured rate →
edge — on one ticker family. A ~3% systematic sample measured +5.48 pts
net; full coverage of the same window measured **−1.53**, and the theory
was retired. The lesson is not that price bins fail; it is that a thin
sample of a cell grid manufactures winners. This theory therefore refuses
to publish a cell's edge from anything but full coverage of its
population, applies Wilson lower bounds rather than raw rates, and splits
the sample in time before believing a cell.

## Data sources

All in-repo, no external feeds, no LLM:

- `tools.board.get_board(conn)` — the session board (live screen).
- `tools/kalshi/markets.py::list_settled` — settled markets per series
  (~60-day reachable window; Kalshi archives beyond that).
- `tools/kalshi/history.py` — candlesticks for the point-in-time ask.
- `/series` category field — the domain axis.
- `tools/sizing.py` — fee math.

## Status

`testing` — 2026-08-29. The first pre-registered population is
**complete** (Climate and Weather, 154/154 series, 3,267 observations over
3,260 settled markets, run `backtest-2026-08-27-calharvest-weather`), and
four cells clear both floors, so the `proposed` condition below is met.

**What the first population measured: nothing to harvest.** All four
measured cells are `<=2d`, each with n≈700–930 over **59 settlement
days**, and every one is inside its own day-clustered noise band:

| cell | n | mean ask | realized | raw edge | day-clustered |
|---|---|---|---|---|---|
| `<=2d\|0.65-0.75` | 824 | 0.6954 | 0.6978 | +0.25p | +0.58 ± 1.80 |
| `<=2d\|0.75-0.85` | 789 | 0.7938 | 0.7959 | +0.21p | −1.09 ± 1.97 |
| `<=2d\|0.85-0.92` | 692 | 0.8803 | 0.8931 | +1.27p | +1.63 ± 1.29 |
| `<=2d\|0.92-0.97` | 926 | 0.9488 | 0.9417 | −0.71p | −0.83 ± 0.85 |

Short-horizon Kalshi weather favorites are priced correctly. Net of fees
and the Wilson bound all four are negative, so the theory emits **nothing**
on this domain — neither a favorite buy nor the mirrored fade. A live run
producing zero candidates from weather is correct behaviour, not a fault.

**The claim this population cannot test.** Every longer-horizon cell has
n ≤ 8: weather markets list and settle within days, so `2d-1w`, `1w-1mo`
and `1mo+` are structurally empty here. The thesis is about horizon
compression ("everything compresses at 1mo+"), so the weather walk tests
one column of a four-column claim. **Politics/Elections is where the
horizon spread lives, and it is not yet collected.** Do not read the
weather result as evidence for or against the theory's central claim.

The original `proposed` bar, now met, was: `collect.py` has completed its
first pre-registered population and `cells.py` has at least one cell at
n ≥ 30 with full coverage of that population.

It does not become `active` until a cell shows positive *net* calibration
edge out-of-sample, at n ≥ 30 **and** n_days ≥ 8 (see the day-clustering
rule below).

## Version

2 — 2026-08-29: **the Wilson bound counts settlement days, not rows.**

This theory already refused to call a cell `measured` below
`MIN_CELL_DAYS`, on the stated grounds that rows are not independent
draws — a screen's whole near-term board settles within hours of itself,
and the 2026-08-27 clustering study measured the day-level swings
directly. But `cell_edge` then took its Wilson bound on the **row** count,
which undid that protection at the one point where it decides whether to
commit money.

Measured on the first complete population: the `<=2d|0.75-0.85` cell went
628/789 over 59 settlement days. Row-counted, the bound claimed
**+1.64 pts** at an ask of 0.75; day-counted it says **−7.27 pts**. Three
live rows priced positive on the row-counted bound; under v2, none do.

The fix collapses the cell to its day count before bounding
(`wilson_lower(round(p·n_days), n_days)`). That is deliberately
conservative rather than clever: it under-uses genuine within-day
information, and a proper cluster-robust interval would sit somewhere
between `n_days` and `n`. Under-claiming is the safe direction for the
number that decides a bet, so the cheap version ships and the refinement
is a later version's job.

**Also in v2, not a decision change:** `price()` now records each row's
cell in `extra_json` (via the new `ScoredCandidate.extra`). An unmeasured
cell's rows exist *only* so that cell can accrue settlements, and
`collect.cell_rates` reads the cell out of `extra_json` — so before this,
every live row was invisible to the grid it was recorded to grow.

1 — initial. Two pre-registered cell families, the price/horizon/category
grid in `cells.py`, Wilson-lower-bound edges, and the overlap exclusions.

## Stage 1 — mechanical screen

Fully deterministic; the whole decision path is code.

1. **Population.** Board markets with a favorite-side ask in
   `[0.65, 0.97]`, plus the mirrored fade band `[0.03, 0.35]` where a
   cell's measured sign says the favorite is rich. Liquidity floor
   `volume >= 500`, spread `<= 0.07`.
2. **No days-to-close cap.** The documented compression *grows* with
   horizon, so capping days would discard the strongest cells. Horizon is
   binned instead (`<=2d` / `2d-1w` / `1w-1mo` / `1mo+`) and capital
   lockup enters through sizing, never the screen.
3. **Cell assignment** (`cells.py`): price bin × horizon bin × coarse
   category, from the series' Kalshi category.
4. **Overlap exclusions**, so two theories never book the same trade.
   These are part of the versioned procedure:
   - **Mention family** (`is_mention_family`) — was `mention_family`'s
     population; retired, but its rows are in the ledger and its window
     overlaps ours.
   - **The YES/NO side-conditional effect at equal price** belongs to
     `no_side_premium`. This theory's cells are *price-level* cells and
     carry no side claim; where the two screens would fire on the same
     contract, this one yields.
   - A gate report names what each exclusion removed, by category.
5. **Edge.** `edge = wilson_lower(cell) − ask − fees`. `edge_basis =
   "measured"` only for cells with n >= 30 **and** n_days >= 8 under full
   coverage of their population; `"model"` for thinner cells, which are
   reported but never recommended.

## Stage 2 — none

There is no LLM anywhere in the decision path. No gate, no analysis, no
prompts, no provenance rows. Tier A by construction, and deliberately so:
the thesis is a measured rate against a price, which is arithmetic.

## Confidence buckets

Not applicable — this theory records `edge_basis="measured"` or `"model"`,
never a judged bucket. Its cells *are* its buckets, and their rates come
from `collect.py`'s measurement rather than from any scale declared here.

## The day-clustering rule (non-negotiable)

Kalshi's board settles in day-clumps: a screen's near-term candidates
resolve within hours of each other, so rows that settle together are not
independent draws. Measured on the shared insider_bias screen population
over three consecutive close-days
(`studies/2026-08-27-settlement-day-clustering/`, n=215, whole
population), the day-level favorite edge ran **+4.26 / −7.29 / +5.40**
net and the YES/NO split reversed outright between days.

That swing is larger than the edge this theory hopes to harvest. So:

- Every cell rate carries `n_days` alongside `n`, from
  `score.settlement_day_clusters()`.
- No cell is `measured` below `n_days >= 8`, whatever `n` says.
- Cell edges are reported with the between-day clustered SE, never the
  row-level SE.

A cell measured on 400 rows that settled across three days is *not*
measured, and this theory will say so rather than quietly banking it.

## How to backtest

**Tier A** — no LLM in the decision path, so all reachable history counts.

The replay is `collect.py` in this folder (never `tools/`), and it is a
*collector* rather than a one-shot replay because its population is far
larger than one session can fetch:

- Series are enumerated from `/series`, filtered to the target categories
  and to `last_updated_ts` within the reachable window.
- Each series is walked with `list_settled(series_ticker=...)`, and each
  surviving market's point-in-time ask is reconstructed from candlesticks
  at the horizon bin's entry offset.
- **Checkpointed per series**: `collect.py` writes each series' result to
  the DB as it completes and records progress, so an interrupted run
  resumes rather than restarting. Kalshi archives settled markets ~60
  days after close, so data not captured now may be unrecoverable
  upstream later — the collector never holds results in memory.

Split-sample: cell rates are fit on the earlier half of the collected
window and evaluated on the later half. A cell counts only if it survives
out-of-sample. With many cells × two signs, this is the main statistical
guard, and it is doubled by the Wilson bound and the `n_days` floor.

**Known biases to state with any result:** the reachable window is ~60
days, far shorter than either paper's; candlestick gaps mean some markets
have no reconstructable entry price and drop out (the insider fullcov run
lost 493 of 7,948 that way); and category comes from Kalshi's own coarse
series label, which is versioned here but not audited market by market.

## Learnings

Nothing measured yet. 2026-08-27: the design decision worth recording
before any data arrives is that the repo's *existing* full-coverage
settled data (`backtest-2026-08-25-*-fullcov`, 6,636 settled rows) cannot
serve this theory — that population was fetch-scoped to exclude Sports,
Crypto, Climate and Weather, Commodities, Economics, Elections and
Financials, and capped at 14 days to close, so it excludes **both**
domains whose contrast is this theory's central claim and every horizon
bin beyond two weeks. See `NOTES.md` 2026-08-27.
