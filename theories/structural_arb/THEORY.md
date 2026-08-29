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

**Depth gate (v2, live only).** Fresh quotes prove existence at
top-of-book; they say nothing about size, and both v1 live finds were
real yet died 0.3–0.5 contracts deep (opps 9248, 9309). Live pricing
therefore reads each finalist leg's orderbook (`orderbook_fp`; resting
bids, asks implied from the opposite side), walks all legs' ask ladders
in lockstep while the marginal basket stays riskless
(`scan.implied_ask_ladder`, `scan.fillable_floor`), and records the
fillable basket count and dollar floor profit in the rationale. A find
whose fillable riskless profit is below **$5** records as
`disposition="rejected"` (dust: real, not actionable) — kept, so the
control group settles. An unreadable book (fetch failure, or the
20-fetch budget) leaves the find screened but explicitly marked
`Depth UNVERIFIED` — v1 behavior, never silent.

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
reason. Since v2 the fillable size at riskless prices is measured from
the book and stated in the rationale — but the book moves between the
measurement and the user's order, so the instruction to re-verify every
leg stands.

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

4 — 2026-08-29: **the mutual-exclusivity guard reads the board, not the
network.** `tools` stopped discarding Kalshi's event envelope on every
pull (`09a66f7`), so `mutually_exclusive` is on every market. This theory
had been re-fetching it one event at a time under `MAX_FLAG_FETCHES=150`,
spent on the largest violations first. Removed: the budget, the per-event
fetch, and the write-back.

The point is not that it is cheaper — it is that the guard is now
**complete**. v3 could check the 150 largest of ~1,449 candidates; v4
checks all 1,449, for free. Live: 1,449 candidates, 1,449 rejected as
non-exclusive, 0 network calls.

The flag is tri-state and `None` is not `False`: a pre-2026-08-29
snapshot carries no envelope, and reading absence as False would let a
replay accept a partition it never verified. Unknown falls back to the
2,042 flags already in `theory_facts`, then reports `flag_unknown`.

3 — 2026-08-29: **stage 1 drops three sterile violation classes before
the orderbook fetch.** The snapshot study
(`studies/2026-08-29-structural-arb-violation-liquidity/`) replayed this
theory's geometry over 11 stored boards and found six violations in five
days, **every one of which the v2 depth gate then rejected**. All six fall
into classes the board alone identifies:

| class | screen | study evidence |
|---|---|---|
| untraded strikes | `MIN_LEG_VOLUME = 100` | 3 finds at 0.0–0.1 lifetime volume, each in one snapshot only |
| frozen thin ladders | same | `KXNCAAMBWINS` in 8 of 11 snapshots at unchanged prices, $0.02 fillable |
| long-dated ladders | `MIN_ANNUALISED_RETURN = 0.05` | `USCLIMATE` 2025/2030: liquid (11,596) and persistent, 1.5%/yr over 4.3 years |

The bar these thresholds had to clear, and the test that pins it
(`test_the_one_liquid_short_dated_violation_survives`): they must **not**
remove `KXNASDAQ100MINY` — the single violation in the whole dataset that
was both liquid (3,918 contracts) and attractively priced (36.4%/yr).
That one still reaches the depth gate, which is whose job it is.

This is a reporting and cost change, not an edge change: all six were
already rejected. What it buys is a scan that stops announcing finds it
will always throw away, and stops spending a rate-limited orderbook fetch
per leg to rediscover what `volume` already said. `MIN_LEG_VOLUME` is
explicitly **not** a liquidity proxy for the depth gate — lifetime volume
and fillable size are different questions, which `KXNASDAQ100MINY` proves
by having lots of the first and none of the second.

1 — initial: nested pairs, geometry NO-baskets, flag NO-baskets; 1¢/leg
buffer; 150-fetch flag cap; live re-quote verification. (An earlier
draft of this note said 25-fetch; the shipped constant was 150.)

2 — 2026-08-27: mechanical depth gate in live pricing. Orderbook per
finalist leg, lockstep ladder walk for fillable riskless size, <$5
fillable floor profit records as rejected, unreadable book records as
screened + `Depth UNVERIFIED`. Decision-path change (a find v1 would
have screened can now be rejected), hence the bump. Motivated by opps
9248 and 9309 — the only two live finds v1 produced, both killed by
hand on depth two sessions running. Backtests are unchanged
(existence only; no historical orderbooks exist).
