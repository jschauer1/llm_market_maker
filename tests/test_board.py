import json

import pytest

from tools import board, db, snapshot

NOW = "2026-08-24T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def _raw(ticker, event="EV", series="KXTHING", **kw):
    base = {
        "ticker": ticker, "event_ticker": event, "series_ticker": series,
        "title": f"title {ticker}", "rules_primary": "rules",
        "status": "active", "close_time": "2026-09-01T00:00:00Z",
        "yes_bid_dollars": "0.80", "yes_ask_dollars": "0.82",
        "no_bid_dollars": "0.18", "no_ask_dollars": "0.20",
        "volume_fp": "900", "open_interest_fp": "500",
        # Bulk the raw payload out the way the live API does.
        "junk_a": "x" * 500, "junk_b": list(range(50)),
    }
    base.update(kw)
    return base


def _board(n=3):
    from tools.kalshi import markets
    return [markets.normalize(_raw(f"T-{i}")) for i in range(n)]


# --- board_info -------------------------------------------------------


def test_board_info_is_none_with_no_snapshots(conn):
    assert board.board_info(conn, now=NOW) is None


def test_board_info_reports_age_and_size(conn):
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:00:00Z")
    info = board.board_info(conn, now=NOW)
    assert info["markets"] == 3
    assert info["age_minutes"] == pytest.approx(60.0)


def test_board_info_uses_only_the_freshest_batch(conn):
    snapshot.save_kalshi(conn, _board(5), now="2026-08-23T12:00:00Z")
    snapshot.save_kalshi(conn, _board(2), now="2026-08-24T11:30:00Z")
    info = board.board_info(conn, now=NOW)
    assert info["markets"] == 2
    assert info["age_minutes"] == pytest.approx(30.0)


# --- caching ----------------------------------------------------------


def test_fresh_snapshot_is_reused_without_fetching(conn, monkeypatch):
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:00:00Z")

    def boom():
        raise AssertionError("list_open must not be called on a cache hit")
    monkeypatch.setattr(board.kalshi_markets, "list_open", boom)

    got = board.get_board(conn, now=NOW)
    assert [m["ticker"] for m in got] == ["T-0", "T-1", "T-2"]


def test_stale_snapshot_triggers_a_fetch(conn, monkeypatch):
    snapshot.save_kalshi(conn, _board(3), now="2026-08-20T12:00:00Z")
    calls = []
    monkeypatch.setattr(board.kalshi_markets, "list_open",
                        lambda: calls.append(1) or _board(7))
    got = board.get_board(conn, now=NOW)
    assert len(calls) == 1
    assert len(got) == 7


def test_no_snapshot_at_all_fetches(conn, monkeypatch):
    calls = []
    monkeypatch.setattr(board.kalshi_markets, "list_open",
                        lambda: calls.append(1) or _board(4))
    assert len(board.get_board(conn, now=NOW)) == 4
    assert len(calls) == 1


def test_force_refetches_even_when_fresh(conn, monkeypatch):
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:59:00Z")
    calls = []
    monkeypatch.setattr(board.kalshi_markets, "list_open",
                        lambda: calls.append(1) or _board(9))
    got = board.get_board(conn, force=True, now=NOW)
    assert len(calls) == 1 and len(got) == 9


def test_a_fetch_is_always_snapshotted(conn, monkeypatch):
    # The pull must never be lost -- that was the original complaint.
    monkeypatch.setattr(board.kalshi_markets, "list_open", lambda: _board(6))
    board.get_board(conn, now=NOW)
    assert board.board_info(conn, now=NOW)["markets"] == 6


def test_max_age_is_honoured(conn, monkeypatch):
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:00:00Z")
    monkeypatch.setattr(board.kalshi_markets, "list_open", lambda: _board(9))
    assert len(board.get_board(conn, max_age_minutes=30, now=NOW)) == 9
    assert len(board.get_board(conn, max_age_minutes=90, now=NOW)) == 9


def test_rebuilt_board_matches_the_fetched_one(conn):
    original = _board(3)
    snapshot.save_kalshi(conn, original, now="2026-08-24T11:00:00Z")
    rebuilt = board.get_board(conn, now=NOW)
    for a, b in zip(original, rebuilt):
        for field in ("ticker", "event_ticker", "series_ticker", "title",
                      "yes_bid", "yes_ask", "no_bid", "no_ask", "mid",
                      "spread", "volume", "open_interest", "status",
                      "is_open", "close_time", "rules_primary"):
            assert a[field] == b[field], field


def test_unrebuildable_snapshot_fails_loudly(conn):
    snapshot.save_kalshi(conn, _board(2), now="2026-08-24T11:00:00Z")
    with db.write(conn):
        conn.execute("UPDATE market_snapshots SET raw_json = '{}'")
    # A short board that looks complete would silently starve a screen.
    with pytest.raises(ValueError, match="cannot be rebuilt"):
        board.get_board(conn, now=NOW)


# --- raw_json projection ---------------------------------------------


def test_projection_drops_fields_nothing_reads(conn):
    snapshot.save_kalshi(conn, _board(1), now=NOW)
    stored = json.loads(conn.execute(
        "SELECT raw_json FROM market_snapshots").fetchone()["raw_json"])
    assert "junk_a" not in stored and "junk_b" not in stored
    assert stored["ticker"] == "T-0"
    assert stored["rules_primary"] == "rules"


def test_projection_keeps_everything_normalize_reads():
    raw = _raw("T-1", result="yes", volume_24h_fp="10",
               rules_secondary="more", yes_sub_title="a", no_sub_title="b",
               last_price_dollars="0.81", open_time="2026-01-01T00:00:00Z")
    projected = snapshot.project_raw(raw)
    from tools.kalshi import markets
    assert markets.normalize(projected) | {"raw": None} == \
           markets.normalize(raw) | {"raw": None}


def test_projection_omits_empty_values():
    projected = snapshot.project_raw(_raw("T-1"))
    # No result / rules_secondary on an open market -- storing nulls for
    # ~100k markets is most of what made raw_json expensive.
    assert "result" not in projected
    assert "rules_secondary" not in projected


def test_projection_shrinks_the_payload():
    raw = _raw("T-1")
    assert len(json.dumps(snapshot.project_raw(raw))) < len(json.dumps(raw)) / 2


def test_compact_rewrites_unprojected_rows(conn):
    snapshot.save_kalshi(conn, _board(3), now=NOW)
    fat = json.dumps(_raw("T-0") | {"filler": "y" * 5000})
    with db.write(conn):
        conn.execute("UPDATE market_snapshots SET raw_json = ?", (fat,))
    assert snapshot.compact_raw_json(conn) == 3
    for row in conn.execute("SELECT raw_json FROM market_snapshots"):
        assert "filler" not in row["raw_json"]
    # Idempotent: nothing left oversized to rewrite.
    assert snapshot.compact_raw_json(conn) == 0
