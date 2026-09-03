"""Pass 4's two promised follow-ups. Descriptive; promotes nothing.

Neither of these is the pre-registered pass-4 test -- that is `pass4.py`,
run once, and its verdict stands whatever this file prints. These are the
two comparisons STUDY.md asks for by name:

1. **The ask-band table at full coverage.** The 2026-09-01
   cross-reference measured the filter's effect on this study's headline
   over **227 of 659** series and said in terms that those numbers
   "carry this study's own one-run rule and are due a re-run on
   completion". The sweep has now completed, so this is that re-run, on
   the same band boundaries so the two are comparable.

2. **What became of pass 3's nine flags.** Pass 4 flags nothing. That is
   only interpretable if you can tell "the effect vanished under the
   filter" from "the series fell out of the family" -- a 75% cut in
   observations does both. Printed per series, with the reason.

Reported GROSS and net side by side. The study's guard scores gross (the
2026-08-29 amendment: fees are a ~constant -1 to -3pt offset, so a
net-scored guard flags every calibrated series as negatively biased);
net answers the separate question of whether a real bias is bettable.

Run: python tickets/study/.../pass4_diagnostics.py
"""

from __future__ import annotations

import sqlite3
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root(start: Path) -> Path:
    for p in start.parents:
        if (p / "tools").is_dir() and (p / "theories").is_dir():
            return p
    raise RuntimeError("repo root not found above %s" % start)


sys.path.insert(0, str(_repo_root(Path(__file__).resolve())))
sys.path.insert(0, str(HERE))

import mine as M                                       # noqa: E402
import pass3 as P3                                     # noqa: E402
import pass4 as P4                                     # noqa: E402

DB = HERE / "data" / "collect.db"

#: The 2026-09-01 cross-reference's boundaries, reused verbatim so the
#: full-coverage numbers sit beside the 227-series ones without a
#: boundary change confounding the comparison.
BANDS = ((0.50, 0.65), (0.65, 0.80), (0.80, 0.90),
         (0.90, 0.97), (0.97, 0.98), (0.98, 1.01))

#: Pass 3's nine, from STUDY.md "Nine flags, and none of them is a
#: finding". Listed here rather than recomputed so this file cannot
#: quietly disagree with the record it is comparing against.
PASS3_FLAGS = ("KXNPBRFI", "KXNFL4Q", "KXATPCHALLENGERDOUBLES",
               "KXUELFTTS", "KXT20TEAMTOTAL", "KXKBORFI", "KXNFL2H",
               "KXCPLTEAMTOTAL", "KXATP")


def _rows(path: Path, tradeable: bool):
    where = "ask IS NOT NULL AND won IS NOT NULL AND close_time IS NOT NULL"
    if tradeable:
        where += (" AND spread IS NOT NULL AND spread <= %r"
                  " AND open_interest IS NOT NULL AND open_interest >= %r"
                  % (P4.TRADEABLE_MAX_SPREAD, P4.TRADEABLE_MIN_OI))
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    conn.row_factory = sqlite3.Row
    out = [(r["day"], float(r["won"]), float(r["ask"]))
           for r in conn.execute(
               "SELECT DATE(close_time) AS day, won, ask FROM obs "
               "WHERE " + where)]
    conn.close()
    return out


def _band_stat(rows):
    """Day-clustered gross and net edge over one band."""
    if not rows:
        return None
    g = M.day_edges(rows)
    n = M.day_edges(rows, net=True)
    days = sorted(g)
    gm, gse = M._mean_se([g[d] for d in days])
    nm, _ = M._mean_se([n[d] for d in days])
    t = gm / gse if gse not in (0.0, float("inf")) else float("nan")
    return {"n": len(rows), "days": len(days), "gross": gm,
            "net": nm, "t": t, "mde": 2.8 * gse,
            "ask": statistics.mean(a for _, _, a in rows),
            "won": statistics.mean(w for _, w, _ in rows)}


def band_table(path: Path = DB) -> None:
    print("=" * 76)
    print("(1) ASK-BAND TABLE at FULL sweep coverage -- the re-run the")
    print("    2026-09-01 cross-reference asked for (it ran on 227/659")
    print("    series; the sweep has since completed at 840/840).")
    print("    GROSS is the study's guard statistic; net beside it.")
    print("    MDE = 2.8*SE on the GROSS figure. A near-zero edge means")
    print("    'calibrated' only where the MDE is small enough to have")
    print("    SEEN a real one -- pass 1's exact mistake, printed here so")
    print("    it cannot be repeated by a reader.")
    print("=" * 76)
    for label, tradeable in (("ALL rows", False), ("TRADEABLE", True)):
        rows = _rows(path, tradeable)
        print("\n  %s  (n=%d)" % (label, len(rows)))
        print("    %-12s %7s %6s %8s %8s %8s %8s %8s %7s"
              % ("band", "n", "days", "mean ask", "realized",
                 "gross", "net", "t", "MDE"))
        for lo, hi in BANDS:
            sub = [r for r in rows if lo <= r[2] < hi]
            st = _band_stat(sub)
            if st is None:
                print("    %-12s %7s" % ("%.2f-%.2f" % (lo, hi), "--"))
                continue
            print("    %-12s %7d %6d %8.3f %8.3f %+8.2f %+8.2f %+8.2f %7.2f"
                  % ("%.2f-%.2f" % (lo, hi), st["n"], st["days"],
                     st["ask"], st["won"], st["gross"], st["net"],
                     st["t"], st["mde"]))


def flag_fates(path: Path = DB) -> None:
    print()
    print("=" * 76)
    print("(2) PASS 3's NINE FLAGS, under pass 4's filter.")
    print("    Pass 4 flags nothing. This separates 'the effect vanished'")
    print("    from 'the series left the family' -- a 75% cut in")
    print("    observations can do either, and they mean opposite things.")
    print("=" * 76)
    p3 = P3.load_collect(path)
    p4 = P4.load_tradeable(path)
    print("  %-26s %19s   %19s" % ("series", "PASS 3 (unfiltered)",
                                   "PASS 4 (tradeable)"))
    for s in PASS3_FLAGS:
        a = M.stat_for(s, p3.get(s, []))
        rows4 = p4.get(s, [])
        b = M.stat_for(s, rows4)
        left = ("%+7.2f t%+6.2f n=%d" % (a.edge, a.t, a.n)) if a else "--"
        if b is not None:
            right = "%+7.2f t%+6.2f n=%d" % (b.edge, b.t, b.n)
            why = ""
        else:
            right = "below floors"
            why = "  (%d obs survive the filter, need n>=%d/days>=%d)" % (
                len(rows4), M.MIN_N, M.MIN_DAYS)
        print("  %-26s %19s   %19s%s" % (s, left, right, why))


def mde_diagnosis(path: Path = DB) -> None:
    """Why the power gate still fails, stated in counts rather than prose."""
    print()
    print("=" * 76)
    print("(3) WHY THE POWER GATE STILL FAILS")
    print("=" * 76)
    for label, loader in (("pass 3 (unfiltered)", P3.load_collect),
                          ("pass 4 (tradeable) ", P4.load_tradeable)):
        by = loader(path)
        adm = [st for s, rows in sorted(by.items())
               if (st := M.stat_for(s, rows)) is not None]
        fam = [st for st in adm if not M.is_mention_family(st.series)]
        mdes = sorted(M.mde(st) for st in fam)
        obs = sum(len(v) for v in by.values())
        print("  %s obs=%7d  series_with_obs=%4d  admitted=%4d  "
              "family=%4d" % (label, obs, len(by), len(adm), len(fam)))
        if mdes:
            print("      median n=%d  median days=%d  median MDE=%.2f  "
                  "MDE<=8: %d/%d"
                  % (statistics.median([st.n for st in fam]),
                     statistics.median([st.n_days for st in fam]),
                     statistics.median(mdes),
                     sum(1 for m in mdes if m <= 8.0), len(mdes)))


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DB
    print("population: %s" % path.name)
    band_table(path)
    flag_fates(path)
    mde_diagnosis(path)


if __name__ == "__main__":
    main()
