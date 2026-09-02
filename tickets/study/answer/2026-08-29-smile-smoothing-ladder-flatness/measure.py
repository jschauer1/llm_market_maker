"""Measure how far Kalshi strike ladders sit from their own isotonic fit.

This is the measurement that killed the `smile-smoothing` idea. It sweeps
the liquidity floor, because the whole question is whether off-curve
strikes exist *where you could actually trade them*.

Run: python tickets/study/answer/2026-08-29-smile-smoothing-ladder-flatness/measure.py
"""

from __future__ import annotations

import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))

import fit                                        # noqa: E402
from tools import board as board_tool, db         # noqa: E402
from tools.sizing import fee_pts                  # noqa: E402

#: (min per-rung volume, max per-rung spread). The first row is the
#: theory's proposed floor; the rest open it up until candidates appear,
#: which is the point of the sweep.
FLOORS = [(200, 0.10), (50, 0.15), (10, 0.25), (0, 0.40), (0, 1.00)]


def best_per_ladder(board, now):
    """(net edge, side, rung, fitted, entry) for each ladder's best rung."""
    out = []
    devs = []
    for ladder in fit.build_ladders(board, now=now):
        if fit.has_hard_violation(ladder):
            continue
        fitted = fit.fit_ladder(ladder)
        best = None
        for rung, fv in zip(ladder.rungs, fitted):
            d = rung.mid - fv
            devs.append(abs(d))
            if d < 0:
                side, entry, model = "yes", rung.yes_ask, fv
            elif d > 0:
                side, entry, model = "no", rung.no_ask, 1.0 - fv
            else:
                continue
            net = (model - entry) * 100.0 - fee_pts(entry)
            if best is None or net > best[0]:
                best = (net, side, rung, fv, entry)
        if best is not None:
            out.append(best)
    return out, devs


def main() -> None:
    conn = db.connect()
    board = board_tool.get_board(conn)
    now = datetime.now(timezone.utc)

    print(f"{'min_vol':>8} {'max_spr':>8} {'ladders':>8} {'rungs':>7} "
          f"{'on-fit':>8} {'max dev':>8} {'best net':>9} {'>=3pts':>7}")
    for min_vol, max_spread in FLOORS:
        fit.MIN_VOLUME, fit.MAX_SPREAD = float(min_vol), max_spread
        n_ladders = len(fit.build_ladders(board, now=now))
        best, devs = best_per_ladder(board, now)
        nets = [b[0] for b in best]
        on_fit = 100.0 * sum(d == 0 for d in devs) / len(devs) if devs else 0.0
        print(f"{min_vol:>8} {max_spread:>8.2f} {n_ladders:>8} {len(devs):>7} "
              f"{on_fit:>7.1f}% {max(devs) if devs else 0:>8.4f} "
              f"{max(nets) if nets else float('nan'):>9.2f} "
              f"{sum(n >= 3 for n in nets):>7}")

    # What the no-floor candidates actually are.
    fit.MIN_VOLUME, fit.MAX_SPREAD = 0.0, 1.0
    best, _ = best_per_ladder(board, now)
    hits = sorted([b for b in best if b[0] >= 3], key=lambda b: -b[0])
    print(f"\n{len(hits)} candidates clear 3pts with NO liquidity floor.")
    if hits:
        sp = [h[2].market.spread for h in hits]
        vol = [h[2].market.volume or 0 for h in hits]
        print(f"  spreads: median {statistics.median(sp):.2f} "
              f"min {min(sp):.2f} max {max(sp):.2f}")
        print(f"  volumes: median {statistics.median(vol):.0f} "
              f"min {min(vol):.0f} max {max(vol):.0f}")
        print(f"  spread <= 0.10 : {sum(s <= 0.10 for s in sp)}")
        print(f"  volume >= 200  : {sum(v >= 200 for v in vol)}")
        print(f"  BOTH           : "
              f"{sum(s <= 0.10 and v >= 200 for s, v in zip(sp, vol))}")
        print("\n  top 8:")
        for net, side, rung, fv, entry in hits[:8]:
            print(f"    {net:+6.2f} {side:3} {rung.market.ticker:42} "
                  f"ask {entry:.2f} spread {rung.market.spread:.2f} "
                  f"vol {rung.market.volume or 0:.0f}")


if __name__ == "__main__":
    main()
