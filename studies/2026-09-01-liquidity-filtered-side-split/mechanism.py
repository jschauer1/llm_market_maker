"""What the liquidity filter DOES to this population -- descriptive, post-hoc,
and deliberately NOT part of the pre-registered test in `measure.py`.

Kept in its own file on purpose. `measure.py` is the pre-registered deciding
experiment for `no-favorite-high-band` and its contents were fixed before any
effect was computed; growing it after seeing a result would blur what was
pre-registered and what was not. Everything here is exploratory description of
a population, not a test of a hypothesis, and must be read that way.

WHY IT IS WORTH RUNNING AT ALL. `measure.py` section 1 showed the filter moves
the cell's pooled NO net edge from -4.31 to -0.02 and the YES from -3.96 to
+2.19. If that holds across the whole price range, then the series-bias
study's headline reading -- "every level is deeply negative" -- is a
statement about quotes nobody could fill rather than about market
calibration, and every future session reading `obs` needs to know it.

    python studies/2026-09-01-liquidity-filtered-side-split/mechanism.py <copy.db>
"""

from __future__ import annotations

import sqlite3
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure import MAX_SPREAD, OI_PRIMARY, day_stat, tradeable  # noqa: E402

BANDS = ((0.50, 0.65), (0.65, 0.80), (0.80, 0.90), (0.90, 0.97),
         (0.97, 0.98), (0.98, 1.01))
OI_BANDS = ((0, 1), (1, 100), (100, 500), (500, 2000), (2000, 10 ** 9))


def line(label, s, width=30):
    if s is None:
        print(f"  {label:{width}} --")
        return
    t = f"{s['t']:+5.2f}" if s["t"] is not None else "  -- "
    print(f"  {label:{width}} n={s['n']:<6} days={s['days']:<3} "
          f"net={s['mean']:+7.2f}  t={t}")


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path or not Path(path).exists():
        sys.exit("usage: mechanism.py <path to a COPY of collect.db>")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM obs")]
    filled = [r for r in rows if r["spread"] is not None]
    print(f"backfilled rows: {len(filled)} of {len(rows)} "
          f"({len(filled)/len(rows):.0%}), "
          f"{len({r['series_ticker'] for r in filled})} series\n")

    print("=== A. NET EDGE BY PRICE BAND: everything vs a tradeable book ===")
    print(f"    filter = spread<={MAX_SPREAD} AND open_interest>={OI_PRIMARY}")
    print(f"    {'band':<14}{'ALL (net / t / n)':<34}TRADEABLE (net / t / n)")
    for lo, hi in BANDS:
        b = [r for r in filled if lo <= r["ask"] < hi]
        k = [r for r in b if tradeable(r, OI_PRIMARY)]
        sa, sk = day_stat(b), day_stat(k)
        fa = (f"{sa['mean']:+7.2f} {sa['t']:+5.2f} n={sa['n']:<6}"
              if sa and sa["t"] is not None else f"{'--':<20}")
        fk = (f"{sk['mean']:+7.2f} {sk['t']:+5.2f} n={sk['n']:<6}"
              if sk and sk["t"] is not None else f"{'--':<20}")
        print(f"    {lo:.2f}-{hi:.2f}    {fa:<34}{fk}")
    print()

    print("=== B. NET EDGE BY OPEN INTEREST, band 0.90-0.97 ===")
    print("    (does calibration improve monotonically as a book appears?)")
    band = [r for r in filled if 0.90 <= r["ask"] < 0.97]
    for lo, hi in OI_BANDS:
        sub = [r for r in band
               if lo <= (r["open_interest"] or 0) < hi
               and r["spread"] is not None and r["spread"] <= MAX_SPREAD]
        tag = f"oi {lo}-{hi}" if hi < 10 ** 9 else f"oi >= {lo}"
        line(tag, day_stat(sub))
    print()

    print("=== C. THE SPREAD-ONLY TEST, which the correction says is NOT enough ===")
    print("    (rows passing spread<=0.07 but holding NO open interest)")
    tight_empty = [r for r in band if r["spread"] is not None
                   and r["spread"] <= MAX_SPREAD
                   and (r["open_interest"] or 0) == 0]
    line("spread<=0.07 AND oi==0", day_stat(tight_empty))
    line("spread<=0.07 AND oi>=100",
         day_stat([r for r in band if tradeable(r, OI_PRIMARY)]))
    print()

    print("=== D. HOW MUCH OF THE CELL IS UNTRADEABLE, by side ===")
    for side in ("no", "yes"):
        b = [r for r in band if r["side"] == side]
        k = [r for r in b if tradeable(r, OI_PRIMARY)]
        z = [r for r in b if (r["open_interest"] or 0) == 0]
        if not b:
            continue
        print(f"  {side.upper():<4} cell rows={len(b):<6} tradeable={len(k):<5} "
              f"({len(k)/len(b):5.1%})   zero-OI={len(z):<6} ({len(z)/len(b):5.1%})")
    print()
    print("    NOTE: if the untradeable share differs by side, then the")
    print("    UNFILTERED side gap is partly a difference in how often each")
    print("    side is quoted into an empty book -- which is a composition")
    print("    effect of exactly the kind measure.py controls for.")


if __name__ == "__main__":
    main()
