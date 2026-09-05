"""Theory-contract adapter for the frozen WG-1 weather model."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Mapping

from tools.domain import Candidate, Edge, Leg, Market, ScoredCandidate, ScreenResult
from tools.sizing import fee_pts
from tools.theory import Theory, TheoryContext

from .model import InsufficientHistory, PROTOCOL, predict


CAMPAIGN = Path(__file__).resolve().parent / "backtests" / "wg1-20260905"
MIN_EDGE_PTS = 8.0
MIN_ASK = 0.05
MAX_ASK = 0.95
MAX_SPREAD = 0.04
MIN_OPEN_INTEREST = 100.0
UTC = timezone.utc
ORDERBOOK_URL = (
    "https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook"
)
MIN_DEPTH_CONTRACTS = 1.0


def _load_stations():
    from theories.weather_model_gap.stations import STATIONS
    return STATIONS


def _bump(counts: dict[str, int], label: str, n: int = 1) -> None:
    counts[label] = counts.get(label, 0) + n


def _finite(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _entry_timestamp(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return int(value)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return int(parsed.timestamp())
    return None


def _weather_company_rules(raw: Mapping) -> bool:
    text = str(raw.get("rules_secondary") or "").lower()
    return "weather company" in text or "weather.com" in text


def _days_to_close(market: Market, now: datetime) -> float:
    if not market.close_time:
        return 0.0
    try:
        close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return 0.0
    if close.tzinfo is None:
        return 0.0
    return max(0.0, (close - now).total_seconds() / 86_400.0)


def _freshen(board: list[Market], fetch):
    """Requote live markets while retaining only point-in-time WG-1 fields."""
    from tools.kalshi import markets as kmarkets

    try:
        quotes = kmarkets.quotes(sorted({m.ticker for m in board}), fetch=fetch)
    except Exception:
        return [], {"quote_fetch_failed": len(board)}
    out: list[Market] = []
    removed: dict[str, int] = {}
    for base in board:
        quote = quotes.get(base.ticker)
        if quote is None:
            _bump(removed, "fresh_quote_missing")
            continue
        # The current quote payload is allowed to update only executable
        # fields.  Strike/source and the reconstructed entry candle remain
        # those retained in the point-in-time board row.
        out.append(replace(
            base,
            yes_bid=quote.yes_bid,
            yes_ask=quote.yes_ask,
            no_bid=quote.no_bid,
            no_ask=quote.no_ask,
            mid=quote.mid,
            spread=quote.spread,
            volume=quote.volume,
            volume_24h=quote.volume_24h,
            open_interest=quote.open_interest,
            status=quote.status,
            is_open=quote.is_open,
        ))
    return out, removed


class WeatherModelGapTheory(Theory):
    id = "weather_model_gap"
    name = "Weather Model Gap"
    version = 1
    uses_llm_judgment = False
    prompts = {"other": "theories/weather_model_gap/model.py"}
    protocol = PROTOCOL
    source_policy = "twc"

    def __init__(self, dataset=None, validation_check=None, fetch=None):
        self._dataset_value = dataset
        self._validation_check = validation_check
        self._fetch = fetch

    def _dataset(self, ctx: TheoryContext):
        if self._dataset_value is not None:
            return self._dataset_value
        if ctx.run_mode == "live":
            from theories.weather_model_gap.live import load_live_dataset
            return load_live_dataset(now=ctx.now)
        from theories.weather_model_gap import data
        return data.load_dataset(CAMPAIGN)

    def _is_validated(self, conn, series: str, now: datetime) -> bool:
        check = self._validation_check
        if check is None:
            try:
                from theories.weather_model_gap.analysis import production_ready
            except (ImportError, AttributeError):
                return False
            try:
                return production_ready(conn, series, now=now) is True
            except Exception:
                return False
        try:
            return check(conn, series) is True
        except Exception:
            return False

    def _settlement_source_matches(self, raw: Mapping, station: Mapping) -> bool:
        """Source-policy seam; production retains the frozen TWC predicate."""
        return _weather_company_rules(raw)

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        funnel = {
            "board": len(ctx.board),
            "population": 0,
            "events": 0,
            "model_ready": 0,
            "executable": 0,
            "above_edge_floor": 0,
            "candidates": 0,
        }
        removed: dict[str, int] = {}
        now_utc = ctx.now.astimezone(UTC) if ctx.now.tzinfo else None
        if now_utc is None:
            return ScreenResult((), funnel, {"naive_decision_time": 1})
        if ctx.run_mode == "live" and not (
            now_utc.hour == 0 and 0 <= now_utc.minute < 60
        ):
            return ScreenResult((), funnel, {"outside_entry_window": 1})

        try:
            stations = _load_stations()
            dataset = self._dataset(ctx)
        except Exception:
            return ScreenResult((), funnel, {"dataset_unavailable": 1})
        supported = set(stations)
        board = [m for m in ctx.board if m.series_ticker in supported]
        funnel["population"] = len(board)
        unsupported = len(ctx.board) - len(board)
        if unsupported:
            _bump(removed, "unsupported_series", unsupported)

        if ctx.run_mode == "live" and board:
            board, quote_removed = _freshen(board, self._fetch)
            for label, count in quote_removed.items():
                _bump(removed, label, count)

        event_rows = dataset.get("events") if isinstance(dataset, Mapping) else None
        if not isinstance(event_rows, list):
            return ScreenResult((), funnel, {**removed, "invalid_dataset": 1})
        events_by_key = {
            row.get("event_ticker"): row for row in event_rows
            if isinstance(row, Mapping) and row.get("event_ticker")
        }
        grouped: dict[str, list[Market]] = {}
        for market in board:
            key = market.event_ticker or ""
            grouped.setdefault(key, []).append(market)

        candidates: list[Candidate] = []
        for event_ticker in sorted(grouped):
            source_event = events_by_key.get(event_ticker)
            if not isinstance(source_event, Mapping):
                _bump(removed, "dataset_event_missing", len(grouped[event_ticker]))
                continue
            target_date = _parse_date(source_event.get("target_date"))
            if target_date is None:
                _bump(removed, "invalid_target_date", len(grouped[event_ticker]))
                continue
            funnel["events"] += 1
            expected_entry = int(datetime.combine(target_date, time.min, UTC).timestamp())
            usable: list[Market] = []
            activity: dict[str, tuple[float, str, int]] = {}
            seen: set[str] = set()
            for market in sorted(grouped[event_ticker], key=lambda m: m.ticker):
                if market.ticker in seen:
                    _bump(removed, "duplicate_ticker")
                    continue
                seen.add(market.ticker)
                raw = market.raw if isinstance(market.raw, Mapping) else {}
                if not market.is_open:
                    _bump(removed, "not_open")
                    continue
                if not self._settlement_source_matches(
                    raw, stations[market.series_ticker]
                ):
                    _bump(removed, "settlement_source")
                    continue
                bid, ask = _finite(market.yes_bid), _finite(market.yes_ask)
                if (bid is None or ask is None or not 0.0 <= bid <= ask <= 1.0):
                    _bump(removed, "invalid_quote")
                    continue
                spread = ask - bid
                if spread > MAX_SPREAD + 1e-12:
                    _bump(removed, "spread")
                    continue
                oi = _finite(market.open_interest)
                if oi is None or oi < MIN_OPEN_INTEREST:
                    _bump(removed, "open_interest")
                    continue
                if "_wg1_entry_volume" in raw:
                    volume = _finite(raw.get("_wg1_entry_volume"))
                    activity_source = "_wg1_entry_volume"
                else:
                    volume = _finite(market.volume_24h)
                    activity_source = "market.volume_24h"
                if volume is None or volume <= 0.0:
                    _bump(removed, "no_entry_activity")
                    continue
                entry_ts = _entry_timestamp(raw.get("_wg1_entry_ts"))
                if entry_ts != expected_entry:
                    _bump(removed, "entry_timestamp")
                    continue
                usable.append(market)
                activity[market.ticker] = (volume, activity_source, entry_ts)

            if not usable:
                continue
            point_event = dict(source_event)
            point_event["markets"] = [
                {
                    "ticker": market.ticker,
                    "event_ticker": market.event_ticker,
                    "series_ticker": market.series_ticker,
                    "strike_type": market.raw.get("strike_type"),
                    "floor_strike": market.raw.get("floor_strike"),
                    "cap_strike": market.raw.get("cap_strike"),
                }
                for market in usable
            ]
            try:
                prediction = predict(dataset, point_event, now_utc, stations=stations)
            except InsufficientHistory:
                _bump(removed, "insufficient_history", len(usable))
                continue
            except ValueError:
                _bump(removed, "invalid_model_input", len(usable))
                continue
            funnel["model_ready"] += len(usable)
            by_ticker = {item.ticker: item for item in prediction.markets}
            ranked = []
            for market in usable:
                probability = by_ticker[market.ticker]
                side_rows = (
                    ("yes", probability.q_yes, float(market.yes_ask)),
                    ("no", probability.q_no, 1.0 - float(market.yes_bid)),
                )
                for side, model_prob, ask in side_rows:
                    if not MIN_ASK <= ask <= MAX_ASK:
                        _bump(removed, "ask_band")
                        continue
                    funnel["executable"] += 1
                    fee = fee_pts(ask)
                    gross = (model_prob - ask) * 100.0
                    net = gross - fee
                    if net + 1e-12 < MIN_EDGE_PTS:
                        _bump(removed, "edge_below_floor")
                        continue
                    funnel["above_edge_floor"] += 1
                    ranked.append((net, market.ticker, side, market, ask,
                                   model_prob, gross, fee))
            if not ranked:
                continue
            # Highest net edge; exact ties resolve by ticker, then side.
            ranked.sort(key=lambda row: (-row[0], row[1], row[2]))
            best = ranked[0]
            if len(ranked) > 1:
                _bump(removed, "lower_ranked", len(ranked) - 1)
            net, ticker, side, market, ask, model_prob, gross, fee = best
            volume, activity_source, entry_ts = activity[ticker]
            metadata = {
                "protocol": self.protocol,
                "source_policy": self.source_policy,
                "station": prediction.station,
                "series_ticker": prediction.series_ticker,
                "event_ticker": prediction.event_ticker,
                "forecast_run": prediction.forecast_run.isoformat(),
                "target_date": prediction.target_date.isoformat(),
                "forecast_proxy": prediction.forecast_proxy,
                "training_n": prediction.training_n,
                "source_digest": prediction.source_digest,
                "forecast_source_digest": prediction.forecast_source_digest,
                "model_prob": model_prob,
                "edge_pts_gross": gross,
                "fee_pts": fee,
                "edge_pts_net": net,
                "entry_ts": entry_ts,
                "decision_ts": int(now_utc.timestamp()),
                "entry_delay_seconds": int(now_utc.timestamp()) - entry_ts,
                "entry_volume": volume,
                "entry_activity_source": activity_source,
                "entry_quote_source": (
                    "fresh_quote" if ctx.run_mode == "live" else "entry_candle"
                ),
            }
            raw = dict(market.raw)
            raw["_weather_model_gap"] = metadata
            priced_market = replace(market, raw=raw, spread=float(market.yes_ask) - float(market.yes_bid))
            candidates.append(Candidate(
                legs=(Leg(market=priced_market, side=side, price=ask),),
                days_to_close=_days_to_close(market, now_utc),
            ))

        # Event revisions must not create two positions for one station/day.
        # Keep the same frozen rank rule across those revisions as within an
        # event: highest net gap, then ticker, then side.
        by_station_date: dict[tuple[str, str], Candidate] = {}
        for candidate in candidates:
            details = candidate.legs[0].market.raw["_weather_model_gap"]
            key = (details["series_ticker"], details["target_date"])
            current = by_station_date.get(key)
            if current is None:
                by_station_date[key] = candidate
                continue
            current_details = current.legs[0].market.raw["_weather_model_gap"]
            rank = (-details["edge_pts_net"], candidate.ticker,
                    candidate.fav_side)
            current_rank = (-current_details["edge_pts_net"], current.ticker,
                            current.fav_side)
            if rank < current_rank:
                by_station_date[key] = candidate
            _bump(removed, "lower_ranked")
        final_candidates = sorted(
            by_station_date.values(),
            key=lambda c: (
                c.legs[0].market.raw["_weather_model_gap"]["target_date"],
                c.legs[0].market.raw["_weather_model_gap"]["series_ticker"],
                c.ticker,
                c.fav_side,
            ),
        )
        funnel["candidates"] = len(final_candidates)
        return ScreenResult(tuple(final_candidates), funnel, removed)

    def _depth(self, candidate: Candidate) -> tuple[float | None, str]:
        """Contracts offered at or better than the quoted one-contract ask."""
        from tools.http import get_json

        leg = candidate.legs[0]
        fetch = self._fetch or get_json
        try:
            payload = fetch(ORDERBOOK_URL.format(ticker=leg.market.ticker))
            book = payload.get("orderbook_fp")
            if not isinstance(book, Mapping):
                return None, "unavailable"
            opposite = book.get(
                "no_dollars" if leg.side == "yes" else "yes_dollars"
            )
            if not isinstance(opposite, list):
                return None, "unavailable"
            depth = 0.0
            for row in opposite:
                if not isinstance(row, (list, tuple)) or len(row) < 2:
                    continue
                try:
                    implied_ask = 1.0 - float(row[0])
                    size = float(row[1])
                except (TypeError, ValueError):
                    continue
                if (math.isfinite(implied_ask) and math.isfinite(size)
                        and size > 0 and implied_ask <= leg.price + 1e-12):
                    depth += size
            return depth, (
                "sufficient" if depth >= MIN_DEPTH_CONTRACTS else "shallow"
            )
        except Exception:
            return None, "unavailable"

    def price(self, ctx: TheoryContext, cands: list[Candidate], verdicts=None):
        out: list[ScoredCandidate] = []
        for candidate in cands:
            leg = candidate.legs[0]
            details = dict(leg.market.raw.get("_weather_model_gap") or {})
            model_prob = details.get("model_prob")
            series = details.get("series_ticker")
            validated = True
            depth, depth_status = None, "not_required"
            if ctx.run_mode == "live":
                validated = (
                    isinstance(series, str)
                    and self._is_validated(ctx.conn, series, ctx.now)
                )
                depth, depth_status = self._depth(candidate)
                details.update({
                    "depth_contracts": depth,
                    "depth_status": depth_status,
                    "depth_required_contracts": MIN_DEPTH_CONTRACTS,
                })
            supported = validated and depth_status in {"not_required", "sufficient"}
            if supported:
                edge = Edge(
                    pts_net=float(details["edge_pts_net"]),
                    basis="model",
                    pts_gross=float(details["edge_pts_gross"]),
                    fee_pts=float(details["fee_pts"]),
                    model_prob=float(model_prob),
                )
                disposition = "screened"
                rationale = "WG-1 station-error model clears the frozen executable edge floor."
            else:
                edge = Edge(pts_net=0.0, basis="prior")
                disposition = "rejected" if validated and depth_status == "shallow" else "screened"
                if not validated:
                    rationale = "WG-1 observation; this station has not passed its frozen validation gate."
                elif depth_status == "shallow":
                    rationale = "WG-1 observation rejected; less than one contract is offered at the quoted ask."
                else:
                    rationale = "WG-1 observation; order-book depth could not be verified."
            out.append(ScoredCandidate(
                candidate=candidate,
                edge=edge,
                rationale=rationale,
                judged_blind=None,
                disposition=disposition,
                evidence_source="open-meteo",
                extra=details,
            ))
        return out
