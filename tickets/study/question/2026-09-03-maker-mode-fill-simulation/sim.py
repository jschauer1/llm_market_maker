"""Book reconstruction and fill simulation from Kalshi per-trade prints.

This module is the whole instrument of the maker-mode study, and it is
deliberately **incapable of reading a settlement outcome**: nothing here
touches `result`, and `market_view()` drops the field before returning.
That is what lets `counts.py` establish the population without the run
having peeked at anything the pre-registration forbids.

The one idea it rests on is Kalshi's aggressor bit. Each print says which
side crossed, so it says which side of the book it consumed:

    s='yes'  the taker BOUGHT yes  ->  it lifted a resting YES ASK
    s='no'   the taker BOUGHT no   ->  it hit a resting YES BID

so the two aggressor sides straddle the spread and a last-touch bid/ask
is recoverable for markets whose candlesticks are empty. See
`tools/domain.Trade` for the measurement pinning that direction.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

# Kalshi's fee model, mirrored from tools/sizing.py so this study states
# its own arithmetic. Kept in sync by test_matches_repo_fee_model.
FEE_RATE = 0.07
FEE_CAP_DOLLARS = 0.035


def fee_pts(price: float) -> float:
    """Per-contract fee in percentage points for a contract at `price`."""
    p = min(max(price, 0.0), 1.0)
    return min(FEE_RATE * p * (1.0 - p), FEE_CAP_DOLLARS) * 100.0


def parse_ts(text: str) -> _dt.datetime:
    """Kalshi ISO-8601, with or without fractional seconds, always UTC."""
    return _dt.datetime.fromisoformat(text)


@dataclass(frozen=True)
class Print:
    """One executed trade, as the study reads it."""

    ts: _dt.datetime
    side: str        # aggressor: 'yes' or 'no'
    price: float     # YES price of the print
    count: float
    block: bool


@dataclass(frozen=True)
class Quote:
    """A last-touch reconstruction of the book at one instant."""

    bid: float
    ask: float
    bid_age_h: float
    ask_age_h: float

    @property
    def spread(self) -> float:
        return self.ask - self.bid


def load_prints(trades: list[dict]) -> list[Print]:
    """Normalize a corpus market's `trades` list, oldest first.

    The corpus stores newest-first (it is a newest-first API walk); every
    caller here wants chronological order, so sorting happens once.
    """
    out = [
        Print(
            ts=parse_ts(t["t"]),
            side=t["s"],
            price=float(t["p"]),
            count=float(t.get("c", 0.0)),
            block=bool(t.get("b", False)),
        )
        for t in trades
    ]
    out.sort(key=lambda p: p.ts)
    return out


def quote_at(
    prints: list[Print], at: _dt.datetime, *, max_age_h: float = 72.0
) -> Quote | None:
    """Last-touch bid and ask at `at`, or None if either side is stale.

    A side is observable only if a NON-BLOCK print of the matching
    aggressor side landed within `max_age_h` before `at`. Block trades are
    negotiated off-book and never sat in the book, so they say nothing
    about where it was.

    Returns None rather than a partial quote: an arm priced at a
    half-observable book is not priced at an executable price, which is
    the thing rule 0f exists to stop.
    """
    bid = ask = None
    bid_ts = ask_ts = None
    for p in prints:
        if p.ts > at:
            break
        if p.block:
            continue
        if p.side == "yes":
            ask, ask_ts = p.price, p.ts
        elif p.side == "no":
            bid, bid_ts = p.price, p.ts
    if bid is None or ask is None:
        return None
    bid_age = (at - bid_ts).total_seconds() / 3600.0
    ask_age = (at - ask_ts).total_seconds() / 3600.0
    if bid_age > max_age_h or ask_age > max_age_h:
        return None
    return Quote(bid=bid, ask=ask, bid_age_h=bid_age, ask_age_h=ask_age)


def fills(
    prints: list[Print],
    *,
    limit: float,
    start: _dt.datetime,
    end: _dt.datetime,
) -> Print | None:
    """The first print that would have filled a resting YES bid at `limit`.

    The rule is TRADE-THROUGH, not touch — the strictest of the three
    available and the one the spec's §10 asks for. A resting bid at
    `limit` is filled only by a non-block no-aggressor print at a price
    STRICTLY BELOW `limit`:

      * a print below `limit` means selling pressure went past my level,
        so whatever queue sat there was exhausted and I was taken;
      * a print AT `limit` is queue-ambiguous — the existing queue may
        have absorbed it all — and does not count.

    Placing at `bid + 1c` is what makes this conservative rather than
    pessimistic: the historical resting bids sat at `bid`, one cent below
    my level, so every aggressor who transacted there would have hit me
    first, and I am alone at my price rather than behind a queue.
    """
    for p in prints:
        if p.ts <= start:
            continue
        if p.ts > end:
            break
        if p.block or p.side != "no":
            continue
        if p.price < limit:
            return p
    return None


def fills_ask(
    prints: list[Print],
    *,
    limit: float,
    start: _dt.datetime,
    end: _dt.datetime,
) -> Print | None:
    """The mirror of `fills`: the first print filling a resting YES ASK.

    Buying NO passively means posting a YES ask one cent INSIDE the
    existing one, so the resting order is on the ask side and it is a
    yes-aggressor that consumes it. Trade-through again, in the mirrored
    direction: a non-block `s='yes'` print STRICTLY ABOVE `limit` means a
    buyer paid more than my offer and would have taken me first.
    """
    for p in prints:
        if p.ts <= start:
            continue
        if p.ts > end:
            break
        if p.block or p.side != "yes":
            continue
        if p.price > limit:
            return p
    return None


@dataclass(frozen=True)
class ArmCost:
    """What one execution arm actually paid, in dollars per contract."""

    price: float
    filled: bool
    fill_ts: _dt.datetime | None

    @property
    def cost_pts(self) -> float:
        """Total cost in points: price paid plus the fee at that price."""
        return self.price * 100.0 + fee_pts(self.price)

    @property
    def gross_pts(self) -> float:
        """Price paid only, fees excluded."""
        return self.price * 100.0


def cross(quote: Quote) -> ArmCost:
    """The control arm: pay the reconstructed ask now."""
    return ArmCost(price=quote.ask, filled=True, fill_ts=None)


def rest_then_cross(
    prints: list[Print],
    *,
    quote_t: Quote,
    quote_end: Quote,
    t: _dt.datetime,
    end: _dt.datetime,
    improvement: float = 0.01,
) -> ArmCost:
    """Post at bid+`improvement`; cross at `end` if it never filled.

    `improvement = 0` is the study's zero-improvement negative control in
    every respect but one: posting AT the bid is a queue-position bet, so
    the control that must return exactly zero is `improvement` set so the
    limit equals the ask (see `zero_control`), not this.
    """
    limit = round(quote_t.bid + improvement, 4)
    hit = fills(prints, limit=limit, start=t, end=end)
    if hit is not None:
        return ArmCost(price=limit, filled=True, fill_ts=hit.ts)
    return ArmCost(price=quote_end.ask, filled=False, fill_ts=None)


def zero_control(quote_t: Quote) -> ArmCost:
    """Negative control: post AT the crossing price, which is crossing.

    Its cost must equal `cross()`'s exactly, so the study's headline
    difference computed against it must be 0.00 for every market. Any
    drift is an accounting bug and voids the run.
    """
    return ArmCost(price=quote_t.ask, filled=True, fill_ts=None)


def market_view(row: dict) -> dict:
    """A corpus row with its prints parsed and its OUTCOME REMOVED.

    `counts.py` runs on these, which is how the pre-registration's claim
    that nothing outcome-shaped was looked at is enforced by the code
    rather than promised in prose.
    """
    return {
        "ticker": row["ticker"],
        "resolved_at": row["resolved_at"],
        "prints": load_prints(row.get("trades") or []),
    }
