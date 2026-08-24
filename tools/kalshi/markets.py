"""Kalshi market data client (public, unauthenticated).

Kalshi's schema changed once already — prices moved from integer cents to
decimal-dollar strings (`yes_ask_dollars`) and sizes gained an `_fp` suffix.
`normalize` is the seam that absorbs that: everything downstream sees one
stable dict of floats, and a shape we do not recognize raises instead of
quietly producing zeros.

Error-handling contract: list_open, list_settled, and quotes all raise on a
single malformed row, propagating the whole page's failure. That is a
different contract from tools/polymarket/markets.py, whose functions skip
an individual bad row and only raise if an entire page fails to parse.
Don't assume one client's tolerance for partial failure carries over to
the other.
"""

from __future__ import annotations

from tools.http import get_json

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

OPEN_STATUSES = {"active", "open"}


class FetchError(Exception):
    """A list_open()/list_settled() walk aborted before reaching exhaustion.

    Kalshi's /events and /markets feeds are NOT sorted by close time (or any
    other useful order), so a partial walk is not a representative sample of
    the board -- it would be a biased slice that could silently exclude
    almost all near-term markets. Both functions therefore always page to
    exhaustion, with no opt-out; this only fires when Kalshi's own cursor
    gets stuck (the same cursor returned twice), which would otherwise loop
    forever. A wrong number is worse than an exception here, so this raises
    rather than returning a partial result that looks complete.
    """


def _price(raw: dict, key: str) -> float | None:
    """Parse a decimal-dollar string field. Absent is fine; garbage is not."""
    value = raw.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"could not parse {key}={value!r} as a number — "
            "Kalshi's schema may have changed"
        ) from exc


def normalize(raw: dict) -> dict:
    """Convert a raw Kalshi market into the internal shape."""
    ticker = raw.get("ticker")
    if not ticker:
        raise ValueError(
            f"market payload has no ticker — schema drift? keys={sorted(raw)}"
        )

    yes_bid = _price(raw, "yes_bid_dollars")
    yes_ask = _price(raw, "yes_ask_dollars")
    spread = (
        yes_ask - yes_bid if yes_bid is not None and yes_ask is not None else None
    )
    mid = (
        (yes_bid + yes_ask) / 2.0
        if yes_bid is not None and yes_ask is not None
        else None
    )
    status = raw.get("status")

    return {
        "platform": "kalshi",
        "ticker": ticker,
        "event_ticker": raw.get("event_ticker"),
        "series_ticker": raw.get("series_ticker"),
        "title": raw.get("title"),
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "no_bid": _price(raw, "no_bid_dollars"),
        "no_ask": _price(raw, "no_ask_dollars"),
        "mid": mid,
        "spread": spread,
        "last_price": _price(raw, "last_price_dollars"),
        "volume": _price(raw, "volume_fp"),
        "volume_24h": _price(raw, "volume_24h_fp"),
        "open_interest": _price(raw, "open_interest_fp"),
        "status": status,
        "is_open": status in OPEN_STATUSES,
        "close_time": raw.get("close_time"),
        "open_time": raw.get("open_time"),
        "result": raw.get("result") or None,
        "rules_primary": raw.get("rules_primary"),
        "raw": raw,
    }


def list_open(limit: int = 200) -> list[dict]:
    """All open markets, walked via the events endpoint to exhaustion.

    Events carry the series ticker, which the candlestick endpoint needs, so
    fetching this way rather than /markets keeps history reachable later.

    Always pages to exhaustion: the walk keeps going until Kalshi's cursor
    comes back empty. There is no partial-fetch option. Kalshi's /events feed
    is NOT sorted by close time, so a prefix of pages is not a random sample
    — it is a biased slice that can contain almost no near-term markets,
    which silently starves any screen with a tight horizon. A full walk
    against the live board takes on the order of 60 pages.

    Two loop-safety guards, since the walk is uncapped: tickers already seen
    on an earlier page are skipped rather than duplicated, and a cursor that
    stops advancing (the same cursor returned twice) raises `FetchError`
    rather than looping forever.
    """
    out: list[dict] = []
    seen_tickers: set[str] = set()
    cursor = ""
    pages = 0

    while True:
        params = {
            "status": "open",
            "with_nested_markets": "true",
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor
        payload = get_json(f"{BASE_URL}/events", params=params)
        pages += 1

        for event in payload.get("events", []):
            for raw in event.get("markets", []):
                market = normalize(raw)
                if market["ticker"] in seen_tickers:
                    continue
                seen_tickers.add(market["ticker"])
                market["event_ticker"] = (
                    market["event_ticker"] or event.get("event_ticker")
                )
                market["series_ticker"] = (
                    market.get("series_ticker") or event.get("series_ticker")
                )
                if not market["title"]:
                    market["title"] = event.get("title")
                out.append(market)

        new_cursor = payload.get("cursor") or ""
        if not new_cursor:
            break
        if new_cursor == cursor:
            raise FetchError(
                f"list_open stopped after {pages} page(s) "
                f"({len(out)} markets) -- Kalshi returned the same cursor "
                "twice in a row, which looks like a server-side pagination "
                "bug. Aborting rather than looping forever."
            )
        cursor = new_cursor

    return out


def list_settled(
    limit: int = 200,
    min_close_ts: int | None = None,
    max_close_ts: int | None = None,
    raw_filter=None,
    on_page=None,
) -> list[dict]:
    """Recently settled markets, with their results, walked to exhaustion.

    Same contract as list_open: always pages until Kalshi's cursor comes
    back empty, with the same two loop-safety guards (tickers already seen
    are skipped rather than duplicated; a cursor that stops advancing raises
    `FetchError` rather than looping forever). There is no partial-fetch
    option, for the same reason list_open has none -- a prefix of pages is
    not a representative sample.

    Kalshi's settled history spans the platform's whole lifetime, so an
    unbounded walk here can be considerably larger and slower than
    list_open's ~60 pages against the live board -- easily hundreds of
    thousands of rows. `min_close_ts`/`max_close_ts` (Unix seconds) bound the
    walk to markets whose close_time falls in that window; Kalshi's API
    honours both and this is the only way to keep a backtest's fetch volume
    bounded rather than scanning the platform's entire history.

    `raw_filter`, if given, is called with each raw (pre-normalize) dict and
    must return True to keep it. It runs before the expensive part of
    `normalize` (parsing every price field), so a caller that only wants a
    small slice of a huge settled window (a backtest's coarse pre-filter,
    say) skips that cost for everything it would discard anyway --
    normalizing every field of a multi-million-row walk when only a few
    hundred rows survive is wasted work. The ticker-presence check that
    `normalize` would raise on always runs first, unconditionally, so
    `raw_filter` cannot mask a row with no ticker at all; it can only skip
    validation of a filtered-out row's *other* fields, which is the trade
    this exists for. `on_page`, if given, is called after each page with
    `(pages, len(out))` -- a multi-hundred-thousand-row walk can take
    minutes, and a caller driving a long background run wants visibility
    into that, not just a final return value.
    """
    out: list[dict] = []
    seen_tickers: set[str] = set()
    cursor = ""
    pages = 0

    while True:
        params = {"status": "settled", "limit": limit}
        if min_close_ts is not None:
            params["min_close_ts"] = min_close_ts
        if max_close_ts is not None:
            params["max_close_ts"] = max_close_ts
        if cursor:
            params["cursor"] = cursor
        payload = get_json(f"{BASE_URL}/markets", params=params)
        pages += 1

        for raw in payload.get("markets", []):
            ticker = raw.get("ticker")
            if not ticker:
                raise ValueError(
                    f"market payload has no ticker — schema drift? "
                    f"keys={sorted(raw)}"
                )
            if ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)
            if raw_filter is not None and not raw_filter(raw):
                continue
            out.append(normalize(raw))

        if on_page is not None:
            on_page(pages, len(out))

        new_cursor = payload.get("cursor") or ""
        if not new_cursor:
            break
        if new_cursor == cursor:
            raise FetchError(
                f"list_settled stopped after {pages} page(s) "
                f"({len(out)} markets) -- Kalshi returned the same cursor "
                "twice in a row, which looks like a server-side pagination "
                "bug. Aborting rather than looping forever."
            )
        cursor = new_cursor

    return out


def quotes(tickers: list[str]) -> dict[str, dict]:
    """Live re-quote for specific tickers, keyed by ticker.

    A ticker absent from the returned dict was not found or not returned
    by Kalshi — the caller must not assume every requested ticker appears.
    """
    if not tickers:
        return {}
    payload = get_json(
        f"{BASE_URL}/markets",
        params={"tickers": ",".join(tickers), "limit": len(tickers)},
    )
    return {
        market["ticker"]: market
        for market in (normalize(raw) for raw in payload.get("markets", []))
    }
