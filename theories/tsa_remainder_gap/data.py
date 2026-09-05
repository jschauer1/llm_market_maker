"""Strict parsers for the frozen TSA remainder-gap reconstruction."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


class DataError(ValueError):
    """A captured source cannot satisfy the frozen data contract."""


_RULE = re.compile(
    r"weekly average TSA airport screenings are above\s+"
    r"(?P<strike>[0-9][0-9,.]*)(?:\s*(?P<million>million))?\s+"
    r"for the week ending\s+(?P<date>[A-Za-z]+\s+\d{1,2},\s+\d{4}),\s+"
    r"according to the TSA",
    re.IGNORECASE,
)
_EVENT = re.compile(r"^(?:KX)?TSAW-(\d{2})([A-Z]{3})(\d{2})$")
_MONTHS = {name: i for i, name in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1
)}


def _iso(value: object) -> datetime:
    if not isinstance(value, str):
        raise DataError("timestamp is not a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataError(f"invalid timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise DataError("timestamp is not timezone-aware")
    return parsed.astimezone(timezone.utc)


def entry_for(week_end: date) -> datetime:
    """The contractual Friday 15:00 UTC entry for a Sunday week end."""
    if week_end.weekday() != 6:
        raise DataError("week_end is not Sunday")
    friday = week_end - timedelta(days=2)
    return datetime(friday.year, friday.month, friday.day, 15, tzinfo=timezone.utc)


def _event_date(value: object) -> date | None:
    match = _EVENT.fullmatch(str(value or "").upper())
    if not match or match.group(2) not in _MONTHS:
        return None
    try:
        return date(2000 + int(match.group(1)), _MONTHS[match.group(2)], int(match.group(3)))
    except ValueError:
        return None


def parse_contract(raw: object) -> tuple[dict | None, str | None]:
    """Parse only explicit-TSA, strict-above weekly contracts."""
    if not isinstance(raw, dict):
        return None, "market_not_object"
    rules = raw.get("rules_primary")
    matches = list(_RULE.finditer(rules)) if isinstance(rules, str) else []
    if not matches:
        return None, "rules_not_explicit_tsa_weekly_strict_above"
    if len(matches) != 1:
        return None, "rules_ambiguous_contract"
    match = matches[0]
    if raw.get("strike_type") not in (None, "greater"):
        return None, "not_strict_above"
    try:
        week_end = datetime.strptime(match.group("date"), "%B %d, %Y").date()
    except ValueError:
        return None, "rules_date_invalid"
    if week_end.weekday() != 6:
        return None, "rules_date_not_sunday"
    if _event_date(raw.get("event_ticker")) != week_end:
        return None, "rules_event_date_mismatch"
    try:
        strike = float(match.group("strike").replace(",", ""))
        if match.group("million"):
            strike *= 1_000_000
    except ValueError:
        return None, "rules_strike_invalid"
    if not math.isfinite(strike) or not strike.is_integer() or strike <= 0:
        return None, "rules_strike_invalid"
    strike_i = int(strike)
    floor = raw.get("floor_strike")
    if floor is not None:
        try:
            if isinstance(floor, bool) or float(floor) != strike_i:
                return None, "rules_strike_mismatch"
        except (TypeError, ValueError):
            return None, "rules_strike_invalid"
    try:
        if _iso(raw.get("open_time")) > entry_for(week_end):
            return None, "market_not_open_at_entry"
    except DataError:
        return None, "open_time_invalid"
    return {"week_end": week_end, "strike": strike_i}, None


def _number(value: object, label: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise DataError(f"{label} is boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DataError(f"{label} is not numeric") from exc
    if not math.isfinite(number):
        raise DataError(f"{label} is not finite")
    return number


def normalize_candle(payload: object, entry_ts: int) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("candlesticks"), list):
        raise DataError("candle response has no candlesticks list")
    matches = [row for row in payload["candlesticks"] if isinstance(row, dict) and row.get("end_period_ts") == entry_ts]
    if len(matches) != 1:
        raise DataError("candle response must contain exactly one bar ending at entry")
    raw = matches[0]

    def close(group: str) -> float | None:
        block = raw.get(group)
        if block is None:
            return None
        if not isinstance(block, dict):
            raise DataError(f"{group} is not an object")
        if block.get("close_dollars") not in (None, ""):
            return _number(block["close_dollars"], f"{group}.close_dollars")
        raw_close = block.get("close")
        value = _number(raw_close, f"{group}.close")
        if value is None:
            return None
        # The old schema emitted integer cents.  The fixed-point schema now
        # returned by the historical endpoint emits decimal strings such as
        # "0.9500" under the same key.
        normalized = value if isinstance(raw_close, str) and "." in raw_close else value / 100.0
        if not 0 <= normalized <= 1:
            raise DataError(f"{group}.close is outside [0, 1]")
        return normalized

    return {
        "end_ts": entry_ts,
        "yes_bid_close": close("yes_bid"),
        "yes_ask_close": close("yes_ask"),
        "open_interest": _number(raw.get("open_interest_fp", raw.get("open_interest")), "open_interest"),
        "volume": _number(raw.get("volume_fp", raw.get("volume")), "volume"),
    }


class _Tables(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def parse_tsa_html(html: str, year: int) -> dict[str, int]:
    parser = _Tables()
    parser.feed(html)
    candidates = [table for table in parser.tables if table and table[0] and table[0][0].strip().lower() == "date"]
    if not candidates:
        raise DataError("TSA page has no Date table")
    table = candidates[0]
    header = [cell.strip().lower() for cell in table[0]]
    if len(header) != 2 or header[1] not in {"numbers", str(year)}:
        raise DataError("TSA year source is not a two-column Date/Numbers table")
    output: dict[str, int] = {}
    for row in table[1:]:
        if len(row) != 2:
            raise DataError("TSA year source is not a two-column table")
        try:
            parsed = datetime.strptime(row[0], "%m/%d/%Y").date()
            value = int(row[1].replace(",", ""))
        except ValueError as exc:
            raise DataError(f"invalid TSA row {row!r}") from exc
        if parsed.year != year or value < 0:
            raise DataError(f"invalid TSA year/value row {row!r}")
        key = parsed.isoformat()
        if key in output and output[key] != value:
            raise DataError(f"conflicting duplicate TSA date {key}")
        output[key] = value
    if not output:
        raise DataError("TSA table contains no data rows")
    return output


def load_dataset(path: str | Path) -> dict:
    dataset_path = Path(path)
    try:
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"cannot load dataset {dataset_path}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise DataError("unsupported dataset schema")
    if data.get("source_validated") is not False or data.get("historical_publication_claim") is not False:
        raise DataError("experimental source flags changed")
    if not isinstance(data.get("daily_counts"), dict) or not isinstance(data.get("events"), list):
        raise DataError("dataset is missing daily_counts/events")
    coverage = data.get("coverage")
    receipts = coverage.get("receipts") if isinstance(coverage, dict) else None
    if not isinstance(receipts, list) or not receipts:
        raise DataError("dataset has no source receipts")
    source_digest = hashlib.sha256(json.dumps(
        receipts, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()).hexdigest()
    if source_digest != data.get("source_digest"):
        raise DataError("source digest mismatch")
    for receipt in receipts:
        if not isinstance(receipt, dict) or not isinstance(receipt.get("path"), str):
            raise DataError("source receipt is malformed")
        source = Path(receipt["path"])
        if not source.is_absolute():
            source = ROOT / source
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != receipt.get("sha256"):
            raise DataError(f"source receipt digest mismatch: {receipt['path']}")
    protocol = dataset_path.parent / "PROTOCOL.md"
    if not protocol.exists() or hashlib.sha256(protocol.read_bytes()).hexdigest() != data.get("protocol_digest"):
        raise DataError("protocol digest mismatch")
    return data
