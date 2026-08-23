"""Credibility-weighted ranking (spec section 8).

A theory's claimed edge is shrunk toward what it has actually demonstrated.
Below PROBATION_N settled bets a fixed floor applies so untested ideas stay
visible without dominating; at or above it the floor is withdrawn, so a
theory that has been measured and found wanting sinks to zero rather than
resting on newcomer protection.

All edge values are in percentage points, including calibration_edge.
"""

from __future__ import annotations

PROBATION_N = 10
PROBATION_CREDIBILITY = 0.25
SHRINK_DENOM = 20
REALIZATION_CLAMP = 1.5


def realization(
    calibration_edge: float | None,
    mean_claimed_edge: float | None,
) -> float:
    """How much of its claimed edge a theory actually delivered.

    Returns 1.0 (neutral) when there is nothing to measure against.
    """
    if calibration_edge is None:
        return 1.0
    if mean_claimed_edge is None or mean_claimed_edge <= 0.0:
        return 1.0
    ratio = calibration_edge / mean_claimed_edge
    return max(0.0, min(ratio, REALIZATION_CLAMP))


def credibility(
    n: int,
    calibration_edge: float | None = None,
    mean_claimed_edge: float | None = None,
) -> float:
    """Weight in [0, 1.5] to apply to a theory's claimed edge."""
    if n < PROBATION_N:
        return PROBATION_CREDIBILITY
    sample_weight = n / (n + SHRINK_DENOM)
    return sample_weight * realization(calibration_edge, mean_claimed_edge)


def ranked_edge(
    edge_pts_net: float,
    n: int,
    calibration_edge: float | None = None,
    mean_claimed_edge: float | None = None,
) -> float:
    """The number find-edge sorts on."""
    return edge_pts_net * credibility(n, calibration_edge, mean_claimed_edge)
