# ND-1 cached diagnostic protocol

ND-1 implementation protocol — frozen before results, 2026-09-05

This narrows the exploratory grid above to **one pooled continuation test**.
No domain, price, horizon, or move-size search is confirmatory. Reversal is
reported as the paired diagnostic at its own executable ask, not adopted
because it happens to win this holdout. New subsets require their own evidence.

**Mechanism and population.** Slow updating by participants who retain their
pre-news view may leave multi-day drift after a large move. The potential
counterparty is that stale belief, not an assumed uninformed market maker.
Target Kalshi event categories Politics, Elections, Economics, Entertainment,
and World; exclude unknown categories, Sports, Mentions, and continuous
financial/crypto prices. The shared board captured 2026-09-05T00:41:36Z contains
4,761 open markets in those categories with OI >=100, spread <=4 cents, and
nonterminal two-sided quotes. This counts an eligible market population, not
4,761 signals. Historical categories use saved series metadata, with missing
coverage reported. No model judges or extracts an outcome.

**Signal and entry.** Use five consecutive daily candles at 86,400-second
spacing. In the fourth candle, the YES quote midpoint moves at least 0.15
from the third candle and finishes in [0.15, 0.85]. Its volume must exceed
the median volume of the three preceding candles, with all volumes valid
and nonnegative. The fifth candle is the entry, a full day after the signal;
the move direction buys YES when positive and NO when negative. Its midpoint
must still be in [0.15, 0.85], spread <=0.04, OI >=100, and volume >0.
All five bid/ask pairs must be ordered, finite, and inside [0,1]. Entry is
YES ask or 1 - YES bid for NO, never a midpoint. Missing/gapped candles
are ineligible, never filled using a future observation. Live runs use the
last completed daily candle within 24 hours for the signal history and the
current rechecked payable quote for entry. That quote may be worse than the
daily close; report the difference. No deadline filter uses realized close.
Hold to resolution. Count the first eligible entry per ticker per campaign;
repeated proposals are attempts, not independent positions.

**Calibration and temporal split.** Fit one additive calibration residual
in direction space: mean(realized directional payout - entry directional
midpoint), over training decisions before 2026-08-01 whose outcomes were
known before 2026-08-01. Minimum 30 training tickers and 10 event clusters.
The mechanical forecast is clamp(entry directional midpoint + residual,
0,1). Validation decisions are 2026-08-01 through 2026-08-17 inclusive;
no validation outcome enters this fitted artifact. Record all signals,
including nonpositive priced candidates as rejected controls. Without a
usable training artifact, record observation-only rows claiming zero edge.
Forecast arithmetic has basis `model`; unsupported observations have `prior`.
An artifact carries its cutoff, source digest, sample counts, and protocol ID.

**Evidence and decision.** Publish net payout at ask less the repository fee
model, plus the more conservative fee for a one-contract rounded order.
Report gross residual, spread cost, event/day counts, and clustered uncertainty
by event and settlement day. Support requires positive net mean with both
95% cluster intervals above zero, >=30 events and >=10 settlement days, and
a valid population reconstruction. Report uncertainty/power when those bars
cannot be reached. A 95% upper bound below +3 net points rejects a practically
large edge in this tested population; it does not prove every continuation
strategy has no edge. Quotes do not prove historical depth or a fillable size.

The first corpus is the existing daily `db/history_cache.db`; its settled-only,
partially collected frame is a named limitation, not a complete market census.
Freeze a manifest and report coverage before computing returns. If selection
or right-censoring cannot be bounded, keep that campaign exploratory (`exp/`)
and never let it silently become production calibration or independent proof.
Use the exact live `screen()` and `price()` in the replay. Test planted
continuation, reversal, fee-erased effects, timing gaps, and future leakage
on fixtures before reading the historical result. Finish with a live run and
an honest evidence status, whether or not ND-1 earns a bet.

**Pre-metrics review clarification (same session).** Actual historical close
is used only to veto a fifth-candle entry at/after trading stopped, never as
a future deadline or proximity feature. Missing close excludes the row.
Outcome availability uses `settlement_ts`, not close time. The frozen
row-weighted estimand means one equal contract per ticker; report largest
event share and effective event count alongside clustered uncertainty.
This measures conditional miscalibration, not causal news diffusion without
a matched control. The cache was collected through the insider screen,
including terminal volume/category exclusions and close-anchored windows;
its replay is therefore exploratory regardless of contamination tier A.

**Implementation work:** test signal/timing and pricing in
`tests/theories/test_news_drift.py`, implement owner-local `signal.py` and
`theory.py`; test terminal-information isolation and fee/cluster arithmetic
in `tests/theories/test_news_drift_data.py`, implement `data.py`, `analysis.py`
and the replay driver; then verify experiment quarantine, run the frozen
campaign and live scan, update runbook/results/memory, and close this ticket
into the implemented theory. No shared replay framework or new dependency.

## build — 2026-09-05

Building ND-1 with frozen daily continuation protocol and explicit coverage/holdout limits.
