import pytest

from tools import sizing


def test_fee_pts_is_maximal_at_fifty_cents():
    # 0.07 * 0.5 * 0.5 = 0.0175 dollars = 1.75 points
    assert sizing.fee_pts(0.50) == pytest.approx(1.75)


def test_fee_pts_is_smaller_at_the_extremes():
    assert sizing.fee_pts(0.10) == pytest.approx(0.63, abs=0.01)
    assert sizing.fee_pts(0.95) == pytest.approx(0.3325, abs=0.001)


def test_fee_pts_respects_the_cap():
    # The cap is $0.035/contract = 3.5 points; the curve never exceeds
    # 1.75 points, so the cap is a safety rail, not an active limit.
    for price in (0.01, 0.25, 0.5, 0.75, 0.99):
        assert sizing.fee_pts(price) <= 3.5


def test_fee_pts_at_certainty_is_zero():
    assert sizing.fee_pts(0.0) == pytest.approx(0.0)
    assert sizing.fee_pts(1.0) == pytest.approx(0.0)


def test_order_fee_dollars_rounds_up_to_the_cent():
    # 1 contract at 0.50: 0.0175 -> rounds up to 0.02
    assert sizing.order_fee_dollars(0.50, 1) == pytest.approx(0.02)
    # 100 contracts at 0.50: 1.75 -> already whole cents
    assert sizing.order_fee_dollars(0.50, 100) == pytest.approx(1.75)


def test_net_edge_subtracts_the_fee():
    # model 0.60 vs price 0.50 = 10 points gross, minus 1.75 fee
    assert sizing.net_edge_pts(0.60, 0.50) == pytest.approx(8.25)


def test_net_edge_can_be_negative():
    assert sizing.net_edge_pts(0.50, 0.50) == pytest.approx(-1.75)


def test_kelly_stake_is_zero_without_edge():
    assert sizing.kelly_stake(0.50, 0.50) == 0.0
    assert sizing.kelly_stake(0.40, 0.50) == 0.0


def test_kelly_stake_is_positive_with_edge():
    stake = sizing.kelly_stake(0.70, 0.50)
    assert 0.0 < stake <= 0.10


def test_kelly_stake_respects_max_stake():
    # A huge edge must still be capped.
    assert sizing.kelly_stake(0.99, 0.10) == pytest.approx(0.10)


def test_kelly_stake_handles_price_at_one():
    assert sizing.kelly_stake(0.99, 1.0) == 0.0


def test_blend_q_shrinks_halfway_toward_the_market():
    # model 0.70, mid 0.50, 50% shrink -> 0.60
    assert sizing.blend_q(0.70, 0.50) == pytest.approx(0.60)


def test_blend_q_caps_claimed_edge():
    # model 0.99 vs mid 0.50 would blend to 0.745, but edge caps at 10 points
    assert sizing.blend_q(0.99, 0.50) == pytest.approx(0.60)


def test_blend_q_caps_probability():
    assert sizing.blend_q(1.0, 0.99) <= 0.985
    assert sizing.blend_q(0.0, 0.01) >= 0.015


def test_blend_q_works_downward():
    # model 0.30, mid 0.50 -> 0.40
    assert sizing.blend_q(0.30, 0.50) == pytest.approx(0.40)


def test_order_fee_dollars_handles_fractional_cents_correctly():
    # Regression: adversarial price where per-contract fee has genuine fractional
    # cents (0.010000000009999999 cents). Must ceiling to $0.02, not $0.01.
    # This case fails with epsilon-based approaches like round(x, 8).
    assert sizing.order_fee_dollars(0.1726731648642293, 1) == pytest.approx(0.02)


def test_order_fee_dollars_hundred_contracts_still_works():
    # Regression: ensure the Decimal fix still correctly handles the original
    # test case (100 contracts at $0.50 must be exactly $1.75, not $1.76).
    assert sizing.order_fee_dollars(0.50, 100) == pytest.approx(1.75)
