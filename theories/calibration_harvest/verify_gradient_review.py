"""Independently verify the peer review of the politics gradient.

Recomputes, from the ledger, every number in llm-market-identifier-4f's
critique: the adjacent paired steps, all three split points, and the
day-level regression of edge on horizon-bin rank. Nothing here is taken
on trust.
"""
import json
import statistics
import sys

sys.path.insert(0, r"c:\Users\jbs00\OneDrive\Documents\Current_Work\LLM_market_identifier")

from tools import db  # noqa: E402

RUN = "backtest-2026-08-29-calharvest-politics"
HORIZONS = ["<=2d", "2d-1w", "1w-1mo", "1mo+"]

conn = db.connect()
rows = []
for r in conn.execute("""
    SELECT a.extra_json, a.entry_price, o.outcome, s.result,
           SUBSTR(COALESCE(s.resolved_at,''),1,10) AS day
    FROM opportunity_attempts a JOIN opportunities o ON o.id=a.opportunity_id
    JOIN settlements s ON s.kalshi_ticker=o.kalshi_ticker
    WHERE o.theory_id='calibration_harvest' AND a.run_id=?""", (RUN,)):
    e = json.loads(r["extra_json"] or "{}")
    if not e.get("cell") or not r["day"]:
        continue
    rows.append((e["horizon_bin"], r["day"],
                 1.0 if r["outcome"] == r["result"] else 0.0,
                 r["entry_price"]))


def by_day(sel):
    acc = {}
    for _h, day, won, ask in sel:
        a = acc.setdefault(day, [0.0, 0.0, 0])
        a[0] += won
        a[1] += ask
        a[2] += 1
    return {d: (w / n - a / n) * 100.0 for d, (w, a, n) in acc.items()}


def paired(a_bins, b_bins):
    """mean/SE/t of (A - B) over settlement days holding both."""
    A = by_day([r for r in rows if r[0] in a_bins])
    B = by_day([r for r in rows if r[0] in b_bins])
    both = sorted(set(A) & set(B))
    d = [A[k] - B[k] for k in both]
    m = statistics.mean(d)
    se = statistics.stdev(d) / len(d) ** 0.5
    return m, se, m / se, len(d), sum(1 for x in d if x > 0)


print("ADJACENT PAIRED STEPS (their claim: flat, one jump, flat)")
for lo, hi in zip(HORIZONS, HORIZONS[1:]):
    m, se, t, n, pos = paired((hi,), (lo,))
    flag = "JUMP" if abs(t) > 2 else "ns"
    print(f"  {hi:8s} - {lo:8s}: {m:+6.2f}  SE {se:4.2f}  t {t:+5.2f}  "
          f"days {n:3d}  {flag}")

print("\nALL THREE SPLIT POINTS (their claim: t=3.50 is the max of three)")
for i in range(1, 4):
    long_bins, short_bins = tuple(HORIZONS[i:]), tuple(HORIZONS[:i])
    m, se, t, n, pos = paired(long_bins, short_bins)
    mark = "  <-- I REPORTED THIS" if i == 2 else ""
    print(f"  split after {HORIZONS[i-1]:8s}: {m:+6.2f}  SE {se:4.2f}  "
          f"t {t:+5.2f}  days {n:3d}{mark}")

print("\nDAY-LEVEL REGRESSION on horizon-bin rank (their proposed estimator)")
rank = {h: i for i, h in enumerate(HORIZONS)}
per_day = {}
for h, day, won, ask in rows:
    per_day.setdefault(day, {}).setdefault(h, [0.0, 0.0, 0])
    a = per_day[day][h]
    a[0] += won
    a[1] += ask
    a[2] += 1
slopes = []
for day, hs in per_day.items():
    if len(hs) < 2:
        continue
    xs = [rank[h] for h in hs]
    ys = [(w / n - a / n) * 100.0 for w, a, n in hs.values()]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        continue
    slopes.append(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom)
m = statistics.mean(slopes)
se = statistics.stdev(slopes) / len(slopes) ** 0.5
print(f"  {m:+.2f} pts/bin  SE {se:.2f}  t {m / se:+.2f}  "
      f"days {len(slopes)}  positive {sum(1 for s in slopes if s > 0)}"
      f"/{len(slopes)}")

print("\nMY OWN PRE-REGISTERED BAR: was the four-way ordering right?")
means = {}
for h in HORIZONS:
    de = list(by_day([r for r in rows if r[0] == h]).values())
    means[h] = statistics.mean(de)
ordered = [means[h] for h in HORIZONS]
print("  ", " -> ".join(f"{v:+.2f}" for v in ordered))
print(f"   required 1mo+ > 1w-1mo > 2d-1w > <=2d : "
      f"{all(b > a for a, b in zip(ordered, ordered[1:]))}")
