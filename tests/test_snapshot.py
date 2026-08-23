import json

import pytest

from tools import db, snapshot

TS = "2026-08-23T12:00:00Z"
LATER = "2026-08-24T12:00:00Z"

KALSHI_MARKET = {
    "platform": "kalshi",
    "ticker": "KXTEST-26",
    "title": "Test market",
    "yes_bid": 0.40,
    "yes_ask": 0.42,
    "mid": 0.41,
    "volume": 1000.0,
    "open_interest": 500.0,
    "status": "active",
    "is_open": True,
    "close_time": "2026-12-01T00:00:00Z",
    "raw": {"ticker": "KXTEST-26", "volume_fp": "1000.00"},
}

POLY_MARKET = {
    "platform": "polymarket",
    "market_id": "0xabc",
    "question": "Test question?",
    "implied_prob_yes": 0.35,
    "best_bid": 0.34,
    "best_ask": 0.36,
    "volume": 5000.0,
    "end_date": "2026-12-01T00:00:00Z",
    "closed": False,
    "raw": {"conditionId": "0xabc"},
}


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def test_save_kalshi_writes_a_row(conn):
    assert snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS) == 1
    row = conn.execute("SELECT * FROM market_snapshots").fetchone()
    assert row["platform"] == "kalshi"
    assert row["market_id"] == "KXTEST-26"
    assert row["yes_bid"] == pytest.approx(0.40)
    assert row["yes_ask"] == pytest.approx(0.42)
    assert row["captured_at"] == TS


def test_save_kalshi_uses_mid_as_implied_probability(conn):
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    row = conn.execute("SELECT * FROM market_snapshots").fetchone()
    assert row["implied_prob_yes"] == pytest.approx(0.41)


def test_save_kalshi_maps_status_to_open(conn):
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    assert conn.execute(
        "SELECT status FROM market_snapshots"
    ).fetchone()["status"] == "open"


def test_save_kalshi_maps_finalized_to_settled(conn):
    settled = dict(KALSHI_MARKET, status="finalized", is_open=False)
    snapshot.save_kalshi(conn, [settled], now=TS)
    assert conn.execute(
        "SELECT status FROM market_snapshots"
    ).fetchone()["status"] == "settled"


def test_save_kalshi_maps_closed_but_unsettled_to_closed(conn):
    # Kalshi genuinely has a third state: closed, awaiting settlement. A
    # strict is_open/else binary would collapse this into "settled", which
    # is wrong — it hasn't resolved yet.
    closed = dict(KALSHI_MARKET, status="closed", is_open=False)
    snapshot.save_kalshi(conn, [closed], now=TS)
    assert conn.execute(
        "SELECT status FROM market_snapshots"
    ).fetchone()["status"] == "closed"


def test_save_kalshi_preserves_the_raw_payload(conn):
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    row = conn.execute("SELECT raw_json FROM market_snapshots").fetchone()
    assert json.loads(row["raw_json"])["volume_fp"] == "1000.00"


def test_save_polymarket_writes_a_row(conn):
    assert snapshot.save_polymarket(conn, [POLY_MARKET], now=TS) == 1
    row = conn.execute("SELECT * FROM market_snapshots").fetchone()
    assert row["platform"] == "polymarket"
    assert row["market_id"] == "0xabc"
    assert row["implied_prob_yes"] == pytest.approx(0.35)
    assert row["title"] == "Test question?"


def test_snapshots_accumulate_rather_than_overwrite(conn):
    # This is the whole point: kalshi_trader overwrote its dump every fetch.
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    snapshot.save_kalshi(conn, [dict(KALSHI_MARKET, yes_ask=0.55)], now=LATER)

    history = snapshot.history_for(conn, "kalshi", "KXTEST-26")
    assert len(history) == 2
    assert history[0]["captured_at"] == TS
    assert history[1]["yes_ask"] == pytest.approx(0.55)


def test_history_for_is_ascending_by_time(conn):
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=LATER)
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    history = snapshot.history_for(conn, "kalshi", "KXTEST-26")
    assert [r["captured_at"] for r in history] == [TS, LATER]


def test_history_for_filters_by_market(conn):
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    snapshot.save_kalshi(conn, [dict(KALSHI_MARKET, ticker="OTHER")], now=TS)
    assert len(snapshot.history_for(conn, "kalshi", "KXTEST-26")) == 1


def test_save_handles_an_empty_list(conn):
    assert snapshot.save_kalshi(conn, [], now=TS) == 0


def test_capture_kalshi_open_persists_what_it_fetches(conn, monkeypatch):
    monkeypatch.setattr(
        snapshot.kalshi_markets, "list_open",
        lambda **kwargs: [KALSHI_MARKET, dict(KALSHI_MARKET, ticker="B")],
    )
    assert snapshot.capture_kalshi_open(conn, now=TS) == 2
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM market_snapshots"
    ).fetchone()["n"] == 2
