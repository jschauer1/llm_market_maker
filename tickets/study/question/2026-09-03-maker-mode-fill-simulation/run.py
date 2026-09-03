"""The contrast: rest-then-cross versus always-cross, on the census intermediate.

Reads `data/markets.jsonl` (built by `counts.py`, which cannot read a
settlement outcome) and computes the pre-registered primary statistic

    D = cost(CROSS) - cost(REST)          in points, per market

plus the pre-declared secondaries and the zero-improvement control. No
settlement outcome is read here either, and none is needed: both arms end
holding the same contract in the same market, so `won` cancels
algebraically out of D. That is what makes this tier A without an
argument, and it is why the design is far better powered than a P&L
comparison -- the settlement variance term is not reduced, it is absent.

    python tickets/study/question/2026-09-03-maker-mode-fill-simulation/run.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mm_sim", _HERE / "sim.py")
sim = importlib.util.module_from_spec(_spec)
sys.modules["mm_sim"] = sim
_spec.loader.exec_module(sim)

DATA = _HERE / "data" / "markets.jsonl"
IMPROVEMENT = 0.01

# Two-sided alpha 0.05, 80% power: z(0.975) + z(0.80).
MDE_Z = 1.959964 + 0.841621
MDE_CEILING_PTS = 1.0        # pre-registered: above this, NOT MEASURED


# ---------------------------------------------------------------- statistics

def day_clustered(rows: list[dict], value) -> dict:
    """Mean over settlement days, with the between-day standard error.

    One observation per settlement day, never per row: rows inside a day
    are not independent draws, and this repo has been bitten by that
    repeatedly (2026-08-27-settlement-day-clustering).
    """
    by_day: dict[str, list[float]] = {}
    for r in rows:
        by_day.setdefault(r["day"], []).append(value(r))
    if not by_day:
        return {"n": 0, "n_days": 0}
    day_means = [statistics.fmean(v) for v in by_day.values()]
    n_days = len(day_means)
    mean = statistics.fmean(day_means)
    if n_days < 2:
        return {"n": len(rows), "n_days": n_days, "mean": mean,
                "se": float("nan"), "t": float("nan"),
                "lo": float("nan"), "hi": float("nan"), "mde": float("nan")}
    sd = statistics.stdev(day_means)
    se = sd / math.sqrt(n_days)
    return {
        "n": len(rows),
        "n_days": n_days,
        "n_events": len({r["event"] for r in rows}),
        "mean": mean,
        "se": se,
        "t": mean / se if se else float("nan"),
        "lo": mean - 1.96 * se,
        "hi": mean + 1.96 * se,
        "mde": MDE_Z * se,
    }


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, order preserved."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


def p_from_t(t: float) -> float:
    """Two-sided normal p-value; day counts here are large enough."""
    if not math.isfinite(t):
        return 1.0
    return math.erfc(abs(t) / math.sqrt(2.0))


# ------------------------------------------------------------------ the arms

def yes_arms(r: dict) -> tuple[float, float]:
    """(D_net, D_gross) in points for the BUY-YES primary."""
    cross_p = r["ask_t"]
    if r["filled"]:
        rest_p = r["limit"]
    else:
        rest_p = r["ask_end"]
    net = (cross_p * 100 + sim.fee_pts(cross_p)) - (rest_p * 100 + sim.fee_pts(rest_p))
    gross = (cross_p - rest_p) * 100
    return net, gross


def no_arms(r: dict) -> tuple[float, float]:
    """(D_net, D_gross) for the BUY-NO mirror check.

    Buying NO passively means posting a YES ask one cent inside the
    existing one; the capture on a fill is the same `spread - 1c`, so any
    difference between this and the primary is drift on the unfilled arm
    rather than spread capture.
    """
    cross_p = 1.0 - r["bid_t"]
    if r["filled_no"]:
        rest_p = 1.0 - (r["ask_t"] - IMPROVEMENT)
    else:
        rest_p = 1.0 - r["bid_end"]
    net = (cross_p * 100 + sim.fee_pts(cross_p)) - (rest_p * 100 + sim.fee_pts(rest_p))
    gross = (cross_p - rest_p) * 100
    return net, gross


def zero_control(r: dict) -> float:
    """Post AT the crossing price. Must be exactly 0.00 for every market."""
    cross_p = r["ask_t"]
    return (cross_p * 100 + sim.fee_pts(cross_p)) - (cross_p * 100 + sim.fee_pts(cross_p))


# ----------------------------------------------------------------- reporting

def line(label: str, s: dict, width: int = 34) -> str:
    if s.get("n_days", 0) < 2:
        return f"  {label:<{width}} n={s.get('n', 0):<5} (too few days)"
    return (
        f"  {label:<{width}} n={s['n']:<5} days={s['n_days']:<4} "
        f"D={s['mean']:+6.2f}  t={s['t']:+5.2f}  "
        f"CI[{s['lo']:+6.2f},{s['hi']:+6.2f}]  MDE={s['mde']:4.2f}"
    )


def main() -> int:
    rows = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        print("no data", file=sys.stderr)
        return 1

    for r in rows:
        r["d_net"], r["d_gross"] = yes_arms(r)

    print("=" * 78)
    print("MAKER MODE -- rest at bid+1c, cross at T+24h if unfilled")
    print("=" * 78)
    print(f"markets                : {len(rows)}")
    print(f"settlement days        : {len({r['day'] for r in rows})}")
    print(f"event clusters         : {len({r['event'] for r in rows})}")
    print(f"series                 : {len({r['series'] for r in rows})}")
    n_fill = sum(1 for r in rows if r["filled"])
    print(f"FILL RATE              : {n_fill}/{len(rows)} = {n_fill/len(rows):.3f}")
    print()

    # ---- negative control 1: the accounting must be exactly zero
    ctrl = [zero_control(r) for r in rows]
    worst = max(abs(c) for c in ctrl)
    print(f"CONTROL zero-improvement arm: max |D| = {worst:.2e}  "
          f"{'PASS' if worst < 1e-9 else 'FAIL -- RUN IS VOID'}")
    print()

    # ---- primary
    print("-" * 78)
    print("PRIMARY (pre-registered): buy YES, D = cost(cross) - cost(rest), points")
    print("-" * 78)
    net = day_clustered(rows, lambda r: r["d_net"])
    gross = day_clustered(rows, lambda r: r["d_gross"])
    print(line("net of fees  [HEADLINE]", net))
    print(line("gross", gross))
    print()
    print(f"  MDE ceiling {MDE_CEILING_PTS:.1f} pt -> "
          f"{'MEASURED' if net['mde'] <= MDE_CEILING_PTS else 'NOT MEASURED'} "
          f"(design resolves {net['mde']:.2f} pt at 80% power)")
    print()

    # ---- decomposition: what the two branches contribute
    filled = [r for r in rows if r["filled"]]
    unfilled = [r for r in rows if not r["filled"]]
    print("-" * 78)
    print("DECOMPOSITION -- the whole question is capture-on-fills vs drift-on-misses")
    print("-" * 78)
    for label, subset in (("filled (capture)", filled), ("unfilled (drift)", unfilled)):
        if subset:
            s = day_clustered(subset, lambda r: r["d_net"])
            share = len(subset) / len(rows)
            print(line(f"{label}  [{share:.1%} of rows]", s))
    if unfilled:
        drift = statistics.fmean([(r["ask_end"] - r["ask_t"]) * 100 for r in unfilled])
        print(f"  mean ask move on unfilled markets  : {drift:+.2f} pts "
              f"(positive = it ran away from you)")
    if filled:
        cap = statistics.fmean([(r["ask_t"] - r["limit"]) * 100 for r in filled])
        print(f"  mean gross capture on a fill       : {cap:+.2f} pts")
    print()

    # ---- pre-declared secondaries, Holm corrected
    print("-" * 78)
    print("SECONDARY (pre-declared, Holm-corrected across the 7 cells below)")
    print("-" * 78)
    cells: list[tuple[str, dict]] = []
    for lo, hi in ((0.02, 0.20), (0.20, 0.50), (0.50, 0.80), (0.80, 0.981)):
        sub = [r for r in rows if lo <= r["ask_t"] < hi]
        if sub:
            cells.append((f"ask [{lo:.2f},{min(hi,0.98):.2f}]", day_clustered(sub, lambda r: r["d_net"])))
    for label, lo, hi in (("spread 2-3c", 0.02, 0.035), ("spread 4-6c", 0.035, 0.065),
                          ("spread >=7c", 0.065, 9.0)):
        sub = [r for r in rows if lo <= r["spread_t"] < hi]
        if sub:
            cells.append((label, day_clustered(sub, lambda r: r["d_net"])))
    praw = [p_from_t(s.get("t", 0.0)) for _, s in cells]
    padj = holm(praw)
    for (label, s), pr, pa in zip(cells, praw, padj):
        print(line(label, s) + f"  p={pr:.3f} holm={pa:.3f}")
    print()

    # ---- fill-rate composition
    print("  fill rate by spread:")
    for label, lo, hi in (("2-3c", 0.02, 0.035), ("4-6c", 0.035, 0.065), (">=7c", 0.065, 9.0)):
        sub = [r for r in rows if lo <= r["spread_t"] < hi]
        if sub:
            f = sum(1 for r in sub if r["filled"]) / len(sub)
            print(f"    {label:<6} n={len(sub):<5} fill={f:.3f}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
