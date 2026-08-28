"""Taking a bet names its theory, and every fill is kept."""

import pytest

from tools import db, ledger, theories

TS = "2026-08-26T12:00:00Z"
TS2 = "2026-08-29T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    for slug in ("t1", "t2"):
        theories.register(c, slug, slug, f"theories/{slug}", now=TS)
    yield c
    c.close()


def _rec(conn, theory="t1", ticker="A", price=0.60):
    opp, _ = ledger.record_opportunity(
        conn, theory_id=theory, theory_version=1, kalshi_ticker=ticker,
        outcome="yes", entry_price=price, edge_pts_net=6.0, now=TS,
    )
    return opp


def test_taking_a_bet_requires_naming_the_theory(conn):
    opp = _rec(conn)
    with pytest.raises(ValueError, match="--theory"):
        ledger.mark_user_action(conn, opp, "taken", size=25)


def test_naming_the_wrong_theory_raises(conn):
    opp = _rec(conn, theory="t1")
    with pytest.raises(ValueError, match="t2"):
        ledger.mark_user_action(
            conn, opp, "taken", size=25, theory_id="t2"
        )


def test_skipping_does_not_require_a_theory(conn):
    opp = _rec(conn)
    ledger.mark_user_action(conn, opp, "skipped", reason="too thin")
    assert ledger.get_opportunity(conn, opp)["user_action"] == "skipped"


def test_a_second_theory_cannot_also_take_the_same_market(conn):
    a = _rec(conn, theory="t1")
    b = _rec(conn, theory="t2")
    ledger.mark_user_action(conn, a, "taken", size=25, theory_id="t1", now=TS)
    with pytest.raises(ValueError, match="already taken"):
        ledger.mark_user_action(
            conn, b, "taken", size=25, theory_id="t2", now=TS
        )


def test_two_fills_are_both_kept(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, price=0.80, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(
        conn, opp, "taken", size=10, price=0.90, theory_id="t1", now=TS2,
    )
    got = [(f["filled_on"], f["size"], f["price"])
           for f in ledger.fills(conn, opp)]
    assert got == [("2026-08-26", 25.0, 0.80), ("2026-08-29", 10.0, 0.90)]


def test_user_size_is_the_sum_of_fills(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(
        conn, opp, "taken", size=10, theory_id="t1", now=TS2,
    )
    row = ledger.get_opportunity(conn, opp)
    assert row["user_size"] == 35.0
    assert row["user_action"] == "taken"


def test_unmarking_clears_the_fills(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(conn, opp, "untouched")
    assert ledger.fills(conn, opp) == []
    row = ledger.get_opportunity(conn, opp)
    assert row["user_action"] == "untouched"
    assert row["user_size"] is None
