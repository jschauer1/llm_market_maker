"""Accumulation decay — the pre-registered measurement. See PREREG.md.

PRIMARY   price path: cost to buy the favorite, by elapsed-fraction bucket.
SECONDARY calibration: net edge of buying the favorite, day-clustered.
"""
import json, sys, math, statistics, datetime as dt, collections
sys.path.insert(0, ".")
from tools.sizing import fee_pts

SRC = sys.argv[1]
BUCKETS = [(-9e9, 0.0, "pre-window"), (0.0, 0.25, "0-25%"), (0.25, 0.5, "25-50%"),
           (0.5, 0.75, "50-75%"), (0.75, 1.0, "75-100%"), (1.0, 9e9, "POST (determined)")]
OI_MIN, SPREAD_MAX = 100.0, 0.07


def ts(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def observations(path):
    """One row per (market, bucket): the candle nearest the bucket midpoint."""
    out = []
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        if not d["candles"]:
            continue
        w0, w1 = ts(d["w0"]), ts(d["w1"])
        span = w1 - w0
        won_yes = d["result"] == "yes"
        event = d["ticker"].split("-")[1]
        for lo, hi, name in BUCKETS:
            mid = (max(lo, -0.5) + min(hi, 1.5)) / 2
            cands = []
            for c in d["candles"]:
                f = (c["end_ts"] - w0) / span
                if lo <= f < hi and c["yes_ask_close"] is not None and c["yes_bid_close"] is not None:
                    cands.append((abs(f - mid), f, c))
            if not cands:
                continue
            _, f, c = min(cands, key=lambda x: x[0])
            ya, yb = c["yes_ask_close"], c["yes_bid_close"]
            spread = ya - yb
            m = (ya + yb) / 2
            fav_yes = m > 0.5
            cost = ya if fav_yes else 1.0 - yb
            fav_won = won_yes if fav_yes else not won_yes
            out.append(dict(
                ticker=d["ticker"], event=event, day=d["resolved_at"][:10], bucket=name,
                f=f, cost=cost, spread=spread, oi=c["open_interest"] or 0.0,
                fav_yes=fav_yes, fav_won=fav_won,
                net=(100.0 * (1.0 if fav_won else 0.0) - 100.0 * cost) - fee_pts(cost),
            ))
    return out


def clustered(rows, key):
    """Mean and t, clustering on `key` (equal weight per cluster)."""
    g = collections.defaultdict(list)
    for r in rows:
        g[r[key]].append(r["net"])
    means = [statistics.mean(v) for v in g.values()]
    if len(means) < 2:
        return (statistics.mean(means) if means else float("nan")), float("nan"), len(means)
    mu = statistics.mean(means)
    se = statistics.stdev(means) / math.sqrt(len(means))
    return mu, (mu / se if se else float("nan")), len(means)


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def report(rows, label):
    print(f"\n{'='*78}\n{label}   (n={len(rows)} observations)\n{'='*78}")
    print(f"{'bucket':<20} {'n':>4} {'mkts':>5} {'evts':>5} | "
          f"{'cost p25':>8} {'p50':>6} {'p75':>6} {'p90':>6} | "
          f"{'NET':>7} {'t':>6} {'days':>5}")
    for _, _, name in BUCKETS:
        b = [r for r in rows if r["bucket"] == name]
        if not b:
            print(f"{name:<20} {'-':>4}")
            continue
        costs = [r["cost"] for r in b]
        mu, t, nd = clustered(b, "day")
        print(f"{name:<20} {len(b):>4} {len({r['ticker'] for r in b}):>5} "
              f"{len({r['event'] for r in b}):>5} | "
              f"{q(costs,.25):>8.3f} {q(costs,.5):>6.3f} {q(costs,.75):>6.3f} "
              f"{q(costs,.9):>6.3f} | {mu:>7.2f} {t:>6.2f} {nd:>5}")


rows = observations(SRC)
liquid = [r for r in rows if r["oi"] >= OI_MIN and r["spread"] <= SPREAD_MAX]
report(rows, "UNFILTERED (reported beside, never the headline)")
report(liquid, f"PRIMARY: LIQUID (open_interest >= {OI_MIN:.0f}, spread <= {SPREAD_MAX})")

post = [r for r in liquid if r["bucket"] == "POST (determined)"]
print(f"\n--- decision bucket: POST, liquid ---")
print(f"observations {len(post)}  markets {len({r['ticker'] for r in post})}  "
      f"events {len({r['event'] for r in post})}  days {len({r['day'] for r in post})}")
if post:
    costs = [r["cost"] for r in post]
    print(f"cost to buy favorite: p10 {q(costs,.10):.3f}  p25 {q(costs,.25):.3f}  "
          f"median {q(costs,.5):.3f}  p75 {q(costs,.75):.3f}  mean {statistics.mean(costs):.3f}")
    print(f"share priced >= 0.97 : {sum(1 for c in costs if c >= 0.97)/len(costs):.1%}")
    print(f"favorite win rate    : {sum(1 for r in post if r['fav_won'])/len(post):.1%}")
    mu, t, nd = clustered(post, "day")
    mue, te, ne = clustered(post, "event")
    print(f"net edge, day-clustered   {mu:+.2f} pts  t={t:+.2f}  ({nd} days)")
    print(f"net edge, event-clustered {mue:+.2f} pts  t={te:+.2f}  ({ne} events)")
