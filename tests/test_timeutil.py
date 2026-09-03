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


# ======================================================== parse_deadline
# Elevated 2026-09-03 from `theories.deadline_drift.collect_settled`,
# under CLAUDE.md's caller-count rule: it had grown a second theory
# calling it (`no_side_premium.exposure_measure`), and a theory importing
# a sibling theory's folder is exactly what
# `test_no_theory_imports_a_sibling_theory` forbids. The sibling import
# had the suite red for two days before the move.

from theories.deadline_drift import collect_settled as dd_collect  # noqa: E402
from tools.timeutil import parse_deadline  # noqa: E402

#: Same contract as REEXPORTS above: elevation leaves ONE implementation,
#: so every module that still names the helper must name this object.
DEADLINE_REEXPORTS = [dd_collect.parse_deadline]


def test_every_module_re_exports_the_one_parse_deadline():
    for fn in DEADLINE_REEXPORTS:
        assert fn is parse_deadline, (
            "a theory kept its own copy of parse_deadline; the elevation "
            "is meant to leave exactly one implementation"
        )


@pytest.mark.parametrize("fn", [parse_deadline] + DEADLINE_REEXPORTS)
def test_parse_deadline_reads_the_stated_date_not_the_close(fn):
    """deadline_drift's correction of 2026-08-29, which has to survive the
    move: actual close is A FUNCTION OF THE OUTCOME on a 'by D' market --
    a NO runs to the deadline, a YES stops when the event fires (median
    210 days early). Only the deadline STATED IN THE RULES is a sound time
    anchor, which is why this parses text rather than reading close_time.
    """
    assert fn(
        "If Alito retires before Jul 1, 2026, then the market resolves to Yes."
    ).startswith("2026-07-01")
    assert fn(
        "If X is traded on or before Feb 12, 2027, resolves Yes."
    ).startswith("2027-02-12")
    assert fn("If X happens, resolves Yes.") is None


@pytest.mark.parametrize("fn", [parse_deadline] + DEADLINE_REEXPORTS)
def test_parse_deadline_accepts_every_cue_word_it_claims(fn):
    """The four cue words are the whole population filter for DD-1, so a
    regression that silently dropped one would shrink the theory's
    population rather than raise."""
    for cue in ("before", "by", "on or before", "no later than"):
        got = fn(f"Resolves Yes if X happens {cue} Mar 4, 2027.")
        assert got is not None and got.startswith("2027-03-04"), cue


@pytest.mark.parametrize("fn", [parse_deadline] + DEADLINE_REEXPORTS)
def test_parse_deadline_returns_an_aware_utc_stamp(fn):
    """Callers subtract this from an aware close_time. A naive return
    would raise `can't subtract offset-naive and offset-aware datetimes`
    at the call site, not here -- the same trap days_until was elevated
    to close."""
    got = datetime.fromisoformat(fn("Resolves Yes if X occurs by Jul 1, 2026."))
    assert got.tzinfo is not None
    assert got.utcoffset() == timezone.utc.utcoffset(None)


@pytest.mark.parametrize("fn", [parse_deadline] + DEADLINE_REEXPORTS)
def test_parse_deadline_tolerates_missing_rules(fn):
    """Kalshi omits rules_primary on some markets; every caller passes the
    field straight through, so None must not raise."""
    assert fn(None) is None
    assert fn("") is None
