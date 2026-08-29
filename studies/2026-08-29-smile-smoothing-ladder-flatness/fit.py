"""Pure arithmetic for the smile-smoothing scanner.

Deterministic math over `tools.domain.Market`: assemble strike ladders,
fit a monotone probability curve across each, and find the one strike
furthest off it. No network, no database, no model. `theory.py` adapts
this to the contract; this module decides.

The shape constraint is the whole theory. A one-sided strike ladder on a
scalar underlying has a probability curve whose direction is forced by
arithmetic, not by any modelling assumption:

- `greater*` rungs price P(X > k), which is **non-increasing** in k.
- `less*` rungs price P(X < k), which is **non-decreasing** in k.

Isotonic (pool-adjacent-violators) regression is the least-squares fit
subject to exactly that constraint and nothing else -- no distribution,
no smoothness, no parameters. A rung far off the fit is a strike the
ladder as a whole disagrees with.

**Why the fit is evaluated at mids but traded at asks.** The consensus
estimate is the mid; the price actually payable is the ask. Fitting on
mids and then crediting the trade at the mid is the spec's named trap and
would manufacture edge on exactly the thinnest rungs, where the half
spread is largest. So `candidate()` fits on mids and then requires the
edge to clear at the executable ask, which is what `entry_price` records.

**What this module deliberately does not trade.** A ladder whose quotes
are already non-monotone at executable prices contains a hard structural
violation -- a riskless trade that `structural_arb` owns and that is
strictly better than this soft one. Those ladders are dropped here rather
than competed for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from tools.domain import Market
from tools.ladders import is_upper_tail, strike_value, underlying_key, yes_set
from tools.sizing import fee_pts

#: A ladder needs this many liquid rungs before a fit means anything.
#: Below 4, isotonic regression essentially interpolates the points and
#: every rung sits on its own fit, so no deviation can be measured.
MIN_RUNGS = 4

#: Per-rung liquidity floors. A rung failing either is dropped from the
#: ladder before fitting -- a stale quote is not evidence about the
#: curve, and it is not tradeable either.
MIN_VOLUME = 200.0
MAX_SPREAD = 0.10

#: Required edge beyond fees before a deviation is a candidate, in
#: percentage points. Deliberately wider than structural_arb's 1c/leg:
#: this trade is not riskless, so the buffer absorbs both execution slip
#: and the fit's own error.
BUFFER_PTS = 3.0

#: Ladders closing outside this window are not scanned. The lower bound
#: keeps settled-but-open rungs out; the upper matches the shared screen.
MIN_DAYS_TO_CLOSE = 0.0
MAX_DAYS_TO_CLOSE = 14.0


@dataclass(frozen=True, slots=True)
class Rung:
    """One strike on a ladder, with both executable sides."""

    market: Market
    strike: float
    mid: float
    yes_ask: float
    no_ask: float


@dataclass(frozen=True, slots=True)
class Ladder:
    """Liquid one-sided strikes on a single underlying, strike-ordered."""

    event_ticker: str
    underlying: str
    upper_tail: bool          # True: P(YES) non-increasing in strike
    rungs: tuple[Rung, ...]


@dataclass(frozen=True, slots=True)
class Finding:
    """The single most off-curve rung of one ladder, priced to trade."""

    ladder: Ladder
    rung: Rung
    fitted: float             # the curve's YES probability at this strike
    side: str                 # 'yes' or 'no' -- the side that moves toward fit
    entry_price: float        # the ask actually payable on that side
    model_prob: float         # fitted probability OF THE SIDE TAKEN
    edge_pts_gross: float
    fee_pts: float
    edge_pts_net: float


def pava(values: list[float], increasing: bool = True) -> list[float]:
    """Pool-adjacent-violators isotonic regression, unweighted.

    Returns the least-squares fit to `values` subject only to being
    monotone in the requested direction. Implemented directly rather than
    pulled from scipy because this fit *is* the decision procedure: it
    should be readable in the same file that trades on it.

    Blocks of a running mean are merged while the previous block violates
    the constraint, which is the standard O(n) formulation.
    """
    if not values:
        return []
    if not increasing:
        return [-v for v in pava([-v for v in values], increasing=True)]

    # Each block: [sum, count]. Merge left while out of order.
    blocks: list[list[float]] = []
    for v in values:
        blocks.append([float(v), 1.0])
        while len(blocks) > 1:
            s2, n2 = blocks[-1]
            s1, n1 = blocks[-2]
            if s1 / n1 <= s2 / n2:
                break
            blocks[-2] = [s1 + s2, n1 + n2]
            blocks.pop()

    out: list[float] = []
    for total, count in blocks:
        out.extend([total / count] * int(count))
    return out


def days_until(close_time: str | None,
               now: datetime | None = None) -> float | None:
    """Days from `now` to an ISO-8601 close.

    FOURTH copy of this helper in the repo (the others are in
    `insider_bias.screen`, `structural_arb.scan` and
    `calibration_harvest.screen`), and `structural_arb.scan`'s copy
    already carries the note "promote to tools/ if a third caller
    appears" -- so the elevation trigger is long since met.

    It is NOT elevated here on purpose. A migration means one
    implementation and deleting every local copy, and one of those copies
    lives in `theories/calibration_harvest/`, which another session was
    actively writing when this was written (2026-08-29). Half-migrating
    across a live working tree is worse than a documented fourth copy.
    Left as one clean task: move it to `tools/`, repoint all four, delete
    the locals. A sibling-theory import would have been the one
    genuinely forbidden option
    (`test_no_theory_imports_a_sibling_theory`).
    """
    if not close_time:
        return None
    try:
        closes = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
    except ValueError:
        return None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (closes - now).total_seconds() / 86400.0


def _ask(price: float | None) -> float | None:
    if price is None:
        return None
    p = float(price)
    return p if 0.0 < p < 1.0 else None


def build_ladders(markets: list[Market], now=None) -> list[Ladder]:
    """Group markets into liquid, one-sided, strike-ordered ladders.

    Grouping is by `(event_ticker, underlying_key)`, never by event alone:
    one Kalshi event routinely holds a separate ladder per player or per
    team, whose strikes compare numerically and mean nothing across
    underlyings. `tools.ladders.underlying_key` carries that rule and
    returns None rather than guessing; None never groups.
    """
    groups: dict[tuple[str, str], list[Rung]] = {}
    tails: dict[tuple[str, str], set[bool]] = {}
    for m in markets:
        if not m.is_open or not m.event_ticker:
            continue
        key_u = underlying_key(m)
        if key_u is None:
            continue
        ys = yes_set(m)
        if ys is None:
            continue
        strike = strike_value(ys)
        tail = is_upper_tail(ys)
        if strike is None or tail is None:
            continue          # `between` rungs have no single threshold
        days = days_until(m.close_time, now=now)
        if days is None or not (MIN_DAYS_TO_CLOSE < days <= MAX_DAYS_TO_CLOSE):
            continue
        if m.volume is None or m.volume < MIN_VOLUME:
            continue
        if m.spread is None or m.spread > MAX_SPREAD:
            continue
        ya, na, mid = _ask(m.yes_ask), _ask(m.no_ask), m.mid
        if ya is None or na is None or mid is None:
            continue
        key = (m.event_ticker, key_u)
        groups.setdefault(key, []).append(
            Rung(market=m, strike=strike, mid=float(mid),
                 yes_ask=ya, no_ask=na))
        tails.setdefault(key, set()).add(tail)

    out = []
    for key, rungs in groups.items():
        tail_set = tails[key]
        if len(tail_set) != 1:
            continue          # mixed greater/less: not one orderable axis
        if len(rungs) < MIN_RUNGS:
            continue
        strikes = [r.strike for r in rungs]
        if len(set(strikes)) != len(strikes):
            continue          # duplicate strikes: the axis is not a function
        out.append(Ladder(event_ticker=key[0], underlying=key[1],
                          upper_tail=next(iter(tail_set)),
                          rungs=tuple(sorted(rungs, key=lambda r: r.strike))))
    return out


def has_hard_violation(ladder: Ladder) -> bool:
    """True when the ladder's *executable* quotes are already non-monotone.

    That is a riskless structural-arb trade (a subset bid above its
    superset's ask). It is strictly better than this theory's soft trade,
    so such ladders are conceded rather than competed for -- and betting a
    fit against a book that is already arbitrageable would be pricing off
    a quote someone is about to take.
    """
    asks = [r.yes_ask for r in ladder.rungs]
    bids = [r.market.yes_bid for r in ladder.rungs]
    if any(b is None for b in bids):
        return False
    for i in range(len(asks) - 1):
        lo_ask, hi_bid = asks[i], bids[i + 1]
        lo_bid, hi_ask = bids[i], asks[i + 1]
        if ladder.upper_tail:
            # P must fall with strike: a higher strike bid above a lower
            # strike's ask is the violation.
            if hi_bid > lo_ask:
                return True
        else:
            if lo_bid > hi_ask:
                return True
    return False


def fit_ladder(ladder: Ladder) -> list[float]:
    """The monotone YES-probability curve implied by the whole ladder."""
    mids = [r.mid for r in ladder.rungs]
    return pava(mids, increasing=not ladder.upper_tail)


def candidate(ladder: Ladder, buffer_pts: float = BUFFER_PTS) -> Finding | None:
    """The ladder's single best off-curve rung, or None.

    **One candidate per ladder, by construction.** Rungs of one ladder are
    not independent bets -- they are strikes on the same underlying whose
    outcomes are mechanically linked -- so emitting several would fill the
    ledger with internally hedged rows and count one draw as many.
    """
    if has_hard_violation(ladder):
        return None
    fitted = fit_ladder(ladder)
    best: Finding | None = None
    for rung, fit in zip(ladder.rungs, fitted):
        if rung.mid < fit:
            side, entry, model = "yes", rung.yes_ask, fit
        elif rung.mid > fit:
            side, entry, model = "no", rung.no_ask, 1.0 - fit
        else:
            continue
        gross = (model - entry) * 100.0
        fee = fee_pts(entry)
        net = gross - fee
        if net < buffer_pts:
            continue
        f = Finding(ladder=ladder, rung=rung, fitted=fit, side=side,
                    entry_price=entry, model_prob=model,
                    edge_pts_gross=gross, fee_pts=fee, edge_pts_net=net)
        if best is None or f.edge_pts_net > best.edge_pts_net:
            best = f
    return best


def scan(markets: list[Market], now=None,
         buffer_pts: float = BUFFER_PTS) -> tuple[list[Finding], dict]:
    """Every ladder's best off-curve rung, plus a funnel for reporting."""
    ladders = build_ladders(markets, now=now)
    hard = [l for l in ladders if has_hard_violation(l)]
    findings = [f for f in (candidate(l, buffer_pts) for l in ladders)
                if f is not None]
    funnel = {
        "board_markets": len(markets),
        "ladders": len(ladders),
        "ladders_conceded_to_structural_arb": len(hard),
        "findings": len(findings),
    }
    return findings, funnel
