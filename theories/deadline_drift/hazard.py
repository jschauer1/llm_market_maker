"""Reproduce the hazard estimate from disk, under both anchors AND both
sides of the book.

Two corrections are baked in here, and both are runnable rather than
asserted -- each is a row you can see next to the number it replaced.

**Correction 1 (2026-08-29): the time anchor.** On a "does X happen by D"
market, actual close is a FUNCTION OF THE OUTCOME -- a NO market runs to
its deadline, a YES market stops the moment the event fires (measured:
median 210 days early, 32/34). Anchoring on it puts the two arms on
different clocks and measures "prices rise before events happen".

**Correction 2 (2026-09-01): the side of the book.** This theory BUYS NO.
The price a NO buyer pays is `no_ask = 1 - yes_bid`, so the breakeven is
`yes_bid`, not `yes_ask`. Measuring the gap against `yes_ask` credits the
strategy with the entire bid-ask spread -- which on this population has a
median of 5-6 points in the entry band, larger than the edge that was
being claimed. CLAUDE.md's "entry prices are the ask you would actually
pay" binds here through the far side of the book, which is easy to miss:
the optimistic field is the one named "ask".

**Why dropping early-YES markets is not survivorship bias.** Conditioning
on "still open at deadline - h" is the hazard-analysis *at-risk set*: a
market that already resolved YES is not available to bet at that moment,
so excluding it is exactly what makes P(YES) the right conditional. The
number this produces answers "given I can still buy NO here, how often
does YES come in?", which is the only question a bettor can act on.

    python -m theories.deadline_drift.hazard
"""
from __future__ import annotations

import json
import math
import re
import statistics
from pathlib import Path

from theories.deadline_drift.screen import in_allowlist

DATA = Path(__file__).parent / "data"

LATE_WINDOW_DAYS = 21
ENTRY_BAND = (0.05, 0.60)
FEE_RATE = 0.07

#: Rules-text exclusions from the round-4 classifier of the audit study
#: `theories/deadline_drift/studies/answer/2026-08-29-deadline-drift-classifier-audit`
#: -- its `classifier.py` was deleted with the investigation on 2026-09-03
#: and reads back at `git show 38028e6:<that path>/classifier.py`. Inlined
#: here, so this script reads nothing outside the theory folder. A
#: market matching any of these is not a per-subject hazard, and the
#: strata table below reports each as its own population rather than
#: silently dropping it -- a code gate must always say what it removed.
THRESHOLD = re.compile(
    r"\bis (?:above|below|at or above|at or below|between)\b"
    r"|\bcloses? (?:above|below)\b|\bhigher than\b|\blower than\b"
    r"|\brise[s]? (?:more|less) than\b|\bprice .{0,40}\b(?:above|below)\b"
    r"|\bthe number of\b"
    r"|\b(?:has|have|is|are)\s+(?:above|below|at least|at most|exactly)\s+\d"
    r"|\bif above \d|\bachieves? an? (?:accuracy|score)\b|\bscores? at least\b",
    re.IGNORECASE)
SCHEDULED = re.compile(
    r"originally scheduled for"
    r"|\bprofessional .{0,60}(?:soccer|basketball|football|cricket|hockey"
    r"|tennis|baseball) (?:game|match)\b|\bearnings call\b"
    r"|Consumer Price Index|Producer Price Index"
    r"|Carbon Arc|OpenRouter|\bMetascore\b"
    r"|\bwins? (?:a|the) (?:tennis major|major|grand slam|championship"
    r"|tournament)\b|\bwins? the .{0,40}(?:Open|Championship|Cup|Series)\b",
    re.IGNORECASE)
MULTI_DESTINATION = re.compile(
    r"\bnext (?:team|club|franchise) is\b|\bnext (?:team|club) is the\b"
    r"|\bis the first\b.{0,80}\bto (?:announce|sell|declare|reach|leave|do so)\b"
    r"|\bis the first (?:person|such subject)\b"
    r"|\bis appointed, elected, named, designated\b"
    r"|\bis,? or is announced to be in the future,? the first\b"
    r"|\band is the first such subject\b"
    r"|\bbecomes .{0,50}\bas a result of government formation\b"
    r"|\bthe 51st state is\b|\bbacks a challenger to\b",
    re.IGNORECASE)


def load() -> tuple[dict, dict, dict]:
    anchors = json.loads((DATA / "anchors.json").read_text(encoding="utf-8"))
    candles = json.loads((DATA / "candles.json").read_text(encoding="utf-8"))
    raw = json.loads((DATA / "settled_raw.json").read_text(encoding="utf-8"))
    rules = {m["ticker"]: (m.get("rules_primary") or "")
             for v in raw.values() if isinstance(v, list) for m in v}
    return anchors, {k: v for k, v in candles.items() if isinstance(v, list)}, rules


def event_map() -> dict:
    """ticker -> event_ticker, the clustering unit for the SE."""
    raw = json.loads((DATA / "settled_raw.json").read_text(encoding="utf-8"))
    return {m["ticker"]: m.get("event_ticker")
            for v in raw.values() if isinstance(v, list) for m in v}


def market_volume() -> dict:
    """Lifetime volume per settled market.

    `screen.py`'s MIN_VOLUME floor is a LIFETIME volume on the market, not
    the volume of one day -- so reproducing the screen with a candle's
    daily `volume` would apply a filter ~20x tighter than the one the
    theory ships.
    """
    raw = json.loads((DATA / "settled_raw.json").read_text(encoding="utf-8"))
    return {m["ticker"]: float(m.get("volume_fp") or 0.0)
            for v in raw.values() if isinstance(v, list) for m in v}


def stratum(rules_text: str) -> str:
    """Which population a settled market belongs to, from its rules alone."""
    if THRESHOLD.search(rules_text):
        return "threshold"
    if SCHEDULED.search(rules_text):
        return "scheduled"
    if MULTI_DESTINATION.search(rules_text):
        return "multi_destination"
    return "hazard"


#: A NO market in a per-subject hazard family runs to its deadline; a NO
#: market in a "which branch" family dies the moment a SIBLING resolves
#: YES.
#:
#: The separation is real but ASYMMETRIC, and the first reading of it was
#: wrong. On a partial capture (~200 multi-destination NO markets) the
#: split looked near-perfect at 98.0% vs 0.0%; at ~525 it is **43.4% vs
#: 0.0%**. The 98% was an artifact of the walk being alphabetical, so the
#: early series were not a random sample of families -- a partial capture
#: is not a small capture, it is a BIASED one, and no number should be
#: quoted from one without saying so.
#:
#: What survives is one-directional and still useful: an early NO close
#: nearly implies a branch family (the audited allowlist is 0/78), but a
#: late NO close does NOT imply a hazard family, since branch families run
#: to the deadline whenever no sibling wins in time. So this detects
#: contamination it finds; it cannot certify a population clean. Run
#: `main()` for the current numbers rather than trusting these.
BRANCH_EARLY_SHARE = 0.5
EARLY_DAYS = 3.0


def branch_families(anchors: dict, *, min_no: int = 3) -> set[str]:
    """Series that settle like "which branch" families, not hazards.

    **This is a cleaning tool, not a screen, and the distinction is load
    bearing.** It reads settlement behaviour, so it cannot classify a
    series that has not settled anything yet and is useless live. It is
    also deliberately applied at the SERIES level: filtering individual
    markets by their own early close would condition on the outcome (an
    early close is overwhelmingly a NO), which would bias P(YES) upward
    and manufacture the very result it is meant to test. A family's
    settlement pattern is a structural fact about how the family is
    built; one market's is a fact about how that market came out.
    """
    per: dict[str, list[bool]] = {}
    for a in anchors.values():
        if a.get("result") != "no" or a.get("closed_early_days") is None:
            continue
        per.setdefault(a.get("series") or "", []).append(
            a["closed_early_days"] > EARLY_DAYS)
    return {s for s, v in per.items()
            if len(v) >= min_no and sum(v) / len(v) > BRANCH_EARLY_SHARE}


def partition_families(anchors: dict, events: dict, *, min_legs: int = 3,
                       min_events: int = 2) -> set[str]:
    """Series whose settled events pay exactly one winner -- partitions.

    Sharper than `branch_families` and it catches what that one misses.
    `KXBIGBROTHERELIMINATION` is the worked example: 8 events of 11-17
    legs, EXACTLY ONE YES EACH ("which houseguest goes this week"), no
    early closes at all because an elimination resolves on schedule. The
    rules-text regex misses it, Kalshi's `mutually_exclusive` flag is not
    on the settled payload, and the early-close tell is blind to it -- but
    the settled outcomes say it outright.

    Same series-level discipline as `branch_families`, and the same
    limits: it reads settlement, so it cleans history and cannot screen a
    live board. A series counts when its multi-leg settled events pay one
    winner apiece.
    """
    per_event: dict[str, list[str]] = {}
    ev_series: dict[str, str] = {}
    for tk, a in anchors.items():
        ev = events.get(tk)
        if not ev:
            continue
        per_event.setdefault(ev, []).append(a.get("result"))
        ev_series[ev] = a.get("series") or ""
    hits: dict[str, list[bool]] = {}
    for ev, res in per_event.items():
        if len(res) < min_legs:
            continue
        hits.setdefault(ev_series[ev], []).append(res.count("yes") == 1)
    # A share rather than `all`: an event whose legs partly fall outside
    # the 60-day archive window can show zero winners simply because the
    # winning leg was not captured. KXBIGBROTHERELIMINATION is 7-of-8
    # one-winner events for exactly that reason, and `all` misses it.
    return {s for s, v in hits.items()
            if len(v) >= min_events and sum(v) / len(v) >= 0.6}


def observe(rows, anchor_row, *, side, anchor="days_to_deadline",
            dlo=0, dhi=LATE_WINDOW_DAYS, band=ENTRY_BAND,
            max_spread=None, min_volume=None, min_oi=None, entry="mean",
            return_row=False):
    """One market -> (price paid against, resolved YES) or None.

    `side` is "bid" (what a NO buyer's breakeven actually is) or "ask"
    (the optimistic view kept so correction 2 stays reproducible).

    `entry` is "mean" (average over every qualifying day in the window --
    i.e. "enter on a day drawn at random from the window") or "first"
    (the earliest qualifying day, which is what the live screen would
    actually do: it fires the first time a market enters the horizon and
    the band). They answer different questions and "first" is the one
    that matches the procedure, so a gap that exists only under "mean" is
    an artifact of averaging, not a strategy.

    `return_row` additionally yields the FIRST qualifying candle, which is
    the decision point. DD-5 needs it because its `recurring` split is
    point-in-time -- "had this series settled >= 3 events before THIS
    market's decision date" -- and that date is not recoverable from the
    (price, outcome) pair. It is exposed here rather than reimplemented in
    the caller so there is exactly one definition of "qualifying"; a
    second copy of this predicate is how the two would silently diverge.
    """
    lo, hi = band
    s = n = 0
    first = None
    for r in sorted(rows, key=lambda x: -x[anchor]):
        d, ask, bid = r[anchor], r["yes_ask"], r.get("yes_bid")
        if not (dlo <= d <= dhi) or not (lo <= ask <= hi):
            continue
        p = ask if side == "ask" else bid
        if p is None:
            continue
        if max_spread is not None and bid is not None \
                and (ask - bid) * 100.0 > max_spread:
            continue
        if min_volume is not None and (r.get("volume") or 0) < min_volume:
            continue
        if min_oi is not None and (r.get("open_interest") or 0) < min_oi:
            continue
        s += p
        n += 1
        if first is None:
            first = r
        if entry == "first":
            break
    if not n:
        return None
    if return_row:
        return s / n, anchor_row["result"] == "yes", first
    return s / n, anchor_row["result"] == "yes"


def estimate(anchors, candles, *, tickers=None, events=None,
             weight="market", **kw):
    """Pooled estimate, one observation per market.

    Two standard errors are returned and the clustered one is the honest
    one. `se_pts` is the naive binomial SE on P(YES), which assumes every
    market is an independent draw. It is not: this population is full of
    events holding many sibling markets (a "which team" event can carry
    30 legs of which exactly one can win), so sibling outcomes are
    mechanically dependent and the naive SE understates. `se_cl_pts`
    is the cluster-robust SE of mean(price - outcome) over EVENTS, which
    also picks up variation in the price leg that the binomial SE ignores
    entirely. Report `z_cl`.
    """
    per = {}
    for tk, rows in candles.items():
        if tickers is not None and tk not in tickers:
            continue
        a = anchors.get(tk)
        if not a or a.get("deadline") is None:
            continue
        got = observe(rows, a, **kw)
        if got:
            per[tk] = got
    n = len(per)
    if not n:
        return {"markets": 0}
    if weight == "event":
        # One vote per EVENT, not per market. A 17-leg "which houseguest"
        # ladder and a 7-leg date ladder are one question each, and
        # market-weighting lets a single event dominate the pooled number
        # in proportion to how finely Kalshi chose to slice it. Averaging
        # within the event first is the honest unit; the clustered SE
        # already treats it as one.
        buckets: dict[str, list] = {}
        for tk, (p, y) in per.items():
            buckets.setdefault((events or {}).get(tk) or tk, []).append((p, y))
        per = {g: (sum(p for p, _ in v) / len(v),
                   sum(1 for _, y in v if y) / len(v))
               for g, v in buckets.items()}
        n = len(per)
    mean_p = sum(p for p, _ in per.values()) / n
    p_yes = sum(float(y) for _, y in per.values()) / n
    yes_n = round(sum(float(y) for _, y in per.values()))
    gap = (mean_p - p_yes) * 100.0
    se = math.sqrt(p_yes * (1 - p_yes) / n) * 100.0

    # Cluster-robust SE of mean(d), d_i = price_i - outcome_i, by event.
    d = {tk: (p - float(y)) for tk, (p, y) in per.items()}
    dbar = sum(d.values()) / n
    groups: dict[str, float] = {}
    for tk, di in d.items():
        g = (events or {}).get(tk) or tk
        groups[g] = groups.get(g, 0.0) + (di - dbar)
    n_clusters = len(groups)
    se_cl = (math.sqrt(sum(v * v for v in groups.values())) / n) * 100.0

    # Kalshi's fee is 0.07*P*(1-P) per contract, P the price paid.
    no_entry = 1.0 - mean_p
    fee = FEE_RATE * no_entry * (1 - no_entry) * 100.0
    return {"markets": n, "yes_n": yes_n, "mean_p": mean_p, "p_yes": p_yes,
            "gap_pts": gap, "se_pts": se,
            "z": gap / se if se else float("nan"),
            "n_clusters": n_clusters, "se_cl_pts": se_cl,
            "z_cl": gap / se_cl if se_cl else float("nan"),
            "fee_pts": fee, "net_pts": gap - fee}


HDR = ("{:<30}{:>6}{:>5}{:>5}{:>8}{:>8}{:>8}{:>8}{:>7}{:>8}".format(
    "", "mkts", "evts", "YES", "price", "P(YES)", "gap", "SEcl", "zcl", "net"))


def _row(label, r, floor=5):
    if not r or r["markets"] < floor:
        print("{:<30}{:>6}   (too few)".format(label, (r or {}).get("markets", 0)))
        return
    print("{:<30}{:>6}{:>5}{:>5}{:>8.3f}{:>8.3f}{:>+8.1f}{:>8.1f}{:>7.2f}{:>+8.1f}".format(
        label, r["markets"], r["n_clusters"], r["yes_n"], r["mean_p"],
        r["p_yes"], r["gap_pts"], r["se_cl_pts"], r["z_cl"], r["net_pts"]))


def main() -> None:
    anchors, candles, rules = load()
    events = event_map()
    strata = {}
    for tk in candles:
        strata.setdefault(stratum(rules.get(tk, "")), []).append(tk)
    hazard = strata.get("hazard", [])
    # The matched set is the only honest bid-vs-ask comparison: markets
    # captured before 2026-09-01 have no stored bid, so comparing an
    # all-markets ask row against a has-bid bid row compares two samples.
    matched = [tk for tk in hazard
               if any(r.get("yes_bid") is not None for r in candles[tk])]

    by_res = {}
    for a in anchors.values():
        if a.get("closed_early_days") is not None:
            by_res.setdefault(a["result"], []).append(a["closed_early_days"])
    print("{} settled markets, {} with candles".format(len(anchors), len(candles)))
    print("  strata: " + ", ".join(
        "{}={}".format(k, len(v))
        for k, v in sorted(strata.items(), key=lambda x: -len(x[1]))))
    print("  hazard markets carrying both sides of the book: {}\n".format(len(matched)))

    print("early settlement (deadline - actual close), days:")
    for k, v in by_res.items():
        if v:
            print("  {:>4} n={:>4}  median {:7.1f}   closed >3d early: {}/{}".format(
                k.upper(), len(v), statistics.median(v),
                sum(1 for x in v if x > 3), len(v)))

    print("\n=== CORRECTION 1: the time anchor (hazard stratum, YES ask) ===")
    print(HDR); print("-" * len(HDR))
    for anchor, label in (("days_to_close", "actual close (BAD)"),
                          ("days_to_deadline", "stated deadline")):
        _row(label, estimate(anchors, candles, events=events, tickers=hazard,
                             side="ask", anchor=anchor))

    print("\n=== CORRECTION 2: the side of the book (same {} markets) ===".format(
        len(matched)))
    print(HDR); print("-" * len(HDR))
    for entry in ("mean", "first"):
        for side, label in (("ask", "YES ask (optimistic)"),
                            ("bid", "YES bid (what NO pays)")):
            _row("{}  entry={}".format(label, entry),
                 estimate(anchors, candles, events=events, tickers=matched, side=side,
                          entry=entry))

    print("\n=== strata, priced off YES bid (a code gate must say what it removed) ===")
    print(HDR); print("-" * len(HDR))
    for name, tks in sorted(strata.items(), key=lambda x: -len(x[1])):
        _row(name, estimate(anchors, candles, events=events, tickers=tks, side="bid"))
    # The allowlist is the only population whose purity was established
    # EXHAUSTIVELY rather than by sample: round 5b inspected all 70 series
    # and found 70/70 per-subject, so it carries no sampling error at all
    # (theories/deadline_drift/studies/answer/2026-08-29-deadline-drift-classifier-audit/). The regex
    # strata above are a ~15%-misclassification screen over a population
    # the same audit measured as 34% multi-destination, so a gap that
    # appears in "hazard" and NOT here is contamination, not edge.
    allow = [tk for tk in candles
             if in_allowlist((anchors.get(tk) or {}).get("series"))]
    _row("ALLOWLIST (audited 70/70)",
         estimate(anchors, candles, events=events, tickers=allow, side="bid"))
    _row("  ...same, off YES ask",
         estimate(anchors, candles, events=events, tickers=allow, side="ask"))
    branch = branch_families(anchors)
    clean = [tk for tk in hazard
             if (anchors.get(tk) or {}).get("series") not in branch]
    print("  [series settling like branch families: {} of {}; "
          "hazard stratum {} -> {} markets]".format(
              len(branch), len({(a or {}).get("series") for a in anchors.values()}),
              len(hazard), len(clean)))
    _row("hazard MINUS branch families", estimate(anchors, candles, events=events,
                                                  tickers=clean, side="bid"))
    _row("  ...same, off YES ask", estimate(anchors, candles, events=events,
                                            tickers=clean, side="ask"))

    # Early close on a NO market is a free structural tell for
    # multi-destination contamination: a per-subject hazard runs to its
    # deadline (the allowlist measured 0/78 early on 2026-08-29), whereas
    # a "which branch" market resolves NO the moment a SIBLING resolves
    # YES. No model needed, and it is computed from fields already on disk.
    print("\n=== early-close tell: share of NO markets closing >3d early ===")
    print("(a per-subject hazard runs to its deadline; a branch market dies"
          " when a sibling wins)")
    for name, tks in sorted(strata.items(), key=lambda x: -len(x[1]))            + [("ALLOWLIST", allow)]:
        early = tot = 0
        for tk in tks:
            a = anchors.get(tk) or {}
            if a.get("result") != "no" or a.get("closed_early_days") is None:
                continue
            tot += 1
            early += a["closed_early_days"] > 3
        if tot:
            print("  {:<24} {:>4}/{:<4} = {:>5.1f}%".format(
                name, early, tot, 100.0 * early / tot))

    print("\n=== liquidity cuts on the hazard stratum, priced off YES bid ===")
    print(HDR); print("-" * len(HDR))
    _row("all", estimate(anchors, candles, events=events, tickers=hazard, side="bid"))
    for ms in (10, 6, 4, 2):
        _row("spread <= {}pts".format(ms),
             estimate(anchors, candles, events=events, tickers=hazard, side="bid", max_spread=ms))
    for mv in (100, 1000):
        _row("volume >= {}".format(mv),
             estimate(anchors, candles, events=events, tickers=hazard, side="bid", min_volume=mv))
    for oi in (100, 1000):
        _row("open interest >= {}".format(oi),
             estimate(anchors, candles, events=events, tickers=hazard, side="bid", min_oi=oi))

    print("\n=== horizon sweep, hazard stratum, priced off YES bid ===")
    print(HDR); print("-" * len(HDR))
    for dlo, dhi in [(0, 7), (7, 14), (14, 21), (21, 30), (30, 45), (0, 21), (0, 45)]:
        _row("{}-{}d".format(dlo, dhi),
             estimate(anchors, candles, events=events, tickers=hazard, side="bid", dlo=dlo, dhi=dhi))

    print("\n=== price sweep, hazard stratum, 0-21d, priced off YES bid ===")
    print(HDR); print("-" * len(HDR))
    for lo, hi in [(0.01, 0.05), (0.05, 0.15), (0.15, 0.30), (0.30, 0.60),
                   (0.60, 0.90), (0.05, 0.60), (0.01, 0.99)]:
        _row("ask ${:.2f}-${:.2f}".format(lo, hi),
             estimate(anchors, candles, events=events, tickers=hazard, side="bid", band=(lo, hi)))

    # THE PRE-REGISTERED CELL. THEORY.md's decision procedure, exactly:
    # allowlist population; days-to-deadline <= 21; YES ask $0.05-0.60;
    # lifetime volume >= 100; edge = (1 - P(YES)) - no_ask - fees, i.e.
    # priced off yes_bid; entered when the screen first fires. Every other
    # table here is exploration and must be read as such -- this is the
    # one number the theory committed to before any data was collected.
    vol = market_volume()
    liquid_allow = [tk for tk in allow if vol.get(tk, 0.0) >= 100.0]
    print("\n=== THE PRE-REGISTERED CELL (THEORY.md's own procedure) ===")
    print("allowlist | <=21d to stated deadline | ask $0.05-0.60 |"
          " lifetime volume >= 100 | entry=first")
    print(HDR); print("-" * len(HDR))
    _row("priced off YES bid (real)",
         estimate(anchors, candles, events=events, tickers=liquid_allow, side="bid",
                  entry="first"))
    _row("priced off YES ask (old)",
         estimate(anchors, candles, events=events, tickers=liquid_allow, side="ask",
                  entry="first"))
    _row("  ...event-weighted",
         estimate(anchors, candles, events=events, tickers=liquid_allow,
                  side="bid", entry="first", weight="event"))
    liquid_haz = [tk for tk in hazard if vol.get(tk, 0.0) >= 100.0]
    _row("same, wide hazard stratum",
         estimate(anchors, candles, events=events, tickers=liquid_haz, side="bid",
                  entry="first"))
    _row("  ...event-weighted",
         estimate(anchors, candles, events=events, tickers=liquid_haz, side="bid",
                  entry="first", weight="event"))
    # The wide stratum's apparent edge is contamination the rules-text
    # screen cannot see. Strip the series whose settled events pay exactly
    # one winner and it goes away -- which is the point of measuring it.
    part = partition_families(anchors, events)
    clean_haz = [tk for tk in liquid_haz
                 if (anchors.get(tk) or {}).get("series") not in part]
    print("  [series settling as one-winner partitions: {}; "
          "liquid hazard {} -> {} markets]".format(
              len(part), len(liquid_haz), len(clean_haz)))
    _row("  ...minus partition families",
         estimate(anchors, candles, events=events, tickers=clean_haz,
                  side="bid", entry="first"))
    _row("  ...minus partitions, ev-weighted",
         estimate(anchors, candles, events=events, tickers=clean_haz,
                  side="bid", entry="first", weight="event"))

    spreads = [(r["yes_ask"] - r["yes_bid"]) * 100.0
               for tk in hazard for r in candles[tk]
               if r.get("yes_bid") is not None
               and 0 <= r["days_to_deadline"] <= LATE_WINDOW_DAYS
               and ENTRY_BAND[0] <= r["yes_ask"] <= ENTRY_BAND[1]]
    if spreads:
        spreads.sort()
        q = statistics.quantiles(spreads, n=4)
        print("\nbid-ask spread over {} in-window daily observations, points:".format(
            len(spreads)))
        print("  median {:.1f}  mean {:.1f}  p25 {:.1f}  p75 {:.1f}  max {:.1f}".format(
            statistics.median(spreads), statistics.mean(spreads),
            q[0], q[2], spreads[-1]))


if __name__ == "__main__":
    main()
