"""ND-1: one-day continuation after an unusually large daily move."""

from __future__ import annotations

import math
import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from tools.domain import Candidate, Edge, Fetch, Leg, ScoredCandidate, ScreenResult
from tools.sizing import fee_pts
from tools.theory import Theory, TheoryContext

from theories.news_drift.signal import (
    MAX_SPREAD,
    MIN_OPEN_INTEREST,
    PRICE_BAND,
    MoveSignal,
    detect,
)


PROTOCOL = "ND-1"
REPO_ROOT = Path(__file__).resolve().parents[2]
ELIGIBLE_CATEGORIES = {
    "politics": "Politics",
    "elections": "Elections",
    "economics": "Economics",
    "entertainment": "Entertainment",
    "world": "World",
}
ND1_CATEGORIES = tuple(ELIGIBLE_CATEGORIES.values())

HistoryLoader = Callable[[object, datetime], list[dict] | None]


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _category(market) -> str | None:
    value = market.event.get("category") if isinstance(market.event, dict) else None
    if not isinstance(value, str):
        return None
    return ELIGIBLE_CATEGORIES.get(value.strip().lower())


def _bump(mapping: dict, key: str) -> None:
    mapping[key] = mapping.get(key, 0) + 1


def _live_entry(market, signal: MoveSignal) -> tuple[float, float, float, str] | str:
    """Fresh bought-side ask, midpoint and spread, or a gate name."""
    bid = _finite(market.yes_bid)
    ask = _finite(market.yes_ask)
    if bid is None or ask is None or not (0.0 <= bid <= ask <= 1.0):
        return "live_invalid_quote"
    midpoint = (bid + ask) / 2.0
    spread = ask - bid
    if not PRICE_BAND[0] <= midpoint <= PRICE_BAND[1]:
        return "live_entry_band"
    if spread > MAX_SPREAD + 1e-12:
        return "live_spread"
    oi = _finite(market.open_interest)
    if oi is None or oi < MIN_OPEN_INTEREST:
        return "live_open_interest"
    if market.volume_24h is None:
        if signal.entry_volume <= 0.0:
            return "live_no_activity"
        activity_source = "entry_candle"
    else:
        volume_24h = _finite(market.volume_24h)
        if volume_24h is None or volume_24h <= 0.0:
            return "live_no_activity"
        activity_source = "volume_24h"

    if signal.side == "yes":
        entry_price = ask
        directional_mid = midpoint
    else:
        no_ask = _finite(market.no_ask)
        if no_ask is None or not 0.0 <= no_ask <= 1.0:
            return "live_invalid_quote"
        entry_price = no_ask
        directional_mid = 1.0 - midpoint
    return entry_price, directional_mid, spread, activity_source


def _population_scope(artifact: dict, *, production: bool
                      ) -> tuple[dict | None, str | None]:
    """Normalize the population an artifact is allowed to price."""
    if "population_series" in artifact:
        values = artifact.get("population_series")
        if (not isinstance(values, list) or not values
                or any(not isinstance(v, str) or not v.strip() for v in values)):
            return None, "population_scope"
        series = [v.strip() for v in values]
        if len(set(series)) != len(series):
            return None, "population_scope"
        return {"kind": "series", "population_series": series}, None

    values = artifact.get("population_categories")
    if values is None:
        if production:
            return None, "population_scope"
        return {"kind": "all_nd1_categories"}, None
    if (not isinstance(values, list) or len(values) != len(ND1_CATEGORIES)
            or any(not isinstance(v, str) for v in values)
            or set(values) != set(ND1_CATEGORIES)):
        return None, "population_scope"
    return {"kind": "categories", "population_categories": list(values)}, None


def _aware_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _utc(parsed) if parsed.tzinfo is not None else None


def _evidence_file(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    path = path if path.is_absolute() else REPO_ROOT / path
    try:
        resolved = path.resolve()
    except OSError:
        return None
    return resolved if resolved.is_relative_to(REPO_ROOT.resolve()) else None


def _sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _registered_validation_run(ctx: TheoryContext, run_id: str,
                               start: datetime, end: datetime) -> bool:
    if ctx.conn is None:
        return False
    row = ctx.conn.execute(
        "SELECT theory_id, theory_version, tier, uses_llm_judgment, "
        "as_of_start, as_of_end "
        "FROM backtest_runs WHERE run_id = ?", (run_id,),
    ).fetchone()
    return bool(row and row["theory_id"] == "news_drift"
                and row["theory_version"] == 1 and row["tier"] in {"A", "B"}
                and row["uses_llm_judgment"] == 0
                and _aware_time(row["as_of_start"]) == start
                and _aware_time(row["as_of_end"]) == end)


def _validation_plan(artifact: dict, scope: dict, ctx: TheoryContext,
                     *, production: bool) -> tuple[dict | None, str | None]:
    plan = artifact.get("validation_plan")
    if not isinstance(plan, dict):
        return None, "validation_plan"
    run_id = plan.get("run_id")
    start, end = _aware_time(plan.get("start")), _aware_time(plan.get("end"))
    cutoff = _aware_time(artifact.get("training_end"))
    if (not isinstance(run_id, str) or not run_id or run_id.startswith("exp/")
            or start is None or end is None or cutoff is None
            or not cutoff <= start < end):
        return None, "validation_plan"
    series = scope.get("population_series") if scope.get("kind") == "series" else None
    if (not series or plan.get("population_series") != series
            or plan.get("source_digest") != artifact.get("source_digest")
            or plan.get("usable_for_validation") is not True
            or plan.get("population_complete") is not True):
        return None, "validation_scope"
    protocol_digest = plan.get("protocol_digest")
    protocol_path = _evidence_file(plan.get("protocol_path"))
    if (not isinstance(protocol_digest, str) or not protocol_digest
            or _sha256(protocol_path) != protocol_digest):
        return None, "validation_protocol"
    manifest_path = _evidence_file(plan.get("manifest_path"))
    if (_sha256(manifest_path) != plan.get("manifest_digest")):
        return None, "validation_manifest"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, AttributeError):
        return None, "validation_manifest"
    expected = {
        "run_id": run_id,
        "source_digest": artifact.get("source_digest"),
        "protocol_digest": protocol_digest,
        "population_series": series,
        "training_end": artifact.get("training_end"),
        "validation_start": plan.get("start"),
        "validation_end": plan.get("end"),
        "population_complete": True,
    }
    if (not isinstance(manifest, dict)
            or any(manifest.get(key) != value for key, value in expected.items())):
        return None, "validation_manifest"
    excluded = manifest.get("confirmation_excluded_events", [])
    if (not isinstance(excluded, list)
            or any(not isinstance(value, str) or not value for value in excluded)
            or len(excluded) != len(set(excluded))):
        return None, "validation_manifest"
    membership_path = _evidence_file(plan.get("membership_path"))
    if _sha256(membership_path) != plan.get("membership_digest"):
        return None, "validation_membership"
    try:
        membership = json.loads(membership_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, AttributeError):
        return None, "validation_membership"
    if not isinstance(membership, list):
        return None, "validation_membership"
    tickers = set()
    for item in membership:
        if (not isinstance(item, dict) or set(item) != {
                "ticker", "side", "entry_ts", "event_ticker"}
                or not isinstance(item["ticker"], str) or not item["ticker"]
                or item["ticker"] in tickers or item["side"] not in {"yes", "no"}
                or isinstance(item["entry_ts"], bool)
                or not isinstance(item["entry_ts"], int)
                or not isinstance(item["event_ticker"], str)
                or not item["event_ticker"]):
            return None, "validation_membership"
        entry = datetime.fromtimestamp(item["entry_ts"], timezone.utc)
        if not start <= entry < end:
            return None, "validation_membership"
        tickers.add(item["ticker"])
    if not _registered_validation_run(ctx, run_id, start, end):
        return None, "validation_run"
    now = _utc(ctx.now)
    if production:
        if ctx.run_mode != "live" or end > now:
            return None, "validation_end"
    elif (ctx.run_mode != "backtest" or ctx.run_id != run_id
          or not start <= now < end):
        return None, "validation_window"
    return {**plan, "start_dt": start, "end_dt": end,
            "excluded_events": set(excluded), "membership": membership}, None


def _validation_bar(rows: list[dict]) -> str | None:
    from theories.news_drift.analysis import measure
    result = measure(rows, include_reversal=False)
    if result["event"]["clusters"] < 30:
        return "validation_event_clusters"
    if result["day"]["clusters"] < 10:
        return "validation_settlement_days"
    if result["event"]["interval"][0] <= 0.0:
        return "validation_event_ci"
    if result["day"]["interval"][0] <= 0.0:
        return "validation_day_ci"
    return None


def _production_validation_reason(artifact: dict, plan: dict,
                                  ctx: TheoryContext) -> str | None:
    rows = ctx.conn.execute(
        """SELECT o.kalshi_ticker, o.outcome, a.decision_date,
                  a.entry_price, a.model_prob, a.edge_pts_gross, a.fee_pts,
                  a.edge_pts_net, a.edge_basis, a.disposition, a.extra_json,
                  s.result, s.resolved_at
             FROM opportunity_attempts a
             JOIN opportunities o ON o.id = a.opportunity_id
             LEFT JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
            WHERE a.run_id = ? AND o.theory_id = ? AND o.theory_version = ?""",
        (plan["run_id"], "news_drift", 1),
    ).fetchall()
    if not rows:
        return "validation_empty"
    if len(rows) != len({row["kalshi_ticker"] for row in rows}):
        return "validation_duplicate_ticker"
    residual = artifact["residual"]
    valued = []
    actual_membership = []
    now = _utc(ctx.now)
    for row in rows:
        try:
            decision = datetime.fromisoformat(row["decision_date"]).replace(
                tzinfo=timezone.utc)
            extra = json.loads(row["extra_json"] or "{}")
        except (TypeError, ValueError):
            return "validation_row"
        if not plan["start_dt"] <= decision < plan["end_dt"]:
            return "validation_window"
        resolved = _aware_time(row["resolved_at"])
        if row["result"] not in {"yes", "no"} or resolved is None:
            return "validation_pending"
        if resolved > now or resolved < decision:
            return "validation_settlement_time"
        if (not isinstance(extra, dict) or extra.get("protocol") != PROTOCOL
                or extra.get("series_ticker") not in plan["population_series"]
                or not isinstance(extra.get("event_ticker"), str)
                or extra.get("calibration_source_digest") != artifact["source_digest"]
                or extra.get("calibration_status") != "usable_validation"):
            return "validation_row"
        entry_ts = extra.get("entry_ts")
        if (isinstance(entry_ts, bool) or not isinstance(entry_ts, int)):
            return "validation_row"
        actual_membership.append({
            "ticker": row["kalshi_ticker"], "side": row["outcome"],
            "entry_ts": entry_ts, "event_ticker": extra["event_ticker"],
        })
        mid = _finite(extra.get("current_directional_mid"))
        recorded_residual = _finite(extra.get("calibration_residual"))
        price, model_prob = _finite(row["entry_price"]), _finite(row["model_prob"])
        if mid is None or recorded_residual != residual or price is None:
            return "validation_row"
        expected_prob = max(0.0, min(1.0, mid + residual))
        expected_gross = (expected_prob - price) * 100.0
        expected_fee = fee_pts(price)
        expected_net = expected_gross - expected_fee
        recorded = [model_prob, _finite(row["edge_pts_gross"]),
                    _finite(row["fee_pts"]), _finite(row["edge_pts_net"])]
        expected = [expected_prob, expected_gross, expected_fee, expected_net]
        if (row["edge_basis"] != "model" or any(value is None for value in recorded)
                or any(abs(got - want) > 1e-8 for got, want in zip(recorded, expected))
                or row["disposition"] != ("screened" if expected_net > 0 else "rejected")):
            return "validation_pricing"
        if expected_net > 0:
            valued.append({
                "result": row["result"], "side": row["outcome"],
                "entry_price": price, "directional_mid": mid,
                "event_ticker": extra["event_ticker"],
                "settlement_day": resolved.date().isoformat(),
            })
    key = lambda item: (item["ticker"], item["side"], item["entry_ts"],
                        item["event_ticker"])
    if sorted(actual_membership, key=key) != sorted(plan["membership"], key=key):
        return "validation_membership"
    reason = _validation_bar(valued)
    if reason:
        return reason
    excluded = plan["excluded_events"]
    if excluded:
        reason = _validation_bar(
            [row for row in valued if row["event_ticker"] not in excluded]
        )
        if reason:
            return "confirmation_" + reason
    return None


def _artifact_status(artifact: object, ctx: TheoryContext
                     ) -> tuple[str, str | None, dict]:
    if not isinstance(artifact, dict) or not artifact:
        return "unusable", "missing_or_malformed", {"kind": "invalid"}
    if artifact.get("protocol") != PROTOCOL:
        return "unusable", "protocol", {"kind": "invalid"}
    if artifact.get("approved") is not True:
        return "unusable", "approval", {"kind": "invalid"}
    cutoff = _aware_time(artifact.get("training_end"))
    if cutoff is None:
        return "unusable", "training_end", {"kind": "invalid"}
    if cutoff > _utc(ctx.now):
        return "unusable", "future_training_cutoff", {"kind": "invalid"}

    residual = _finite(artifact.get("residual"))
    n = artifact.get("n")
    clusters = artifact.get("event_clusters")
    digest = artifact.get("source_digest")
    if residual is None:
        return "unusable", "residual", {"kind": "invalid"}
    if isinstance(n, bool) or not isinstance(n, int) or n < 30:
        return "unusable", "training_n", {"kind": "invalid"}
    if isinstance(clusters, bool) or not isinstance(clusters, int) or clusters < 10:
        return "unusable", "event_clusters", {"kind": "invalid"}
    if not isinstance(digest, str) or not digest.strip():
        return "unusable", "source_digest", {"kind": "invalid"}

    eligible = artifact.get("eligible_for_production")
    if (eligible is False and ctx.run_mode == "backtest"
            and ctx.run_id.startswith("exp/")):
        scope, scope_reason = _population_scope(artifact, production=False)
        if scope_reason:
            return "unusable", scope_reason, {"kind": "invalid"}
        return "usable_experiment", None, scope
    scope, scope_reason = _population_scope(artifact, production=True)
    if scope_reason:
        return "unusable", scope_reason, {"kind": "invalid"}
    if ctx.run_mode == "backtest":
        _plan, validation_reason = _validation_plan(
            artifact, scope, ctx, production=False
        )
        if validation_reason:
            return "unusable", validation_reason, scope
        return "usable_validation", None, scope
    if eligible is not True:
        return "unusable", "production_eligibility", scope
    plan, validation_reason = _validation_plan(
        artifact, scope, ctx, production=True
    )
    if not validation_reason:
        validation_reason = _production_validation_reason(artifact, plan, ctx)
    if validation_reason:
        return "unusable", validation_reason, scope
    return "usable", None, scope


class NewsDriftTheory(Theory):
    id = "news_drift"
    name = "News Drift"
    version = 1
    uses_llm_judgment = False
    prompts = {}

    def __init__(
        self,
        history_loader: HistoryLoader | None = None,
        calibration: dict | None = None,
        fetch: Fetch | None = None,
    ) -> None:
        self._history_loader = history_loader
        self._calibration = calibration
        self._fetch = fetch

    def _history(self, market, now: datetime):
        if self._history_loader is not None:
            return self._history_loader(market, now)
        from theories.news_drift import data
        return data.load_live_history(market, now, fetch=self._fetch)

    def _load_calibration(self):
        if self._calibration is not None:
            return self._calibration
        try:
            from theories.news_drift import data
            return data.load_calibration()
        except (ImportError, OSError, ValueError):
            return None

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        funnel = {
            "board": len(ctx.board),
            "eligible_category": 0,
            "history_coverage": 0,
            "missing_history_coverage": 0,
            "signals": 0,
            "candidates": 0,
        }
        removed: dict[str, int] = {}
        candidates: list[Candidate] = []
        seen: set[str] = set()
        as_of_ts = int(_utc(ctx.now).timestamp())

        for market in ctx.board:
            category = _category(market)
            if category is None:
                raw_category = market.event.get("category") if isinstance(market.event, dict) else None
                label = str(raw_category).strip() if raw_category else "unknown"
                _bump(removed, f"category:{label}")
                continue
            funnel["eligible_category"] += 1
            if not market.is_open:
                _bump(removed, "not_open")
                continue
            if market.ticker in seen:
                _bump(removed, "duplicate_ticker")
                continue
            seen.add(market.ticker)

            try:
                history = self._history(market, ctx.now)
            except Exception:
                history = None
            if not isinstance(history, list) or len(history) < 5:
                funnel["missing_history_coverage"] += 1
                _bump(removed, "missing_history_coverage")
                continue
            funnel["history_coverage"] += 1
            signal = detect(history, as_of_ts)
            if signal is None:
                _bump(removed, "no_signal")
                continue
            funnel["signals"] += 1

            entry_source = "daily_candle"
            activity_source = "entry_candle"
            entry_price = signal.entry_price
            current_directional_mid = signal.directional_mid
            entry_spread = signal.entry_spread
            if ctx.run_mode == "live":
                live = _live_entry(market, signal)
                if isinstance(live, str):
                    _bump(removed, live)
                    continue
                (entry_price, current_directional_mid, entry_spread,
                 activity_source) = live
                entry_source = "live_quote"

            features = asdict(signal)
            features.update({
                "protocol": PROTOCOL,
                "category": category,
                "event_ticker": market.event_ticker,
                "series_ticker": market.series_ticker,
                "entry_source": entry_source,
                "live_activity_source": activity_source,
                "deadline_unknown": True,
                "current_directional_mid": current_directional_mid,
                "daily_to_current_mid_deviation": (
                    current_directional_mid - signal.directional_mid
                ),
            })
            raw = dict(market.raw)
            raw["_news_drift"] = features
            priced_market = replace(market, raw=raw, spread=entry_spread)
            candidates.append(Candidate(
                legs=(Leg(market=priced_market, side=signal.side,
                          price=entry_price),),
                # ND-1 has no realized-close or duration selection feature.
                days_to_close=0.0,
            ))

        funnel["candidates"] = len(candidates)
        return ScreenResult(candidates=tuple(candidates), funnel=funnel,
                            gate_removed=removed)

    def price(self, ctx: TheoryContext, cands: list[Candidate],
              verdicts=None) -> list[ScoredCandidate]:
        artifact = self._load_calibration()
        status, reason, scope = _artifact_status(artifact, ctx)
        usable = status.startswith("usable")
        out: list[ScoredCandidate] = []

        for candidate in cands:
            leg = candidate.legs[0]
            features = dict(leg.market.raw.get("_news_drift", {}))
            common_extra = {
                **features,
                "protocol": PROTOCOL,
                "category": features.get("category"),
                "calibration_status": status,
                "calibration_scope": scope,
            }
            if isinstance(artifact, dict):
                common_extra.update({
                    "calibration_training_end": artifact.get("training_end"),
                    "calibration_residual": artifact.get("residual"),
                    "calibration_n": artifact.get("n"),
                    "calibration_event_clusters": artifact.get("event_clusters"),
                    "calibration_source_digest": artifact.get("source_digest"),
                    "calibration_approved": artifact.get("approved"),
                    "eligible_for_production": artifact.get(
                        "eligible_for_production"
                    ),
                })
                validation = artifact.get("validation_evidence")
                if isinstance(validation, dict):
                    common_extra["calibration_validation"] = dict(validation)
            if not usable:
                common_extra["calibration_reason"] = reason
                out.append(ScoredCandidate(
                    candidate=candidate,
                    edge=Edge(pts_net=0.0, basis="prior"),
                    disposition="screened",
                    rationale=(
                        "ND-1 observation only: no usable approved calibration "
                        f"artifact ({reason}); claims zero edge and is not a "
                        "recommendation."
                    ),
                    extra=common_extra,
                ))
                continue

            in_scope = True
            if scope["kind"] == "series":
                in_scope = features.get("series_ticker") in scope["population_series"]
            elif scope["kind"] == "categories":
                in_scope = features.get("category") in scope["population_categories"]
            if not in_scope:
                common_extra["calibration_reason"] = "outside_population_scope"
                out.append(ScoredCandidate(
                    candidate=candidate,
                    edge=Edge(pts_net=0.0, basis="prior"),
                    disposition="screened",
                    rationale=(
                        "ND-1 observation only: this candidate is outside the "
                        "calibration artifact's declared population; claims "
                        "zero edge and is not a recommendation."
                    ),
                    extra=common_extra,
                ))
                continue

            directional_mid = _finite(features.get("current_directional_mid"))
            if directional_mid is None:
                common_extra["calibration_status"] = "unusable"
                common_extra["calibration_reason"] = "missing_directional_mid"
                out.append(ScoredCandidate(
                    candidate=candidate,
                    edge=Edge(pts_net=0.0, basis="prior"),
                    disposition="screened",
                    rationale=(
                        "ND-1 observation only: candidate lacks its point-in-time "
                        "directional midpoint; claims zero edge."
                    ),
                    extra=common_extra,
                ))
                continue

            model_prob = max(0.0, min(1.0, directional_mid + artifact["residual"]))
            gross = (model_prob - leg.price) * 100.0
            fee = fee_pts(leg.price)
            net = gross - fee
            out.append(ScoredCandidate(
                candidate=candidate,
                edge=Edge(
                    pts_net=net,
                    basis="model",
                    pts_gross=gross,
                    fee_pts=fee,
                    model_prob=model_prob,
                ),
                disposition="screened" if net > 0.0 else "rejected",
                rationale=(
                    f"ND-1 {leg.side.upper()} continuation: directional midpoint "
                    f"{directional_mid:.3f} plus frozen residual "
                    f"{artifact['residual']:+.3f}, entered at executable ask "
                    f"{leg.price:.3f}; net edge {net:+.2f} points after fees."
                ),
                extra=common_extra,
            ))
        return out
