"""calibration_harvest -- the FORWARD, out-of-sample per-cell measurement.

`gradient.py` and `read_cells.py` read the *backtest* populations that the
theory's cell grid was fitted on. This module reads the other corpus, the
one nobody had looked at: the live rows the theory records so its cells
accrue settlements ("Recorded so the cell accrues settlements; not a
recommendation"), joined to the settlements they have since earned.

Why that corpus is the one the kill criterion asks for. THEORY.md fixes the
bar as *"No cell clears fees out-of-sample at n >= 30 AND n_days >= 8"*.
Backtest rows cannot answer it -- the grid was drawn on them. A live row was
written before its market resolved and scored afterwards, so every row here
is out of sample by construction, with no replay approximation in the way.

Read alongside `score.calibration_edge`, which pools this same population
into ONE number and therefore cannot bear on this theory at all: the
hypothesis is per-cell and SIGNED (politics compressed toward 50%, weather
the reverse inside 12h), so pooling opposite-signed cells cancels exactly
the effect the theory claims. The aggregate is a fact about the board, not
about the decision procedure.

Day-clustered throughout, for the reason cells.py already states: Kalshi
settles in day-clumps, so 400 rows over 3 days is 3 draws, not 400.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict

from tools import db
from tools.sizing import fee_pts
from theories.calibration_harvest.cells import (
    MIN_CELL_N, MIN_CELL_DAYS, wilson_lower,
)

#: The cell is written into the rationale by the live screen; there is no
#: extra_json on these rows. Parsing it back is lossless -- cell_key()
#: composed the string -- and avoids re-deriving a horizon from a
#: days_to_close nobody stored.
_CELL_RE = re.compile(r"^cell ([a-z_]+\|[^|]+\|[0-9.\-]+):")

#: Runs excluded from the forward corpus, by id, with the reason.
#:
#: `live` is a defective run made 2026-08-30: the theory was instantiated
#: as `CalibrationHarvestTheory()` with neither `categories` nor
#: `cell_rates`, against its RUNBOOK, so every one of its 9,777 rows
#: landed in a `other|...` cell (the domain axis silently collapsed) and
#: was priced at edge 0.0 even where a measured cell existed. Its rows
#: are real sightings of real markets, so they are quarantined rather
#: than deleted -- but a cell measurement that pools them is measuring
#: a mislabelled population. `live-2026-08-30-calharvest` is the same
#: board re-run correctly and is the row set to use.
EXCLUDED_RUNS: dict[str, str] = {
    "live": "no categories/cell_rates passed; domain axis collapsed to "
            "'other' and every edge forced to 0.0 (2026-08-30)",
}

#: Reads ATTEMPTS, never the position rollup. A position's `run_id` is
#: frozen at its FIRST sighting, so a market screened yesterday and
#: re-screened today still reports yesterday's run -- which makes any
#: per-run cell measurement keyed on `opportunities.run_id` silently
#: wrong. `collect.cell_rates` documents this same trap for the
#: collection runs (attempt-fidelity, spec section 9); this is a fifth
#: consumer of it. The attempt carries its own entry_price, rationale
#: and edge, which is exactly the per-decision state a cell needs.
ROWS_SQL = """
SELECT a.run_id, a.decision_date, a.entry_price, a.rationale,
       a.edge_pts_net, a.edge_basis,
       o.kalshi_ticker, o.outcome,
       s.result, s.resolved_at
FROM opportunity_attempts a
JOIN opportunities o ON o.id = a.opportunity_id
JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
WHERE o.theory_id = 'calibration_harvest'
  AND o.theory_version = ?
  AND o.run_mode = 'live'
"""


def load(conn, version: int = 2, *, include_excluded: bool = False,
         ) -> list[dict]:
    out = []
    for r in conn.execute(ROWS_SQL, (version,)):
        if not include_excluded and r["run_id"] in EXCLUDED_RUNS:
            continue
        m = _CELL_RE.match(r["rationale"] or "")
        if not m or r["result"] not in ("yes", "no"):
            continue
        out.append({
            "cell": m.group(1),
            "ask": float(r["entry_price"]),
            "won": 1 if r["outcome"] == r["result"] else 0,
            "day": (r["resolved_at"] or "")[:10],
            "basis": r["edge_basis"],
            "run_id": r["run_id"],
            "ticker": r["kalshi_ticker"],
        })
    return out


def _day_clustered(rows: list[dict]) -> tuple[float | None, float | None, int]:
    """(mean, SE, n_days) of the per-day gross edge in points."""
    by_day: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(100.0 * (r["won"] - r["ask"]))
    day_means = [statistics.fmean(v) for v in by_day.values()]
    n_days = len(day_means)
    if n_days == 0:
        return None, None, 0
    mean = statistics.fmean(day_means)
    if n_days < 2:
        return mean, None, n_days
    se = statistics.stdev(day_means) / math.sqrt(n_days)
    return mean, se, n_days


def cells(conn, version: int = 2) -> list[dict]:
    """Per-cell forward measurement, richest cells first."""
    rows = load(conn, version)
    by_cell: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cell[r["cell"]].append(r)

    out = []
    for cell, rs in by_cell.items():
        n = len(rs)
        n_markets = len({r["ticker"] for r in rs})
        wins = sum(r["won"] for r in rs)
        ask = statistics.fmean(r["ask"] for r in rs)
        fee = statistics.fmean(fee_pts(r["ask"]) for r in rs)
        mean, se, n_days = _day_clustered(rs)
        wl = wilson_lower(wins, n)
        out.append({
            "cell": cell, "n": n, "n_markets": n_markets,
            "n_days": n_days, "wins": wins,
            "mean_ask": ask, "realized": wins / n,
            "gross_pts": 100.0 * (wins / n - ask),
            "fee_pts": fee,
            "net_pts": 100.0 * (wins / n - ask) - fee,
            "day_mean": mean, "day_se": se,
            "t": (mean / se) if (mean is not None and se) else None,
            # The theory's own committing rule: a cell may only be bet at
            # the pessimistic end of its interval, never its raw rate.
            "wilson_lower": wl,
            "net_at_wilson": 100.0 * (wl - ask) - fee,
            "measurable": n >= MIN_CELL_N and n_days >= MIN_CELL_DAYS,
        })
    return sorted(out, key=lambda c: -c["n"])


def kill_criterion(conn, version: int = 2) -> dict:
    """THEORY.md's bar: does ANY cell clear fees out-of-sample at both floors?

    Reported three ways on purpose. `clears_raw` is the loosest reading
    (raw rate, net of fees) and `clears_wilson` the theory's own committing
    rule; `clears_significant` additionally demands the day-clustered t
    stand at 2. A bar that is met on one reading and missed on another is
    not a verdict, and saying which reading was used is the difference
    between a falsification and a claim.
    """
    cs = cells(conn, version)
    elig = [c for c in cs if c["measurable"]]
    return {
        "cells_total": len(cs),
        "cells_measurable": len(elig),
        "clears_raw": [c["cell"] for c in elig if c["net_pts"] > 0],
        "clears_wilson": [c["cell"] for c in elig if c["net_at_wilson"] > 0],
        "clears_significant": [
            c["cell"] for c in elig
            if c["net_pts"] > 0 and (c["t"] or 0) >= 2.0
        ],
        "cells": cs,
    }


def _fmt(v, spec=".2f"):
    return "     -" if v is None else format(v, spec)


def main() -> None:
    conn = db.connect()
    res = kill_criterion(conn)
    print(f"forward per-cell measurement -- calibration_harvest v2 "
          f"(live rows, out of sample)\n")
    hdr = (f"{'cell':38} {'n':>5} {'days':>5} {'ask':>6} {'real':>6} "
           f"{'gross':>7} {'net':>7} {'daymean':>8} {'t':>6} {'netWil':>8}")
    print(hdr); print("-" * len(hdr))
    for c in res["cells"]:
        flag = "*" if c["measurable"] else " "
        print(f"{flag}{c['cell']:37} {c['n']:5d} {c['n_days']:5d} "
              f"{c['mean_ask']:6.3f} {c['realized']:6.3f} "
              f"{c['gross_pts']:7.2f} {c['net_pts']:7.2f} "
              f"{_fmt(c['day_mean'], '8.2f')} {_fmt(c['t'], '6.2f')} "
              f"{c['net_at_wilson']:8.2f}")
    print(f"\n* = clears both floors (n >= {MIN_CELL_N}, "
          f"n_days >= {MIN_CELL_DAYS})")
    print(f"\ncells total      : {res['cells_total']}")
    print(f"cells measurable : {res['cells_measurable']}")
    print(f"clears fees (raw rate)      : {res['clears_raw'] or 'NONE'}")
    print(f"clears fees (Wilson bound)  : {res['clears_wilson'] or 'NONE'}")
    print(f"clears fees + t >= 2        : {res['clears_significant'] or 'NONE'}")


if __name__ == "__main__":
    main()
