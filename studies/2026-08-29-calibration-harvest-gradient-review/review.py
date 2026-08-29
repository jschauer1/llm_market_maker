"""Reproduce the three checks in STUDY.md against the politics run.

Read-only: imports `calibration_harvest.gradient`'s loaders and recomputes.
Run: python studies/2026-08-29-calibration-harvest-gradient-review/review.py
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import db                                             # noqa: E402
from theories.calibration_harvest.gradient import (               # noqa: E402
    DEFAULT_RUN, HORIZONS, _mean_se, edges_by_day, load)


def paired(rows, a_bins, b_bins):
    """mean(edge over a_bins - edge over b_bins) on shared settlement days."""
    A = edges_by_day([r for r in rows if r[0] in a_bins])
    B = edges_by_day([r for r in rows if r[0] in b_bins])
    both = sorted(set(A) & set(B))
    if len(both) < 3:
        return None
    d = [A[x] - B[x] for x in both]
    m, se = _mean_se(d)
    return m, se, m / se, len(both), sum(1 for x in d if x > 0)


def main() -> None:
    rows = load(db.connect(), DEFAULT_RUN)

    print("1. adjacent steps, paired within day (prediction: all positive)")
    for lo, hi in zip(HORIZONS, HORIZONS[1:]):
        m, se, t, nd, _ = paired(rows, (hi,), (lo,))
        print(f"   {'OK ' if t > 0 else 'INV'} {hi:7} - {lo:7}: {m:+6.2f} "
              f"SE {se:5.2f}  t {t:+5.2f}  (n_days {nd})")
    print("   -> the effect is ONE step at the 1-week boundary, not a slope")

    print("\n2. every possible split point (reported one is after 2d-1w)")
    for i in range(1, len(HORIZONS)):
        m, se, t, nd, pos = paired(rows, tuple(HORIZONS[i:]),
                                   tuple(HORIZONS[:i]))
        mark = "  <-- REPORTED" if i == 2 else ""
        print(f"   split after {HORIZONS[i-1]:7}: {m:+6.2f} SE {se:5.2f} "
              f"t {t:+5.2f}  days {nd}  pos {pos}{mark}")
    print("   -> reported t is the MAX of three; one split shows nothing")

    print("\n3. split-free trend: day-level slope of edge on horizon rank")
    rank = {h: i for i, h in enumerate(HORIZONS)}
    per_day: dict = {}
    for h, day, won, ask in rows:
        a = per_day.setdefault(day, {}).setdefault(h, [0.0, 0.0, 0])
        a[0] += won
        a[1] += ask
        a[2] += 1
    slopes = []
    for bins in per_day.values():
        if len(bins) < 3:
            continue
        xs = [rank[h] for h in bins]
        ys = [(w / n - a / n) * 100.0 for h, (w, a, n) in bins.items()]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        den = sum((x - mx) ** 2 for x in xs)
        if den:
            slopes.append(
                sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den)
    m, se = _mean_se(slopes)
    print(f"   {m:+.2f} pts/bin  SE {se:.2f}  t {m/se:+.2f}  "
          f"days {len(slopes)}  positive {sum(s > 0 for s in slopes)}"
          f"/{len(slopes)}")
    print("   -> this is what should be quoted as the headline")


if __name__ == "__main__":
    main()
