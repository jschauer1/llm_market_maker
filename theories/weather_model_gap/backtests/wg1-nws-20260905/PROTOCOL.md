# WG-1-NWS: frozen legacy-source diagnostic, 2026-09-05

## Question and scope

Can WG-1's forecast-error model outperform payable asks in the earlier NWS
settlement regime? This cheap experiment uses already retained source data
to decide whether investigating a bridge to current TWC contracts is worth
further work. No NWS forecast-versus-price returns have been inspected.
It is not current-source evidence, and cannot authorize a TWC recommendation.

Exactly KXHIGHNY/KXHIGHLAX/KXHIGHCHI events with NWS daily climate-report
rules and matching Central Park/LAX/Midway stations, March1–August13,2026.
Keep binary final payouts, exact consistent whole-degree labels and as-of
settlement timing. Missing/invalid labels or forecasts stay excluded visibly.
Do not rewrite original source rules to satisfy the TWC gate.

## Fixed procedure

Use WG-1 unchanged except the explicit NWS source predicate and diagnostic
protocol identity: prior-day12Z ecmwf_ifs max hourly forecast over fixed standard
day; half-up integer rounding; preceding90calendar-day same-station errors;
minimum30 known labels; Jeffreys hit probability; exact00UTC entry candle;
YES ask/NO complementary ask; spread<=.04, OI>=100, positive hourly volume,
buy price[.05,.95]; largest net edge>=8points, one contract per station/date,
deterministic ticker/side ties. The same theory start/finish implementation
must generate decisions. No fee, lead, threshold or city selection changes.

March–April supplies initial training. **May1–August13 inclusive** is the
single chronological holdout, with training labels advancing only as settled.
Freeze selected decisions without outcomes before computing returns. All ledger
rows use `exp/wg1-nws-20260905/holdout`, tier A and no LLM; production scores
exclude this experiment. Derived labels have separate source identity linked
to the immutable base dataset and this protocol.

## Interpretation and stopping rule

Primary: pooled one-position-per-station/date net returns, event/weather-date/
settlement-date cluster intervals, rounded one-contract fee sensitivity,
pending-outcome bounds and coverage. Report all three predeclared cities;
city diagnostic support uses >=30 clusters on each axis and mean−2.6SE>0.
Use the same WG-1 statistical functions, never a post-hoc best-price cell.

If even the NWS model is unconfirmed, preserve that scope and stop without
retuning. Positive legacy-source evidence can justify a separately specified
source-equivalence study; it still cannot price current TWC bets. An upper
confidence bound below+3netpoints rules out a practically large effect only
for this frozen legacy population. No special treatment for a favorable city.

Source: sibling campaign `../wg1-20260905/dataset.json` and its immutable
manifest, plus original archived market rules, forecasts and exact-entry quotes.
The new campaign stores only its small derived identity, frozen decisions and
result; it does not duplicate the raw corpus.
