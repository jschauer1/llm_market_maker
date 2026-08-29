"""Compose all measured close-days into one within-day side-asymmetry series.

Reads the 2026-08-27 study's data files (close days 08-25/26/27) and this
study's (08-28, 08-29) -- same method, so they compose -- and reports the
paired NO-minus-YES net edge per day with a day-clustered SE and a sign
test.

Why paired: the day effect is a common shock to both sides, so it cancels
in the difference. `compute_score` measures each side against its own
price and therefore inherits the full day swing (+4.26/-7.29/+5.40 on the
first three days), which is wider than the effect being looked for.

Run: python studies/2026-08-29-side-asymmetry-extension/compose.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "studies/2026-08-27-settlement-day-clustering/data"
NEW = Path(__file__).resolve().parent / "data"


def fee_pts(price: float) -> float:
    return min(0.07 * price * (1.0 - price), 0.035) * 100.0


def load_old(path: Path, close_day: str | None = None):
    rows = json.loads(path.read_text())
    out = []
    for r in rows:
        if r.get("result") not in ("yes", "no"):
            continue
        if close_day and (r.get("close") or "")[:10] != close_day:
            continue
        out.append({"side": r["side"], "ask": r["price"],
                    "result": r["result"]})
    return out


def load_new(path: Path):
    d = json.loads(path.read_text())
    return [{"side": m["side"], "ask": m["ask"], "result": m["result"]}
            for m in d["markets"] if m.get("result") in ("yes", "no")]


def edge(rs):
    if not rs:
        return None
    wr = sum(r["result"] == r["side"] for r in rs) / len(rs)
    ask = sum(r["ask"] for r in rs) / len(rs)
    fee = sum(fee_pts(r["ask"]) for r in rs) / len(rs)
    return {"n": len(rs), "net": round((wr - ask) * 100 - fee, 2)}


def main() -> None:
    days = {}
    for d in ("2026-08-25", "2026-08-26"):
        days[d] = load_old(OLD / "close-2026-08-25-26.json", d)
    days["2026-08-27"] = load_old(OLD / "close-2026-08-27.json")
    days["2026-08-28"] = load_new(NEW / "close-2026-08-28.json")
    days["2026-08-29"] = load_new(NEW / "close-2026-08-29.json")

    print("Within-day side asymmetry on the shared insider_bias screen")
    print("population. Thesis (no_side_premium): NO - YES > 0.\n")
    print(f"{'close day':12} {'all':>16} {'YES':>16} {'NO':>16} {'NO-YES':>9}")
    diffs = []
    for d in sorted(days):
        rs = days[d]
        a, y, n = (edge(rs), edge([r for r in rs if r["side"] == "yes"]),
                   edge([r for r in rs if r["side"] == "no"]))
        diff = round(n["net"] - y["net"], 2) if (y and n) else None
        if diff is not None:
            diffs.append((d, diff))
        def f(e):
            return f"n={e['n']:<3}{e['net']:+7.2f}" if e else "n=0"
        print(f"{d:12} {f(a):>16} {f(y):>16} {f(n):>16} "
              f"{diff if diff is not None else '-':>9}")

    # Per-side day means, equally weighted. These are what the theory's
    # two cells actually claim (-3.9 for YES favorites, +2.0 for NO), so
    # they are the direct check on its point estimates.
    ys = [edge([r for r in days[d] if r["side"] == "yes"]) for d in sorted(days)]
    ns = [edge([r for r in days[d] if r["side"] == "no"]) for d in sorted(days)]
    ym = statistics.mean([e["net"] for e in ys if e])
    nm = statistics.mean([e["net"] for e in ns if e])
    print()
    print(f"day-equal-weighted mean, YES side = {ym:+.2f} pts  (cell B claims -3.9)")
    print(f"day-equal-weighted mean, NO  side = {nm:+.2f} pts  (cell A claims +2.0, narrower slice)")

    vals = [v for _, v in diffs]
    print(f"\nn_days = {len(vals)}   (no_side_premium's amended bar: >= 8)")
    print(f"mean NO-YES  = {statistics.mean(vals):+.2f} pts")
    if len(vals) > 1:
        se = statistics.stdev(vals) / len(vals) ** 0.5
        print(f"day-clustered SE = {se:.2f}   t = "
              f"{statistics.mean(vals)/se:+.2f} on {len(vals)-1} df")
    pos = sum(v > 0 for v in vals)
    print(f"sign test: {pos}/{len(vals)} days positive "
          f"(two-sided p = {_sign_p(pos, len(vals)):.3f})")


def _sign_p(k: int, n: int) -> float:
    from math import comb
    k = max(k, n - k)
    tail = sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n
    return min(1.0, 2 * tail)


if __name__ == "__main__":
    main()
