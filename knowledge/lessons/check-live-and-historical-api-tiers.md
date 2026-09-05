# Check both Kalshi API tiers before declaring old data unavailable

**Summary:** For older Kalshi records, check both live and historical endpoints before concluding that the data cannot be recovered.
**Applies to:** Settled-market and candlestick retrieval observed for crypto and weather research on 2026-09-05; this does not establish that every previously missing record is recoverable.
**Finding:** Observed — Kalshi now partitions older markets, candlesticks, and trades into `/historical` endpoints behind a moving cutoff. An empty live response can therefore mean that the record moved rather than vanished.
**Do next time:** Fetch `/historical/cutoff`, query the applicable live and historical feeds, then merge and deduplicate. Continue capturing source data because availability and completeness can still change.
**Evidence:** [Kalshi historical-data overview](https://docs.kalshi.com/getting_started/historical_data), especially “How It Works” and “Historical Endpoints”; [historical market API](https://docs.kalshi.com/api-reference/historical/get-historical-markets).
**Revisit when:** Kalshi changes its cutoff policy or historical endpoint coverage.
**Updated:** 2026-09-05
