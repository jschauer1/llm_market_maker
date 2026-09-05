"""Stable data contract and strict settlement labels for WG-1."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re


_STATION_RULE_ALIASES = {
    "KNYC": ("new york city", "central park, new york"),
    "KLAX": ("los angeles",),
    "KMDW": ("chicago",),
}


def _null_label(reason: str) -> dict:
    return {"value": None, "resolved_at": None, "reason": reason}


def _aware_iso(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.isoformat()


def _station_rule_matches(rule: str, station: dict) -> bool:
    lowered = rule.lower()
    cli = str(station["cli_id"]).lower()
    markers = re.findall(r"\bcli\s*([a-z]{3})\b", lowered)
    if markers:
        return all(marker == cli for marker in markers)
    aliases = _STATION_RULE_ALIASES.get(str(station.get("station")), ())
    return any(alias in lowered for alias in aliases)


def _nws_provider(rule: str) -> bool:
    lowered = rule.lower()
    return "national weather service" in lowered or bool(
        re.search(r"\bnws\b", lowered)
    )


def nws_source_rules_match(row: dict, station: dict) -> bool:
    """Require NWS in both rule fields and the payout station in primary."""
    primary = str(row.get("rules_primary") or "")
    secondary = str(row.get("rules_secondary") or "")
    return (
        _nws_provider(primary)
        and _nws_provider(secondary)
        and _station_rule_matches(primary, station)
    )


def normalize_label(
    markets: list[dict], station: dict, *, source_policy: str = "twc"
) -> dict:
    """Return an exact payout temperature only when every label invariant holds."""
    if source_policy not in {"twc", "nws"}:
        raise ValueError("source_policy must be 'twc' or 'nws'")
    if not markets or not all(
        isinstance(row, dict) and str(row.get("status", "")).lower() == "finalized"
        for row in markets
    ):
        return _null_label("not_all_finalized")

    results = [str(row.get("result", "")).lower() for row in markets]
    if any(result not in {"yes", "no"} for result in results):
        return _null_label("non_binary_result")
    if results.count("yes") != 1:
        return _null_label("not_exactly_one_yes")

    settlement_values: list[Decimal] = []
    for row in markets:
        try:
            settled = Decimal(str(row.get("settlement_value_dollars", "")))
        except (InvalidOperation, ValueError):
            return _null_label("non_binary_settlement_value")
        if not settled.is_finite() or settled not in {Decimal(0), Decimal(1)}:
            return _null_label("non_binary_settlement_value")
        settlement_values.append(settled)
    for result, settled in zip(results, settlement_values):
        if settled != (Decimal(1) if result == "yes" else Decimal(0)):
            return _null_label("settlement_value_result_mismatch")

    values: list[Decimal] = []
    for row in markets:
        try:
            value = Decimal(str(row.get("expiration_value", "")))
        except (InvalidOperation, ValueError):
            return _null_label("missing_or_invalid_expiration_value")
        if not value.is_finite():
            return _null_label("missing_or_invalid_expiration_value")
        values.append(value)
    if any(value != values[0] for value in values[1:]):
        return _null_label("inconsistent_expiration_value")
    if values[0] != values[0].to_integral_value():
        return _null_label("expiration_value_not_whole_degree")

    settlements = [_aware_iso(row.get("settlement_ts")) for row in markets]
    if any(value is None for value in settlements):
        return _null_label("missing_or_invalid_settlement_ts")
    instants = [datetime.fromisoformat(value) for value in settlements]
    if any(instant != instants[0] for instant in instants[1:]):
        return _null_label("inconsistent_settlement_ts")

    primary = [str(row.get("rules_primary") or "") for row in markets]
    if source_policy == "twc":
        # This is the frozen production rule: keep its historical behavior
        # unchanged while the diagnostic opts into the stricter NWS branch.
        if any("the weather company" not in rule.lower() for rule in primary):
            return _null_label("source_rule_mismatch")
    else:
        secondary = [str(row.get("rules_secondary") or "") for row in markets]
        if any(not _nws_provider(rule) for rule in (*primary, *secondary)):
            return _null_label("source_rule_mismatch")
    if any(
        not _station_rule_matches(rule, station) for rule in primary
    ):
        return _null_label("station_rule_mismatch")

    return {
        "value": int(values[0]),
        "resolved_at": settlements[0],
        "reason": None,
    }


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a 64-character sha256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be hexadecimal") from exc
    return value


def load_dataset(campaign: str | Path) -> dict:
    """Load the compact campaign interface and verify its immutable identities."""
    root = Path(campaign)
    path = root / "dataset.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("dataset must be an object")
    if not isinstance(payload.get("events"), list):
        raise ValueError("dataset events must be a list")
    if not isinstance(payload.get("coverage"), dict):
        raise ValueError("dataset coverage must be an object")
    _digest(payload.get("source_digest"), "source_digest")
    protocol_digest = _digest(payload.get("protocol_digest"), "protocol_digest")
    protocol = root / "PROTOCOL.md"
    if protocol.exists():
        actual = hashlib.sha256(protocol.read_bytes()).hexdigest()
        if actual != protocol_digest:
            raise ValueError("protocol_digest does not match PROTOCOL.md")
    return payload
