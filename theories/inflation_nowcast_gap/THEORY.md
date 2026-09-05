# Inflation Nowcast Gap

## Hypothesis

The Cleveland Fed's independently published daily CPI nowcast can contain
release-specific information that is not fully reflected in Kalshi's monthly
CPI threshold ladders. The likely counterparty mistake is anchoring to a stale
consensus or prior print while the nowcast incorporates newer oil, gasoline,
CPI, and PCE inputs. The effect may persist because the contracts are small,
monthly, and fragmented across many strikes even though the underlying macro
release is professionally watched.

This is separate from `econ-anchoring`. That proposal extrapolates recent
official prints and uses Kalshi's mode as a consensus proxy. This theory uses
only the external official nowcast and its historical first-print residuals.

## Data sources

- Cleveland Fed monthly nowcast JSON: exact daily headline and core CPI
  estimates, retained with response bytes and hashes.
- BLS archived CPI releases: first published seasonally adjusted monthly
  headline and core values, retained with publication times and hashes.
- Kalshi `KXCPI` and `KXCPICORE`: rules, hourly candles, current executable
  quotes, open interest, and volume.

The frozen data and replay contract is
[ING-1](backtests/ing1-20260905/PROTOCOL.md). V1 excludes PCE because its
Kalshi archive does not yet contain 30 independent release dates.

## Status

`proposed` — implementation and source collection began 2026-09-05 under the
frozen ING-1 protocol. It becomes `testing` only after the normal Theory
contract runs and records an honest observation.

## Version

1 — prior-business-day noon ET entry; expanding same-series first-print
residual CDF; Decimal half-up one-decimal mapping; strict-above strikes;
8-point fee-net minimum; spread, OI, ask, and entry-hour-activity gates; one
position per BLS release date across headline and core.

## Stage 1 — mechanical screen

Match only exact `KXCPI` and `KXCPICORE` strict-above, single-decimal,
seasonally adjusted month-over-month contracts. At the fixed noon ET entry,
use only earlier BLS publications from the same series. Add each prior residual
to the current Cleveland nowcast, round each possible print to one decimal with
Decimal `ROUND_HALF_UP`, and count strict threshold hits. Jeffreys smoothing
converts those counts to YES/NO model probabilities.

Require at least 30 prior months, positive exact entry-hour volume, OI at least
100, spread at most 10 cents, chosen ask in `[0.05, 0.95]`, and at least eight
percentage points after the normal fee. Select one highest net gap across both
series and all strikes on a release date, with deterministic ticker/side ties.
Every exclusion is reported in the funnel.

## Stage 2 — what needs judgment

None. The full procedure is deterministic, uses no LLM judgment, records
`edge_basis="model"`, and qualifies for tier A when replay source timestamps
pass audit.

## Confidence buckets

None. Probabilities come from the frozen mechanical residual CDF.

## How to backtest

Use `TheoryContext(run_mode="backtest", run_id="ing1-20260905/holdout")`
with `ctx.now` equal to each event's fixed entry time. Reconstruct the market
from the exact hourly candle at or before that time and call the same
`screen()` and `price()` used live. Freeze decisions and source hashes before
joining settlements. Price only at the executable ask and cluster all
headline/core strikes on the same BLS release date.

Positive evidence requires at least 30 independent traded release dates,
positive fee-net ROI, and a release-date-clustered 95% confidence interval
whose lower bound exceeds zero. A smaller result is underpowered. Thresholds
stay frozen after results.

## Learnings

[Browse scoped lessons](learnings/README.md). Working narrative belongs in
dated files under `notes/`.
