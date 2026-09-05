"""WG-1 exact-entry replay. Freeze decisions before recording any returns."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import json
import math
from pathlib import Path

from tools import db, score
from tools.domain import Market
from tools.theory import TheoryContext
from . import analysis, data
from .stations import STATIONS
from .theory import WeatherModelGapTheory

UTC = timezone.utc
START, END = date(2026, 7, 1), date(2026, 9, 1)


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def freeze(path: Path, value) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError(f"Frozen {path.name} changed; declare another campaign")
    else:
        save(path, value)


def _instant(value) -> datetime | None:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo else None
    except (TypeError, ValueError, AttributeError):
        return None


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def reconstruct(raw: dict, event: dict, candles: list, entry: datetime):
    """Future payload fields cannot provide a quote, activity or selection feature."""
    opened, closed = _instant(raw.get("open_time")), _instant(raw.get("close_time"))
    if opened is None or closed is None or not opened <= entry < closed:
        return None, "not_open_at_entry"
    exact = [c for c in candles if c.get("end_ts") == int(entry.timestamp())]
    if len(exact) != 1:
        return None, "entry_candle_missing"
    candle = exact[0]
    bid, ask = _number(candle.get("yes_bid_close")), _number(candle.get("yes_ask_close"))
    if bid is None or ask is None or not 0 <= bid <= ask <= 1:
        return None, "invalid_quote"
    volume, oi = _number(candle.get("volume")), _number(candle.get("open_interest"))
    # Scheduled end of the station's standard day, not terminal close proximity.
    close = entry + timedelta(days=1, hours=-STATIONS[event["series_ticker"]]["standard_utc_offset_hours"])
    fields = {k: raw.get(k) for k in (
        "ticker", "event_ticker", "title", "rules_primary", "rules_secondary",
        "strike_type", "floor_strike", "cap_strike", "open_time")}
    fields.update(series_ticker=event["series_ticker"],
                  _wg1_entry_ts=int(entry.timestamp()), _wg1_entry_volume=volume)
    return Market(
        platform="kalshi", ticker=raw["ticker"], title=raw.get("title"),
        yes_bid=bid, yes_ask=ask, no_bid=1-ask, no_ask=1-bid,
        mid=(bid+ask)/2, spread=ask-bid, volume=volume, volume_24h=volume,
        open_interest=oi, status="active", is_open=True,
        open_time=opened.isoformat(), close_time=close.isoformat(),
        rules_primary=raw.get("rules_primary"), event_ticker=event["event_ticker"],
        series_ticker=event["series_ticker"], raw=fields,
    ), None


def decision(scored) -> dict:
    c, extra = scored.candidate, scored.extra
    return dict(ticker=c.ticker, side=c.fav_side, entry_price=c.entry_price,
                model_prob=scored.edge.model_prob,
                **{key: extra[key] for key in (
                    "target_date", "series_ticker", "event_ticker", "training_n",
                    "forecast_run", "forecast_proxy", "source_digest", "forecast_source_digest")})


def prepare(conn, campaign: Path):
    dataset = data.load_dataset(campaign)
    receipt = json.loads((campaign / "manifest.json").read_text(encoding="utf-8"))
    if (not receipt.get("completed_at") or receipt["source_digest"] != dataset["source_digest"]
            or receipt["protocol_digest"] != dataset["protocol_digest"]):
        raise ValueError("Source collection is incomplete or identity changed")
    theory = WeatherModelGapTheory(dataset=dataset)
    rows, runs, gates, funnel = [], [], Counter(), Counter()
    target = START
    while target < END:
        entry = datetime.combine(target, time.min, UTC)
        board = []
        for event in dataset["events"]:
            if event["target_date"] != target.isoformat():
                continue
            for raw in event["markets"]:
                market, reason = reconstruct(raw, event, event["candles"].get(raw["ticker"], []), entry)
                if reason:
                    gates[reason] += 1
                else:
                    board.append(market)
        ctx = TheoryContext.build(conn, board, entry, run_id=analysis.RUN_ID, run_mode="backtest")
        run = theory.start(ctx)
        preview = run.finish(dry_run=True)
        chosen = [decision(item) for item in preview.scored]
        rows.extend(chosen)
        runs.append((run, chosen))
        gates.update(preview.gate_removed)
        funnel.update(preview.funnel)
        target += timedelta(days=1)
    freeze(campaign / "decisions.json", rows)
    manifest = dict(protocol="WG-1", run_id=analysis.RUN_ID,
                    source_digest=dataset["source_digest"], protocol_digest=dataset["protocol_digest"],
                    dataset_digest=analysis.digest(campaign / "dataset.json"),
                    decisions_digest=analysis.digest(campaign / "decisions.json"),
                    population_series=sorted(STATIONS), entry_start=START.isoformat(),
                    entry_end_exclusive=END.isoformat(), coverage=dataset["coverage"],
                    reconstruction_and_screen_removed=dict(gates), funnel=dict(funnel))
    freeze(campaign / "evaluation_manifest.json", manifest)
    return dataset, rows, runs, manifest


def register(conn, campaign: Path, manifest: dict):
    notes = json.dumps({"protocol": "WG-1",
                        "evaluation_manifest_digest": analysis.digest(campaign / "evaluation_manifest.json"),
                        "dataset_digest": manifest["dataset_digest"]}, sort_keys=True)
    existing = conn.execute("SELECT theory_id,theory_version,tier,uses_llm_judgment,notes "
                            "FROM backtest_runs WHERE run_id=?", (analysis.RUN_ID,)).fetchone()
    if existing:
        if tuple(existing) != ("weather_model_gap", 1, "A", 0, notes):
            raise ValueError("Registered campaign identity changed")
        return
    score.record_backtest_run(conn, analysis.RUN_ID, "weather_model_gap", 1,
                             as_of_start="2026-07-01T00:00:00Z", as_of_end="2026-09-01T00:00:00Z",
                             tier="A", uses_llm_judgment=False, notes=notes)


def replay(conn, campaign: Path):
    dataset, decisions, runs, manifest = prepare(conn, campaign)
    register(conn, campaign, manifest)
    for run, frozen in runs:
        actual = run.finish()
        if [decision(item) for item in actual.scored] != frozen:
            raise ValueError("Recorded decisions diverge from the frozen preview")
    by_event = {e["event_ticker"]: e for e in dataset["events"]}
    rows = []
    now = datetime.now(UTC)
    for selected in decisions:
        event = by_event[selected["event_ticker"]]
        raw = next(m for m in event["markets"] if m["ticker"] == selected["ticker"])
        label = data.normalize_label(event["markets"], STATIONS[selected["series_ticker"]])
        resolved = _instant(label.get("resolved_at"))
        entry = datetime.combine(date.fromisoformat(selected["target_date"]), time.min, UTC)
        result = raw.get("result") if resolved and entry < resolved <= now else None
        if result not in {"yes", "no"}:
            result = None
        if result:
            existing = conn.execute("SELECT result FROM settlements WHERE kalshi_ticker=?",
                                    (selected["ticker"],)).fetchone()
            if existing and existing["result"] != result:
                raise ValueError("Conflicting existing settlement")
            score.record_settlement(conn, selected["ticker"], result,
                                    resolved_at=resolved.isoformat(), settle_price=float(result == "yes"))
        rows.append(dict(selected, result=result,
                         settlement_day=resolved.date().isoformat() if resolved else None,
                         pending_reason=label.get("reason") if result is None else None))
    results = dict(protocol="WG-1", run_id=analysis.RUN_ID, coverage=manifest["coverage"],
                   pooled=analysis.summarize(rows),
                   ledger_score=score.compute_score(conn, "weather_model_gap", 1,
                                                    "backtest", run_id=analysis.RUN_ID),
                   cities={series: analysis.summarize(
                       [r for r in rows if r["series_ticker"] == series], city=True) for series in STATIONS},
                   gate_removed=manifest["reconstruction_and_screen_removed"])
    save(campaign / "results.json", results)
    save(campaign / "settled_decisions.json", rows)
    for series, summary in results["cities"].items():
        if analysis.production_ready(conn, series, campaign=campaign) != summary["supported"]:
            raise ValueError(f"Production proof disagrees with replay for {series}")
    score.save_segment_scores(conn, "weather_model_gap", 1)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=analysis.CAMPAIGN)
    parser.add_argument("--prepare", action="store_true", help="Freeze decisions without settlements/returns")
    args = parser.parse_args()
    conn = db.connect()
    if args.prepare:
        _, rows, _, manifest = prepare(conn, args.campaign)
        print(json.dumps(dict(decisions=len(rows), gates=manifest["reconstruction_and_screen_removed"]), indent=2))
    else:
        print(json.dumps(replay(conn, args.campaign), indent=2))


if __name__ == "__main__":
    main()
