"""WG-1 return measurements and city-scoped production evidence."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean

from tools.cluster_stats import cluster_interval
from tools.sizing import fee_pts, order_fee_dollars

CAMPAIGN = Path(__file__).resolve().parent / "backtests/wg1-20260905"
RUN_ID = "wg1-20260905/holdout"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(rows: list[dict], *, city: bool = False) -> dict:
    known = [r for r in rows if r.get("result") in {"yes", "no"}]
    pending = [r for r in rows if r.get("result") not in {"yes", "no"}]
    valued = [dict(r, net=100 * (float(r["result"] == r["side"]) - r["entry_price"])
                   - fee_pts(r["entry_price"])) for r in known]
    event = cluster_interval(valued, "net", "event_ticker")
    day = cluster_interval(valued, "net", "target_date")
    settlement = cluster_interval(valued, "net", "settlement_day")
    intervals = (event, day, settlement)
    # >=30 clusters: 2.6 exceeds the two-sided 98.33% t critical at df>=29.
    # Three predeclared cities may earn support independently of the parent.
    lower = [r["mean"] - 2.6 * r["se"] if city and r["se"] is not None
             else r["interval"][0] if r["interval"] is not None else None
             for r in intervals]
    supported = bool(not pending and all(r["clusters"] >= 30 for r in intervals)
                     and all(v is not None and v > 0 for v in lower))
    worst = sum(r["net"] for r in valued) + sum(
        -100 * r["entry_price"] - fee_pts(r["entry_price"]) for r in pending)
    sizes = Counter(r["event_ticker"] for r in known)
    return {
        "n": len(known), "total_n": len(rows), "pending_n": len(pending),
        "net_pts": mean(r["net"] for r in valued) if valued else None,
        "net_one_contract_pts": mean(
            100 * (float(r["result"] == r["side"]) - r["entry_price"]
                   - order_fee_dollars(r["entry_price"], 1)) for r in known) if known else None,
        "event": event, "day": day, "settlement_day": settlement,
        "support_lower_bounds": lower, "city_comparison_adjusted": city,
        "supported": supported,
        "pending_worst_case_net_pts": worst / len(rows) if rows else None,
        "pending_best_case_net_pts": (worst + 100 * len(pending)) / len(rows) if rows else None,
        "max_event_share": max(sizes.values()) / len(known) if known else None,
    }


def production_ready(conn, series: str, *, now: datetime | None = None,
                     campaign: Path | None = None) -> bool:
    """Recompute support from actual frozen holdout attempts, never a report flag."""
    if conn is None:
        return False
    campaign = campaign or CAMPAIGN
    try:
        manifest = json.loads((campaign / "evaluation_manifest.json").read_text(encoding="utf-8"))
        decisions = json.loads((campaign / "decisions.json").read_text(encoding="utf-8"))
        if (manifest["run_id"] != RUN_ID or manifest["protocol"] != "WG-1"
                or manifest["decisions_digest"] != digest(campaign / "decisions.json")
                or manifest["protocol_digest"] != digest(campaign / "PROTOCOL.md")
                or manifest["dataset_digest"] != digest(campaign / "dataset.json")
                or series not in manifest["population_series"]):
            return False
        registered = conn.execute(
            "SELECT theory_id,theory_version,tier,uses_llm_judgment,notes FROM backtest_runs WHERE run_id=?",
            (RUN_ID,),
        ).fetchone()
        if not registered or tuple(registered)[:4] != ("weather_model_gap", 1, "A", 0):
            return False
        registered_proof = json.loads(registered["notes"])
        if (registered_proof.get("protocol") != "WG-1"
                or registered_proof.get("evaluation_manifest_digest") != digest(campaign / "evaluation_manifest.json")
                or registered_proof.get("dataset_digest") != manifest["dataset_digest"]):
            return False
        attempts = conn.execute(
            """SELECT o.kalshi_ticker,o.outcome,a.decision_date,a.entry_price,a.model_prob,
                      a.edge_basis,a.edge_pts_net,a.extra_json,s.result,s.resolved_at
                 FROM opportunity_attempts a JOIN opportunities o ON o.id=a.opportunity_id
                 LEFT JOIN settlements s ON s.kalshi_ticker=o.kalshi_ticker
                WHERE a.run_id=? AND o.theory_id='weather_model_gap' AND o.theory_version=1""",
            (RUN_ID,),
        ).fetchall()
        expected = {(r["ticker"], r["side"], r["target_date"]): r for r in decisions}
        if len(expected) != len(decisions) or len(attempts) != len(expected):
            return False
        valued, seen = [], set()
        now = now or datetime.now(timezone.utc)
        for r in attempts:
            key = r["kalshi_ticker"], r["outcome"], r["decision_date"]
            if key in seen or key not in expected:
                return False
            seen.add(key)
            frozen = expected[key]
            extra = json.loads(r["extra_json"])
            if (r["edge_basis"] != "model" or extra["protocol"] != "WG-1"
                    or extra["source_digest"] != manifest["source_digest"]
                    or extra["series_ticker"] != frozen["series_ticker"]
                    or extra["event_ticker"] != frozen["event_ticker"]
                    or abs(r["entry_price"] - frozen["entry_price"]) > 1e-9
                    or abs(r["model_prob"] - frozen["model_prob"]) > 1e-9):
                return False
            net = 100 * (r["model_prob"] - r["entry_price"]) - fee_pts(r["entry_price"])
            if net < 8 - 1e-9 or abs(net - r["edge_pts_net"]) > 1e-8:
                return False
            result, resolved = r["result"], r["resolved_at"]
            resolved_dt = datetime.fromisoformat(resolved.replace("Z", "+00:00")) if resolved else None
            if (resolved_dt is None or resolved_dt.tzinfo is None or resolved_dt > now
                    or resolved_dt.date().isoformat() < r["decision_date"]):
                result = None
            if extra["series_ticker"] == series:
                valued.append(dict(frozen, result=result,
                                   settlement_day=resolved_dt.date().isoformat() if resolved_dt else None))
        return summarize(valued, city=True)["supported"]
    except (OSError, ValueError, TypeError, KeyError):
        return False
