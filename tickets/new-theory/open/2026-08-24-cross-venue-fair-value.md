---
title: Treat the Polymarket mid as fair value and buy the Kalshi side that converges toward it
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: open
---
Effort: M · LLM in decision path: match-time only (per-trade mechanical) · Backtest tier: A on the mechanical rule; pairs are confirmed facts

**This ticket is the spec.** Before starting, run
`python -m tools.cli ideas search "cross-venue-fair-value"` in case the status
moved, and read [the backlog's shared contracts](../README.md)
first — rules 0 through 0e there have killed more ideas in this
repo than any single spec's own kill criteria have.

## Assessment

**Applicability 3/5 · Implementability 3/5 · Likelihood of success 3/5 ·
Composite 9/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 3:* throughput is bounded by the confirmed-pair
  inventory; when a gap opens it is directly bettable.
- *Implementability 3:* pair store, hand confirmation of the first
  stable, and two-venue data plumbing — moderate, and the pair store is
  reusable infrastructure for two other specs.
- *Likelihood 3:* the gaps are documented and persistent (1–5%), but the
  load-bearing premise — that Polymarket is the *right* side — is
  genuinely uncertain: Clinton & Huang measured Kalshi more accurate in
  2024 politics. The premise test may scope this theory down to
  non-political categories, or kill it.

## 1. Hypothesis

On events listed on both venues, Polymarket is usually deeper and sharper
(larger positions, professional flow, per-wallet accountability). Treat
the Polymarket mid as fair value; when the Kalshi ask is cheap against it
beyond fees plus a divergence threshold, buy the Kalshi side that
converges. A *one-sided* trade — the user can only bet Kalshi — so it
carries event risk, unlike two-leg arb, and needs a bigger threshold than
an arb bot uses.

## 2. Evidence

Persistent 1–5% cross-venue gaps are widely documented, driven by
different user bases, fee structures, and capital frictions. Clinton &
Huang 2025 found prices for identical contracts diverged across exchanges
through the 2024 cycle with arbitrage peaking in the final two weeks —
and found Kalshi more accurate than Polymarket in that sample (78% vs 67%
of markets called correctly), a caution against assuming the direction.
Two-leg arb is competed (public bots); one-sided convergence-taking is a
riskier trade with a wider moat — it requires believing one venue is
*right*, which is testable, not assumed (section 6).

## 3. Non-goals and exclusions

- No two-leg arbitrage (user cannot trade Polymarket).
- No pair trades without a confirmed match on **resolution criteria, not
  topic** — different resolution sources or deadlines make a "same"
  market a different bet.
- Thin Polymarket books are not fair value: PM volume and depth minimums
  are part of the screen, and PM volume must be wash-filtered (see
  section 10).

## 4. Decision procedure

- **Pair store:** `tools/match_market.py` produces candidates;
  confirmation compares resolution criteria. Hand-confirm the first
  stable of pairs (a bad match is the worst failure mode; hand-checking
  doubles as calibration for a later LLM confirmation stage, which would
  record provenance + prompt on disk). Confirmed pairs are static facts
  with stored evidence — match confirmation is *not* in the per-trade
  decision path.
- **Per-trade (mechanical):**
  `edge = |PM_mid − K_ask side-adjusted| − fees − threshold`, PM
  liquidity floor. `edge_basis="model"`.

## 5. Data requirements

In-repo: `tools/polymarket/markets.py` (prices, history),
`tools/kalshi/markets.py`, match_market, pair store in SQLite with
confirmation evidence (who/what confirmed, date, criteria notes). A
resolution-criteria change on either venue invalidates a pair.

## 6. Backtest design

Tier A on the mechanical rule over historical prices of hand-confirmed
pairs. Two measurements, in order:

1. **Premise test:** when the venues disagree, who moves? If Kalshi
   converges to Polymarket more often than the reverse, the fair-value
   premise holds. If not — and Clinton & Huang's accuracy numbers warn it
   may not — kill before betting anything.
2. P&L of the threshold rule net of fees.

## 7. Kill criteria

- Premise test failing.
- Gaps existing mostly on pairs whose resolution criteria differ subtly:
  that is two different bets, not mispricing. If > ~20% of candidate gaps
  are criteria-mismatch on audit, raise the matching bar before running.

## 8. Implementation plan

`theories/cross_venue/{THEORY.md,pairs.py,divergence.py}` + tests. The
pair store is shared infrastructure —
[whale-follow](2026-08-24-whale-follow.md) and
[insider-flow-radar](2026-08-24-insider-flow-radar.md)
reuse it. Effort M.

## 9. Testing approach

Unit tests: divergence arithmetic with side adjustment, threshold logic,
pair-store round-trips and invalidation. Premise-test harness on fixture
price paths with planted convergence direction.

## 10. Open risks

- **Wash trading contaminates PM liquidity screens**: a Columbia study
  estimates ~25% of all-time Polymarket volume is fake (45% in sports).
  The PM depth/volume floor must use wash-filtered figures or holder
  counts, not raw volume.
- Direction may be event-class-dependent (PM sharper on crypto/world,
  Kalshi sharper on US politics per Clinton & Huang) — the premise test
  should report per-category, and the theory may end up scoped to the
  categories where PM wins.
- Pair inventory is small at any moment; throughput-bound.

## 11. Sources

- [Why the same market prices differently](https://www.predictionhunt.com/blog/why-same-market-different-prices-kalshi-polymarket)
- [How PM/Kalshi arbitrage works](https://www.trevorlasn.com/blog/how-prediction-market-polymarket-kalshi-arbitrage-works) · [public arb bot](https://github.com/ImMike/polymarket-arbitrage)
- [Clinton & Huang 2025](https://ideas.repec.org/p/osf/socarx/d5yx2_v1.html) — cross-exchange divergence and the per-venue accuracy caution.
