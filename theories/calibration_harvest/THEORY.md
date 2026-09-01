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

`under_review` — 2026-09-01. **The pre-registered kill criterion is met
and retirement is proposed for the user's ruling.**

Third population complete (`backtest-2026-09-01-calharvest-econfin`,
1,181/1,181 series, 2,666 observations, five mapped domains). It is
genuinely out of sample — the grid was drawn on weather and politics.
**27 cells clear both floors; zero clear fees**, with net edge at the v4
bound running −6.57 to −25.29. The falsification condition below, fixed
before the data existed, is satisfied.

The test is fair, which took the whole 2026-09-01 session to arrange:
until v4 the pricing rule was *arithmetically incapable* of firing, so a
theory with no edge and a theory that could not express one produced
identical empty reports. v4 removed that excuse on a structural argument,
demonstrably without changing anything bettable — and the fresh
population still came back empty.

Across all six walked domains: **0 of 20 measured domain-band cells shows
a bettable effect; 8 exclude one; 12 are underpowered.** **0 of 27
econfin cells survives Holm.** The horizon axis — the only axis that ever
showed structure — **reverses sign out of sample** (`1mo+` +9.38 on
weather+politics, **−5.09** on econfin), so the horizon claim is dead
rather than merely unproven. The liquidity split, newly capturable this
session, shows no ordering in either direction.

Not proof of absence: sci_tech is thin, 12 cells are underpowered, and
Sports (3,274 series) and Entertainment (598) are unwalked. If one more
walk is wanted before ruling, **Sports is the right one** — it is the
largest population on Kalshi and the forward corpus turns out to be
dominated by it. Full numbers: `NOTES.md` 2026-09-01 (later still).

Status is `under_review`, not paused: it keeps running and recording,
because pulling a theory you suspect is broken guarantees you never find
out whether it was broken or unlucky.

### History

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

**Strengthened 2026-09-01: in weather a bettable price effect is now
*excluded*, not merely absent.** Day-clustered 95% intervals on the gross
edge, per band, against the gross edge v4 would need to fire at that ask
(the frontier in Version 4): `0.65-0.75` +0.45 [−3.05, +3.94] vs +7.9;
`0.75-0.85` −1.42 [−5.25, +2.41] vs +6.9; `0.85-0.92` +1.29 [−1.20,
+3.78] vs +5.5; `0.92-0.97` −0.88 [−2.55, +0.78] vs +3.5. Every upper
bound sits below its threshold, on 3,267 rows over 59 settlement days.
This is the cleanest negative result the theory owns.

**Politics, by contrast, is underpowered at the band level rather than
null** — its intervals run ±8–12 points because 45–57 settlement days
carry only 229–618 rows, and the two lower bands cannot exclude a
bettable effect. "Politics shows nothing" would overstate it. Pooling the
two domains to narrow the intervals is *not* available: the thesis says
their signs are opposite, so pooling measures what it claims cancels.
See `NOTES.md` 2026-09-01 for the full table and for the pooled version
of it, which is wrong and is kept as a warning.

**The claim that population could not test.** Every longer-horizon
weather cell has n ≤ 8: weather markets list and settle within days, so
`2d-1w`, `1w-1mo` and `1mo+` are structurally empty there. The thesis is
about horizon compression, so the weather walk tested one column of a
four-column claim.

**Politics/Elections completed the same day (2,507/2,507 series, 1,541
observations, 916 markets) and it does test the claim. The
pre-registered test FAILED.**

The bar fixed before the data landed (`4a01f9a`) required the horizon
ordering `1mo+` > `1w-1mo` > `2d-1w` > `<=2d`. Observed, day-clustered
with price bands pooled: **−1.21 → −4.26 → +5.05 → +9.38** — violated at
the first step.

An earlier version of this section reported a two-group long-vs-short
contrast (+7.68, t 3.50) as though it had been pre-registered. **It had
not been**; it was chosen after seeing where the sign flipped, and it was
the best of the three available split points (+0.11, +3.50, +2.23). That
claim is **retracted**. See `NOTES.md` 2026-08-29 (correction) for the
full account, and
`studies/2026-08-29-calibration-harvest-gradient-review/` for the peer
review that caught it.

**What actually stands** is narrower. Decomposed into adjacent paired
steps, the data is flat, one jump, flat:

| step | mean | SE | t |
|---|---|---|---|
| `2d-1w` − `<=2d` | −2.19 | 2.45 | −0.90 |
| `1w-1mo` − `2d-1w` | **+7.01** | 2.36 | **+2.96** |
| `1mo+` − `1w-1mo` | +0.06 | 3.03 | +0.02 |

That is **a single level shift at the one-week boundary, not a slope** —
and Le 2026's prediction is of continuously growing calibration slopes,
which a lone discontinuity does not corroborate. About **38% of the step
is composition**: restricted to the 95 series present on both sides it
falls from +9.31 to **+5.75**, because the series mix differs materially
across the boundary. Whether the remainder is a horizon effect at all
needs a within-series estimator.

**Treat it as a hypothesis for the next population, not a result.**

**Nothing is recommendable, and that part is unchanged.** All sixteen
cells are net-negative at the Wilson bound (−5.68 to −29.92 pts), because
bounding on `n_days` of 16–47 gives an interval far wider than any effect
seen here. The effect being real and the effect being bettable are
different questions, and what would close the gap is more settlement
days, not more rows.

Full numbers and reproduction: `NOTES.md` 2026-08-29, and
`python -m theories.calibration_harvest.gradient`.

The original `proposed` bar, now met, was: `collect.py` has completed its
first pre-registered population and `cells.py` has at least one cell at
n ≥ 30 with full coverage of that population.

It does not become `active` until a cell shows positive *net* calibration
edge out-of-sample, at n ≥ 30 **and** n_days ≥ 8 (see the day-clustering
rule below).

## Version

4 — 2026-09-01: **the bound was a design effect pinned at rho = 1, and at
that value the pricing rule could not fire at the theory's own gate.**

`cell_edge` bounded on the settlement-day count. That is not a neutral
choice of estimator — it is the standard design-effect correction
`n_eff = n / (1 + (mbar - 1) * rho)` evaluated at **rho = 1**, total
within-day dependence. v2 adopted it deliberately and hedged correctly at
the time: "a proper cluster-robust interval would sit somewhere between
`n_days` and `n`."

**Measured, it does.** ANOVA intracluster correlation over the 20 cells of
both complete populations clearing n>=30 and n_days>=8: median **0.027**,
mean 0.067, max 0.315. Weather cells (mbar 12–16) measure rho ≈ 0 — their
same-day rows are fourteen different cities, close to independent draws —
while politics cells (mbar 2.6–5.3) run higher, which is the right
direction, since same-day politics markets often share an underlying
event. The clustering is real; assuming it was *total* is what was wrong.

**What rho = 1 cost: feasibility.** The minimum settlement-day count at
which any positive edge was arithmetically possible, at *any* realized
rate — ask 0.70 → 10 days, 0.80 → 17, 0.88 → 31, 0.92 → 48, 0.95 → **79**.
`MIN_CELL_DAYS` is **8**, so the gate awarded the `measured` label — the
label that authorizes a bet — to cells the pricing rule provably could not
emit on. And Kalshi's reachable history is **58 days**, so the 0.92–0.97
band, the band this theory's own thesis says is richest, could never fire
from a tier-A backtest at all. Every "0 cells recommendable" result this
theory has produced is partly this, and none of it was about the data.

The change: `effective_n(n, n_days)` applies the design effect with one
pooled `CLUSTER_RHO = 0.2326` — the **90th percentile** of the measured
cells, ~3.5x the mean, deliberately pessimistic and deliberately a single
number, because a per-cell rho is a free parameter per cell. `n_eff` is
clamped to `[1, n]`. `MIN_CELL_N` and `MIN_CELL_DAYS` are untouched, and
rho = 1 still reproduces v3 exactly while rho = 0 reproduces v1 — both
pinned by tests.

**Evidence: `continues`.** No grid boundary, bin, floor or screen
threshold moved, and both tier-A collection runs measured exactly the
cells v4 prices against. What changed is how a cell's interval is
computed, not which cells exist or what was observed.

**It changes nothing bettable, and that is the integrity check.** Across
all 20 measured cells: day-Wilson fires 0, DEFF-Wilson fires **1**,
row-Wilson fires 2. The one cell is `politics|1mo+|0.75-0.85` at +1.25
net — **in-sample**, n=50 (the thinnest long-horizon cell), 1 of 20
comparisons, and part of the horizon claim **retracted on 2026-08-29**.
It is recorded as not a result and must not be bet. A fix motivated by
making history look good would have made history look good.

What v4 buys is the frontier: required true gross edge at the 58-day
ceiling falls from +14.5/+11.4/+10.3/impossible (asks 0.70/0.80/0.88/0.95)
to **+7.9/+6.9/+5.5/+3.5** — from "larger than anything in the
literature" to "the size the literature reports". Full derivation,
tables and the pre-registered bar for confirming v4: `NOTES.md`
2026-09-01 (later).

3 — 2026-09-01: **one run per floor, against a complete category map — and
`other` no longer means two different things.**

The domain axis had been collapsing silently since the theory started
recording live rows. `categories` is only a label map for
`cells.cell_key`; `screen()` has no population filter and always walked
the whole board. The RUNBOOK nevertheless said the live screen ran twice
per floor, "once per complete population, with distinct run ids so
same-day attempts never double-count a market", with a weather-only map
and a politics-only map. Both runs therefore screened everything, and each
labelled the other's population `other`.

Measured on the 2026-09-01 board: **9,247 attempts per run, 100% overlap,
6,944 with an identical cell key.** The `other|*` cells — which held
nearly all the data — got the same market twice from one board *and* a
blend of every domain the theory exists to separate. Politics is claimed
compressed toward 50% and weather has the opposite sign inside 12h, so
pooling them measures exactly what the hypothesis says cancels.

Two changes, both to the decision path:

- **The map is complete.** `collect.all_series_categories()` returns all
  13,687 series in a single `/series` fetch with no cursor, so a market's
  cell follows its true Kalshi category. On the 2026-09-01 board that is
  9,220 survivors across **11 real domains**, with `other` falling from
  9,123 (99.4%) to **102 (1.1%)**. `target_series` is not reused for this:
  it filters to the categories being *collected* and drops anything
  untouched in 58 days, which is right for a settled-history walk and is
  precisely what stripped the domains here.
- **`unmapped` is split from `other`.** `other` now means only "a real
  Kalshi category the grid does not bin" — Commodities, Social,
  Transportation, Exotics, Education. A series the run's map never covered
  is `unmapped`, a defect in the run rather than a fact about the market.
  Conflated, a partial map was indistinguishable from a legitimate
  residual; split, it produces a conspicuous `unmapped|*` cell. `screen()`
  also reports `uncategorized` in its funnel, which is 0 on a correct run.

**Evidence: `continues`.** No grid boundary, bin, floor, Wilson bound or
screen threshold moved, so both tier-A collection runs measured exactly
the cells v3 prices against and stand unchanged — they walked their own
categories with correct labels throughout. The defective *live* rows are
quarantined on their own merits rather than by the bump, because `other`
changed meaning and every row already written was recorded under the old
one: `other|*` below v3 is excluded by
`forward_cells.OTHER_QUARANTINED_BELOW_VERSION`, and the exact-duplicate
run `live-2026-08-29-calharvest-v2` by `EXCLUDED_RUNS`. The quarantine is
per **cell**, so the clean `weather|*` and `politics|*` rows from those
same runs keep counting; what survives is one correctly labelled row per
market per day.

Nothing was measurable when this landed (0 of 21 cells cleared both
floors, the best at 4 settlement days against a bar of 8), so the
quarantine costs no conclusion — it prevents one.

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
5. **Edge.** `edge = wilson_lower(cell, n_eff) − ask − fees`, where
   `n_eff` discounts the cell's rows for within-day dependence by a
   measured design effect (v4; `cells.effective_n`). `edge_basis =
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
