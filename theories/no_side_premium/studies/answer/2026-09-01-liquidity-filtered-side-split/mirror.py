"""Price the mirrored leg, and separate the market's error from the toll.

Reproduces STUDY.md's "Addendum, same session: the successor thesis was
priced, and it is not a trade either" -- the run that killed idea 36
(`mid-band-favorite-fade`) fifteen minutes after it was filed.

WHY THIS FILE EXISTS. The addendum's numbers were first produced ad hoc.
A result this repo quotes must be reconstructible from disk by a session
that never saw the one that made it, so the arithmetic is checked in.

THE POINT IN ONE LINE. The favorite's ask and the underdog's ask sum to
1 + spread, not 1, because taking either side crosses the book. So the
two legs are bound by an IDENTITY rather than by symmetry:

    fav_net + dog_net  ==  -(spread + fee_fav + fee_dog)

which means a one-sided net edge of -N does NOT imply +N on the other
side. It implies -(round_trip - N), and both sides lose whenever the
mispricing is smaller than the round trip. That identity is asserted at
the end of this script rather than merely printed, so the file fails
loudly if the arithmetic is ever changed to something that violates it.

    python theories/no_side_premium/studies/answer/2026-09-01-liquidity-filtered-side-split/mirror.py <copy.db>
"""

from __future__ import annotations

import collections
import sqlite3
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure import OI_PRIMARY, fee_pts, tradeable  # noqa: E402

BANDS = ((0.50, 0.65), (0.65, 0.80), (0.50, 0.80),
         (0.80, 0.90), (0.90, 0.97), (0.97, 1.01))


def underdog_ask(r) -> float:
    """What you pay for the other side.

    favorite_bid = favorite_ask - spread, and the underdog's ask is the
    complement of the favorite's BID -- not of its ask. Getting this
    wrong is worth the whole spread, which is how idea 36 looked like a
    +3.90 trade when it was a -1.04 one.
    """
    return 1.0 - r["ask"] + r["spread"]


def round_trip(r) -> float:
    """Spread plus a fee on each leg, in points."""
    return r["spread"] * 100 + fee_pts(r["ask"]) + fee_pts(underdog_ask(r))


def day_agg(rows, value):
    """Day-clustered mean/SE of a per-row quantity."""
    by: dict[str, list] = collections.defaultdict(list)
    for r in rows:
        by[r["close_time"][:10]].append(r)
    vals = [statistics.mean([value(r) for r in rs]) for rs in by.values()]
    mean = statistics.mean(vals)
    se = statistics.stdev(vals) / len(vals) ** 0.5 if len(vals) > 1 else None
    return mean, se, (mean / se if se else None), len(vals), sum(v > 0 for v in vals)


def fav_net(r):
    return (r["won"] - r["ask"]) * 100 - fee_pts(r["ask"])


def dog_net(r):
    a = underdog_ask(r)
    return ((1 - r["won"]) - a) * 100 - fee_pts(a)


def gross_at_mid(r):
    """The market's error, gross of every cost of acting on it."""
    return (r["won"] - (r["ask"] - r["spread"] / 2)) * 100


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path or not Path(path).exists():
        sys.exit("usage: mirror.py <path to a COPY of collect.db>")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM obs WHERE spread IS NOT NULL")]
    print(f"backfilled rows: {len(rows)} over "
          f"{len({r['series_ticker'] for r in rows})} series\n")

    print("=== 1. BOTH LEGS, priced off the side you would actually pay ===")
    print("    naive mirror = -1 x the favorite leg. It is WRONG by the round trip.")
    print(f"    {'fav ask':<14}{'BUY FAVORITE':>22}{'naive':>10}"
          f"{'BUY UNDERDOG':>22}{'round trip':>12}")
    for lo, hi in BANDS:
        keep = [r for r in rows if lo <= r["ask"] < hi
                and tradeable(r, OI_PRIMARY)]
        if len(keep) < 30:
            continue
        fm, _, ft, _, _ = day_agg(keep, fav_net)
        dm, _, dt, _, _ = day_agg(keep, dog_net)
        rt, _, _, _, _ = day_agg(keep, round_trip)
        print(f"    {lo:.2f}-{hi:.2f}      {fm:+7.2f} (t={ft:+5.2f}) "
              f"{-fm:+9.2f}   {dm:+7.2f} (t={dt:+5.2f}) {rt:11.2f}")

    print()
    print("=== 2. THE MARKET'S ERROR vs THE TOLL FOR ACTING ON IT ===")
    print("    mid = ask - spread/2, gross of fees. If |gross| < round trip,")
    print("    the mispricing is real but unreachable from either side.")
    for lo, hi in BANDS:
        keep = [r for r in rows if lo <= r["ask"] < hi
                and tradeable(r, OI_PRIMARY)]
        if len(keep) < 30:
            continue
        gm, _, gt, nd, _ = day_agg(keep, gross_at_mid)
        rt, _, _, _, _ = day_agg(keep, round_trip)
        print(f"    {lo:.2f}-{hi:.2f}  n={len(keep):<5} days={nd:<3} "
              f"GROSS@mid={gm:+6.2f} (t={gt:+5.2f})   round trip={rt:5.2f}")

    print()
    print("=== 3. THE IDENTITY, asserted rather than printed ===")
    band = [r for r in rows if 0.50 <= r["ask"] < 0.80
            and tradeable(r, OI_PRIMARY)]
    f_, _, _, _, _ = day_agg(band, fav_net)
    d_, _, _, _, _ = day_agg(band, dog_net)
    c_, _, _, _, _ = day_agg(band, round_trip)
    print(f"    fav_net + dog_net = {f_:+.4f} + {d_:+.4f} = {f_ + d_:+.4f}")
    print(f"    -(round trip)     = {-c_:+.4f}")
    assert abs((f_ + d_) + c_) < 1e-9, (
        "fav_net + dog_net must equal -(spread + both fees) exactly; "
        "if this fails the book-side arithmetic above is wrong")
    print("    OK -- agreement to 1e-9.")
    print()
    print("    So: a one-sided net edge of -N does NOT imply +N on the other")
    print("    side. It implies -(round_trip - N), and BOTH SIDES LOSE")
    print("    whenever the mispricing is smaller than the round trip.")


if __name__ == "__main__":
    main()
