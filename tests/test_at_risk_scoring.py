"""Scoring a position by the portion of it that is actually at risk.

A position costing C that pays at least `min` and at most `max` bundles a
guaranteed return of `min` with a lottery on the difference. Grading the
lottery alone is what makes a floor basket scoreable at all -- see the
multi-leg spec's sections 3.6 and 3.6.1.
"""

import sqlite3

import pytest

from tools import db, ledger, score, theories

TS = "2026-08-25T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _legs(a=0.60, b=0.35):
    return [
        {"kalshi_ticker": "KXLATE-26", "outcome": "yes", "entry_price": a},
        {"kalshi_ticker": "KXEARLY-26", "outcome": "no", "entry_price": b},
    ]


def _basket(conn, **over):
    kwargs = dict(theory_id="t1", theory_version=1, legs=_legs(),
                  edge_pts_net=4.0, edge_basis="model", now=TS)
    kwargs.update(over)
    return ledger.record_basket(conn, **kwargs)


def test_opportunities_has_min_payout_defaulting_to_zero(conn):
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(opportunities)").fetchall()}
    assert "min_payout" in cols
    opp_id, _ = _basket(conn)
    assert ledger.get_opportunity(conn, opp_id)["min_payout"] == \
        pytest.approx(0.0)


def test_a_single_position_defaults_to_a_zero_floor(conn):
    """The default is what makes this change a no-op for existing rows."""
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXS-26",
        outcome="yes", entry_price=0.5, edge_pts_net=6.0, now=TS)
    assert ledger.get_opportunity(conn, opp_id)["min_payout"] == \
        pytest.approx(0.0)


def test_record_basket_persists_a_declared_floor(conn):
    opp_id, _ = _basket(conn, min_payout=1.0, max_payout=2.0)
    row = ledger.get_opportunity(conn, opp_id)
    assert row["min_payout"] == pytest.approx(1.0)
    assert row["max_payout"] == pytest.approx(2.0)


@pytest.mark.parametrize("bad", [-0.5, None, "1.0", True, float("nan")])
def test_a_nonsense_floor_is_refused(conn, bad):
    with pytest.raises(ValueError, match="min_payout"):
        _basket(conn, min_payout=bad, max_payout=2.0)


def test_a_floor_above_the_ceiling_is_refused(conn):
    with pytest.raises(ValueError, match="min_payout"):
        _basket(conn, min_payout=2.5, max_payout=2.0)


def test_a_floor_equal_to_the_ceiling_is_allowed(conn):
    """A position that always pays the same amount is a bond. If it costs
    less than it pays that is a real, if unusual, arbitrage -- and the
    riskless branch handles it before any at-risk division is reached."""
    opp_id, _ = _basket(conn, min_payout=1.0, max_payout=1.0)
    assert ledger.get_opportunity(conn, opp_id)["min_payout"] == \
        pytest.approx(1.0)
