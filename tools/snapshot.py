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

import hashlib
import json
import sqlite3
import zlib  # used from Task 4; harmless to import now

from tools.db import utcnow, write
from tools.kalshi import markets as kalshi_markets
from tools.polymarket import markets as poly_markets

# Upsert on (platform, market_id, captured_at). Re-saving the same market
# within the same capture second overwrites rather than duplicating: a batch
# is one row per market, always. Last write wins, which is what a caller
# re-saving a market mid-pull would mean.
_INSERT = """
    INSERT INTO market_snapshots (
        platform, market_id, captured_at, title, implied_prob_yes,
        yes_bid, yes_ask, volume, open_interest, close_time, status,
        raw_json, event_json, last_seen_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (platform, market_id, captured_at) DO UPDATE SET
        title            = excluded.title,
        implied_prob_yes = excluded.implied_prob_yes,
        yes_bid          = excluded.yes_bid,
        yes_ask          = excluded.yes_ask,
        volume           = excluded.volume,
        open_interest    = excluded.open_interest,
        close_time       = excluded.close_time,
        status           = excluded.status,
        raw_json         = excluded.raw_json,
        event_json       = excluded.event_json,
        last_seen_at     = excluded.last_seen_at
"""


def payload_text(value):
    """A payload column's JSON text. Identity for TEXT rows; Task 4
    extends this to decode zlib BLOB rows."""
    return value


def _payload_key(raw_text: str | None, event_text: str | None) -> bytes:
    """Byte-exact identity of one capture's full payload.

    The design gate (2026-08-29, commit 6fe567a) measured dedup on the
    complete raw_json+event_json and ruled out field exclusions: rules
    text, close_time, everything counts. NULL event_json is distinct
    from '{}' and from 'null' by construction here.
    """
    h = hashlib.sha256()
    h.update(b"\x00" if raw_text is None else raw_text.encode("utf-8"))
    h.update(b"\x1f")
    h.update(b"\x00" if event_text is None else event_text.encode("utf-8"))
    return h.digest()


def _latest_rows(conn, platform: str) -> dict[str, tuple[str, bytes]]:
    """market_id -> (captured_at, payload key) of each market's latest row."""
    out = {}
    for row in conn.execute(
        """
        SELECT market_id, captured_at, raw_json, event_json
          FROM market_snapshots
         WHERE platform = ? AND id IN (
               SELECT MAX(id) FROM market_snapshots
                WHERE platform = ? GROUP BY market_id)
        """,
        (platform, platform),
    ):
        out[row["market_id"]] = (
            row["captured_at"],
            _payload_key(payload_text(row["raw_json"]),
                         payload_text(row["event_json"])),
        )
    return out


def _save(conn, platform: str, rows: list[tuple], stamp: str) -> int:
    """Dedup-aware write of one pull (spec 5.2 phase 2).

    Each incoming row is compared byte-exactly against the market's
    latest stored payload:
      unchanged and stamp is not older -> UPDATE last_seen_at (interval
        extends; no new row);
      anything else -> INSERT (same-second re-save still lands on the
        (platform, market_id, captured_at) upsert, last write wins).
    An *older* stamp never extends an interval backwards: it inserts as
    history, which is what a backfill save means.
    Returns rows physically written or updated (unchanged bumps count).
    """
    latest = _latest_rows(conn, platform)
    inserts, bumps = [], []
    for r in rows:
        market_id, raw_text, event_text = r[1], r[11], r[12]
        seen = latest.get(market_id)
        if (seen is not None and seen[1] == _payload_key(raw_text, event_text)
                and stamp >= seen[0]):
            bumps.append((stamp, platform, market_id))
        else:
            inserts.append(r + (stamp,))
    with write(conn):
        if inserts:
            conn.executemany(_INSERT, inserts)
        if bumps:
            conn.executemany(
                """
                UPDATE market_snapshots SET last_seen_at = MAX(last_seen_at, ?)
                 WHERE platform = ? AND market_id = ? AND id = (
                       SELECT MAX(id) FROM market_snapshots
                        WHERE platform = ? AND market_id = ?)
                """,
                [(s, p, m, p, m) for s, p, m in bumps],
            )
    return len(inserts) + len(bumps)


# Kalshi's own status strings (see kalshi_markets.OPEN_STATUSES and
# normalize()'s is_open) mapped onto the three-state open|closed|settled
# column defined by db/schema.sql and the design spec. Kalshi genuinely has
# a third state — closed but not yet settled — that a strict is_open/else
# binary would collapse into "settled" incorrectly.
_SETTLED_STATUSES = {"finalized", "settled"}


def _kalshi_snapshot_status(m) -> str:
    status = m.status
    if status in kalshi_markets.OPEN_STATUSES:
        return "open"
    if status in _SETTLED_STATUSES:
        return "settled"
    return "closed"


# Snapshots store the market's COMPLETE raw payload.
#
# An earlier version projected it down to the fields `normalize` reads, to
# save ~98 MB per 100k-market pull (about half the payload). That was a bad
# trade and the mistake is worth recording: the projection was scoped from
# what the *current code* reads, which quietly makes today's code the ceiling
# on tomorrow's questions. It dropped `previous_yes_bid_dollars` and
# friends -- the 24h-prior prices that ARE momentum, which insider_bias's own
# stage-2 warning signs tell a session to check -- along with
# `yes_bid_size_fp`/`yes_ask_size_fp` (order-book depth, what `find-edge`'s
# executability filter actually wants) and `can_close_early` /
# `early_close_condition` (whether the resolution source can miss the close).
#
# Kalshi sends 42 fields, ~2 KB per market. Storing all of them costs ~200 MB
# per pull and keeps every future question answerable. If space ever does bind,
# drop whole old snapshot BATCHES rather than trimming fields: losing a day of
# history is a decision you can see and reverse by not repeating it, whereas a
# field trimmed out of every row is gone silently and forever.


def save_kalshi(
    conn: sqlite3.Connection, markets: list, now: str | None = None
) -> int:
    """Persist normalized Kalshi markets. Returns rows written."""
    stamp = now or utcnow()
    rows = [
        (
            "kalshi",
            m.ticker,
            stamp,
            m.title,
            # This is the market MID, not an executable price — anything
            # that needs an actual entry price for a bet must use yes_ask
            # (or yes_bid for the NO side), never this column.
            m.mid,
            m.yes_bid,
            m.yes_ask,
            m.volume,
            m.open_interest,
            m.close_time,
            _kalshi_snapshot_status(m),
            json.dumps(m.raw or {}),
            # None, not "{}": a capture with no envelope must stay
            # distinguishable from an envelope that was genuinely empty.
            json.dumps(m.event) if getattr(m, "event", None) else None,
        )
        for m in markets
    ]
    if not rows:
        return 0
    return _save(conn, "kalshi", rows, stamp)


def save_polymarket(
    conn: sqlite3.Connection, markets: list, now: str | None = None
) -> int:
    """Persist normalized Polymarket markets. Returns rows written."""
    stamp = now or utcnow()
    rows = [
        (
            "polymarket",
            m.market_id,
            stamp,
            m.question,
            m.implied_prob_yes,
            m.best_bid,
            m.best_ask,
            m.volume,
            None,
            m.end_date,
            "settled" if m.closed else "open",
            json.dumps(m.raw),
            None,          # Polymarket has no Kalshi event envelope.
        )
        for m in markets
    ]
    if not rows:
        return 0
    return _save(conn, "polymarket", rows, stamp)


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
