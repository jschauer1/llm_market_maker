"""calibration_harvest -- board screen, exclusions, and the no-cell-no-bet rule.

The screen's job is to bin the board, not to pick winners: everything it
emits carries a cell, and `price()` refuses to recommend a cell that has not
been measured. These tests pin the parts that would silently change the
theory if edited -- the absent days-to-close cap, the overlap exclusions, and
the rule that an unmeasured cell never reaches `measured`.
"""

from datetime import datetime, timezone

import pytest

from tools.domain import Market
from tools.theory import TheoryContext
from theories.calibration_harvest import screen as S
from theories.calibration_harvest.theory import CalibrationHarvestTheory

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)


def m(ticker, *, yes_ask=None, no_ask=None, yes_bid=None, no_bid=None,
      volume=5000.0, days=5.0, series=None, status="active"):
    """A board market shaped like normalize() produces."""
    close = NOW.timestamp() + days * 86400
    mid = None
    if yes_ask is not None and yes_bid is not None:
        mid = (yes_ask + yes_bid) / 2
    spread = None
    if yes_ask is not None and yes_bid is not None:
        spread = round(yes_ask - yes_bid, 6)
    return Market(
        platform="kalshi", ticker=ticker, title=ticker,
        yes_ask=yes_ask, no_ask=no_ask, yes_bid=yes_bid, no_bid=no_bid,
        mid=mid, spread=spread, volume=volume, status=status, is_open=True,
        close_time=datetime.fromtimestamp(close, timezone.utc)
            .isoformat().replace("+00:00", "Z"),
        series_ticker=series or ticker.split("-")[0],
    )


def _ctx(board, categories=None):
    return TheoryContext(conn=None, board=board, now=NOW,
                         run_id="test", run_mode="live")


# ---- the band ------------------------------------------------------------

def test_favorite_in_band_survives():
    board = [m("KXPOL-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23)]
    res = S.screen(board, now=NOW, categories={"KXPOL": "Politics"})
    assert len(res.candidates) == 1
    assert res.candidates[0].legs[0].side == "yes"
    assert res.candidates[0].legs[0].price == 0.80


def test_dead_middle_is_dropped_because_no_cell_claims_it():
    board = [m("KXPOL-1", yes_ask=0.52, yes_bid=0.48, no_ask=0.52)]
    res = S.screen(board, now=NOW, categories={"KXPOL": "Politics"})
    assert res.candidates == ()
    assert res.gate_removed.get("no_cell") == 1


def test_wide_spread_is_dropped():
    board = [m("KXPOL-1", yes_ask=0.80, yes_bid=0.60, no_ask=0.20)]
    res = S.screen(board, now=NOW, categories={"KXPOL": "Politics"})
    assert res.candidates == ()
    assert res.gate_removed.get("spread") == 1


def test_thin_volume_is_dropped():
    board = [m("KXPOL-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23,
               volume=10.0)]
    res = S.screen(board, now=NOW, categories={"KXPOL": "Politics"})
    assert res.candidates == ()
    assert res.gate_removed.get("volume") == 1


# ---- the horizon rule that distinguishes this theory ---------------------

def test_long_dated_markets_are_kept_not_capped():
    """insider_bias caps at 14 days; this theory must NOT inherit that.

    Le 2026's horizon component is strongest at 1mo+, so a cap would throw
    away the best cells before they are ever measured.
    """
    board = [m("KXPOL-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23, days=200)]
    res = S.screen(board, now=NOW, categories={"KXPOL": "Politics"})
    assert len(res.candidates) == 1
    assert res.candidates[0].days_to_close == pytest.approx(200, abs=0.1)


def test_already_closed_market_is_dropped():
    board = [m("KXPOL-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23, days=-1)]
    res = S.screen(board, now=NOW, categories={"KXPOL": "Politics"})
    assert res.candidates == ()


# ---- overlap exclusions (part of the versioned procedure) ----------------

def test_mention_family_is_excluded_and_reported():
    board = [m("KXTRUMPMENTION-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23,
               series="KXTRUMPMENTION")]
    res = S.screen(board, now=NOW, categories={"KXTRUMPMENTION": "Mentions"})
    assert res.candidates == ()
    assert res.gate_removed.get("mention_family") == 1


def test_gate_report_names_every_exclusion_reason():
    board = [
        m("KXPOL-1", yes_ask=0.52, yes_bid=0.48, no_ask=0.52),
        m("KXPOL-2", yes_ask=0.80, yes_bid=0.60, no_ask=0.20),
        m("KXTRUMPMENTION-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23,
          series="KXTRUMPMENTION"),
        m("KXPOL-3", yes_ask=0.80, yes_bid=0.77, no_ask=0.23),
    ]
    res = S.screen(board, now=NOW,
                   categories={"KXPOL": "Politics",
                               "KXTRUMPMENTION": "Mentions"})
    assert len(res.candidates) == 1
    assert res.gate_removed["no_cell"] == 1
    assert res.gate_removed["spread"] == 1
    assert res.gate_removed["mention_family"] == 1
    assert res.funnel["board_markets"] == 4
    assert res.funnel["survivors"] == 1


# ---- cells are attached, and drive pricing ------------------------------

def test_candidate_carries_its_cell_key():
    board = [m("KXPOL-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23, days=5)]
    res = S.screen(board, now=NOW, categories={"KXPOL": "Politics"})
    assert S.cell_of(res.candidates[0]) == "politics|2d-1w|0.75-0.85"


def test_unmeasured_cell_prices_as_model_and_is_never_endorsed():
    """No cell rates exist yet, so nothing this theory emits is bettable."""
    board = [m("KXPOL-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23)]
    theory = CalibrationHarvestTheory(
        categories={"KXPOL": "Politics"}, cell_rates={})
    run = theory.start(_ctx(board))
    scored = theory.price(run.ctx, list(run.candidates))
    assert len(scored) == 1
    assert scored[0].edge.basis == "model"
    assert scored[0].disposition == "screened"


def test_measured_cell_prices_as_measured():
    board = [m("KXPOL-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23)]
    theory = CalibrationHarvestTheory(
        categories={"KXPOL": "Politics"},
        cell_rates={"politics|2d-1w|0.75-0.85":
                    {"wins": 190, "n": 200, "n_days": 20}},
    )
    run = theory.start(_ctx(board))
    scored = theory.price(run.ctx, list(run.candidates))
    assert scored[0].edge.basis == "measured"
    assert scored[0].edge.pts_net > 0


def test_day_clustered_cell_never_prices_as_measured():
    """A cell with 200 rows over 3 days is 3 draws -- must stay `model`."""
    board = [m("KXPOL-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23)]
    theory = CalibrationHarvestTheory(
        categories={"KXPOL": "Politics"},
        cell_rates={"politics|2d-1w|0.75-0.85":
                    {"wins": 190, "n": 200, "n_days": 3}},
    )
    run = theory.start(_ctx(board))
    scored = theory.price(run.ctx, list(run.candidates))
    assert scored[0].edge.basis == "model"


def test_theory_declares_no_llm_judgment():
    """Tier A by construction -- a prompt here would be a design error."""
    theory = CalibrationHarvestTheory()
    assert theory.uses_llm_judgment is False
    assert theory.prompts == {}


def test_priced_rows_carry_their_cell_as_queryable_context():
    """An unmeasured cell's rows exist only so that cell can accrue
    settlements, and `collect.cell_rates` reads the cell out of
    `extra_json`. Until 2026-08-29 `price()` put the cell in `rationale`
    and left `extra_json` null, so the first live run's 10,269 rows were
    invisible to the very grid they were recorded to grow."""
    board = [m("KXPOL-1", yes_ask=0.80, yes_bid=0.77, no_ask=0.23, days=5)]
    theory = CalibrationHarvestTheory(
        categories={"KXPOL": "Politics"}, cell_rates={})
    run = theory.start(_ctx(board, categories={"KXPOL": "Politics"}))
    scored = theory.price(run.ctx, list(run.candidates))

    extra = scored[0].extra
    assert extra["cell"] == "politics|2d-1w|0.75-0.85"
    assert extra["domain"] == "politics"
    assert extra["horizon_bin"] == "2d-1w"
    assert extra["price_bin"] == "0.75-0.85"
    assert extra["series_ticker"] == "KXPOL"
