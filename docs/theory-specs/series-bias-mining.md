# series-bias-mining — a machine for finding more mention_families

**Priority:** 4 of 12 · **Effort:** M · **LLM in decision path:** no ·
**Backtest tier:** A

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search
> "series-bias-mining"` for status changes since this was written. Formalize
> via the `propose-theory` skill before writing procedure code.

## Thesis

`mention_family` was found by accident: a backtest slice showed one
recurring series family with a persistent, exploitable bias. There is no
reason it is the only one. Mine *every* recurring series with enough settled
history for persistent price-vs-outcome bias, and promote the survivors into
their own bucketed sub-theories.

## Why the edge should exist

Recurring series (daily/weekly weather, econ prints, pop-culture
recurrences) are traded by habitual retail flow with stable behavioral
biases, and each series has its own resolution quirks that casual traders
misprice consistently. The domain-specificity finding (Le 2026: political
markets compressed, short-horizon weather too extreme, Fed/rates markets
near-perfectly calibrated in the macro-markets literature) says bias lives
at the *family* level, not the board level — which is exactly what a
per-series miner exploits and a board-wide average washes out.

## Procedure

Fully mechanical, and mostly a *measurement pipeline* rather than a screen:

- For every series with ≥ 30 settled markets in history: at fixed decision
  points (7d, 3d, 1d before close), record (price, outcome) pairs from
  candlesticks; compute realized rate vs mean price per price bin; flag
  series where the gap clears fees with a Wilson interval excluding zero.
- Guard against multiple comparisons — this is the idea's central
  statistical risk. With hundreds of series, dozens will look biased by
  chance. Require: bias present in the first half of the series' history AND
  the second half, same sign, before flagging.
- Output: a ranked list of candidate families, each with its measured bin
  table. Each survivor becomes a small bucketed theory (or a new bucket
  under a shared umbrella theory — decide in THEORY.md; separate theories
  keep track records clean and is the safer default).

## Backtest

The miner *is* a tier-A backtest. The live theory that follows each
discovered family inherits the family's measured rates as
`edge_basis="measured"` only for the exact bins the split-sample test
validated.

## Kill criteria

If nothing survives the split-sample test, the board's recurring series are
calibrated — a valuable negative result; record it. If survivors appear but
their live settlements regress hard (measured rate minus live rate > 10
points at n ≥ 20), the miner is overfitting; tighten the split test before
mining again.

## Build notes

`theories/series_miner/{THEORY.md,mine.py}` plus tests. Effort M — the work
is careful statistics, not plumbing. The candlestick fetch loop over
hundreds of series should batch and cache aggressively
(`tools/kalshi/history.py`); ~12 months is the available depth.

## Sources

- [Le 2026 — Domain-Specific Calibration Dynamics](https://arxiv.org/pdf/2602.19520) (read in full) — bias is domain/family-conditional, not uniform.
- The repo's own mention_family history (RESEARCH_LOG.md, 2026-08-24 entries) — the existence proof this miner generalizes.
