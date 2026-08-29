"""Per-series bias miner. Implements STUDY.md's pre-registered bar exactly.

No model, no network, no ledger writes: this reads settled backtest rows
and reports which recurring series show a persistent price-vs-outcome
bias that survives a four-part multiple-comparisons guard.

Every constant here is quoted from STUDY.md, which was committed before
any per-series number was computed. Changing one changes the
pre-registration and must be done in the open, not silently.

Run: python studies/2026-08-29-series-bias-mining/mine.py
"""

from __future__ import annotations

import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import db                       # noqa: E402
from tools.sizing import fee_pts           # noqa: E402

#: The only two runs sharing one decision rule, and disjoint. See
#: STUDY.md "Population" for why calharvest-weather is excluded.
RUNS = ("backtest-2026-08-25-insider-fullcov",
        "backtest-2026-08-25-mention-fullcov")

#: Per-series inclusion floors (STUDY.md "Per-series inclusion floors").
MIN_N = 40
MIN_DAYS = 8
MIN_HALF_N = 15
MIN_HALF_DAYS = 3

#: Guard thresholds (STUDY.md "The multiple-comparisons guard").
MIN_HALF_EDGE = 1.0
MIN_ABS_T = 2.0
ALPHA = 0.05

#: mention_family's series -- the built-in negative control. Measured,
#: never promoted; a flag here means the guard is too loose.
MENTION_MARKER = ("MENTION", "SAY", "ACT")


@dataclass(frozen=True)
class SeriesStat:
    series: str
    n: int
    n_days: int
    edge: float          # GROSS: realized rate - ask. The bias.
    edge_net: float      # gross minus fees. Bettability, not bias.
    se: float
    t: float
    p: float
    first_edge: float
    second_edge: float
    passes_split: bool
    passes_t: bool


def series_of(ticker: str) -> str:
    return ticker.split("-")[0]


def is_mention_family(series: str) -> bool:
    return any(mark in series for mark in MENTION_MARKER)


def load(conn, runs=RUNS) -> dict[str, list[tuple]]:
    """{series: [(day, won, ask), ...]} for settled single-leg rows."""
    marks = ",".join("?" * len(runs))
    sql = f"""
        SELECT o.kalshi_ticker, o.outcome, o.entry_price,
               s.result, DATE(s.resolved_at) AS day
        FROM opportunities o
        JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
        WHERE o.run_mode = 'backtest' AND o.position_kind = 'single'
          AND o.run_id IN ({marks})
          AND s.result IS NOT NULL AND s.resolved_at IS NOT NULL
          AND o.entry_price IS NOT NULL
    """
    out: dict[str, list[tuple]] = {}
    for r in conn.execute(sql, runs):
        won = 1.0 if (r["outcome"] or "").lower() == (r["result"] or "").lower() else 0.0
        out.setdefault(series_of(r["kalshi_ticker"]), []).append(
            (r["day"], won, float(r["entry_price"])))
    return out


def day_edges(rows, net: bool = False) -> dict[str, float]:
    """One edge per settlement day, in points.

    GROSS by default -- `(mean won - mean ask) * 100` -- because that is
    the *calibration bias*, which is what this study measures and guards
    on. See STUDY.md's 2026-08-29 amendment: scoring the guard net of
    fees gives a perfectly calibrated series a persistent ~-1 to -3 pt
    "bias" of the right sign in both halves, so every calibrated series
    would flag as negatively biased. Fees are a trading cost, not a
    property of the price.

    `net=True` subtracts the per-contract fee and is reported alongside,
    for the separate question of whether a real bias is bettable.
    """
    acc: dict[str, list] = {}
    for day, won, ask in rows:
        a = acc.setdefault(day, [0.0, 0.0, 0.0, 0])
        a[0] += won
        a[1] += ask
        a[2] += fee_pts(ask)
        a[3] += 1
    return {d: (w / n - a / n) * 100.0 - (f / n if net else 0.0)
            for d, (w, a, f, n) in acc.items()}


def _mean_se(values) -> tuple[float, float]:
    """Mean and between-day SE. Zero variance yields SE 0, which callers
    must treat as infinitely significant rather than as t=0 -- the
    opposite error, and one a fixture caught."""
    if len(values) < 2:
        return (statistics.mean(values) if values else 0.0), float("inf")
    return statistics.mean(values), statistics.stdev(values) / len(values) ** 0.5


def _two_sided_p(t: float, df: int) -> float:
    if df < 1 or not (t == t):
        return 1.0
    if t in (float("inf"), float("-inf")):
        return 0.0          # zero between-day variance: maximally significant
    from scipy import stats
    return float(2 * stats.t.sf(abs(t), df))


def stat_for(series: str, rows) -> SeriesStat | None:
    """The pre-registered per-series statistic, or None if it fails the
    inclusion floors (which are read in neither direction)."""
    edges = day_edges(rows)
    days = sorted(edges)
    if len(rows) < MIN_N or len(days) < MIN_DAYS:
        return None

    mid = len(days) // 2
    first_days, second_days = days[:mid], days[mid:]
    first_rows = [r for r in rows if r[0] in set(first_days)]
    second_rows = [r for r in rows if r[0] in set(second_days)]
    if (len(first_rows) < MIN_HALF_N or len(second_rows) < MIN_HALF_N
            or len(first_days) < MIN_HALF_DAYS
            or len(second_days) < MIN_HALF_DAYS):
        return None

    vals = [edges[d] for d in days]
    mean, se = _mean_se(vals)
    if se == 0:
        # Identical every day: a real, perfectly consistent effect (or a
        # degenerate fixture). t=0 here would be exactly backwards.
        t = 0.0 if mean == 0 else float("inf") * (1 if mean > 0 else -1)
    else:
        t = mean / se
    net_edges = day_edges(rows, net=True)
    mean_net, _ = _mean_se([net_edges[d] for d in days])
    f_mean, _ = _mean_se([edges[d] for d in first_days])
    s_mean, _ = _mean_se([edges[d] for d in second_days])

    same_sign = (f_mean > 0) == (s_mean > 0)
    both_big = min(abs(f_mean), abs(s_mean)) >= MIN_HALF_EDGE
    return SeriesStat(
        series=series, n=len(rows), n_days=len(days),
        edge=mean, edge_net=mean_net, se=se,
        t=t, p=_two_sided_p(t, len(days) - 1),
        first_edge=f_mean, second_edge=s_mean,
        passes_split=bool(same_sign and both_big),
        passes_t=abs(t) >= MIN_ABS_T,
    )


def holm(stats: list[SeriesStat], alpha: float = ALPHA) -> set[str]:
    """Series surviving Holm-Bonferroni over the whole tested family."""
    ordered = sorted(stats, key=lambda s: s.p)
    m = len(ordered)
    survivors: set[str] = set()
    for i, s in enumerate(ordered):
        if s.p <= alpha / (m - i):
            survivors.add(s.series)
        else:
            break          # Holm stops at the first failure
    return survivors


def mine(conn, runs=RUNS) -> dict:
    by_series = load(conn, runs)
    stats = [st for series, rows in sorted(by_series.items())
             if (st := stat_for(series, rows)) is not None]
    survivors = holm(stats)
    flagged = [s for s in stats
               if s.passes_split and s.passes_t and s.series in survivors]
    return {
        "series_seen": len(by_series),
        "series_tested": len(stats),
        "expected_false_positives": ALPHA * len(stats),
        "passing_split": sum(s.passes_split for s in stats),
        "passing_split_and_t": sum(s.passes_split and s.passes_t
                                   for s in stats),
        "holm_survivors": len(survivors),
        "flagged": flagged,
        "stats": stats,
    }


def main() -> None:
    res = mine(db.connect())
    print(f"series seen              : {res['series_seen']}")
    print(f"series tested (floors)   : {res['series_tested']}")
    print(f"expected false positives : {res['expected_false_positives']:.1f} "
          f"(alpha {ALPHA} x tested)")
    print(f"pass split-sample guard  : {res['passing_split']}")
    print(f"  ... and |t| >= 2       : {res['passing_split_and_t']}")
    print(f"survive Holm-Bonferroni  : {res['holm_survivors']}")
    print(f"FLAGGED (all four gates) : {len(res['flagged'])}")

    if res["stats"]:
        print("\nevery tested series, by |t|:")
        print(f"  {'series':26} {'n':>5} {'days':>5} {'gross':>7} {'net':>7} "
              f"{'SE':>6} {'t':>6} {'p':>7} {'h1':>7} {'h2':>7}  gates")
        for s in sorted(res["stats"], key=lambda x: -abs(x.t)):
            gates = ("S" if s.passes_split else "-") + \
                    ("T" if s.passes_t else "-") + \
                    ("H" if s.series in holm(res["stats"]) else "-")
            ctl = " [mention: negative control]" if is_mention_family(s.series) else ""
            print(f"  {s.series:26} {s.n:5} {s.n_days:5} {s.edge:+7.2f} "
                  f"{s.edge_net:+7.2f} {s.se:6.2f} {s.t:+6.2f} {s.p:7.4f} "
                  f"{s.first_edge:+7.2f} {s.second_edge:+7.2f}  {gates}{ctl}")


if __name__ == "__main__":
    main()
