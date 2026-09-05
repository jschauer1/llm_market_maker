"""Capture post-judgment books and fee evidence one completed batch at a time.

The command reads no partial first output.  Each complete batch produces one
immutable ``book-capture.json`` checkpoint; a later invocation skips it.
Raw HTTP bodies and receipts are retained beside the checkpoints.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlencode
import uuid

import requests


STUDY_DIR = Path(__file__).resolve().parent
REPO_ROOT = STUDY_DIR.parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.atomic_write import write_json  # noqa: E402
from tools.book import other_side_ask  # noqa: E402
from tools.judgments import load_batch  # noqa: E402
from tools.kalshi.markets import BASE_URL  # noqa: E402
from tools import sizing  # noqa: E402


DEFAULT_ROOT = STUDY_DIR / "data" / "judgments"
OUTPUT_NAME = "book-capture.json"
DEPTH_TARGETS = (100, 500, 1000)
MAX_WORKERS = 4
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
USER_AGENT = "market-edge-finder-broad-procedural-study/1.0"
FEE_PDF = (
    REPO_ROOT
    / "theories"
    / "procedural_bottlenecks"
    / "data"
    / "design_audit"
    / "raw"
    / "fees"
    / "kalshi-fee-schedule-attempt1.pdf"
)
FEE_PDF_META = FEE_PDF.with_suffix(".pdf.meta.json")
FEE_EFFECTIVE_UTC = "2026-07-07T00:00:00Z"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


class FeeSpec:
    """Whether a series has enough evidence for an actual taker fee."""

    def __init__(self, status: str, multiplier: float | None, reason: str | None):
        self.status = status
        self.multiplier = multiplier
        self.reason = reason

    @classmethod
    def quadratic(cls, multiplier: float) -> "FeeSpec":
        value = _number(multiplier)
        if value is None or value < 0:
            return cls.unknown("invalid_quadratic_multiplier")
        return cls("verified_quadratic", value, None)

    @classmethod
    def unknown(cls, reason: str) -> "FeeSpec":
        return cls("unknown", None, reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "multiplier": self.multiplier,
            "reason": self.reason,
        }


class CaptureFailure(RuntimeError):
    def __init__(self, message: str, receipts: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.receipts = receipts or []


def fee_schedule_evidence() -> dict[str, Any]:
    """Verify the retained, dated official schedule before using its formula."""

    if not FEE_PDF.exists() or not FEE_PDF_META.exists():
        return {"status": "unknown", "reason": "retained_official_schedule_missing"}
    try:
        metadata = json.loads(FEE_PDF_META.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unknown", "reason": f"invalid_schedule_receipt: {exc}"}
    body_sha = hashlib.sha256(FEE_PDF.read_bytes()).hexdigest()
    if metadata.get("body_sha256") != body_sha:
        return {"status": "unknown", "reason": "schedule_hash_mismatch"}
    url = metadata.get("url")
    retrieved = metadata.get("retrieved_at")
    if not isinstance(url, str) or "kalshi.com" not in url or not isinstance(retrieved, str):
        return {"status": "unknown", "reason": "schedule_receipt_not_official_or_undated"}
    return {
        "status": "verified",
        "formula": "round_up(M * 0.07 * C * P * (1-P))",
        "effective_utc": FEE_EFFECTIVE_UTC,
        "retrieved_utc": retrieved,
        "url": url,
        "sha256": body_sha,
        "receipt_path": FEE_PDF_META.relative_to(REPO_ROOT).as_posix(),
        "body_path": FEE_PDF.relative_to(REPO_ROOT).as_posix(),
    }


def _fee_spec(series: Mapping[str, Any] | None, schedule: Mapping[str, Any]) -> FeeSpec:
    if schedule.get("status") != "verified":
        return FeeSpec.unknown("general_schedule_unverified")
    if not isinstance(series, Mapping):
        return FeeSpec.unknown("series_metadata_missing")
    if str(series.get("fee_type", "")).lower() != "quadratic":
        return FeeSpec.unknown("series_fee_type_not_supported_quadratic")
    multiplier = _number(series.get("fee_multiplier"))
    if multiplier is None or multiplier < 0:
        return FeeSpec.unknown("series_fee_multiplier_missing_or_invalid")
    return FeeSpec.quadratic(multiplier)


def _ask_ladder(orderbook: Mapping[str, Any] | None, side: str) -> list[tuple[float, float]]:
    if side not in {"yes", "no"}:
        raise ValueError("side must be yes or no")
    if not isinstance(orderbook, Mapping):
        return []
    opposite = "no_dollars" if side == "yes" else "yes_dollars"
    ladder = []
    for raw in orderbook.get(opposite) or []:
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) < 2:
            continue
        bid, quantity = _number(raw[0]), _number(raw[1])
        if bid is None or quantity is None or quantity <= 0 or not 0 < bid < 1:
            continue
        # Validate with the shared identity, then preserve the wire decimal.
        # 1 - float(.70) adds noise that can round a $1.47 fee to $1.48.
        other_side_ask(bid, 0.0)
        ladder.append((float(Decimal(1) - Decimal(str(raw[0]))), quantity))
    return sorted(ladder)


def _curve(
    ladder: Sequence[tuple[float, float]], target: float, fee: FeeSpec
) -> dict[str, Any]:
    remaining = float(target)
    filled = 0.0
    cost = 0.0
    fills: list[tuple[float, float]] = []
    for ask, available in ladder:
        take = min(remaining, available)
        if take <= 0:
            continue
        fills.append((ask, take))
        cost += ask * take
        filled += take
        remaining -= take
        if remaining <= 1e-12:
            break
    complete = filled + 1e-12 >= target
    average = cost / filled if filled else None
    fee_dollars = None
    average_payable = None
    if complete and fee.multiplier is not None:
        # The official formula rounds each executed price level separately.
        fee_dollars = sum(
            _level_fee(ask, quantity, fee.multiplier)
            for ask, quantity in fills
        )
        average_payable = (cost + fee_dollars) / float(target)
    return {
        "target_contracts": float(target),
        "filled_contracts": round(filled, 10),
        "available_contracts": round(sum(q for _, q in ladder), 10),
        "fill_complete": complete,
        "best_ask": ladder[0][0] if ladder else None,
        "worst_ask": fills[-1][0] if fills else None,
        "average_price": average,
        "fee_dollars": fee_dollars,
        "average_payable": average_payable,
        "fee_status": fee.status,
        "fee_unknown_reason": fee.reason,
    }


def _level_fee(price: float, contracts: float, multiplier: float) -> float:
    """Apply tools.sizing's model without float noise at a cent boundary."""

    p = Decimal(str(price))
    per_contract = min(
        Decimal(str(sizing.FEE_RATE)) * p * (Decimal(1) - p),
        Decimal(str(sizing.FEE_CAP_DOLLARS)),
    )
    total = per_contract * Decimal(str(contracts)) * Decimal(str(multiplier))
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def depth_curves(
    orderbook: Mapping[str, Any] | None,
    fee: FeeSpec,
    targets: Iterable[int | float] = DEPTH_TARGETS,
) -> dict[str, dict[str, dict[str, Any]]]:
    target_values = tuple(float(value) for value in targets)
    return {
        "buy_yes": {
            f"{target:g}": _curve(_ask_ladder(orderbook, "yes"), target, fee)
            for target in target_values
        },
        "buy_no": {
            f"{target:g}": _curve(_ask_ladder(orderbook, "no"), target, fee)
            for target in target_values
        },
    }


def _atomic_write_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            Path(temporary).unlink()
        except OSError:
            pass


def fetch_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    raw_dir: Path,
    label: str,
    request: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = _utc_now,
    max_attempts: int = 4,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """GET JSON conservatively while preserving every response body."""

    request = request or requests.get
    receipts: list[dict[str, Any]] = []
    requested_url = url + ("?" + urlencode(params) if params else "")
    for attempt in range(1, max_attempts + 1):
        try:
            response = request(
                url,
                params=dict(params) if params else None,
                timeout=30,
                headers={"User-Agent": USER_AGENT},
            )
        except requests.exceptions.RequestException as exc:
            receipts.append(
                {
                    "url": requested_url,
                    "captured_utc": _iso(now()),
                    "status": None,
                    "sha256": None,
                    "response_path": None,
                    "error": str(exc),
                }
            )
            if attempt == max_attempts:
                raise CaptureFailure(str(exc), receipts) from exc
            sleep(0.5 * 2 ** (attempt - 1))
            continue

        body = bytes(response.content)
        path = raw_dir / f"{label}-attempt-{attempt}.json"
        _atomic_write_bytes(path, body)
        receipt = {
            "url": getattr(response, "url", None) or requested_url,
            "captured_utc": _iso(now()),
            "status": int(response.status_code),
            "sha256": hashlib.sha256(body).hexdigest(),
            "response_path": path.as_posix(),
            "bytes": len(body),
        }
        receipts.append(receipt)
        if response.status_code == 200:
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CaptureFailure(f"invalid JSON from {receipt['url']}", receipts) from exc
            if not isinstance(payload, dict):
                raise CaptureFailure(f"non-object JSON from {receipt['url']}", receipts)
            return payload, receipts
        if response.status_code not in RETRYABLE_STATUS or attempt == max_attempts:
            raise CaptureFailure(
                f"GET {receipt['url']} failed with status {response.status_code}", receipts
            )
        sleep(0.5 * 2 ** (attempt - 1))
    raise AssertionError("unreachable")


def _complete_batch(folder: Path) -> tuple[Any, list[dict[str, Any]]] | None:
    exclusions = folder.parent / 'quality-exclusions.json'
    if exclusions.exists() and folder.name in json.loads(exclusions.read_text(encoding='utf-8')):
        return None
    first_output = folder / "first-output.jsonl"
    if not first_output.exists():
        return None
    receipt = load_batch(folder / "receipt.json")
    try:
        rows = [
            json.loads(line)
            for line in first_output.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    keys = [row.get("key") for row in rows if isinstance(row, Mapping)]
    expected = list(receipt.request.candidate_keys)
    if len(keys) != len(expected) or len(keys) != len(set(keys)) or set(keys) != set(expected):
        return None
    by_key = {row["key"]: row for row in rows}
    return receipt, [by_key[key] for key in expected]


def _input_market_index(receipt: Any) -> dict[str, dict[str, Any]]:
    payload = receipt.request.payload
    out = {}
    for event in payload.get("events", []) if isinstance(payload, Mapping) else []:
        for market in event.get("markets", []) if isinstance(event, Mapping) else []:
            if isinstance(market, Mapping) and isinstance(market.get("key"), str):
                out[market["key"]] = dict(market)
    return out


def _failure_rows(endpoint: str, exc: CaptureFailure) -> list[dict[str, Any]]:
    if not exc.receipts:
        return [{"endpoint": endpoint, "error": str(exc), "status": None}]
    return [dict(row, endpoint=endpoint, error=str(exc)) for row in exc.receipts]


def _capture_market(
    ticker: str, raw_dir: Path, fetch: Callable[..., Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "market_metadata": None,
        "rules_status": None,
        "orderbook": None,
        "responses": {"market": [], "orderbook": []},
        "failures": [],
    }
    try:
        payload, receipts = fetch(
            f"{BASE_URL}/markets/{ticker}",
            raw_dir=raw_dir,
            label=f"market-{ticker}",
        )
        result["responses"]["market"] = receipts
        market = payload.get("market")
        if not isinstance(market, Mapping):
            raise CaptureFailure("market response has no market object", receipts)
        market = dict(market)
        result["market_metadata"] = market
        result["rules_status"] = {
            "status": market.get("status"),
            "rules_primary": market.get("rules_primary"),
            "rules_secondary": market.get("rules_secondary"),
        }
    except CaptureFailure as exc:
        result["failures"].extend(_failure_rows("market", exc))
    try:
        payload, receipts = fetch(
            f"{BASE_URL}/markets/{ticker}/orderbook",
            params={"depth": 100},
            raw_dir=raw_dir,
            label=f"orderbook-{ticker}",
        )
        result["responses"]["orderbook"] = receipts
        book = payload.get("orderbook_fp")
        if not isinstance(book, Mapping):
            raise CaptureFailure("orderbook response has no orderbook_fp object", receipts)
        result["orderbook"] = dict(book)
    except CaptureFailure as exc:
        result["failures"].extend(_failure_rows("orderbook", exc))
    return result


def _capture_series(
    series: str, raw_dir: Path, fetch: Callable[..., Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "metadata": None,
        "fee_changes": None,
        "responses": {"series": [], "fee_changes": []},
        "failures": [],
    }
    try:
        payload, receipts = fetch(
            f"{BASE_URL}/series/{series}",
            raw_dir=raw_dir,
            label=f"series-{series}",
        )
        result["responses"]["series"] = receipts
        metadata = payload.get("series")
        if not isinstance(metadata, Mapping):
            raise CaptureFailure("series response has no series object", receipts)
        result["metadata"] = dict(metadata)
    except CaptureFailure as exc:
        result["failures"].extend(_failure_rows("series", exc))
    try:
        payload, receipts = fetch(
            f"{BASE_URL}/series/fee_changes",
            params={"series_ticker": series, "show_historical": "true"},
            raw_dir=raw_dir,
            label=f"series-fee-changes-{series}",
        )
        result["responses"]["fee_changes"] = receipts
        changes = payload.get("series_fee_change_arr")
        if not isinstance(changes, list):
            raise CaptureFailure("fee-change response has no array", receipts)
        result["fee_changes"] = changes
    except CaptureFailure as exc:
        result["failures"].extend(_failure_rows("fee_changes", exc))
    return result


def _pool_map(
    values: Iterable[str], worker: Callable[[str], dict[str, Any]], workers: int
) -> dict[str, dict[str, Any]]:
    values = list(values)
    if not values:
        return {}
    with ThreadPoolExecutor(max_workers=min(max(1, workers), MAX_WORKERS)) as executor:
        futures = {executor.submit(worker, value): value for value in values}
        return {futures[future]: future.result() for future in as_completed(futures)}


def capture_completed_batches(
    root: Path,
    *,
    fetch: Callable[..., Any] | None = None,
    now: Callable[[], datetime] = _utc_now,
    workers: int = MAX_WORKERS,
) -> dict[str, int]:
    if workers < 1 or workers > MAX_WORKERS:
        raise ValueError(f"workers must be between 1 and {MAX_WORKERS}")
    fetch = fetch or fetch_json
    schedule = fee_schedule_evidence()
    series_cache: dict[str, dict[str, Any]] = {}
    counts = {"captured_batches": 0, "skipped_incomplete": 0, "skipped_existing": 0}

    for folder in sorted(Path(root).glob("batch-*")):
        output = folder / OUTPUT_NAME
        if output.exists():
            counts["skipped_existing"] += 1
            continue
        complete = _complete_batch(folder)
        if complete is None:
            counts["skipped_incomplete"] += 1
            continue
        receipt, judgments = complete
        started = now()
        if started.tzinfo is None:
            raise ValueError("capture clock must return an aware datetime")
        first_output = folder / "first-output.jsonl"
        stat = first_output.stat()
        capture_id = started.strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:8]
        raw_dir = folder / "book-capture-raw" / capture_id
        candidate_keys = list(receipt.request.candidate_keys)
        input_markets = _input_market_index(receipt)
        markets = _pool_map(
            candidate_keys,
            lambda ticker: _capture_market(ticker, raw_dir / "markets", fetch),
            workers,
        )

        series_for_market = {}
        for ticker in candidate_keys:
            fresh = markets[ticker].get("market_metadata") or {}
            fallback = input_markets.get(ticker) or {}
            series = fresh.get("series_ticker") or fallback.get("series")
            series_for_market[ticker] = series if isinstance(series, str) and series else None
        missing_series = sorted(
            {series for series in series_for_market.values() if series and series not in series_cache}
        )
        series_cache.update(
            _pool_map(
                missing_series,
                lambda series: _capture_series(
                    series,
                    Path(root) / "book-capture-raw" / capture_id / "series",
                    fetch,
                ),
                workers,
            )
        )

        for ticker in candidate_keys:
            series = series_for_market[ticker]
            series_result = series_cache.get(series or "")
            fee = _fee_spec(
                series_result.get("metadata") if series_result else None,
                schedule,
            )
            markets[ticker]["series_ticker"] = series
            markets[ticker]["fee"] = fee.to_dict()
            book = markets[ticker].pop("orderbook")
            markets[ticker]["depth_curves"] = (
                depth_curves(book, fee) if isinstance(book, Mapping) else None
            )

        mtime_seconds = stat.st_mtime_ns / 1_000_000_000
        artifact = {
            "schema_version": 1,
            "batch_id": receipt.request.batch_id,
            "capture_id": capture_id,
            "capture_started_utc": _iso(started),
            "capture_lag_seconds": started.timestamp() - mtime_seconds,
            "first_output": {
                "path": first_output.as_posix(),
                "mtime_ns": stat.st_mtime_ns,
                "mtime_utc": _iso(datetime.fromtimestamp(mtime_seconds, tz=timezone.utc)),
                "sha256": hashlib.sha256(first_output.read_bytes()).hexdigest(),
            },
            "candidate_keys": candidate_keys,
            "judgments": {row["key"]: row for row in judgments},
            "markets": {ticker: markets[ticker] for ticker in candidate_keys},
            "series": {
                series: series_cache[series]
                for series in sorted({value for value in series_for_market.values() if value})
            },
            "fee_schedule_evidence": schedule,
            "depth_targets_contracts": list(DEPTH_TARGETS),
            "book_side_identity": {
                "buy_yes_ask": "1 - NO bid",
                "buy_no_ask": "1 - YES bid",
            },
            "outcomes_inspected": False,
            "ledger_writes": False,
        }
        write_json(output, artifact, indent=2, sort_keys=True)
        counts["captured_batches"] += 1
    return counts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judgments-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, choices=range(1, 5))
    args = parser.parse_args(argv)
    print(
        json.dumps(
            capture_completed_batches(args.judgments_root, workers=args.workers),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
