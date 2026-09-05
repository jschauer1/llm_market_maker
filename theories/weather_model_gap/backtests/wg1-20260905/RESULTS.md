# WG-1: insufficient current-source history; no edge measured

Frozen run `wg1-20260905/holdout` selected **zero trades**. No win rate or
return estimate exists. This is a source-coverage failure, not evidence that
weather forecasts cannot beat Kalshi prices.

All three cities switched from NWS to The Weather Company on **2026-08-14**.
The March–August inventory has 184 events per city, but only the final 18 per
city use the current settlement source. WG-1 requires 30 same-station,
same-source settled labels before entry. None of the July–August holdout can
meet that requirement. Do not borrow older NWS labels without separately
establishing that the source change preserves the forecast-error distribution.

| Population | Comparable history dates | Selected trades | Result |
|---|---:|---:|---|
| Weather Model Gap | 18 dates across 3 cities | 0 | Insufficient calibration |
| ↳ nyc | 18 | 0 | Same |
| ↳ lax | 18 | 0 | Same |
| ↳ chicago | 18 | 0 | Same |

Collection retained 3,312 legs across 552 events: 3,289 exact entry candles,
23 missing/wrong-time candles, and 549 complete event forecasts. The missing
forecast is the exact June 10 12Z run, affecting all three June 11 targets.
One NYC June 23 event has an inconsistent missing payout temperature; its NWS
source already excludes it. All 3,312 payouts are binary rather than fractional
fallback settlements.

Holdout gate removals: 783 non-TWC legs, 250 legs without enough training,
59 without entry-hour activity, 19 without the entry candle, 3 with low OI,
and 2 with wide spreads. Counts describe sequential gates, not independent
market populations. Parent and all city scores remain n=0.

The exact [protocol](PROTOCOL.md), `evaluation_manifest.json`, `decisions.json`,
`dataset.json`, source `manifest.json`, and registered run preserve the test.
`results.json` is regenerable through the owner replay. Raw source receipts
are retained locally under `raw/`, excluded from Git; preserve that directory
when moving the research data. No historical depth or fills are claimed.

Revisit after 30 current-source labels per city exist **and** a new, frozen
independent validation period can accrue. Alternatively, an explicit paired
source-equivalence study could justify a bridge; merely sharing a station name
cannot. Do not relax the source gate to rescue this campaign.
