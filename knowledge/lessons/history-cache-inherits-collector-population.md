# A shared cache retains its collector's selection rules

**Summary:** Reusing `history_cache.db` for a new theory does not make it a representative market sample.
**Applies to:** The insider-screen backfill in this cache, inspected for ND-1 on 2026-09-05; not every historical dataset.
**Finding:** Observed — the collector filters categories and terminal volume, then requests a 45-day window anchored to realized close. ND-1 found 4,508 mapped target tickers, but no coverage denominator for its broader population. Mechanical replay does not remove this selection.
**Do next time:** Trace the producing collector before trusting cached coverage. Use this frame for scoped diagnostics; enumerate the intended population and fixed calendar windows before claiming a new theory's edge.
**Evidence:** [Backfill procedure](../../theories/insider_bias/backfill_history.py), `run`; [selection](../../theories/insider_bias/replay.py), `candidate_series` and `is_candidate`; [ND-1 scope audit](../../theories/news_drift/backtests/nd1-cache-20260905/RESULTS.md#scope-and-reproducibility).
**Revisit when:** A complete, explicitly sampled population supports the proposed inference.
**Updated:** 2026-09-05
