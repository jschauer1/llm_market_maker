"""Aggregation gap — the executable-price and fee test the ticket deferred.

The ticket (tickets/new-theory/completed/2026-09-01-aggregation-gap.md)
names this as the likely killer and says to test it first:

    "The gap does not exceed fees plus the cost of holding both legs.
     This is the LIKELY killer and must be tested first."

Two things are measured here, both on the session board, no force:
 1. Whether KXHOUSEWINSTATE's ladder actually spans the support, i.e.
    whether E[Dem seats] is DETERMINED or merely BOUNDED.
 2. The gap at worst-case executable quotes, against the real fee cost
    of the multi-leg basket that would capture it.
"""
import sys, os, re, collections, statistics
sys.path.insert(0, os.path.abspath("."))
from tools.db import connect
from tools.board import get_board
from tools.sizing import fee_pts

COMPLETE = ["AL", "GA", "LA", "SC", "TN"]   # the ticket's own 5 complete-coverage states


def load():
    conn = connect()
    b = get_board(conn)                      # no force -- the floor owns that
    st, dist = collections.defaultdict(dict), collections.defaultdict(list)
    for m in b:
        if (m.series_ticker or "") == "KXHOUSEWINSTATE":
            mm = re.match(r"KXHOUSEWINSTATE-([A-Z]{2})D-([AE])(\d+)$", m.ticker)
            if mm:
                st[mm.group(1)][(mm.group(2), int(mm.group(3)))] = m
        elif (m.series_ticker or "") == "KXHOUSERACE" and m.ticker.endswith("-26-D"):
            mm = re.match(r"KXHOUSERACE-([A-Z]{2})(\d+)-26-D", m.ticker)
            if mm:
                dist[mm.group(1)].append(m)
    return st, dist


def main():
    st, dist = load()
    mid = lambda m: (m.yes_ask + m.yes_bid) / 2

    print("=== 1. IS E[seats] RECOVERABLE? ladder completeness per state ===")
    print(f"{'st':<4}{'ndist':>6}{'A-strikes':>12}{'E-strikes':>26}{'partition':>11}{'bound width':>13}")
    for s in sorted(st):
        n = len(dist[s])
        if not n:
            continue
        A = sorted(k for (t, k) in st[s] if t == "A")
        E = sorted(k for (t, k) in st[s] if t == "E")
        if not A:
            continue
        Ee = {k: m for (t, k), m in st[s].items() if t == "E"}
        Es = {k: m for (t, k), m in st[s].items() if t == "A"}
        amax = max(Es)
        psum = sum(mid(m) for m in Ee.values()) + mid(Es[amax])
        width = (n - (amax + 1)) * mid(Es[amax])
        print(f"{s:<4}{n:>6}{str(A):>12}{str(E):>26}{psum:>11.3f}{width:>13.3f}")

    print("\n=== 2. EXECUTABLE PRICES AND FEES, the ticket's 5 complete states ===")
    print(f"{'st':<4}{'legs':>5}{'gap_mid':>9}{'gap_worst':>11}{'fees_$':>9}{'net_worst':>11}{'net_mid':>9}")
    tot = []
    for s in COMPLETE:
        ds, ent = dist[s], st[s]
        legs = list(ds) + list(ent.values())
        Ee = {k: m for (t, k), m in ent.items() if t == "E"}
        Es = {k: m for (t, k), m in ent.items() if t == "A"}
        amax = max(Es)
        Eof = lambda px: sum(k * px(m) for k, m in Ee.items()) + (amax + 1) * px(Es[amax])
        gap_mid = sum(mid(m) for m in ds) - Eof(mid)
        # worst case: districts marked at BID, state expectation at ASK
        gap_worst = sum(m.yes_bid for m in ds) - Eof(lambda m: m.yes_ask)
        # ONE contract per leg -- a LOWER BOUND on the real basket, which needs
        # k contracts of each "exactly k" leg to replicate the seat count.
        fees = sum(fee_pts(m.yes_ask or 0.5) / 100.0 for m in legs)
        print(f"{s:<4}{len(legs):>5}{gap_mid:>9.3f}{gap_worst:>11.3f}{fees:>9.3f}"
              f"{gap_worst-fees:>11.3f}{gap_mid-fees:>9.3f}")
        tot.append((gap_mid, gap_worst, fees, len(legs)))
    print(f"\nmean  gap_mid {statistics.mean(t[0] for t in tot):+.3f}   "
          f"gap_worst {statistics.mean(t[1] for t in tot):+.3f}   "
          f"fees ${statistics.mean(t[2] for t in tot):.3f}   "
          f"legs {statistics.mean(t[3] for t in tot):.1f}")
    print(f"mean net at worst-case executable prices: "
          f"{statistics.mean(t[1]-t[2] for t in tot):+.3f}")
    print(f"THE TICKET'S OWN worst-case figure was +0.073 seats; measured basket "
          f"fees are ${statistics.mean(t[2] for t in tot):.3f}.")


if __name__ == "__main__":
    main()
