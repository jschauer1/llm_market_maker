"""Tests for tools/ladders.py -- scalar strike-ladder geometry.

The `yes_set`/`underlying_key` behaviour is also exercised through
`tests/theories/test_structural_arb.py`, which was passing before this
module was elevated out of that theory and still passes unchanged. These
tests cover the module on its own terms, and the two helpers added at
elevation (`strike_value`, `is_upper_tail`) that no theory test reaches.
"""

from __future__ import annotations

import pytest

from tools.domain import Market
from tools.ladders import (NEG_INF, POS_INF, is_upper_tail, num,
                           strike_value, underlying_key, yes_set)


def m(ticker: str, title: str = "Above #?", **raw) -> Market:
    return Market(platform="kalshi", ticker=ticker, title=title, raw=raw)


# ------------------------------------------------------------------- num

@pytest.mark.parametrize("value", [True, False, "3", None, [1], float("nan"),
                                   float("inf"), float("-inf")])
def test_num_rejects_non_finite_and_non_numeric(value):
    assert num(value) is None


def test_num_accepts_ints_and_floats():
    assert num(3) == 3.0
    assert num(-2.5) == -2.5


# --------------------------------------------------------------- yes_set

def test_yes_set_one_sided_types_carry_their_closure():
    g = yes_set(m("G", strike_type="greater", floor_strike=10))
    assert (g.lo, g.hi, g.lo_closed, g.boundary_known) == (10, POS_INF, False, True)

    ge = yes_set(m("GE", strike_type="greater_or_equal", floor_strike=10))
    assert (ge.lo, ge.lo_closed) == (10, True)

    lt = yes_set(m("L", strike_type="less", cap_strike=5))
    assert (lt.lo, lt.hi, lt.hi_closed, lt.boundary_known) == (NEG_INF, 5, False, True)

    le = yes_set(m("LE", strike_type="less_or_equal", cap_strike=5))
    assert (le.hi, le.hi_closed) == (5, True)


def test_between_is_flagged_boundary_unknown():
    b = yes_set(m("B", strike_type="between", floor_strike=1, cap_strike=2))
    assert (b.lo, b.hi) == (1, 2)
    assert b.boundary_known is False, (
        "between's open/closed convention is not published per market; "
        "proofs touching its endpoints must not trust it"
    )


def test_a_one_sided_type_carrying_both_bounds_is_refused():
    """The KXSTARSHIPSPACE-26-8.0 case: strike_type='less' with
    floor == cap == 8 and a title reading 'exactly 8'. Believing the type
    field manufactures a riskless pair that loses whenever the outcome
    lands between the strikes."""
    assert yes_set(m("S", strike_type="less", floor_strike=8, cap_strike=8)) is None
    assert yes_set(m("S", strike_type="greater", floor_strike=8, cap_strike=8)) is None


@pytest.mark.parametrize("raw", [
    {},                                              # no strike_type
    {"strike_type": "structured"},                   # unsupported
    {"strike_type": "greater"},                      # missing floor
    {"strike_type": "less"},                         # missing cap
    {"strike_type": "between", "floor_strike": 5, "cap_strike": 1},  # inverted
])
def test_yes_set_returns_none_rather_than_guessing(raw):
    assert yes_set(m("X", **raw)) is None


# -------------------------------------------------- strike_value / tail

def test_strike_value_and_tail_direction():
    g = yes_set(m("G", strike_type="greater", floor_strike=10))
    assert strike_value(g) == 10
    assert is_upper_tail(g) is True, "P(X > k) falls as k rises"

    lt = yes_set(m("L", strike_type="less", cap_strike=5))
    assert strike_value(lt) == 5
    assert is_upper_tail(lt) is False, "P(X < k) rises as k rises"


def test_between_has_no_single_threshold():
    b = yes_set(m("B", strike_type="between", floor_strike=1, cap_strike=2))
    assert strike_value(b) is None
    assert is_upper_tail(b) is None, (
        "a two-edged interval cannot be ordered on one axis, so a ladder "
        "mixing it with one-sided rungs must not be fitted"
    )


# --------------------------------------------------- underlying_key

def test_same_title_shape_groups_across_strikes():
    a = m("KXX-26AUG29-4", title="Above 4 runs?")
    b = m("KXX-26AUG29-6", title="Above 6 runs?")
    assert underlying_key(a) == underlying_key(b) is not None


def test_different_subjects_never_group_even_with_uniform_tickers():
    """KXMLBHIT holds a hits-ladder per player under one event. A false
    merge compares thresholds that mean nothing to each other."""
    a = m("KXMLBHIT-G-2", title="Brian Serven: 2+ hits?")
    b = m("KXMLBHIT-G-2", title="Darell Hernaiz: 2+ hits?")
    assert underlying_key(a) != underlying_key(b)


@pytest.mark.parametrize("tail", ["ATHBSERVEN10", "SJSU20", "DEM11T30"])
def test_a_letters_bearing_tail_is_identity_not_a_threshold(tail):
    assert underlying_key(m(f"KXX-26AUG29-{tail}")) is None


@pytest.mark.parametrize("tail", ["-2", "B48.5", "T4500", "7"])
def test_pure_strike_tokens_are_accepted(tail):
    assert underlying_key(m(f"KXX-26AUG29-{tail}")) is not None


def test_an_empty_title_never_groups():
    assert underlying_key(m("KXX-26AUG29-4", title="")) is None
