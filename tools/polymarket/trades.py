"""Polymarket trade and holder data — the raw material for whale-following.

Polymarket exposes per-trade wallet identity publicly, which Kalshi does not.
That asymmetry is the point: a theory can watch who is betting what here and
then look for the equivalent Kalshi market to actually trade.

`filterAmount` filters by USD notional server-side, so finding large trades
does not require pulling the whole tape.
"""

from __future__ import annotations

from collections import defaultdict

from tools.http import get_json

DATA_URL = "https://data-api.polymarket.com"
DEFAULT_WHALE_USD = 10000


def normalize_trade(raw: dict) -> dict:
    """Convert a raw trade into the internal shape, with USD notional."""
    wallet = raw.get("proxyWallet")
    if not wallet:
        raise ValueError(
            f"trade has no proxyWallet — schema drift? keys={sorted(raw)}"
        )

    size = raw.get("size")
    price = raw.get("price")
    usd = None
    if size is not None and price is not None:
        usd = float(size) * float(price)

    return {
        "wallet": wallet,
        "name": raw.get("name") or raw.get("pseudonym"),
        "side": raw.get("side"),
        "size": float(size) if size is not None else None,
        "price": float(price) if price is not None else None,
        "usd": usd,
        "market_id": raw.get("conditionId"),
        "title": raw.get("title"),
        "outcome": raw.get("outcome"),
        "timestamp": raw.get("timestamp"),
        "raw": raw,
    }


def recent(
    limit: int = 100,
    min_usd: float | None = None,
    taker_only: bool = True,
) -> list[dict]:
    """Recent trades, optionally filtered by USD notional server-side."""
    params: dict = {"limit": limit}
    if taker_only:
        params["takerOnly"] = "true"
    if min_usd is not None:
        params["filterAmount"] = min_usd

    payload = get_json(f"{DATA_URL}/trades", params=params)
    rows = payload if isinstance(payload, list) else []
    out = []
    for raw in rows:
        try:
            out.append(normalize_trade(raw))
        except ValueError:
            continue
    if rows and not out:
        raise ValueError(
            f"received {len(rows)} row(s) but none parsed — "
            "Polymarket's schema may have changed"
        )
    return out


def whales(
    min_usd: float = DEFAULT_WHALE_USD, limit: int = 100
) -> list[dict]:
    """Large recent trades, biggest first."""
    found = recent(limit=limit, min_usd=min_usd)
    return sorted(found, key=lambda t: t["usd"] or 0.0, reverse=True)


def _normalize_holder(holder: dict, token: str | None) -> dict:
    """Convert a raw holder entry into the internal shape."""
    wallet = holder.get("proxyWallet")
    if not wallet:
        raise ValueError(
            f"holder has no proxyWallet — schema drift? keys={sorted(holder)}"
        )
    return {
        "wallet": wallet,
        "name": holder.get("name") or holder.get("pseudonym"),
        "amount": holder.get("amount"),
        "outcome_index": holder.get("outcomeIndex"),
        "token": token,
    }


def holders(market_id: str, limit: int = 20) -> list[dict]:
    """Largest position holders in a market, across both outcome tokens."""
    payload = get_json(
        f"{DATA_URL}/holders", params={"market": market_id, "limit": limit}
    )
    rows = payload if isinstance(payload, list) else []
    out = []
    total = 0
    for block in rows:
        if not isinstance(block, dict):
            # A non-dict block (e.g. a bare string) has no "holders" to
            # read — skip it rather than crashing the whole call.
            continue
        token = block.get("token")
        for holder in block.get("holders", []):
            total += 1
            try:
                out.append(_normalize_holder(holder, token))
            except ValueError:
                # One malformed holder should not sink the whole response.
                continue
    if total and not out:
        raise ValueError(
            f"received {total} holder row(s) but none parsed — "
            "Polymarket's schema may have changed"
        )
    return out


def by_wallet(trade_list: list[dict]) -> dict[str, list[dict]]:
    """Group normalized trades by wallet, for per-trader analysis."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for trade in trade_list:
        grouped[trade["wallet"]].append(trade)
    return dict(grouped)
