"""calibration_harvest — cell grid, Wilson bounds, signed edge arithmetic.

The design constraint these pin comes from mention_family's death: a ~3%
sample of a price-bin grid measured +5.48 net, full coverage of the same
window measured -1.53, and the theory was retired. So a cell's edge here is
never its raw rate -- it is a Wilson LOWER bound, and it is not `measured`
at all until the cell clears both a row floor and a settlement-DAY floor.
"""

import pytest

from theories.calibration_harvest import cells


# ---- price bins -----------------------------------------------------------

def test_price_bins_partition_the_favorite_band():
    assert cells.price_bin(0.65) == "0.65-0.75"
    assert cells.price_bin(0.74999) == "0.65-0.75"
    assert cells.price_bin(0.75) == "0.75-0.85"
    assert cells.price_bin(0.85) == "0.85-0.92"
    assert cells.price_bin(0.92) == "0.92-0.97"
    assert cells.price_bin(0.97) == "0.92-0.97"


def test_price_bins_cover_the_fade_band():
    assert cells.price_bin(0.03) == "0.03-0.15"
    assert cells.price_bin(0.15) == "0.15-0.35"
    assert cells.price_bin(0.349) == "0.15-0.35"


def test_price_outside_any_band_has_no_bin():
    """The dead middle is deliberately unbinned -- no cell claims it."""
    assert cells.price_bin(0.50) is None
    assert cells.price_bin(0.0) is None
    assert cells.price_bin(1.0) is None


# ---- horizon bins ---------------------------------------------------------

def test_horizon_bins_are_open_ended_upward():
    assert cells.horizon_bin(0.5) == "<=2d"
    assert cells.horizon_bin(2.0) == "<=2d"
    assert cells.horizon_bin(2.01) == "2d-1w"
    assert cells.horizon_bin(7.0) == "2d-1w"
    assert cells.horizon_bin(7.01) == "1w-1mo"
    assert cells.horizon_bin(30.0) == "1w-1mo"
    # No cap: the documented compression GROWS with horizon, so the screen
    # must not discard long-dated markets the way insider_bias does.
    assert cells.horizon_bin(365.0) == "1mo+"


def test_negative_horizon_has_no_bin():
    assert cells.horizon_bin(-1.0) is None


# ---- category mapping -----------------------------------------------------

def test_elections_and_politics_collapse_to_one_domain():
    """Le 2026's 'politics' is Kalshi's Politics AND Elections."""
    assert cells.domain_for("Politics") == "politics"
    assert cells.domain_for("Elections") == "politics"


def test_weather_is_its_own_domain_because_its_sign_is_opposite():
    assert cells.domain_for("Climate and Weather") == "weather"


def test_unmapped_category_falls_to_other_not_to_a_guess():
    assert cells.domain_for("Transportation") == "other"
    assert cells.domain_for(None) == "other"


# ---- cell keys ------------------------------------------------------------

def test_cell_key_is_stable_and_readable():
    key = cells.cell_key(price=0.80, days_to_close=3.0, category="Politics")
    assert key == "politics|2d-1w|0.75-0.85"


def test_cell_key_is_none_when_any_axis_is_none():
    assert cells.cell_key(price=0.50, days_to_close=3.0,
                          category="Politics") is None
    assert cells.cell_key(price=0.80, days_to_close=-1.0,
                          category="Politics") is None


# ---- Wilson bound ---------------------------------------------------------

def test_wilson_lower_is_below_the_raw_rate():
    assert cells.wilson_lower(wins=30, n=30) < 1.0
    assert cells.wilson_lower(wins=27, n=30) < 27 / 30


def test_wilson_lower_tightens_toward_the_rate_as_n_grows():
    small = cells.wilson_lower(wins=9, n=10)
    large = cells.wilson_lower(wins=900, n=1000)
    assert small < large < 0.90


def test_wilson_lower_of_empty_cell_is_zero():
    assert cells.wilson_lower(wins=0, n=0) == 0.0


def test_wilson_lower_handles_the_all_wins_case_mention_family_flagged():
    """mention_family's 41/41 bin took 1.000 at face value and died for it."""
    bound = cells.wilson_lower(wins=41, n=41)
    assert 0.85 < bound < 0.95


# ---- edge arithmetic ------------------------------------------------------

def test_edge_is_wilson_bound_minus_ask_minus_fees():
    e = cells.cell_edge(wins=90, n=100, n_days=10, ask=0.80)
    expected = (cells.wilson_lower(90, 100) - 0.80) * 100 - cells.fee_pts(0.80)
    assert e.pts_net == pytest.approx(expected)
    assert e.basis == "measured"


def test_thin_cell_is_model_not_measured():
    e = cells.cell_edge(wins=9, n=10, n_days=10, ask=0.80)
    assert e.basis == "model"


def test_day_clustered_cell_is_model_however_many_rows_it_has():
    """The 2026-08-27 rule: 400 rows over 3 days is not a measurement."""
    e = cells.cell_edge(wins=380, n=400, n_days=3, ask=0.80)
    assert e.basis == "model"
    e_ok = cells.cell_edge(wins=380, n=400, n_days=8, ask=0.80)
    assert e_ok.basis == "measured"


def test_edge_can_be_negative_and_is_reported_not_clamped():
    e = cells.cell_edge(wins=70, n=100, n_days=10, ask=0.95)
    assert e.pts_net < 0


def test_edge_never_claims_measured_without_both_floors():
    assert cells.cell_edge(wins=29, n=29, n_days=20, ask=0.8).basis == "model"
    assert cells.cell_edge(wins=30, n=30, n_days=7, ask=0.8).basis == "model"
    assert cells.cell_edge(wins=30, n=30, n_days=8, ask=0.8).basis == "measured"
