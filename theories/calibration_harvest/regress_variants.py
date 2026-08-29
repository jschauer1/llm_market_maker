"""Why does the peer's regression say +3.14/t=2.68 and mine +0.50/t=0.26?

Same data, same stated estimator ("day-level regression of edge on
horizon-bin rank"), very different answers -- so the difference is in an
unstated construction choice. Enumerate the plausible ones and see which
reproduces 42 days / +3.14 / SE 1.17 / 26 of 42 positive.
"""
import json
import statistics
import sys

sys.path.insert(0, r"c:\Users\jbs00\OneDrive\Documents\Current_Work\LLM_market_identifier")

from tools import db  # noqa: E402

RUN = "backtest-2026-08-29-calharvest-politics"
HORIZONS = ["<=2d", "2d-1w", "1w-1mo", "1mo+"]
RANK = {h: i for i, h in enumerate(HORIZONS)}

conn = db.connect()
raw = []
for r in conn.execute("""
    SELECT a.extra_json, a.entry_price, o.outcome, s.result,
           SUBSTR(COALESCE(s.resolved_at,''),1,10) AS day
    FROM opportunity_attempts a JOIN opportunities o ON o.id=a.opportunity_id
    JOIN settlements s ON s.kalshi_ticker=o.kalshi_ticker
    WHERE o.theory_id='calibration_harvest' AND a.run_id=?""", (RUN,)):
    e = json.loads(r["extra_json"] or "{}")
    if not e.get("cell") or not r["day"]:
        continue
    raw.append((e["horizon_bin"], r["day"],
                1.0 if r["outcome"] == r["result"] else 0.0,
                r["entry_price"]))

# day -> horizon -> [wins, ask_sum, n]
per_day = {}
for h, day, won, ask in raw:
    per_day.setdefault(day, {}).setdefault(h, [0.0, 0.0, 0])
    a = per_day[day][h]
    a[0] += won
    a[1] += ask
    a[2] += 1


def day_slope(hs, weighted=False):
    xs, ys, ws = [], [], []
    for h, (w, a, n) in hs.items():
        xs.append(RANK[h])
        ys.append((w / n - a / n) * 100.0)
        ws.append(n)
    if not weighted:
        ws = [1.0] * len(xs)
    tw = sum(ws)
    mx = sum(x * w for x, w in zip(xs, ws)) / tw
    my = sum(y * w for y, w in zip(ys, ws)) / tw
    den = sum(w * (x - mx) ** 2 for x, w in zip(xs, ws))
    if den == 0:
        return None
    return sum(w * (x - mx) * (y - my)
               for x, y, w in zip(xs, ys, ws)) / den


def report(label, slopes):
    if len(slopes) < 3:
        print(f"{label:44s} too few days ({len(slopes)})")
        return
    m = statistics.mean(slopes)
    se = statistics.stdev(slopes) / len(slopes) ** 0.5
    pos = sum(1 for s in slopes if s > 0)
    hit = " <== MATCHES PEER" if (abs(m - 3.14) < 0.15
                                  and len(slopes) == 42) else ""
    print(f"{label:44s} {m:+6.2f}  SE {se:4.2f}  t {m/se:+5.2f}  "
          f"days {len(slopes):3d}  pos {pos}/{len(slopes)}{hit}")


print("variants of 'day-level regression of edge on horizon-bin rank':\n")
for min_bins in (2, 3, 4):
    for weighted in (False, True):
        slopes = []
        for day, hs in per_day.items():
            if len(hs) < min_bins:
                continue
            s = day_slope(hs, weighted)
            if s is not None:
                slopes.append(s)
        report(f"  >={min_bins} bins present, "
               f"{'obs-weighted' if weighted else 'unweighted'}", slopes)

# Pooled OLS over all (day, bin) cells, ignoring day structure entirely.
xs, ys = [], []
for day, hs in per_day.items():
    for h, (w, a, n) in hs.items():
        xs.append(RANK[h])
        ys.append((w / n - a / n) * 100.0)
mx, my = statistics.mean(xs), statistics.mean(ys)
den = sum((x - mx) ** 2 for x in xs)
slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
resid = [y - (my + slope * (x - mx)) for x, y in zip(xs, ys)]
s2 = sum(r * r for r in resid) / (len(xs) - 2)
se = (s2 / den) ** 0.5
print(f"\n  pooled OLS over all day-bin cells (no day clustering):"
      f"      {slope:+6.2f}  SE {se:4.2f}  t {slope/se:+5.2f}  "
      f"cells {len(xs)}")

print(f"\n  days with >=2 bins: "
      f"{sum(1 for hs in per_day.values() if len(hs) >= 2)}")
print(f"  days with >=3 bins: "
      f"{sum(1 for hs in per_day.values() if len(hs) >= 3)}")
print(f"  days with all 4   : "
      f"{sum(1 for hs in per_day.values() if len(hs) == 4)}")
