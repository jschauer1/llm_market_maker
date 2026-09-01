"""Pass 3: run the pre-registered miner over the broad collection.

Passes 1 and 2 read `opportunities`/`settlements` in the main DB, because
their populations were replays of other theories' screens. Pass 3's
population is the dedicated broad sweep in `data/collect.db`, so the only
new code here is a loader that puts it in the miner's shape. **The
statistic, the floors, the gates and the Holm family come from `mine.py`
unchanged** -- this module must never redefine the bar, only feed it.

The bar this implements is STUDY.md "Pass 3 analysis bar", committed
before any per-series number on this population was computed:

  * admission by COUNT alone (n>=40, n_days>=8, halves) -- no MDE filter,
    reversing pass 2, whose SE-based floor was not outcome-neutral;
  * Holm family = every admitted NON-control series;
  * power reported, never filtered: MDE distribution and the win-rate
    composition by MDE stratum, so the selection channel pass 2 found is
    visible rather than silent;
  * the MDE<=5 view still runs, SECOND and labelled outcome-correlated.

Run: python studies/2026-08-29-series-bias-mining/pass3.py
"""

from __future__ import annotations

import sqlite3
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

import mine as M                                       # noqa: E402

DB = HERE / "data" / "collect.db"

#: STUDY.md "When this pass counts as measured", fixed before the data.
MIN_TESTED_FOR_MEASURED = 30
MAX_MEDIAN_MDE_FOR_MEASURED = 8.0

#: STUDY.md "Pre-registered signs for the two carried candidates".
PREREGISTERED_SIGNS = {"KXRT": -1, "KXLOWTLV": +1}


def load_collect(path: Path = DB) -> dict[str, list[tuple]]:
    """{series: [(day, won, ask), ...]} from the broad sweep.

    One observation per market, already priced at 25% of scheduled
    lifetime by `collect.py`. The settlement day is the market's close
    date -- the same day-clustering unit the miner uses everywhere.
    """
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    conn.row_factory = sqlite3.Row
    out: dict[str, list[tuple]] = {}
    for r in conn.execute(
            "SELECT series_ticker, DATE(close_time) AS day, won, ask "
            "FROM obs WHERE ask IS NOT NULL AND won IS NOT NULL "
            "AND close_time IS NOT NULL"):
        out.setdefault(r["series_ticker"], []).append(
            (r["day"], float(r["won"]), float(r["ask"])))
    conn.close()
    return out


def win_rate(rows) -> float:
    return sum(w for _, w, _ in rows) / len(rows)


def run(by_series: dict[str, list[tuple]] | None = None) -> dict:
    """The pre-registered pass-3 analysis. No filtering by outcome."""
    by_series = load_collect() if by_series is None else by_series
    admitted = [(s, rows, st) for s, rows in sorted(by_series.items())
                if (st := M.stat_for(s, rows)) is not None]

    control = [st for s, _, st in admitted if M.is_mention_family(s)]
    family = [(s, rows, st) for s, rows, st in admitted
              if not M.is_mention_family(s)]
    stats = [st for _, _, st in family]

    survivors = M.holm(stats)
    flagged = [st for st in stats
               if st.passes_split and st.passes_t and st.series in survivors]

    mdes = sorted(M.mde(st) for st in stats)
    median_mde = statistics.median(mdes) if mdes else float("inf")
    measured = (len(stats) >= MIN_TESTED_FOR_MEASURED
                and median_mde <= MAX_MEDIAN_MDE_FOR_MEASURED)

    # The selection channel pass 2 found, made visible: win-rate
    # composition by MDE stratum. Reported, never used to filter.
    lo = [win_rate(rows) for _, rows, st in family if M.mde(st) <= 8.0]
    hi = [win_rate(rows) for _, rows, st in family if M.mde(st) > 8.0]

    # Secondary, labelled: pass 2's outcome-correlated power floor.
    powered = [st for st in stats if M.mde(st) <= M.MAX_MDE_PTS]
    powered_surv = M.holm(powered)
    powered_flagged = [st for st in powered
                       if st.passes_split and st.passes_t
                       and st.series in powered_surv]

    carried = {st.series: st for st in stats
               if st.series in PREREGISTERED_SIGNS}

    return {
        "series_seen": len(by_series),
        "series_admitted": len(admitted),
        "control": control,
        "stats": stats,
        "median_mde": median_mde,
        "mdes": mdes,
        "measured": measured,
        "flagged": flagged,
        "holm_survivors": survivors,
        "expected_false_positives": M.ALPHA * len(stats),
        "winrate_low_mde": statistics.mean(lo) if lo else None,
        "winrate_high_mde": statistics.mean(hi) if hi else None,
        "powered_tested": len(powered),
        "powered_flagged": powered_flagged,
        "carried": carried,
    }


def main() -> None:
    r = run()
    print("=" * 72)
    print("PASS 3 -- broad sweep, bar pre-registered in STUDY.md 2026-09-01")
    print("=" * 72)
    print("series with priced obs      : %d" % r["series_seen"])
    print("series clearing floors      : %d" % r["series_admitted"])
    print("  of which mention control  : %d" % len(r["control"]))
    print("series TESTED (Holm family) : %d" % len(r["stats"]))
    print("expected false positives    : %.1f" % r["expected_false_positives"])
    print("median MDE over tested      : %.2f pts" % r["median_mde"])
    print()
    print("PRE-REGISTERED 'MEASURED'?  : %s   (needs >=%d tested and "
          "median MDE <=%s)"
          % ("YES" if r["measured"] else "NO -- not measured",
             MIN_TESTED_FOR_MEASURED, MAX_MEDIAN_MDE_FOR_MEASURED))
    print("FLAGGED (all four gates)    : %d" % len(r["flagged"]))
    for st in sorted(r["flagged"], key=lambda x: -abs(x.t)):
        print("    %-24s n=%5d days=%4d gross=%+7.2f net=%+7.2f "
              "t=%+6.2f p=%.2e halves %+6.2f/%+6.2f"
              % (st.series, st.n, st.n_days, st.edge, st.edge_net,
                 st.t, st.p, st.first_edge, st.second_edge))

    print()
    print("-- selection channel (reported, never filtered) --")
    if r["winrate_low_mde"] is not None and r["winrate_high_mde"] is not None:
        print("  mean win rate, MDE<=8 : %.4f" % r["winrate_low_mde"])
        print("  mean win rate, MDE >8 : %.4f" % r["winrate_high_mde"])
        print("  (pass 2 measured 0.864 vs 0.829; a gap here means an "
              "MDE floor would again admit on outcome)")

    print()
    print("-- SECONDARY view: pass 2's MDE<=5 floor, OUTCOME-CORRELATED --")
    print("  tested  : %d" % r["powered_tested"])
    print("  flagged : %d  %s"
          % (len(r["powered_flagged"]),
             [s.series for s in r["powered_flagged"]]))

    print()
    print("-- carried candidates, signs fixed before looking --")
    for series, want in PREREGISTERED_SIGNS.items():
        st = r["carried"].get(series)
        if st is None:
            print("  %-12s not in the admitted family this pass" % series)
            continue
        got = 1 if st.edge > 0 else -1
        ok = (got == want and st.passes_t
              and st.series in r["holm_survivors"])
        note = "" if got == want else "  [SIGN OPPOSITE -- failed test]"
        print("  %-12s predicted %s | gross %+7.2f t %+6.2f p %.2e "
              "n=%d days=%d -> %s%s"
              % (series, "+" if want > 0 else "-", st.edge, st.t, st.p,
                 st.n, st.n_days,
                 "CONFIRMED" if ok else "not confirmed", note))

    print()
    print("-- negative control (mention_family), measured not promoted --")
    bad = [s for s in r["control"] if s.passes_split and s.passes_t]
    print("  control series admitted : %d" % len(r["control"]))
    print("  control tripping split+t: %d  %s"
          % (len(bad), [s.series for s in bad]))


if __name__ == "__main__":
    main()
