"""Confidence buckets — measured probabilities instead of guessed ones.

LLMs are poorly calibrated probability estimators. They cluster on round
numbers, drift with phrasing, and anchor hard on any number already in
context — so asking a model for `q` while showing it the market price mostly
measures the anchor.

This module is the alternative. A judgment step returns an ordinal bucket
("strong", "moderate", "weak"), and the bucket's own realized win rate
supplies the probability. "When this theory says strong, it wins 78% of the
time" is a fact about the past, not an introspection, and it is exactly what
the edge calculation needs.

Until a bucket has MIN_BUCKET_N settled results, the theory's declared prior
stands in and the result is flagged `prior` so nobody mistakes a placeholder
for a measurement.
"""

from __future__ import annotations

from tools.sizing import fee_pts

MIN_BUCKET_N = 10


def edge_for(
    bucket: str,
    entry_price: float,
    rates: dict,
    priors: dict,
    min_n: int = MIN_BUCKET_N,
) -> tuple[float, str]:
    """Net edge in points for a bucketed judgment, and where it came from.

    Returns (edge_pts_net, edge_basis) where edge_basis is "measured" when the
    bucket has enough settled history to speak for itself, otherwise "prior".
    """
    measured = rates.get(bucket)
    if measured and measured.get("n", 0) >= min_n:
        probability = measured["win_rate"]
        gross = (probability - entry_price) * 100.0
        return gross - fee_pts(entry_price), "measured"

    return float(priors.get(bucket, 0.0)), "prior"
