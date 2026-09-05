"""Complete-calendar chart replay; same ND-1 signal and immutable holdout."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from tools import db, score, theories
from tools.theory import TheoryContext
from . import analysis, data
from .backtest import ROOT, digest, records, save
from .collect_charts import SERIES
from .theory import NewsDriftTheory

CAMPAIGN = Path(__file__).resolve().parent / "backtests/nd1-charts-long-20260905"
TRAINING_END = "2026-05-01T00:00:00+00:00"
VALIDATION_END = "2026-09-01T00:00:00+00:00"
VALIDATION_RUN = "nd1-charts-long-20260905/holdout"


def timestamp(iso: str | None) -> int | None:
    if not iso:
        return None
    parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Historical timestamps must carry UTC offsets")
    return int(parsed.timestamp())


def freeze_manifest(campaign: Path) -> dict:
    """Freeze a complete source frame before reading any returns."""
    collected = json.loads((campaign / "manifest.json").read_text(encoding="utf-8"))
    if collected.get("coverage_complete") is not True:
        raise ValueError("Incomplete collection cannot be a clean validation replay")
    if set(collected["series"]) != set(SERIES):
        raise ValueError("Collected population differs from the preregistered six series")
    expected_start = timestamp("2026-01-01T00:00:00Z")
    expected_end = timestamp(VALIDATION_END)
    if (collected["window"]["start_ts"], collected["window"]["end_ts"]) != (expected_start, expected_end):
        raise ValueError("Collection window does not match the long protocol")
    exposed_path = campaign / "previously_exposed_events.json"
    exposed = json.loads(exposed_path.read_text(encoding="utf-8"))["event_tickers"]
    manifest = {
        "protocol": "ND-1", "source_digest": digest(campaign / "history.db"),
        "protocol_digest": digest(campaign / "PROTOCOL.md"),
        "collector_manifest_digest": digest(campaign / "manifest.json"),
        "categories_digest": digest(campaign / "series_categories.json"),
        "exposure_digest": digest(exposed_path),
        "population_series": list(SERIES), "population_complete": True,
        "training_end": TRAINING_END, "validation_start": TRAINING_END,
        "validation_end": VALIDATION_END, "run_id": VALIDATION_RUN,
        "confirmation_excluded_events": exposed,
        "coverage": {"markets": collected["markets"], "candles": collected["candles"]},
    }
    path = campaign / "replay_manifest.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != manifest:
        raise ValueError("Frozen replay source changed; do not reuse this holdout run")
    if not path.exists():
        save(path, manifest)
    return manifest


def decisions(campaign: Path, manifest: dict) -> list[dict]:
    """First valid signal per ticker; unresolved outcomes stay explicit."""
    categories = json.loads((campaign / "series_categories.json").read_text(encoding="utf-8"))["categories"]
    out = []
    counts = Counter()
    for raw, candles, category in records(campaign / "history.db", categories):
        theory = NewsDriftTheory(history_loader=lambda m, now: candles, calibration={})
        counts["tickers"] += 1
        for candle in candles[4:]:
            ts = candle["end_ts"]
            if ts >= timestamp(VALIDATION_END):
                break
            market = data.reconstruct(raw, candles, category, ts)
            if market is None:
                counts["not_open_or_invalid_entry"] += 1
                continue
            ctx = TheoryContext(None, [market], datetime.fromtimestamp(ts, timezone.utc),
                                run_id="exp/nd1-chart-enumeration", run_mode="backtest")
            screen = theory.screen(ctx)
            if not screen.candidates:
                continue
            candidate = screen.candidates[0]
            resolved = timestamp(raw.get("settlement_ts"))
            # Known trading availability, not an outcome/horizon screen.
            if resolved is not None and resolved <= ts:
                counts["already_settled_at_entry"] += 1
                continue
            result = raw.get("result") if resolved is not None else None
            if result not in {"yes", "no"}:
                result = None
            out.append({
                "ticker": raw["ticker"], "event_ticker": candidate.key,
                "series_ticker": raw["series_ticker"], "category": category,
                "entry_ts": ts, "side": candidate.fav_side,
                "entry_price": candidate.entry_price,
                "directional_mid": market.mid if candidate.fav_side == "yes" else 1 - market.mid,
                "reverse_price": market.no_ask if candidate.fav_side == "yes" else market.yes_ask,
                "resolved_ts": resolved, "result": result,
                "settlement_day": datetime.fromtimestamp(resolved, timezone.utc).date().isoformat() if resolved is not None else None,
            })
            break
    save(campaign / "decisions.json", {"source_digest": manifest["source_digest"],
                                       "funnel": dict(counts), "rows": out})
    return out


def artifact_for(campaign: Path, manifest: dict, rows: list[dict]) -> dict:
    artifact = analysis.fit_calibration(rows, cutoff_ts=timestamp(TRAINING_END),
                                        source_digest=manifest["source_digest"])
    artifact["population_series"] = list(SERIES)
    artifact["validation_plan"] = {
        "run_id": VALIDATION_RUN, "start": TRAINING_END, "end": VALIDATION_END,
        "source_digest": manifest["source_digest"],
        "protocol_digest": manifest["protocol_digest"],
        "population_series": list(SERIES), "usable_for_validation": True,
        "population_complete": True,
        "protocol_path": (campaign / "PROTOCOL.md").relative_to(ROOT).as_posix(),
        "manifest_path": (campaign / "replay_manifest.json").relative_to(ROOT).as_posix(),
        "manifest_digest": digest(campaign / "replay_manifest.json"),
    }
    save(campaign / "calibration_for_validation.json", artifact)
    return artifact


def replay(campaign: Path, conn) -> dict:
    manifest = freeze_manifest(campaign)
    rows = decisions(campaign, manifest)
    # Saved before fitting/reading returns: later verification can require the
    # exact holdout membership rather than accepting a cherry-picked run.
    membership = [{k: r[k] for k in ("ticker", "side", "entry_ts", "event_ticker")}
                  for r in rows if timestamp(TRAINING_END) <= r["entry_ts"] < timestamp(VALIDATION_END)]
    membership_path = campaign / "validation_membership.json"
    if membership_path.exists() and json.loads(membership_path.read_text(encoding="utf-8")) != membership:
        raise ValueError("Validation membership changed on replay")
    if not membership_path.exists():
        save(membership_path, membership)
    artifact = artifact_for(campaign, manifest, rows)
    artifact["validation_plan"]["membership_path"] = membership_path.relative_to(ROOT).as_posix()
    artifact["validation_plan"]["membership_digest"] = digest(membership_path)
    save(campaign / "calibration_for_validation.json", artifact)
    train = [r for r in rows if r["entry_ts"] < timestamp(TRAINING_END)
             and r["resolved_ts"] is not None and r["resolved_ts"] < timestamp(TRAINING_END)
             and r["result"] in {"yes", "no"}]
    holdout = [r for r in rows if timestamp(TRAINING_END) <= r["entry_ts"] < timestamp(VALIDATION_END)]
    categories = json.loads((campaign / "series_categories.json").read_text(encoding="utf-8"))["categories"]
    raw_map = {raw["ticker"]: (raw, candles, category)
               for raw, candles, category in records(campaign / "history.db", categories)}
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    summaries = {}
    excluded = set(manifest["confirmation_excluded_events"])
    for phase, selected, run_id in (("train", train, "exp/nd1-charts-long-20260905/train"),
                                     ("holdout", holdout, VALIDATION_RUN)):
        if not conn.execute("SELECT 1 FROM backtest_runs WHERE run_id=?", (run_id,)).fetchone():
            score.record_backtest_run(
                conn, run_id, "news_drift", 1, tier="A", uses_llm_judgment=False,
                as_of_start=TRAINING_END if phase == "holdout" else "2026-01-01",
                as_of_end=VALIDATION_END if phase == "holdout" else TRAINING_END,
                notes=f"Complete fixed-calendar chart cohort; {phase}. Protocol "
                      f"{manifest['protocol_digest']}; source {manifest['source_digest']}; "
                      f"{campaign.relative_to(ROOT).as_posix()}/PROTOCOL.md. "
                      "Prior-exposure sensitivity required; quotes have no historical depth.",
            )
        positives, count = [], 0
        for r in selected:
            raw, candles, category = raw_map[r["ticker"]]
            market = data.reconstruct(raw, candles, category, r["entry_ts"])
            theory = NewsDriftTheory(history_loader=lambda m, now: candles,
                                    calibration=artifact if phase == "holdout" else {})
            ctx = TheoryContext.build(conn, [market], datetime.fromtimestamp(r["entry_ts"], timezone.utc),
                                      run_id=run_id, run_mode="backtest")
            result = theory.start(ctx).finish()
            if len(result.opportunity_ids) != 1:
                raise AssertionError("Enumerated signal did not survive the actual replay")
            count += 1
            if result.scored[0].edge.pts_net > 0:
                positives.append(r)
            if r["result"] in {"yes", "no"}:
                existing = conn.execute("SELECT result FROM settlements WHERE kalshi_ticker=?", (r["ticker"],)).fetchone()
                if existing and existing["result"].lower() != r["result"]:
                    raise ValueError(f"Conflicting settlement for {r['ticker']}")
                if not existing:
                    score.record_settlement(conn, r["ticker"], r["result"],
                                            datetime.fromtimestamp(r["resolved_ts"], timezone.utc).isoformat())
        summaries[phase] = {"run_id": run_id, "recorded": count,
                            "all_signals": analysis.summarize(selected),
                            "positive_forecasts": analysis.summarize(positives),
                            "unexposed_all": analysis.summarize([r for r in selected if r["event_ticker"] not in excluded]),
                            "unexposed_positive_forecasts": analysis.summarize([r for r in positives if r["event_ticker"] not in excluded])}
    result = {"protocol": "ND-1", "phases": summaries, "calibration": artifact,
              "source_digest": manifest["source_digest"], "production_artifact_installed": False}
    save(campaign / "results.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", action="store_true")
    args = p.parse_args()
    if args.prepare:
        m = freeze_manifest(CAMPAIGN)
        print(json.dumps({k: v for k, v in m.items() if k != "confirmation_excluded_events"}, indent=2))
        return
    conn = db.connect()
    try:
        print(json.dumps(replay(CAMPAIGN, conn), indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
