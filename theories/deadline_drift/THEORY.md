# Deadline Drift

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
in the decision path; `edge_basis="model"`; tier A.

1. **Population** (`screen.py`): allowlist series families, by-deadline
   phrasing, minus the structural guard — Kalshi's `mutually_exclusive`
   flag, and events priced as a partition (>=3 siblings sharing one
   deadline summing $0.90–1.05). **981 markets in 70 series** on the
   2026-08-29 board.
2. **Candidates**: open, days-to-close <= 21, YES ask in $0.05–0.60, NO ask
   available, volume >= 100.
3. **Edge**: `(1 - P(YES | price bin, days bin)) - no_ask - fees`, with the
   probability from hazard bins over settled allowlist history.

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

`proposed` — 2026-08-29. The screen runs and reproduces the audited
population exactly, but **the hazard bins that define the edge have never
been collected**, so `price()` returns nothing rather than inventing a
prior. Collecting them is the only step between here and `testing`.

To reach `testing`: bins collected, screen recording opportunities.
To reach `active`: a tier A backtest with positive `calibration_edge_net`.
To `under_review`: n=20 with `calibration_edge_net` <= 0.

## Candidate flow

The population is long-dated by nature, so a snapshot understates it: **41**
markets sit inside the <=21-day window today, but **714 close over the next
12 months**, each passing through that window once. Live scans surface a
handful at a time; the backtest population is the annual flow.

## Version

**v1** (2026-08-29) — initial. Allowlist screen + structural guard, hazard
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
`studies/2026-08-29-structural-gate-payload-version/`.
