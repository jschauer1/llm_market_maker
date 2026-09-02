"""Scalar strike-ladder geometry over `tools.domain.Market` objects.

Pure, deterministic, no network and no database: what a market's YES set
is as an interval, and which markets are strikes on the *same* underlying
quantity. Nothing here decides a trade; it says what a ladder is so a
theory can decide.

Elevated from `theories/structural_arb/scan.py` on 2026-08-29 under the
normal caller-count rule, with three real callers: `structural_arb`
(interval containment and exclusivity proofs), `smile_smoothing` (fitting
a monotone curve across a ladder), and
`theories/structural_arb/studies/answer/2026-08-29-structural-arb-violation-liquidity/probe.py`.
Behaviour is unchanged by the move — `structural_arb` re-exports these
names and its decision procedure is byte-identical in effect, so the move
does **not** bump its version.

Both traps below cost real money if re-derived carelessly, which is the
reason this is one shared implementation rather than a copy per theory.

**Boundary honesty.** `greater`/`greater_or_equal`/`less`/`less_or_equal`
carry their closure in the name and are treated as known. `between` looks
inclusive on Kalshi but is unverified per market, so its closure is
flagged UNKNOWN and any proof touching a `between` endpoint must demand
strict inequality rather than trusting the flag.

**Self-contradicting metadata proves nothing.** A one-sided strike type
carrying BOTH bounds is refused outright: the live example
`KXSTARSHIPSPACE-26-8.0` declares `strike_type='less'` with
`floor == cap == 8` while its title reads "exactly 8". Its true YES set is
the point {8}; believing the type field there manufactures a "riskless"
pair that loses whenever the outcome lands between the strikes.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from tools.domain import Market

NEG_INF = float("-inf")
POS_INF = float("inf")

#: (lo_closed, hi_closed) for the strike types whose closure is stated by
#: the type name itself. `between` is deliberately absent -- see module
#: docstring.
KNOWN_CLOSURE = {
    "greater": (False, False),           # hi at +inf
    "greater_or_equal": (True, False),
    "less": (False, False),              # lo at -inf
    "less_or_equal": (False, True),
}


@dataclass(frozen=True, slots=True)
class YesSet:
    """The set of outcomes on which a scalar-strike market resolves YES,
    as an interval. `boundary_known` is False for `between`, whose
    open/closed convention Kalshi does not state per market."""

    lo: float
    hi: float
    lo_closed: bool
    hi_closed: bool
    boundary_known: bool


def num(value: object) -> float | None:
    """A finite float, or None. Rejects bools (which are ints in Python),
    non-numerics, NaN and infinities."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return float(value)


def yes_set(market: Market) -> YesSet | None:
    """The market's YES interval, or None when it has no usable scalar
    strike (structured/custom/absent strike_type, or missing bounds).

    A one-sided type carrying BOTH bounds is refused -- see the module
    docstring's KXSTARSHIPSPACE case. Metadata that contradicts itself
    proves nothing."""
    raw = market.raw or {}
    st = raw.get("strike_type")
    floor = num(raw.get("floor_strike"))
    cap = num(raw.get("cap_strike"))
    if st in ("greater", "greater_or_equal"):
        if floor is None or cap is not None:
            return None
        lo_closed, _ = KNOWN_CLOSURE[st]
        return YesSet(floor, POS_INF, lo_closed, False, True)
    if st in ("less", "less_or_equal"):
        if cap is None or floor is not None:
            return None
        _, hi_closed = KNOWN_CLOSURE[st]
        return YesSet(NEG_INF, cap, False, hi_closed, True)
    if st == "between":
        if floor is None or cap is None or floor > cap:
            return None
        # Closure assumed closed for width, but flagged unknown: proofs
        # touching these endpoints must not rely on the assumption.
        return YesSet(floor, cap, True, True, False)
    return None


_STRIKE_TOKEN = re.compile(r"^[TB]?-?\d+(?:\.\d+)?$")
_DIGITS = re.compile(r"\d+")


def underlying_key(market: Market) -> str | None:
    """Which scalar quantity this market's strike thresholds refer to.

    One Kalshi event is NOT one underlying: KXMLBHIT-<game> holds a
    hits-ladder per *player*, KXNCAAFTEAMTOTAL-<game> a points-ladder
    per *team* -- same event_ticker, same strike_type, floors that
    compare numerically and mean nothing across underlyings. Interval
    proofs and curve fits are only valid within one underlying, so
    candidates group by this key and None never groups.

    Two conservative requirements, both mechanical:
    - the ticker's last segment must be a pure strike token
      (optionally T/B-prefixed number: "-2", "-B48.5", "-T4500"). A
      letters-bearing tail (ATHBSERVEN10, SJSU20, DEM11T30) is carrying
      identity, not just a threshold.
    - titles must be identical once digit runs are masked: "Brian
      Serven: 2+ hits?" and "Darell Hernaiz: 2+ hits?" separate here
      even when a series' tickers look uniform.
    A false split costs a candidate; a false merge costs real money."""
    seg = market.ticker.rsplit("-", 1)[-1]
    if not _STRIKE_TOKEN.match(seg.upper()):
        return None
    masked = _DIGITS.sub("#", market.title or "")
    masked = " ".join(masked.split()).lower()
    return masked or None


def strike_value(ys: YesSet) -> float | None:
    """The single threshold a one-sided strike is defined by, or None.

    `greater*` is defined by its floor, `less*` by its cap. A `between`
    interval has two edges and no single threshold, so it returns None --
    a ladder mixing the two cannot be ordered on one axis."""
    if ys.hi == POS_INF and ys.lo != NEG_INF:
        return ys.lo
    if ys.lo == NEG_INF and ys.hi != POS_INF:
        return ys.hi
    return None


def is_upper_tail(ys: YesSet) -> bool | None:
    """True for `greater*` (YES probability falls as the strike rises),
    False for `less*` (it rises), None when neither."""
    if ys.hi == POS_INF and ys.lo != NEG_INF:
        return True
    if ys.lo == NEG_INF and ys.hi != POS_INF:
        return False
    return None
