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
    """The bound is taken on the DESIGN-EFFECT-CORRECTED sample size
    -- changed 2026-09-01 (v4), see cell_edge and effective_n. Not the row
    count (v1, too tight) and not the settlement-day count (v2/v3, which
    is this same formula pinned at rho = 1)."""
    n_eff = cells.effective_n(n=100, n_days=10)
    e = cells.cell_edge(wins=90, n=100, n_days=10, ask=0.80)
    expected = ((cells.wilson_lower(round(0.9 * n_eff), n_eff) - 0.80) * 100
                - cells.fee_pts(0.80))
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


def test_the_bound_discounts_rows_for_within_day_dependence():
    # 628/789 (79.6%) over 59 days, bought at 0.75. The cell that made
    # v2 abandon row-counting: row-counted the bound was
    # wilson_lower(628, 789) = 0.7664, claiming +1.64pts on a cell whose
    # gross edge is +0.2. It must still not fire.
    edge = cells.cell_edge(wins=628, n=789, n_days=59, ask=0.75)
    assert edge.basis == "measured"
    assert edge.model_prob < cells.wilson_lower(628, 789), (
        "the bound must discount 789 rows that arrived on 59 days"
    )
    assert edge.pts_net < 0, "this cell has no edge and must not price one"


# --- v4: the day count was a design effect pinned at rho = 1 -------------
#
# NOTES.md 2026-09-01 (later). Bounding on `n_days` is
# `n / (1 + (mbar - 1) * rho)` at rho = 1. Measured rho over the 20 cells
# of both complete populations is 0.027 (median) / 0.067 (mean), so the
# assumption was wrong by enough to make the rule INFEASIBLE at the
# theory's own gate: at MIN_CELL_DAYS = 8 no cell priced above 0.65 could
# emit a positive edge at any realized rate whatsoever.


def test_effective_n_endpoints_recover_both_shipped_estimators(monkeypatch):
    """rho = 1 must reproduce v3 exactly, rho = 0 must reproduce v1."""
    monkeypatch.setattr(cells, "CLUSTER_RHO", 1.0)
    assert cells.effective_n(n=789, n_days=59) == 59
    monkeypatch.setattr(cells, "CLUSTER_RHO", 0.0)
    assert cells.effective_n(n=789, n_days=59) == 789


def test_effective_n_sits_between_the_day_count_and_the_row_count():
    n_eff = cells.effective_n(n=789, n_days=59)
    assert 59 < n_eff < 789


def test_effective_n_never_exceeds_the_rows_it_has():
    assert cells.effective_n(n=30, n_days=30) == 30
    assert cells.effective_n(n=5, n_days=99) <= 5


def test_a_cell_at_the_measurement_floor_can_actually_fire():
    """The v3 defect, pinned. `basis == 'measured'` is the label that
    authorizes a bet, so a cell carrying it must be able to price a
    positive edge at SOME realized rate. Under v3 a cell at 0.80 needed
    17 settlement days before that was arithmetically possible, and at
    0.95 it needed 79 -- more than the 58 days Kalshi's archive reaches,
    so the richest price band could never fire at all."""
    for ask in (0.70, 0.80, 0.88, 0.95):
        perfect = cells.cell_edge(
            wins=30 * 14, n=30 * 14, n_days=30, ask=ask,
        )
        assert perfect.basis == "measured"
        assert perfect.pts_net > 0, (
            f"a flawless cell at ask {ask} must be able to price an edge"
        )


def test_the_correction_does_not_resurrect_a_flat_cell():
    """The integrity check on v4: loosening the bound must not turn a cell
    with no gross edge into a bettable one. All four complete-population
    weather cells are flat gross (+0.2 to +1.3) and must stay negative."""
    for wins, n, ask in ((575, 824, 0.695), (628, 789, 0.794),
                         (618, 692, 0.880), (872, 926, 0.949)):
        assert cells.cell_edge(wins, n, n_days=59, ask=ask).pts_net < 0


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
