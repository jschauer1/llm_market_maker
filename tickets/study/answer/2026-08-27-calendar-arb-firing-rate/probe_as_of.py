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
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tools import db, snapshot                              # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe import scan                                      # noqa: E402


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
    main()
