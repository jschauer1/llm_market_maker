"""Durable write-through cache for Kalshi historical data.

Why this exists (2026-08-25): the full-coverage backtests are
tens-of-thousands of small HTTP fetches whose *distillate* (screen hits,
settlements) lands in the ledger while the raw candles and settled-market
payloads were fetched, used once, and discarded. That made every variant
re-test (a different price band, a different entry rule, the NO-side
hypothesis) cost a full re-walk — and, worse, Kalshi archives settled
markets out of its public API ~60 days after close (see
`markets.py::list_settled`), so raw data not captured while reachable is
not merely expensive to refetch, it is *gone*. This module is the same
philosophy as `tools/snapshot.py` ("keep the complete raw payload"),
applied to the two payloads the walks touch: per-market candlesticks and
settled-market listing rows.

Lives in its own SQLite file (`db/history_cache.db`), not in
`market_edge.db`: the main DB is the source of truth for *structured
facts*; this is a bulk raw-payload cache (hundreds of MB at full scale),
and keeping it separate means backing up or vacuuming one never drags the
other. WAL mode, single writer expected.

`cached_candlesticks` is a drop-in for `history.candlesticks`: it returns
the cached candles when the stored window covers the request (sliced to
the requested range), and otherwise fetches, stores, and returns. A fetch
that returns zero candles is stored too — "Kalshi served nothing for this
window" is an answer worth remembering, not a miss to retry forever.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tools.db import utcnow
from tools.kalshi import history

DEFAULT_CACHE_PATH = Path("db") / "history_cache.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    ticker          TEXT    NOT NULL,
    period_interval INTEGER NOT NULL,
    start_ts        INTEGER NOT NULL,
    end_ts          INTEGER NOT NULL,
    series_ticker   TEXT,
    fetched_at      TEXT    NOT NULL,
    payload         TEXT    NOT NULL,
    PRIMARY KEY (ticker, period_interval)
);
CREATE TABLE IF NOT EXISTS settled_markets (
    ticker        TEXT PRIMARY KEY,
    series_ticker TEXT,
    close_time    TEXT,
    fetched_at    TEXT NOT NULL,
    payload       TEXT NOT NULL
);
"""


def connect(path: str | Path = DEFAULT_CACHE_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def cached_candlesticks(
    conn: sqlite3.Connection,
    series_ticker: str,
    ticker: str,
    start_ts: int,
    end_ts: int,
    period_interval: int = 1440,
    fetch_candles=None,
) -> list[dict]:
    """history.candlesticks with a durable write-through cache.

    Cache hit requires the stored window to cover the requested one; the
    stored candles are then sliced to the request so a caller cannot see
    candles it did not ask for. `fetch_candles` is injectable for tests,
    same discipline as the repo-wide `fetch` convention.
    """
    row = conn.execute(
        "SELECT start_ts, end_ts, payload FROM candles "
        "WHERE ticker = ? AND period_interval = ?",
        (ticker, period_interval),
    ).fetchone()
    if row is not None and row[0] <= start_ts and row[1] >= end_ts:
        candles = json.loads(row[2])
        return [c for c in candles if start_ts <= c["end_ts"] <= end_ts]

    fetch_candles = fetch_candles or history.candlesticks
    candles = fetch_candles(
        series_ticker, ticker,
        start_ts=start_ts, end_ts=end_ts, period_interval=period_interval,
    )
    with conn:
        conn.execute(
            "REPLACE INTO candles (ticker, period_interval, start_ts, "
            "end_ts, series_ticker, fetched_at, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticker, period_interval, start_ts, end_ts, series_ticker,
             utcnow(), json.dumps(candles)),
        )
    return candles


def store_settled_markets(conn: sqlite3.Connection, survivors) -> int:
    """Persist settled-market listing payloads (`Market.raw`), latest wins.

    Takes the domain `Market` objects a listing walk produced; each must
    still carry its raw payload. Returns how many were written.
    """
    written = 0
    with conn:
        for m in survivors:
            if not m.raw:
                continue
            conn.execute(
                "REPLACE INTO settled_markets (ticker, series_ticker, "
                "close_time, fetched_at, payload) VALUES (?, ?, ?, ?, ?)",
                (m.ticker, m.series_ticker, m.close_time, utcnow(),
                 json.dumps(m.raw)),
            )
            written += 1
    return written


def has_candles(conn: sqlite3.Connection, ticker: str,
                period_interval: int = 1440) -> bool:
    """True when any candle window is stored for this market."""
    return conn.execute(
        "SELECT 1 FROM candles WHERE ticker = ? AND period_interval = ?",
        (ticker, period_interval),
    ).fetchone() is not None
