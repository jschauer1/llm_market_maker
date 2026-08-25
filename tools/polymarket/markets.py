"""Polymarket market data via the public Gamma API.

Polymarket is a research and signal source, never a bet destination — the
user can only wager on Kalshi. Anything found here must be resolved to a
Kalshi ticker through tools/match_market.py before it can be recorded as an
opportunity.

Gamma returns `outcomes` and `outcomePrices` as JSON-encoded STRINGS rather
than arrays, which is the main parsing wrinkle. The API is public but
undocumented enough that shapes may shift, so parse failures raise.

Every fetching function here takes an optional `fetch` transport, defaulting
to `get_json` at call time. That default is resolved in the body rather than
in the signature on purpose: binding the function object at import time would
freeze it into the signature and silently defeat the
`monkeypatch.setattr(markets, "get_json", ...)` this module's own tests use.
The parameter is what lets a backtest, a replay, or a theory substitute a
canned payload, none of which can reach for monkeypatch.
"""

from __future__ import annotations

import json

from tools.domain import Fetch, PolymarketMarket
from tools.http import get_json

GAMMA_URL = "https://gamma-api.polymarket.com/markets"

YES_NO = ("yes", "no")


def _string_array(raw: dict, key: str) -> list:
    """Gamma encodes arrays as JSON strings; tolerate both forms."""
    value = raw.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"could not parse {key}={value!r} as JSON — "
            "Polymarket's schema may have changed"
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(f"{key} did not decode to a list: {parsed!r}")
    return parsed


def _number(raw: dict, key: str) -> float | None:
    value = raw.get(key)
    if value is None or value == "":
        return None
    return float(value)


def normalize(raw: dict) -> PolymarketMarket:
    """Convert a raw Gamma market into the internal shape."""
    market_id = raw.get("conditionId")
    if not market_id:
        raise ValueError(
            f"market payload has no conditionId — schema drift? "
            f"keys={sorted(raw)}"
        )

    outcomes = _string_array(raw, "outcomes")
    prices = [float(p) for p in _string_array(raw, "outcomePrices")]

    implied_yes = None
    if len(outcomes) == 2 and len(prices) == 2:
        labels = [str(o).strip().lower() for o in outcomes]
        if labels == list(YES_NO):
            implied_yes = prices[0]
        elif labels == list(reversed(YES_NO)):
            implied_yes = prices[1]

    return PolymarketMarket(
        platform="polymarket",
        market_id=market_id,
        question=raw.get("question"),
        slug=raw.get("slug"),
        outcomes=outcomes,
        outcome_prices=prices,
        implied_prob_yes=implied_yes,
        best_bid=_number(raw, "bestBid"),
        best_ask=_number(raw, "bestAsk"),
        volume=_number(raw, "volumeNum"),
        liquidity=_number(raw, "liquidityNum"),
        end_date=raw.get("endDate"),
        closed=bool(raw.get("closed")),
        description=raw.get("description"),
        raw=raw,
    )


def _fetch(params: dict, fetch: Fetch | None = None) -> list[PolymarketMarket]:
    fetch = fetch or get_json
    payload = fetch(GAMMA_URL, params=params)
    rows = payload if isinstance(payload, list) else payload.get("data", [])
    out = []
    for raw in rows:
        try:
            out.append(normalize(raw))
        except ValueError:
            # One malformed row should not sink the page. The shape guard
            # still fires for anything that reaches a caller.
            continue
    if rows and not out:
        raise ValueError(
            f"received {len(rows)} row(s) but none parsed — "
            "Polymarket's schema may have changed"
        )
    return out


def list_open(limit: int = 100, order: str = "volumeNum", *,
              fetch: Fetch | None = None) -> list[PolymarketMarket]:
    """Open markets, most-traded first by default."""
    return _fetch(
        {
            "closed": "false",
            "limit": limit,
            "order": order,
            "ascending": "false",
        },
        fetch=fetch,
    )


def list_resolved(limit: int = 100, *,
                  fetch: Fetch | None = None) -> list[PolymarketMarket]:
    """Closed markets. Note that resolution encoding in `outcomePrices` is
    inconsistent for older markets, so treat these as signal, not truth."""
    return _fetch({"closed": "true", "limit": limit}, fetch=fetch)
