"""The opportunity contract (spec section 6).

Every theory, however it works internally, ends by calling
record_opportunity. Two rules are enforced here rather than in prose:

1. Every suggestion must be tradeable on Kalshi. A Polymarket-sourced
   finding keeps its provenance in evidence_source/evidence_market_id but
   still requires a kalshi_ticker.

2. Re-sighting the same thesis updates the existing row rather than
   inserting a new one. A market that stays mispriced for a week is one
   bet seen seven times, not seven bets. entry_price and first_seen_at
   preserve the entry actually available at first sighting, so scoring
   measures a real position rather than an average of repeated looks.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow

LIVE_RUN_ID = "live"
VALID_EDGE_BASES = ("measured", "prior", "model")


def record_opportunity(
    conn: sqlite3.Connection,
    *,
    theory_id: str,
    theory_version: int,
    kalshi_ticker: str,
    outcome: str,
    entry_price: float,
    edge_pts_net: float,
    run_mode: str = "live",
    run_id: str | None = None,
    scan_id: str | None = None,
    spread_at_call: float | None = None,
    volume_at_call: float | None = None,
    model_prob: float | None = None,
    edge_pts_gross: float | None = None,
    fee_pts: float | None = None,
    edge_basis: str = "prior",
    confidence: str | None = None,
    judged_blind: bool | None = None,
    rationale: str | None = None,
    suggested_size: float | None = None,
    evidence_source: str | None = None,
    evidence_market_id: str | None = None,
    extra_json: str | None = None,
    now: str | None = None,
) -> tuple[int, bool]:
    """Record or refresh an opportunity. Returns (id, was_created)."""
    if not kalshi_ticker:
        raise ValueError(
            "kalshi_ticker is required: every suggestion must resolve to a "
            "tradeable Kalshi market"
        )
    if edge_pts_net is None:
        raise ValueError(
            "edge_pts_net is required: it is the common currency used to "
            "rank across theories"
        )
    if run_mode not in ("live", "backtest"):
        raise ValueError(f"invalid run_mode {run_mode!r}")
    if run_mode == "backtest" and not run_id:
        raise ValueError("run_id is required for backtest runs")
    if edge_basis not in VALID_EDGE_BASES:
        raise ValueError(
            f"invalid edge_basis {edge_basis!r}; "
            f"expected one of {VALID_EDGE_BASES}"
        )

    resolved_run_id = run_id or LIVE_RUN_ID
    stamp = now or utcnow()

    existing = conn.execute(
        """
        SELECT id FROM opportunities
        WHERE theory_id = ? AND theory_version = ? AND run_id = ?
          AND kalshi_ticker = ? AND outcome = ?
        """,
        (theory_id, theory_version, resolved_run_id, kalshi_ticker, outcome),
    ).fetchone()

    if existing is not None:
        conn.execute(
            """
            UPDATE opportunities SET
                last_seen_at = ?,
                times_seen = times_seen + 1,
                edge_pts_net = ?,
                model_prob = COALESCE(?, model_prob),
                edge_pts_gross = COALESCE(?, edge_pts_gross),
                fee_pts = COALESCE(?, fee_pts),
                spread_at_call = COALESCE(?, spread_at_call),
                volume_at_call = COALESCE(?, volume_at_call),
                confidence = COALESCE(?, confidence),
                rationale = COALESCE(?, rationale),
                suggested_size = COALESCE(?, suggested_size)
            WHERE id = ?
            """,
            (
                stamp,
                edge_pts_net,
                model_prob,
                edge_pts_gross,
                fee_pts,
                spread_at_call,
                volume_at_call,
                confidence,
                rationale,
                suggested_size,
                existing["id"],
            ),
        )
        conn.commit()
        return existing["id"], False

    cursor = conn.execute(
        """
        INSERT INTO opportunities (
            theory_id, theory_version, run_mode, run_id, scan_id,
            kalshi_ticker, outcome, entry_price, spread_at_call,
            volume_at_call, model_prob, edge_pts_gross, fee_pts,
            screen_edge_pts_net, edge_pts_net, edge_basis, disposition,
            confidence, judged_blind,
            rationale, suggested_size, evidence_source, evidence_market_id,
            user_action, first_seen_at, last_seen_at, times_seen, extra_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  'screened', ?, ?, ?, ?, ?, ?, 'untouched', ?, ?, 1, ?)
        """,
        (
            theory_id,
            theory_version,
            run_mode,
            resolved_run_id,
            scan_id,
            kalshi_ticker,
            outcome,
            entry_price,
            spread_at_call,
            volume_at_call,
            model_prob,
            edge_pts_gross,
            fee_pts,
            edge_pts_net,
            edge_pts_net,
            edge_basis,
            confidence,
            1 if judged_blind else (0 if judged_blind is not None else None),
            rationale,
            suggested_size,
            evidence_source,
            evidence_market_id,
            stamp,
            stamp,
            extra_json,
        ),
    )
    conn.commit()
    return cursor.lastrowid, True


def get_opportunity(
    conn: sqlite3.Connection, opportunity_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)
    ).fetchone()


def list_opportunities(
    conn: sqlite3.Connection,
    theory_id: str | None = None,
    run_mode: str | None = None,
    disposition: str | None = None,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[object] = []
    if theory_id is not None:
        clauses.append("theory_id = ?")
        params.append(theory_id)
    if run_mode is not None:
        clauses.append("run_mode = ?")
        params.append(run_mode)
    if disposition is not None:
        clauses.append("disposition = ?")
        params.append(disposition)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return conn.execute(
        f"SELECT * FROM opportunities{where} ORDER BY id", params
    ).fetchall()
