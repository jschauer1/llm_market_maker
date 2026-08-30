import json

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
    # Design gate (6fe567a): rules text, close_time -- everything -- counts.
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
    assert json.loads(row["raw_json"])["rules_primary"] == "v1"


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
