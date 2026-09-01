---
title: Every theory here pays the ask, and the measured transfer runs to makers: rest a limit order instead of crossing
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: open
---
Effort: M · LLM in decision path: no · Backtest tier: A (measurement design below)

**This ticket is the spec.** Before starting, run
`python -m tools.cli ideas search "maker-mode-execution"` in case the status
moved, and read [the backlog's shared contracts](../README.md)
first — rules 0 through 0e there have killed more ideas in this
repo than any single spec's own kill criteria have.

## Assessment

**Applicability 5/5 · Implementability 4/5 · Likelihood of success 3/5 ·
Composite 12/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 5:* not a theory but a points-per-trade improvement to
  every maker-eligible theory in the backlog; the user can rest limit
  orders manually on Kalshi today.
- *Implementability 4:* the ledger and report changes are small; the hard
  part is an honest fill simulator (queue position is invisible;
  touch-vs-trade-through matters).
- *Likelihood 3:* the taker→maker transfer is measured (+1.12pp/trade),
  but so is the adverse selection on passive fills (Palumbo's
  "underwriters" finding) — the paired rest-vs-cross backtest genuinely
  could go either way, and either answer is cheap and decisive.

## 1. Hypothesis

Every spec in this backlog prices entries at the ask, paying the spread.
But the measured structural transfer in prediction markets runs from
takers to makers: crossing the spread costs ~1pp per trade on average, and
the maker side collects it. For any candidate whose edge does not depend
on immediacy (most of this backlog — base-rate and calibration edges decay
over days, not minutes), resting a limit order at or inside the bid
captures the maker side of that transfer and adds 1–3 points to every
filled trade. The user can do this manually: Kalshi supports resting limit
orders natively.

## 2. Evidence

- Becker: takers −1.12% mean excess return per trade, makers +1.12% — a
  symmetric, structural, measured transfer.
- Palumbo 2026, "A Microstructure Perspective on Prediction Markets"
  (SSRN, Kalshi NFL trade-level): passive limit-order providers earn
  season-positive P&L (~$29M aggregate) *without* forecasting skill — but
  systematically end up with directional terminal exposure and weekly
  drawdowns; Kalshi LPs are "functionally closer to underwriters than
  market makers." The caveat is the design constraint in section 4: fills
  are adversely selected, so maker mode is only safe where the theory
  already wants the position at that price.
- Whelan: Kalshi taker fees are charged on execution price — a maker fill
  at a better price also pays lower fees, compounding the saving.

## 3. Non-goals and exclusions

- Not a market-making strategy: no two-sided quoting, no inventory
  management, no continuous presence. One-sided resting orders only, on
  candidates a theory already endorsed at the *ask*.
- Not for time-sensitive theories: `settled-but-trading` and any
  news/drift entry must cross — their edge decays faster than a fill
  arrives. Each THEORY.md declares `execution: taker` or
  `execution: maker-eligible`.
- Never violates the ledger contract: `entry_price` remains the executable
  ask at decision time (the comparable number across theories). Maker
  fills are recorded alongside, not instead.

## 4. Design

- **Placement rule (v1, deliberately simple):** for a maker-eligible
  candidate with net edge E at the ask, also compute the edge at the
  current bid + 1¢. Recommend to the user: "cross at `ask` (edge E), or
  rest at `bid+1¢` (edge E + spread − 1¢ if filled)." The theory's
  minimum-edge threshold applies to the *ask* number, so a candidate is
  never recommended that only works if the better fill happens.
- **Adverse-selection guard:** a resting order that fills is more likely
  filled by informed flow (Palumbo's underwriter finding). v1 mitigates
  structurally rather than dynamically: maker mode only on candidates
  whose edge comes from measured base rates (calibration cells, hazard
  bins) where the thesis is "the price is wrong on average," not "I know
  something" — and never within 48h of scheduled resolution-relevant
  events.
- **Ledger extension:** `extra_json` gains
  `{limit_recommended, limit_price, limit_filled, fill_price, fill_time}`
  set via `mark-taken` when the user reports what happened. `roi_taken`
  then reflects real fills automatically.

## 5. Data requirements

None new. Bid/ask from the board and quotes; fee-at-price from
`tools/sizing.py`.

## 6. Measurement design (the tier-A test)

The question is not whether spread capture is worth points (arithmetic)
but whether **fills are adversely selected enough to eat the saving**.
Measure from candlestick history, no LLM:

- For historical candidates of any measured theory (calibration-harvest
  cells work immediately): simulate a resting order at bid+1¢ with a
  time-in-force of H hours; it "fills" when the historical bid path
  crosses it. Compare settled P&L of (always-cross) vs (rest-then-cross-
  at-expiry-if-unfilled) — the honest paired comparison, since unfilled
  orders don't disappear, they get worse prices later.
- Report fill rate, P&L per trade both arms, and the adverse-selection
  gap (P&L of filled maker trades vs the same cells' taker average).

## 7. Kill criteria

If the paired comparison shows rest-then-cross underperforms always-cross
net (fills concentrate in losers badly enough to overwhelm the spread
saving), record that with magnitudes and drop maker mode — the
recommendation format stays taker-only. This is a cheap, decisive test and
should run before any live recommendation carries a limit-price line.

## 8. Implementation plan

1. Measurement script first (theory-local under whichever measured theory
   runs it first, e.g. `theories/calibration_harvest/maker_sim.py`).
2. If it passes: `tools/sizing.py` gains the dual-quote edge computation;
   `find-edge`'s report format gains the two-line entry; `ledger.py`
   `mark-taken` gains the fill fields. Each is a versioned change.

## 9. Testing approach

Unit tests for the fill simulator (bid-path crossing, time-in-force
expiry, the paired-arm accounting) against constructed candle fixtures;
ledger round-trip test for the new fill fields.

## 10. Open risks

- Candlestick granularity limits fill simulation fidelity (a bid that
  touched the limit intra-candle may not show); the simulator should use
  the candle's low-bid conservatively and state the bias direction.
- Queue position is invisible — a touched price does not guarantee a
  fill. The simulator's fill assumption is optimistic; discount fill
  rates accordingly (start: assume fill only if the bid *trades through*
  the limit, not merely touches).
- User workflow friction: two-line recommendations are only useful if the
  user actually rests orders; if `mark-taken` data shows they never do,
  retire the feature regardless of the backtest.

## 11. Sources

- [Becker — Microstructure of Wealth Transfer](https://www.jbecker.dev/research/prediction-market-microstructure)
- [Palumbo 2026 — A Microstructure Perspective on Prediction Markets](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6325658)
- [Whelan — Makers and Takers](https://www.karlwhelan.com/Papers/Kalshi.pdf)
