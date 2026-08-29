"""Read a collection run's cells: rates, mean ask, and the day-clustered SE.

`collect.py rates` prints wins/n/days. This adds the three things a cell
cannot honestly be read without:

- the **mean ask actually paid**, because a raw edge measured against a
  price-bin midpoint is not an edge against anything real;
- the theory's own **Wilson-bounded** edge at that ask, which is what
  `price()` would claim;
- the **day-clustered SE**, which THEORY.md mandates reporting and which
  is what decides whether a cell means anything at all. Every headline in
  this repo that skipped it has been wrong (see NOTES.md 2026-08-29).

Usage::

    python -m theories.calibration_harvest.read_cells [run_id]

Read-only; touches no network.
"""

from __future__ import annotations

import json
import statistics
import sys

from tools import db
from theories.calibration_harvest import cells

DEFAULT_RUN = "backtest-2026-08-27-calharvest-weather"

SQL = """
    SELECT a.extra_json, a.entry_price, o.outcome, s.result,
           SUBSTR(COALESCE(s.resolved_at, ''), 1, 10) AS day
    FROM opportunity_attempts a
    JOIN opportunities o ON o.id = a.opportunity_id
    JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
    WHERE o.theory_id = 'calibration_harvest' AND a.run_id = ?
"""


def gather(conn, run_id: str) -> dict[str, dict]:
    """Per-cell tallies, including a per-day breakdown for clustering."""
    acc: dict[str, dict] = {}
    for row in conn.execute(SQL, (run_id,)):
        key = json.loads(row["extra_json"] or "{}").get("cell")
        if not key:
            continue
        cell = acc.setdefault(key, {"wins": 0, "n": 0, "days": set(),
                                    "asks": [], "by_day": {}})
        cell["n"] += 1
        won = row["outcome"] == row["result"]
        cell["wins"] += 1 if won else 0
        cell["asks"].append(row["entry_price"])
        if row["day"]:
            cell["days"].add(row["day"])
            d = cell["by_day"].setdefault(row["day"], [0, 0, 0.0])
            d[0] += 1 if won else 0
            d[1] += 1
            d[2] += row["entry_price"]
    return acc


def main() -> None:
    run_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RUN
    conn = db.connect()
    acc = gather(conn, run_id)
    if not acc:
        print(f"no cells recorded for run {run_id!r}")
        return

    print(f"run: {run_id}\n")
    print(f"{'cell':38s} {'n':>5s} {'days':>5s} {'meanask':>8s} "
          f"{'realized':>9s} {'raw edge':>9s} {'wilson':>7s} "
          f"{'net':>7s} {'basis':>9s}")
    for key in sorted(acc, key=lambda k: -acc[k]["n"]):
        c = acc[key]
        n, wins = c["n"], c["wins"]
        mean_ask = sum(c["asks"]) / n
        realized = wins / n
        edge = cells.cell_edge(wins, n, len(c["days"]), mean_ask)
        print(f"{key:38s} {n:5d} {len(c['days']):5d} {mean_ask:8.4f} "
              f"{realized:9.4f} {(realized - mean_ask) * 100:+8.2f}p "
              f"{edge.model_prob:7.4f} {edge.pts_net:+7.2f} "
              f"{edge.basis:>9s}")

    print("\nday-clustered raw edge (THEORY.md mandates reporting this):")
    for key in sorted(acc, key=lambda k: -acc[k]["n"]):
        c = acc[key]
        if len(c["by_day"]) < 3:
            continue
        per_day = [(w / dn - asks / dn) * 100.0
                   for w, dn, asks in c["by_day"].values()]
        mean = statistics.mean(per_day)
        se = statistics.stdev(per_day) / (len(per_day) ** 0.5)
        verdict = "SIGNIFICANT" if abs(mean) > 2 * se else "inside noise"
        print(f"  {key:38s} {mean:+7.2f}pts +/- {se:5.2f} "
              f"(n_days={len(per_day)})   {verdict}")


if __name__ == "__main__":
    main()
