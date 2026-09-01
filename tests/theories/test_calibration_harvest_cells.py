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
    # The `None` half of this assertion used to read `== "other"`. That was
    # the old meaning, and changing it is a deliberate vocabulary change
    # rather than a test fix: `other` now means only "a category the grid
    # does not bin", and a series the run's map never covered is
    # `unmapped`. The rows written under the old meaning are quarantined in
    # `forward_cells.OTHER_QUARANTINED_BELOW_VERSION`; see the three
    # `other`/`unmapped` tests at the end of this file.
    assert cells.domain_for("Transportation") == "other"
    assert cells.domain_for(None) == "unmapped"


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
    """The bound is taken on the SETTLEMENT-DAY count, not the row count
    -- changed 2026-08-29, see cell_edge. Here 90/100 over 10 days is
    read as 9/10, which is the whole point: ten days of evidence buys a
    ten-day-wide interval however many rows those days held."""
    e = cells.cell_edge(wins=90, n=100, n_days=10, ask=0.80)
    expected = (cells.wilson_lower(9, 10) - 0.80) * 100 - cells.fee_pts(0.80)
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


# --- the bound must count settlement days, not rows (2026-08-29) --------
#
# The theory already refuses to call a cell `measured` below
# MIN_CELL_DAYS, because "rows are not independent draws" -- a screen's
# whole near-term board settles within hours of itself. But `cell_edge`
# then computed its Wilson bound on the ROW count, which undoes that
# protection at exactly the point where money would be committed.
#
# Measured on the first complete population (weather, 2026-08-29): the
# `<=2d|0.75-0.85` cell went 628/789 over 59 settlement days. Row-counted,
# the bound claims +1.64pts at an ask of 0.75. Day-counted it says
# -7.27pts. Three live rows were priced positive on the row-counted bound
# and all three flip negative under the day-counted one.


def test_the_bound_counts_settlement_days_not_rows():
    # 628/789 (79.6%) over 59 days, bought at 0.75.
    edge = cells.cell_edge(wins=628, n=789, n_days=59, ask=0.75)
    assert edge.basis == "measured"
    # Row-counted this was wilson_lower(628, 789) = 0.7664 -> +1.64pts.
    assert edge.model_prob < 0.72, (
        "the bound must widen for 59 independent days, not 789 rows"
    )
    assert edge.pts_net < 0


def test_many_rows_on_one_day_buy_almost_no_confidence():
    """The failure this exists to stop: a cell that looks overwhelming on
    row count but rests on a handful of settlement days."""
    wide = cells.cell_edge(wins=900, n=1000, n_days=50, ask=0.80)
    narrow = cells.cell_edge(wins=900, n=1000, n_days=10, ask=0.80)
    assert narrow.model_prob < wide.model_prob, (
        "the same rows spread over fewer days must yield a weaker bound"
    )


def test_the_point_estimate_is_preserved_when_days_are_ample():
    """Day-counting must not bias the estimate, only widen the interval:
    the bound still sits below the raw rate and above zero."""
    edge = cells.cell_edge(wins=940, n=1000, n_days=200, ask=0.50)
    assert 0.0 < edge.model_prob < 0.94
    assert edge.pts_net > 0, "a genuinely strong, well-spread cell survives"


def test_a_cell_with_no_settlement_days_cannot_claim_a_bound():
    edge = cells.cell_edge(wins=50, n=60, n_days=0, ask=0.50)
    assert edge.basis == "model"
    assert edge.model_prob == 0.0


# ---- `other` vs `unmapped`: two different facts, two different names -----
#
# Until 2026-09-01 `domain_for` returned "other" for both, which is how the
# domain axis collapsed silently on three separate runs. The distinction is
# available at the call site and always was: `screen.py` looks the series up
# with `categories.get(...)`, so a series the map does not cover arrives as
# None, while a mapped-but-unbinned category arrives as its real string.

def test_a_category_the_grid_does_not_map_is_other():
    """Commodities, Social, Transportation, Exotics and Education are real
    Kalshi categories the grid deliberately does not bin. They are what
    `other` was designed to hold -- 102 of 9,220 survivors on the
    2026-09-01 board."""
    assert cells.domain_for("Commodities") == "other"
    assert cells.domain_for("Exotics") == "other"


def test_a_series_missing_from_the_map_is_unmapped_not_other():
    """A series the run's category map never covered is a defect in the
    RUN, not a fact about the market. Naming it `other` made a partial map
    indistinguishable from a complete one -- the weather run's 9,123
    `other` rows looked exactly like a legitimate residual."""
    assert cells.domain_for(None) == "unmapped"
    assert cells.cell_key(price=0.90, days_to_close=1.0,
                          category=None).startswith("unmapped|")


def test_unmapped_and_other_are_distinct_cells():
    """The point of the split: a partial-map run now produces a visibly
    wrong cell instead of a plausible-looking one."""
    missing = cells.cell_key(price=0.90, days_to_close=1.0, category=None)
    unbinned = cells.cell_key(price=0.90, days_to_close=1.0,
                              category="Commodities")
    assert missing != unbinned
