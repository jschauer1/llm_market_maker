"""Run 1's three supporting checks, made reproducible for the completion re-run.

Run 1 (37% backfill coverage) rested its DO-NOT-BUILD verdict on three
checks that were computed ad hoc and never persisted: an open-interest
ladder, an out-of-sample split, and a leave-one-series-out sweep, plus a
decomposition showing the series-equal-weighted counter-evidence was
carried by series contributing a single pair. `measure.py` already
reproduces the ladder and the split. The LOO and the decomposition
existed only in that session's scrollback, which is exactly the failure
CLAUDE.md's data conventions are about -- so they live here now.

This file adds NOTHING to the pre-registration. Every constant is
imported from `measure.py`, which is where they were fixed before any
effect was computed. It only re-derives, at a stated collection state,
the checks whose numbers the STUDY.md write-up quotes.

    python theories/no_side_premium/studies/answer/2026-09-01-liquidity-filtered-side-split/completion_checks.py <copy.db>
"""

from __future__ import annotations

import collections
import sqlite3
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from measure import (  # noqa: E402  -- pre-registered constants, not redefined
    BAND_HI,
    BAND_LO,
    MIN_PER_SIDE_PRIMARY,
    OI_PRIMARY,
    net,
    tradeable,
)


def load(db: str):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT ticker, series_ticker, close_time, side, ask, won, "
        "       spread, volume, open_interest "
        "  FROM obs "
        " WHERE ask IS NOT NULL AND won IS NOT NULL AND close_time IS NOT NULL"
    ).fetchall()
    conn.close()
    return rows


def pairs_for(band, min_per_side: int):
    cells = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in band:
        cells[(r["series_ticker"], r["close_time"][:10])][r["side"]].append(r)
    return [
        (k[0], k[1], net(v["no"]) - net(v["yes"]))
        for k, v in cells.items()
        if len(v["yes"]) >= min_per_side and len(v["no"]) >= min_per_side
    ]


def day_clustered(pairs):
    by_day = collections.defaultdict(list)
    for _ser, day, x in pairs:
        by_day[day].append(x)
    vals = [statistics.mean(v) for v in by_day.values()]
    if len(vals) < 2:
        return None, None, None
    m = statistics.mean(vals)
    se = statistics.stdev(vals) / len(vals) ** 0.5
    return m, se, (m / se if se else None)


def main() -> None:
    db = sys.argv[1] if len(sys.argv) > 1 else (
        "theories/insider_bias/mention_family/studies/investigation/2026-08-29-series-bias-mining/data/collect.db")
    rows = load(db)
    have = [r for r in rows if r["spread"] is not None]
    series = {r["series_ticker"] for r in rows}
    print(f"COLLECTION STATE: {len(rows)} observations, {len(series)} series")
    pct = 100.0 * len(have) / max(1, len(rows))
    print(f"BACKFILL COVERAGE: {len(have)} rows "
          f"({pct:.2f}%) carry liquidity columns")

    # --- coverage by first letter: run 1's caveat was that whole
    #     categories were absent because backfill runs alphabetically.
    print("\n=== 0. COVERAGE BY FIRST LETTER OF SERIES TICKER ===")
    print("    (run 1's caveat: alphabetical backfill meant whole")
    print("     families were absent. This is the check that retires it.)")
    per = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        # series tickers are KX-prefixed; the letter that ordered the
        # backfill is the first one after KX.
        t = r["series_ticker"]
        key = (t[2:3] or "?") if t.startswith("KX") else (t[0:1] or "?")
        per[key][0] += 1
        if r["spread"] is not None:
            per[key][1] += 1
    line = []
    for k in sorted(per):
        tot, cov = per[k]
        line.append(f"{k} {100*cov//max(1,tot):3d}%")
    print("   ", "  ".join(line))
    worst = [(k, v) for k, v in per.items() if v[1] < v[0]]
    short = ", ".join(f"{k}({v[0] - v[1]} rows short)" for k, v in sorted(worst))
    print(f"    letters below 100%: {short or 'none'}")

    band = [r for r in have
            if BAND_LO <= r["ask"] < BAND_HI and tradeable(r, OI_PRIMARY)]
    pairs = pairs_for(band, MIN_PER_SIDE_PRIMARY)
    all_series = sorted({s for s, _, _ in pairs})
    m, se, t = day_clustered(pairs)
    print(f"\n=== 1. THE PRIMARY, restated ===")
    print(f"    WITHIN (series, close day), spread<=0.07 & oi>={OI_PRIMARY}")
    print(f"    {len(pairs)} pairs over {len(all_series)} series"
          f"   mean={m:+.2f}  SE={se:.2f}  t={t:+.2f}")

    # --- LOO over series: is the estimate carried by one family?
    print("\n=== 2. LEAVE-ONE-SERIES-OUT (run 1's check 3) ===")
    loo = []
    for s in all_series:
        kept = [p for p in pairs if p[0] != s]
        lm, _lse, _lt = day_clustered(kept)
        if lm is not None:
            loo.append((lm, s))
    loo.sort()
    neg = sum(1 for v, _ in loo if v < 0)
    print(f"    {len(loo)} estimates   range {loo[0][0]:+.2f} .. "
          f"{loo[-1][0]:+.2f}   negative in {neg}/{len(loo)}")
    print(f"    most negative when dropping {loo[-1][1]} -> {loo[-1][0]:+.2f}")
    print(f"    most positive when dropping {loo[0][1]} -> {loo[0][0]:+.2f}")
    print("    (a LOO range that straddles zero means no single series")
    print("     carries the estimate -- the same reading as run 1's,")
    print("     but here the estimate it fails to carry is ~0, not -1.02)")

    # --- the k=1 decomposition that explained run 1's counter-evidence
    print("\n=== 3. SERIES-EQUAL-WEIGHTING DECOMPOSED (run 1's counter-evidence) ===")
    print("    Run 1: series-equal gave +9.11 while day-clustering gave -1.02,")
    print("    and 23 of 40 series contributed a SINGLE pair, which can only")
    print("    take values near 0 or near +/-100. Does that hold at completion?")
    by_ser = collections.defaultdict(list)
    for s, _day, x in pairs:
        by_ser[s].append(x)
    servals = {s: statistics.mean(v) for s, v in by_ser.items()}
    k1 = [v for s, v in servals.items() if len(by_ser[s]) == 1]
    kn = [v for s, v in servals.items() if len(by_ser[s]) > 1]
    print(f"    series-equal-weighted, all      n={len(servals):<4} "
          f"mean={statistics.mean(servals.values()):+7.2f}  "
          f"median={statistics.median(servals.values()):+7.2f}")
    if k1:
        print(f"    series with exactly 1 pair      n={len(k1):<4} "
              f"mean={statistics.mean(k1):+7.2f}  "
              f"median={statistics.median(k1):+7.2f}")
    if kn:
        print(f"    series with >1 pair             n={len(kn):<4} "
              f"mean={statistics.mean(kn):+7.2f}  "
              f"median={statistics.median(kn):+7.2f}")
    top = sorted(servals.items(), key=lambda kv: -abs(kv[1]))[:6]
    print("    largest |series value| and its pair count:")
    for s, v in top:
        print(f"      {s:28s} {v:+8.2f}   k={len(by_ser[s])}")


if __name__ == "__main__":
    main()
