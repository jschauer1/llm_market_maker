"""TRG-1 experimental archive replay; decisions freeze before settlement."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from tools import atomic_write, db, score
from tools.cluster_stats import cluster_interval
from tools.domain import Market
from tools.sizing import fee_pts, order_fee_dollars
from tools.theory import TheoryContext

UTC = timezone.utc
CAMPAIGN = Path(__file__).parent / "backtests" / "trg1-20260905"
START, SPLIT, END = date(2022, 6, 19), date(2025, 8, 31), date(2026, 8, 30)
RUN_PREFIX = "exp/trg1-20260905/"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(path: Path, value) -> None:
    """An existing campaign identity may be replayed, never overwritten."""
    content = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"frozen evidence changed: {path}")
        return
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def instant(value) -> datetime | None:
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (float, int)):
            return datetime.fromtimestamp(value, UTC)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except (ValueError, TypeError, AttributeError, OverflowError, OSError):
        return None


def number(value):
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (ValueError, TypeError):
        return None


def reconstruct(raw, event, candle, source_digest):
    """Only contract metadata and fixed-entry observations reach the model."""
    from .data import entry_for, parse_contract
    contract, reason = parse_contract(raw)
    if reason or contract is None:
        return None, reason or "invalid_contract"
    week = contract["week_end"]
    if isinstance(week, str):
        week = date.fromisoformat(week)
    entry = entry_for(week)
    if (week.isoformat() != event["week_end"]
            or instant(event["entry_time"]) != entry):
        return None, "entry_calendar_mismatch"
    opened = instant(raw.get("open_time"))
    if opened is None or opened > entry:
        return None, "not_open_at_entry"
    for key in ("close_time", "settlement_ts"):
        closed = instant(raw.get(key))
        if closed is not None and closed <= entry:
            return None, "closed_before_entry"
    if not candle or number(candle.get("end_ts")) != entry.timestamp():
        return None, "missing_exact_candle"
    bid, ask = number(candle.get("yes_bid_close")), number(candle.get("yes_ask_close"))
    oi, volume = number(candle.get("open_interest")), number(candle.get("volume"))
    if bid is None or ask is None or not 0 <= bid <= ask <= 1:
        return None, "invalid_quote"
    if oi is None or oi < 0 or volume is None or volume < 0:
        return None, "missing_entry_liquidity"
    nominal_close = datetime.combine(week, time(23, 59), ZoneInfo("America/New_York"))
    safe = {key: raw.get(key) for key in ("ticker", "rules_primary", "rules_secondary")}
    safe.update(week_end=week.isoformat(), strike=contract["strike"],
                entry_time=entry.isoformat(), source_digest=source_digest)
    return Market(
        platform="kalshi", ticker=raw["ticker"], title=raw.get("title"),
        yes_bid=bid, yes_ask=ask, no_bid=1-ask, no_ask=1-bid,
        mid=(bid+ask)/2, spread=ask-bid, volume=volume, volume_24h=volume,
        open_interest=oi, is_open=True, status="open", open_time=opened.isoformat(),
        close_time=nominal_close.astimezone(UTC).isoformat(),
        rules_primary=raw.get("rules_primary"), event_ticker=event["event_ticker"],
        series_ticker="KXTSAW", raw=safe,
        event={"category": "Economics", "event_ticker": event["event_ticker"]},
    ), None


def decision(scored, week: date, run_id: str):
    leg = scored.candidate.legs[0]
    return {"run_id": run_id, "week_end": week.isoformat(),
            "event_ticker": leg.market.event_ticker, "ticker": leg.market.ticker,
            "side": leg.side, "price": leg.price,
            "model_prob": scored.edge.model_prob, "edge_pts_net": scored.edge.pts_net,
            "entry_time": leg.market.raw["entry_time"], "extra": scored.extra}


def prepare(conn, campaign=CAMPAIGN):
    from .data import entry_for, load_dataset
    from .theory import TsaRemainderGapTheory
    campaign = Path(campaign)
    dataset = load_dataset(campaign / "dataset.json")
    if dataset.get("protocol_digest") != digest(campaign / "PROTOCOL.md"):
        raise ValueError("dataset protocol digest mismatch")
    freeze(campaign / "identity.json", {
        "dataset_digest": digest(campaign / "dataset.json"),
        "protocol_digest": digest(campaign / "PROTOCOL.md"),
        "source_digest": dataset["source_digest"],
        "source_validated": False, "run_prefix": RUN_PREFIX,
    })
    theory = TsaRemainderGapTheory(daily_counts=dataset["daily_counts"])
    by_week = defaultdict(list)
    for event in dataset["events"]:
        by_week[event["week_end"]].append(event)
    decisions, runs, coverage = [], [], []
    week = START
    while week <= END:
        run_id = RUN_PREFIX + ("development" if week < SPLIT else "holdout")
        events, board, removed = by_week[week.isoformat()], [], Counter()
        for event in events:
            for raw in event["markets"]:
                market, reason = reconstruct(raw, event, event["candles"].get(raw["ticker"]),
                                             dataset["source_digest"])
                if reason:
                    removed[reason] += 1
                else:
                    board.append(market)
        if not events:
            removed["missing_event"] += 1
        ctx = TheoryContext.build(conn, board, entry_for(week), run_id=run_id,
                                  run_mode="backtest")
        run = theory.start(ctx)
        preview = run.finish(dry_run=True)
        selected = [decision(item, week, run_id) for item in preview.scored]
        if len(selected) > 1:
            raise ValueError("more than one position in a target week")
        removed.update(preview.gate_removed)
        decisions.extend(selected)
        runs.append((run, selected, week))
        coverage.append({"week_end": week.isoformat(), "run_id": run_id,
                         "positions": len(selected), "events": len(events),
                         "entry_markets": len(board), "removed": dict(removed),
                         "funnel": preview.funnel})
        week += timedelta(days=7)
    freeze(campaign / "decisions.json", decisions)
    freeze(campaign / "evaluation_manifest.json", {
        "identity_digest": digest(campaign / "identity.json"),
        "decisions_digest": digest(campaign / "decisions.json"), "weeks": coverage,
    })
    return dataset, decisions, runs, coverage


def register(conn, campaign):
    from .data import entry_for
    notes = json.dumps({"protocol": "TRG-1", "source_validated": False,
                        "evaluation_manifest_digest": digest(campaign / "evaluation_manifest.json")},
                       sort_keys=True)
    for partition, start, end in (("development", START, SPLIT),
                                   ("holdout", SPLIT, END + timedelta(days=7))):
        run_id = RUN_PREFIX + partition
        expected = ("tsa_remainder_gap", 1, "A", 0, notes,
                    entry_for(start).isoformat(), entry_for(end).isoformat())
        existing = conn.execute(
            "SELECT theory_id,theory_version,tier,uses_llm_judgment,notes,as_of_start,as_of_end "
            "FROM backtest_runs WHERE run_id=?", (run_id,)).fetchone()
        if existing:
            if tuple(existing) != expected:
                raise ValueError("registered replay identity changed")
        else:
            score.record_backtest_run(conn, run_id, "tsa_remainder_gap", 1,
                tier="A", uses_llm_judgment=False, notes=notes,
                as_of_start=expected[-2], as_of_end=expected[-1])


def summarize(rows):
    settled, lower, upper = [], [], []
    for row in rows:
        known = row.get("result") in {"yes", "no"}
        won = float(row["side"] == row["result"]) if known else None
        cost = row["price"]*100 + fee_pts(row["price"])
        lower.append((won or 0)*100-cost)
        upper.append((won if known else 1)*100-cost)
        if known:
            settled.append({**row, "net": won*100-cost,
                "rounded_net": (won-row["price"]-order_fee_dollars(row["price"], 1))*100})
    intervals = {f"{axis}_{value}": cluster_interval(settled, value, axis)
                 for axis in ("week_end", "settlement_day") for value in ("net", "rounded_net")}
    return {"positions": len(rows), "settled": len(settled),
            "pending": len(rows)-len(settled), "source_validated": False, "supported": False,
            "mean_net_pts": mean(r["net"] for r in settled) if settled else None,
            "rounded_mean_net_pts": mean(r["rounded_net"] for r in settled) if settled else None,
            "intervals": intervals,
            "pending_net_bounds": [mean(lower), mean(upper)] if rows else None}


def settle(conn, decisions, dataset, now):
    raw_by_ticker = {raw["ticker"]: raw for e in dataset["events"] for raw in e["markets"]}
    rows = []
    for selected in decisions:
        raw = raw_by_ticker[selected["ticker"]]
        resolved = instant(raw.get("settlement_ts"))
        result = raw.get("result")
        entry = instant(selected["entry_time"])
        if result not in {"yes", "no"} or not resolved or not entry < resolved <= now:
            result, reason = None, "missing_binary_asof_settlement"
        else:
            existing = conn.execute("SELECT result FROM settlements WHERE kalshi_ticker=?",
                                    (selected["ticker"],)).fetchone()
            if existing and existing["result"] != result:
                raise ValueError("conflicting existing settlement")
            score.record_settlement(conn, selected["ticker"], result,
                                    resolved_at=resolved.isoformat(),
                                    settle_price=float(result == "yes"))
            reason = None
        rows.append({**selected, "result": result,
                     "settlement_day": resolved.date().isoformat() if result else None,
                     "pending_reason": reason})
    return rows


def replay(conn, campaign=CAMPAIGN, *, now=None, prepare_only=False):
    campaign = Path(campaign)
    dataset, decisions, runs, coverage = prepare(conn, campaign)
    if prepare_only:
        return {"prepared_positions": len(decisions), "calendar_weeks": len(coverage)}
    register(conn, campaign)
    for run, frozen, week in runs:
        actual = run.finish()
        if [decision(item, week, run.ctx.run_id) for item in actual.scored] != frozen:
            raise ValueError("recorded decisions differ from frozen decisions")
    rows = settle(conn, decisions, dataset, now or datetime.now(UTC))
    results = {"protocol": "TRG-1", "source_validated": False,
               "interpretation": "Experimental current-archive reconstruction; not production evidence.",
               "source_coverage": dataset["coverage"], "partitions": {}}
    for partition in ("development", "holdout"):
        run_id = RUN_PREFIX+partition
        selected = [r for r in rows if r["run_id"] == run_id]
        weeks = [r for r in coverage if r["run_id"] == run_id]
        removed = Counter()
        for week in weeks:
            removed.update(week["removed"])
        results["partitions"][partition] = {
            **summarize(selected), "calendar_weeks": len(weeks),
            "no_signal_weeks": sum(r["positions"] == 0 for r in weeks),
            "removed": dict(removed),
            "sides": {side: summarize([r for r in selected if r["side"] == side])
                      for side in ("yes", "no")},
            "ledger_score": score.compute_score(conn, "tsa_remainder_gap", 1,
                                                 "backtest", run_id=run_id),
        }
    atomic_write.write_json(campaign / "settled_decisions.json", rows)
    atomic_write.write_json(campaign / "results.json", results)
    lines = ["# TRG-1 archive diagnostic", "", results["interpretation"], ""]
    for name, part in results["partitions"].items():
        lines.append(f"- {name}: {part['positions']} entries / {part['calendar_weeks']} weeks; "
                     f"{part['pending']} pending; mean net {part['mean_net_pts']} points; "
                     f"rounded-fee net {part['rounded_mean_net_pts']} points.")
    lines += ["", "No parameter was tuned to these returns. See `results.json` for clustered "
              "intervals, sides, exclusion counts, pending bounds and ledger scores. "
              "The historical source-vintage limitation remains regardless of profit.", ""]
    atomic_write.write_text(campaign / "RESULTS.md", "\n".join(lines))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=CAMPAIGN)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args(argv)
    conn = db.connect()
    db.init_db(conn)
    result = replay(conn, args.campaign, prepare_only=args.prepare)
    print(json.dumps(result if args.prepare else {
        name: {k: v for k, v in part.items() if k not in {"ledger_score", "sides", "removed"}}
        for name, part in result["partitions"].items()}, indent=2))


if __name__ == "__main__":
    main()
