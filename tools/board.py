"""One Kalshi board per session, shared by every theory.

A complete board is ~100k markets and about 13 seconds of paging. That is
cheap enough to do once and far too expensive to do per theory: a session
running four theories should pull once, not four times, and a second session
that starts while the first pull is still fresh should reuse it rather than
re-walking the whole feed.

Before this existed the reuse was prose in a skill — `find-edge` told the
session to reuse the board `go` had already fetched. That works inside one
context window and nowhere else. Two sessions on 2026-08-24 pulled the board
19 hours apart with no way for the second to know the first had already
written it. This module makes the reuse a mechanism.

The cache is the snapshot table, not a side file. `save_kalshi` already
persists every pull, so the freshest snapshot batch *is* the cached board —
there is nothing extra to store, invalidate, or keep in sync, and the history
the project accrues comes for free.

A rebuilt board is identical to a fetched one, `market["raw"]` included:
snapshots store the complete Kalshi payload, so a cache hit and a forced
fetch hand back the same shape. That matters more than it sounds — a cache
that returned a thinner `raw` would make any theory reading an uncommon field
work on a forced pull and silently return `None` on a cached one.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from tools import snapshot
from tools.db import utcnow
from tools.kalshi import markets as kalshi_markets

#: How old the freshest snapshot may be before `get_board` refetches.
#: Four hours is chosen to cover a long working session while guaranteeing a
#: new session the next morning gets fresh prices.
DEFAULT_MAX_AGE_MINUTES = 240


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def board_info(conn: sqlite3.Connection, now: str | None = None) -> dict | None:
    """Age and size of the freshest stored board, or None if there is none."""
    row = conn.execute(
        """
        SELECT captured_at, COUNT(*) AS n
          FROM market_snapshots
         WHERE platform = 'kalshi'
           AND captured_at = (SELECT MAX(captured_at)
                                FROM market_snapshots
                               WHERE platform = 'kalshi')
         GROUP BY captured_at
        """
    ).fetchone()
    if row is None:
        return None
    age = (_parse(now or utcnow()) - _parse(row["captured_at"])).total_seconds()
    return {
        "captured_at": row["captured_at"],
        "markets": row["n"],
        "age_minutes": age / 60.0,
    }


def _rebuild(conn: sqlite3.Connection, captured_at: str) -> list[dict]:
    """Reconstruct normalized markets from a stored snapshot batch."""
    rows = conn.execute(
        """
        SELECT raw_json FROM market_snapshots
         WHERE platform = 'kalshi' AND captured_at = ?
        """,
        (captured_at,),
    ).fetchall()
    out = []
    for row in rows:
        raw = json.loads(row["raw_json"] or "{}")
        if not raw.get("ticker"):
            # A snapshot written before raw_json carried a ticker cannot be
            # rebuilt. Fail loudly rather than return a short board that
            # looks complete -- a screen reading it would silently under-run.
            raise ValueError(
                f"snapshot batch {captured_at} has rows with no ticker in "
                "raw_json and cannot be rebuilt into a board. Re-fetch with "
                "get_board(conn, force=True)."
            )
        out.append(kalshi_markets.normalize(raw))
    return out


def get_board(
    conn: sqlite3.Connection,
    *,
    max_age_minutes: float = DEFAULT_MAX_AGE_MINUTES,
    force: bool = False,
    now: str | None = None,
) -> list[dict]:
    """The complete Kalshi board, fetching only if what is stored is stale.

    Every theory should call this rather than `markets.list_open()`, so one
    session makes one pull. Pass `force=True` for the deliberate session-start
    refresh (`go`'s Orient step) or when a price is known to have moved and
    freshness genuinely matters — re-quoting a handful of tickers before
    betting is `markets.quotes()`, which is cheaper than any board pull.

    A fetch is always snapshotted, so the pull is never lost.
    """
    if not force:
        info = board_info(conn, now=now)
        if info is not None and info["age_minutes"] <= max_age_minutes:
            return _rebuild(conn, info["captured_at"])

    board = kalshi_markets.list_open()
    snapshot.save_kalshi(conn, board, now=now)
    return board
