"""Replay taker-flow following over settled Kalshi markets. Tier A.

No model anywhere in the decision path: the signal is a volume-weighted
imbalance statistic and the entry is a threshold, so this replays over all
reachable history and re-runs for free.

WHAT "ALL REACHABLE HISTORY" MEANS HERE, and it is the binding constraint.
Two independent floors have to both clear:

  - the trade feed retains nothing before 2026-06-26T00:00:00Z
    (`tools.kalshi.trades.RETENTION_FLOOR`), so a market needs its whole
    flow window above that date;
  - outcomes come from the `settlements` table, which is what past sessions
    happened to capture, and Kalshi archives settled markets out of
    `/markets` at ~60 days, so outcomes cannot be backfilled either.

The intersection is roughly 2026-07-06 onward. That is not a parameter to
tune -- it is the window that exists.

KNOWN BIASES, stated here because a replay whose biases are unwritten
produces a number nobody can caveat:

  1. ENTRY IS THE LAST TRADE PRICE, NOT THE ASK. Kalshi archives no
     historical order books and candlesticks come back empty for archived
     tickers, so there is no ask to reconstruct. This FLATTERS the
     strategy by roughly a half-spread on every position. A positive
     result that does not clear the typical spread of its population is
     not a result.
  2. SURVIVORSHIP IN THE OUTCOME SOURCE. `settlements` holds what earlier
     sessions collected, not a census of what settled. It is not known to
     be biased along flow, but it is not a random sample either.
  3. THE DECISION POINT IS RELATIVE TO RESOLUTION, NOT CLOSE. `settlements`
     carries `resolved_at` and not `close_time`, so a market that resolved
     long after it stopped trading gets a decision point further from its
     real close than the buffer suggests. This makes the buffer a lower
     bound on how early the decision was taken, which is the conservative
     direction.
"""

from __future__ import annotations

import collections
import json
import math
import os
import random
import statistics
from datetime import datetime, timedelta

from theories.taker_flow.features import (
    EXTREME_IMBALANCE,
    event_key,
    flow_bucket,
    is_single_name,
)
from tools.kalshi import trades as trades_client

#: Earliest resolution date whose 7-day flow window clears the trade
#: retention floor with a margin. See the module docstring.
MIN_RESOLVED = "2026-07-06"

def _ts(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def collect(conn, out_path: str, target: int, seed: int = 11) -> int:
    """Fetch trade history for settled markets, incrementally and resumably.

    One JSON line per market, flushed as it lands: an interrupted run
    resumes from the file rather than restarting. That is not politeness --
    both the trade feed and `/markets` age their data out, so a run that
    loses its work may not be able to re-fetch it.
    """
    done = set()
    if os.path.exists(out_path):
        with open(out_path) as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["ticker"])
                except (ValueError, KeyError):
                    continue

    rows = [
        (r[0], r[1], r[2])
        for r in conn.execute(
            """
            SELECT kalshi_ticker, resolved_at, result FROM settlements
            WHERE result IN ('yes','no') AND resolved_at IS NOT NULL
              AND resolved_at >= ?
            ORDER BY kalshi_ticker
            """,
            (MIN_RESOLVED,),
        )
    ]
    random.Random(seed).shuffle(rows)
    todo = [r for r in rows if r[0] not in done][: max(0, target - len(done))]

    written = 0
    with open(out_path, "a") as fh:
        for ticker, resolved_at, result in todo:
            try:
                rows_t = trades_client.trades(ticker, max_pages=8)
                err = None
            except Exception as exc:                      # noqa: BLE001
                rows_t, err = [], str(exc)
            fh.write(
                json.dumps(
                    {
                        "ticker": ticker,
                        "resolved_at": resolved_at,
                        "result": result,
                        "err": err,
                        "trades": [
                            {
                                "t": t.created_time,
                                "s": t.taker_side,
                                "c": t.count,
                                "p": t.yes_price,
                                "b": t.is_block_trade,
                            }
                            for t in rows_t
                        ],
                    }
                )
                + "\n"
            )
            fh.flush()
            written += 1
    return written


def build_records(
    raw_rows,
    *,
    buffer_hours: float = 24.0,
    lookback_days: float = 7.0,
    min_trades: int = 20,
) -> list[dict]:
    """Reconstruct the decision at `buffer_hours` before resolution.

    Nothing after the decision point is read: the imbalance and the price
    both come from trades at or before it. That property is what makes
    this lookahead-free, so it is the one thing worth testing directly.
    """
    offset = timedelta(hours=buffer_hours)
    window = timedelta(days=lookback_days)
    out = []
    for row in raw_rows:
        if not row.get("trades"):
            continue
        decision_at = _ts(row["resolved_at"]) - offset
        floor = decision_at - window
        win = [t for t in row["trades"] if floor <= _ts(t["t"]) <= decision_at]
        if len(win) < min_trades:
            continue
        imb = _imbalance(win)
        if imb is None:
            continue
        out.append(
            {
                "ticker": row["ticker"],
                "imbalance": imb,
                "price": max(win, key=lambda t: _ts(t["t"]))["p"],
                "won_yes": 1 if row["result"] == "yes" else 0,
                "single_name": is_single_name(row["ticker"]),
                "flow_bucket": flow_bucket(imb),
                "event": event_key(row["ticker"]),
                "day": row["resolved_at"][:10],
                "n_trades": len(win),
            }
        )
    return out


def _imbalance(win) -> float | None:
    vy = sum(t["c"] for t in win if t["s"] == "yes")
    vn = sum(t["c"] for t in win if t["s"] == "no")
    return (vy - vn) / (vy + vn) if vy + vn > 0 else None


def follow_pnl(rec: dict) -> float:
    """Points gained by taking the side the flow is taking, at entry price.

    Not fee-adjusted and not spread-adjusted -- see bias 1 in the module
    docstring. This is the gross number; the caller subtracts.
    """
    if rec["imbalance"] > 0:
        return 100.0 * (rec["won_yes"] - rec["price"])
    return 100.0 * ((1 - rec["won_yes"]) - (1 - rec["price"]))


def evaluate(records: list[dict], threshold: float = 0.6) -> dict:
    """Clustered edge for the follow-the-flow rule above `threshold`.

    Clusters by event: strikes inside one Kalshi event resolve against the
    same underlying, so treating them as independent draws would shrink the
    error bar by a factor the data does not earn.
    """
    sel = [r for r in records if abs(r["imbalance"]) > threshold]
    if not sel:
        return {"n": 0}
    pnl = [follow_pnl(r) for r in sel]
    by_event = collections.defaultdict(list)
    for rec, p in zip(sel, pnl):
        by_event[rec["event"]].append(p)
    clusters = [statistics.mean(v) for v in by_event.values()]
    mean = statistics.mean(pnl)
    cse = (
        statistics.stdev(clusters) / math.sqrt(len(clusters))
        if len(clusters) > 1
        else float("nan")
    )
    return {
        "n": len(sel),
        "edge_pts": mean,
        "n_clusters": len(clusters),
        "n_days": len({r["day"] for r in sel}),
        "cluster_se": cse,
        "cluster_t": mean / cse if cse == cse and cse else float("nan"),
        "ci_lo": mean - 1.96 * cse if cse == cse else float("nan"),
        "ci_hi": mean + 1.96 * cse if cse == cse else float("nan"),
        "mean_price": statistics.mean(r["price"] for r in sel),
    }


def load(path: str) -> list[dict]:
    with open(path) as fh:
        return [json.loads(line) for line in fh]


#: The replay's own run id. Declared in the slice's `mined_from_run_ids`,
#: so the run that suggested the extreme threshold can never vouch for it.
RUN_ID = "backtest-2026-09-01-takerflow"


def record_run(
    conn,
    records: list[dict],
    *,
    theory_version: int = 1,
    run_id: str = RUN_ID,
    threshold: float = 0.6,
) -> int:
    """Write the replay's decisions to the ledger as OBSERVATIONS.

    Every row records `edge_pts_net=0.0` with `edge_basis='prior'`, and
    that is deliberate rather than lazy. This replay is what PRODUCED the
    per-bucket numbers the live theory now claims, so letting it also
    claim them would make `realization` -- delivered edge over claimed
    edge -- approximately 1.0 by construction, and credibility would look
    earned when nothing had been demonstrated. `rank.realization` treats a
    non-positive claimed edge as neutral, so recording no claim is the
    honest way to say "this run measures, it does not predict" (the
    2026-08-30 observation-rows ruling).

    The realized calibration edge is unaffected: it is computed from the
    outcome against the entry price, which is the number this run exists
    to establish.
    """
    from tools import ledger

    written = 0
    for rec in records:
        if abs(rec["imbalance"]) <= threshold:
            continue
        side = "yes" if rec["imbalance"] > 0 else "no"
        entry = rec["price"] if side == "yes" else 1.0 - rec["price"]
        if not 0.0 < entry < 1.0:
            continue
        decision_day = (
            _ts(rec["day"] + "T00:00:00Z") - timedelta(hours=24)
        ).date().isoformat()
        ledger.record_opportunity(
            conn,
            theory_id="taker_flow",
            theory_version=theory_version,
            kalshi_ticker=rec["ticker"],
            outcome=side,
            entry_price=entry,
            edge_pts_net=0.0,
            edge_basis="prior",
            run_mode="backtest",
            run_id=run_id,
            confidence=rec["flow_bucket"],
            decision_date=decision_day,
            rationale=(
                f"replay: taker imbalance {rec['imbalance']:+.3f} over "
                f"{rec['n_trades']} trades in the trailing 7d, decision 24h "
                f"before resolution. Observation, not a prediction -- this "
                f"run measured the bucket rates the live theory uses."
            ),
            extra_json=json.dumps(
                {
                    "imbalance": round(rec["imbalance"], 4),
                    "flow_bucket": rec["flow_bucket"],
                    "window_trades": rec["n_trades"],
                    "single_name": rec["single_name"],
                    "event": rec["event"],
                }
            ),
        )
        written += 1
    return written
