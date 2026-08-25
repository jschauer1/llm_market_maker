# new-market-anchor — issuance mispricing in the first 48 hours

**Priority:** 11 of 12 · **Effort:** S (study) · **LLM in decision path:**
no · **Backtest tier:** A

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search
> "new-market-anchor"` for status changes since this was written. Formalize
> via the `propose-theory` skill only if the study finds a bias.

## Thesis

Newly listed markets open anchored (near $0.50, or at a market-maker's
coarse prior) and take days to find fair value. If first-48h prices are
systematically biased vs resolution in a measurable direction (e.g., too
close to $0.50 — real favorites are cheap early), buying the eventual
favorite early captures the correction.

## Why the edge should exist

The horizon effect — Le 2026 measures the universal compression component
rising from 0.99 at 0–1h to 1.32 beyond a month on Kalshi, and a newly
listed market is by construction at its longest-horizon, most-compressed
moment — plus cold-start liquidity: nobody has done the work yet, and the
first quotes are a market-maker's guess. This idea is deliberately staged as
*measurement first*: the bias direction is an empirical question, not an
assumption (note the overlap with
[calibration-harvest](calibration-harvest.md)'s 1mo+ cells; if that theory
is built first, this study is nearly free as a byproduct — just add a
listing-age dimension to its cell matrix).

## Procedure

Stage 0 is a study, not a theory: across all settled markets, compare price
at listing+24h/+48h to resolution, binned by price and category. Only if a
stable bias emerges does this become a theory (screen: markets < 48h old
matching the biased profile; edge from the measured bias;
`edge_basis="measured"`). If no bias, record the negative and close.

## Backtest

The study is the tier-A backtest.

## Kill criteria

Built in — no measured bias, no theory. Cheap either way.

## Build notes

Start as a script in `theories/new_market_anchor/study.py`. Effort S for the
study. Highest information-per-hour in this backlog after
calibration-harvest, because the repo already has all the data it needs.

## Sources

- [Le 2026 — Domain-Specific Calibration Dynamics](https://arxiv.org/pdf/2602.19520) (read in full) — the universal horizon compression component.
