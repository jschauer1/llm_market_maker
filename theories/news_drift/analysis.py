"""ND-1 frozen estimation and diagnostic returns; never outcome selection."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

from tools.cluster_stats import cluster_interval
from tools.sizing import fee_pts, order_fee_dollars


def fit_calibration(rows: list[dict], *, cutoff_ts: int,
                    source_digest: str) -> dict:
    seen = set()
    train = []
    for r in sorted(rows, key=lambda r: (r["entry_ts"], r["ticker"])):
        if (r["entry_ts"] >= cutoff_ts or r.get("resolved_ts") is None
                or r["resolved_ts"] >= cutoff_ts):
            continue
        if r["ticker"] in seen or r["result"] not in {"yes", "no"}:
            continue
        seen.add(r["ticker"])
        train.append(r)
    n = len(train)
    clusters = len({r["event_ticker"] for r in train})
    return {
        "protocol": "ND-1", "approved": n >= 30 and clusters >= 10,
        # This corpus is a partial settled-only sample. Fit for the exp/
        # diagnostic, never install it as live calibration by file existence.
        "eligible_for_production": False,
        "training_end": datetime.fromtimestamp(cutoff_ts, timezone.utc).isoformat(),
        "n": n, "event_clusters": clusters, "source_digest": source_digest,
        "residual": mean(float(r["result"] == r["side"]) - r["directional_mid"]
                         for r in train) if train else 0.0,
    }


def measure(rows: list[dict], *, include_reversal: bool = True) -> dict:
    if not rows:
        return {"n": 0, "net_pts": None, "event": cluster_interval([], "net", "event_ticker"),
                "day": cluster_interval([], "net", "settlement_day")}
    valued = []
    for r in rows:
        if r.get("result") not in {"yes", "no"}:
            raise ValueError("Unresolved outcomes require summarize(), never an assumed loss")
        won = float(r["result"] == r["side"])
        ask = r["entry_price"]
        valued.append(dict(r, net=100 * (won - ask) - fee_pts(ask),
                           gross_mid=100 * (won - r["directional_mid"]),
                           gross_ask=100 * (won - ask),
                           net_one=100 * (won - ask - order_fee_dollars(ask, 1))))
    event = cluster_interval(valued, "net", "event_ticker")
    day = cluster_interval(valued, "net", "settlement_day")
    result = {
        "n": len(rows), "gross_mid_pts": mean(r["gross_mid"] for r in valued),
        "gross_ask_pts": mean(r["gross_ask"] for r in valued),
        "net_pts": mean(r["net"] for r in valued),
        "net_one_contract_pts": mean(r["net_one"] for r in valued),
        "event": event, "day": day,
        "positive_statistical_bar": bool(
            event["clusters"] >= 30 and day["clusters"] >= 10
            and event["interval"][0] > 0 and day["interval"][0] > 0),
    }
    sizes = defaultdict(int)
    for r in rows:
        sizes[r["event_ticker"]] += 1
    result["max_event_share"] = max(sizes.values()) / len(rows)
    result["effective_event_count"] = len(rows) ** 2 / sum(n * n for n in sizes.values())
    day_values = defaultdict(list)
    for r in valued:
        day_values[r["settlement_day"]].append(r["net"])
    result["equal_day_net_pts"] = mean(mean(values) for values in day_values.values())
    if include_reversal:
        reverse = [dict(r, side="no" if r["side"] == "yes" else "yes",
                        entry_price=r["reverse_price"],
                        directional_mid=1 - r["directional_mid"]) for r in rows]
        result["reversal"] = measure(reverse, include_reversal=False)
    return result


def summarize(rows: list[dict]) -> dict:
    """Retain pending bets in the denominator and display honest payout bounds."""
    known = [r for r in rows if r.get("result") in {"yes", "no"}]
    pending = [r for r in rows if r.get("result") not in {"yes", "no"}]
    result = measure(known)
    result.update(total_n=len(rows), pending_n=len(pending))
    if rows:
        paid_net = sum(100 * (float(r["side"] == r["result"]) - r["entry_price"])
                       - fee_pts(r["entry_price"]) for r in known)
        worst = paid_net + sum(-100 * r["entry_price"] - fee_pts(r["entry_price"])
                               for r in pending)
        result["pending_worst_case_net_pts"] = worst / len(rows)
        result["pending_best_case_net_pts"] = (worst + 100 * len(pending)) / len(rows)
    else:
        result["pending_worst_case_net_pts"] = None
        result["pending_best_case_net_pts"] = None
    if pending:
        result["positive_statistical_bar"] = False
    return result
