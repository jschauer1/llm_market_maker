import sqlite3

import pytest

from tools import db, ledger, theories

TS = "2026-08-23T12:00:00Z"
LATER = "2026-08-24T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_opportunities_has_the_basket_columns(conn):
    cols = _columns(conn, "opportunities")
    assert {"position_kind", "leg_count", "max_payout"} <= cols


def test_opportunity_legs_table_exists(conn):
    cols = _columns(conn, "opportunity_legs")
    assert cols == {
        "opportunity_id", "leg_index", "kalshi_ticker", "outcome",
        "entry_price", "spread_at_call", "volume_at_call",
    }


def test_existing_single_leg_row_defaults_are_correct(conn):
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXTEST-26",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, now=TS,
    )
    row = ledger.get_opportunity(conn, opp_id)
    assert row["position_kind"] == "single"
    assert row["leg_count"] == 1
    assert row["max_payout"] == pytest.approx(1.0)


def test_position_kind_rejects_an_unknown_value(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO opportunities (theory_id, theory_version, run_mode,"
            " run_id, kalshi_ticker, outcome, entry_price,"
            " screen_edge_pts_net, edge_pts_net, position_kind,"
            " first_seen_at, last_seen_at)"
            " VALUES ('t1', 1, 'live', 'live', 'X', 'yes', 0.4, 1.0, 1.0,"
            " 'combo', ?, ?)",
            (TS, TS),
        )


def test_basket_key_is_stable_across_leg_order():
    a = [{"kalshi_ticker": "AAA", "outcome": "yes"},
         {"kalshi_ticker": "BBB", "outcome": "no"}]
    b = list(reversed(a))
    assert ledger.basket_key(a) == ledger.basket_key(b)


def test_basket_key_normalizes_case():
    a = [{"kalshi_ticker": "aaa", "outcome": "YES"}]
    b = [{"kalshi_ticker": "AAA", "outcome": "yes"}]
    assert ledger.basket_key(a) == ledger.basket_key(b)


def test_basket_key_differs_on_different_legs():
    a = [{"kalshi_ticker": "AAA", "outcome": "yes"}]
    b = [{"kalshi_ticker": "AAA", "outcome": "no"}]
    assert ledger.basket_key(a) != ledger.basket_key(b)


def test_basket_key_shape():
    key = ledger.basket_key([{"kalshi_ticker": "AAA", "outcome": "yes"}])
    assert key.startswith("BASKET:")
    assert len(key) == len("BASKET:") + 16


def test_basket_key_raises_on_missing_ticker():
    with pytest.raises(ValueError, match="leg 0.*kalshi_ticker.*required"):
        ledger.basket_key([{"kalshi_ticker": None, "outcome": "yes"}])


def test_basket_key_raises_on_missing_outcome():
    with pytest.raises(ValueError, match="leg 0.*outcome.*required"):
        ledger.basket_key([{"kalshi_ticker": "AAA", "outcome": None}])


def test_basket_key_prevents_delimiter_collision():
    # Without escaping, these two would produce the same hash with string joining.
    # With json.dumps(), they must be different.
    a = [{"kalshi_ticker": "123", "outcome": "yes"},
         {"kalshi_ticker": "456", "outcome": "no"}]
    b = [{"kalshi_ticker": "123", "outcome": "yes|456:no"}]
    assert ledger.basket_key(a) != ledger.basket_key(b)
