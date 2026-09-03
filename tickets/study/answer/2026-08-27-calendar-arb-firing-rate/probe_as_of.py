"""calendar-arb firing-rate probe — the re-runnable version of `probe.py`.

**Why this file exists.** `probe.py` rebuilds each board with
`WHERE captured_at = ?`. That was correct when it ran on 2026-08-27 and
stopped being correct on 2026-08-30, when dedup-on-write (spec 5.2 phase 2)
landed: a pull now writes NO row for a market whose payload did not change,
so an exact-stamp filter returns *the markets that moved at that pull*
rather than the board. It fails silently — a plausible board of the wrong
markets — and the missing subset is the illiquid one, so it is biased along
exactly the axis this study measures.

Measured on the identical defect in `structural_arb`'s probe, same 17
captures both ways: 3,254 markets exact against 107,656 reconstructed at
2026-08-27T11:47:05Z, and 24 raw violations found against 36. A third of
the findings were invisible.

`probe.py` is left exactly as run, because its zero-violation result is
what falsified calendar-arb's hard-arbitrage premise and is cited as-run.
This file supersedes it for any re-run, and follows
`2026-08-29-structural-arb-violation-liquidity/probe_volume_threshold.py`
in printing the exact-stamp count beside the reconstructed one, so the
distortion stays visible instead of being quietly corrected away.

The scan itself is imported from `probe.py` unchanged — the only thing
this file changes is how a board is rebuilt.

    python tickets/study/answer/2026-08-27-calendar-arb-firing-rate/probe_as_of.py out.json
"""
import collections
import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tools import db, snapshot                              # noqa: E402
from tools.sizing import fee_pts                            # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe import price, scan, subject_key                  # noqa: E402


#: Result 2's horizon buckets, in days, exactly as the published table
#: splits them. `None` is the open-ended top bucket.
HORIZON_BUCKETS = (("<=90d", 90), ("90d-1y", 365), ("1y-3y", 1095),
                   (">3y", None))


def _bucket(days: float) -> str:
    for name, hi in HORIZON_BUCKETS:
        if hi is None or days <= hi:
            return name
    raise AssertionError("unreachable: the last bucket is open-ended")


def ladder_pairs(rows, as_of: str):
    """Every ordered ladder pair on one board, with horizon and scope.

    The enumeration is `probe.scan`'s, step for step -- same status
    filter, same strike-aware `subject_key`, same executable
    `yes_ask`/`no_ask`, same skip of equal close times. It differs only
    in yielding EVERY pair rather than only the violating ones, because
    Result 2 tabulates the whole population while Result 1 tabulates its
    tail. Keeping them identical is what lets the cell counts be checked
    against `scan`'s own `checked` total on the same board.
    """
    t0 = _dt.datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    groups = collections.defaultdict(list)
    for m in rows:
        if m.get("status") not in ("active", "open"):
            continue
        k = subject_key(m)
        if k is None or not k[0]:
            continue
        groups[k].append(m)

    for k, ms in groups.items():
        ms = [m for m in ms if m.get("close_time")]
        if len(ms) < 2:
            continue
        ms.sort(key=lambda m: m["close_time"])
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                early, later = ms[i], ms[j]
                if early["close_time"] == later["close_time"]:
                    continue
                y = price(later, "yes_ask")
                n = price(early, "no_ask")
                if y is None or n is None or y <= 0 or n <= 0:
                    continue
                close = _dt.datetime.fromisoformat(
                    later["close_time"].replace("Z", "+00:00"))
                yield {
                    "series": k[0],
                    "same_event": (early.get("event_ticker")
                                   == later.get("event_ticker")),
                    "horizon": _bucket((close - t0).total_seconds() / 86400.0),
                    "cost": y + n,
                    "cost_net": y + n + (fee_pts(y) + fee_pts(n)) / 100.0,
                    "yes_ticker": later["ticker"],
                    "no_ticker": early["ticker"],
                }


def tabulate(rows, as_of: str) -> dict:
    """Result 2's horizon x scope table: pairs and min cost per cell."""
    cells: dict = {}
    for pair in ladder_pairs(rows, as_of):
        key = (pair["horizon"],
               "same-event" if pair["same_event"] else "cross-event")
        c = cells.setdefault(key, {"pairs": 0, "min_cost": None,
                                   "min_cost_net": None, "argmin": None})
        c["pairs"] += 1
        if c["min_cost"] is None or pair["cost"] < c["min_cost"]:
            c["min_cost"] = pair["cost"]
            c["argmin"] = (pair["series"], pair["yes_ticker"],
                           pair["no_ticker"])
        if c["min_cost_net"] is None or pair["cost_net"] < c["min_cost_net"]:
            c["min_cost_net"] = pair["cost_net"]
    return cells


def print_table(cells: dict, label: str) -> None:
    """`min cost` is GROSS (yes_ask + no_ask), which is what the published
    table reports; `min +fees` adds both legs' fees, and a cell below
    1.000 there is a genuine violation rather than a near miss."""
    print()
    print("RESULT 2 TABLE -- %s" % label)
    print("  %-10s %-12s %7s %10s %10s" % ("horizon", "scope", "pairs",
                                           "min cost", "min +fees"))
    total = 0
    for name, _ in HORIZON_BUCKETS:
        for scope in ("same-event", "cross-event"):
            c = cells.get((name, scope))
            if c is None:
                print("  %-10s %-12s %7d %10s %10s" % (name, scope, 0,
                                                       "--", "--"))
                continue
            total += c["pairs"]
            print("  %-10s %-12s %7d %10.3f %10.3f"
                  % (name, scope, c["pairs"], c["min_cost"],
                     c["min_cost_net"]))
    print("  %-23s %7d" % ("TOTAL", total))


def board_as_of(conn, at: str) -> list[dict]:
    """The board at `at`, by validity interval. Use this, never the stamp."""
    return [json.loads(snapshot.payload_text(r["raw_json"]))
            for r in snapshot.board_as_of(conn, "kalshi", at)]


def board_exact_stamp_count(conn, at: str) -> int:
    """How many rows the superseded query would have seen, for contrast."""
    # EXACT-STAMP-OK: counts the wrong query's rows on purpose, so the size
    # of the distortion is printed rather than silently corrected away.
    return conn.execute(
        "SELECT COUNT(*) FROM market_snapshots "
        "WHERE platform = 'kalshi' AND captured_at = ?", (at,)
    ).fetchone()[0]


def main_table():
    """Re-derive Result 2's horizon x scope table on correct boards.

    **The bar was fixed before any number here existed**, by ticket
    `2026-09-02-calendar-arb-295-pair-table-unverified` (filed
    2026-09-02): does the near-dated same-event cell still hold ~295
    pairs at min cost 1.000, and is the near-dated CROSS-event cell
    still empty? Those two are the structural finding that closed
    calendar-arb, and Result 2 was published from a board reconstructed
    with the exact-stamp query that dedup-on-write invalidated.

    The newest capture is the headline, because Result 2 was computed on
    "the newest board" and the comparison has to be like for like. Every
    other capture is printed underneath as a stability check -- a
    structural claim about how Kalshi *lists* date ladders should not
    move from board to board, and if it does, that is itself the finding.
    """
    conn = db.connect()
    caps = [r["captured_at"] for r in conn.execute(
        "SELECT DISTINCT captured_at FROM market_snapshots "
        "WHERE platform='kalshi' ORDER BY captured_at")]
    newest = caps[-1]

    rows = board_as_of(conn, newest)
    exact = board_exact_stamp_count(conn, newest)
    print("headline capture : %s" % newest)
    print("  markets: %d reconstructed, %d by the superseded exact-stamp "
          "query" % (len(rows), exact))
    cells = tabulate(rows, newest)
    print_table(cells, "newest board %s" % newest)

    near_same = cells.get(("<=90d", "same-event"))
    near_cross = cells.get(("<=90d", "cross-event"))
    print()
    print("THE TWO PRE-STATED CLAIMS")
    print("  near-dated same-event pairs : %d  (published 295)"
          % (near_same["pairs"] if near_same else 0))
    print("  min cost in that cell       : %s  (published 1.000)"
          % ("%.3f" % near_same["min_cost"] if near_same else "--"))
    print("  near-dated CROSS-event pairs: %d  (published 0)"
          % (near_cross["pairs"] if near_cross else 0))
    if near_cross:
        print("      min cost %.3f  %s" % (near_cross["min_cost"],
                                           near_cross["argmin"]))

    print()
    print("STABILITY -- the same two cells on every stored capture")
    print("  %-24s %8s %9s %10s %10s" % ("capture", "markets", "near/same",
                                         "min cost", "near/cross"))
    for cap in caps:
        r = board_as_of(conn, cap)
        cl = tabulate(r, cap)
        s = cl.get(("<=90d", "same-event"))
        x = cl.get(("<=90d", "cross-event"))
        print("  %-24s %8d %9d %10s %10d"
              % (cap, len(r), s["pairs"] if s else 0,
                 "%.3f" % s["min_cost"] if s else "--",
                 x["pairs"] if x else 0))


def main():
    conn = db.connect()
    caps = [r["captured_at"] for r in conn.execute(
        "SELECT DISTINCT captured_at FROM market_snapshots "
        "WHERE platform='kalshi' ORDER BY captured_at")]
    total = []
    print(f"{'capture':24s} {'exact':>8s} {'as_of':>8s} {'pairs':>7s} "
          f"{'viol':>5s}")
    for cap in caps:
        rows = board_as_of(conn, cap)
        exact = board_exact_stamp_count(conn, cap)
        checked, findings = scan(rows)
        flag = "  <- truncated" if exact < len(rows) * 0.99 else ""
        print(f"{cap:24s} {exact:8d} {len(rows):8d} {checked:7d} "
              f"{len(findings):5d}{flag}")
        for f in findings:
            scope = "same-event" if f["same_event"] else "CROSS-EVENT"
            print(f"    [{scope}] {f['series']:22s} profit={f['profit']:+.4f}"
                  f"  YES {f['yes_ticker']} @{f['yes_ask']:.2f}"
                  f" ({f['yes_close']})  NO {f['no_ticker']}"
                  f" @{f['no_ask']:.2f} ({f['no_close']})")
        total.append((cap, checked, findings))
    print()
    all_f = [f for _, _, fs in total for f in fs]
    print(f"snapshots={len(total)}  total pairs checked="
          f"{sum(c for _, c, _ in total)}  total violations={len(all_f)}")
    if all_f:
        cross = [f for f in all_f if not f["same_event"]]
        print(f"cross-event violations (calendar-arb's own claim): {len(cross)}")
        print(f"median profit/basket: "
              f"{sorted(f['profit'] for f in all_f)[len(all_f)//2]:.4f}")
    if len(sys.argv) > 1:
        json.dump(all_f, open(sys.argv[1], "w"), indent=1)


if __name__ == "__main__":
    if "--table" in sys.argv:
        main_table()
    else:
        main()
