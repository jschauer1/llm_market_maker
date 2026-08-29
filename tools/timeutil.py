"""Time helpers shared across theories.

One function so far. It lives here because three theory screens needed
it and a sibling-theory import is forbidden
(`test_no_theory_imports_a_sibling_theory`), which leaves `tools/` as the
only legal home for shared code.
"""

from __future__ import annotations

from datetime import datetime, timezone


def days_until(close_time: str | None,
               now: datetime | None = None) -> float | None:
    """Days from `now` to an ISO-8601 close, or None if unusable.

    Elevated 2026-08-29 from three near-copies that had drifted apart, in
    `insider_bias.screen`, `structural_arb.scan` and
    `calibration_harvest.screen`. They were **not** identical, so the
    merge was a behaviour decision rather than a move:

    - `insider_bias` and `calibration_harvest` subtracted `now` directly,
      and `calibration_harvest` made it *required*.
    - `structural_arb` additionally coerced a naive `now` to UTC.

    Hand a naive datetime to the first two and you got
    ``TypeError: can't subtract offset-naive and offset-aware
    datetimes``; hand it to the third and you got a number.

    This is the **superset**: `now` optional (defaulting to the current
    UTC time) *and* naive input coerced to UTC. That preserves every
    currently-working path byte for byte and changes behaviour only where
    the old code raised, so it is a no-op for every live decision and
    bumps no theory version. Verified at elevation that no caller
    anywhere passes a naive datetime -- two of the three would already
    have been crashing if one did.

    `now` stays the **second positional** parameter: at least one caller
    passes it positionally (`calibration_harvest.screen`), and reordering
    or renaming it would break that call site silently while still
    type-checking.
    """
    if not close_time:
        return None
    try:
        closes = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
    except ValueError:
        return None
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return (closes - reference).total_seconds() / 86400.0
