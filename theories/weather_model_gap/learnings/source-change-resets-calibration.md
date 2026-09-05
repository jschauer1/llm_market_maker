# A weather station is not the whole settlement definition

**Summary:** NWS-era errors cannot automatically calibrate current TWC weather contracts.

**Applies to:** WG-1 v1; KXHIGHNY, KXHIGHLAX and KXHIGHCHI; March–August 2026 source census.

**Finding:** Observed: all three series changed from NWS daily climate reports to The Weather Company on August 14. Only 18 dates per city in the retained window match today's source, below 30 required training labels. The frozen replay therefore selected zero trades and measured no edge.

**Do next time:** Count comparable source regimes before expensive forecast/candle collection. Match station, source, precision and settlement clock; require evidence before transferring errors across a rule change.

**Evidence:** [WG-1 result](../backtests/wg1-20260905/RESULTS.md), run `wg1-20260905/holdout`; source rules in `dataset.json` event markets.

**Revisit when:** Thirty current-source labels and a new independent validation window exist, or a paired source-equivalence study supports transfer.

**Updated:** 2026-09-05.
