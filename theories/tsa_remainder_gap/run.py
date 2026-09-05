"""Capture and record the Friday TRG-1 TSA remainder observation."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable, Mapping

import requests

from tools import board as board_store
from tools import db, slices, theories
from tools.domain import Market
from tools.http import get_json
from tools.kalshi import markets as kalshi_markets
from tools.theory import TheoryContext

from .data import entry_for, parse_contract, parse_tsa_html
from .model import PROTOCOL
from .theory import TsaRemainderGapTheory


UTC = timezone.utc
MAX_AGE_SECONDS = 1800
ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data" / "live"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("time must be timezone-aware")
    return value.astimezone(UTC)


def _in_window(value: datetime) -> bool:
    return value.weekday() == 4 and value.hour == 15 and value.minute < 30


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("collection timestamp is missing")
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError as exc:
        raise ValueError("collection timestamp is invalid") from exc


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_once(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"immutable live capture changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _write_json_once(path: Path, value: object) -> None:
    _write_once(path, json.dumps(value, indent=2, sort_keys=True).encode("utf-8") + b"\n")


def _get_html(url: str) -> bytes:
    response = requests.get(
        url, timeout=30, headers={"User-Agent": "market-edge-finder/1.0"}
    )
    response.raise_for_status()
    return response.content


class _CaptureFetch:
    def __init__(self, root: Path, fetch: Callable):
        self.root = root
        self.fetch = fetch
        self.orderbooks: dict[str, object] = {}

    def __call__(self, url: str, params: dict | None = None, timeout: int = 30):
        request = {"url": url, "params": dict(params or {})}
        path = self.root / f"{_sha_bytes(_canonical(request))}.json"
        if path.exists():
            wrapper = json.loads(path.read_text(encoding="utf-8"))
            if wrapper.get("request") != request:
                raise ValueError("captured request identity changed")
            response = wrapper["response"]
        else:
            response = self.fetch(url, params=params, timeout=timeout)
            _write_json_once(path, {"request": request, "response": response})
        if url.endswith("/orderbook"):
            self.orderbooks[url.rsplit("/", 2)[-2]] = response
        return response


def _source_url(year: int, current_year: int) -> str:
    if year == current_year:
        return "https://www.tsa.gov/travel/passenger-volumes"
    return f"https://www.tsa.gov/travel/passenger-volumes/{year}"


def collect_live(
    conn,
    *,
    now: datetime | None = None,
    fetch=None,
    fetch_html=None,
    clock=None,
    data_dir: str | Path | None = None,
    out_path: str | Path | None = None,
) -> dict:
    """Retain fresh TSA pages, quotes and finalist order books."""
    started = _utc(now or datetime.now(UTC))
    if not _in_window(started):
        return {
            "status": "outside_entry_window", "protocol": PROTOCOL,
            "as_of": started.isoformat(), "funnel": {"board": 0, "candidates": 0},
        }
    fetch = fetch or get_json
    fetch_html = fetch_html or _get_html
    clock = clock or (lambda: datetime.now(UTC))
    target = started.date() + timedelta(days=2)
    root = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    capture_dir = root / started.strftime("trg1-%Y%m%dT%H%M%SZ")
    artifact_path = capture_dir / "collection.json"
    if artifact_path.exists():
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    earliest = target - timedelta(days=7 * 52 + 6)
    counts: dict[str, int] = {}
    receipts = []
    for year in range(earliest.year, target.year + 1):
        url = _source_url(year, target.year)
        path = capture_dir / "source" / f"tsa-{year}.html"
        if not path.exists():
            _write_once(path, bytes(fetch_html(url)))
        payload = path.read_bytes()
        # Receipt is durable before any value from it reaches the model.
        receipt = {
            "path": str(path.resolve()), "url": url,
            "sha256": _sha_bytes(payload), "year": year,
        }
        receipts.append(receipt)
        for day, value in parse_tsa_html(payload.decode("utf-8"), year).items():
            if day in counts and counts[day] != value:
                raise ValueError(f"conflicting TSA count for {day}")
            counts[day] = value
    source_completed = _utc(clock())
    source_digest = _sha_bytes(_canonical([
        {"url": row["url"], "sha256": row["sha256"]} for row in receipts
    ]))

    shared_board = board_store.get_board(conn)
    structural: list[tuple[Market, dict]] = []
    for market in shared_board:
        raw = dict(market.raw) if isinstance(market.raw, Mapping) else {}
        candidate_raw = dict(raw)
        candidate_raw.setdefault("event_ticker", market.event_ticker)
        candidate_raw.setdefault("open_time", market.open_time)
        candidate_raw.setdefault("rules_primary", market.rules_primary)
        parsed, _ = parse_contract(candidate_raw)
        if parsed and parsed["week_end"] == target:
            structural.append((market, parsed))

    capture_fetch = _CaptureFetch(capture_dir / "http", fetch)
    fresh = kalshi_markets.quotes(
        sorted({market.ticker for market, _ in structural}), fetch=capture_fetch
    )
    quoted = _utc(clock())
    point_board = []
    collection_removed: dict[str, int] = {}
    for market, parsed in structural:
        quote = fresh.get(market.ticker)
        if quote is None:
            collection_removed["fresh_quote_missing"] = (
                collection_removed.get("fresh_quote_missing", 0) + 1
            )
            continue
        current_raw = dict(quote.raw) if isinstance(quote.raw, Mapping) else {}
        current_raw.setdefault("event_ticker", quote.event_ticker)
        current_raw.setdefault("open_time", quote.open_time)
        current_raw.setdefault("rules_primary", quote.rules_primary)
        current_contract, _ = parse_contract(current_raw)
        if current_contract is None or current_contract["week_end"] != target:
            collection_removed["fresh_contract_invalid"] = (
                collection_removed.get("fresh_contract_invalid", 0) + 1
            )
            continue
        raw = dict(current_raw)
        raw.update({
            "week_end": target.isoformat(), "strike": current_contract["strike"],
            "entry_time": entry_for(target).isoformat(),
            "source_digest": source_digest,
        })
        point_board.append(replace(
            quote,
            event_ticker=quote.event_ticker or market.event_ticker,
            series_ticker=quote.series_ticker or market.series_ticker,
            title=quote.title or market.title,
            raw=raw,
        ))

    ctx = TheoryContext(
        conn=None, board=point_board, now=quoted,
        run_id=f"live/trg1-{started.strftime('%Y%m%dT%H%M%SZ')}",
        run_mode="live",
    )
    dry = TsaRemainderGapTheory(counts, fetch=capture_fetch).start(ctx).finish(dry_run=True)
    artifact = {
        "status": "complete", "protocol": PROTOCOL,
        "as_of": started.isoformat(), "week_end": target.isoformat(),
        "source_fetch_completed_at": source_completed.isoformat(),
        "quote_fetch_completed_at": quoted.isoformat(),
        "source_digest": source_digest, "source_receipts": receipts,
        "daily_counts": counts,
        "board": [asdict(market) for market in point_board],
        "orderbooks": capture_fetch.orderbooks,
        "funnel": dry.funnel,
        "gate_removed": {
            key: collection_removed.get(key, 0) + dry.gate_removed.get(key, 0)
            for key in set(collection_removed) | set(dry.gate_removed)
        },
        "signals": [
            {
                "ticker": row.candidate.ticker,
                "side": row.candidate.fav_side,
                "entry_price": row.candidate.entry_price,
                "model_prob": row.edge.model_prob,
            }
            for row in dry.scored
        ],
        "capture_dir": str(capture_dir.resolve()),
        "collection_path": str(artifact_path.resolve()),
    }
    _write_json_once(artifact_path, artifact)
    if out_path is not None and Path(out_path).resolve() != artifact_path.resolve():
        _write_json_once(Path(out_path), artifact)
    return artifact


def _captured_fetch(orderbooks: Mapping[str, object]):
    def fetch(url: str, params=None, timeout=30):
        if not url.endswith("/orderbook"):
            raise ValueError("retained collection only permits orderbook reads")
        ticker = url.rsplit("/", 2)[-2]
        if ticker not in orderbooks:
            raise KeyError(ticker)
        return orderbooks[ticker]
    return fetch


def _reparse_source(collection: Mapping) -> dict[str, int]:
    receipts = collection.get("source_receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ValueError("TSA source receipts are required")
    counts: dict[str, int] = {}
    identities = []
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            raise ValueError("TSA source receipt is invalid")
        path = Path(str(receipt.get("path") or ""))
        year = receipt.get("year")
        url = receipt.get("url")
        if isinstance(year, bool) or not isinstance(year, int) or not isinstance(url, str):
            raise ValueError("TSA source receipt year/url is invalid")
        if not path.is_file():
            raise ValueError("TSA source receipt is missing or changed")
        payload = path.read_bytes()
        digest = _sha_bytes(payload)
        if digest != receipt.get("sha256"):
            raise ValueError("TSA source receipt is missing or changed")
        identities.append({"url": url, "sha256": digest})
        for day, value in parse_tsa_html(payload.decode("utf-8"), year).items():
            if day in counts and counts[day] != value:
                raise ValueError(f"conflicting TSA count for {day}")
            counts[day] = value
    derived_digest = _sha_bytes(_canonical(identities))
    if derived_digest != collection.get("source_digest"):
        raise ValueError("source digest does not match TSA receipts")
    if counts != collection.get("daily_counts"):
        raise ValueError("daily counts do not match TSA source receipts")
    return counts


def _recorded_weeks(conn) -> set[str]:
    rows = conn.execute(
        """SELECT a.extra_json
             FROM opportunity_attempts a
             JOIN opportunities o ON o.id=a.opportunity_id
            WHERE o.theory_id=? AND o.run_mode='live'""",
        (TsaRemainderGapTheory.id,),
    ).fetchall()
    output = set()
    for row in rows:
        try:
            extra = json.loads(row[0] or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(extra.get("week_end"), str):
            output.add(extra["week_end"])
    return output


def _segments(conn, scored, opportunity_ids) -> list[dict]:
    paired = list(zip(scored, opportunity_ids))
    output = [{
        "segment": "parent", "candidates": len(paired),
        "opportunity_ids": [opportunity_id for _, opportunity_id in paired],
    }]
    for spec in slices.list_slices(conn, TsaRemainderGapTheory.id):
        matcher = slices.build_matcher(json.loads(spec["predicate_json"]))
        selected = [
            pair for pair in paired if matcher({
                "outcome": pair[0].candidate.fav_side,
                "entry_price": pair[0].candidate.entry_price,
                "confidence": pair[0].confidence,
                "extra": pair[0].extra or {},
            })
        ]
        output.append({
            "segment": spec["slug"], "status": spec["status"],
            "reason": spec["hypothesis"], "candidates": len(selected),
            "opportunity_ids": [opportunity_id for _, opportunity_id in selected],
        })
    return output


def record_collection(conn, collection: dict, *, now: datetime | None = None) -> dict:
    """Validate a retained live collection and record at most one week."""
    if collection.get("status") == "outside_entry_window":
        return {
            "status": "outside_entry_window", "opportunity_ids": [],
            "duplicate_weeks": 0, "segments": _segments(conn, [], []),
            "funnel": dict(collection.get("funnel") or {}),
        }
    if collection.get("status") != "complete" or collection.get("protocol") != PROTOCOL:
        raise ValueError("collection is not a complete TRG-1 artifact")
    recorded = _utc(now or datetime.now(UTC))
    source_at = _parse_time(collection.get("source_fetch_completed_at"))
    quoted_at = _parse_time(collection.get("quote_fetch_completed_at"))
    if not _in_window(recorded) or not _in_window(source_at) or not _in_window(quoted_at):
        raise ValueError("collection is outside the TRG-1 entry window")
    if not source_at <= quoted_at <= recorded:
        raise ValueError("collection timestamps are out of order")
    if (recorded - source_at).total_seconds() > MAX_AGE_SECONDS or (
        recorded - quoted_at
    ).total_seconds() > MAX_AGE_SECONDS:
        raise ValueError("collection source or quotes are stale")
    expected_week = recorded.date() + timedelta(days=2)
    if collection.get("week_end") != expected_week.isoformat():
        raise ValueError("collection week does not match recording window")
    daily_counts = _reparse_source(collection)
    source_digest = collection.get("source_digest")
    if not isinstance(source_digest, str) or not source_digest:
        raise ValueError("source digest is required")
    board = [Market.from_mapping(row) for row in collection.get("board") or []]
    if any(market.raw.get("source_digest") != source_digest for market in board):
        raise ValueError("board source digest does not match TSA receipt")
    orderbooks = collection.get("orderbooks")
    if not isinstance(orderbooks, Mapping):
        raise ValueError("retained orderbooks are required")

    theories.register(
        conn, TsaRemainderGapTheory.id, TsaRemainderGapTheory.name,
        "theories/tsa_remainder_gap",
    )
    ctx = TheoryContext.build(
        conn, board, quoted_at,
        run_id=f"trg1-live-{quoted_at.strftime('%Y%m%dT%H%M%SZ')}",
        run_mode="live",
    )
    run = TsaRemainderGapTheory(
        daily_counts, fetch=_captured_fetch(orderbooks)
    ).start(ctx)
    with db.write(conn):
        conn.execute("BEGIN IMMEDIATE")
        seen = _recorded_weeks(conn)
        kept = []
        duplicates = 0
        for candidate in run.candidates:
            week = candidate.legs[0].market.raw["_tsa_remainder_gap"]["week_end"]
            if week in seen:
                duplicates += 1
                continue
            seen.add(week)
            kept.append(candidate)
        run.candidates = kept
        if duplicates:
            run.screen_result.gate_removed["already_recorded_week"] = duplicates
        result = run.finish()
    return {
        "status": "recorded", "quote_time": quoted_at.isoformat(),
        "opportunity_ids": list(result.opportunity_ids),
        "duplicate_weeks": duplicates, "funnel": result.funnel,
        "gate_removed": result.gate_removed,
        "segments": _segments(conn, result.scored, result.opportunity_ids),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path)
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    conn = db.connect()
    try:
        db.init_db(conn)
        collection = (
            json.loads(args.collection.read_text(encoding="utf-8"))
            if args.collection else
            collect_live(conn, data_dir=args.data_dir, out_path=args.out)
        )
        if args.collect:
            print(json.dumps({
                "status": collection.get("status"),
                "collection_path": collection.get("collection_path"),
                "funnel": collection.get("funnel", {}),
            }, sort_keys=True))
            return 0
        summary = record_collection(conn, collection)
        print(json.dumps(summary, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "stopped", "error": str(exc)}))
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
