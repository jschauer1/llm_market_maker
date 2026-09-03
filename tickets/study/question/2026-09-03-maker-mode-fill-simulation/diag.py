"""Diagnostics: the mirror check, the staleness limit, and the tradeable slice.

Three things the pre-registration committed to reporting, plus the one
question the primary result immediately raises.

1. The BUY-NO mirror (pre-declared secondary 3).
2. The realized quote-lag distribution and its relationship to the
   reconstructed spread ("Known limits" in STUDY.md).
3. Concentration of the wide-spread cell, so the headline is not one
   corner.
4. The slice this repo can actually trade: `theories/insider_bias/
   screen.py` pins `spread <= 0.07`, and `taker_flow` filters the same
   way. The primary population is not that population.

    python tickets/study/question/2026-09-03-maker-mode-fill-simulation/diag.py
"""

from __future__ import annotations

import importlib.util
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _name, _file in (("mm_sim", "sim.py"), ("mm_run", "run.py")):
    _spec = importlib.util.spec_from_file_location(_name, _HERE / _file)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _mod
    _spec.loader.exec_module(_mod)
import mm_run as R  # noqa: E402
import mm_sim as sim  # noqa: E402

rows = [json.loads(l) for l in (_HERE / "data" / "markets.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()]
for r in rows:
    r["d_net"], r["d_gross"] = R.yes_arms(r)
    r["dno_net"], r["dno_gross"] = R.no_arms(r)
    r["stale"] = max(r["bid_age_h"], r["ask_age_h"])

print("=" * 78)
print("1. MIRROR CHECK (pre-declared secondary 3): buy NO instead of YES")
print("=" * 78)
print("   Capture on a fill is the same spread - 1c by construction, so a")
print("   difference between the sides is DRIFT on the unfilled arm, not")
print("   spread capture.")
print()
print(R.line("YES (primary)", R.day_clustered(rows, lambda r: r["d_net"])))
print(R.line("NO  (mirror)", R.day_clustered(rows, lambda r: r["dno_net"])))
n_no = sum(1 for r in rows if r["filled_no"])
print(f"   fill rate  YES {sum(1 for r in rows if r['filled'])/len(rows):.3f}"
      f"   NO {n_no/len(rows):.3f}")
print()

print("=" * 78)
print("2. THE INSTRUMENT: is a wide reconstructed spread a real spread?")
print("=" * 78)
print("   bid_hat and ask_hat are LAST-TOUCH prices. If the two sides last")
print("   printed far apart in time, the gap between them is partly the")
print("   price having MOVED, not a spread anyone could have crossed.")
print()
print(f"   {'spread cell':<14} {'n':>5} {'median lag h':>13} {'p90 lag h':>11} "
      f"{'median prints':>14}")
for label, lo, hi in (("2-3c", 0.02, 0.035), ("4-6c", 0.035, 0.065),
                      (">=7c", 0.065, 9.0)):
    sub = [r for r in rows if lo <= r["spread_t"] < hi]
    if sub:
        lags = sorted(r["stale"] for r in sub)
        pr = sorted(r["n_prints"] for r in sub)
        print(f"   {label:<14} {len(sub):>5} {statistics.median(lags):>13.2f} "
              f"{lags[int(0.9*len(lags))]:>11.2f} {statistics.median(pr):>14.0f}")
print()
print("   D by quote freshness (both sides), all spreads pooled:")
for label, lo, hi in (("both < 2h", 0.0, 2.0), ("2-12h", 2.0, 12.0),
                      ("12-72h", 12.0, 72.1)):
    sub = [r for r in rows if lo <= r["stale"] < hi]
    if len(sub) > 20:
        print("   " + R.line(label, R.day_clustered(sub, lambda r: r["d_net"])))
print()

print("=" * 78)
print("3. IS THE WIDE-SPREAD CELL ONE CORNER?")
print("=" * 78)
wide = [r for r in rows if r["spread_t"] >= 0.065]
top = Counter(r["series"] for r in wide).most_common(5)
print(f"   n={len(wide)}  series={len({r['series'] for r in wide})}  "
      f"events={len({r['event'] for r in wide})}  "
      f"days={len({r['day'] for r in wide})}")
print(f"   top series: {', '.join(f'{s} {c}({c/len(wide):.0%})' for s, c in top)}")
worst = None
for s in {r["series"] for r in wide}:
    rest = [r for r in wide if r["series"] != s]
    if len({r["day"] for r in rest}) >= 5:
        st = R.day_clustered(rest, lambda r: r["d_net"])
        if worst is None or st["mean"] < worst[1]["mean"]:
            worst = (s, st)
if worst:
    print("   " + R.line(f"leave-one-series-out worst ({worst[0]})", worst[1]))
print()

print("=" * 78)
print("4. THE SLICE THIS REPO CAN ACTUALLY TRADE")
print("=" * 78)
print("   theories/insider_bias/screen.py pins spread <= 0.07; taker_flow")
print("   screens the same way. That filter is upstream of every candidate")
print("   maker mode would ever be applied to.")
print()
tradeable = [r for r in rows if r["spread_t"] <= 0.07]
excluded = [r for r in rows if r["spread_t"] > 0.07]
print("   " + R.line("spread <= 7c  [THE REAL POPULATION]",
                     R.day_clustered(tradeable, lambda r: r["d_net"])))
print("   " + R.line("spread >  7c  (screened out anyway)",
                     R.day_clustered(excluded, lambda r: r["d_net"])))
print()
print(f"   share of the primary population that survives the filter: "
      f"{len(tradeable)}/{len(rows)} = {len(tradeable)/len(rows):.1%}")
print()
print("   and inside it, by price band:")
for lo, hi in ((0.02, 0.20), (0.20, 0.50), (0.50, 0.80), (0.80, 0.981)):
    sub = [r for r in tradeable if lo <= r["ask_t"] < hi]
    if len(sub) > 20:
        print("   " + R.line(f"ask [{lo:.2f},{min(hi,0.98):.2f}]",
                             R.day_clustered(sub, lambda r: r["d_net"])))
print()
print("   the favorite band this repo's screens actually bet (0.65-0.97):")
fav = [r for r in tradeable if 0.65 <= r["ask_t"] <= 0.97]
if fav:
    print("   " + R.line("spread<=7c AND ask 0.65-0.97",
                         R.day_clustered(fav, lambda r: r["d_net"])))
    print(f"   fill rate in that slice: "
          f"{sum(1 for r in fav if r['filled'])/len(fav):.3f}")
