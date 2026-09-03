"""Time helpers shared across theories.

Everything here arrived the same way: a helper written inside one theory
that grew a second real caller in another. A theory may not import a
sibling theory's folder (`test_no_theory_imports_a_sibling_theory`), so
`tools/` is the only legal home for shared code, and elevation is a
**migration** -- one implementation, the local copy deleted and re-exported
-- never a second copy.

  `days_until`      elevated 2026-08-29 from three drifted near-copies.
  `parse_deadline`  elevated 2026-09-03 from `deadline_drift`.
"""

from __future__ import annotations

import re
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


# --------------------------------------------------------- parse_deadline

_MON = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_DEADLINE = re.compile(
    rf"\b(?:before|by|on or before|no later than)\s+"
    rf"({_MON})\w*\s+(\d{{1,2}}),?\s*(\d{{4}})", re.IGNORECASE)
_MONI = {m: i + 1 for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def parse_deadline(rules: str | None) -> str | None:
    """The deadline STATED IN THE RULES -- the only sound time anchor.

    **Why the stated date and not `close_time`.** This is deadline_drift's
    correction of 2026-08-29, and it is the whole reason this function
    parses prose instead of reading a published field. On a "by date D"
    market the actual close is *a function of the outcome*: a NO runs all
    the way to D, while a YES stops the moment the event fires -- a median
    of 210 days earlier. So `close_time` leaks the answer, and anchoring on
    it makes any timing measurement look like an edge when it is only
    hindsight. The date written in the rules is fixed before the outcome is
    known, which is what makes it usable as a decision point.

    Returns an **aware UTC** ISO-8601 stamp, or None when no deadline is
    stated. Aware matters: every caller subtracts this from an aware
    `close_time`, and a naive return would raise at the call site rather
    than here.

    Elevated 2026-09-03 from `theories.deadline_drift.collect_settled`,
    which had been its only home. `no_side_premium.exposure_measure` became
    a second caller and imported it across the theory boundary, which is
    forbidden and had the suite red; the caller-count rule in CLAUDE.md was
    already satisfied, so the fix was the move rather than an exemption.
    Behaviour is byte-for-byte the pre-move implementation -- the regex and
    the month table came across unchanged -- so this bumps no theory
    version and alters no recorded decision.
    """
    hit = _DEADLINE.search(rules or "")
    if not hit:
        return None
    return datetime(int(hit.group(3)), _MONI[hit.group(1)[:3].title()],
                    int(hit.group(2)), tzinfo=timezone.utc).isoformat()
