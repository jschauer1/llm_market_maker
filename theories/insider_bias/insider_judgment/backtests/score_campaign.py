"""Regenerate every number in RESULTS.md from the ledger.

Run:  python -m theories.insider_bias.insider_judgment.backtests.score_campaign

Produces: full-population bucket x side, the pre-registered family with
Holm-Bonferroni on the replication runs, and the event-clustered t for
the bet rule. Kept in-repo so the campaign's statistics are one command
to reproduce or extend when live rows accumulate — not an artifact of
one session's scratchpad.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict

from tools import db
from tools.sizing import fee_pts

JUDGED_PREFIX = "backtest-2026-08-26-insider-judged-%"
REPLICATION_RUNS = ("backtest-2026-08-26-insider-judged-s200b",
                    "backtest-2026-08-26-insider-judged-s57")


def binom_p(k: int, n: int, probs: list[float]) -> float:
    """Exact upper-tail P(wins >= k) under heterogeneous fair prices."""
    dp = [1.0]
    for p in probs:
        nd = [0.0] * (len(dp) + 1)
        for i, v in enumerate(dp):
            nd[i] += v * (1 - p)
            nd[i + 1] += v * p
        dp = nd
    return sum(dp[k:])


def event_clustered_t(rows: list[dict]) -> tuple[int, float, float, float]:
    """(n_events, mean event net, t, one-sided normal p)."""
    ev = defaultdict(list)
    for d in rows:
        ev[d["event"]].append(d["net"])
    means = [sum(v) / len(v) for v in ev.values()]
    ne = len(means)
    mu = sum(means) / ne
    var = sum((x - mu) ** 2 for x in means) / (ne - 1)
    t = mu / math.sqrt(var / ne)
    p = 0.5 * (1 - math.erf(t / math.sqrt(2)))
    return ne, mu, t, p


def load(conn: sqlite3.Connection) -> list[dict]:
    # Reads what the judged run itself recorded (opportunity_attempts),
    # not the position rollup -- after position-identity merges, a
    # re-sighted position's opportunities.run_id is the *earliest* run's,
    # so filtering there would silently miss every merged row (attempt
    # fidelity spec, 2026-08-27 sec 9). o.outcome is identity, not
    # per-attempt, so it still comes from the position join.
    rows = conn.execute(
        """select a.run_id, o.outcome, a.entry_price, a.confidence,
                  a.extra_json, s.result
           from opportunity_attempts a
           join opportunities o on o.id = a.opportunity_id
           join settlements s on s.kalshi_ticker = o.kalshi_ticker
           where a.run_id like ? and s.result in ('yes','no')""",
        (JUDGED_PREFIX,),
    ).fetchall()
    out = []
    for r in rows:
        x = json.loads(r["extra_json"])
        won = r["result"] == r["outcome"]
        out.append(dict(
            p=r["entry_price"], won=won, side=r["outcome"],
            bucket=r["confidence"], event=x["event_ticker"],
            rep=r["run_id"] in REPLICATION_RUNS,
            diverge=x.get("rules_diverge_from_title"),
            net=((1.0 if won else 0.0) - r["entry_price"]) * 100
                - fee_pts(r["entry_price"]),
        ))
    return out


def cell(rows: list[dict], label: str) -> None:
    n = len(rows)
    if n == 0:
        print(f"{label:30s} n=0")
        return
    wins = sum(d["won"] for d in rows)
    probs = [d["p"] for d in rows]
    net = sum(d["net"] for d in rows) / n
    ev = len(set(d["event"] for d in rows))
    print(f"{label:30s} n={n:4d} ev={ev:4d} win={wins/n:.3f} "
          f"price={sum(probs)/n:.3f} net={net:+6.2f} "
          f"p_fair={binom_p(wins, n, probs):.4f}")


def main() -> None:
    conn = db.connect()
    D = load(conn)
    conn.close()
    print(f"judged rows: {len(D)}  events: {len(set(d['event'] for d in D))}")

    print("\n=== full population, bucket x side ===")
    for b in ("strong", "moderate", "weak"):
        for side in ("no", "yes"):
            cell([d for d in D if d["bucket"] == b and d["side"] == side],
                 f"{b} {side.upper()}")

    def rule(d):
        return d["side"] == "no" and d["bucket"] in ("strong", "moderate")

    print("\n=== pre-registered family, Holm on replication data (m=4) ===")
    fam = {
        "bet rule (str+mod NO)": [d for d in D if d["rep"] and rule(d)],
        "moderate-NO": [d for d in D if d["rep"]
                        and d["bucket"] == "moderate" and d["side"] == "no"],
        "strong-NO": [d for d in D if d["rep"]
                      and d["bucket"] == "strong" and d["side"] == "no"],
        "diverge flag": [d for d in D if d["rep"] and d["diverge"]],
    }
    ps = sorted((binom_p(sum(d["won"] for d in sub), len(sub),
                         [d["p"] for d in sub]), name)
                for name, sub in fam.items())
    stopped = False
    for i, (p, name) in enumerate(ps):
        thresh = 0.05 / (len(ps) - i)
        if stopped or p > thresh:
            stopped = True
            print(f"{name:24s} p={p:.4f} -> fails")
        else:
            print(f"{name:24s} p={p:.4f} vs {thresh:.4f} -> SURVIVES")

    print("\n=== event-clustered t, bet rule ===")
    for label, sub in (("replication", [d for d in D if d["rep"] and rule(d)]),
                       ("pooled", [d for d in D if rule(d)])):
        ne, mu, t, p = event_clustered_t(sub)
        print(f"{label:12s} events={ne:3d} mean_net={mu:+.2f} "
              f"t={t:+.2f} one-sided p~{p:.4f}")


if __name__ == "__main__":
    main()
