"""Compose every measured close-day into one within-day side-asymmetry series.

Reads this study's `data/close-<day>.json` files -- all produced by
`measure.py`, one method, one vintage -- and reports the paired
NO-minus-YES net edge per day with a day-clustered SE and a sign test.

Why paired: the day effect is a common shock to both sides, so it cancels
in the difference. `compute_score` measures each side against its own
price and therefore inherits the full day swing (+4.26/-7.29/+5.40 on the
first three days), which is wider than the effect being looked for.

Two rules this file enforces, both fixed before the 2026-09-01 numbers
were computed:

* **A close day enters the series at >= 90% settled.** The 2026-08-29 day
  entered the first pass at 24-of-70 and read +9.49; complete, it reads
  +4.10. A partial day is a biased draw -- markets that settle early are
  finished sports -- so it is reported and excluded, never averaged in.
* **Every day is re-measured together.** Days frozen at an older
  settlement state are not comparable to days measured today.

Run: python studies/2026-08-29-side-asymmetry-extension/compose.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DATA = Path(__file__).resolve().parent / "data"
MIN_SETTLED_FRACTION = 0.90


def fee_pts(price: float) -> float:
    return min(0.07 * price * (1.0 - price), 0.035) * 100.0


def load_days():
    """{close_day: (rows, settled_fraction)} over every measured day."""
    days = {}
    for path in sorted(DATA.glob("close-*.json")):
        d = json.loads(path.read_text())
        rows = [{"side": m["side"], "ask": m["ask"], "result": m["result"]}
                for m in d["markets"] if m.get("result") in ("yes", "no")]
        pop = d["n_population"] or 1
        days[d["close_day"]] = (rows, len(rows) / pop)
    return days


def edge(rs):
    if not rs:
        return None
    wr = sum(r["result"] == r["side"] for r in rs) / len(rs)
    ask = sum(r["ask"] for r in rs) / len(rs)
    fee = sum(fee_pts(r["ask"]) for r in rs) / len(rs)
    return {"n": len(rs), "net": round((wr - ask) * 100 - fee, 2)}


def _sign_p(k: int, n: int) -> float:
    from math import comb
    k = max(k, n - k)
    tail = sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main() -> None:
    days = load_days()
    included = {d: rs for d, (rs, frac) in days.items()
                if frac >= MIN_SETTLED_FRACTION}
    excluded = {d: frac for d, (_, frac) in days.items()
                if frac < MIN_SETTLED_FRACTION}

    print("Within-day side asymmetry on the shared insider_bias screen")
    print("population. Thesis (no_side_premium): NO - YES > 0.\n")
    print(f"{'close day':12} {'settled':>8} {'all':>16} {'YES':>16} "
          f"{'NO':>16} {'NO-YES':>9}")
    diffs = []
    for d in sorted(days):
        rs, frac = days[d]
        a, y, n = (edge(rs), edge([r for r in rs if r["side"] == "yes"]),
                   edge([r for r in rs if r["side"] == "no"]))
        diff = round(n["net"] - y["net"], 2) if (y and n) else None
        mark = "" if d in included else "  <- EXCLUDED, partial"
        if diff is not None and d in included:
            diffs.append((d, diff))

        def f(e):
            return f"n={e['n']:<3}{e['net']:+7.2f}" if e else "n=0"
        print(f"{d:12} {frac*100:7.0f}% {f(a):>16} {f(y):>16} {f(n):>16} "
              f"{diff if diff is not None else '-':>9}{mark}")

    if excluded:
        print(f"\nExcluded ({MIN_SETTLED_FRACTION:.0%} settled required): "
              + ", ".join(f"{d} at {frac:.0%}" for d, frac in sorted(excluded.items())))

    ys = [edge([r for r in included[d] if r["side"] == "yes"])
          for d in sorted(included)]
    ns = [edge([r for r in included[d] if r["side"] == "no"])
          for d in sorted(included)]
    ym = statistics.mean([e["net"] for e in ys if e])
    nm = statistics.mean([e["net"] for e in ns if e])
    print()
    print(f"day-equal-weighted mean, YES side = {ym:+.2f} pts  "
          f"(cell B claims -3.9)")
    print(f"day-equal-weighted mean, NO  side = {nm:+.2f} pts  "
          f"(cell A claims +2.0, narrower slice)")

    vals = [v for _, v in diffs]
    print(f"\nn_days = {len(vals)}   (no_side_premium's amended bar: >= 8)")
    print(f"mean NO-YES  = {statistics.mean(vals):+.2f} pts")
    if len(vals) > 1:
        se = statistics.stdev(vals) / len(vals) ** 0.5
        t = statistics.mean(vals) / se
        print(f"day-clustered SE = {se:.2f}   t = {t:+.2f} on {len(vals)-1} df")
        print(f"95% CI (normal)  = [{statistics.mean(vals)-1.96*se:+.2f}, "
              f"{statistics.mean(vals)+1.96*se:+.2f}]")
    pos = sum(v > 0 for v in vals)
    print(f"sign test: {pos}/{len(vals)} days positive "
          f"(two-sided p = {_sign_p(pos, len(vals)):.3f})")


if __name__ == "__main__":
    main()
