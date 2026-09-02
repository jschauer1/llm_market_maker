"""Tests for tools/timeutil.days_until, and for the elevation itself.

The elevation merged three copies that had drifted apart, so these tests
carry both halves of the claim made in the commit message:

- the **no-op half** -- an aware `now` behaves identically through all
  three theory screens that used to own a copy, which is what makes the
  merge safe for live decisions;
- the **delta half** -- a naive `now` now works everywhere, where two of
  the three previously raised TypeError.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from theories.insider_bias import screen as ib_screen
from theories.structural_arb import scan as sa_scan
from tools.timeutil import days_until

AWARE = datetime(2026, 8, 29, 0, 0, 0, tzinfo=timezone.utc)
NAIVE = datetime(2026, 8, 29, 0, 0, 0)

#: Every module that re-exports the elevated helper. The point of the
#: elevation is that these are the SAME function, so every behavioural
#: assertion below runs through all of them.
#:
#: There were three. The third, `calibration_harvest.screen.days_until`,
#: went with that theory's retirement on 2026-09-01 -- its code is deleted
#: and retrievable at the rev named in
#: `theories/retired/calibration_harvest/RETIRED.md`. This test is about
#: `timeutil`, not about that theory, so it kept its coverage and lost one
#: fixture rather than being deleted alongside the code it borrowed.
REEXPORTS = [ib_screen.days_until, sa_scan.days_until]


def test_every_theory_screen_re_exports_the_one_implementation():
    for fn in REEXPORTS:
        assert fn is days_until, (
            "a theory kept its own copy; the elevation is meant to leave "
            "exactly one implementation"
        )


# ------------------------------------------------------- the no-op half

@pytest.mark.parametrize("fn", REEXPORTS)
def test_an_aware_now_is_unchanged_everywhere(fn):
    """This is what proves the merge is safe for live decisions."""
    assert fn("2026-08-30T00:00:00Z", AWARE) == pytest.approx(1.0)
    assert fn("2026-08-29T12:00:00Z", AWARE) == pytest.approx(0.5)
    assert fn("2026-08-28T00:00:00Z", AWARE) == pytest.approx(-1.0)


@pytest.mark.parametrize("fn", REEXPORTS)
def test_unusable_input_returns_none_rather_than_raising(fn):
    assert fn(None, AWARE) is None
    assert fn("", AWARE) is None
    assert fn("not-a-date", AWARE) is None


# ------------------------------------------------------- the delta half

@pytest.mark.parametrize("fn", REEXPORTS)
def test_a_naive_now_is_coerced_to_utc_everywhere(fn):
    """Previously a TypeError in insider_bias and calibration_harvest,
    and a number in structural_arb. Now uniformly a number."""
    assert fn("2026-08-30T00:00:00Z", NAIVE) == pytest.approx(1.0)
    assert fn("2026-08-30T00:00:00Z", NAIVE) == fn("2026-08-30T00:00:00Z", AWARE)


# --------------------------------------------------- signature contract

def test_now_is_accepted_positionally():
    """calibration_harvest.screen calls this positionally. Reordering or
    renaming the parameter would break that call site silently while
    still type-checking."""
    assert days_until("2026-08-30T00:00:00Z", AWARE) == pytest.approx(1.0)


def test_now_is_optional_and_defaults_to_utc_now():
    """calibration_harvest's copy made it required; the superset does
    not, so a caller may omit it."""
    assert days_until("2030-01-01T00:00:00Z") > 0
    assert days_until("2020-01-01T00:00:00Z") < 0
