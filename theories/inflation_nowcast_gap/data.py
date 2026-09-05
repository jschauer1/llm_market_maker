"""Strict source parsers for the ING-1 inflation-nowcast dataset."""

from __future__ import annotations

from datetime import date, datetime, timedelta, time, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "inflation-nowcast-gap/v1"
NY = ZoneInfo("America/New_York")
MEASURES = ("CPI Inflation", "Core CPI Inflation")
SERIES_MEASURE = {"KXCPI": MEASURES[0], "KXCPICORE": MEASURES[1]}
_MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1
)}
_EVENT = re.compile(r"^(KXCPI(?:CORE)?)-(\d{2})([A-Z]{3})$")


class DataError(ValueError):
    """A retained source cannot satisfy the frozen data contract."""


def _decimal_text(value: object, label: str) -> str:
    if isinstance(value, bool) or value in (None, ""):
        raise DataError(f"{label} is missing")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise DataError(f"{label} is not decimal") from exc
    if not number.is_finite():
        raise DataError(f"{label} is not finite")
    return str(value).strip().lstrip("+").replace("-.", "-0.") if str(value).strip() else str(number)


def _target(value: object) -> tuple[int, int, str]:
    match = re.fullmatch(r"(20\d{2})-(\d{1,2})", str(value or ""))
    if not match:
        raise DataError(f"invalid target month {value!r}")
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        raise DataError(f"invalid target month {value!r}")
    return year, month, f"{year:04d}-{month:02d}"


def parse_nowcasts(payload: object) -> dict[str, dict[str, dict[str, str]]]:
    """Return target-month -> observation-date -> exact monthly measures."""
    if not isinstance(payload, list):
        raise DataError("Cleveland payload is not a list")
    output: dict[str, dict[str, dict[str, str]]] = {}
    for envelope in payload:
        if not isinstance(envelope, dict) or not isinstance(envelope.get("chart"), dict):
            raise DataError("Cleveland envelope is malformed")
        year, month, target = _target(envelope["chart"].get("subcaption"))
        categories = envelope.get("categories")
        if not isinstance(categories, list) or len(categories) != 1 or not isinstance(categories[0], dict):
            raise DataError(f"{target} categories are malformed")
        labels = categories[0].get("category")
        if not isinstance(labels, list):
            raise DataError(f"{target} category rows are malformed")
        datasets = envelope.get("dataset")
        if not isinstance(datasets, list):
            raise DataError(f"{target} datasets are malformed")
        by_name = {row.get("seriesname"): row.get("data") for row in datasets if isinstance(row, dict)}
        for measure in MEASURES:
            if not isinstance(by_name.get(measure), list):
                raise DataError(f"{target} missing exact measure {measure}")
            if len(by_name[measure]) != len(labels):
                raise DataError(f"{target} measure/category length mismatch")

        dated: dict[str, dict[str, str]] = {}
        current_year, prior_month = year, None
        for index, raw_label in enumerate(labels):
            label = raw_label.get("label") if isinstance(raw_label, dict) else None
            match = re.fullmatch(r"(\d{2})/(\d{2})", str(label or ""))
            if not match:
                continue
            label_month, day = int(match.group(1)), int(match.group(2))
            if prior_month is not None and label_month < prior_month:
                current_year += 1
            prior_month = label_month
            try:
                observed = date(current_year, label_month, day)
            except ValueError as exc:
                raise DataError(f"{target} has invalid observation date {label}") from exc
            first = date(year, month, 1)
            if not first <= observed <= first + timedelta(days=75):
                raise DataError(f"{target} observation date is outside its chart window")
            values: dict[str, str] = {}
            for measure in MEASURES:
                raw = by_name[measure][index]
                value = raw.get("value") if isinstance(raw, dict) else None
                if value in (None, ""):
                    break
                values[measure] = _decimal_text(value, f"{target} {measure} {label}")
            if len(values) == len(MEASURES):
                dated[observed.isoformat()] = values
        output[target] = dated
    return output


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, value: str) -> None:
        if self._href is not None:
            self._text.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def parse_bls_archive_index(html: str) -> list[dict[str, str]]:
    parser = _Links()
    parser.feed(html)
    rows: dict[str, dict[str, str]] = {}
    for href, label in parser.links:
        match = re.fullmatch(r"([A-Za-z]+)\s+(20\d{2})\s+Consumer Price Index", label)
        path = re.search(r"/archives/cpi_(\d{2})(\d{2})(20\d{2})\.htm$", href, re.I)
        if not match or not path or match.group(1)[:3].upper() not in _MONTHS:
            continue
        target = f"{int(match.group(2)):04d}-{_MONTHS[match.group(1)[:3].upper()]:02d}"
        try:
            release = date(int(path.group(3)), int(path.group(1)), int(path.group(2)))
        except ValueError as exc:
            raise DataError(f"invalid BLS archive URL {href}") from exc
        row = {"target_month": target, "release_date": release.isoformat(),
               "url": urljoin("https://www.bls.gov/bls/news-release/cpi.htm", href)}
        if target in rows and rows[target] != row:
            raise DataError(f"conflicting BLS releases for {target}")
        rows[target] = row
    if not rows:
        raise DataError("BLS archive index has no CPI HTML releases")
    return sorted(rows.values(), key=lambda row: row["target_month"])


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, value: str) -> None:
        self.parts.append(value)


def _signed_change(text: str, subject: str, month_name: str) -> str:
    if subject == "headline":
        anchor = r"Consumer Price Index for All Urban Consumers\s*\(CPI-U\)"
    else:
        anchor = r"(?:index for\s+)?all items less food and energy"
    action = r"(?P<action>increased|rose|advanced|declined|decreased|fell|dropped|was unchanged|unchanged)"
    anchor_match = re.search(anchor, text, re.I)
    if not anchor_match:
        raise DataError(f"BLS release missing {subject} first-print statement")
    statement = text[anchor_match.start():anchor_match.start() + 400]
    if subject == "headline" and (
        month_name.lower() not in statement.lower() or "seasonally adjusted" not in statement.lower()
    ):
        raise DataError("BLS headline statement does not identify monthly seasonally adjusted change")
    match = re.search(
        action + r"(?:\s+(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))\s+percent)?",
        statement, re.I,
    )
    if not match:
        raise DataError(f"BLS release missing {subject} first-print statement")
    action_text = match.group("action").lower()
    if "unchanged" in action_text:
        return "0.0"
    raw = match.group("value")
    if raw is None:
        raise DataError(f"BLS release missing {subject} value")
    number = Decimal(raw)
    if action_text in {"declined", "decreased", "fell", "dropped"}:
        number = -abs(number)
    elif number < 0:
        raise DataError(f"BLS {subject} direction conflicts with value")
    if number.as_tuple().exponent < -1:
        raise DataError(f"BLS {subject} value is not a one-decimal first print")
    return f"{number:.1f}"


def parse_bls_first_release(html: str, target_month: str) -> dict[str, str]:
    year, month, canonical = _target(target_month)
    parser = _Text()
    parser.feed(html)
    text = " ".join(" ".join(parser.parts).split())
    month_name = date(year, month, 1).strftime("%B")
    if not re.search(rf"Consumer Price Index\s+[^A-Za-z0-9]+\s*{month_name}\s+{year}", text, re.I):
        raise DataError(f"BLS release does not identify target {canonical}")
    stamp = re.search(
        r"(?:embargoed until\s+)?8:30\s+a\.m\.\s+\((EST|EDT|ET)\)\s+"
        r"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+)?"
        r"([A-Za-z]+)\s+(\d{1,2}),\s+(20\d{2})",
        text, re.I,
    )
    if not stamp:
        raise DataError("BLS release missing exact 8:30 publication timestamp")
    release_day = datetime.strptime(
        f"{stamp.group(2)} {stamp.group(3)} {stamp.group(4)}", "%B %d %Y"
    ).date()
    published = datetime.combine(release_day, time(8, 30), NY)
    expected_zone = "EDT" if published.utcoffset() == timedelta(hours=-4) else "EST"
    if stamp.group(1).upper() not in {"ET", expected_zone}:
        raise DataError("BLS timestamp timezone label conflicts with calendar date")
    return {
        "headline": _signed_change(text, "headline", month_name),
        "core": _signed_change(text, "core", month_name),
        "published_at": published.isoformat(),
    }


def entry_for(release_ts: datetime, source_dates: list[str] | None = None) -> datetime:
    """Return noon ET on the latest verified source business day before release."""
    if release_ts.tzinfo is None:
        raise DataError("release timestamp is not aware")
    release_day = release_ts.astimezone(NY).date()
    if source_dates is not None:
        available = sorted(date.fromisoformat(value) for value in source_dates)
        eligible = [value for value in available if value < release_day and value.weekday() < 5]
        if not eligible or (release_day - eligible[-1]).days > 4:
            raise DataError("Cleveland has no row on the last source business day")
        prior = eligible[-1]
    else:
        prior = release_day - timedelta(days=1)
        while prior.weekday() >= 5:
            prior -= timedelta(days=1)
    return datetime.combine(prior, time(12), NY)


def parse_contract(raw: object) -> tuple[dict | None, str | None]:
    """Parse only exact headline/core CPI, one-decimal, strict-above ladders."""
    if not isinstance(raw, dict):
        return None, "market_not_object"
    event_ticker = str(raw.get("event_ticker") or "").upper()
    match = _EVENT.fullmatch(event_ticker)
    if not match or match.group(3) not in _MONTHS:
        return None, "unsupported_event_ticker"
    series = match.group(1)
    target = f"{2000 + int(match.group(2)):04d}-{_MONTHS[match.group(3)]:02d}"
    rules = raw.get("rules_primary")
    if not isinstance(rules, str):
        return None, "rules_missing"
    if raw.get("strike_type") != "greater" or not re.search(r"\b(?:more than|above)\b", rules, re.I):
        return None, "rules_not_strict_above"
    year, month = target.split("-")
    month_name = date(int(year), int(month), 1).strftime("%B")
    if month_name.lower() not in rules.lower() or year not in rules:
        return None, "rules_target_month_mismatch"
    if "single-decimal" not in rules.lower() and "single-decimal" not in str(raw.get("rules_secondary") or "").lower():
        # Core uses "single-decimal value" in secondary on current records.
        secondary = str(raw.get("rules_secondary") or "")
        if "single-decimal" not in secondary.lower():
            return None, "rules_not_single_decimal"
    if series == "KXCPICORE" and "less food and energy" not in rules.lower():
        return None, "rules_measure_mismatch"
    if series == "KXCPI" and "consumer price index" not in rules.lower():
        return None, "rules_measure_mismatch"
    try:
        strike = Decimal(str(raw.get("floor_strike")))
    except InvalidOperation:
        return None, "strike_invalid"
    if not strike.is_finite():
        return None, "strike_invalid"
    return {"series_ticker": series, "event_ticker": event_ticker,
            "target_month": target, "strike": strike}, None


def normalize_candle(payload: object, entry_ts: int) -> dict[str, str | int | None]:
    if not isinstance(payload, dict) or not isinstance(payload.get("candlesticks"), list):
        raise DataError("candle response has no candlesticks list")
    rows = [row for row in payload["candlesticks"]
            if isinstance(row, dict) and row.get("end_period_ts") == entry_ts]
    if len(rows) != 1:
        raise DataError("candle response must contain exactly one bar ending at entry")
    raw = rows[0]

    def close(group: str) -> str | None:
        block = raw.get(group)
        if block is None:
            return None
        if not isinstance(block, dict):
            raise DataError(f"{group} is not an object")
        if block.get("close_dollars") not in (None, ""):
            value = _decimal_text(block["close_dollars"], f"{group}.close_dollars")
        elif block.get("close") not in (None, ""):
            legacy = block["close"]
            number = Decimal(_decimal_text(legacy, f"{group}.close"))
            value = str(number if isinstance(legacy, str) and "." in legacy else number / 100)
        else:
            return None
        if not Decimal("0") <= Decimal(value) <= Decimal("1"):
            raise DataError(f"{group}.close outside [0,1]")
        return value

    def count(primary: str, fallback: str) -> str | None:
        value = raw.get(primary, raw.get(fallback))
        return None if value in (None, "") else _decimal_text(value, primary)

    return {"end_ts": entry_ts, "yes_bid_close": close("yes_bid"),
            "yes_ask_close": close("yes_ask"),
            "open_interest": count("open_interest_fp", "open_interest"),
            "volume": count("volume_fp", "volume")}


def _critical(dataset: dict) -> dict:
    return {"training_rows": dataset.get("training_rows"), "events": dataset.get("events"),
            "receipts": dataset.get("_receipts")}


def load_dataset(path: str | Path) -> dict:
    dataset_path = Path(path)
    try:
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"cannot load dataset {dataset_path}") from exc
    if not isinstance(dataset, dict) or dataset.get("schema_version") != SCHEMA_VERSION:
        raise DataError("unsupported dataset schema")
    for key, kind in (("sources", dict), ("training_rows", list), ("events", list),
                      ("coverage", dict), ("_receipts", list)):
        if not isinstance(dataset.get(key), kind):
            raise DataError(f"dataset missing {key}")
    expected = hashlib.sha256(json.dumps(
        _critical(dataset), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()).hexdigest()
    if dataset.get("source_digest") != expected:
        raise DataError("source digest mismatch")
    for receipt in dataset["_receipts"]:
        if not isinstance(receipt, dict) or not isinstance(receipt.get("path"), str):
            raise DataError("source receipt is malformed")
        source = Path(receipt["path"])
        if not source.is_absolute():
            source = ROOT / source
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != receipt.get("sha256"):
            raise DataError(f"source receipt digest mismatch: {receipt['path']}")
    protocol = dataset_path.parent / "PROTOCOL.md"
    if not protocol.exists() or hashlib.sha256(protocol.read_bytes()).hexdigest() != dataset.get("protocol_digest"):
        raise DataError("protocol digest mismatch")
    return dataset
