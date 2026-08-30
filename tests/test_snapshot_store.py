import json
import zlib

import pytest

from tools import board, db, snapshot
from tools.kalshi import markets as kalshi_markets

NOW = "2026-08-24T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def _mk(ticker, **kw):
    raw = {
        "ticker": ticker, "event_ticker": "EV", "series_ticker": "KXTHING",
        "title": f"title {ticker}", "status": "active",
        "close_time": "2026-09-01T00:00:00Z",
        "yes_bid_dollars": "0.80", "yes_ask_dollars": "0.82",
        "no_bid_dollars": "0.18", "no_ask_dollars": "0.20",
        "volume_fp": "900", "open_interest_fp": "500",
    }
    raw.update(kw)
    return kalshi_markets.normalize(raw)


def test_unchanged_resave_extends_the_interval_instead_of_inserting(conn):
    # The 56.5%-measured waste (spec 5.2): a market that moved nothing
    # used to write a full new row every pull. Now the existing row's
    # validity interval absorbs the pull.
    snapshot.save_kalshi(conn, [_mk("T-0")], now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0")], now=NOW)
    rows = conn.execute(
        "SELECT captured_at, last_seen_at FROM market_snapshots"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["captured_at"] == "2026-08-24T11:00:00Z"
    assert rows[0]["last_seen_at"] == NOW


def test_changed_payload_still_inserts_a_new_row(conn):
    snapshot.save_kalshi(conn, [_mk("T-0")], now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0", yes_ask_dollars="0.90")], now=NOW)
    rows = conn.execute(
        "SELECT captured_at, last_seen_at FROM market_snapshots"
        " ORDER BY captured_at"
    ).fetchall()
    assert len(rows) == 2
    # The old row's interval is NOT extended by a changed pull.
    assert rows[0]["last_seen_at"] == "2026-08-24T11:00:00Z"
    assert rows[1]["captured_at"] == rows[1]["last_seen_at"] == NOW


def test_unchanged_only_means_byte_exact_full_payload(conn):
    # Design gate (6fe567a): rules text, close_time — everything — counts.
    # A change in a field no material column carries must still insert.
    snapshot.save_kalshi(conn, [_mk("T-0", rules_primary="old rules")],
                         now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0", rules_primary="NEW rules")],
                         now=NOW)
    n = conn.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
    assert n == 2


def test_out_of_order_stamp_never_regresses_last_seen_at(conn):
    # Tests pass historical now= stamps; an "unchanged" save with an older
    # stamp must not shrink the interval or collapse history.
    snapshot.save_kalshi(conn, [_mk("T-0")], now=NOW)
    snapshot.save_kalshi(conn, [_mk("T-0")], now="2026-08-23T12:00:00Z")
    rows = conn.execute(
        "SELECT captured_at, last_seen_at FROM market_snapshots"
        " ORDER BY captured_at"
    ).fetchall()
    assert len(rows) == 2          # older stamp inserts as history
    assert rows[1]["last_seen_at"] == NOW


def test_point_in_time_resolves_via_the_interval(conn):
    # The structural-gate guarantee (spec 5.2): market text at time T is
    # the row whose [captured_at, last_seen_at] spans T.
    snapshot.save_kalshi(conn, [_mk("T-0", rules_primary="v1")],
                         now="2026-08-24T10:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0", rules_primary="v1")],
                         now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0", rules_primary="v2")], now=NOW)
    t = "2026-08-24T10:30:00Z"
    row = conn.execute(
        "SELECT raw_json FROM market_snapshots"
        " WHERE platform='kalshi' AND market_id='T-0'"
        "   AND captured_at <= ? AND last_seen_at >= ?",
        (t, t),
    ).fetchone()
    assert json.loads(
        snapshot.payload_text(row["raw_json"]))["rules_primary"] == "v1"


def test_board_reports_the_pull_even_when_nothing_changed(conn):
    # A pull where every market is unchanged writes no row; the board must
    # still be that pull: full size, fresh age.
    snapshot.save_kalshi(conn, [_mk("T-0"), _mk("T-1")],
                         now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0"), _mk("T-1")], now=NOW)
    info = board.board_info(conn, now=NOW)
    assert info["markets"] == 2
    assert info["age_minutes"] == pytest.approx(0.0)
    got = board.get_board(conn, now=NOW)
    assert sorted(m.ticker for m in got) == ["T-0", "T-1"]


def test_mixed_pull_rebuilds_current_rows_only(conn):
    # One market changed, one didn't, one left the board: the rebuilt
    # board is exactly the pull's two markets at their current payloads.
    snapshot.save_kalshi(
        conn, [_mk("T-0"), _mk("T-1"), _mk("T-GONE")],
        now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(
        conn, [_mk("T-0"), _mk("T-1", yes_ask_dollars="0.95")], now=NOW)
    got = board.get_board(conn, now=NOW)
    assert sorted(m.ticker for m in got) == ["T-0", "T-1"]
    assert {m.ticker: m.yes_ask for m in got}["T-1"] == pytest.approx(0.95)


def test_backfill_gives_legacy_rows_their_captured_at(conn):
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots"
            " (platform, market_id, captured_at, title, raw_json,"
            "  last_seen_at)"
            " VALUES ('kalshi', 'L-1', ?, 't', '{}', NULL)", (NOW,))
    db.init_db(conn)
    row = conn.execute(
        "SELECT last_seen_at FROM market_snapshots WHERE market_id='L-1'"
    ).fetchone()
    assert row["last_seen_at"] == NOW


# --- review fixes, 2026-08-30: id-targeted decisions, one per market ---


def test_reviewer_repro_three_saves_land_on_one_row_per_market(conn):
    # CRITICAL review finding: save(v1)@t1 -> insert; save(v1)@t2 -> bump
    # (row: cap=t1, reach=t2); save(v2)@t2 -> the old code saw a changed
    # payload whose stamp didn't collide with the row's OWN captured_at,
    # so it inserted a SECOND row also carrying last_seen_at=t2, and
    # board._rebuild returned ["T-0", "T-0"]. Exactly one row must carry
    # the max stamp per market.
    t1, t2 = "2026-08-24T10:00:00Z", "2026-08-24T11:00:00Z"
    snapshot.save_kalshi(conn, [_mk("T-0")], now=t1)
    snapshot.save_kalshi(conn, [_mk("T-0")], now=t2)
    snapshot.save_kalshi(conn, [_mk("T-0", yes_ask_dollars="0.90")], now=t2)

    on_max_stamp = conn.execute(
        "SELECT COUNT(*) FROM market_snapshots"
        " WHERE market_id = 'T-0' AND last_seen_at = ?", (t2,),
    ).fetchone()[0]
    assert on_max_stamp == 1

    got = board.get_board(conn, now=t2)
    assert [m.ticker for m in got] == ["T-0"]
    assert got[0].yes_ask == pytest.approx(0.90)


def test_in_batch_duplicate_ticker_decides_once_last_copy_wins(conn):
    # CRITICAL review finding, variant 2: one batch holding both an
    # unchanged and a changed copy of the same ticker used to queue a
    # bump for the unchanged copy and an insert for the changed one
    # against the same pre-batch snapshot; the bump's dynamic
    # `id = (SELECT MAX(id) ...)` then resolved AFTER the insert had
    # already run and landed on the row the insert had just written.
    # Deduping the batch per market first (last occurrence wins) means
    # only one decision is ever made, so this can no longer happen.
    snapshot.save_kalshi(conn, [_mk("T-0")], now="2026-08-24T10:00:00Z")
    unchanged = _mk("T-0")
    changed = _mk("T-0", yes_ask_dollars="0.77")
    n = snapshot.save_kalshi(conn, [unchanged, changed], now=NOW)
    assert n == 1                       # one decision, not two

    rows = conn.execute(
        "SELECT captured_at, last_seen_at, yes_ask FROM market_snapshots"
        " WHERE market_id = 'T-0' ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    # The original row is untouched -- no mis-targeted bump reached it.
    assert (rows[0]["captured_at"] == rows[0]["last_seen_at"]
            == "2026-08-24T10:00:00Z")
    # The last copy in the batch is the one that landed.
    assert rows[1]["captured_at"] == rows[1]["last_seen_at"] == NOW
    assert rows[1]["yes_ask"] == pytest.approx(0.77)


def test_contested_second_retracts_the_superseded_row_to_its_own_cap(conn):
    # Controller ruling's disambiguation for a stamp two payloads both
    # claim: the surviving row's interval is retracted back to its own
    # captured_at -- it was never actually unchanged at the contested
    # stamp -- and the new payload gets a fresh row alone on that stamp.
    t1, t2 = "2026-08-24T10:00:00Z", "2026-08-24T11:00:00Z"
    snapshot.save_kalshi(conn, [_mk("T-0")], now=t1)
    snapshot.save_kalshi(conn, [_mk("T-0")], now=t2)          # bump to t2
    snapshot.save_kalshi(conn, [_mk("T-0", yes_ask_dollars="0.90")], now=t2)

    rows = conn.execute(
        "SELECT captured_at, last_seen_at FROM market_snapshots"
        " WHERE market_id = 'T-0' ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    old, new = rows
    assert old["captured_at"] == old["last_seen_at"] == t1     # retracted
    assert new["captured_at"] == new["last_seen_at"] == t2     # alone on t2


# --- dedup_history: retro-collapse of legacy rows (spec 5.2 phase 2) ---


def _insert_legacy(conn, market_id, captured_at, raw, event=None):
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots (platform, market_id, captured_at,"
            " raw_json, event_json, last_seen_at) VALUES"
            " ('kalshi', ?, ?, ?, ?, ?)",
            (market_id, captured_at, raw, event, captured_at))


def test_dedup_history_collapses_consecutive_identical_rows(conn):
    _insert_legacy(conn, "H-1", "2026-08-20T10:00:00Z", '{"a":1}')
    _insert_legacy(conn, "H-1", "2026-08-20T11:00:00Z", '{"a":1}')
    _insert_legacy(conn, "H-1", "2026-08-20T12:00:00Z", '{"a":1}')
    _insert_legacy(conn, "H-1", "2026-08-20T13:00:00Z", '{"a":2}')
    stats = snapshot.dedup_history(conn)
    assert stats["deleted"] == 2
    rows = conn.execute(
        "SELECT captured_at, last_seen_at, raw_json FROM market_snapshots"
        " ORDER BY captured_at").fetchall()
    assert len(rows) == 2
    # The survivor's interval absorbed both deleted stamps.
    assert rows[0]["captured_at"] == "2026-08-20T10:00:00Z"
    assert rows[0]["last_seen_at"] == "2026-08-20T12:00:00Z"
    assert rows[1]["captured_at"] == "2026-08-20T13:00:00Z"


def test_dedup_history_keeps_a_reverted_payload(conn):
    # a -> b -> a is three observations, not two: only CONSECUTIVE equals
    # collapse, or the reversion at 12:00 would be erased from history.
    _insert_legacy(conn, "H-2", "2026-08-20T10:00:00Z", '{"p":"a"}')
    _insert_legacy(conn, "H-2", "2026-08-20T11:00:00Z", '{"p":"b"}')
    _insert_legacy(conn, "H-2", "2026-08-20T12:00:00Z", '{"p":"a"}')
    stats = snapshot.dedup_history(conn)
    assert stats["deleted"] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM market_snapshots").fetchone()[0] == 3


def test_dedup_history_distinguishes_null_event_from_empty(conn):
    _insert_legacy(conn, "H-3", "2026-08-20T10:00:00Z", '{"a":1}', None)
    _insert_legacy(conn, "H-3", "2026-08-20T11:00:00Z", '{"a":1}', "{}")
    assert snapshot.dedup_history(conn)["deleted"] == 0


def test_dedup_history_is_idempotent(conn):
    _insert_legacy(conn, "H-4", "2026-08-20T10:00:00Z", '{"a":1}')
    _insert_legacy(conn, "H-4", "2026-08-20T11:00:00Z", '{"a":1}')
    assert snapshot.dedup_history(conn)["deleted"] == 1
    assert snapshot.dedup_history(conn)["deleted"] == 0


def test_dedup_history_preserves_point_in_time_reads(conn):
    _insert_legacy(conn, "H-5", "2026-08-20T10:00:00Z", '{"r":"v1"}')
    _insert_legacy(conn, "H-5", "2026-08-20T11:00:00Z", '{"r":"v1"}')
    _insert_legacy(conn, "H-5", "2026-08-20T12:00:00Z", '{"r":"v2"}')
    snapshot.dedup_history(conn)
    t = "2026-08-20T11:00:00Z"
    row = conn.execute(
        "SELECT raw_json FROM market_snapshots WHERE market_id='H-5'"
        " AND captured_at <= ? AND last_seen_at >= ?", (t, t)).fetchone()
    assert json.loads(snapshot.payload_text(row["raw_json"]))["r"] == "v1"


def test_dedup_history_never_collapses_across_platforms(conn):
    # H-6 exists on both platforms with byte-identical payloads. Grouping
    # by market_id alone (ignoring platform) would see them as one
    # market's two consecutive observations and delete the later one --
    # every other reader in this module (history_for, _latest_rows) scopes
    # a "market" by (platform, market_id), and dedup_history must match.
    _insert_legacy(conn, "H-6", "2026-08-20T10:00:00Z", '{"a":1}')
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots (platform, market_id,"
            " captured_at, raw_json, event_json, last_seen_at) VALUES"
            " ('polymarket', 'H-6', '2026-08-20T11:00:00Z', '{\"a\":1}',"
            " NULL, '2026-08-20T11:00:00Z')")
    stats = snapshot.dedup_history(conn)
    assert stats["deleted"] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM market_snapshots WHERE market_id = 'H-6'"
    ).fetchone()[0] == 2


def _insert_with_reach(conn, market_id, captured_at, raw, last_seen_at):
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots (platform, market_id, captured_at,"
            " raw_json, last_seen_at) VALUES ('kalshi', ?, ?, ?, ?)",
            (market_id, captured_at, raw, last_seen_at))


def test_dedup_history_absorption_never_widens_interval_ambiguity(conn):
    # Carried finding, Task 3 review: dedup_history's docstring now states
    # the property this pins -- absorbing a doomed row's reach into its
    # keeper must never make a point-in-time query MORE ambiguous than it
    # already was. Out-of-order test-style writes (accepted by controller
    # ruling 2026-08-30, see _save's own docstring) can leave a row's
    # last_seen_at already reaching past a LATER, different-key row's
    # captured_at -- an ambiguity that predates dedup_history entirely.
    t1 = "2026-08-20T10:00:00Z"
    t2 = "2026-08-20T11:00:00Z"
    t3 = "2026-08-20T12:00:00Z"     # the contested instant
    t4 = "2026-08-20T13:00:00Z"
    _insert_with_reach(conn, "H-7", t1, '{"a":1}', t1)
    # Out-of-order write: this row's own last_seen_at (t4) already reaches
    # past H-7's later, different-payload row's captured_at (t3) -- before
    # dedup_history ever runs, a point-in-time query at t3 already matches
    # two rows (this one and the one below).
    _insert_with_reach(conn, "H-7", t2, '{"a":1}', t4)
    _insert_with_reach(conn, "H-7", t3, '{"a":2}', t3)

    def matches_at(t):
        return conn.execute(
            "SELECT COUNT(*) FROM market_snapshots WHERE market_id='H-7'"
            " AND captured_at <= ? AND last_seen_at >= ?", (t, t),
        ).fetchone()[0]

    before = matches_at(t3)
    snapshot.dedup_history(conn)      # collapses t1/t2 (same payload)
    after = matches_at(t3)
    assert before == after == 2


def test_payload_text_decodes_blob_and_passes_text_and_none(conn):
    assert snapshot.payload_text(None) is None
    assert snapshot.payload_text('{"a":1}') == '{"a":1}'
    blob = zlib.compress('{"a":1}'.encode("utf-8"))
    assert snapshot.payload_text(blob) == '{"a":1}'
    assert snapshot.payload_text(memoryview(blob)) == '{"a":1}'


def test_new_saves_store_compressed_payloads(conn):
    snapshot.save_kalshi(conn, [_mk("C-0")], now=NOW)
    row = conn.execute(
        "SELECT raw_json FROM market_snapshots").fetchone()
    assert isinstance(row["raw_json"], bytes)          # BLOB = zlib codec
    assert json.loads(snapshot.payload_text(row["raw_json"]))["ticker"] == "C-0"


def test_dedup_compares_across_codecs(conn):
    # A plain-text legacy row and a compressed re-save of the SAME payload
    # must still count as unchanged: identity is the decoded text.
    raw = '{"ticker": "X-1", "v": 1}'
    _insert_legacy(conn, "X-1", "2026-08-24T11:00:00Z", raw)
    key_old = snapshot._payload_key(raw, None)
    key_new = snapshot._payload_key(
        snapshot.payload_text(zlib.compress(raw.encode("utf-8"))), None)
    assert key_old == key_new


def test_compress_history_converts_text_rows_in_place(conn):
    _insert_legacy(conn, "C-1", "2026-08-24T11:00:00Z", '{"a": 1}', '{"e": 2}')
    stats = snapshot.compress_history(conn)
    assert stats["compressed"] == 1
    row = conn.execute("SELECT raw_json, event_json FROM market_snapshots"
                       " WHERE market_id='C-1'").fetchone()
    assert isinstance(row["raw_json"], bytes)
    assert json.loads(snapshot.payload_text(row["raw_json"]))["a"] == 1
    assert json.loads(snapshot.payload_text(row["event_json"]))["e"] == 2
    assert snapshot.compress_history(conn)["compressed"] == 0   # idempotent


def test_board_rebuild_reads_mixed_codecs(conn):
    # One legacy text row and one compressed row in the same board.
    m0, m1 = _mk("C-2"), _mk("C-3")
    snapshot.save_kalshi(conn, [m0, m1], now=NOW)     # compressed writes
    with db.write(conn):                               # revert one to text
        conn.execute(
            "UPDATE market_snapshots SET raw_json = ? WHERE market_id='C-2'",
            (json.dumps(m0.raw),))
    got = board.get_board(conn, now=NOW)
    assert sorted(m.ticker for m in got) == ["C-2", "C-3"]


# --- cross-codec identity through _save, end to end (task 5 review) --


def test_cross_codec_bump_then_insert_through_save(conn):
    # Controller ruling, task 5: pins the cross-codec identity path through
    # _save end-to-end -- reviewed by probe during task 4, made permanent
    # here. A legacy TEXT row and a fresh save_kalshi() call carrying the
    # byte-identical payload must compare equal and BUMP (never insert a
    # redundant second row); only a genuinely changed payload inserts, and
    # the new row lands in the current write-side codec (BLOB).
    t1 = "2026-08-24T10:00:00Z"
    m = _mk("X-9")
    raw_text = json.dumps(m.raw or {})
    _insert_legacy(conn, "X-9", t1, raw_text)

    n = snapshot.save_kalshi(conn, [m], now=NOW)
    assert n == 1                                       # one decision: bump
    rows = conn.execute(
        "SELECT captured_at, last_seen_at, raw_json FROM market_snapshots"
        " WHERE market_id = 'X-9' ORDER BY id"
    ).fetchall()
    assert len(rows) == 1                                # bump, not insert
    assert rows[0]["captured_at"] == t1
    assert rows[0]["last_seen_at"] == NOW
    assert isinstance(rows[0]["raw_json"], str)          # a bump never re-encodes

    t3 = "2026-08-24T13:00:00Z"
    changed = _mk("X-9", yes_ask_dollars="0.77")
    n2 = snapshot.save_kalshi(conn, [changed], now=t3)
    assert n2 == 1
    rows = conn.execute(
        "SELECT captured_at, last_seen_at, raw_json FROM market_snapshots"
        " WHERE market_id = 'X-9' ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    new_row = rows[-1]
    assert new_row["captured_at"] == new_row["last_seen_at"] == t3
    assert isinstance(new_row["raw_json"], bytes)        # new insert is BLOB
    assert json.loads(
        snapshot.payload_text(new_row["raw_json"])
    )["yes_ask_dollars"] == "0.77"


# --- the split (spec 5.2 phase 4) -------------------------------------


def test_fresh_db_puts_snapshots_in_the_attached_file(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    snapshot.save_kalshi(c, [_mk("S-0")], now=NOW)
    # Unqualified name resolves to the attached table...
    assert c.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0] == 1
    # ...because main genuinely does not have one.
    assert c.execute(
        "SELECT COUNT(*) FROM main.sqlite_master WHERE name='market_snapshots'"
    ).fetchone()[0] == 0
    assert c.execute(
        "SELECT COUNT(*) FROM snapdb.sqlite_master WHERE name='market_snapshots'"
    ).fetchone()[0] == 1
    assert (tmp_path / "test.snapshots.db").exists()
    db.close(c)


def test_unsplit_database_is_refused_loudly(tmp_path):
    # Build a pre-split DB shape by hand: table in main, rows present.
    import sqlite3 as raw_sqlite
    legacy = raw_sqlite.connect(tmp_path / "old.db")
    legacy.execute("CREATE TABLE market_snapshots (id INTEGER PRIMARY KEY,"
                   " platform TEXT, market_id TEXT, captured_at TEXT,"
                   " raw_json TEXT, last_seen_at TEXT)")
    legacy.execute("INSERT INTO market_snapshots"
                   " (platform, market_id, captured_at, raw_json)"
                   " VALUES ('kalshi','L','2026-08-24T11:00:00Z','{}')")
    legacy.commit(); legacy.close()
    c = db.connect(tmp_path / "old.db")
    with pytest.raises(RuntimeError, match="split-snapshots"):
        db.init_db(c)
    c.close()


def test_split_snapshots_moves_rows_and_drops_main(tmp_path):
    import sqlite3 as raw_sqlite
    legacy = raw_sqlite.connect(tmp_path / "old.db")
    legacy.execute("CREATE TABLE market_snapshots (id INTEGER PRIMARY KEY,"
                   " platform TEXT, market_id TEXT, captured_at TEXT,"
                   " title TEXT, implied_prob_yes REAL, yes_bid REAL,"
                   " yes_ask REAL, volume REAL, open_interest REAL,"
                   " close_time TEXT, status TEXT, raw_json TEXT,"
                   " event_json TEXT, last_seen_at TEXT)")
    legacy.execute("INSERT INTO market_snapshots"
                   " (platform, market_id, captured_at, raw_json, last_seen_at)"
                   " VALUES ('kalshi','M','2026-08-24T11:00:00Z','{\"a\":1}',"
                   " '2026-08-24T11:00:00Z')")
    legacy.commit(); legacy.close()
    c = db.connect(tmp_path / "old.db")
    stats = db.split_snapshots(c, tmp_path / "old.db")
    assert stats["moved"] == 1
    assert c.execute("SELECT COUNT(*) FROM snapdb.market_snapshots"
                     ).fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM main.sqlite_master"
                     " WHERE name='market_snapshots'").fetchone()[0] == 0
    db.init_db(c)          # now passes: main is split
    snapshot.save_kalshi(c, [_mk("S-1")], now=NOW)   # writes land attached
    assert c.execute("SELECT COUNT(*) FROM market_snapshots"
                     ).fetchone()[0] == 2
    db.close(c)


# --- split_snapshots rerun-safety (review finding, 2026-08-30) --------


def test_split_snapshots_is_rerun_safe_after_success(tmp_path):
    # Any second invocation after a completed split -- including a fresh
    # or already-split database -- must not crash. Pre-fix,
    # `PRAGMA main.table_info(market_snapshots)` on the now-missing main
    # table returned an EMPTY result with no error, so `col_list` became
    # "" and the copy's INSERT was malformed SQL
    # (`OperationalError: near ")"`).
    import sqlite3 as raw_sqlite
    legacy = raw_sqlite.connect(tmp_path / "old.db")
    legacy.execute("CREATE TABLE market_snapshots (id INTEGER PRIMARY KEY,"
                   " platform TEXT, market_id TEXT, captured_at TEXT,"
                   " raw_json TEXT, last_seen_at TEXT)")
    legacy.execute("INSERT INTO market_snapshots"
                   " (platform, market_id, captured_at, raw_json)"
                   " VALUES ('kalshi','L','2026-08-24T11:00:00Z','{}')")
    legacy.commit(); legacy.close()

    c = db.connect(tmp_path / "old.db")
    first = db.split_snapshots(c, tmp_path / "old.db")
    assert first["moved"] == 1

    second = db.split_snapshots(c, tmp_path / "old.db")   # rerun: no crash
    assert second["moved"] == 0
    assert second["note"] == "main already split; vacuum only"
    assert "vacuumed_bytes_after" in second
    assert c.execute(
        "SELECT COUNT(*) FROM snapdb.market_snapshots"
    ).fetchone()[0] == 1               # nothing duplicated by the rerun
    db.close(c)


def test_split_snapshots_resumes_after_drop_before_vacuum(tmp_path):
    # The realistic crash window: the DROP TABLE commits but the process
    # dies before VACUUM runs, so main lacks the table yet was never
    # vacuumed. Reproduced by hand -- driving the same copy-then-drop
    # steps split_snapshots itself performs, stopping short of VACUUM --
    # since letting split_snapshots reach that state naturally would
    # require actually killing the process mid-call. The operator's
    # obvious recovery step (run split-snapshots again) must finish the
    # interrupted VACUUM rather than crash on the same malformed-INSERT
    # bug as the plain rerun case above.
    import sqlite3 as raw_sqlite
    legacy = raw_sqlite.connect(tmp_path / "old.db")
    legacy.execute("CREATE TABLE market_snapshots (id INTEGER PRIMARY KEY,"
                   " platform TEXT, market_id TEXT, captured_at TEXT,"
                   " raw_json TEXT, last_seen_at TEXT)")
    legacy.execute("INSERT INTO market_snapshots"
                   " (platform, market_id, captured_at, raw_json)"
                   " VALUES ('kalshi','L','2026-08-24T11:00:00Z','{}')")
    legacy.commit(); legacy.close()

    c = db.connect(tmp_path / "old.db")
    db._init_snap_schema(c)
    cols = [r[1] for r in c.execute(
        "PRAGMA main.table_info(market_snapshots)")]
    col_list = ", ".join(cols)
    with db.write(c):
        c.execute(
            f"INSERT INTO snapdb.market_snapshots ({col_list})"
            f" SELECT {col_list} FROM main.market_snapshots"
        )
    with db.write(c):
        c.execute("DROP TABLE main.market_snapshots")   # committed...
    # ...but VACUUM never ran -- the exact crash window the guard exists
    # for. Confirm the setup actually reproduces it before relying on it.
    assert c.execute(
        "SELECT COUNT(*) FROM main.sqlite_master WHERE name='market_snapshots'"
    ).fetchone()[0] == 0

    stats = db.split_snapshots(c, tmp_path / "old.db")   # the recovery call
    assert stats["moved"] == 0
    assert stats["note"] == "main already split; vacuum only"
    assert "vacuumed_bytes_after" in stats
    assert c.execute(
        "SELECT COUNT(*) FROM snapdb.market_snapshots"
    ).fetchone()[0] == 1
    db.close(c)


def test_db_close_checkpoints_the_wal(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    snapshot.save_kalshi(c, [_mk("S-2")], now=NOW)
    db.close(c)
    # After a TRUNCATE checkpoint the -wal files are empty or gone.
    for name in ("test.db-wal", "test.snapshots.db-wal"):
        p = tmp_path / name
        assert (not p.exists()) or p.stat().st_size == 0
