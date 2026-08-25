# Reading notes — Angelini & De Angelis 2026, "When Do Markets Fully Process Public Information? Evidence from Real-Time Prediction Markets"

Source: arXiv:2606.07811 **v1, 5 Jun 2026** —
https://arxiv.org/pdf/2606.07811
Authors: Giovanni Angelini, Luca De Angelis (University of Bologna).
Read in full 2026-08-24 (PDF text extracted via pypdf). These notes
transcribe the numbers the theory specs cite, with locators.

## Setting and data

Live NBA event contracts on Kalshi: one-minute quotes (bid/ask, volume,
open interest) merged with timestamped NBA play-by-play. Benchmark win
probability constructed from pre-game prices + live game state. Drift
regressions: 312k–353k observations, ~1,437 game clusters (Table 6).

## Headline findings

- **Impact coefficient (abstract; Table 5 context):** "a one-minute
  change in the benchmark probability is associated with only about a
  **0.64-for-one** contemporaneous change in market prices." In clutch
  situations the coefficient falls to **≈0.51** (Appendix C, quoted
  §5 end).
- **Pre-game prices are well calibrated** and become more accurate over
  the final 24 hours (§1, §4) — prices are informative; the failure is
  *dynamic* updating, not static calibration.
- **Drift after incomplete updating — Table 6** (coefficient ρ on the
  updating gap; raw / net-of-future-benchmark-changes):

  | Horizon | Raw drift | Net of benchmark changes |
  |---|---|---|
  | 1 min | 0.150*** (0.011) | 0.379*** (0.019) |
  | 2 min | 0.164*** (0.013) | 0.414*** (0.025) |
  | 5 min | 0.195*** (0.016) | 0.459*** (0.029) |
  | 10 min | 0.196*** (0.018) | 0.458*** (0.031) |
  | 15 min | 0.236*** (0.019) | 0.484*** (0.032) |

  In words (§5): "at the five-minute horizon, a 10 percentage point
  initial updating gap predicts a 2.0 percentage point subsequent price
  change and a 4.6 percentage point price change net of benchmark
  updates."
- **Moderators (§6):** salient signals (three-pointers, lead changes,
  scoring runs) are incorporated relatively quickly in liquid markets;
  the same signals generate substantially greater underreaction when
  liquidity is low, and those gaps predict stronger subsequent drift.
- **The tradeability negative the news-drift spec is built around**
  (§5, verbatim): "**executable-style returns that buy at the ask and
  sell at the bid are negative, indicating that the predictable
  midpoint drift is largely absorbed by trading costs.**" Also from the
  abstract: "the predictable midpoint drift does not translate into a
  simple arbitrage opportunity once bid–ask costs are imposed."
- Robustness (§5, Appendices A–B): result survives alternative
  benchmark models and microstructure restrictions (positive volume,
  narrow spreads, non-stale quotes); the sub-one coefficient is not a
  stale-quote artifact.

## How the specs use this

- **news-drift**: the 0.64 coefficient + Table 6 drift establish the
  phenomenon on Kalshi; the executable-returns quote is why the spec's
  likelihood is scored 2/5 and its thesis is explicitly an
  extrapolation to slower timescales/domains.
- **overreaction-fade**: the counter-evidence motivating the joint
  sign-measurement design (underreaction at minute scale vs documented
  overreaction at day scale in politics).
- **maker-mode-execution / structural-arb**: general caution that
  midpoint-level edges die at executable prices — the reason every
  backtest in the backlog charges the historical spread.
