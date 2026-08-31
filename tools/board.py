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

A rebuilt board is identical to a fetched one, `market.raw` included:
snapshots store the complete Kalshi payload, so a cache hit and a forced
fetch hand back the same shape. That matters more than it sounds — a cache
that returned a thinner `raw` would make any theory reading an uncommon field
work on a forced pull and silently return `None` on a cached one.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import datetime

from tools import snapshot
from tools.db import utcnow
from tools.domain import Market
from tools.kalshi import markets as kalshi_markets

#: How old the freshest snapshot may be before `get_board` refetches.
#: Four hours is chosen to cover a long working session while guaranteeing a
#: new session the next morning gets fresh prices.
DEFAULT_MAX_AGE_MINUTES = 240

#: The floor `force=True` honours. Ruled 2026-08-29 (enforcing-surfaces
#: spec 5.3): with 4-5 concurrent sessions, unconditional force makes
#: them reason over *different* boards; a board younger than this is the
#: session's board, force or not. Re-quoting a handful of tickers is
#: `markets.quotes()`, which no floor touches.
FORCE_FLOOR_MINUTES = 30


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def board_info(conn: sqlite3.Connection, now: str | None = None) -> dict | None:
    """Age and size of the freshest stored board, or None if there is none.

    A pull where nothing changed writes no rows (spec 5.2 phase 2), so
    the board is not "rows sharing one captured_at": it is the rows
    whose interval reaches the latest pull stamp. `captured_at` in the
    returned dict is that pull stamp (kept under its old key: it is the
    batch identity every caller already treats it as).
    """
    row = conn.execute(
        """
        SELECT MAX(last_seen_at) AS stamp, COUNT(*) AS n
          FROM market_snapshots
         WHERE platform = 'kalshi'
           AND last_seen_at = (SELECT MAX(last_seen_at)
                                 FROM market_snapshots
                                WHERE platform = 'kalshi')
        """
    ).fetchone()
    if row is None or row["stamp"] is None:
        return None
    age = (_parse(now or utcnow()) - _parse(row["stamp"])).total_seconds()
    return {"captured_at": row["stamp"], "markets": row["n"],
            "age_minutes": age / 60.0}


def _rebuild(conn: sqlite3.Connection, stamp: str) -> list[Market]:
    """Reconstruct normalized markets from the rows holding one pull stamp.

    Under interval semantics a row's `last_seen_at` is the latest pull
    that observed it, so the rows composing pull `stamp` are the ones
    whose interval reaches exactly that stamp -- not the ones inserted at
    that captured_at, which an unchanged pull may not have inserted any
    of at all.
    """
    rows = conn.execute(
        """
        SELECT raw_json, event_json FROM market_snapshots
         WHERE platform = 'kalshi' AND last_seen_at = ?
        """,
        (stamp,),
    ).fetchall()
    out = []
    for row in rows:
        raw = json.loads(snapshot.payload_text(row["raw_json"]) or "{}")
        if not raw.get("ticker"):
            # A snapshot written before raw_json carried a ticker cannot be
            # rebuilt. Fail loudly rather than return a short board that
            # looks complete -- a screen reading it would silently under-run.
            raise ValueError(
                f"snapshot batch {stamp} has rows with no ticker in "
                "raw_json and cannot be rebuilt into a board. Re-fetch with "
                "get_board(conn, force=True)."
            )
        market = kalshi_markets.normalize(
            raw,
            json.loads(snapshot.payload_text(row["event_json"]) or "null"))
        # `list_open` patches series/event identity onto each market from
        # its event envelope; the snapshot stores only the market's own raw
        # payload, where those fields are absent. Without this derivation a
        # rebuilt board has series_ticker=None on every market, which
        # silently disables anything that classifies by family --
        # discovered 2026-08-26 when gate.py passed 349/349 events on a
        # cached board after passing 100/349 on the same board freshly
        # fetched. Kalshi tickers embed the identity (SERIES-EVENT-STRIKE),
        # so derive what the payload does not carry.
        ticker = market.ticker
        patch = {}
        if not market.series_ticker:
            patch["series_ticker"] = ticker.split("-", 1)[0]
        if not market.event_ticker and "-" in ticker:
            patch["event_ticker"] = ticker.rsplit("-", 1)[0]
        if patch:
            market = replace(market, **patch)
        out.append(market)
    return out


def get_board(
    conn: sqlite3.Connection,
    *,
    max_age_minutes: float = DEFAULT_MAX_AGE_MINUTES,
    force: bool = False,
    now: str | None = None,
) -> list[Market]:
    """The complete Kalshi board, fetching only if what is stored is stale.

    Every theory should call this rather than `markets.list_open()`, so one
    session makes one pull. Pass `force=True` for the deliberate session-start
    refresh (`go`'s Orient step) or when a price is known to have moved and
    freshness genuinely matters — re-quoting a handful of tickers before
    betting is `markets.quotes()`, which is cheaper than any board pull.
    A board younger than FORCE_FLOOR_MINUTES is reused even under force
    (ruled 2026-08-29) — unless `max_age_minutes` was explicitly passed
    tighter than the floor, in which case that tighter bound wins.

    A fetch is always snapshotted, so the pull is never lost.
    """
    info = board_info(conn, now=now)
    # force means "refresh unless this is basically the board I already
    # have," not "ignore what the caller asked for." An explicitly tighter
    # max_age_minutes than the floor is still honoured -- min(), not a flat
    # override -- so force never becomes less strict than a plain max_age
    # would have been. No caller passes both today, so this only ever
    # narrows the floor.
    floor = min(max_age_minutes, FORCE_FLOOR_MINUTES) if force else max_age_minutes
    if info is not None and info["age_minutes"] <= floor:
        return _rebuild(conn, info["captured_at"])

    board = kalshi_markets.list_open()
    snapshot.save_kalshi(conn, board, now=now)
    return board
