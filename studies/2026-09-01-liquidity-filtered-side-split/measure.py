"""The deciding experiment for `no-favorite-high-band`: does the NO-favorite
side gap survive once the quotes are ones you could actually fill?

`studies/2026-09-01-side-split-60day-obs/` found the pooled NO-minus-YES gap
in the 0.90-0.97 band is +3.95 (t=3.03) and that ALL of it is composition:
differenced within (series, close day) it is -1.85. But that sweep applies no
liquidity filter at all, while the `insider_bias.screen` population where the
same control does NOT reverse (+7.69) filters on spread and volume. So the two
populations disagree about the same question, and the candidate reason is that
the sweep's gap lives among quotes nobody could fill.

This runs the composition control INSIDE the liquidity filter. That is the one
run the parent ticket names as deciding whether the theory gets built.

The filter, the threshold, the control's minimum rows per side, the sensitivity
ladder and the decision rule are all pre-registered in STUDY.md and were fixed
BEFORE any effect number in this file was computed. Do not change them here.

Supersedes nothing: `2026-09-01-side-split-60day-obs/measure.py` is left as
run, because its numbers are cited in the ticket and the floor report.

Run against a COPY of the collector's db -- a multi-hour backfill holds the
live file and a long read risks locking it:

    python studies/2026-09-01-liquidity-filtered-side-split/measure.py <copy.db>
"""

from __future__ import annotations

import collections
import sqlite3
import statistics
import sys
from pathlib import Path

# --- pre-registered constants; see STUDY.md -------------------------------
BAND_LO, BAND_HI = 0.90, 0.97   # insider_bias.screen's own upper bound
MAX_SPREAD = 0.07               # second, explicitly NOT load-bearing
OI_PRIMARY = 100                # set from the distribution, before any effect
OI_LADDER = (250, 500, 1000, 2000)
MIN_PER_SIDE_PRIMARY = 1
MIN_PER_SIDE_LADDER = (2, 3)
OOS_BEFORE = "2026-08-20"       # clear of the 2026-08-25 fullcov mining runs


def fee_pts(price: float) -> float:
    return min(0.07 * price * (1.0 - price), 0.035) * 100.0


def net(rows) -> float | None:
    """Net edge in points: (win rate - mean ask) - mean fee."""
    if not rows:
        return None
    wr = sum(r["won"] for r in rows) / len(rows)
    ask = sum(r["ask"] for r in rows) / len(rows)
    fee = sum(fee_pts(r["ask"]) for r in rows) / len(rows)
    return (wr - ask) * 100 - fee


def day_stat(rows):
    """Day-clustered mean/SE. Rows within a close day are not independent
    draws (2026-08-27 settlement-day clustering study)."""
    by_day: dict[str, list] = {}
    for r in rows:
        by_day.setdefault(r["close_time"][:10], []).append(r)
    vals = [v for v in (net(rs) for rs in by_day.values()) if v is not None]
    if not vals:
        return None
    mean = statistics.mean(vals)
    se = statistics.stdev(vals) / len(vals) ** 0.5 if len(vals) > 1 else None
    return {"n": len(rows), "days": len(vals), "mean": mean, "se": se,
            "t": (mean / se) if se else None, "pos": sum(v > 0 for v in vals)}


def show(label, s, width: int = 46) -> None:
    if s is None:
        print(f"  {label:{width}} --")
        return
    se = f"{s['se']:5.2f}" if s["se"] else "  -- "
    t = f"{s['t']:+5.2f}" if s["t"] is not None else "  -- "
    print(f"  {label:{width}} n={s['n']:<5} days={s['days']:<3} "
          f"mean={s['mean']:+7.2f}  SE={se}  t={t}  {s['pos']}/{s['days']}+")


def tradeable(r, oi_min: int) -> bool:
    """The pre-registered filter. open_interest is the load-bearing half:
    a 1c spread on a market nobody holds is still a quote (series-bias
    STUDY.md, 'Correction to pass 4's filter')."""
    return (r["spread"] is not None and r["spread"] <= MAX_SPREAD
            and (r["open_interest"] or 0) >= oi_min)


def control(band, min_per_side: int, verbose: bool = True):
    """Difference NO minus YES WITHIN (series, close day).

    This is the whole experiment. A pooled side gap can be a fact about
    which markets happen to be NO-favorites rather than about sides;
    differencing within a series on one day removes that by construction.
    """
    cells = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in band:
        cells[(r["series_ticker"], r["close_time"][:10])][r["side"]].append(r)
    pairs = [(k[0], k[1], net(v["no"]) - net(v["yes"]))
             for k, v in cells.items()
             if len(v["yes"]) >= min_per_side and len(v["no"]) >= min_per_side]
    if len(pairs) < 2:
        if verbose:
            print(f"    min>={min_per_side}: only {len(pairs)} pair(s) -- "
                  f"NOT MEASURED")
        return None

    by_day = collections.defaultdict(list)
    by_ser = collections.defaultdict(list)
    for ser, day, x in pairs:
        by_day[day].append(x)
        by_ser[ser].append(x)
    dayvals = [statistics.mean(v) for v in by_day.values()]
    servals = [statistics.mean(v) for v in by_ser.values()]

    def agg(vals):
        m = statistics.mean(vals)
        se = statistics.stdev(vals) / len(vals) ** 0.5 if len(vals) > 1 else None
        return m, se, (m / se if se else None)

    dm, dse, dt = agg(dayvals)
    sm, sse, st = agg(servals)
    if verbose:
        print(f"    min>={min_per_side}: {len(pairs)} pairs over "
              f"{len(by_ser)} series, {len(by_day)} days")
        print(f"      day-clustered          k={len(dayvals):<4} "
              f"mean={dm:+6.2f}  SE={dse if dse is None else round(dse,2)}  "
              f"t={dt if dt is None else round(dt,2)}  "
              f"{sum(v > 0 for v in dayvals)}/{len(dayvals)}+")
        print(f"      series-equal-weighted  k={len(servals):<4} "
              f"mean={sm:+6.2f}  SE={sse if sse is None else round(sse,2)}  "
              f"t={st if st is None else round(st,2)}  "
              f"{sum(v > 0 for v in servals)}/{len(servals)}+")
        print(f"      pair-equal-weighted    k={len(pairs):<4} "
              f"mean={statistics.mean([x for _, _, x in pairs]):+6.2f}")
    return {"pairs": len(pairs), "series": len(by_ser), "days": len(by_day),
            "day_mean": dm, "day_se": dse, "day_t": dt,
            "ser_mean": sm, "ser_se": sse, "ser_t": st,
            "day_pos": sum(v > 0 for v in dayvals)}


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path or not Path(path).exists():
        sys.exit("usage: measure.py <path to a COPY of collect.db>")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM obs")]
    filled = [r for r in rows if r["spread"] is not None]

    print(f"COLLECTION STATE: {len(rows)} observations, "
          f"{len({r['series_ticker'] for r in rows})} series, "
          f"{len({r['close_time'][:10] for r in rows})} close days")
    print(f"BACKFILL COVERAGE: {len(filled)} rows ({len(filled)/len(rows):.0%}) "
          f"over {len({r['series_ticker'] for r in filled})} series carry "
          f"liquidity columns")
    print("(one-run rule: a number belongs to the collection state that "
          "produced it; series are backfilled ALPHABETICALLY, so partial "
          "coverage is not a random sample)\n")

    band = [r for r in filled if BAND_LO <= r["ask"] < BAND_HI]
    keep = [r for r in band if tradeable(r, OI_PRIMARY)]
    print(f"=== 0. THE FILTER: spread<={MAX_SPREAD} AND "
          f"open_interest>={OI_PRIMARY} ===")
    print(f"  cell rows with liquidity columns : {len(band)}")
    print(f"  removed by the filter            : {len(band)-len(keep)} "
          f"({(len(band)-len(keep))/max(len(band),1):.1%})")
    print(f"  survivors                        : {len(keep)} over "
          f"{len({r['series_ticker'] for r in keep})} series, "
          f"{len({r['close_time'][:10] for r in keep})} close days")
    vols = [r["volume"] or 0 for r in keep]
    if vols:
        print(f"  per-period volume among survivors (reported, NOT "
              f"thresholded): median={statistics.median(vols):.1f} "
              f"mean={statistics.mean(vols):.1f}")
    print()

    print("=== 1. POOLED SINGLE-SIDE NET, inside the filter ===")
    print("    (the statistic the theory would be built on; pooled, so it")
    print("     carries the composition it is the control's job to remove)")
    for side in ("no", "yes"):
        show(f"{side.upper()} favorites | tradeable",
             day_stat([r for r in keep if r["side"] == side]))
    for side in ("no", "yes"):
        show(f"{side.upper()} favorites | UNfiltered (for contrast)",
             day_stat([r for r in band if r["side"] == side]))
    print()

    print("=== 2. THE COMPOSITION CONTROL -- this is what decides ===")
    print("    NO minus YES within (series, close day), inside the filter")
    res = control(keep, MIN_PER_SIDE_PRIMARY)
    print("    -- ladder on rows-per-side (robustness, never the headline) --")
    for m in MIN_PER_SIDE_LADDER:
        control(keep, m)
    print()

    print("=== 3. SENSITIVITY LADDER on the open-interest threshold ===")
    print("    (robustness. The primary above decides; a result living at")
    print("     exactly one threshold should be visible as such.)")
    for T in (OI_PRIMARY,) + OI_LADDER:
        sub = [r for r in band if tradeable(r, T)]
        nod = day_stat([r for r in sub if r["side"] == "no"])
        c = control(sub, MIN_PER_SIDE_PRIMARY, verbose=False)
        pooled = f"{nod['mean']:+6.2f}" if nod else "    --"
        if c:
            print(f"  T={T:<5} rows={len(sub):<5} ser={c['series']:<4} "
                  f"pairs={c['pairs']:<4} | NO pooled={pooled} | "
                  f"WITHIN day={c['day_mean']:+6.2f} "
                  f"(t={c['day_t'] if c['day_t'] is None else round(c['day_t'],2)}) "
                  f"series={c['ser_mean']:+6.2f}")
        else:
            print(f"  T={T:<5} rows={len(sub):<5} | NO pooled={pooled} | "
                  f"WITHIN: not measured")
    print()

    print("=== 4. OUT-OF-SAMPLE SPLIT inside the filter ===")
    print("    (cells were mined from the 2026-08-25 fullcov runs; rows")
    print(f"     closing before {OOS_BEFORE} are clear of that window)")
    for label, pred in (
        (f"close <  {OOS_BEFORE} (clean)",
         lambda r: r["close_time"][:10] < OOS_BEFORE),
        (f"close >= {OOS_BEFORE} (overlaps)",
         lambda r: r["close_time"][:10] >= OOS_BEFORE),
    ):
        sub = [r for r in keep if pred(r)]
        for side in ("no", "yes"):
            show(f"{side.upper()} | {label}",
                 day_stat([r for r in sub if r["side"] == side]), width=54)
        c = control(sub, MIN_PER_SIDE_PRIMARY, verbose=False)
        if c:
            print(f"    WITHIN (series, day): day={c['day_mean']:+6.2f} "
                  f"(t={c['day_t'] if c['day_t'] is None else round(c['day_t'],2)}"
                  f", {c['day_pos']}/{c['days']}+) "
                  f"series={c['ser_mean']:+6.2f} over {c['series']} series")
        else:
            print("    WITHIN (series, day): not measured")
    print()

    print("=== 5. VERDICT against the pre-registered decision rule ===")
    if res is None:
        print("  NOT MEASURED -- the filter left too few both-sided series.")
    else:
        d, t = res["day_mean"], res["day_t"]
        print(f"  within-series within-day = {d:+.2f} pts "
              f"(t={t if t is None else round(t,2)}, "
              f"{res['day_pos']}/{res['days']} days positive, "
              f"{res['series']} series)")
        if t is not None and t > 1.0 and d > 0:
            print("  -> POSITIVE and not explained away: the screen result is")
            print("     not contradicted by the sweep. BUILD.")
        elif d <= 0:
            print("  -> <= 0: composition here too. DO NOT BUILD; record the")
            print("     negative against idea 33.")
        else:
            print("  -> positive but weak; read section 3's ladder and the")
            print("     out-of-sample split before deciding.")


if __name__ == "__main__":
    main()
