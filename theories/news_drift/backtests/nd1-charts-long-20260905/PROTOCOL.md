# ND-1 long chart cohort — pre-results design amendment, 2026-09-05

The short chart campaign remains an auditable declaration. Before computing
any chart-cohort return, enumeration showed its 17-day entry holdout has only
four scheduled expiry dates, making the ten-day evidence bar predictably
underpowered. This separate campaign expands the calendar for power, not to
select a winning interval. No chart result or sign was used to choose dates.

**Population and procedure:** unchanged ND-1 signal, entry and pricing
arithmetic; exact series KXALBUMEQUIV, KXPUREALBUMS, KXTOPSONG,
KXBILLBOARDRUNNERUPSONG, KXTOPALBUM, KXBILLBOARDRUNNERUPALBUM.
All statuses, both live and archive endpoints, complete pagination, and no
final-volume/outcome prefilter. Preserve the 7,247-market enumeration and
raw source responses. Candles use **2026-01-01 through 2026-09-01 UTC**.
Skip API candle calls only when actual trading availability is entirely
outside that fixed window (open >= end or actual close <= start), retaining
those tickers and reasons in the manifest. Missing data is never empty history.

**Split:** train on first signals entering before **2026-05-01**, using only
settlements known before that instant; holdout first entries May 1–August 31.
Only the training partition fits the single pooled directional-mid residual.
Dates, sign, move threshold, spread, volume and price-band gates are fixed.
The calibration cutoff is artifact provenance, not a hardcoded market feature.
No model judges, and the replay calls the same live screen/pricing functions.

**Prior exposure:** the earlier broad cache diagnostic overlapped some later
calendar dates. Save its event IDs before this new analysis; publish both the
whole holdout and a confirmation sensitivity excluding every previously
screened event. A supported finding must survive the same positive evidence
bar in that unexposed panel as well. Do not silently label reused rows new
independent evidence. This additional bar is fixed before measuring the cohort.

**Evidence:** one equal contract per ticker; >=30 event clusters and >=10
settlement days, positive net mean and both 95% event/day cluster intervals
above zero. Publish maximum event share, effective event count, equal-day
sensitivity, and one-contract rounded-fee returns. Unresolved signals remain
in the denominator; a positive claim must survive all pending outcomes losing.
Reversal remains a diagnostic, never another chance to pass. An upper bound
below +3 net points rules out a practically large effect only in this scope;
insufficient power leaves it unconfirmed.

The mechanics are contamination tier A. Valid held-out evidence may affect
production probabilities at full weight; complete collection alone does not
make a losing or underpowered result bettable. Any trained artifact applies
only to these six registered `weekly-charts` series. Historical quotes have
no size/depth guarantee; fresh executable quotes/depth are checked separately.
