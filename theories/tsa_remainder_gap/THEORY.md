# TSA Remainder Gap

## Hypothesis

On Friday, four of the seven daily TSA passenger counts are already public.
Pricing only the unresolved three-day remainder may beat traders using a broad
weekly travel narrative. The hypothesized other side is retail overlooking
partial-week arithmetic; persistence and tradable profit remain unconfirmed.

## Data sources

Primary TSA annual daily tables and Kalshi KXTSAW weekly contracts, including
historical TSAW records with matching explicit TSA-source rules. The source
census contains 219 event records from June 2022 through August 2026. These are
weekly observations, not thousands of independent strikes.

[Source audit](sources/SOURCE_AUDIT.md): today's TSA archive crosses a settled
strike in 16/219 records; rounding does not explain it. No sampled public archive
recovered those historical vintages. Historical data remain useful for an
explicit experimental diagnostic, with this limitation visible.

## Status

`under_review` after the frozen archive diagnostic: its 44 holdout positions
averaged -8.07 net points, with both clustered 95% intervals below zero.
[Results and scope](backtests/trg1-20260905/RESULTS.md). Source revisions still
limit inference; this is evidence against the fixed reconstruction, not every
possible TSA model. No supported edge or recommended bet has been established.

## Version

1 — TRG-1, fixed before trading returns were inspected, 2026-09-05.

## Stage 1 — mechanical screen

At Friday 15:00 UTC, sum Monday–Thursday counts S4. For each of the preceding
52 complete calendar weeks, compute the Friday–Sunday / Monday–Thursday ratio.
For a weekly-average strict-above strike K, count ratios above (7K-S4)/S4 using
exact integer comparison. qYES=(count+0.5)/53; qNO=1-qYES.

Take the highest fee-net edge across both sides and strikes, at most one position
per week. Require at least 8 net points, spread <=10 cents, entry open interest
>=100, and a valid bought-side ask strictly between zero and one. Tie-break by
ticker then side. Historical entry uses the candle ending exactly Friday 15:00
UTC, with no terminal liquidity substitution. Missing or closed-at-entry markets
remain explicit exclusions.

Live runs require an actual sealed source receipt containing Thursday, fresh
quotes and at least 10 contracts at the best ask, within Friday 15:00–15:30 UTC.
The shared model produces arithmetic `edge_basis="model"` probabilities. They
are probationary estimates; experimental historical rows provide no production
track record. One position per week is enforced when recording.

## Stage 2 — judgment

None. No model classifies or invents probabilities.

## Sub-theories

None registered. A promising narrower population must be registered and confirmed
independently; descriptive holiday or side tables do not create evidence for it.

## How to backtest

[TRG-1 protocol](backtests/trg1-20260905/PROTOCOL.md) freezes dates, fees, entries
and evaluation. Development ends 2025-08-24; the holdout covers 2025-08-31 through
2026-08-30. Both runs use `exp/` identities, tier A with no LLM judgment. Decisions
are sealed before settlement, and immutable identities prevent accidental reuse
of a run name for changed inputs. [Runbook](RUNBOOK.md) gives commands.

A source-valid confirmation needs >=30 entered weeks, no pending outcomes and
positive lower clustered bounds after rounded fees. An interval containing zero
is unconfirmed. An upper bound below +3 net points argues against that practical
edge within the tested population. The current-archive campaign cannot qualify
regardless of its profit. No-signal weeks establish only absent entries.

## Relation to earlier work

This narrows the dead `accumulation-decay` idea: it forecasts an unresolved tail,
instead of buying a favorite after its outcome is determined. It does not use
consensus anchoring or a weather forecast. The old executable-price failure is
a reason to measure carefully, not proof that TSA has no edge.
