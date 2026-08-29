"""The horizon-gradient test: the theory's central claim, as ONE contrast.

The spec predicts favorites underpriced with the effect **growing with
horizon** (Le 2026: political calibration slopes 1.48-1.83 from 12h out to
a month). Testing that cell by cell is sixteen chances to find a story --
the failure that killed `mention_family` -- so the bar pre-registered on
2026-08-29 (NOTES.md, before the politics data landed) made the *gradient*
the test, as a single contrast.

Two estimators, because they answer slightly different questions:

- **unpaired**: long-horizon day edges vs short-horizon day edges, two
  independent samples. Simple, but the two groups share settlement days,
  and a day-level common shock inflates its SE.
- **paired within day** (`long_edge - short_edge` on the same settlement
  day): cancels that shock. This is the estimator `no_side_premium`
  adopted on 2026-08-29 for the same reason, and here 45 of 46
  long-horizon days also carry short-horizon data, so almost nothing is
  discarded to get it.

Usage::

    python -m theories.calibration_harvest.gradient [run_id]

Read-only; touches no network.
"""

from __future__ import annotations

import json
import math
import statistics
import sys

from tools import db

DEFAULT_RUN = "backtest-2026-08-29-calharvest-politics"
HORIZONS = ["<=2d", "2d-1w", "1w-1mo", "1mo+"]
LONG = ("1w-1mo", "1mo+")

SQL = """
    SELECT a.extra_json, a.entry_price, o.outcome, s.result,
           SUBSTR(COALESCE(s.resolved_at, ''), 1, 10) AS day
    FROM opportunity_attempts a
    JOIN opportunities o ON o.id = a.opportunity_id
    JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
    WHERE o.theory_id = 'calibration_harvest' AND a.run_id = ?
"""


def load(conn, run_id: str) -> list[tuple]:
    out = []
    for r in conn.execute(SQL, (run_id,)):
        extra = json.loads(r["extra_json"] or "{}")
        if not extra.get("cell") or not r["day"]:
            continue
        out.append((extra["horizon_bin"], r["day"],
                    1.0 if r["outcome"] == r["result"] else 0.0,
                    r["entry_price"]))
    return out


def edges_by_day(rows) -> dict[str, float]:
    """One edge per settlement day: mean(won) - mean(ask), in points."""
    acc: dict[str, list] = {}
    for _h, day, won, ask in rows:
        a = acc.setdefault(day, [0.0, 0.0, 0])
        a[0] += won
        a[1] += ask
        a[2] += 1
    return {d: (w / n - a / n) * 100.0 for d, (w, a, n) in acc.items()}


def _mean_se(values) -> tuple[float, float]:
    return (statistics.mean(values),
            statistics.stdev(values) / len(values) ** 0.5)


def main() -> None:
    run_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RUN
    rows = load(db.connect(), run_id)
    if not rows:
        print(f"no settled, cell-tagged rows for run {run_id!r}")
        return
    print(f"run: {run_id}\nobservations with a settlement day: {len(rows)}\n")

    print("per-horizon, day-clustered (price bands pooled):")
    print(f"{'horizon':10s} {'rows':>7s} {'days':>6s} {'edge':>8s} "
          f"{'SE':>6s} {'t':>6s}")
    per_horizon = {}
    for h in HORIZONS:
        sel = [r for r in rows if r[0] == h]
        if not sel:
            continue
        de = list(edges_by_day(sel).values())
        mean, se = _mean_se(de)
        per_horizon[h] = mean
        print(f"{h:10s} {len(sel):7d} {len(de):6d} {mean:+8.2f} {se:6.2f} "
              f"{mean / se:+6.2f}")

    long_days = edges_by_day([r for r in rows if r[0] in LONG])
    short_days = edges_by_day([r for r in rows if r[0] not in LONG])

    mL, seL = _mean_se(list(long_days.values()))
    mS, seS = _mean_se(list(short_days.values()))
    diff = mL - mS
    sed = (seL ** 2 + seS ** 2) ** 0.5
    print("\nunpaired contrast (long vs short horizon):")
    print(f"  long  {mL:+7.2f} +/- {seL:5.2f} ({len(long_days)} days)")
    print(f"  short {mS:+7.2f} +/- {seS:5.2f} ({len(short_days)} days)")
    print(f"  diff  {diff:+7.2f} +/- {sed:5.2f}   t = {diff / sed:+.2f}")

    both = sorted(set(long_days) & set(short_days))
    if len(both) >= 3:
        paired = [long_days[d] - short_days[d] for d in both]
        mean, se = _mean_se(paired)
        wins = sum(1 for x in paired if x > 0)
        n = len(paired)
        p = sum(math.comb(n, i) for i in range(wins, n + 1)) / 2 ** n
        print("\npaired within-day contrast (cancels the day shock):")
        print(f"  mean {mean:+.2f}pts  SE {se:.2f}  t {mean / se:+.2f}  "
              f"days={n}")
        print(f"  positive days {wins}/{n}; one-sided sign test p = {p:.4f}")
        print(f"  -> {'CONFIRMED' if mean / se > 2 else 'not confirmed'} "
              "at 2 SE")

    ordered = [per_horizon[h] for h in HORIZONS if h in per_horizon]
    print("\nmonotonicity: " + " -> ".join(f"{v:+.2f}" for v in ordered))
    print(f"  strictly increasing: "
          f"{all(b > a for a, b in zip(ordered, ordered[1:]))}")


if __name__ == "__main__":
    main()
