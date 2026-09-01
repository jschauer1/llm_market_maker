"""Kalshi executed-trade feed (public, unauthenticated).

Kalshi publishes the AGGRESSOR SIDE of every executed trade. That is most
of what flow analysis needs and the repo had no client for it until now;
`markets.py` gives quotes and `history.py` gives candles, and neither says
who crossed the spread.

Three properties of this feed were measured on 2026-09-01 and each one
changes what a caller may conclude. They are documented here because every
one of them is invisible from the payload and expensive to rediscover.

**Retention floor: 2026-06-26T00:00:00Z, a hard global boundary.** Six
long-lived markets -- 2028 nomination markets that have traded for over a
year -- were paged to exhaustion and every one bottomed out within minutes
of that timestamp (`KXPRESNOMD-28-KH` 4,338 trades, `KXPRESNOMD-28-GN`
16,048, `KXALIENS-27` 15,783). Nothing older is served for any market. So
a market's oldest returned trade is NOT its open: read it as the floor
unless it is comfortably above it. `/markets` archives settled markets at
~60 days, so this feed reaches roughly one week further and no more -- it
is NOT a route to history older than the archive floor, which is what a
first reading of it suggested.

Whether the floor is FIXED (a Kalshi migration date, so the window grows)
or ROLLING (~67 days, advancing daily) is undecided and cheap to settle:
re-measure `retention_floor()` on a later date and compare. The boundary
sitting exactly at midnight UTC of a specific date is weak evidence for
fixed; one re-measurement decides it.

**Ordering is newest-first, and `min_ts` does not seek backwards.** It is
a lower-bound filter applied to a newest-first walk: passing a min_ts of
2025-01-01 returns the most recent 1,000 trades, not the oldest. Reaching
old trades means paging through everything after them, so `max_pages` is
a real budget rather than a safety valve.

**The board-wide feed is not a bulk-collection route.** With no `ticker`,
40 pages (40,000 trades) covered about four minutes of wall-clock. Collect
per ticker.
"""

from __future__ import annotations

from tools.domain import Fetch, Trade
from tools.http import get_json
from tools.kalshi.markets import BASE_URL

#: Oldest trade timestamp the feed will serve, measured 2026-09-01 by
#: paging six long-lived markets to exhaustion. See the module docstring on
#: whether this is fixed or rolling -- callers should treat it as a floor
#: that may move, not a constant, and `retention_floor()` re-measures it.
RETENTION_FLOOR = "2026-06-26T00:00:00Z"

#: The only two joint values of (taker_side, taker_outcome_side,
#: taker_book_side) observed over 93,399 trades. A payload outside this set
#: means the schema changed and the one-bit collapse below is no longer safe.
_TAKER_SHAPES = {
    ("yes", "yes", "bid"),
    ("no", "no", "ask"),
}


class TradeFetchError(Exception):
    """A trade walk aborted because Kalshi's cursor stopped advancing.

    Unlike `markets.FetchError` this is not about representativeness: a
    prefix of the trade feed IS a meaningful sample, because the feed is
    ordered newest-first and the most recent trades are the ones a live
    signal reads. Partial walks are therefore normal here and exhausting
    `max_pages` is not an error condition.
    """


def _price(raw: dict, key: str) -> float:
    value = raw.get(key)
    if value is None or value == "":
        raise ValueError(f"trade has no {key} - Kalshi's schema may have changed")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"could not parse {key}={value!r} as a number - "
            "Kalshi's schema may have changed"
        ) from exc


def normalize(raw: dict) -> Trade:
    """Convert a raw Kalshi trade into the internal shape.

    Raises on a taker-field combination outside the two measured shapes.
    That is deliberate: the whole value of this feed is the aggressor side,
    so a schema change there must fail loudly rather than quietly collapse
    into a side that no longer means what the caller thinks.
    """
    shape = (
        raw.get("taker_side"),
        raw.get("taker_outcome_side"),
        raw.get("taker_book_side"),
    )
    if shape not in _TAKER_SHAPES:
        raise ValueError(
            f"unrecognized taker field combination {shape} - Kalshi's trade "
            "schema may have changed; the aggressor side can no longer be "
            "read as one bit and tools/kalshi/trades.py needs revisiting"
        )
    count_raw = raw.get("count_fp")
    try:
        count = float(count_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"could not parse count_fp={count_raw!r} as a number - "
            "Kalshi's schema may have changed"
        ) from exc
    return Trade(
        ticker=raw["ticker"],
        trade_id=raw["trade_id"],
        created_time=raw["created_time"],
        taker_side=shape[0],
        count=count,
        yes_price=_price(raw, "yes_price_dollars"),
        no_price=_price(raw, "no_price_dollars"),
        is_block_trade=bool(raw.get("is_block_trade", False)),
        raw=raw,
    )


def trades(
    ticker: str,
    *,
    min_ts: int | None = None,
    max_pages: int = 10,
    limit: int = 1000,
    fetch: Fetch | None = None,
) -> list[Trade]:
    """Executed trades for one market, newest first.

    Walks until the cursor runs out or `max_pages` is spent, whichever
    comes first. A partial walk is a valid newest-first prefix, not a
    biased slice -- see `TradeFetchError` on why that differs from
    `markets.list_open`. `min_ts` (Unix seconds) filters the walk but does
    not seek: it cannot reach past `max_pages` worth of recent trades.
    """
    get = fetch or get_json
    out: list[Trade] = []
    cursor: str | None = None
    seen: set[str] = set()
    for _ in range(max_pages):
        params: dict = {"ticker": ticker, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        if min_ts is not None:
            params["min_ts"] = min_ts
        payload = get(f"{BASE_URL}/markets/trades", params)
        batch = payload.get("trades") or []
        out.extend(normalize(raw) for raw in batch)
        cursor = payload.get("cursor")
        if not cursor or not batch:
            break
        if cursor in seen:
            raise TradeFetchError(
                f"cursor stopped advancing for {ticker} after {len(out)} trades"
            )
        seen.add(cursor)
    return out


def imbalance(rows: list[Trade]) -> float | None:
    """Volume-weighted taker imbalance in [-1, +1], or None with no volume.

    +1 is entirely yes-aggressive flow, -1 entirely no-aggressive. Weighted
    by contract count rather than trade count, so one 300-lot does not read
    the same as three 1-lots.
    """
    vy = sum(t.count for t in rows if t.taker_side == "yes")
    vn = sum(t.count for t in rows if t.taker_side == "no")
    total = vy + vn
    if total <= 0:
        return None
    return (vy - vn) / total


def retention_floor(
    probe_tickers: tuple[str, ...] = (
        "KXPRESNOMD-28-GN",
        "KXALIENS-27",
        "CONTROLH-2026-R",
    ),
    max_pages: int = 60,
    fetch: Fetch | None = None,
) -> str | None:
    """Re-measure the oldest trade the feed serves, by paging to exhaustion.

    Defaults to long-lived markets whose own open predates any plausible
    floor, so the answer is the feed's limit and not the market's age.
    Returns None if no probe returned a trade. Settles the fixed-vs-rolling
    question in the module docstring when compared against a past run.
    """
    oldest: str | None = None
    for ticker in probe_tickers:
        for t in trades(ticker, max_pages=max_pages, fetch=fetch):
            if oldest is None or t.created_time < oldest:
                oldest = t.created_time
    return oldest
