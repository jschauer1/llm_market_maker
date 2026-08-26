"""Backfill the durable history cache for already-walked populations.

The two full-coverage backtests (2026-08-25) fetched raw candles and
settled-market payloads, used them once, and kept only the distillate —
before `tools/kalshi/cache.py` existed. This walks the same populations
again and stores the raw data, fetching only what the cache does not
already hold, so it is cheap wherever a cache-aware run already passed and
a full capture where none did. With Kalshi archiving settled markets ~60
days after close, this is time-critical for the June markets: raw data
not captured while reachable is gone, not merely expensive.

No ledger writes, no screening, no recording — this is data capture only.

Run:
    python -m theories.insider_bias.backfill_history --family mention \
        --checkpoint <path>
    python -m theories.insider_bias.backfill_history --family all \
        --checkpoint <path>

`--family` picks the population: `mention` (the sibling theory's 379
series), `insider` (everything else), `all` (both). The window matches the
full-coverage runs.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from tools.kalshi import cache as history_cache
from theories.insider_bias.insider_judgment import backtest as sibling
from theories.insider_bias.mention_family.mention_bucket import is_mention_family

WINDOW_MIN_CLOSE = int(datetime(2026, 5, 26, tzinfo=timezone.utc).timestamp())
WINDOW_MAX_CLOSE = int(
    datetime(2026, 8, 24, 21, 51, 52, tzinfo=timezone.utc).timestamp()
)
SERIES_RECENCY_DAYS = 450.0


def _parse_ts(iso: str | None) -> int | None:
    if not iso:
        return None
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def series_for(family: str) -> list[dict]:
    all_series = sibling.candidate_series(recency_days=SERIES_RECENCY_DAYS)
    if family == "mention":
        return [s for s in all_series
                if is_mention_family(s.get("ticker") or "")]
    if family == "insider":
        return [s for s in all_series
                if not is_mention_family(s.get("ticker") or "")]
    return all_series


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=["mention", "insider", "all"],
                        required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()

    state = (json.loads(args.checkpoint.read_text(encoding="utf-8"))
             if args.checkpoint.exists() else {"series": {}})
    series_list = series_for(args.family)
    print(f"{len(series_list)} series ({args.family}), "
          f"window {WINDOW_MIN_CLOSE}..{WINDOW_MAX_CLOSE}")

    conn = history_cache.connect()
    try:
        for ticker, survivors in sibling.iter_settled_survivors(
            series_list, WINDOW_MIN_CLOSE, WINDOW_MAX_CLOSE
        ):
            if ticker in state["series"]:
                continue
            stored = history_cache.store_settled_markets(conn, survivors)
            fetched = 0
            skipped = 0
            for m in survivors:
                close_ts = _parse_ts(m.close_time)
                if close_ts is None:
                    continue
                if history_cache.has_candles(conn, m.ticker):
                    skipped += 1
                    continue
                history_cache.cached_candlesticks(
                    conn, ticker, m.ticker,
                    start_ts=close_ts - int(
                        sibling.VOLUME_WARMUP_DAYS * 86400),
                    end_ts=close_ts, period_interval=1440,
                )
                fetched += 1
            state["series"][ticker] = {
                "n_survivors": len(survivors), "payloads": stored,
                "candles_fetched": fetched, "candles_cached": skipped,
            }
            args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
            args.checkpoint.write_text(json.dumps(state, indent=1),
                                       encoding="utf-8")
            if survivors:
                print(f"  {ticker:30s} survivors={len(survivors):4d} "
                      f"fetched={fetched:4d} already_cached={skipped:4d}")
    finally:
        conn.close()

    done = state["series"].values()
    print(f"done: {len(done)} series, "
          f"{sum(s['n_survivors'] for s in done)} survivors, "
          f"{sum(s['candles_fetched'] for s in done)} candle windows fetched, "
          f"{sum(s['candles_cached'] for s in done)} already cached")


if __name__ == "__main__":
    main()
