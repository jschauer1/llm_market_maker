# ND-1 chart cohort — declared before returns, 2026-09-05

Test the unchanged ND-1 daily continuation procedure on a fully enumerated
recurring chart/sales subset. This cohort is chosen by issuance structure and
data availability, without reading its returns. It cannot supply a probability
for the rest of News Drift's population.

Exact series: KXALBUMEQUIV, KXPUREALBUMS, KXTOPSONG,
KXBILLBOARDRUNNERUPSONG, KXTOPALBUM, KXBILLBOARDRUNNERUPALBUM.
Their predefined weekly releases make a finite cohort feasible; category
comes from the exchange's series metadata, never an outcome classifier.

Enumerate every status through complete public endpoint pagination, including
archived markets if the API cutoff requires it. Keep raw responses and ticker
denominators, including zero-volume, null-quote and unresolved markets.
Fix candle requests to 2026-06-01 through 2026-08-18 UTC, with the initial
five completed daily bars as warmup. Do not anchor the window to realized
close or use terminal volume to decide which markets get candles. A missing
or truncated series/candle response makes coverage incomplete; it is not zero
signals. Checkpoint every response so collection can resume.

Use the unchanged five-candle ND-1 signal and executable entry. Actual close
only vetoes an entry at/after trading ended. Select each ticker's first signal
in the fixed window. Training decisions and known settlements precede Aug 1;
holdout decisions span Aug 1–17 inclusive. Training outcomes become known at
settlement_ts; unresolved holdout rows remain in the denominator as pending.
Do not move the split, thresholds or category/series list after observing data.

The estimate remains one equal contract per ticker. Show event and settlement
day intervals, maximum event share, effective event count, and an equal-day
sensitivity because related chart/sales contracts share the same release.
No sign or price-bin search on the holdout. The paired reversal result is a
diagnostic, never independent confirmation for an opposite strategy.

The predeclared +3-point practical bar and positive-evidence requirements are
the parent ND-1 protocol's: >=30 events, >=10 settlement days, positive
fee-net mean with both cluster intervals above zero, valid complete coverage.
Report one-contract rounded fees and no historical depth guarantee.
Unresolved returns must be bounded, including all losses, before a positive
claim; otherwise the result is pending. A subset finding remains a registered
chart sub-theory with these exact series and its own evidence. Production
probabilities may use valid backtests in full, exclusively within this scope.
