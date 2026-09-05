"""Capture blind-safe FDA market rules and operator-only economic inputs.

The default ``audit`` phase never reads a current order book.  It copies the
preserved historical market metadata, fetches targeted current metadata,
collects the fixed historical candle windows, and records fee evidence.  The
``current`` phase is deliberately separate so the operator can run it only
after the first judgments have been saved.

Every HTTP body is retained byte-for-byte under ``data/market_audit/raw`` and
described by URL, capture time, status, byte count, and SHA-256 in the capture
manifest.  Derived JSON never contains a market result.  ``rules.json`` also
excludes every price and status field so it is safe to use in blind judging.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import requests


STUDY_DIR = Path(__file__).resolve().parent
REPO_ROOT = STUDY_DIR.parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.atomic_write import write_json  # noqa: E402


BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
DATA_DIR = STUDY_DIR / "data"
AUDIT_DIR = DATA_DIR / "market_audit"
RAW_DIR = AUDIT_DIR / "raw"
EXPOSURE_PATH = DATA_DIR / "exposure_audit.json"
PRIOR_FDA_DIR = (
    STUDY_DIR.parents[1]
    / "answer"
    / "2026-09-05-procedural-viability"
    / "data"
    / "fda"
)
MANIFEST_PATH = AUDIT_DIR / "capture_manifest.json"
FEE_SCHEDULE_URL = "https://www.kalshi.com/docs/kalshi-fee-schedule.pdf"
PRESERVED_FEE_SCHEDULE = (
    REPO_ROOT
    / "theories"
    / "procedural_bottlenecks"
    / "data"
    / "design_audit"
    / "raw"
    / "fees"
    / "kalshi-fee-schedule-attempt1.pdf"
)
PRESERVED_FEE_SCHEDULE_META = PRESERVED_FEE_SCHEDULE.with_suffix(".pdf.meta.json")
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
USER_AGENT = "market-edge-finder-fda-study/1.0"
DEPTH_TARGETS = (100, 500, 1000)

SERIES_BY_PREFIX = {
    "KXFDAAPPROVALDATECMPS-": "KXFDAAPPROVALDATECMPS",
    "KXFDAAPPROVALDATENTLA-": "KXFDAAPPROVALDATENTLA",
    "KXFDARETATRUTIDE-": "KXFDARETATRUTIDE",
    "KXFDAAPPROVE-": "KXFDAAPPROVE",
}


class CaptureFailure(RuntimeError):
    """One endpoint was unavailable after retaining every response received."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp needs an explicit UTC offset: {value!r}")
    return parsed.astimezone(timezone.utc)


def iso_from_ts(value: int | float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def series_for_ticker(ticker: str) -> str:
    for prefix, series in SERIES_BY_PREFIX.items():
        if ticker.startswith(prefix):
            return series
    raise ValueError(f"no frozen FDA series mapping for ticker {ticker}")


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _candle_close(candle: Mapping[str, Any], side: str) -> float | None:
    block = candle.get(side)
    if not isinstance(block, Mapping):
        return None
    return _float(block.get("close_dollars", block.get("close")))


def select_historical_entry(
    candles: Sequence[Mapping[str, Any]], decision_ts: int
) -> dict[str, Any]:
    """Select the first valid close from decision+15m through +75m.

    A valid historical quote has both YES bid and ask strictly inside (0, 1),
    a nonnegative spread no larger than seven cents, and a candle timestamp in
    the pre-registered window.  The NO ask is the executable book identity
    ``1 - YES bid``; no trade price or midpoint enters the result.
    """

    start_ts = decision_ts + 15 * 60
    end_ts = start_ts + 60 * 60
    selected: dict[str, Any] | None = None
    exclusions: list[dict[str, Any]] = []

    def exclude(raw_ts: Any, reason: str, **fields: Any) -> None:
        stamp = iso_from_ts(raw_ts) if isinstance(raw_ts, (int, float)) else None
        exclusions.append({"candle_end_utc": stamp, "reason": reason, **fields})

    for candle in sorted(candles, key=lambda row: row.get("end_period_ts", -1)):
        raw_ts = candle.get("end_period_ts")
        if not isinstance(raw_ts, (int, float)):
            exclude(raw_ts, "missing_end_period_ts")
            continue
        if raw_ts < start_ts:
            exclude(raw_ts, "before_entry_window")
            continue
        if raw_ts > end_ts:
            exclude(raw_ts, "after_entry_window")
            continue

        bid = _candle_close(candle, "yes_bid")
        ask = _candle_close(candle, "yes_ask")
        if bid is None or ask is None:
            exclude(raw_ts, "missing_bid_or_ask", yes_bid=bid, yes_ask=ask)
            continue
        if not 0.0 < bid < 1.0 or not 0.0 < ask < 1.0:
            exclude(raw_ts, "bid_or_ask_outside_open_unit_interval", yes_bid=bid, yes_ask=ask)
            continue
        spread = ask - bid
        if spread < 0.0:
            exclude(raw_ts, "negative_spread", yes_bid=bid, yes_ask=ask)
            continue
        if spread > 0.07 + 1e-12:
            exclude(
                raw_ts,
                "spread_above_0.07",
                yes_bid=bid,
                yes_ask=ask,
                spread=round(spread, 10),
            )
            continue
        if selected is not None:
            exclude(raw_ts, "later_than_selected_valid_candle")
            continue
        selected = {
            "candle_end_utc": iso_from_ts(raw_ts),
            "yes_bid": round(bid, 10),
            "yes_ask": round(ask, 10),
            "no_ask": round(1.0 - bid, 10),
            "spread": round(spread, 10),
        }

    return {
        "window_start_utc": iso_from_ts(start_ts),
        "window_end_utc": iso_from_ts(end_ts),
        "selected": selected,
        "excluded_candles": exclusions,
        "availability": "available" if selected else "unavailable",
        "unavailable_reason": None if selected else "no_valid_candle_within_window",
    }


def implied_ask_ladder(
    orderbook: Mapping[str, Any] | None, side: str
) -> list[tuple[float, float]]:
    """Return executable asks from the opposite side's resting bids."""

    if side not in {"yes", "no"}:
        raise ValueError("side must be 'yes' or 'no'")
    if not orderbook:
        return []
    opposite_key = "no_dollars" if side == "yes" else "yes_dollars"
    out: list[tuple[float, float]] = []
    for level in orderbook.get(opposite_key) or []:
        if not isinstance(level, Sequence) or isinstance(level, (str, bytes)):
            continue
        if len(level) < 2:
            continue
        bid = _float(level[0])
        quantity = _float(level[1])
        if bid is None or quantity is None:
            continue
        ask = 1.0 - bid
        if 0.0 < ask < 1.0 and quantity > 0.0:
            out.append((ask, quantity))
    return sorted(out, key=lambda row: row[0])


def _curve(ladder: Sequence[tuple[float, float]], target: float) -> dict[str, Any]:
    available = sum(quantity for _, quantity in ladder)
    remaining = float(target)
    filled = 0.0
    cost = 0.0
    worst: float | None = None
    for ask, quantity in ladder:
        take = min(remaining, quantity)
        if take <= 0.0:
            continue
        cost += ask * take
        filled += take
        remaining -= take
        worst = ask
        if remaining <= 1e-12:
            break
    best = ladder[0][0] if ladder else None
    return {
        "target_contracts": float(target),
        "filled_contracts": round(filled, 10),
        "available_contracts": round(available, 10),
        "fill_complete": filled + 1e-12 >= target,
        "best_ask": None if best is None else round(best, 10),
        "worst_ask": None if worst is None else round(worst, 10),
        "vwap_ask": None if filled == 0.0 else cost / filled,
        "adverse_price_movement": (
            None if best is None or worst is None else round(worst - best, 10)
        ),
    }


def depth_curves(
    orderbook: Mapping[str, Any] | None,
    targets: Iterable[int | float] = DEPTH_TARGETS,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Build both-side quantity curves from Kalshi's bid-only order book."""

    yes = implied_ask_ladder(orderbook, "yes")
    no = implied_ask_ladder(orderbook, "no")
    targets = tuple(float(target) for target in targets)
    return {
        "buy_yes": {f"{target:g}": _curve(yes, target) for target in targets},
        "buy_no": {f"{target:g}": _curve(no, target) for target in targets},
    }


def build_blind_rule(
    market: Mapping[str, Any], *, deadline: str, rules_vintage: str
) -> dict[str, Any]:
    """Copy only the contract text fields approved for blind judgment."""

    return {
        "ticker": market.get("ticker") or "",
        "title": market.get("title") or "",
        "rules_primary": market.get("rules_primary") or "",
        "rules_secondary": market.get("rules_secondary") or "",
        "deadline": deadline,
        "rules_vintage": rules_vintage,
    }


def _atomic_write_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            Path(temp_name).unlink()
        except OSError:
            pass


def _safe_label(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("._")


class CaptureSession:
    """Small raw-byte capture helper scoped to this one finite study."""

    def __init__(self, phase: str):
        self.started_utc = utc_now()
        self.capture_id = self.started_utc.replace("-", "").replace(":", "").replace(".", "")
        self.phase = phase
        self.directory = RAW_DIR / phase / self.capture_id
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.manifest = self._load_manifest()

    @staticmethod
    def _load_manifest() -> dict[str, Any]:
        if not MANIFEST_PATH.exists():
            return {"schema_version": 1, "captures": []}
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def _record(self, row: dict[str, Any]) -> None:
        self.manifest.setdefault("captures", []).append(row)
        write_json(MANIFEST_PATH, self.manifest, indent=2, sort_keys=True)

    def copy_preserved(self, source: Path, label: str) -> Path:
        body = source.read_bytes()
        destination = self.directory / f"{_safe_label(label)}{source.suffix}"
        _atomic_write_bytes(destination, body)
        captured_utc = utc_now()
        self._record(
            {
                "capture_id": self.capture_id,
                "phase": self.phase,
                "label": label,
                "method": "preserved_copy",
                "url": None,
                "captured_utc": captured_utc,
                "status_code": None,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "response_path": destination.relative_to(STUDY_DIR).as_posix(),
                "reused_from": source.relative_to(REPO_ROOT).as_posix(),
                "available": True,
            }
        )
        return destination

    def get(
        self,
        url: str,
        *,
        label: str,
        params: Mapping[str, Any] | None = None,
        suffix: str = ".json",
        parse_json: bool = True,
        attempts: int = 3,
    ) -> tuple[Any, dict[str, Any]]:
        last_error: str | None = None
        for attempt in range(1, attempts + 1):
            requested_utc = utc_now()
            try:
                response = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self._record(
                    {
                        "capture_id": self.capture_id,
                        "phase": self.phase,
                        "label": label,
                        "attempt": attempt,
                        "method": "GET",
                        "url": requests.Request("GET", url, params=params).prepare().url,
                        "requested_utc": requested_utc,
                        "captured_utc": utc_now(),
                        "status_code": None,
                        "bytes": 0,
                        "sha256": None,
                        "response_path": None,
                        "available": False,
                        "error": last_error,
                    }
                )
                if attempt < attempts:
                    time.sleep(attempt)
                    continue
                raise CaptureFailure(f"GET {url} failed: {last_error}") from exc

            captured_utc = utc_now()
            body = response.content
            path = self.directory / f"{_safe_label(label)}_attempt{attempt}{suffix}"
            _atomic_write_bytes(path, body)
            row = {
                "capture_id": self.capture_id,
                "phase": self.phase,
                "label": label,
                "attempt": attempt,
                "method": "GET",
                "url": response.url,
                "requested_utc": requested_utc,
                "captured_utc": captured_utc,
                "status_code": response.status_code,
                "content_type": response.headers.get("Content-Type"),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "response_path": path.relative_to(STUDY_DIR).as_posix(),
                "available": response.status_code == 200,
            }
            self._record(row)
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
                if response.status_code in RETRYABLE_STATUS and attempt < attempts:
                    retry_after = _float(response.headers.get("Retry-After"))
                    time.sleep(min(retry_after or attempt, 10.0))
                    continue
                raise CaptureFailure(f"GET {response.url} returned {response.status_code}")

            if not parse_json:
                return body, row
            try:
                return response.json(), row
            except ValueError as exc:
                row["available"] = False
                row["error"] = "HTTP 200 response was not valid JSON"
                self._record({**row, "manifest_correction": True})
                raise CaptureFailure(f"GET {response.url} returned invalid JSON") from exc

        raise CaptureFailure(f"GET {url} failed: {last_error}")


def _load_exposure() -> dict[str, Any]:
    return json.loads(EXPOSURE_PATH.read_text(encoding="utf-8"))


def _historical_roster(exposure: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "subject_id": row["subject_id"],
            "ticker": row["selected_ticker"],
            "deadline": row["deadline_date"],
            "decision_utc": row["diagnostic_asof_utc"],
            "series_ticker": series_for_ticker(row["selected_ticker"]),
        }
        for row in exposure["historical_eligible_subjects"]
    ]


def _current_roster(exposure: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "subject_id": row["subject_id"],
            "ticker": row["ticker"],
            "deadline": row["deadline_date"],
            "series_ticker": series_for_ticker(row["ticker"]),
        }
        for row in exposure["current_forward_outcome_validation"]["in_window_cases"]
    ]


def _iter_saved_markets(payload: Mapping[str, Any]) -> Iterable[tuple[dict[str, Any], str | None]]:
    for market in payload.get("markets") or []:
        if isinstance(market, dict):
            yield market, market.get("series_ticker")
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        series = event.get("series_ticker")
        for market in event.get("markets") or []:
            if isinstance(market, dict):
                yield market, series


def _preserved_market_index() -> dict[str, tuple[dict[str, Any], Path, str | None]]:
    index: dict[str, tuple[dict[str, Any], Path, str | None]] = {}
    candidates = sorted(PRIOR_FDA_DIR.glob("kalshi_*events.json")) + sorted(
        PRIOR_FDA_DIR.glob("kalshi_*historical_markets_page*.json")
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for market, series in _iter_saved_markets(payload):
            ticker = market.get("ticker")
            if ticker:
                index[ticker] = (market, path, series)
    return index


def _market_from_payload(payload: Mapping[str, Any], ticker: str) -> dict[str, Any]:
    market = payload.get("market")
    if isinstance(market, dict) and market.get("ticker") == ticker:
        return market
    for candidate, _ in _iter_saved_markets(payload):
        if candidate.get("ticker") == ticker:
            return candidate
    raise ValueError(f"market response did not contain requested ticker {ticker}")


def _history_payload(
    capture: CaptureSession, row: Mapping[str, Any]
) -> tuple[dict[str, Any] | None, str | None, list[dict[str, str]]]:
    decision_ts = int(parse_utc(row["decision_utc"]).timestamp())
    params = {
        "start_ts": decision_ts + 15 * 60,
        "end_ts": decision_ts + 75 * 60,
        "period_interval": 1,
    }
    ticker = row["ticker"]
    failures: list[dict[str, str]] = []
    live_url = (
        f"{BASE_URL}/series/{row['series_ticker']}/markets/{ticker}/candlesticks"
    )
    try:
        payload, receipt = capture.get(
            live_url,
            params=params,
            label=f"historical_candles_live_{ticker}",
        )
        if payload.get("candlesticks"):
            return payload, receipt["response_path"], failures
        failures.append({"endpoint": "live", "reason": "empty_candlesticks"})
    except (CaptureFailure, AttributeError) as exc:
        failures.append({"endpoint": "live", "reason": str(exc)})

    archived_url = f"{BASE_URL}/historical/markets/{ticker}/candlesticks"
    try:
        payload, receipt = capture.get(
            archived_url,
            params=params,
            label=f"historical_candles_archived_{ticker}",
        )
        return payload, receipt["response_path"], failures
    except CaptureFailure as exc:
        failures.append({"endpoint": "archived", "reason": str(exc)})
        return None, None, failures


def _capture_fee_evidence(
    capture: CaptureSession, series_tickers: Iterable[str]
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "captured_utc": utc_now(),
        "general_schedule": None,
        "series": {},
        "historical_fee_limit": (
            "Current series metadata is not silently applied to 2026-05-15. "
            "Historical use requires a dated schedule or fee-change row shown to "
            "cover that decision time."
        ),
    }
    try:
        _, receipt = capture.get(
            FEE_SCHEDULE_URL,
            label="kalshi_fee_schedule",
            suffix=".pdf",
            parse_json=False,
        )
        evidence["general_schedule"] = {
            "url": receipt["url"],
            "captured_utc": receipt["captured_utc"],
            "sha256": receipt["sha256"],
            "response_path": receipt["response_path"],
            "document_effective_date": None,
            "limitation": (
                "The internally dated PDF is retained, but this collector does "
                "not infer its effective date from the current download URL."
            ),
        }
    except CaptureFailure as exc:
        if PRESERVED_FEE_SCHEDULE.exists() and PRESERVED_FEE_SCHEDULE_META.exists():
            copied = capture.copy_preserved(
                PRESERVED_FEE_SCHEDULE, "preserved_kalshi_fee_schedule_2026-07-07"
            )
            copied_meta = capture.copy_preserved(
                PRESERVED_FEE_SCHEDULE_META,
                "preserved_kalshi_fee_schedule_2026-07-07_meta",
            )
            meta = json.loads(PRESERVED_FEE_SCHEDULE_META.read_text(encoding="utf-8"))
            body = copied.read_bytes()
            evidence["general_schedule"] = {
                "url": meta.get("url"),
                "original_retrieved_utc": meta.get("retrieved_at"),
                "copied_utc": utc_now(),
                "sha256": hashlib.sha256(body).hexdigest(),
                "response_path": copied.relative_to(STUDY_DIR).as_posix(),
                "receipt_path": copied_meta.relative_to(STUDY_DIR).as_posix(),
                "document_effective_date": "2026-07-07",
                "fresh_attempt_error": str(exc),
                "limitation": (
                    "The preserved official PDF is dated effective July 7, 2026. "
                    "It supports the current general formula but postdates the "
                    "May 15 historical entry and is not historical fee evidence."
                ),
            }
        else:
            evidence["general_schedule"] = {"available": False, "error": str(exc)}

    for series in sorted(set(series_tickers)):
        row: dict[str, Any] = {"series_ticker": series}
        try:
            payload, receipt = capture.get(
                f"{BASE_URL}/series/{series}",
                label=f"series_metadata_{series}",
            )
            raw = payload.get("series") or {}
            row["current"] = {
                "fee_type": raw.get("fee_type"),
                "fee_multiplier": raw.get("fee_multiplier"),
                "last_updated_ts": raw.get("last_updated_ts"),
                "captured_utc": receipt["captured_utc"],
                "response_path": receipt["response_path"],
            }
        except CaptureFailure as exc:
            row["current"] = {"available": False, "error": str(exc)}
        try:
            payload, receipt = capture.get(
                f"{BASE_URL}/series/fee_changes",
                params={"series_ticker": series, "show_historical": "true"},
                label=f"series_fee_changes_{series}",
            )
            changes = payload.get("series_fee_change_arr") or []
            row["dated_changes"] = changes
            row["dated_changes_capture_utc"] = receipt["captured_utc"]
            row["dated_changes_response_path"] = receipt["response_path"]
        except CaptureFailure as exc:
            row["dated_changes"] = None
            row["dated_changes_error"] = str(exc)
        evidence["series"][series] = row
    return evidence


def run_audit() -> int:
    exposure = _load_exposure()
    historical = _historical_roster(exposure)
    current = _current_roster(exposure)
    capture = CaptureSession("audit")
    preserved = _preserved_market_index()
    rules: dict[str, Any] = {}
    copied_sources: dict[Path, Path] = {}
    unavailable: dict[str, Any] = {}

    for row in historical:
        ticker = row["ticker"]
        found = preserved.get(ticker)
        if found is None:
            unavailable[ticker] = {"kind": "rules", "reason": "preserved_market_not_found"}
            continue
        market, source, _ = found
        if source not in copied_sources:
            copied_sources[source] = capture.copy_preserved(
                source, f"preserved_{source.stem}"
            )
        rules[ticker] = build_blind_rule(
            market,
            deadline=row["deadline"],
            rules_vintage=(
                "Copied verbatim from preserved Kalshi metadata captured on "
                "2026-09-05, after the 2026-05-15 decision time and after the "
                "market outcome was exposed. No contemporaneous rule record was "
                "found, so the historical rule vintage is unproved."
            ),
        )

    current_market_receipts: dict[str, dict[str, Any]] = {}
    for row in current:
        ticker = row["ticker"]
        try:
            payload, receipt = capture.get(
                f"{BASE_URL}/markets/{ticker}",
                label=f"current_market_metadata_{ticker}",
            )
            market = _market_from_payload(payload, ticker)
            current_market_receipts[ticker] = receipt
        except (CaptureFailure, ValueError) as exc:
            found = preserved.get(ticker)
            if found is None:
                unavailable[ticker] = {"kind": "rules", "reason": str(exc)}
                continue
            market, source, _ = found
            if source not in copied_sources:
                copied_sources[source] = capture.copy_preserved(
                    source, f"preserved_{source.stem}"
                )
            current_market_receipts[ticker] = {
                "captured_utc": None,
                "response_path": copied_sources[source].relative_to(STUDY_DIR).as_posix(),
                "fallback_reason": str(exc),
            }
        stamp = current_market_receipts[ticker].get("captured_utc") or "unavailable"
        rules[ticker] = build_blind_rule(
            market,
            deadline=row["deadline"],
            rules_vintage=(
                f"Fresh targeted Kalshi metadata captured {stamp}; this proves "
                "the rule text only at that retrieval and not at an earlier "
                "selection or source-freeze time. A preserved Sep 5 payload was "
                "used only if the fresh endpoint was unavailable."
            ),
        )

    # The rules are an input to independent judgment.  Persist them before
    # any quote/fee work so a later endpoint failure cannot block judging.
    write_json(
        AUDIT_DIR / "rules.json",
        {"rules": rules},
        indent=2,
        sort_keys=True,
    )

    historical_quotes: dict[str, Any] = {}
    for row in historical:
        payload, response_path, endpoint_failures = _history_payload(capture, row)
        candles = payload.get("candlesticks") if isinstance(payload, dict) else []
        selection = select_historical_entry(
            candles or [], int(parse_utc(row["decision_utc"]).timestamp())
        )
        selection.update(
            {
                "subject_id": row["subject_id"],
                "decision_utc": row["decision_utc"],
                "raw_response_path": response_path,
                "endpoint_failures": endpoint_failures,
                "depth_limit": (
                    "Historical candles contain displayed bid/ask closes but no "
                    "resting size; this is displayed-price sensitivity, not an "
                    "actual 100-contract fill."
                ),
            }
        )
        historical_quotes[row["ticker"]] = selection
        if selection["availability"] == "unavailable":
            unavailable[row["ticker"]] = {
                "kind": "historical_quote",
                "reason": selection["unavailable_reason"],
                "endpoint_failures": endpoint_failures,
                "excluded_candles": selection["excluded_candles"],
            }

    fee_evidence = _capture_fee_evidence(
        capture, [row["series_ticker"] for row in historical + current]
    )
    write_json(
        AUDIT_DIR / "historical_quotes.json",
        {
            "classification": "operator_only_economic_input_excluded_from_blind_judgment",
            "entry_rule": (
                "First valid 1-minute bid/ask candle at or after decision+15m, "
                "through decision+75m inclusive; both prices in (0,1), spread <=0.07; "
                "NO ask = 1 - YES bid."
            ),
            "quotes": historical_quotes,
        },
        indent=2,
        sort_keys=True,
    )
    write_json(AUDIT_DIR / "unavailable_quotes.json", unavailable, indent=2, sort_keys=True)
    write_json(AUDIT_DIR / "fee_evidence.json", fee_evidence, indent=2, sort_keys=True)
    write_json(
        AUDIT_DIR / "operator_economic_inputs.json",
        {
            "classification": "operator_only_excluded_from_blind_judgment",
            "historical_quotes_path": "data/market_audit/historical_quotes.json",
            "fee_evidence_path": "data/market_audit/fee_evidence.json",
            "current_books_path": None,
            "outcomes_included": False,
            "profit_comparisons_included": False,
        },
        indent=2,
        sort_keys=True,
    )
    available_count = sum(
        row["availability"] == "available" for row in historical_quotes.values()
    )
    print(
        json.dumps(
            {
                "phase": "audit",
                "rules": len(rules),
                "historical_quotes_available": available_count,
                "historical_quotes_total": len(historical_quotes),
                "unavailable_entries": len(unavailable),
                "capture_id": capture.capture_id,
            },
            sort_keys=True,
        )
    )
    return 0


def run_current(judgments_saved_at: str) -> int:
    judgment_time = parse_utc(judgments_saved_at)
    exposure = _load_exposure()
    current = _current_roster(exposure)
    capture = CaptureSession("current")
    books: dict[str, Any] = {}
    unavailable: dict[str, Any] = {}

    for row in current:
        ticker = row["ticker"]
        market_receipt: dict[str, Any] | None = None
        orderbook_receipt: dict[str, Any] | None = None
        try:
            _, market_receipt = capture.get(
                f"{BASE_URL}/markets/{ticker}",
                label=f"current_market_metadata_{ticker}",
            )
        except CaptureFailure as exc:
            unavailable.setdefault(ticker, {})["market_metadata"] = str(exc)
        try:
            payload, orderbook_receipt = capture.get(
                f"{BASE_URL}/markets/{ticker}/orderbook",
                params={"depth": 100},
                label=f"current_orderbook_{ticker}",
            )
            orderbook = payload.get("orderbook_fp")
            if not isinstance(orderbook, Mapping):
                raise ValueError("response has no orderbook_fp object")
            curves = depth_curves(orderbook)
            if not implied_ask_ladder(orderbook, "yes"):
                unavailable.setdefault(ticker, {})["buy_yes"] = "no_valid_no_bid_levels"
            if not implied_ask_ladder(orderbook, "no"):
                unavailable.setdefault(ticker, {})["buy_no"] = "no_valid_yes_bid_levels"
        except (CaptureFailure, ValueError) as exc:
            orderbook = None
            curves = depth_curves(None)
            unavailable.setdefault(ticker, {})["orderbook"] = str(exc)

        observed_utc = (
            orderbook_receipt or market_receipt or {"captured_utc": utc_now()}
        )["captured_utc"]
        latency_seconds = (parse_utc(observed_utc) - judgment_time).total_seconds()
        books[ticker] = {
            "subject_id": row["subject_id"],
            "deadline": row["deadline"],
            "judgments_saved_utc": judgment_time.isoformat(timespec="seconds").replace(
                "+00:00", "Z"
            ),
            "current_capture_utc": observed_utc,
            "latency_from_judgments_seconds": latency_seconds,
            "market_metadata_raw_response_path": (
                market_receipt.get("response_path") if market_receipt else None
            ),
            "orderbook_raw_response_path": (
                orderbook_receipt.get("response_path") if orderbook_receipt else None
            ),
            "book_side_identity": {
                "buy_yes_ask": "1 - NO bid",
                "buy_no_ask": "1 - YES bid",
            },
            "orderbook_depth_levels_requested": 100,
            "captured_bid_level_counts": {
                "yes": len((orderbook or {}).get("yes_dollars") or []),
                "no": len((orderbook or {}).get("no_dollars") or []),
            },
            "depth_limit": (
                "Curves use the captured top 100 bid levels per side. An "
                "incomplete target with exactly 100 captured opposite-side "
                "levels may have additional uncaptured depth."
            ),
            "depth_curves": curves,
        }

    fee_evidence = _capture_fee_evidence(
        capture, [row["series_ticker"] for row in current]
    )
    output = {
        "classification": "operator_only_economic_input_excluded_from_blind_judgment",
        "capture_id": capture.capture_id,
        "judgments_saved_utc": judgment_time.isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "depth_targets_contracts": list(DEPTH_TARGETS),
        "books": books,
        "unavailable_quotes": unavailable,
        "fee_evidence": fee_evidence,
        "outcomes_included": False,
        "profit_comparisons_included": False,
    }
    current_path = AUDIT_DIR / f"current_books_{capture.capture_id}.json"
    write_json(current_path, output, indent=2, sort_keys=True)
    write_json(AUDIT_DIR / "current_books_latest.json", output, indent=2, sort_keys=True)
    write_json(
        AUDIT_DIR / "operator_economic_inputs.json",
        {
            "classification": "operator_only_excluded_from_blind_judgment",
            "historical_quotes_path": "data/market_audit/historical_quotes.json",
            "fee_evidence_path": "data/market_audit/fee_evidence.json",
            "current_books_path": current_path.relative_to(STUDY_DIR).as_posix(),
            "outcomes_included": False,
            "profit_comparisons_included": False,
        },
        indent=2,
        sort_keys=True,
    )
    print(
        json.dumps(
            {
                "phase": "current",
                "books": len(books),
                "unavailable_tickers": len(unavailable),
                "capture_id": capture.capture_id,
                "output": current_path.relative_to(REPO_ROOT).as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="phase", required=True)
    subparsers.add_parser(
        "audit", help="capture rule metadata, historical quote windows, and fees"
    )
    current = subparsers.add_parser(
        "current", help="capture seven current books after judgments are saved"
    )
    current.add_argument(
        "--judgments-saved-at",
        required=True,
        help="UTC ISO-8601 time when the first judgments were durably saved",
    )
    args = parser.parse_args(argv)
    if args.phase == "audit":
        return run_audit()
    return run_current(args.judgments_saved_at)


if __name__ == "__main__":
    raise SystemExit(main())
