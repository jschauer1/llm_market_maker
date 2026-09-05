"""Frozen WG-1-NWS legacy-source diagnostic.

This is an experiment lane over the immutable WG-1 source corpus.  It cannot
run live and its rows never enter the production evidence pool.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path

from tools import db, score
from tools.domain import ScreenResult
from tools.theory import TheoryContext

from . import analysis, backtest, data
from .stations import STATIONS
from .theory import WeatherModelGapTheory


UTC = timezone.utc
PROTOCOL = "WG-1-NWS"
SOURCE_POLICY = "nws"
RUN_ID = "exp/wg1-nws-20260905/holdout"
START = date(2026, 5, 1)
END = date(2026, 8, 14)
SOURCE_START = date(2026, 3, 1)
CAMPAIGN = Path(__file__).resolve().parent / "backtests" / "wg1-nws-20260905"
BASE_CAMPAIGN = Path(__file__).resolve().parent / "backtests" / "wg1-20260905"


def _canonical_digest(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _day(value) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _base_receipt(base_campaign: Path, dataset: dict) -> dict:
    receipt_path = base_campaign / "manifest.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        not receipt.get("completed_at")
        or receipt.get("source_digest") != dataset.get("source_digest")
        or receipt.get("protocol_digest") != dataset.get("protocol_digest")
    ):
        raise ValueError("base WG-1 collection is incomplete or changed")
    return receipt


def derive_dataset(
    campaign: Path = CAMPAIGN,
    base_campaign: Path = BASE_CAMPAIGN,
) -> tuple[dict, dict]:
    """Build an in-memory NWS label view without copying the raw corpus."""
    campaign, base_campaign = Path(campaign), Path(base_campaign)
    base = data.load_dataset(base_campaign)
    _base_receipt(base_campaign, base)
    protocol_path = campaign / "PROTOCOL.md"
    protocol_digest = analysis.digest(protocol_path)
    base_dataset_path = base_campaign / "dataset.json"
    base_dataset_digest = analysis.digest(base_dataset_path)

    events = []
    reasons: Counter[str] = Counter()
    by_series: Counter[str] = Counter()
    valid_by_series: Counter[str] = Counter()
    rules_identity = []
    for event in base["events"]:
        target = _day(event.get("target_date"))
        series = event.get("series_ticker")
        if (
            target is None
            or target < SOURCE_START
            or target >= END
            or series not in STATIONS
        ):
            continue
        markets = event.get("markets")
        if not isinstance(markets, list):
            markets = []
        label = data.normalize_label(
            markets, STATIONS[series], source_policy=SOURCE_POLICY
        )
        reason = label.get("reason") or "valid"
        reasons[f"{series}:{reason}"] += 1
        by_series[series] += 1
        if reason == "valid":
            valid_by_series[series] += 1
        for raw in markets:
            rules_identity.append({
                "event_ticker": event.get("event_ticker"),
                "ticker": raw.get("ticker"),
                "rules_primary": raw.get("rules_primary"),
                "rules_secondary": raw.get("rules_secondary"),
            })
        events.append({**event, "label": label})

    identity_core = {
        "protocol": PROTOCOL,
        "source_policy": SOURCE_POLICY,
        "base_dataset_path": str(base_dataset_path),
        "base_dataset_digest": base_dataset_digest,
        "base_source_digest": base["source_digest"],
        "base_protocol_digest": base["protocol_digest"],
        "protocol_digest": protocol_digest,
        "rules_fields": ["rules_primary", "rules_secondary"],
        "rules_digest": _canonical_digest(rules_identity),
    }
    derived_source_digest = _canonical_digest(identity_core)
    coverage = {
        "events": len(events),
        "events_by_series": dict(sorted(by_series.items())),
        "valid_labels_by_series": dict(sorted(valid_by_series.items())),
        "label_reasons": dict(sorted(reasons.items())),
        "source_start": SOURCE_START.isoformat(),
        "source_end_inclusive": (END - timedelta(days=1)).isoformat(),
    }
    identity = {
        **identity_core,
        "derived_source_digest": derived_source_digest,
        "coverage": coverage,
    }
    backtest.freeze(campaign / "derived_identity.json", identity)
    return {
        "events": events,
        "coverage": coverage,
        "source_digest": derived_source_digest,
        "protocol_digest": protocol_digest,
        "source_policy": SOURCE_POLICY,
    }, identity


class LegacyNWSDiagnosticTheory(WeatherModelGapTheory):
    """WG-1 with only its frozen settlement-source predicate replaced."""

    protocol = PROTOCOL
    source_policy = SOURCE_POLICY

    def _settlement_source_matches(self, raw, station) -> bool:
        return data.nws_source_rules_match(raw, station)

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        if ctx.run_mode != "backtest" or ctx.run_id != RUN_ID:
            return ScreenResult(
                (),
                {"board": len(ctx.board), "candidates": 0},
                {"experiment_scope": max(1, len(ctx.board))},
            )
        return super().screen(ctx)


def _decision(scored) -> dict:
    row = backtest.decision(scored)
    row.update(protocol=PROTOCOL, source_policy=SOURCE_POLICY)
    return row


def prepare(
    conn,
    campaign: Path = CAMPAIGN,
    base_campaign: Path = BASE_CAMPAIGN,
):
    """Freeze all holdout decisions before any returns are evaluated."""
    campaign = Path(campaign)
    dataset, identity = derive_dataset(campaign, base_campaign)
    theory = LegacyNWSDiagnosticTheory(dataset=dataset)
    decisions, runs = [], []
    gates: Counter[str] = Counter()
    funnel: Counter[str] = Counter()
    target = START
    while target < END:
        entry = datetime.combine(target, time.min, UTC)
        board = []
        for event in dataset["events"]:
            if event.get("target_date") != target.isoformat():
                continue
            for raw in event.get("markets", []):
                market, reason = backtest.reconstruct(
                    raw,
                    event,
                    event.get("candles", {}).get(raw.get("ticker"), []),
                    entry,
                )
                if reason:
                    gates[reason] += 1
                else:
                    board.append(market)
        ctx = TheoryContext.build(
            conn, board, entry, run_id=RUN_ID, run_mode="backtest"
        )
        run = theory.start(ctx)
        preview = run.finish(dry_run=True)
        selected = [_decision(item) for item in preview.scored]
        decisions.extend(selected)
        runs.append((run, selected))
        gates.update(preview.gate_removed)
        funnel.update(preview.funnel)
        target += timedelta(days=1)

    backtest.freeze(campaign / "decisions.json", decisions)
    manifest = {
        "protocol": PROTOCOL,
        "source_policy": SOURCE_POLICY,
        "run_id": RUN_ID,
        "derived_source_digest": dataset["source_digest"],
        "derived_identity_digest": analysis.digest(
            campaign / "derived_identity.json"
        ),
        "protocol_digest": analysis.digest(campaign / "PROTOCOL.md"),
        "decisions_digest": analysis.digest(campaign / "decisions.json"),
        "base_dataset_digest": identity["base_dataset_digest"],
        "rules_digest": identity["rules_digest"],
        "population_series": list(STATIONS),
        "entry_start": START.isoformat(),
        "entry_end_exclusive": END.isoformat(),
        "coverage": dataset["coverage"],
        "reconstruction_and_screen_removed": dict(gates),
        "funnel": dict(funnel),
    }
    backtest.freeze(campaign / "evaluation_manifest.json", manifest)
    return dataset, decisions, runs, manifest


def register(conn, campaign: Path, manifest: dict) -> None:
    notes = json.dumps({
        "protocol": PROTOCOL,
        "source_policy": SOURCE_POLICY,
        "evaluation_manifest_digest": analysis.digest(
            campaign / "evaluation_manifest.json"
        ),
        "derived_source_digest": manifest["derived_source_digest"],
        "base_dataset_digest": manifest["base_dataset_digest"],
    }, sort_keys=True)
    existing = conn.execute(
        "SELECT theory_id,theory_version,tier,uses_llm_judgment,notes "
        "FROM backtest_runs WHERE run_id=?",
        (RUN_ID,),
    ).fetchone()
    expected = ("weather_model_gap", 1, "A", 0, notes)
    if existing:
        if tuple(existing) != expected:
            raise ValueError("registered NWS diagnostic identity changed")
        return
    score.record_backtest_run(
        conn,
        RUN_ID,
        "weather_model_gap",
        1,
        as_of_start="2026-05-01T00:00:00Z",
        as_of_end="2026-08-14T00:00:00Z",
        tier="A",
        uses_llm_judgment=False,
        notes=notes,
    )


def _resolved_result(selected, event, now: datetime) -> tuple[str | None, str | None, str | None]:
    label = data.normalize_label(
        event.get("markets", []),
        STATIONS[selected["series_ticker"]],
        source_policy=SOURCE_POLICY,
    )
    resolved = backtest._instant(label.get("resolved_at"))
    entry = datetime.combine(
        date.fromisoformat(selected["target_date"]), time.min, UTC
    )
    raw = next(
        row for row in event["markets"] if row.get("ticker") == selected["ticker"]
    )
    result = raw.get("result") if resolved and entry < resolved <= now else None
    if result not in {"yes", "no"}:
        result = None
    return (
        result,
        resolved.date().isoformat() if resolved else None,
        label.get("reason") if result is None else None,
    )


def _upper_below_three(summary: dict) -> bool:
    intervals = [
        summary[axis].get("interval")
        for axis in ("event", "day", "settlement_day")
    ]
    return bool(intervals) and all(
        interval is not None and interval[1] < 3.0 for interval in intervals
    )


def _results_markdown(results: dict) -> str:
    lines = [
        "# WG-1-NWS legacy diagnostic results",
        "",
        "This experiment measures only the archived NWS settlement regime. "
        "It cannot validate current TWC contracts.",
        "",
        "| Population | Known / selected | Net pts | One-contract net pts | Supported |",
        "|---|---:|---:|---:|---|",
    ]
    groups = [("Pooled", results["pooled"]), *[
        (series, results["cities"][series]) for series in STATIONS
    ]]
    for name, summary in groups:
        net = "n/a" if summary["net_pts"] is None else f"{summary['net_pts']:.2f}"
        one = (
            "n/a" if summary["net_one_contract_pts"] is None
            else f"{summary['net_one_contract_pts']:.2f}"
        )
        lines.append(
            f"| {name} | {summary['n']} / {summary['total_n']} | "
            f"{net} | {one} | {summary['supported']} |"
        )
    lines.extend([
        "",
        f"Coverage: {json.dumps(results['coverage'], sort_keys=True)}",
        "",
        f"Frozen gate removals: {json.dumps(results['gate_removed'], sort_keys=True)}",
        "",
        "Interpretation: " + results["interpretation"],
        "",
    ])
    return "\n".join(lines)


def replay(
    conn,
    campaign: Path = CAMPAIGN,
    base_campaign: Path = BASE_CAMPAIGN,
    *,
    now: datetime | None = None,
) -> dict:
    dataset, decisions, runs, manifest = prepare(conn, campaign, base_campaign)
    register(conn, Path(campaign), manifest)
    for run, frozen in runs:
        actual = run.finish()
        if [_decision(item) for item in actual.scored] != frozen:
            raise ValueError("recorded NWS decisions diverge from frozen preview")

    event_by_key = {
        event["event_ticker"]: event for event in dataset["events"]
    }
    rows = []
    now = (now or datetime.now(UTC)).astimezone(UTC)
    for selected in decisions:
        event = event_by_key[selected["event_ticker"]]
        result, settlement_day, pending_reason = _resolved_result(
            selected, event, now
        )
        if result:
            existing = conn.execute(
                "SELECT result FROM settlements WHERE kalshi_ticker=?",
                (selected["ticker"],),
            ).fetchone()
            if existing and existing["result"] != result:
                raise ValueError("conflicting existing settlement")
            raw = next(
                row for row in event["markets"]
                if row.get("ticker") == selected["ticker"]
            )
            resolved = backtest._instant(raw.get("settlement_ts"))
            score.record_settlement(
                conn,
                selected["ticker"],
                result,
                resolved_at=resolved.isoformat(),
                settle_price=float(result == "yes"),
            )
        rows.append({
            **selected,
            "result": result,
            "settlement_day": settlement_day,
            "pending_reason": pending_reason,
        })

    pooled = analysis.summarize(rows)
    cities = {
        series: analysis.summarize(
            [row for row in rows if row["series_ticker"] == series], city=True
        )
        for series in STATIONS
    }
    confirmed = pooled["supported"] or any(
        result["supported"] for result in cities.values()
    )
    ruled_out = _upper_below_three(pooled)
    if confirmed:
        interpretation = (
            "Legacy NWS evidence is positive enough to justify a separately "
            "specified NWS-to-TWC source-equivalence study; it does not "
            "authorize current recommendations."
        )
    elif ruled_out:
        interpretation = (
            "The frozen legacy population is unconfirmed and its pooled "
            "cluster intervals rule out a +3 point net effect. Stop without "
            "retuning."
        )
    else:
        interpretation = (
            "The frozen legacy population is unconfirmed and remains too "
            "uncertain to rule out a +3 point effect. Stop without retuning."
        )
    results = {
        "protocol": PROTOCOL,
        "source_policy": SOURCE_POLICY,
        "run_id": RUN_ID,
        "coverage": manifest["coverage"],
        "pooled": pooled,
        "cities": cities,
        "ledger_score": score.compute_score(
            conn, "weather_model_gap", 1, "backtest", run_id=RUN_ID
        ),
        "gate_removed": manifest["reconstruction_and_screen_removed"],
        "practically_large_effect_ruled_out": ruled_out,
        "interpretation": interpretation,
    }
    backtest.save(Path(campaign) / "results.json", results)
    backtest.save(Path(campaign) / "settled_decisions.json", rows)
    (Path(campaign) / "RESULTS.md").write_text(
        _results_markdown(results), encoding="utf-8"
    )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=CAMPAIGN)
    parser.add_argument("--base-campaign", type=Path, default=BASE_CAMPAIGN)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args(argv)
    conn = db.connect()
    try:
        if args.prepare:
            _, decisions, _, manifest = prepare(
                conn, args.campaign, args.base_campaign
            )
            payload = {
                "status": "frozen",
                "decisions": len(decisions),
                "coverage": manifest["coverage"],
                "gate_removed": manifest["reconstruction_and_screen_removed"],
            }
        else:
            payload = replay(conn, args.campaign, args.base_campaign)
        print(json.dumps(payload, sort_keys=True))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
