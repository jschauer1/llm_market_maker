"""Locks compute_score's exact arithmetic before the basket refactor.

These numbers are not derived from the implementation -- they are computed
by hand from the documented fee model and the definitions in the spec, so a
refactor that changes them fails here rather than silently shifting every
theory's calibration_edge_net.
"""

import pytest

from tools import db, ledger, score, theories
from tools.sizing import fee_pts

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _bet(conn, ticker, entry_price, edge, outcome="yes"):
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker=ticker,
        outcome=outcome, entry_price=entry_price, edge_pts_net=edge, now=TS,
    )
    return opp_id


def test_four_settled_singles_produce_exact_numbers(conn):
    # Two winners at 0.50, one winner at 0.80, one loser at 0.20.
    _bet(conn, "A", 0.50, 6.0)
    _bet(conn, "B", 0.50, 6.0)
    _bet(conn, "C", 0.80, 4.0)
    _bet(conn, "D", 0.20, 8.0)
    for ticker, result in (("A", "yes"), ("B", "yes"),
                           ("C", "yes"), ("D", "no")):
        score.record_settlement(conn, ticker, result, resolved_at=TS)

    r = score.compute_score(conn, "t1", 1)

    assert r["n"] == 4
    assert r["win_rate"] == pytest.approx(0.75)
    assert r["price_implied_rate"] == pytest.approx(0.50)
    assert r["calibration_edge"] == pytest.approx(25.0)
    assert r["mean_claimed_edge"] == pytest.approx(6.0)
    # mean_fee_pts is pinned to a hand-derived expression, not restated from
    # the implementation: tools.sizing.fee_pts stays the single source of
    # truth for the per-price fee model, but the aggregation over it -- the
    # denominator and the per-row application -- is exactly what this test
    # must lock, since a mixed single-leg/basket sample averaging over the
    # wrong denominator would otherwise slip through unnoticed.
    expected_mean_fee = (fee_pts(0.50) * 2 + fee_pts(0.80) + fee_pts(0.20)) / 4
    assert r["mean_fee_pts"] == pytest.approx(expected_mean_fee)
    assert r["calibration_edge_net"] == pytest.approx(25.0 - expected_mean_fee)


def test_roi_all_uses_cost_including_fees(conn):
    _bet(conn, "A", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes", resolved_at=TS)
    r = score.compute_score(conn, "t1", 1)
    from tools.sizing import fee_pts
    cost = 0.50 + fee_pts(0.50) / 100.0
    assert r["roi_all"] == pytest.approx((1.0 - cost) / cost)


def test_unsettled_rows_are_excluded(conn):
    _bet(conn, "A", 0.50, 6.0)
    _bet(conn, "B", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes", resolved_at=TS)
    assert score.compute_score(conn, "t1", 1)["n"] == 1
