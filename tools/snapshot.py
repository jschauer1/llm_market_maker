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
import zlib

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
        -- MAX(), not a plain overwrite: a same-second changed payload
        -- must never regress an interval a prior bump had already
        -- extended past this captured_at (spec 5.2 phase 2, controller
        -- ruling 2026-08-30).
        last_seen_at     = MAX(last_seen_at, excluded.last_seen_at)
"""


def payload_text(value):
    """A payload column's JSON text, whatever its stored codec.

    The cell's TYPE is the codec (spec 5.2 phase 3 allows a codec column
    or a sniff; the sqlite value type is the sniff with no magic bytes):
    TEXT rows are pre-compression plain JSON and pass through; BLOB rows
    are zlib. None stays None. ALL reads of raw_json/event_json go
    through here -- a direct json.loads() on the column breaks on any row
    written after 2026-08-30.
    """
    if value is None or isinstance(value, str):
        return value
    return zlib.decompress(bytes(value)).decode("utf-8")


def _encode(text: str | None):
    """The write-side codec: plain JSON text -> a zlib BLOB, None -> None.

    Every new write goes through this; `payload_text` above is its
    inverse and is what every reader must go through instead of trusting
    the column's stored type.
    """
    return None if text is None else zlib.compress(text.encode("utf-8"))


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


def _latest_rows(conn, platform: str) -> dict[str, tuple[int, str, str, bytes]]:
    """market_id -> (id, captured_at, last_seen_at, payload key) of the
    market's latest row.

    Returning `id` (rather than deriving it again at write time) is what
    lets every write below target `WHERE id = ?` directly -- no subquery
    re-resolves "the latest row" after other rows in the same batch have
    already been written, which is what let a same-batch bump mis-target
    a row this same call had just inserted (review finding, 2026-08-30).
    """
    out = {}
    for row in conn.execute(
        """
        SELECT id, market_id, captured_at, last_seen_at, raw_json, event_json
          FROM market_snapshots
         WHERE platform = ? AND id IN (
               SELECT MAX(id) FROM market_snapshots
                WHERE platform = ? GROUP BY market_id)
        """,
        (platform, platform),
    ):
        out[row["market_id"]] = (
            row["id"],
            row["captured_at"],
            row["last_seen_at"],
            _payload_key(payload_text(row["raw_json"]),
                         payload_text(row["event_json"])),
        )
    return out


def _save(conn, platform: str, rows: list[tuple], stamp: str) -> int:
    """Dedup-aware write of one pull (spec 5.2 phase 2).

    The incoming batch is deduped by market_id first, last occurrence
    wins -- the same "last write wins" rule `_INSERT`'s own comment
    already documents for a market re-saved mid-pull. Deciding once per
    market, rather than once per incoming row, is what stops an
    unchanged-then-changed pair for one ticker inside a single batch from
    producing an insert immediately followed by a bump that targets the
    row the insert just wrote (review finding, 2026-08-30).

    Reading "the latest row per market" and deciding what to do about it
    happen inside one `BEGIN IMMEDIATE` transaction together with the
    writes, so a second writer cannot decide from a snapshot the first is
    about to invalidate -- without it, two concurrent callers could both
    read the same latest row, and a bump from one could land on a row the
    other had just inserted (review finding, 2026-08-30). `write()` is not
    used here because it does not itself open the transaction; the explicit
    BEGIN IMMEDIATE must happen before `_latest_rows` reads, and `write()`
    only wraps writes it is handed after entry. Commit/rollback are
    therefore handled directly, mirroring what `write()` does.

    Per market, given the incoming (stamp, new_key) and the latest known
    row (id, cap=captured_at, reach=last_seen_at, key):
      no latest row                       -> INSERT (cap=reach=stamp).
      new_key == key and stamp >= cap     -> UPDATE last_seen_at =
        MAX(last_seen_at, stamp) WHERE id -- the interval extends, no new
        row.
      new_key == key and stamp < cap      -> INSERT: an unchanged payload
        at a stamp older than the row's own capture is history, not an
        extension.
      new_key != key and stamp == cap     -> INSERT, which lands on the
        (platform, market_id, captured_at) unique key and upserts in
        place (same-second last-write-wins); its DO UPDATE folds
        last_seen_at forward with MAX() rather than overwriting, so a
        same-second changed payload can never regress an interval a prior
        bump had already extended.
      new_key != key and stamp == reach   -> the contested second's
        (reach > cap)                        payload is ambiguous between
        the two captures that both claim it: the surviving row is
        retracted to its own cap (UPDATE last_seen_at = cap WHERE id --
        it was never actually unchanged at this stamp) and the new
        payload gets its own row (cap=reach=stamp). This matches the
        pre-dedup upsert outcome for a plain two-save sequence, and it
        forgets any bump stamps strictly between cap and reach -- a
        bounded, same-second-conflict-only information loss, accepted by
        controller ruling 2026-08-30.
      anything else (out-of-order stamp,  -> plain INSERT. Production
        different payload)                   stamps are monotone
        (`utcnow()`), so this combination -- and the overlapping interval
        it can leave behind -- only arises from test-style backfills
        that pass an out-of-order `now=`, accepted by controller ruling
        2026-08-30.

    Returns rows physically written or updated (unchanged bumps count).
    """
    deduped: dict[str, tuple] = {}
    for r in rows:
        deduped[r[1]] = r          # market_id -> row; last occurrence wins
    rows = list(deduped.values())

    conn.execute("BEGIN IMMEDIATE")
    try:
        latest = _latest_rows(conn, platform)
        inserts, bumps, retractions = [], [], []
        for r in rows:
            # Incoming row layout (`save_kalshi`/`save_polymarket`): r[0:11]
            # = platform..status (11 plain columns), r[11] = raw_json text,
            # r[12] = event_json text -- always plain text at this point,
            # never yet encoded. `_INSERT`'s columns are those 11, then
            # raw_json, event_json, last_seen_at (14 total), so an insert
            # tuple is r[:11] + (encoded raw, encoded event, stamp).
            # Identity is decided on the DECODED text (cross-codec: a
            # legacy TEXT row and a fresh compressed re-save of the same
            # payload must hash equal), and only the surviving inserts pay
            # to encode -- a bump never touches the payload columns at all.
            market_id, raw_text, event_text = r[1], r[11], r[12]
            new_key = _payload_key(raw_text, event_text)
            seen = latest.get(market_id)
            if seen is None:
                inserts.append(
                    r[:11] + (_encode(raw_text), _encode(event_text), stamp))
                continue
            row_id, cap, reach, key = seen
            if new_key == key and stamp >= cap:
                bumps.append((stamp, row_id))
            elif new_key == key:                       # stamp < cap
                inserts.append(
                    r[:11] + (_encode(raw_text), _encode(event_text), stamp))
            elif stamp == reach and reach > cap:
                retractions.append((cap, row_id))
                inserts.append(
                    r[:11] + (_encode(raw_text), _encode(event_text), stamp))
            else:                    # stamp == cap, or out-of-order+changed
                inserts.append(
                    r[:11] + (_encode(raw_text), _encode(event_text), stamp))
        if retractions:
            conn.executemany(
                "UPDATE market_snapshots SET last_seen_at = ? WHERE id = ?",
                retractions,
            )
        if inserts:
            conn.executemany(_INSERT, inserts)
        if bumps:
            conn.executemany(
                "UPDATE market_snapshots"
                " SET last_seen_at = MAX(last_seen_at, ?) WHERE id = ?",
                bumps,
            )
    except BaseException:
        conn.rollback()
        raise
    conn.commit()
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


def dedup_history(conn: sqlite3.Connection, batch_markets: int = 2000) -> dict:
    """Collapse consecutive byte-identical rows per market (spec 5.2).

    For each (platform, market_id) -- not market_id alone: `history_for`
    and every other reader in this module scope a "market" by the pair,
    and grouping on market_id alone would interleave a Kalshi and a
    Polymarket row that happen to share an id string -- walk its rows
    oldest-first; a row whose full payload (raw_json + event_json,
    byte-exact -- the design gate ruled out field exclusions) equals its
    immediate predecessor's is deleted and the predecessor's last_seen_at
    absorbs its stamp. Only consecutive equals collapse: a reverted
    payload is a new observation.

    A collapsed keeper's last_seen_at is the MAX over every stamp in its
    chain, including a reach a doomed row had already accumulated from
    Task 2's write-path bumps (a row can carry last_seen_at > captured_at
    before it is ever touched here) -- never just the chain's captured_at
    values. String-max on ISO-8601 UTC stamps (`YYYY-MM-DDTHH:MM:SSZ`,
    fixed width) sorts chronologically, so plain `max()` on the text is
    exact.

    Absorption never widens pre-existing interval ambiguity (carried
    finding, Task 3 review). Out-of-order test-style writes (accepted by
    controller ruling 2026-08-30 -- see `_save`'s own docstring) can leave
    one row's last_seen_at already reaching past a *later*, different-key
    row's captured_at: a point-in-time query at an instant in that overlap
    already matches two rows before this function ever runs. The MAX()
    above only ever carries forward a reach some row in the collapsed run
    already carried -- it is never assembled from parts that individually
    fell short of the contested instant -- so collapsing that run leaves
    the same instant matching the same count of rows afterward, just via
    the keeper instead of the row that gets deleted. This matters because
    a widened ambiguity would be silent: nothing rejects an extra match,
    it would simply make a point-in-time read (`test_point_in_time_
    resolves_via_the_interval`'s whole guarantee) nondeterministic between
    two payloads instead of one. See `test_dedup_history_absorption_
    never_widens_interval_ambiguity` for the constructed regression.

    Incremental and idempotent (data conventions): commits per batch of
    markets, so an interrupted run resumes by simply re-running --
    already collapsed markets yield nothing on the second pass.
    """
    stats = {"markets": 0, "deleted": 0, "kept": 0}
    market_ids = [
        (r[0], r[1]) for r in conn.execute(
            "SELECT DISTINCT platform, market_id FROM market_snapshots"
            " ORDER BY platform, market_id"
        )
    ]
    for i in range(0, len(market_ids), batch_markets):
        chunk = market_ids[i:i + batch_markets]
        with write(conn):
            for platform, mid in chunk:
                rows = conn.execute(
                    "SELECT id, captured_at, last_seen_at, raw_json,"
                    " event_json FROM market_snapshots"
                    " WHERE platform = ? AND market_id = ?"
                    " ORDER BY captured_at, id",
                    (platform, mid)).fetchall()
                stats["markets"] += 1
                keeper, keeper_key, keeper_reach = None, None, None
                doomed, reaches = [], {}
                for row in rows:
                    key = _payload_key(payload_text(row["raw_json"]),
                                       payload_text(row["event_json"]))
                    if keeper is not None and key == keeper_key:
                        doomed.append(row["id"])
                        keeper_reach = max(keeper_reach,
                                           row["last_seen_at"] or
                                           row["captured_at"])
                        reaches[keeper] = keeper_reach
                    else:
                        keeper, keeper_key = row["id"], key
                        keeper_reach = (row["last_seen_at"] or
                                        row["captured_at"])
                for kid, reach in reaches.items():
                    conn.execute(
                        "UPDATE market_snapshots SET last_seen_at = ?"
                        " WHERE id = ?", (reach, kid))
                if doomed:
                    conn.executemany(
                        "DELETE FROM market_snapshots WHERE id = ?",
                        [(d,) for d in doomed])
                stats["deleted"] += len(doomed)
                stats["kept"] += len(rows) - len(doomed)
    return stats


def compress_history(conn: sqlite3.Connection, batch_rows: int = 20000) -> dict:
    """Convert plain-text payload rows to zlib BLOBs, in batches.

    Incremental and idempotent (data conventions): each batch selects only
    rows still TEXT-typed via sqlite's own `typeof()`, so an interrupted
    run resumes where it stopped rather than re-scanning or re-compressing
    what an earlier batch already converted. `bytes_before`/`bytes_after`
    are measured only over the rows this call actually touched, which is
    what makes the JSON-only compression ratio it reports meaningful
    (measured ~8x on this project's payloads) rather than diluted by rows
    that were already BLOB.
    """
    stats = {"compressed": 0, "already": 0,
             "bytes_before": 0, "bytes_after": 0}
    while True:
        rows = conn.execute(
            "SELECT id, raw_json, event_json FROM market_snapshots"
            " WHERE typeof(raw_json) = 'text'"
            "    OR typeof(event_json) = 'text'"
            " LIMIT ?", (batch_rows,)).fetchall()
        if not rows:
            break
        updates = []
        for row in rows:
            raw, event = row["raw_json"], row["event_json"]
            before = (len(raw) if isinstance(raw, str) else 0) + \
                     (len(event) if isinstance(event, str) else 0)
            raw_out = _encode(raw) if isinstance(raw, str) else raw
            event_out = _encode(event) if isinstance(event, str) else event
            after = (len(raw_out) if isinstance(raw_out, bytes) else 0) + \
                    (len(event_out) if isinstance(event_out, bytes) else 0)
            stats["bytes_before"] += before
            stats["bytes_after"] += after
            updates.append((raw_out, event_out, row["id"]))
        with write(conn):
            conn.executemany(
                "UPDATE market_snapshots SET raw_json = ?, event_json = ?"
                " WHERE id = ?", updates)
        stats["compressed"] += len(updates)
    stats["already"] = conn.execute(
        "SELECT COUNT(*) FROM market_snapshots").fetchone()[0] - stats["compressed"]
    return stats


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
