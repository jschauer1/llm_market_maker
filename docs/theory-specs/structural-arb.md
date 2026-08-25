# structural-arb — monotonicity and basket-sum violations

**Priority:** 3 of 12 · **Effort:** S · **LLM in decision path:** no ·
**Backtest tier:** A

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search "structural-arb"`
> for status changes since this was written. Formalize via the
> `propose-theory` skill before writing procedure code.

## Thesis

Within a single event, prices must satisfy hard logical constraints: a
strike ladder must be monotone (P(above 50k) ≥ P(above 60k)), and a
mutually-exclusive-exhaustive outcome set must have YES prices summing to
≥ $1 at the bid and ≤ $1 + spread at the ask. When executable quotes violate
a constraint by more than fees, the trade is close to risk-free.

## Why the edge should exist

Retail flow hits individual strikes without repricing siblings, and Kalshi
has no cross-contract margining to force consistency. Public cross-platform
arb bots exist (several on GitHub), which caps how long violations last —
but a scanner that runs every session costs nearly nothing, and the user
only needs the violation to exist at the moment they look. Expected firing
rate: low. Expected edge when it fires: real.

## Procedure

Fully mechanical. From the board, group markets by `event_ticker`; for
ladders (detect strike-ordered siblings from ticker structure), check
ask-side monotonicity violations net of fees; for mutually-exclusive events,
check `sum(YES asks) < 1 − fees` (buy the basket) and
`sum(NO asks) < (k−1) − fees`. Require a buffer (start: 1¢ per leg) and
top-of-book size on every leg. `edge_basis="model"` — the edge is
arithmetic. One caveat to encode: confirm from the event metadata that the
outcome set is actually exhaustive (some Kalshi events have an implicit
"none of the above" that never trades); non-exhaustive sets only support the
monotonicity check, not basket sums.

## Backtest

Tier A against snapshot history: replay stored board snapshots
(`tools/snapshot.py` keeps complete raw payloads) and count violations that
were executable net of fees. Note the honesty constraint: snapshots are
point-in-time, so the backtest measures *existence*, not persistence — say
so in THEORY.md rather than claiming fill certainty.

## Kill criteria

Not applicable in the usual sense — the theory can't be wrong, only idle. If
it fires zero times in 60 days of sessions, record that and leave it
running; it costs nothing.

## Build notes

`theories/structural_arb/{THEORY.md,scan.py}` plus tests with constructed
violation fixtures. Effort S. This is also the natural home for a shared
"group siblings by event" helper that [smile-smoothing](smile-smoothing.md)
will want later — build it in the theory first per the repo's promotion
rule.

## Sources

- [Public PM/Kalshi arb bot](https://github.com/ImMike/polymarket-arbitrage) — evidence the hard-arb space is watched; within-Kalshi single-event consistency is the less-competed corner.
- [How prediction-market arbitrage works](https://www.trevorlasn.com/blog/how-prediction-market-polymarket-kalshi-arbitrage-works)
