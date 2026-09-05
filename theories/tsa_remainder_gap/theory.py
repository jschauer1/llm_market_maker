"""Theory-contract adapter for the frozen TRG-1 TSA remainder model."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import math
from typing import Mapping

from tools.domain import Candidate, Edge, Leg, Market, ScoredCandidate, ScreenResult
from tools.http import get_json
from tools.kalshi.markets import BASE_URL
from tools.sizing import fee_pts
from tools.theory import Theory, TheoryContext

from .data import entry_for, parse_contract
from .model import InsufficientCounts, PROTOCOL, forecast


UTC = timezone.utc
MIN_EDGE_PTS = 8.0
MAX_SPREAD = 0.10
MIN_OPEN_INTEREST = 100.0
MIN_BEST_ASK_DEPTH = 10.0
ORDERBOOK_URL = f"{BASE_URL}/markets/{{ticker}}/orderbook"


def _bump(counts: dict[str, int], key: str, amount: int = 1) -> None:
    counts[key] = counts.get(key, 0) + amount


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(UTC) if result.tzinfo else None


def _days_to_close(market: Market, now: datetime) -> float:
    close = _timestamp(market.close_time)
    return max(0.0, (close - now).total_seconds() / 86400.0) if close else 0.0


class TsaRemainderGapTheory(Theory):
    id = "tsa_remainder_gap"
    name = "TSA Remainder Gap"
    version = 1
    uses_llm_judgment = False
    prompts = {"other": "theories/tsa_remainder_gap/model.py"}
    protocol = PROTOCOL

    def __init__(self, daily_counts=None, fetch=None):
        self._daily_counts = daily_counts
        self._fetch = fetch

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        funnel = {
            "board": len(ctx.board),
            "population": 0,
            "model_ready": 0,
            "executable": 0,
            "above_edge_floor": 0,
            "candidates": 0,
        }
        removed: dict[str, int] = {}
        if ctx.now.tzinfo is None:
            return ScreenResult((), funnel, {"naive_decision_time": 1})
        now = ctx.now.astimezone(UTC)
        if ctx.run_mode == "backtest" and not ctx.run_id.startswith("exp/"):
            return ScreenResult(
                (), funnel, {"experimental_source_requires_exp_run": 1}
            )
        if ctx.run_mode not in {"live", "backtest"}:
            return ScreenResult((), funnel, {"unsupported_run_mode": 1})
        if ctx.run_mode == "live" and not (
            now.weekday() == 4 and now.hour == 15 and now.minute < 30
        ):
            return ScreenResult((), funnel, {"outside_entry_window": 1})
        if not isinstance(self._daily_counts, Mapping):
            return ScreenResult((), funnel, {"daily_counts_unavailable": 1})

        eligible: list[tuple[float, str, str, Candidate]] = []
        for market in sorted(ctx.board, key=lambda item: item.ticker):
            raw = dict(market.raw) if isinstance(market.raw, Mapping) else {}
            contract_input = dict(raw)
            contract_input.setdefault("event_ticker", market.event_ticker)
            contract_input.setdefault("open_time", market.open_time)
            contract_input.setdefault("rules_primary", market.rules_primary)
            parsed, reason = parse_contract(contract_input)
            if parsed is None:
                _bump(removed, reason or "contract_invalid")
                continue
            week_end = parsed["week_end"]
            strike = parsed["strike"]
            if raw.get("week_end") != week_end.isoformat() or raw.get("strike") != strike:
                _bump(removed, "contract_metadata_mismatch")
                continue
            entry = _timestamp(raw.get("entry_time"))
            if entry != entry_for(week_end):
                _bump(removed, "entry_time_mismatch")
                continue
            if ctx.run_mode == "backtest" and now != entry:
                _bump(removed, "decision_time_mismatch")
                continue
            if ctx.run_mode == "live" and week_end != now.date() + timedelta(days=2):
                _bump(removed, "not_current_week")
                continue
            source_digest = raw.get("source_digest")
            if not isinstance(source_digest, str) or not source_digest:
                _bump(removed, "source_digest_missing")
                continue
            funnel["population"] += 1
            if not market.is_open:
                _bump(removed, "not_open")
                continue
            bid, ask = _number(market.yes_bid), _number(market.yes_ask)
            if bid is None or ask is None or not 0 <= bid <= ask <= 1:
                _bump(removed, "invalid_quote")
                continue
            spread = ask - bid
            if spread > MAX_SPREAD + 1e-12:
                _bump(removed, "spread")
                continue
            oi = _number(market.open_interest)
            if oi is None or oi < MIN_OPEN_INTEREST:
                _bump(removed, "open_interest")
                continue
            try:
                estimate = forecast(self._daily_counts, week_end, strike)
            except InsufficientCounts:
                _bump(removed, "insufficient_counts")
                continue
            except ValueError:
                _bump(removed, "invalid_model_input")
                continue
            funnel["model_ready"] += 1

            for side, model_prob, entry_price in (
                ("yes", estimate.q_yes, ask),
                ("no", estimate.q_no, 1.0 - bid),
            ):
                if not 0 < entry_price < 1:
                    _bump(removed, "invalid_ask")
                    continue
                funnel["executable"] += 1
                fee = fee_pts(entry_price)
                gross = (model_prob - entry_price) * 100.0
                net = gross - fee
                if net + 1e-12 < MIN_EDGE_PTS:
                    _bump(removed, "edge_below_floor")
                    continue
                funnel["above_edge_floor"] += 1
                details = {
                    "protocol": PROTOCOL,
                    "week_end": week_end.isoformat(),
                    "S4": estimate.s4,
                    "strike": strike,
                    "ratio_count": estimate.ratio_count,
                    "model_prob": model_prob,
                    "edge_pts_gross": gross,
                    "fee_pts": fee,
                    "edge_pts_net": net,
                    "entry_time": entry.isoformat(),
                    "decision_time": now.isoformat(),
                    "source_digest": source_digest,
                }
                priced_raw = dict(raw)
                priced_raw["_tsa_remainder_gap"] = details
                priced_market = replace(market, raw=priced_raw, spread=spread)
                candidate = Candidate(
                    legs=(Leg(priced_market, side, entry_price),),
                    days_to_close=_days_to_close(market, now),
                )
                if ctx.run_mode == "live":
                    depth, depth_status = self._best_ask_depth(candidate)
                    if depth_status != "sufficient":
                        _bump(removed, f"depth_{depth_status}")
                        continue
                    details.update({
                        "best_ask_depth": depth,
                        "depth_status": depth_status,
                        "depth_required": MIN_BEST_ASK_DEPTH,
                    })
                    priced_raw["_tsa_remainder_gap"] = details
                    candidate = replace(
                        candidate,
                        legs=(replace(candidate.legs[0], market=replace(
                            candidate.legs[0].market, raw=priced_raw
                        )),),
                    )
                eligible.append((net, market.ticker, side, candidate))

        by_week: dict[str, tuple[float, str, str, Candidate]] = {}
        for row in eligible:
            details = row[3].legs[0].market.raw["_tsa_remainder_gap"]
            key = details["week_end"]
            current = by_week.get(key)
            if current is None or (-row[0], row[1], row[2]) < (
                -current[0], current[1], current[2]
            ):
                if current is not None:
                    _bump(removed, "lower_ranked")
                by_week[key] = row
            else:
                _bump(removed, "lower_ranked")
        candidates = tuple(
            by_week[key][3] for key in sorted(by_week)
        )
        funnel["candidates"] = len(candidates)
        return ScreenResult(candidates, funnel, removed)

    def _best_ask_depth(self, candidate: Candidate) -> tuple[float | None, str]:
        leg = candidate.legs[0]
        fetch = self._fetch or get_json
        try:
            payload = fetch(ORDERBOOK_URL.format(ticker=leg.market.ticker))
            book = payload.get("orderbook_fp")
            if not isinstance(book, Mapping):
                return None, "unavailable"
            levels = book.get("no_dollars" if leg.side == "yes" else "yes_dollars")
            if not isinstance(levels, list):
                return None, "unavailable"
            depth = 0.0
            for level in levels:
                if not isinstance(level, (list, tuple)) or len(level) < 2:
                    continue
                try:
                    implied_ask = 1.0 - float(level[0])
                    size = float(level[1])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(size) and size > 0 and abs(implied_ask - leg.price) <= 1e-12:
                    depth += size
            return depth, "sufficient" if depth >= MIN_BEST_ASK_DEPTH else "shallow"
        except Exception:
            return None, "unavailable"

    def price(self, ctx: TheoryContext, cands: list[Candidate], verdicts=None):
        scored = []
        for candidate in cands:
            details = dict(candidate.legs[0].market.raw["_tsa_remainder_gap"])
            edge = Edge(
                pts_net=details["edge_pts_net"], basis="model",
                pts_gross=details["edge_pts_gross"],
                fee_pts=details["fee_pts"],
                model_prob=details["model_prob"],
            )
            scored.append(ScoredCandidate(
                candidate=candidate,
                edge=edge,
                rationale="TRG-1 fixed 52-week remainder model clears the executable edge floor.",
                disposition="screened",
                evidence_source="tsa",
                extra=details,
            ))
        return scored


__all__ = ["TsaRemainderGapTheory"]
