"""Cluster-robust intervals for repeated observations sharing one outcome."""
from __future__ import annotations

from collections import defaultdict
import math
from statistics import mean


def cluster_interval(rows: list[dict], value: str, cluster: str) -> dict:
    """Row-weighted mean with cluster-sandwich SE and conservative t critical.

    Duplicating every sibling does not increase precision. For unequal groups,
    residual sums (not unweighted group means) preserve the point estimand.
    """
    if not rows:
        return {"clusters": 0, "mean": None, "se": None, "interval": None}
    avg = mean(r[value] for r in rows)
    sums = defaultdict(float)
    for r in rows:
        sums[r[cluster]] += r[value] - avg
    g = len(sums)
    if g < 2:
        return {"clusters": g, "mean": avg, "se": None, "interval": None}
    se = math.sqrt(g / (g - 1) * sum(x * x for x in sums.values())) / len(rows)
    # Two-sided .95 Student t quantiles, rounded upward. Use the preceding
    # tabulated df rather than interpolating to a spuriously tighter bound.
    quantiles = {1: 12.707, 2: 4.303, 3: 3.183, 4: 2.777, 5: 2.571,
                 6: 2.447, 7: 2.365, 8: 2.307, 9: 2.263, 10: 2.229,
                 12: 2.179, 15: 2.132, 20: 2.086, 30: 2.043,
                 60: 2.001, 120: 1.980}
    critical = quantiles[max(df for df in quantiles if df <= g - 1)]
    return {"clusters": g, "mean": avg, "se": se,
            "interval": [avg - critical * se, avg + critical * se]}
