# Structural Arb

## Hypothesis

Within a single Kalshi event, executable quotes must satisfy hard logical
constraints: a strike ladder must be monotone (YES "above 50k" cannot cost
less than a bid on YES "above 60k"), and a set of mutually exclusive
outcomes can produce at most one YES, so NO contracts across k of them
must together be worth at least k−1. When top-of-book asks violate a
constraint by more than fees, buying the violating combination is
guaranteed profit — no forecast involved.

Why it persists: retail flow hits individual strikes without repricing
siblings, and Kalshi has no cross-contract margining forcing consistency.
Public arb bots compress the lifetime of violations, which caps the firing
rate, not the validity — the scanner costs nothing per session and only
needs a violation to exist at the moment it looks.

Full design rationale: `docs/superpowers/specs/theories/
2026-08-24-theory-structural-arb-design.md` (registry idea
`structural-arb`).

## Decision procedure (fully mechanical, edge_basis="model")

Group the session board's open markets by `event_ticker` (≥2 siblings).
Three proofs, all in `scan.py`, all conservative — a proof that cannot be
completed is a non-finding:

1. **Nested pair.** Scalar strikes (`greater[_or_equal]`,
   `less[_or_equal]`, `between` via `floor_strike`/`cap_strike`) become
   YES-intervals. If A's interval provably contains B's, buy YES(A) at
   ask + NO(B) at ask: pays 1 always, 2 when the outcome falls in A∖B.
   Fires when cost + fees + buffer < 1. `min_payout=1, max_payout=2`.
2. **NO basket, geometry-proved.** Over pairwise provably-disjoint
   intervals in one event, at most one YES is possible, so NO on all k
   pays ≥ k−1. Optimal subset by weighted-interval-scheduling DP on
   per-leg saving `1 − no_ask − fee`. Fires when
   Σ(no_ask) + fees + buffer < k−1. `min_payout=k−1, max_payout=k`.
3. **NO basket, flag-proved.** Same arithmetic over events (typically
   categorical, `strike_type=structured/custom`) whose envelope declares
   `mutually_exclusive: true` — never assumed, because non-ME events
   routinely sum YES prices above $1 legitimately. Flags are stable
   structural facts, so each is fetched once ever: `theory_facts`
   (kind=`event_me_flag`) first, network on a miss with a 150-fetch
   budget per screen spent on the largest violations first; capped-out
   candidates are counted in the funnel. A provable interior overlap
   between two same-underlying scalar legs contradicts the flag and
   voids the event.

Two proofs-of-nothing the first live board forced, both load-bearing:

- **One event is not one underlying.** KXMLBHIT-\<game\> holds a hits
  ladder per player; KXNCAAFTEAMTOTAL-\<game\> a points ladder per
  team. Interval proofs run only within an *underlying group*: ticker's
  last segment must be a pure strike token (`[TB]?-?digits[.digits]`)
  AND titles must match after masking digit runs. A false split loses a
  candidate; a false merge loses money.
- **Strike metadata can contradict itself.** KXSTARSHIPSPACE-26-8.0
  declares `strike_type=less` with `floor=cap=8` while meaning
  "exactly 8". A one-sided type carrying both bounds is refused
  outright.

Boundary honesty: `between`'s open/closed convention is not published per
market, so proofs touching a `between` endpoint require strict
inequality. **YES-side basket sums are deliberately absent in v1**: their
floor needs exhaustiveness ("at least one YES"), which neither the flag
("at most one") nor strike endpoints can prove.

Buffer: 1¢ per leg beyond fees (spec). Fees: unrounded per-contract
`0.07·P·(1−P)` capped at $0.035 (`tools/sizing.fee_pts`); an actual order
rounds up to the cent, which amortizes at size — the rationale says so.

Live runs re-quote every leg of every finding (`markets.quotes`) and
re-run the scan on fresh asks before anything is recorded; the board can
be tens of minutes old and this theory's false positives cost real money.
Backtest runs never re-quote — they price the snapshot.

Every find is recorded with `ledger.record_basket` (one position, joint
payoff), `disposition="screened"` (nothing to interpret),
`edge_basis="model"`. Because cost + fees ≤ `min_payout`, scoring routes
every row to the riskless bucket: `riskless_n`/`riskless_roi`, never
calibration. `edge_pts_net` is the guaranteed return on cost in points.

## Stage 2 — none

Fully deterministic; no gate, no judgment, no prompts. Tier A by
construction.

## Execution risk (reported, never modelled)

A basket is riskless only if **all** legs fill at the recorded asks.
Every report tells the user to verify each leg before entering any;
single-leg-pair findings rank above wide baskets at equal edge for this
reason. Depth beyond top-of-book is not checked (the board carries no
book depth) — small size only until verified on the book.

## Data sources

The session board (`tools/board.py`) only, plus per-finalist event
envelopes and per-finding fresh quotes from Kalshi's public API. No
Polymarket, no models.

## How to backtest

Tier A. Replay stored board snapshots (`tools/snapshot.py` keeps complete
raw payloads): rebuild each snapshot's board, run this same `screen()`
with `run_mode="backtest"` (same functions as live — a reimplemented
screen backtests nothing), record findings under a `backtest-*` run_id.
Known bias, stated per the spec: snapshots are point-in-time, so the
replay measures violation **existence**, not persistence or fillability —
no fill certainty is claimed.

## Kill criteria

The arithmetic cannot be wrong, only idle. If it fires zero times in 60
days of sessions, record that in NOTES.md and leave it running — it costs
nothing. The falsifiable part is the riskless claim itself: any settled
basket paying below its declared `min_payout` is a proof error and
`score.py` raises loudly on it; one such event sends the theory
`under_review` immediately.

## Status

`testing` — 2026-08-26: procedure implemented and running; first live
scan this session. (`proposed` skipped-through the same day the scaffold
ran end to end.)

## Version

1 — initial: nested pairs, geometry NO-baskets, flag NO-baskets; 1¢/leg
buffer; 25-fetch flag cap; live re-quote verification.
