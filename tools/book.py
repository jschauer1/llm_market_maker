"""Book-side arithmetic: what the other side of a quote actually costs.

**Three functions and an identity. Not an execution model.** Execution
risk is *reported* to the user, never modelled (CLAUDE.md, baskets), so
nothing here touches slippage or depth, and it should not grow to.

**Why it exists.** On 2026-09-01 two theories died to the same structural
fact within an hour, in different populations, from opposite directions,
neither session aware of the other:

- `deadline_drift` priced a NO-buying strategy against `yes_ask`, when a
  NO buyer pays `1 - yes_bid`. Same 95 markets, same outcomes: a **+9.5
  point gap at z=2.60** off the ask, **+2.3 at z=0.64** off the bid. The
  edge was the spread.
- The `no-favorite-high-band` successor idea read a −3.90 favorite as a
  +3.90 underdog. The real underdog leg measures **−1.04**: both sides
  lose, and must.

Neither error was caught by a test, because both were arithmetically
self-consistent — just against the wrong price. That is what makes this
worth a module: the failure is silent and produces a plausible,
significant-looking positive result.

**The one fact underneath both.** On Kalshi the round trip is 2–5 points
and it is usually **larger than the effect being measured**. Taking either
side crosses the book, so the two asks sum to `1 + spread`, never to 1,
and the two legs' net edges are bound by an identity rather than by
symmetry:

    net(this side) + net(other side) == -round_trip_cost_pts

So **a one-sided net edge of −N does not imply +N on the other side.** It
implies −(round trip − N) over there. The step from "do not buy this" to
"so buy the other one" is worth −4.94 points on the measured mid band, and
it is available to make anywhere a theory reports a signed cell edge.
`test_book.py` pins the identity, which is what makes the mistake
impossible to make silently.

The fee model is `tools.sizing`'s and is not re-implemented here — five
studies already carry their own copy of `min(0.07*p*(1-p), 0.035)` and
this must not become a sixth.
"""

from __future__ import annotations

from tools.sizing import fee_pts, net_edge_pts

__all__ = ["other_side_ask", "round_trip_cost_pts", "net_edge_pts", "fee_pts"]


def other_side_ask(ask: float, spread: float) -> float:
    """What the opposite side costs to take, in decimal dollars.

    **Not `1 - ask`.** The complement of *this* ask is the other side's
    *bid*; buying the other side means crossing the spread again:

        this_bid  = ask - spread
        other_ask = 1 - this_bid = 1 - ask + spread

    Raises on inputs that are not quotes. The binding constraint is
    `spread <= ask` — a wider spread puts this side's *bid* below zero, so
    the pair does not exist — and it is not the obvious one: `ask=0.99,
    spread=0.05` looks extreme and is fine (bid 0.94, other side 0.06),
    while `ask=0.05, spread=0.07` looks milder and is impossible. Silently
    clamping instead of raising would reproduce exactly the class of error
    this module exists for.
    """
    if not 0.0 <= ask <= 1.0:
        raise ValueError(f"ask {ask} is not a price in [0, 1]")
    if spread < 0.0:
        raise ValueError(f"spread {spread} is negative")
    other = 1.0 - ask + spread
    if not 0.0 <= other <= 1.0:
        raise ValueError(
            f"ask {ask} with spread {spread} implies an other-side ask of "
            f"{other}, which is not a price in [0, 1]"
        )
    return other


def round_trip_cost_pts(ask: float, spread: float) -> float:
    """Total cost in percentage points of holding both sides: the spread
    plus each leg's fee.

    This is the bar any claimed edge has to clear, and on this exchange it
    runs 2–5 points depending on price — bigger than most effects anyone
    measures here.
    """
    return (
        spread * 100.0
        + fee_pts(ask)
        + fee_pts(other_side_ask(ask, spread))
    )
