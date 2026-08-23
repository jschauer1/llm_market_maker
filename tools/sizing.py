"""Kalshi fee model and position sizing.

Fee model verified against Kalshi's published schedule on 2026-08-23:
per-contract fee is 0.07 * P * (1-P) dollars, capped at $0.035, and an
actual order's total fee rounds UP to the whole cent.

Two fee functions exist on purpose. `fee_pts` is the unrounded per-contract
rate in percentage points, used for edge math at screen time when the
contract count is not yet known. `order_fee_dollars` is what an order is
actually charged.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

FEE_RATE = 0.07
FEE_CAP_DOLLARS = 0.035
KELLY_FRACTION = 0.25
MAX_STAKE_FRACTION = 0.10


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def fee_pts(price: float) -> float:
    """Per-contract fee in percentage points for a contract at `price`."""
    p = _clamp(price, 0.0, 1.0)
    per_contract = min(FEE_RATE * p * (1.0 - p), FEE_CAP_DOLLARS)
    return per_contract * 100.0


def order_fee_dollars(price: float, contracts: int) -> float:
    """Total fee actually charged for an order, rounded up to the cent."""
    p = _clamp(price, 0.0, 1.0)
    per_contract = min(FEE_RATE * p * (1.0 - p), FEE_CAP_DOLLARS)
    # Use Decimal for exact ceiling rounding in cents. A float epsilon approach
    # (e.g., round(x, 8)) can under-round genuine fractional cents: for prices
    # like 0.1726731648642293, the per-contract fee has real fractional cents
    # that would be erased by thresholding. Decimal(str(x)) captures the float's
    # exact short representation, preserving fractional parts for correct ceiling.
    total = Decimal(str(per_contract)) * Decimal(contracts)
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def net_edge_pts(model_prob: float, entry_price: float) -> float:
    """Edge in percentage points after fees, at an executable entry price."""
    gross = (model_prob - entry_price) * 100.0
    return gross - fee_pts(entry_price)


def kelly_stake(
    model_prob: float,
    entry_price: float,
    fraction: float = KELLY_FRACTION,
    max_stake: float = MAX_STAKE_FRACTION,
) -> float:
    """Fractional-Kelly bankroll fraction for a binary contract.

    A contract costing p pays 1 on a win, so full Kelly is (q - p) / (1 - p).
    The fee is folded into an effective price.
    """
    p_eff = entry_price + min(
        FEE_RATE * entry_price * (1.0 - entry_price), FEE_CAP_DOLLARS
    )
    if p_eff >= 1.0:
        return 0.0
    full = (model_prob - p_eff) / (1.0 - p_eff)
    if full <= 0.0:
        return 0.0
    return min(full * fraction, max_stake)


def blend_q(
    model_prob: float,
    market_mid: float,
    shrink: float = 0.5,
    max_edge_pts: float = 10.0,
    prob_cap: float = 0.985,
) -> float:
    """Shrink a model probability toward the market and cap claimed edge.

    Ported from kalshi_trader. A model that disagrees wildly with a liquid
    market is usually wrong, so claimed edge is bounded in both directions.
    """
    blended = market_mid + (model_prob - market_mid) * (1.0 - shrink)
    max_edge = max_edge_pts / 100.0
    blended = _clamp(blended, market_mid - max_edge, market_mid + max_edge)
    return _clamp(blended, 1.0 - prob_cap, prob_cap)
