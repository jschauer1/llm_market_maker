# Deadline Drift

<!-- research-memory-route -->
> [Find scoped lessons and avoided mistakes](learnings/README.md). Read this specification
> for the claim/procedure relevant to your task; historical learning narratives
> are source evidence, not an accumulating current-memory summary.
<!-- /research-memory-route -->


## Hypothesis

Markets that resolve YES only if a discrete, **unscheduled affirmative
event** occurs by a deadline — charged before D, pardoned before D, traded
before D, manager out before D, IPO confirmed before D — systematically
overprice YES as the deadline approaches with no event. Buy NO in the late
window when the implied hazard exceeds the historical hazard by more than
fees.

**The mistake, and why it persists.** Three mechanisms, two documented:

- **Longshot bias.** Late-window YES on a quiet market *is* a longshot, and
  longshots are overpriced.
- **Capital asymmetry** (Berg, Nelson & Rietz, 500k+ Intrade transactions):
  high-likelihood events underpriced and low-likelihood events overpriced
  specifically at long horizon. NO on a $0.90 favorite locks ~$0.90 to win
  ~$0.10 — a 9:1 capital commitment for a thin return. Unattractive to
  retail, capital-inefficient for professionals, so the correction is slow.
  **This is the answer to "why isn't it arbitraged away": the trade is
  unpleasant, not unavailable.**
- **Anchoring.** The story that made the market interesting keeps the price
  sticky as the clock runs out.

## What would falsify it

Stated before any bin is collected, per the spec's section 7:

- **Implied and empirical hazard agree within fees across all bins.** The
  market prices decay correctly; the theory is dead. Primary kill criterion,
  and the bins measure it directly.
- Positive gross edge that fees consume entirely — NO at $0.40–0.95 locks
  near-full collateral per point of profit, so this is a live risk and must
  be reported as `edge_pts_net`, never gross.
- The effect exists only where liquidity is worst, i.e. it is a spread
  artifact rather than a hazard mispricing.

## Data sources

In-repo only, Kalshi-native — no cross-platform matching needed. Board and
rules text, candlesticks for point-in-time replay, fee math.

## Decision procedure

**Stage 1 only. There is no stage 2 and none is planned.** No LLM anywhere
in the decision path; tier A.

**v2 (2026-09-01) ships DD-1's population.** v1's allowlist is described
below under "Why an allowlist rather than a board-wide screen" and is no
longer what the screen selects; `screen.in_allowlist` survives as a
recorded feature, not a filter.

1. **Population** (`screen.wide_population`): by-deadline phrasing, rules
   stratum `hazard` (i.e. not `threshold`, `scheduled` or
   `multi_destination` — `hazard.stratum`), minus partitions. The
   partition exclusion is one exclusion applied with the three
   instruments each population affords: the **series** set
   `hazard.partition_families` returned over settled history (persisted
   by `population.py`, since that function reads settlements and cannot
   screen a live board), Kalshi's `mutually_exclusive` envelope flag, and
   the price-partition test (>=3 siblings sharing one deadline summing
   $0.90–1.05). **4,404 markets** on the 2026-09-01 board, against 981 in
   70 series for v1.
2. **Candidates**: open, **days to the deadline stated in the rules** <= 21
   (never `close_time` — see correction 1), YES ask in $0.05–0.60, NO ask
   available, volume >= 100. Entry is the **first** qualifying day, which
   the ledger's dedup key enforces by preserving `entry_price` and
   `first_seen_at` from the first sighting.
3. **Edge**: `(1 - P(YES | price bin, days bin)) - no_ask - fees`, with the
   probability from hazard bins over settled history. **`hazard_bins.json`
   does not exist and must not be written until DD-1 clears**, so
   `price()` instead emits **observation rows** — claimed edge 0,
   `disposition='screened'`, a rationale saying outright that they are not
   recommendations — under the 2026-08-30 ruling. Zero is load-bearing:
   `ranked_edge = edge_pts_net × credibility`, so no row this theory
   currently produces can promote to a bet.

**Recorded per row, never filtered on** (`screen.features`): `recurring`
and `settled_events` (DD-2's split), `branch_family`, `in_allowlist`,
`event_legs` and `event_ask_sum` (the fixed-k elimination shape),
`open_interest` (kill criterion 3, which the ledger has no column for and
which cannot be recovered after the fact), and `yes_bid_implied` — which
is `1 - no_ask`, the side a NO buyer actually bets against, never the
field named `yes_ask`.

**`no_ask` is `1 - yes_bid`, and that is not a detail.** The step above
was always written correctly; the *measurement* script was not, and
priced the trade off `yes_ask` from 2026-08-29 until 2026-09-01. That
credits the strategy with the whole bid-ask spread, which on this
population runs a 4-point median and a 6-point mean — enough to roughly
double the apparent edge (wide stratum: +10.1 off the ask, +4.6 off the
bid). Anything measuring this theory reconstructs prices from raw
candles, which steps outside the `Market`/`no_ask` types that enforce the
convention everywhere else in the repo. Use `hazard.observe(side="bid")`.

### Why an allowlist rather than a board-wide rules-text screen

Five audit rounds established that a *board-wide* mechanical screen cannot
reach the spec's 10% misclassification bar. Rounds 1–4 tuned regex to a
plateau near 15%; round 5 added Kalshi's exclusivity flag and a
price-partition test and returned **12%** — not distinguishable from round 4
at n=50. The residue is multi-destination "which branch" markets, which are
semantic, and **both structural signals are blind on exactly that residue**
(all six round-5 misses carry `mutually_exclusive=False`).

Round 5b audited the allowlist **exhaustively** — a series-level construct,
so all 70 series were inspected with *no sampling error* — and found
**70/70** genuinely per-subject: every sibling is a different subject, never
a branch of one outcome. 0 carry `mutually_exclusive=True`; 0 are priced as
partitions.

The structural guard is kept on top of the family rule because it is what
removes `KXUKCABOUT` — "who is **next** to leave the Burnham Cabinet", 23
markets, a pure partition the suffix rule would otherwise admit.

## Status

`testing`, v2. The live procedure records zero-edge observation rows while
DD-1 accrues; until `hazard_bins.json` is deliberately created after DD-1
clears, this theory cannot produce a recommendation. The current registry,
code, and runbook all use v2.

The evidence questions remain separate:

- **DD-1** is the primary forward test on markets settling after 2026-09-01.
  Its current record comes only from the score report.
- **`dd2-one-off`** is a registered sub-theory of DD-1. It remains
  first-class and accrues on its own record; use the slice report for its
  current gates.
- **DD-3** is the selection-correction replication. The open
  [stopping-rule ticket](tickets/open/2026-09-03-dd3-final-read-at-80-clusters.md)
  permits exactly one further reading, at the first completed sweep that
  reaches the floor.
- **DD-4** completed below its floor and is not rerun. **DD-5** cannot be
  identified as specified because the unseen arm is almost necessarily
  one-off; it is not a second route to a recommendation.

The completed sweep did establish a material board-selection effect, so the
earlier positive in-sample headline is withdrawn and must not be cited as this
theory's edge. The full measurements and reasoning are preserved in the
[historical notebook](theories/deadline_drift/notes/archive/NOTES.md) under
the 2026-09-03 sweep entry. They do not contaminate DD-1's forward set.

There is no eligible replay shortcut for DD-1 from the already captured
history: that history was used to select its population. Tier A/B replays
normally count in full, but recording this same analysis as a backtest would
let the discovery sample validate its own rule. Use
`python -m tools.cli score report deadline_drift` and
`python -m tools.cli slices report deadline_drift` for current evidence.

## Candidate flow

The population is long-dated by nature, so one board snapshot understates
its flow: markets enter the <=21-day window over time. Report each run's
actual funnel from `ScreenResult`; the historical annual-flow estimate is
preserved in `theories/deadline_drift/notes/archive/NOTES.md`.

## Version

**v2** (2026-09-01, `continues`) — moved the shipped population from the
70-series allowlist to DD-1's pre-registered by-deadline hazard stratum minus
partition families, and anchored the live horizon to the deadline stated in
the rules rather than `close_time`. v1 recorded no rows, so the continuing
chain pools no stale observations.

**v1** (2026-08-29) — initial. Allowlist screen plus structural guard; hazard
bins pending.

## Known defects carried forward

The price-partition test here has a **two-sided** band ($0.90–1.05). Round
5's frozen classifier had no lower bound, and session 09 found 281 of its
318 exclusions were spurious — `KXCOACHOUTNFL` is 22 *independent* coach
hazards summing 0.13. That classifier is deliberately left unpatched
(freezing it before the sample was drawn is what made round 5
out-of-sample); the fix lives here instead.

When the backtest is built it must construct the screen payload from the
`market_snapshots` capture at or before the decision point, never a current
fetch: `rules_primary` changes substantively on live markets, and a moved
strike does not merely misjudge one market — it reassigns it to a different
stochastic process and poisons a whole bin. See
`docs/2026-08-29-structural-gate-payload-version/`.
