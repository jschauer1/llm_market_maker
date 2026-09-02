"""Book-side arithmetic: the mistake two theories made in the same hour.

2026-09-01, independently and from opposite directions:

  * `deadline_drift`'s hazard.py priced a NO-buying strategy against
    `yes_ask`, when a NO buyer pays `1 - yes_bid`. Same 95 markets, same
    outcomes: +9.5 gap at z=2.60 off the ask, +2.3 at z=0.64 off the bid.
    The edge was the spread.
  * `no-favorite-high-band`'s successor idea read a -3.90 favorite as a
    +3.90 underdog. The real underdog leg is -1.04: both sides lose.

Neither was caught by a test, because both were arithmetically
self-consistent -- just against the wrong price. On Kalshi the round trip
is 2-5 points and is usually larger than the effect being measured.
"""

import pytest

from tools import book
from tools.sizing import fee_pts


def test_the_other_side_costs_one_minus_this_side_plus_the_spread():
    """Not `1 - ask`. Taking either side crosses the book, so the two asks
    sum to 1 + spread, never to 1."""
    assert book.other_side_ask(0.60, 0.02) == pytest.approx(0.42)
    assert book.other_side_ask(0.60, 0.0) == pytest.approx(0.40)


def test_the_two_asks_sum_to_one_plus_the_spread():
    for ask, spread in ((0.60, 0.02), (0.93, 0.01), (0.10, 0.07)):
        assert ask + book.other_side_ask(ask, spread) == pytest.approx(
            1.0 + spread
        )


def test_round_trip_is_the_spread_plus_both_legs_fees():
    ask, spread = 0.60, 0.02
    expected = spread * 100.0 + fee_pts(ask) + fee_pts(
        book.other_side_ask(ask, spread)
    )
    assert book.round_trip_cost_pts(ask, spread) == pytest.approx(expected)


def test_round_trip_is_the_two_to_five_points_the_incident_warns_about():
    """Sanity on real Kalshi bands: the toll is the same order as, or
    bigger than, most measured effects."""
    for ask, spread in ((0.60, 0.02), (0.75, 0.03), (0.93, 0.01)):
        assert 1.0 < book.round_trip_cost_pts(ask, spread) < 6.0


@pytest.mark.parametrize(
    "win_rate,ask,spread",
    [(0.62, 0.60, 0.02), (0.50, 0.93, 0.01), (0.80, 0.12, 0.07),
     (0.33, 0.40, 0.00)],
)
def test_both_legs_net_to_minus_the_round_trip(win_rate, ask, spread):
    """THE IDENTITY, and the reason this module exists.

    net(this side) + net(other side) == -round_trip, always. So a cell
    measured at -N is NOT an opportunity of +N on the complement -- it is
    -(round_trip - N) over there, and whenever the mispricing is smaller
    than the toll, BOTH SIDES LOSE. Measured on the liquidity study's
    0.50-0.80 band, n=2,609: -3.8989 + -1.0411 = -4.9400 exactly.
    """
    other = book.other_side_ask(ask, spread)
    this_net = book.net_edge_pts(win_rate, ask)
    other_net = book.net_edge_pts(1.0 - win_rate, other)
    assert this_net + other_net == pytest.approx(
        -book.round_trip_cost_pts(ask, spread), abs=1e-9
    )


def test_the_naive_mirror_is_wrong_by_exactly_the_round_trip():
    """The step this guards: 'do not buy this' -> 'so buy the other one'."""
    win_rate, ask, spread = 0.55, 0.65, 0.03
    this_net = book.net_edge_pts(win_rate, ask)
    naive_mirror = -this_net
    real_other = book.net_edge_pts(
        1.0 - win_rate, book.other_side_ask(ask, spread)
    )
    assert naive_mirror - real_other == pytest.approx(
        book.round_trip_cost_pts(ask, spread), abs=1e-9
    )


def test_the_liquidity_study_numbers_reproduce():
    """Regression against the measured case in
    studies/2026-09-01-liquidity-filtered-side-split (addendum): a 1.68pt
    spread over the 0.50-0.80 band gives a 4.94pt round trip."""
    # Mean favorite ask and spread for that band, as reported.
    rt = book.round_trip_cost_pts(0.65, 0.0168)
    assert rt == pytest.approx(4.94, abs=0.12)


def test_net_edge_pts_is_the_one_in_sizing():
    """One fee model, not a second copy. Five studies already carry their
    own `min(0.07*p*(1-p), 0.035)`; this module must not become a sixth."""
    from tools import sizing

    assert book.net_edge_pts is sizing.net_edge_pts


def test_a_zero_spread_still_costs_both_fees():
    """Even a locked market charges the round trip -- the fees do not
    vanish when the spread does."""
    rt = book.round_trip_cost_pts(0.50, 0.0)
    assert rt == pytest.approx(fee_pts(0.50) * 2)
    assert rt > 0


def test_a_spread_wider_than_the_ask_is_rejected():
    """The binding constraint is `spread <= ask`: a wider spread puts this
    side's BID below zero, so the quote pair does not exist. Silently
    clamping it would reproduce the class of error this module exists for.

    Note it is not the obvious constraint. `ask=0.99, spread=0.05` looks
    extreme and is fine (bid 0.94, other side 0.06); `ask=0.05,
    spread=0.07` looks milder and is impossible.
    """
    assert book.other_side_ask(0.99, 0.05) == pytest.approx(0.06)
    with pytest.raises(ValueError):
        book.other_side_ask(0.05, 0.07)
    with pytest.raises(ValueError):
        book.other_side_ask(1.5, 0.01)
    with pytest.raises(ValueError):
        book.other_side_ask(0.5, -0.01)
