"""Domain value types for the theory layer.

Frozen dataclasses, composition over inheritance. These name a structure
that already existed in the code rather than imposing a new one: a
candidate *was* a market dict plus three keys, and a scored candidate
*was* that plus three more, spread with `{**c, ...}` at two call sites and
written down nowhere.

The types make omissions impossible rather than discouraged, which is this
repo's stated preference:

- `ScoredCandidate` is a distinct type from `Candidate`, so "an unscored
  candidate cannot reach the ledger" is enforced rather than remembered.
- `Verdict` declares **no numeric field**, so an out-of-process judge has
  no channel through which to hand back a probability. An LLM cannot
  predict an edge; it can classify. Numbers enter downstream and
  mechanically, from a bucket's own realized win rate (`Edge.from_bucket`)
  or a theory's own arithmetic.
- `slots=True` forbids attribute injection, which kills the
  `{**c, "new_key": ...}` pattern these types replace.

`Market` is the unified Kalshi shape. `PolymarketMarket` is deliberately
its own type: the two platforms disagree on nearly every field name, and a
lossy union would be worse than two honest types. Polymarket is a research
source, never a bet destination.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from typing import Protocol

from tools.buckets import edge_for

VALID_EDGE_BASES = ("measured", "model", "prior")
VALID_DISPOSITIONS = ("screened", "endorsed", "rejected")
VALID_SIDES = ("yes", "no")


class Fetch(Protocol):
    """The transport seam every fetching function takes.

    One optional parameter is what makes a theory testable against a
    canned payload with no network and no monkeypatch -- the same
    discipline this repo already applies to clocks with an injectable
    `now`, applied to transports.
    """

    def __call__(self, url: str, params: dict | None = None,
                 timeout: int = 30) -> dict | list: ...


def _validate_price(price: object, label: str = "price") -> None:
    """Prices are decimal dollars in [0, 1], checked at construction.

    Same rules as `ledger._validate_entry_price`, which is retained -- the
    ledger is still callable directly and must stay defensive. This is the
    earlier, additional line: it catches the cents mistake
    (`entry_price=40`) before a value can be composed into a position.
    """
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        raise ValueError(
            f"{label} must be a number in decimal dollars [0, 1], "
            f"got {price!r}"
        )
    if isinstance(price, float) and math.isnan(price):
        # NaN compares False to every ordering check, so it would sail
        # through the bounds test below if not caught explicitly.
        raise ValueError(
            f"{label} must be a number in decimal dollars [0, 1], "
            f"got {price!r}"
        )
    if not 0.0 <= price <= 1.0:
        raise ValueError(
            f"{label} {price!r} is outside [0, 1]; prices are decimal "
            f"dollars, not cents -- {price} probably means "
            f"{float(price) / 100.0}"
        )


@dataclass(frozen=True, slots=True)
class Market:
    """One Kalshi market, exactly as `kalshi.markets.normalize` shapes it.

    The field set mirrors that function's dict one-for-one, `last_price`
    and `volume_24h` included. `raw` is the complete wire payload, passed
    through untouched and excluded from equality and repr: `tools/board.py`
    guarantees a cached board and a fetched board are identical *including*
    `raw`, because a thinner `raw` would make a theory reading an uncommon
    field work on a forced pull and silently return None on a cached one.
    """

    platform: str
    ticker: str
    title: str | None = None
    yes_bid: float | None = None
    yes_ask: float | None = None
    no_bid: float | None = None
    no_ask: float | None = None
    mid: float | None = None
    spread: float | None = None
    last_price: float | None = None
    volume: float | None = None
    volume_24h: float | None = None
    open_interest: float | None = None
    status: str | None = None
    is_open: bool = False
    close_time: str | None = None
    open_time: str | None = None
    result: str | None = None
    rules_primary: str | None = None
    event_ticker: str | None = None
    series_ticker: str | None = None
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.ticker:
            raise ValueError("Market.ticker must be non-empty")

    @classmethod
    def from_mapping(cls, m) -> "Market":
        """Build from a normalize()-shaped mapping, ignoring unknown keys.

        The JSON boundary: snapshots, fixtures, and any stored payload
        come back as plain dicts, and a field this type does not model yet
        must not crash a rebuild.
        """
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in dict(m).items() if k in names})


@dataclass(frozen=True, slots=True)
class PolymarketMarket:
    """One Polymarket market, as `polymarket.markets.normalize` shapes it.

    Field names match the historical dict exactly, so snapshotting and
    market matching keep working unchanged. `outcomes` and
    `outcome_prices` stay lists rather than tuples for the same reason.
    """

    platform: str
    market_id: str
    question: str | None = None
    slug: str | None = None
    outcomes: list = field(default_factory=list)
    outcome_prices: list = field(default_factory=list)
    implied_prob_yes: float | None = None
    best_bid: float | None = None
    best_ask: float | None = None
    volume: float | None = None
    liquidity: float | None = None
    end_date: str | None = None
    closed: bool = False
    description: str | None = None
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.market_id:
            raise ValueError("PolymarketMarket.market_id must be non-empty")

    @classmethod
    def from_mapping(cls, m) -> "PolymarketMarket":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in dict(m).items() if k in names})


@dataclass(frozen=True, slots=True)
class Leg:
    """One tradeable position in a market: a side, and what it costs."""

    market: Market
    side: str                     # "yes" | "no"
    price: float                  # the ask actually payable, never the mid

    def __post_init__(self) -> None:
        if self.side not in VALID_SIDES:
            raise ValueError(
                f"Leg.side must be one of {VALID_SIDES}, got {self.side!r}"
            )
        _validate_price(self.price, "Leg.price")


@dataclass(frozen=True, slots=True)
class Candidate:
    """A position: one leg normally, several when the payoff is joint.

    One type, no second-class path -- a single position is the one-leg
    case. `max_payout` is the most the position can pay and is what
    scoring normalizes against; 1.0 (a single contract) for singles, and
    for a NO-basket over k mutually exclusive outcomes, k-1. `min_payout`
    is the guaranteed floor -- the least the position can pay regardless
    of outcome, 0.0 (all-or-nothing) by default. Scoring grades only the
    portion of the payout above this floor; a floor equal to the ceiling
    is a riskless position (a bond, or an arbitrage if it costs less than
    it pays), not an error.
    """

    legs: tuple[Leg, ...]
    days_to_close: float
    max_payout: float = 1.0
    min_payout: float = 0.0

    def __post_init__(self) -> None:
        if not self.legs:
            raise ValueError(
                "Candidate needs at least one leg: the tradeability "
                "guarantee lives on the legs, so a position with none "
                "resolves to no Kalshi market"
            )
        mp = self.max_payout
        if (isinstance(mp, bool) or not isinstance(mp, (int, float))
                or (isinstance(mp, float) and math.isnan(mp)) or mp <= 0):
            raise ValueError(
                f"max_payout must be a positive number, got {mp!r}"
            )
        mn = self.min_payout
        if (isinstance(mn, bool) or not isinstance(mn, (int, float))
                or (isinstance(mn, float) and math.isnan(mn)) or mn < 0):
            raise ValueError(
                f"min_payout must be a non-negative number, got {mn!r}"
            )
        if mn > self.max_payout:
            raise ValueError(
                f"min_payout {mn!r} exceeds max_payout {self.max_payout!r}; "
                "a position cannot guarantee more than it can pay"
            )

    @property
    def is_basket(self) -> bool:
        return len(self.legs) > 1

    @property
    def cost(self) -> float:
        """What the whole position costs -- may exceed 1.0 for a basket."""
        return sum(leg.price for leg in self.legs)

    @property
    def key(self) -> str:
        """Stable identity, valid for every shape.

        The event key for a single leg, so sibling strikes deduped into
        one judgment share it -- which is how one verdict reaches them
        all. Sorted leg tickers for a basket, so leg ordering cannot
        produce two identities for one position.
        """
        if not self.is_basket:
            market = self.legs[0].market
            return market.event_ticker or market.ticker
        return "+".join(sorted(leg.market.ticker for leg in self.legs))

    def _single(self) -> Leg:
        if self.is_basket:
            raise ValueError(
                f"single-leg convenience called on a {len(self.legs)}-leg "
                "basket; use .legs, .cost, or .key instead -- silently "
                "returning leg 0 would drop the rest of the position"
            )
        return self.legs[0]

    @property
    def ticker(self) -> str:
        """Single-leg convenience. Raises on a basket."""
        return self._single().market.ticker

    @property
    def entry_price(self) -> float:
        """Single-leg convenience. Raises on a basket; use .cost."""
        return self._single().price

    @property
    def fav_side(self) -> str:
        """Single-leg convenience. Raises on a basket."""
        return self._single().side

    @property
    def title(self) -> str | None:
        """Single-leg convenience. Raises on a basket."""
        return self._single().market.title

    @property
    def event_key(self) -> str:
        """Single-leg convenience. Raises on a basket; use .key."""
        self._single()
        return self.key


@dataclass(frozen=True, slots=True)
class Edge:
    """An edge in percentage points, and where the number came from.

    `basis` is not decoration. `measured` means a confidence bucket's own
    realized win rate produced it, `model` a mechanical calculation, and
    `prior` a declared placeholder awaiting data. There is deliberately no
    basis meaning "it felt about right".
    """

    pts_net: float
    basis: str                    # "measured" | "model" | "prior"
    pts_gross: float | None = None
    fee_pts: float | None = None
    model_prob: float | None = None

    def __post_init__(self) -> None:
        if self.basis not in VALID_EDGE_BASES:
            raise ValueError(
                f"invalid basis {self.basis!r}; expected one of "
                f"{VALID_EDGE_BASES}"
            )

    @classmethod
    def from_bucket(cls, bucket: str, entry_price: float,
                    rates: dict, priors: dict) -> "Edge":
        """Turn a judge's bucket label into a number, mechanically.

        This is the only sanctioned path from an LLM's classification to a
        probability: `tools.buckets.edge_for` uses the bucket's realized
        win rate, so "when this theory says strong, it wins 78% of the
        time" is a fact about the past rather than an introspection. That
        function stays pure; this only wraps it.
        """
        pts_net, basis = edge_for(bucket, entry_price, rates, priors)
        measured = rates.get(bucket) if basis == "measured" else None
        return cls(
            pts_net=pts_net,
            basis=basis,
            model_prob=measured["win_rate"] if measured else None,
        )


@dataclass(frozen=True, slots=True)
class Verdict:
    """What an out-of-process judge may say about a candidate.

    Deliberately **no numeric field**, and a conventions test keeps it
    that way. Asked for a probability while looking at a price, a model
    produces something near that price and it feels like analysis; it is
    not. So the judge classifies against a stated definition and picks a
    bucket from the theory's declared scale, and there is no channel here
    for a probability, a confidence percentage, or an edge.
    """

    bucket: str
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not self.bucket or not self.bucket.strip():
            raise ValueError(
                "Verdict.bucket must be non-empty: a verdict is a label "
                "from the theory's declared scale"
            )


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """A candidate with an edge attached -- the only thing the ledger path
    accepts, so an unscored candidate cannot reach it."""

    candidate: Candidate
    edge: Edge
    confidence: str | None = None      # the theory's own bucket label
    rationale: str | None = None
    judged_blind: bool | None = None
    disposition: str = "screened"      # screened | endorsed | rejected
    evidence_source: str = "kalshi"    # "kalshi" | "polymarket" | ...
    evidence_market_id: str | None = None  # the non-Kalshi source id, if any

    def __post_init__(self) -> None:
        if self.disposition not in VALID_DISPOSITIONS:
            raise ValueError(
                f"invalid disposition {self.disposition!r}; expected one "
                f"of {VALID_DISPOSITIONS}"
            )


@dataclass(frozen=True, slots=True)
class ScreenResult:
    """Everything `screen()` produced: candidates, plus the counts that
    describe how it got them.

    The funnel counts exist because CLAUDE.md requires a gate to report
    what it removed by category -- a gate that drops silently is how a
    scan reports coverage it never had. They travel here because `Theory`
    is stateless and has nowhere else to put them.
    """

    candidates: tuple[Candidate, ...]
    funnel: dict = field(default_factory=dict)
    gate_removed: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScanResult:
    """What one theory produced in one run, uniform across every theory.

    This is what lets a session compose results from four theories without
    knowing what any of them does internally -- and what a subagent handed
    a single theory id returns.
    """

    theory_id: str
    theory_version: int
    status: str                        # the DB registry status
    scored: tuple[ScoredCandidate, ...]
    opportunity_ids: tuple[int, ...]
    funnel: dict                       # board -> screened -> ... -> recorded
    gate_removed: dict                 # by category; {} when there is no gate
    judged: bool                       # did stage 2 actually run
