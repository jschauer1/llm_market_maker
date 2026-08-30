"""Are structural_arb's nested-pair violations tradeable, or only visible?

Replays the theory's own geometry finder over every stored board snapshot
and records, for each violation, the LIFETIME VOLUME of its two legs and
how many snapshots it survives.

Geometry only: `_nested_pair_findings` is pure and deterministic, so this
needs no API and no mutually-exclusive flag lookups. The flag check only
ever REMOVES findings, so this is an upper bound on the theory's firing
rate -- the conservative direction for the question being asked ("are any
of them tradeable?"). Grouping must still match `scan.scan()` exactly;
see `findings_for` for the 1,800x error that follows from getting it
wrong.

Read-only. Writes a CSV to data/.
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

HERE = pathlib.Path(__file__).parent
OUT = HERE / "data"
OUT.mkdir(exist_ok=True)


def snapshots(conn) -> list[str]:
    return [r["captured_at"] for r in conn.execute(
        "SELECT DISTINCT captured_at FROM market_snapshots "
        "WHERE platform = 'kalshi' ORDER BY captured_at")]


def board_at(conn, captured_at: str) -> list[Market]:
    """Rehydrate a stored pull.

    `raw_json` holds the RAW Kalshi payload -- the whole point of
    snapshotting it (CLAUDE.md: "a board rebuilt from cache is identical
    to a freshly fetched one") -- so it goes back through the same
    `markets.normalize` a live fetch uses, not through
    `Market.from_mapping`, which expects an already-normalized mapping.
    """
    out = []
    for row in conn.execute(
        "SELECT raw_json FROM market_snapshots "
        "WHERE platform = 'kalshi' AND captured_at = ?", (captured_at,)
    ):
        out.append(kmarkets.normalize(
            json.loads(snapshot.payload_text(row["raw_json"]))))
    return out


def findings_for(board: list[Market]) -> list:
    """Every nested-pair violation on this board, by the theory's own
    geometry -- grouped exactly as `scan.scan()` groups.

    The `underlying_key` split is load-bearing and was omitted in this
    probe's first draft, which produced 10,799 "violations" that were
    mostly nonsense: one event holds several ladders (a spread ladder per
    TEAM, a hits ladder per PLAYER), whose strike numbers compare
    numerically and mean nothing across subjects. `KXCFLSPREAD-...-MTL8`
    against `...-WPG4` is not a nesting -- both legs can lose -- and it
    dominated the first count. Same class of error the calendar-arb study
    hit from the other direction.
    """
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
    caps = snapshots(conn)
    print(f"snapshots: {len(caps)}")

    seen: dict[tuple, dict] = defaultdict(
        lambda: {"n_snapshots": 0, "costs": set()})
    rows = []
    for cap in caps:
        board = board_at(conn, cap)
        found = findings_for(board)
        print(f"  {cap}  markets={len(board):6d}  violations={len(found)}")
        for f in found:
            legs = tuple(sorted(l.market.ticker for l in f.legs))
            rec = seen[legs]
            rec["n_snapshots"] += 1
            rec["costs"].add(round(sum(l.price for l in f.legs), 4))
            rec["event"] = f.legs[0].market.event_ticker
            rec["series"] = f.legs[0].market.series_ticker
            rec["volumes"] = tuple(l.market.volume for l in f.legs)
            rec["prices"] = tuple(l.price for l in f.legs)
            rec["last"] = cap

    print(f"\ndistinct violations across all snapshots: {len(seen)}")
    for legs, rec in sorted(seen.items(),
                            key=lambda kv: -kv[1]["n_snapshots"]):
        vols = rec["volumes"]
        rows.append({
            "legs": " + ".join(legs),
            "series": rec["series"],
            "n_snapshots": rec["n_snapshots"],
            "min_leg_volume": min(v or 0.0 for v in vols),
            "max_leg_volume": max(v or 0.0 for v in vols),
            "distinct_costs": len(rec["costs"]),
            "cost": sorted(rec["costs"])[0],
        })

    with (OUT / "violations.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["legs"])
        w.writeheader()
        w.writerows(rows)

    print("\nby minimum leg lifetime volume:")
    buckets = [(0, 1), (1, 100), (100, 500), (500, 10 ** 9)]
    for lo, hi in buckets:
        sel = [r for r in rows if lo <= r["min_leg_volume"] < hi]
        persist = [r for r in sel if r["n_snapshots"] > 1]
        frozen = [r for r in sel if r["distinct_costs"] == 1
                  and r["n_snapshots"] > 1]
        label = f"{lo}-{hi if hi < 10 ** 9 else 'inf'}"
        print(f"  vol {label:>10s}: {len(sel):4d} violations, "
              f"{len(persist):4d} seen in >1 snapshot, "
              f"{len(frozen):4d} of those never moved a cent")

    print("\nmost persistent violations:")
    for r in rows[:12]:
        print(f"  {r['n_snapshots']:2d} snaps  cost={r['cost']:.4f}  "
              f"minvol={r['min_leg_volume']:9.1f}  "
              f"costs_seen={r['distinct_costs']}  {r['legs'][:74]}")
    print(f"\nwritten: {OUT / 'violations.csv'}")


if __name__ == "__main__":
    main()
