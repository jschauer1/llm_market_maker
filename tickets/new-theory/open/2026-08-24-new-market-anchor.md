---
title: Newly listed markets open anchored near $0.50 and take days to find fair value (measurement study first)
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: open
---
Effort: S · LLM in decision path: no · Backtest tier: A

**This ticket is the spec.** Before starting, run
`python -m tools.cli ideas search "new-market-anchor"` in case the status
moved, and read [the backlog's shared contracts](../README.md)
first — rules 0 through 0e there have killed more ideas in this
repo than any single spec's own kill criteria have.

## Assessment

**Applicability 3/5 · Implementability 5/5 · Likelihood of success 2/5 ·
Composite 10/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 3:* until the study reports, this produces no bets; if a
  bias is found, early entries apply board-wide.
- *Implementability 5:* nearly free, especially as a listing-age
  dimension on calibration-harvest's cell matrix.
- *Likelihood 2:* cold-start spreads are widest exactly where the bias
  would be harvested, and market-maker quotes may leave no net residue —
  the study is guaranteed information, but the odds it graduates into a
  *tradeable* theory are below even. Priced into the effort score: the
  bet here is an S-effort study, not a theory build.

## 1. Hypothesis

Newly listed markets open anchored (near $0.50, or at a market-maker's
coarse prior) and take days to find fair value. If first-48h prices are
systematically biased vs resolution in a measurable direction (e.g., too
close to $0.50 — real favorites cheap early), buying the eventual
favorite early captures the correction.

## 2. Evidence

The horizon effect: Le 2026 measures the universal compression component
rising from 0.99 at 0–1h to 1.32 beyond a month on Kalshi, and a newly
listed market is by construction at its longest-horizon, most-compressed
moment. Plus cold-start liquidity: nobody has done the work yet, and the
first quotes are a market-maker's guess.

## 3. Non-goals and exclusions

Deliberately staged as *measurement first* — the bias direction is an
empirical question, not an assumption. No screen, no live candidates, no
registry claim of edge until the study reports.

## 4. Decision procedure

Stage 0 study: across all settled markets, compare price at listing+24h
and +48h to resolution, binned by price and category. Only if a stable
bias emerges does this become a theory (screen: markets < 48h old
matching the biased profile; edge from the measured bias;
`edge_basis="measured"`). If no bias: record the negative and close the
registry entry.

## 5. Data requirements

In-repo: settled markets with listing times and candlesticks. Note the
overlap with
[calibration-harvest](../completed/2026-08-24-calibration-harvest.md)'s
1mo+ cells — if that theory is built first, this study is nearly free as
a byproduct: add a listing-age dimension to its cell matrix.

## 6. Backtest design

The study is the tier-A backtest. Split-sample across time like every
measurement in this backlog.

## 7. Kill criteria

Built in — no measured bias, no theory. Cheap either way.

## 8. Implementation plan

`theories/new_market_anchor/study.py` (or a listing-age dimension in
calibration-harvest's `cells.py` — decide at build time and record
which). Effort S. Highest information-per-hour in this backlog after
calibration-harvest.

## 9. Testing approach

Unit tests for listing-age computation from market metadata and bin
assignment; fixture set with a planted early-price bias.

## 10. Open risks

Listing timestamps may be approximate for older markets (first-candle
time proxies listing time); state the proxy and its bias direction.

## 11. Sources

- [Le 2026](https://arxiv.org/pdf/2602.19520) — universal horizon
  compression component.
