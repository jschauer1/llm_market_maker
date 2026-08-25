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


def _settle(conn, pairs):
    for ticker, result in pairs:
        score.record_settlement(conn, ticker, result, resolved_at=TS)


def test_at_risk_rate_prices_only_the_portion_that_can_be_lost(conn):
    # entry_price 1.55, floor 1.00, ceiling 2.00 -> a 0.55 bet on a 1.00
    # payoff. implied_rate is the market's rate, not the trader's cost, so
    # it is built from entry_price rather than cost -- fee is kept out of
    # it for the same reason _single_leg_observations builds implied_rate
    # from `price` rather than `cost`: _aggregate subtracts the fee exactly
    # once, via mean_fee_pts, and including it here too would subtract it
    # twice.
    _basket(conn, legs=_legs(0.95, 0.60), min_payout=1.0, max_payout=2.0)
    _settle(conn, [("KXLATE-26", "yes"), ("KXEARLY-26", "no")])  # pays 2.00
    obs = score._basket_observations(conn, "t1", 1, "live", "all", None)
    assert len(obs) == 1
    assert obs[0]["implied_rate"] == pytest.approx((1.55 - 1.0) / (2.0 - 1.0))
    assert obs[0]["won"] is True
    assert obs[0]["riskless"] is False


def test_paying_only_the_floor_is_an_at_risk_loss(conn):
    _basket(conn, legs=_legs(0.95, 0.60), min_payout=1.0, max_payout=2.0)
    _settle(conn, [("KXLATE-26", "yes"), ("KXEARLY-26", "yes")])  # pays 1.00
    obs = score._basket_observations(conn, "t1", 1, "live", "all", None)
    assert obs[0]["won"] is False
    assert obs[0]["payout"] == pytest.approx(1.0)


def test_a_zero_floor_reproduces_the_historical_formula(conn):
    """The non-regression claim, asserted directly: with no declared floor
    the at-risk rate IS entry_price/max_payout, which is what every
    existing row was scored by (see
    test_basket_implied_rate_is_normalized_by_max_payout in
    test_baskets.py, which pins the same formula and is untouched by this
    change)."""
    _basket(conn, legs=_legs(0.40, 0.55))          # floor 0, ceiling 1
    # Only KXLATE wins (KXEARLY's "no" outcome misses) so the basket pays
    # exactly its declared max_payout of 1.0, satisfying the all-or-nothing
    # guard -- unlike the first test above, this basket was never given a
    # max_payout of 2.0, so a double-win here would overshoot it.
    _settle(conn, [("KXLATE-26", "yes"), ("KXEARLY-26", "yes")])
    obs = score._basket_observations(conn, "t1", 1, "live", "all", None)
    assert obs[0]["implied_rate"] == pytest.approx(0.95 / 1.0)


def test_a_payout_below_the_declared_floor_raises(conn):
    """The check that makes a theory-declared floor safe: the claim is
    verified against what actually settled."""
    _basket(conn, legs=_legs(0.60, 0.35), min_payout=1.0, max_payout=2.0)
    _settle(conn, [("KXLATE-26", "no"), ("KXEARLY-26", "yes")])  # pays 0.00
    with pytest.raises(ValueError, match="below its declared min_payout"):
        score._basket_observations(conn, "t1", 1, "live", "all", None)


def test_a_payout_between_floor_and_ceiling_still_raises(conn):
    """The at-risk decomposition assumes a binary at-risk portion. A
    three-leg basket paying 1 of a possible 3 has no single `won` event."""
    legs = [
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.30},
        {"kalshi_ticker": "KXB-26", "outcome": "yes", "entry_price": 0.30},
        {"kalshi_ticker": "KXC-26", "outcome": "yes", "entry_price": 0.30},
    ]
    _basket(conn, legs=legs, max_payout=3.0)
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "no"), ("KXC-26", "no")])
    with pytest.raises(ValueError, match="neither its min_payout"):
        score._basket_observations(conn, "t1", 1, "live", "all", None)


def test_a_riskless_position_is_reported_separately_not_calibrated(conn):
    # cost 0.95 against a guaranteed 1.00 -- calendar-arb's shape.
    _basket(conn, legs=_legs(0.60, 0.35), min_payout=1.0, max_payout=2.0)
    _settle(conn, [("KXLATE-26", "yes"), ("KXEARLY-26", "yes")])  # pays 1.00
    r = score.compute_score(conn, "t1", 1)

    assert r["riskless_n"] == 1
    assert r["riskless_roi"] > 0            # it made money, certainly
    # ...and contributed nothing to the calibrated population:
    assert r["n"] == 0
    assert r["win_rate"] is None
    assert r["calibration_edge_net"] is None


def test_riskless_and_calibrated_positions_do_not_pool(conn):
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXS-26",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS)
    _basket(conn, legs=_legs(0.60, 0.35), min_payout=1.0, max_payout=2.0)
    _settle(conn, [("KXS-26", "yes"), ("KXLATE-26", "yes"),
                   ("KXEARLY-26", "yes")])
    r = score.compute_score(conn, "t1", 1)

    assert r["n"] == 1                       # the single position only
    assert r["win_rate"] == pytest.approx(1.0)
    assert r["riskless_n"] == 1              # the arbitrage, kept apart
    assert r["roi_all"] is not None          # money still counts as money


def test_no_riskless_positions_leaves_the_keys_at_their_defaults(conn):
    # Only KXLATE wins (KXEARLY's "no" outcome misses, same settlement as
    # test_a_zero_floor_reproduces_the_historical_formula above) so the
    # basket pays exactly its max_payout of 1.0 -- an ordinary at-risk
    # basket, not a riskless one.
    _basket(conn, legs=_legs(0.40, 0.55))
    _settle(conn, [("KXLATE-26", "yes"), ("KXEARLY-26", "yes")])
    r = score.compute_score(conn, "t1", 1)
    assert r["riskless_n"] == 0
    assert r["riskless_roi"] is None
    assert r["n"] == 1


def test_empty_score_carries_the_riskless_keys(conn):
    r = score.compute_score(conn, "t1", 1)
    assert r["n"] == 0 and r["riskless_n"] == 0
    assert r["riskless_roi"] is None
