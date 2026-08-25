"""Scoring a position by the portion of it that is actually at risk.

A position costing C that pays at least `min` and at most `max` bundles a
guaranteed return of `min` with a lottery on the difference. Grading the
lottery alone is what makes a floor basket scoreable at all -- see the
multi-leg spec's sections 3.6 and 3.6.1.
"""

import sqlite3

import pytest

from tools import db, ledger, score, theories
from tools.sizing import fee_pts

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


def _riskless_pair(conn):
    """Two riskless baskets with deliberately different economics.

    `taken` costs ~0.98 against a guaranteed 1.00 -- barely profitable.
    `untouched` costs ~0.16 against the same guaranteed 1.00 -- wildly
    profitable. Only `taken` is ever marked taken. If roi_taken folded
    both in unconditionally it would land far from either position's own
    ROI and dead center between them; if it correctly counted only
    `taken`, it lands exactly on that position's own number. The two
    outcomes cannot be mistaken for each other by coincidence, which is
    the point: a fixture using identical cost/payout for both positions
    would let a wrong implementation pass by accident.
    """
    taken_legs = [
        {"kalshi_ticker": "KXT1-26", "outcome": "yes", "entry_price": 0.60},
        {"kalshi_ticker": "KXT2-26", "outcome": "no", "entry_price": 0.35},
    ]
    untouched_legs = [
        {"kalshi_ticker": "KXU1-26", "outcome": "yes", "entry_price": 0.10},
        {"kalshi_ticker": "KXU2-26", "outcome": "no", "entry_price": 0.05},
    ]
    taken_id, _ = ledger.record_basket(
        conn, theory_id="t1", theory_version=1, legs=taken_legs,
        min_payout=1.0, max_payout=2.0, edge_pts_net=4.0,
        edge_basis="model", now=TS)
    untouched_id, _ = ledger.record_basket(
        conn, theory_id="t1", theory_version=1, legs=untouched_legs,
        min_payout=1.0, max_payout=2.0, edge_pts_net=4.0,
        edge_basis="model", now=TS)
    ledger.mark_user_action(conn, taken_id, "taken", size=10)

    # Leg 1 of each basket settles "yes" (matches its "yes" outcome, wins);
    # leg 2 settles "yes" too, which misses its "no" outcome and loses. Each
    # basket pays exactly its min_payout of 1.00 -- both riskless regardless
    # of which side actually wins, since cost is far under the floor either
    # way.
    _settle(conn, [
        ("KXT1-26", "yes"), ("KXT2-26", "yes"),
        ("KXU1-26", "yes"), ("KXU2-26", "yes"),
    ])

    # Expected costs computed independently from the legs' own numbers
    # (not from anything score.py returns), the same way
    # test_at_risk_rate_prices_only_the_portion_that_can_be_lost pins its
    # implied_rate against a hand-computed figure.
    taken_cost = 0.60 + 0.35 + (fee_pts(0.60) + fee_pts(0.35)) / 100.0
    untouched_cost = 0.10 + 0.05 + (fee_pts(0.10) + fee_pts(0.05)) / 100.0
    return taken_cost, untouched_cost


def test_roi_taken_excludes_a_riskless_position_never_marked_taken(conn):
    """The design call flagged in the task-4 report, now guarded: folding
    every riskless position into roi_taken unconditionally would let a
    position nobody ever placed inflate the figure that is supposed to
    measure money actually put down. Only a riskless basket sits in this
    theory's history, so this exercises the EMPTY_SCORE-derived branch of
    _aggregate -- the one that had to compute roi_taken from scratch
    rather than fold onto an existing calibrated accumulator.
    """
    taken_cost, untouched_cost = _riskless_pair(conn)
    payout = 1.0  # both baskets pay exactly their min_payout; see helper.

    taken_alone_roi = (payout - taken_cost) / taken_cost
    both_folded_roi = (
        (2 * payout - taken_cost - untouched_cost)
        / (taken_cost + untouched_cost)
    )
    # If this fails, the fixture's two positions were not different enough
    # to distinguish the correct behaviour from the wrong one.
    assert taken_alone_roi != pytest.approx(both_folded_roi)

    r = score.compute_score(conn, "t1", 1)
    assert r["riskless_n"] == 2
    assert r["roi_taken"] == pytest.approx(taken_alone_roi)
    assert r["roi_taken"] != pytest.approx(both_folded_roi)

    # The other half of the contract: roi_all counts BOTH riskless
    # positions, taken or not -- money is money for that figure.
    all_cost = taken_cost + untouched_cost
    all_roi = (2 * payout - all_cost) / all_cost
    assert r["roi_all"] == pytest.approx(all_roi)


def test_roi_taken_excludes_an_untaken_riskless_position_pooled_with_a_bet(
    conn,
):
    """The same guard, but for the branch where a calibrated position keeps
    `rows` non-empty and riskless cost/payout are folded onto the existing
    taken_cost/taken_return accumulator rather than computed from nothing.
    A wrong unconditional fold is a risk in this branch independently of
    the EMPTY_SCORE branch above -- a refactor could fix one and miss the
    other.
    """
    bet_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXBET-26",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS)
    ledger.mark_user_action(conn, bet_id, "taken", size=10)
    _settle(conn, [("KXBET-26", "yes")])  # the single position wins

    taken_cost, untouched_cost = _riskless_pair(conn)
    payout = 1.0

    bet_cost = 0.50 + fee_pts(0.50) / 100.0
    bet_payout = 1.0

    taken_alone_roi = (
        (bet_payout + payout - bet_cost - taken_cost)
        / (bet_cost + taken_cost)
    )
    both_folded_roi = (
        (bet_payout + 2 * payout - bet_cost - taken_cost - untouched_cost)
        / (bet_cost + taken_cost + untouched_cost)
    )
    assert taken_alone_roi != pytest.approx(both_folded_roi)

    r = score.compute_score(conn, "t1", 1)
    assert r["n"] == 1
    assert r["riskless_n"] == 2
    assert r["roi_taken"] == pytest.approx(taken_alone_roi)
    assert r["roi_taken"] != pytest.approx(both_folded_roi)

    all_cost = bet_cost + taken_cost + untouched_cost
    all_roi = (bet_payout + 2 * payout - all_cost) / all_cost
    assert r["roi_all"] == pytest.approx(all_roi)
