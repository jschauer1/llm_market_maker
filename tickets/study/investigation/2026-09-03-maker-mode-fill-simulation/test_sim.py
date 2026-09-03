"""Planted-path fixtures for the maker-mode fill simulator (rule 0d).

Written and passing BEFORE the corpus was read. Every case has an answer
known by construction, and the two that matter most are the ones a
permissive simulator gets wrong in the direction that manufactures a
finding: a print that merely TOUCHES the limit, and a BLOCK trade at the
limit. Both must fail to fill.

Run from the repo root:  python -m pytest <this file> -q
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mm_sim", _HERE / "sim.py")
sim = importlib.util.module_from_spec(_spec)
sys.modules["mm_sim"] = sim
_spec.loader.exec_module(sim)

T0 = _dt.datetime(2026, 8, 1, 12, 0, tzinfo=_dt.timezone.utc)


def p(hours: float, side: str, price: float, *, block: bool = False, count: float = 10.0):
    return {
        "t": (T0 + _dt.timedelta(hours=hours)).isoformat().replace("+00:00", "Z"),
        "s": side,
        "p": price,
        "c": count,
        "b": block,
    }


def prints(*rows):
    return sim.load_prints(list(rows))


# --------------------------------------------------------------------------
# Book reconstruction
# --------------------------------------------------------------------------

def test_aggressor_sides_straddle_the_spread():
    """yes-taker prints give the ask, no-taker prints give the bid."""
    q = sim.quote_at(prints(p(0, "no", 0.60), p(1, "yes", 0.66)), T0 + _dt.timedelta(hours=2))
    assert q is not None
    assert q.bid == 0.60
    assert q.ask == 0.66
    assert q.spread == pytest.approx(0.06)


def test_quote_uses_the_latest_touch_on_each_side_independently():
    q = sim.quote_at(
        prints(p(0, "no", 0.50), p(1, "yes", 0.60), p(2, "no", 0.55)),
        T0 + _dt.timedelta(hours=3),
    )
    assert (q.bid, q.ask) == (0.55, 0.60)


def test_quote_ignores_prints_after_the_decision_point():
    """No lookahead: a later print must not inform the quote at T."""
    q = sim.quote_at(
        prints(p(0, "no", 0.50), p(1, "yes", 0.60), p(5, "no", 0.20)),
        T0 + _dt.timedelta(hours=2),
    )
    assert q.bid == 0.50


def test_quote_is_none_when_one_side_was_never_printed():
    assert sim.quote_at(prints(p(0, "no", 0.50)), T0 + _dt.timedelta(hours=1)) is None
    assert sim.quote_at(prints(p(0, "yes", 0.50)), T0 + _dt.timedelta(hours=1)) is None


def test_quote_is_none_when_a_side_is_staler_than_the_cap():
    rows = prints(p(0, "no", 0.50), p(1, "yes", 0.60))
    at = T0 + _dt.timedelta(hours=80)
    assert sim.quote_at(rows, at, max_age_h=72.0) is None
    assert sim.quote_at(rows, at, max_age_h=100.0) is not None


def test_block_trades_do_not_set_the_book():
    """A negotiated block never sat in the book, so it cannot be a touch."""
    q = sim.quote_at(
        prints(p(0, "no", 0.50), p(1, "yes", 0.60), p(2, "no", 0.90, block=True)),
        T0 + _dt.timedelta(hours=3),
    )
    assert q.bid == 0.50


def test_crossed_reconstruction_is_visible_to_the_caller():
    """bid > ask is a real possibility across a move; the study excludes it."""
    q = sim.quote_at(prints(p(0, "yes", 0.40), p(1, "no", 0.70)), T0 + _dt.timedelta(hours=2))
    assert q.bid > q.ask          # the caller's inclusion rule 3 rejects this
    assert q.spread < 0


# --------------------------------------------------------------------------
# The fill rule — trade-through, not touch
# --------------------------------------------------------------------------

END = T0 + _dt.timedelta(hours=24)


def test_a_print_below_the_limit_fills():
    hit = sim.fills(prints(p(1, "no", 0.59)), limit=0.61, start=T0, end=END)
    assert hit is not None and hit.price == 0.59


def test_a_print_exactly_at_the_limit_does_not_fill():
    """Queue-ambiguous: the existing queue may have absorbed all of it."""
    assert sim.fills(prints(p(1, "no", 0.61)), limit=0.61, start=T0, end=END) is None


def test_a_print_above_the_limit_does_not_fill():
    assert sim.fills(prints(p(1, "no", 0.70)), limit=0.61, start=T0, end=END) is None


def test_a_block_trade_through_the_limit_does_not_fill():
    """The case that would most flatter the maker arm if it were wrong."""
    assert sim.fills(prints(p(1, "no", 0.40, block=True)), limit=0.61, start=T0, end=END) is None


def test_a_yes_aggressor_below_the_limit_does_not_fill():
    """A yes-taker lifts an ASK. It never consumes a resting bid."""
    assert sim.fills(prints(p(1, "yes", 0.40)), limit=0.61, start=T0, end=END) is None


def test_fills_outside_the_time_in_force_do_not_count():
    assert sim.fills(prints(p(30, "no", 0.10)), limit=0.61, start=T0, end=END) is None
    assert sim.fills(prints(p(-1, "no", 0.10)), limit=0.61, start=T0, end=END) is None


def test_the_first_qualifying_print_is_the_fill():
    hit = sim.fills(
        prints(p(1, "no", 0.60), p(2, "no", 0.30)), limit=0.61, start=T0, end=END
    )
    assert hit.price == 0.60


def test_no_prints_in_the_window_is_no_fill():
    assert sim.fills(prints(), limit=0.61, start=T0, end=END) is None


# --------------------------------------------------------------------------
# Arm accounting
# --------------------------------------------------------------------------

def test_filled_arm_pays_the_limit_not_the_print_price():
    """A passive order fills AT its own price, never at the taker's."""
    rows = prints(p(0, "no", 0.60), p(1, "yes", 0.66), p(5, "no", 0.50))
    q = sim.quote_at(rows, T0 + _dt.timedelta(hours=2))
    arm = sim.rest_then_cross(
        rows, quote_t=q, quote_end=q, t=T0 + _dt.timedelta(hours=2), end=END
    )
    assert arm.filled
    assert arm.price == pytest.approx(0.61)      # bid 0.60 + 1c, not 0.50


def test_unfilled_arm_pays_the_later_ask():
    rows = prints(p(0, "no", 0.60), p(1, "yes", 0.66))
    q_t = sim.quote_at(rows, T0 + _dt.timedelta(hours=2))
    q_end = sim.Quote(bid=0.70, ask=0.76, bid_age_h=1.0, ask_age_h=1.0)
    arm = sim.rest_then_cross(
        rows, quote_t=q_t, quote_end=q_end, t=T0 + _dt.timedelta(hours=2), end=END
    )
    assert not arm.filled
    assert arm.price == pytest.approx(0.76)      # crossed later, worse


def test_capture_on_a_fill_is_spread_minus_one_cent():
    rows = prints(p(0, "no", 0.60), p(1, "yes", 0.66), p(5, "no", 0.55))
    q = sim.quote_at(rows, T0 + _dt.timedelta(hours=2))
    rest = sim.rest_then_cross(
        rows, quote_t=q, quote_end=q, t=T0 + _dt.timedelta(hours=2), end=END
    )
    d_gross = sim.cross(q).gross_pts - rest.gross_pts
    assert d_gross == pytest.approx(5.0)         # 6c spread, 1c given up


def test_zero_improvement_control_is_exactly_zero():
    """The study's stated void condition: this must be 0.00 everywhere."""
    for bid, ask in ((0.10, 0.14), (0.60, 0.66), (0.88, 0.97)):
        q = sim.Quote(bid=bid, ask=ask, bid_age_h=1.0, ask_age_h=1.0)
        d = sim.cross(q).cost_pts - sim.zero_control(q).cost_pts
        assert d == pytest.approx(0.0, abs=1e-12)


def test_fee_matches_the_repo_fee_model():
    """sim.fee_pts mirrors tools/sizing.py; drift here would be silent."""
    from tools import sizing

    for price in (0.02, 0.13, 0.5, 0.66, 0.9, 0.98):
        assert sim.fee_pts(price) == pytest.approx(sizing.fee_pts(price))


def test_market_view_cannot_leak_the_outcome():
    """counts.py runs on these; the pre-registration depends on it."""
    view = sim.market_view(
        {"ticker": "X", "resolved_at": "2026-08-01T00:00:00Z", "result": "yes",
         "trades": [p(0, "no", 0.5)]}
    )
    assert "result" not in view
    assert set(view) == {"ticker", "resolved_at", "prints"}


# --------------------------------------------------------------------------
# The mirrored fill rule — resting a YES ask (i.e. buying NO passively)
# --------------------------------------------------------------------------

def test_ask_side_print_above_the_limit_fills():
    hit = sim.fills_ask(prints(p(1, "yes", 0.66)), limit=0.65, start=T0, end=END)
    assert hit is not None and hit.price == 0.66


def test_ask_side_print_exactly_at_the_limit_does_not_fill():
    assert sim.fills_ask(prints(p(1, "yes", 0.65)), limit=0.65, start=T0, end=END) is None


def test_ask_side_print_below_the_limit_does_not_fill():
    assert sim.fills_ask(prints(p(1, "yes", 0.60)), limit=0.65, start=T0, end=END) is None


def test_ask_side_ignores_no_aggressors_and_blocks():
    assert sim.fills_ask(prints(p(1, "no", 0.90)), limit=0.65, start=T0, end=END) is None
    assert sim.fills_ask(
        prints(p(1, "yes", 0.90, block=True)), limit=0.65, start=T0, end=END
    ) is None


def test_ask_side_respects_the_time_in_force():
    assert sim.fills_ask(prints(p(30, "yes", 0.90)), limit=0.65, start=T0, end=END) is None


def test_mirror_capture_equals_the_primary_capture():
    """Both sides capture spread - 1c on a fill; only the miss branch differs."""
    bid, ask = 0.60, 0.66
    yes_capture = (ask - (bid + 0.01)) * 100
    no_cross = 1.0 - bid
    no_rest = 1.0 - (ask - 0.01)
    assert (no_cross - no_rest) * 100 == pytest.approx(yes_capture)
