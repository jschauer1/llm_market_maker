"""One-time import of kalshi_trader's real track record.

insider_bias should start with evidence rather than at zero, so its ledger
and scored results come across into the new schema.

The important part is the dedup. kalshi_trader appended a row every time a
run recommended a bet, so a market that stayed attractive for a week appears
five times. Importing that naively would import the exact duplication bug
this design exists to prevent — five rows for one real position, and a
calibration number that counts the same market five times. record_opportunity
upserts, so repeat rows collapse into one with times_seen incremented, and
rows are imported oldest-first so the surviving entry_price is the one that
was actually available at first sighting.

Provenance: kalshi_trader's q values came from OpenAI gpt-5 (LLM
introspection), which this system's spec says model_prob should never come
from. The data is imported anyway — it is the only dataset that can answer
whether LLM-introspected probabilities actually realize their claimed edge —
but it is labeled rather than laundered: edge_basis is the least-trusted
"prior" basis, and extra_json records exactly where the number came from.

Usage:
    python migrate_kalshi_trader.py --source <path-to-kalshi_trader>
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

from tools import db, ledger, score, theories
from tools.sizing import net_edge_pts

THEORY_ID = "insider_bias"
THEORY_NAME = "Insider Bias"
THEORY_PATH = "theories/insider_bias"


def _price(value: str | None) -> float | None:
    """Parse a price that may be decimal dollars or integer cents."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1.0:
        number = number / 100.0
    if not 0.0 <= number <= 1.0:
        return None
    return number


def _number(value: str | None) -> float | None:
    """Parse a plain dollar amount. Not a price — no cents/clamp handling."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(row: dict, *keys: str) -> str | None:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return None


def parse_ledger_row(row: dict) -> dict | None:
    """Convert a kalshi_trader ledger row into record_opportunity kwargs."""
    ticker = _first(row, "ticker", "market_ticker")
    if not ticker:
        return None

    entry_price = _price(_first(row, "price", "fav_price_exec", "fav_price"))
    if entry_price is None:
        return None

    # q_blend is what kalshi_trader actually sized its bets on: it computed
    # q_model (the raw LLM estimate) then shrank it toward the market mid to
    # get q_blend. q_blend is the honest "what did it actually claim" figure,
    # so it is preferred over q_model. The brief's original keys (q,
    # model_q, blended_q) are kept as fallbacks for synthetic/fixture rows.
    model_prob = _price(_first(row, "q_blend", "q_model", "q", "model_q",
                               "blended_q"))
    # A historical row with no recorded q has no claimable edge. Record it at
    # zero rather than inventing one — it still counts toward calibration,
    # which is what the imported history is for.
    edge = (
        net_edge_pts(model_prob, entry_price) if model_prob is not None else 0.0
    )

    return {
        "kalshi_ticker": ticker,
        "outcome": (_first(row, "bet_side", "side") or "yes").lower(),
        "entry_price": entry_price,
        "model_prob": model_prob,
        "edge_pts_net": edge,
        "rationale": _first(row, "rationale", "reason"),
        # run_ts is the real column; timestamp/created_at/ts are kept as
        # fallbacks for synthetic/fixture rows.
        "timestamp": _first(row, "run_ts", "timestamp", "created_at", "ts"),
        "q_model": _price(_first(row, "q_model")),
        "q_blend": _price(_first(row, "q_blend")),
        "stake_usd": _number(_first(row, "stake_usd")),
    }


def migrate(
    conn,
    ledger_rows: list[dict],
    scored_rows: list[dict] | None = None,
    now: str | None = None,
) -> dict:
    """Import ledger rows and settlements. Returns a summary."""
    theories.register(conn, THEORY_ID, THEORY_NAME, THEORY_PATH,
                      status="active", now=now)

    parsed = []
    skipped = 0
    for row in ledger_rows:
        entry = parse_ledger_row(row)
        if entry is None:
            skipped += 1
            continue
        parsed.append(entry)

    # Oldest first, so the surviving entry_price is the one that was actually
    # available when this bet was first recommended.
    parsed.sort(key=lambda e: e["timestamp"] or "")

    imported = 0
    deduped = 0
    # Note on repeat sightings: record_opportunity's ON CONFLICT clause
    # refreshes model_prob to the LATEST sighting's value (COALESCE prefers
    # excluded/new over existing), but extra_json is only written on the
    # initial INSERT and is never touched by the update clause, so it
    # freezes at the FIRST sighting's q_model/q_blend. For a ticker seen
    # more than once, model_prob and extra_json.q_blend can therefore
    # disagree. This is pre-existing behavior of tools.ledger's upsert
    # design (entry_price/first_seen_at also freeze at first sighting on
    # purpose); changing it would mean altering ledger.record_opportunity's
    # ON CONFLICT clause, which affects live scanning far beyond this
    # one-time migration, so it is accepted rather than worked around here.
    # It does not affect compute_score, which reads neither field.
    for entry in parsed:
        _, created = ledger.record_opportunity(
            conn,
            theory_id=THEORY_ID,
            theory_version=1,
            kalshi_ticker=entry["kalshi_ticker"],
            outcome=entry["outcome"],
            entry_price=entry["entry_price"],
            edge_pts_net=entry["edge_pts_net"],
            model_prob=entry["model_prob"],
            rationale=entry["rationale"],
            # The predecessor's probabilities were LLM-introspected (OpenAI
            # gpt-5), never a mechanical model or a measurement, so they get
            # the least-trusted of the three valid bases — labeled, not
            # laundered — with the raw provenance preserved in extra_json.
            edge_basis="prior",
            suggested_size=entry["stake_usd"],
            extra_json=json.dumps({
                "model_prob_source":
                    "kalshi_trader gpt-5 (LLM-introspected)",
                "q_model": entry["q_model"],
                "q_blend": entry["q_blend"],
            }),
            now=entry["timestamp"] or now,
        )
        if created:
            imported += 1
        else:
            deduped += 1

    settlements = 0
    for row in scored_rows or []:
        ticker = _first(row, "ticker", "market_ticker")
        # `result` (the market's resolution: "yes"/"no", empty while
        # unresolved) and `outcome` (whether the BET won: "WIN"/"LOSS"/
        # "pending") are categorically different columns in the real scored
        # CSV — `outcome` must never be used as a fallback for `result`.
        # Conflating them silently wrote "pending" as a settlement result
        # for still-open markets, which never matches a bet's "yes"/"no"
        # outcome and so scored every unresolved row as a guaranteed loss.
        result = _first(row, "result", "settlement_result")
        market_status = _first(row, "market_status")
        if not ticker or not result:
            continue
        # Belt-and-braces: also skip anything explicitly flagged as not yet
        # finalized, in case a future source ever populates `result` early.
        if market_status and market_status.lower() != "finalized":
            continue
        score.record_settlement(
            conn, ticker, str(result).lower(),
            # The real scored CSV carries no resolution timestamp at all
            # (no resolved_at/settled_at/timestamp column) — resolved_at
            # stays NULL rather than being derived from close_time, which
            # is when the market closed, not when it actually resolved.
            resolved_at=_first(row, "resolved_at", "settled_at", "timestamp"),
        )
        settlements += 1

    return {
        "imported": imported,
        "deduped": deduped,
        "settlements": settlements,
        "skipped": skipped,
    }


def _read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True,
                        help="path to the kalshi_trader repo")
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)

    ledger_path = os.path.join(args.source, "ledger", "bets_ledger.csv")
    if not os.path.exists(ledger_path):
        print(f"no ledger at {ledger_path}", file=sys.stderr)
        return 1

    scored: list[dict] = []
    for path in sorted(
        glob.glob(os.path.join(args.source, "kalshi_data_backtest",
                               "scored_*.csv"))
    ):
        scored.extend(_read_csv(path))

    conn = db.connect(args.db) if args.db else db.connect()
    db.init_db(conn)
    try:
        summary = migrate(conn, _read_csv(ledger_path), scored)
    finally:
        conn.close()

    print(
        f"imported {summary['imported']} opportunities "
        f"({summary['deduped']} repeat sightings collapsed, "
        f"{summary['skipped']} unparseable rows skipped), "
        f"{summary['settlements']} settlements"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
