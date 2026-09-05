"""Collect, execute, and record one WG-1 live observation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from tools import db, slices, theories
from tools.domain import Market
from tools.http import get_json
from tools.theory import TheoryContext

from .live import CaptureFetch, collect_live, load_live_dataset
from .theory import WeatherModelGapTheory


UTC = timezone.utc
MAX_QUOTE_AGE_SECONDS = 1800


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("recording time must be timezone-aware")
    return value.astimezone(UTC)


_DECLARED_CITY_SLICES = (
    (
        "nyc",
        {"extra": {"series_ticker": "KXHIGHNY"}},
        "New York has its own station-specific forecast-error calibration.",
    ),
    (
        "lax",
        {"extra": {"series_ticker": "KXHIGHLAX"}},
        "Los Angeles has its own station-specific forecast-error calibration.",
    ),
    (
        "chicago",
        {"extra": {"series_ticker": "KXHIGHCHI"}},
        "Chicago has its own station-specific forecast-error calibration.",
    ),
)


def _slice_specs(conn) -> list[tuple[str, dict, str, str]]:
    registered = {}
    ordered = []
    for row in slices.list_slices(conn, WeatherModelGapTheory.id):
        spec = (
            row["slug"],
            json.loads(row["predicate_json"]),
            row["hypothesis"],
            row["status"],
        )
        registered[row["slug"]] = spec
        ordered.append(spec)
    specs = [
        registered.get(slug, (slug, predicate, reason, "declared"))
        for slug, predicate, reason in _DECLARED_CITY_SLICES
    ]
    specs.extend(spec for spec in ordered if spec[0] not in {
        slug for slug, _, _ in _DECLARED_CITY_SLICES
    })
    return specs


def _segment_row(scored) -> dict:
    candidate = scored.candidate
    if candidate.is_basket:
        return {"position_kind": "basket", "extra": scored.extra or {}}
    leg = candidate.legs[0]
    return {
        "position_kind": "single",
        "outcome": leg.side,
        "confidence": scored.confidence,
        "entry_price": leg.price,
        "extra": scored.extra or {},
    }


def _segments(conn, scored, opportunity_ids) -> list[dict]:
    rows = list(zip(scored, opportunity_ids))

    def summary(segment: str, selected, *, reason=None, status=None):
        return {
            "segment": segment,
            "reason": reason,
            "status": status,
            "candidates": len(selected),
            "recorded": len(selected),
            "model_supported": sum(
                row.edge.basis == "model" for row, _ in selected
            ),
            "prior_observations": sum(
                row.edge.basis == "prior" for row, _ in selected
            ),
            "opportunity_ids": [opp_id for _, opp_id in selected],
        }

    output = [summary(
        "parent",
        rows,
        reason="All WG-1 station-day recommendations.",
        status="parent",
    )]
    for slug, predicate, reason, status in _slice_specs(conn):
        matcher = slices.build_matcher(predicate)
        selected = [row for row in rows if matcher(_segment_row(row[0]))]
        output.append(summary(
            slug, selected, reason=reason, status=status
        ))
    return output


def _recorded_station_dates(
    conn, decision_date: str
) -> set[tuple[str, str]]:
    rows = conn.execute(
        """SELECT a.extra_json
             FROM opportunity_attempts a
            JOIN opportunities o ON o.id=a.opportunity_id
            WHERE o.theory_id='weather_model_gap'
              AND o.run_mode='live'
              AND a.decision_date=?""",
        (decision_date,),
    ).fetchall()
    keys = set()
    for row in rows:
        try:
            extra = json.loads(row[0] or "{}")
        except (TypeError, ValueError):
            continue
        series, target = extra.get("series_ticker"), extra.get("target_date")
        if isinstance(series, str) and isinstance(target, str):
            keys.add((series, target))
    return keys


def record_collection(
    conn,
    collection: dict,
    *,
    now: datetime | None = None,
    dataset=None,
    validation_check=None,
) -> dict:
    """Replay retained live inputs through the normal contract and record."""
    if collection.get("status") == "outside_entry_window":
        return {
            "status": "outside_entry_window",
            "opportunity_ids": [],
            "duplicate_station_dates": 0,
            "segments": _segments(conn, [], []),
            "funnel": dict(collection.get("funnel") or {}),
        }
    if collection.get("status") != "complete" or collection.get("protocol") != "WG-1":
        raise ValueError("collection is not a complete WG-1 artifact")
    recorded_at = _utc(now or datetime.now(UTC))
    quoted = datetime.fromisoformat(
        collection["quote_fetch_completed_at"].replace("Z", "+00:00")
    )
    quoted = _utc(quoted)
    if (
        quoted.hour != 0
        or recorded_at.hour != 0
        or quoted.date() != recorded_at.date()
    ):
        raise ValueError("collection is outside the WG-1 entry window")
    age = (recorded_at - quoted).total_seconds()
    if not 0 <= age <= MAX_QUOTE_AGE_SECONDS:
        raise ValueError("collection quotes are stale or future-dated")
    if collection.get("target_date") != quoted.date().isoformat():
        raise ValueError("collection target date does not match quote date")

    if dataset is None:
        dataset = load_live_dataset(collection["dataset_path"])
    if dataset.get("source_digest") != collection.get("dataset_source_digest"):
        raise ValueError("collection dataset source digest changed")
    board = [Market.from_mapping(row) for row in collection.get("board", [])]
    capture_fetch = CaptureFetch(
        Path(collection["capture_dir"]) / "http",
        get_json,
        lambda: recorded_at,
        allow_network=False,
    )
    theory = WeatherModelGapTheory(
        dataset=dataset,
        validation_check=validation_check,
        fetch=capture_fetch,
    )
    ctx = TheoryContext.build(
        conn,
        board,
        quoted,
        run_id=f"wg1-live-{quoted.strftime('%Y%m%dT%H%M%SZ')}",
        run_mode="live",
    )
    run = theory.start(ctx)
    theories.register(
        conn,
        WeatherModelGapTheory.id,
        WeatherModelGapTheory.name,
        "theories/weather_model_gap",
    )
    with db.write(conn):
        conn.execute("BEGIN IMMEDIATE")
        seen = _recorded_station_dates(conn, quoted.date().isoformat())
        kept = []
        duplicates = 0
        for candidate in run.candidates:
            extra = candidate.legs[0].market.raw.get("_weather_model_gap") or {}
            key = (extra.get("series_ticker"), extra.get("target_date"))
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            kept.append(candidate)
        run.candidates = kept
        if duplicates:
            run.screen_result.gate_removed[
                "already_recorded_station_date"
            ] = duplicates
        result = run.finish()
    return {
        "status": "recorded",
        "quote_time": quoted.isoformat(),
        "opportunity_ids": list(result.opportunity_ids),
        "duplicate_station_dates": duplicates,
        "funnel": result.funnel,
        "gate_removed": result.gate_removed,
        "segments": _segments(conn, result.scored, result.opportunity_ids),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.collection:
            path = args.collection
            collection = json.loads(path.read_text(encoding="utf-8"))
        else:
            collection = collect_live(data_dir=args.data_dir)
            path = (Path(collection["capture_dir"]) / "collection.json"
                    if collection.get("capture_dir") else None)
        conn = db.connect()
        try:
            summary = record_collection(conn, collection)
        finally:
            conn.close()
        if path is not None:
            recorded_path = path.with_suffix(".recorded.json")
            recorded_path.write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            summary["recorded_summary"] = str(recorded_path)
        print(json.dumps(summary, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "stopped", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
