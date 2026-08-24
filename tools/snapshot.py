"""First-party market history capture (spec section 5).

kalshi_trader overwrote its raw market dump on every fetch, so it retained no
history at all. This table accumulates instead — every capture is a new row.

Two reasons it matters. It hedges against either platform's own historical
API being too shallow, and it grows the clean (tier B) backtest window over
time, since markets that resolve after today are uncontaminated by any
model's training data.

find-edge calls capture_kalshi_open as a side effect, so history accrues from
ordinary use without any scheduler.
"""

from __future__ import annotations

import json
import sqlite3

from tools.db import utcnow, write
from tools.kalshi import markets as kalshi_markets
from tools.polymarket import markets as poly_markets

_INSERT = """
    INSERT INTO market_snapshots (
        platform, market_id, captured_at, title, implied_prob_yes,
        yes_bid, yes_ask, volume, open_interest, close_time, status, raw_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# Kalshi's own status strings (see kalshi_markets.OPEN_STATUSES and
# normalize()'s is_open) mapped onto the three-state open|closed|settled
# column defined by db/schema.sql and the design spec. Kalshi genuinely has
# a third state — closed but not yet settled — that a strict is_open/else
# binary would collapse into "settled" incorrectly.
_SETTLED_STATUSES = {"finalized", "settled"}


def _kalshi_snapshot_status(m: dict) -> str:
    status = m.get("status")
    if status in kalshi_markets.OPEN_STATUSES:
        return "open"
    if status in _SETTLED_STATUSES:
        return "settled"
    return "closed"


def save_kalshi(
    conn: sqlite3.Connection, markets: list[dict], now: str | None = None
) -> int:
    """Persist normalized Kalshi markets. Returns rows written."""
    stamp = now or utcnow()
    rows = [
        (
            "kalshi",
            m["ticker"],
            stamp,
            m.get("title"),
            # This is the market MID, not an executable price — anything
            # that needs an actual entry price for a bet must use yes_ask
            # (or yes_bid for the NO side), never this column.
            m.get("mid"),
            m.get("yes_bid"),
            m.get("yes_ask"),
            m.get("volume"),
            m.get("open_interest"),
            m.get("close_time"),
            _kalshi_snapshot_status(m),
            json.dumps(m.get("raw", {})),
        )
        for m in markets
    ]
    if not rows:
        return 0
    with write(conn):
        conn.executemany(_INSERT, rows)
    return len(rows)


def save_polymarket(
    conn: sqlite3.Connection, markets: list[dict], now: str | None = None
) -> int:
    """Persist normalized Polymarket markets. Returns rows written."""
    stamp = now or utcnow()
    rows = [
        (
            "polymarket",
            m["market_id"],
            stamp,
            m.get("question"),
            m.get("implied_prob_yes"),
            m.get("best_bid"),
            m.get("best_ask"),
            m.get("volume"),
            None,
            m.get("end_date"),
            "settled" if m.get("closed") else "open",
            json.dumps(m.get("raw", {})),
        )
        for m in markets
    ]
    if not rows:
        return 0
    with write(conn):
        conn.executemany(_INSERT, rows)
    return len(rows)


def history_for(
    conn: sqlite3.Connection, platform: str, market_id: str
) -> list[sqlite3.Row]:
    """Every snapshot of one market, oldest first."""
    return conn.execute(
        """
        SELECT * FROM market_snapshots
        WHERE platform = ? AND market_id = ?
        ORDER BY captured_at
        """,
        (platform, market_id),
    ).fetchall()


def capture_kalshi_open(
    conn: sqlite3.Connection,
    limit: int = 200,
    now: str | None = None,
) -> int:
    """Fetch and persist the current open Kalshi board.

    Always captures the complete board (`list_open` always pages to
    exhaustion, with no partial-fetch option) — on the order of 95k markets,
    roughly a minute of paging. A partial capture is worse than no capture at
    all for first-party history: a biased slice looks like data, and nothing
    downstream can tell the difference after the fact.
    """
    found = kalshi_markets.list_open(limit=limit)
    return save_kalshi(conn, found, now=now)


def capture_polymarket_open(
    conn: sqlite3.Connection, limit: int = 100, now: str | None = None
) -> int:
    """Fetch and persist the current open Polymarket board."""
    found = poly_markets.list_open(limit=limit)
    return save_polymarket(conn, found, now=now)
