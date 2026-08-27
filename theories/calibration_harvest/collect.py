"""calibration_harvest -- tier-A settled-history collector.

This is the theory's replay, and it lives here rather than in `tools/`
because everything about it is thesis-specific (CLAUDE.md, "What lives in a
theory"): which slice of history is reachable, how an entry price is
reconstructed for *this* theory's horizon bins, and which approximations
that forces.

It is a **collector**, not a one-shot replay, because its population is much
larger than one session can fetch: the two pre-registered domains alone span
~2,650 series (Politics 1,060 + Elections 1,444 + Climate and Weather 154,
recency-filtered, measured 2026-08-27). So it checkpoints per series and
writes every observation to the DB as the series completes. An interrupted
run resumes; it never restarts from zero. That is not politeness -- Kalshi
archives settled markets out of its public API ~60 days after close, so a
market whose rows a crashed run failed to persist may be unrecoverable
upstream by the time anyone re-runs.

**The reconstruction.** For each settled market, for each horizon bin, read
the daily candle at that bin's entry offset and take the ask as of that
candle's close. No candle at that offset means no observation for that bin
-- a market that did not exist 14 days before close contributes nothing to
`1w-1mo`, which is the correct answer and not a gap to fill by
interpolation.

**One market can contribute to several bins, deliberately.** The rows share
an outcome, so they are not independent -- but every row of one market
settles on the same day, so the day-clustered SE this theory mandates
already absorbs that dependence. Documented in THEORY.md's known biases: the
point estimate can still be tilted by markets that contribute unequal
numbers of rows, which is second-order and is why the `n_days` floor, not
`n`, is the gate on calling a cell measured.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from tools import db, ledger, score
from tools.kalshi import history, markets
from tools.http import get_json
from theories.calibration_harvest import cells

#: Entry offset in days before close, per horizon bin. Each is comfortably
#: inside its bin so a one-candle timing slip cannot move an observation
#: into a neighbouring cell.
ENTRY_OFFSET_DAYS: dict[str, float] = {
    "<=2d": 1.0,
    "2d-1w": 4.0,
    "1w-1mo": 14.0,
    "1mo+": 45.0,
}

MAX_SPREAD = 0.07
MIN_VOLUME = 500.0

#: Matches the screen's exclusion, for the same reason: `mention_family`'s
#: population must not be pooled into this theory's evidence.
MENTION_MARKERS = ("MENTION", "SAY", "ACT")

#: Kalshi archives settled markets ~60 days after close; a longer window
#: just returns nothing. Measured 2026-08-25 by the sibling fullcov runs.
REACHABLE_DAYS = 58.0


def _is_mention(series: str | None) -> bool:
    s = (series or "").upper()
    return any(marker in s for marker in MENTION_MARKERS)


def worth_fetching(volume: float | None) -> bool:
    """True if a settled market could ever have cleared the volume floor.

    Cumulative volume only grows, so a market whose FINAL volume is below
    the floor was below it at every earlier moment too -- the live screen
    could never have fired on it. Checking the settlement snapshot first
    skips the candlestick call entirely, which is the collector's dominant
    cost. Same reasoning as `insider_bias.replay.is_candidate`.
    """
    return volume is not None and volume >= MIN_VOLUME


def _candle_at(candles: list[dict], target_ts: int) -> tuple[dict, float] | None:
    """The last candle at or before `target_ts`, and volume accumulated to it.

    "At or before" is what makes this lookahead-free: a candle whose period
    ends after the entry moment already contains information the entry
    decision could not have had. The running volume is summed over exactly
    those same candles, so an entry never sees liquidity that arrived after
    it -- Kalshi's candle volume is per-period, not cumulative, so the sum
    is what the live screen's `volume` field would have shown.
    """
    best = None
    running = 0.0
    for candle in sorted(candles, key=lambda c: c.get("end_ts") or 0):
        ts = candle.get("end_ts")
        if ts is None or ts > target_ts:
            continue
        running += candle.get("volume") or 0.0
        best = candle
    if best is None:
        return None
    return best, running


def observations_for(
    ticker: str,
    series: str,
    category: str | None,
    close_ts: int,
    result: str,
    candles: list[dict],
) -> list[dict]:
    """One observation per horizon bin this market can actually support."""
    out: list[dict] = []
    close_iso = datetime.fromtimestamp(close_ts, timezone.utc) \
        .isoformat().replace("+00:00", "Z")

    for bin_label, offset in ENTRY_OFFSET_DAYS.items():
        target = close_ts - int(offset * 86400)
        found = _candle_at(candles, target)
        if found is None:
            continue
        candle, volume_at_entry = found

        # The live screen's liquidity floor, reconstructed. Without it the
        # collector measures markets `screen.py` would never have surfaced,
        # and every cell rate would describe a population the theory cannot
        # actually trade.
        if volume_at_entry < MIN_VOLUME:
            continue

        yes_bid = candle.get("yes_bid_close")
        yes_ask = candle.get("yes_ask_close")
        if yes_bid is None or yes_ask is None:
            continue

        spread = yes_ask - yes_bid
        if spread > MAX_SPREAD or spread < 0:
            continue

        mid = (yes_bid + yes_ask) / 2.0
        if mid >= 0.5:
            side, price = "yes", yes_ask
        else:
            # The NO ask is the complement of the YES bid: to buy NO you
            # lift the resting YES bid from the other side of the book.
            side, price = "no", round(1.0 - yes_bid, 6)

        key = cells.cell_key(price=price, days_to_close=offset,
                             category=category)
        if key is None:
            continue

        out.append({
            "ticker": ticker,
            "series": series,
            "category": category,
            "cell": key,
            "domain": cells.domain_for(category),
            "horizon_bin": bin_label,
            "price_bin": cells.price_bin(price),
            "entry_price": price,
            "outcome": side,
            "result": result,
            "won": side == result,
            "days_to_close": offset,
            "close_iso": close_iso,
        })
    return out


def record(conn, observations: list[dict], run_id: str) -> int:
    """Write observations plus their settlements. Idempotent by ticker.

    Rows land in `opportunities` with `run_mode='backtest'` rather than in a
    bespoke table so the existing scoring path -- including
    `score.settlement_day_clusters`, which this theory depends on -- works
    with no new machinery. `edge_basis='model'` because a collected row is a
    measurement input, never a recommendation; the cell rate it feeds is
    what may later earn `measured`.

    `resolved_at` is the market's close time, which is what makes day
    clustering meaningful -- omit it and every collected row falls into one
    undated cluster and `n_days` becomes a lie.
    """
    written = 0
    for obs in observations:
        _, created = ledger.record_opportunity(
            conn,
            theory_id="calibration_harvest",
            theory_version=1,
            kalshi_ticker=obs["ticker"],
            outcome=obs["outcome"],
            entry_price=obs["entry_price"],
            edge_pts_net=0.0,
            edge_basis="model",
            run_mode="backtest",
            run_id=run_id,
            rationale=(
                f"tier-A collection row for cell {obs['cell']} "
                f"(entry {obs['days_to_close']:.0f}d before close); "
                f"measurement input, not a recommendation"
            ),
            extra_json=json.dumps({
                "cell": obs["cell"],
                "domain": obs["domain"],
                "horizon_bin": obs["horizon_bin"],
                "price_bin": obs["price_bin"],
                "series_ticker": obs["series"],
                "category": obs["category"],
                "days_to_close_at_entry": obs["days_to_close"],
            }),
        )
        score.record_settlement(
            conn, obs["ticker"], obs["result"], resolved_at=obs["close_iso"]
        )
        if created:
            written += 1
    conn.commit()
    return written


def cell_rates(conn, run_id: str) -> dict[str, dict]:
    """Per-cell wins / n / n_days, read back from what was collected.

    `n_days` counts distinct settlement days, not rows -- the floor that
    decides whether a cell may call itself `measured`.
    """
    sql = """
        SELECT o.extra_json, o.outcome, s.result,
               SUBSTR(COALESCE(s.resolved_at, ''), 1, 10) AS day
        FROM opportunities o
        JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
        WHERE o.theory_id = 'calibration_harvest' AND o.run_id = ?
    """
    acc: dict[str, dict] = {}
    for row in conn.execute(sql, (run_id,)).fetchall():
        extra = json.loads(row["extra_json"] or "{}")
        key = extra.get("cell")
        if not key:
            continue
        cell = acc.setdefault(key, {"wins": 0, "n": 0, "_days": set()})
        cell["n"] += 1
        if row["outcome"] == row["result"]:
            cell["wins"] += 1
        if row["day"]:
            cell["_days"].add(row["day"])
    return {
        key: {"wins": c["wins"], "n": c["n"], "n_days": len(c["_days"])}
        for key, c in acc.items()
    }


# ---- the driver ----------------------------------------------------------

def load_checkpoint(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"series": {}}


def save_checkpoint(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1), encoding="utf-8")


def target_series(categories: set[str], now: datetime | None = None,
                  recency_days: float = REACHABLE_DAYS) -> list[dict]:
    """Series in the target categories, touched recently enough to matter."""
    now = now or datetime.now(timezone.utc)
    cutoff = now.timestamp() - recency_days * 86400
    payload = get_json(f"{markets.BASE_URL}/series", params={"limit": 1000})
    out = []
    for series in payload.get("series", []):
        if series.get("category") not in categories:
            continue
        if _is_mention(series.get("ticker")):
            continue
        ts = series.get("last_updated_ts")
        if ts:
            try:
                parsed = datetime.fromisoformat(
                    str(ts).replace("Z", "+00:00")
                ).timestamp()
                if parsed < cutoff:
                    continue
            except ValueError:
                pass
        out.append(series)
    return out


def _parse_ts(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return int(datetime.fromisoformat(
            iso.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def collect_series(conn, series: dict, min_close_ts: int, max_close_ts: int,
                   run_id: str) -> dict:
    """Walk one series' settled markets and persist their observations."""
    ticker = series.get("ticker")
    category = series.get("category")
    settled = markets.list_settled(
        limit=1000, min_close_ts=min_close_ts, max_close_ts=max_close_ts,
        series_ticker=ticker,
    )

    observations: list[dict] = []
    no_candles = 0
    below_floor = 0
    for market in settled:
        if not market.result:
            continue
        close_ts = _parse_ts(market.close_time)
        if close_ts is None:
            continue
        if not worth_fetching(market.volume):
            below_floor += 1
            continue
        candles = history.candlesticks(
            ticker, market.ticker,
            start_ts=close_ts - int(60 * 86400),
            end_ts=close_ts,
            period_interval=1440,
        )
        if not candles:
            no_candles += 1
            continue
        observations.extend(observations_for(
            ticker=market.ticker, series=ticker, category=category,
            close_ts=close_ts, result=market.result, candles=candles,
        ))

    written = record(conn, observations, run_id=run_id)
    return {
        "n_settled": len(settled),
        "n_obs": len(observations),
        "written": written,
        "no_candles": no_candles,
        "below_floor": below_floor,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["enumerate", "run", "rates"])
    parser.add_argument("--categories", default="Politics,Elections",
                        help="comma-separated Kalshi series categories")
    parser.add_argument("--run-id", default="backtest-2026-08-27-calharvest")
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--limit-series", type=int, default=None)
    args = parser.parse_args()

    conn = db.connect()
    try:
        if args.mode == "rates":
            for key, rate in sorted(cell_rates(conn, args.run_id).items()):
                print(f"  {key:44s} {rate['wins']:5d}/{rate['n']:<5d} "
                      f"days={rate['n_days']:3d}")
            return

        cats = {c.strip() for c in args.categories.split(",") if c.strip()}
        series_list = target_series(cats)
        print(f"{len(series_list)} series in {sorted(cats)}")
        if args.limit_series:
            series_list = series_list[: args.limit_series]

        if args.mode == "enumerate":
            for series in series_list:
                print(f"  {series.get('ticker'):32s} "
                      f"{series.get('category')}")
            return

        if args.checkpoint is None:
            parser.error("--checkpoint is required for mode=run")

        now = datetime.now(timezone.utc)
        max_close = int(now.timestamp())
        min_close = int(max_close - REACHABLE_DAYS * 86400)

        state = load_checkpoint(args.checkpoint)
        for series in series_list:
            ticker = series.get("ticker")
            if not ticker or ticker in state["series"]:
                continue
            outcome = collect_series(
                conn, series, min_close, max_close, args.run_id
            )
            state["series"][ticker] = outcome
            save_checkpoint(args.checkpoint, state)
            if outcome["n_obs"]:
                print(f"  {ticker:32s} settled={outcome['n_settled']:4d} "
                      f"obs={outcome['n_obs']:4d} "
                      f"thin={outcome['below_floor']:4d} "
                      f"no_candles={outcome['no_candles']:3d}")

        done = state["series"].values()
        print(f"done: {len(state['series'])} series, "
              f"{sum(s['n_obs'] for s in done)} observations")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
