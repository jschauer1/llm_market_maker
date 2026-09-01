"""Is `MIN_LEG_VOLUME = 100` throwing away fillable violations?

v3 set that threshold from THIS study's first pass, which saw six
violations. A threshold fit on n=6 and never revalidated now removes
every raw violation the live scan finds (2 on 2026-08-31, 3 on
2026-09-01, all removed as "untraded or near-untraded leg"), so the
theory's daily "0 survivors" is indistinguishable from "the threshold ate
them". This measures the distribution the threshold cuts through.

TWO CORRECTIONS TO `probe.py`, which this supersedes rather than edits
(the original stays as the record of what the v3 thresholds were fit on):

1. BOARD RECONSTRUCTION. `probe.py` reads a board with
   `WHERE captured_at = ?`. `snapshot.board_as_of` exists precisely
   because that stopped being the board on 2026-08-30, when
   dedup-on-write landed: a pull writes NO row for a market whose
   payload did not change, so an exact-stamp filter returns "the markets
   that moved at that pull" -- and moving markets are the liquid ones.
   The original instrument is therefore biased along exactly the axis
   this study measures. This one reconstructs properly and reports both
   numbers so the size of the distortion is visible.

2. OPEN INTEREST. `probe.py` recorded lifetime `volume` only. Open
   interest is the better sterility signal -- volume is cumulative and
   backward-looking, while OI is contracts outstanding right now -- and
   it is on every snapshot row already.

Geometry only, as in `probe.py`: `_nested_pair_findings` is pure, needs
no network, and the ME-flag path only ever REMOVES findings, so this is
an upper bound on the firing rate -- the conservative direction for
"are any of them tradeable?".

Read-only against the DB. Writes a CSV to data/.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools import db, snapshot                          # noqa: E402
from tools.domain import Market                         # noqa: E402
from tools.kalshi import markets as kmarkets            # noqa: E402
from theories.structural_arb import scan                # noqa: E402
from theories.structural_arb.theory import MIN_LEG_VOLUME  # noqa: E402

HERE = pathlib.Path(__file__).parent
OUT = HERE / "data"
OUT.mkdir(exist_ok=True)


def captures(conn) -> list[str]:
    return [r["captured_at"] for r in conn.execute(
        "SELECT DISTINCT captured_at FROM market_snapshots "
        "WHERE platform = 'kalshi' ORDER BY captured_at")]


def _markets(rows) -> list[Market]:
    """Rehydrate through the same normalize a live fetch uses."""
    out = []
    for row in rows:
        text = snapshot.payload_text(row["raw_json"])
        if not text:
            continue
        out.append(kmarkets.normalize(json.loads(text)))
    return out


def board_as_of(conn, at: str) -> list[Market]:
    return _markets(snapshot.board_as_of(conn, "kalshi", at))


def board_exact_stamp(conn, at: str) -> list[Market]:
    """probe.py's reconstruction, kept only to size its error."""
    return _markets(conn.execute(
        "SELECT raw_json FROM market_snapshots "
        "WHERE platform = 'kalshi' AND captured_at = ?", (at,)))


def findings_for(board: list[Market]) -> list:
    """Every nested-pair violation, grouped exactly as `scan.scan_events`
    groups. The `underlying_key` split is load-bearing -- omitting it
    produced 10,799 nonsense "violations" in this probe's first draft."""
    found = []
    for event, markets in scan.group_by_event(board).items():
        groups: dict[str, list] = {}
        for m in markets:
            ys = scan.yes_set(m)
            if ys is None:
                continue
            key = scan.underlying_key(m)
            if key is None:
                continue
            groups.setdefault(key, []).append((m, ys))
        for scalar in groups.values():
            if len(scalar) >= 2:
                found.extend(scan._nested_pair_findings(scalar, event))
    return found


def main() -> None:
    conn = db.connect()
    caps = captures(conn)
    print("captures: %d\n" % len(caps))
    print("%-22s %8s %8s %8s %8s"
          % ("capture", "exact", "as_of", "v_exact", "v_as_of"))

    seen: dict[tuple, dict] = defaultdict(
        lambda: {"n_captures": 0, "costs": set()})
    for cap in caps:
        b_exact = board_exact_stamp(conn, cap)
        b_asof = board_as_of(conn, cap)
        f_exact = findings_for(b_exact)
        f_asof = findings_for(b_asof)
        print("%-22s %8d %8d %8d %8d"
              % (cap, len(b_exact), len(b_asof), len(f_exact), len(f_asof)))
        for f in f_asof:
            legs = tuple(sorted(l.market.ticker for l in f.legs))
            rec = seen[legs]
            rec["n_captures"] += 1
            rec["costs"].add(round(sum(l.price for l in f.legs), 4))
            rec["event"] = f.legs[0].market.event_ticker
            rec["series"] = f.legs[0].market.series_ticker
            rec["volumes"] = tuple(l.market.volume for l in f.legs)
            rec["ois"] = tuple(l.market.open_interest for l in f.legs)
            rec["profit_floor"] = f.profit_floor
            rec["cost"] = f.cost

    rows = []
    for legs, rec in sorted(seen.items(), key=lambda kv: -kv[1]["n_captures"]):
        vols = [v or 0.0 for v in rec["volumes"]]
        ois = [o or 0.0 for o in rec["ois"]]
        rows.append({
            "legs": " + ".join(legs),
            "series": rec["series"],
            "n_captures": rec["n_captures"],
            "min_leg_volume": min(vols),
            "min_leg_oi": min(ois),
            "max_leg_oi": max(ois),
            "distinct_costs": len(rec["costs"]),
            "cost": sorted(rec["costs"])[0],
            "profit_floor": round(rec["profit_floor"], 4),
        })

    with (OUT / "violations_v2.csv").open("w", newline="",
                                          encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows
                           else ["legs"])
        w.writeheader()
        w.writerows(rows)

    print("\ndistinct violations across all captures: %d" % len(rows))

    print("\n--- what MIN_LEG_VOLUME = %g cuts through ---" % MIN_LEG_VOLUME)
    buckets = [(0, 1), (1, 10), (10, 100), (100, 500), (500, 10 ** 9)]
    for lo, hi in buckets:
        sel = [r for r in rows if lo <= r["min_leg_volume"] < hi]
        if not sel:
            continue
        with_oi = [r for r in sel if r["min_leg_oi"] >= 100]
        persist = [r for r in sel if r["n_captures"] > 1]
        frozen = [r for r in sel
                  if r["distinct_costs"] == 1 and r["n_captures"] > 1]
        side = "REMOVED by threshold" if hi <= MIN_LEG_VOLUME else "kept"
        label = "%d-%s" % (lo, hi if hi < 10 ** 9 else "inf")
        print("  vol %9s [%-20s]: %4d violations, %3d with min leg OI>=100,"
              " %3d persistent, %3d frozen"
              % (label, side, len(sel), len(with_oi), len(persist),
                 len(frozen)))

    removed = [r for r in rows if r["min_leg_volume"] < MIN_LEG_VOLUME]
    live_oi = [r for r in removed if r["min_leg_oi"] >= 100]
    print("\nviolations the threshold removes            : %d" % len(removed))
    print("  ...of which BOTH legs carry OI >= 100     : %d" % len(live_oi))
    if live_oi:
        print("\n  THESE ARE THE CANDIDATES THE THRESHOLD MAY BE WRONG ABOUT:")
        for r in sorted(live_oi, key=lambda r: -r["min_leg_oi"])[:20]:
            print("    minvol=%8.1f minOI=%9.1f floor=%.4f caps=%2d  %s"
                  % (r["min_leg_volume"], r["min_leg_oi"],
                     r["profit_floor"], r["n_captures"], r["legs"][:66]))

    print("\nwritten: %s" % (OUT / "violations_v2.csv"))


if __name__ == "__main__":
    main()
