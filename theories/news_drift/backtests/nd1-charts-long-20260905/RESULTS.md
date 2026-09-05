# ND-1 weekly charts: no supported bet

The frozen procedure cannot supply a production calibration. January–April
had eight signals across seven events, below the predeclared 30-ticker,
10-event minimum. May–August generated 91 observations, including nine still
open at capture. All 91 were recorded as zero-edge priors; there were **zero
model-priced recommendations**. The following returns describe buying every
signal, not a portfolio the calibrated procedure recommended.

| Sample | Settled / pending | Events / days | Net points | Event 95% interval | Day 95% interval |
|---|---:|---:|---:|---:|---:|
| Training | 8 / 0 | 7 / 7 | +16.66 | −4.43 to +37.75 | −4.43 to +37.75 |
| Holdout | 82 / 9 | 44 / 19 | −5.75 | −16.04 to +4.53 | −16.17 to +4.66 |
| Holdout excluding previously exposed events | 10 / 9 | 9 / 5 | −6.17 | −41.10 to +28.75 | −43.07 to +30.72 |

Holdout net across **all 91**, bounding every pending outcome as a loss/win,
is −11.96 to −2.07 points. One-contract rounded fees reduce settled net to
−6.20; equal-day weighting gives −12.28. The largest event contributes 9.8%
of settled rows; effective event count is 28.25. Exploratory reversal returns
are +0.69 points, with both clustered intervals spanning zero: no supported
reverse strategy either. The +3-point effect falsifier is not met by either
settled holdout upper bound; a general no-edge conclusion would overreach.

Coverage: all 7,247 markets in the six preregistered series, 54,752 daily
candles, zero missing requests/category conflicts. Calendar-disjoint markets
remain explicit empty histories. Quotes establish historical ask prices,
not fillable depth. The longer calendar was chosen before chart returns
because the short campaign had too few settlement dates. Earlier cache
exposure is separately excluded in the confirmation panel.

**Next decision:** keep observation-only; do not install this artifact or
tune thresholds against the holdout. A materially different mechanism needs
its own frozen test. Acquire more independent training only if expected
opportunity value justifies it. Keep the raw census for future measurements.

Reproduce with `python -m theories.news_drift.backtest_charts`. Exact numbers
live in [results.json](results.json), cohort identity in
[replay_manifest.json](replay_manifest.json), and the predeclared rules in
[PROTOCOL.md](PROTOCOL.md). Ledger validation run:
`nd1-charts-long-20260905/holdout`; training is experimental.
