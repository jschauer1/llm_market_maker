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


def list_open(limit: int = 200, max_pages: int = 10) -> list[dict]:
    """All open markets, walked via the events endpoint.

    Events carry the series ticker, which the candlestick endpoint needs, so
    fetching this way rather than /markets keeps history reachable later.
    """
    out: list[dict] = []
    cursor = ""
    for _ in range(max_pages):
        params = {
            "status": "open",
            "with_nested_markets": "true",
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor
        payload = get_json(f"{BASE_URL}/events", params=params)

        for event in payload.get("events", []):
            for raw in event.get("markets", []):
                market = normalize(raw)
                market["event_ticker"] = (
                    market["event_ticker"] or event.get("event_ticker")
                )
                market["series_ticker"] = (
                    market.get("series_ticker") or event.get("series_ticker")
                )
                if not market["title"]:
                    market["title"] = event.get("title")
                out.append(market)

        cursor = payload.get("cursor") or ""
        if not cursor:
            break
    return out


def list_settled(limit: int = 200, max_pages: int = 5) -> list[dict]:
    """Recently settled markets, with their results."""
    out: list[dict] = []
    cursor = ""
    for _ in range(max_pages):
        params = {"status": "settled", "limit": limit}
        if cursor:
            params["cursor"] = cursor
        payload = get_json(f"{BASE_URL}/markets", params=params)
        out.extend(normalize(raw) for raw in payload.get("markets", []))
        cursor = payload.get("cursor") or ""
        if not cursor:
            break
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
