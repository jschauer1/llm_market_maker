"""Classification shared by the live screen and the replay.

Both `theory.py` and `backtest.py` need these, and neither may import the
other: `theory.py` is the decision procedure and `backtest.py` replays it,
so an import in either direction is a cycle. They live here instead.
"""

from __future__ import annotations

import re

#: Where |imbalance| splits the population. Recorded on every row as
#: `extra.flow_bucket` so a slice predicate can address it -- slice
#: predicates match `extra` exactly, so the bucket has to be a categorical
#: label rather than a number to compare against.
EXTREME_IMBALANCE = 0.9

#: A strike suffix that is a bare number, optionally prefixed by the
#: threshold/band markers Kalshi uses (T=above, B=below). Everything else
#: names an entity.
_NUMERIC_STRIKE = re.compile(r"^[TB]?-?\d+(\.\d+)?$")


def flow_bucket(imbalance: float) -> str:
    """Which measured population a candidate belongs to."""
    return "extreme" if abs(imbalance) >= EXTREME_IMBALANCE else "strong"


def is_single_name(ticker: str) -> bool:
    """True when the ticker's strike names an entity rather than a number.

    `KXPRESNOMD-28-KH` (a person) is single-name; `KXHIGHTSFO-26AUG01-T73`
    (a temperature) is broad-based. This is the structural single-name /
    broad-based split the Stanford study localises its effect in, derived
    from the ticker rather than from judgment -- a market's own name is a
    published fact, so no prompt is written to re-derive it.

    KNOWN IMPURITY, left deliberately unfixed: city-coded weather
    (`KXRAIN-26JUL28-BOS`) and outcome-coded game markets
    (`KXMLSGAME-...-TIE`) classify as single-name because their suffix is
    alphabetic. The split was PRE-REGISTERED in this form on 2026-09-01
    and re-tuning it after seeing the result is exactly the contamination
    the pre-registration exists to prevent. It measured no difference
    either way (+0.71 single-name vs +0.69 broad-based), so the impurity
    did not decide anything.
    """
    parts = ticker.split("-")
    if len(parts) < 3:
        return True
    return not _NUMERIC_STRIKE.match(parts[-1])


def event_key(ticker: str) -> str:
    """The market's event -- siblings inside one event are correlated."""
    parts = ticker.split("-")
    return "-".join(parts[:-1]) if len(parts) >= 3 else ticker
