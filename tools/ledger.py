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

Two fields are normalized on entry, because the dedup key is compared with
SQLite's case-sensitive binary collation while everything downstream
compares case-insensitively: `outcome` is lowercased and `kalshi_ticker` is
uppercased (Kalshi tickers are uppercase), both stripped. Without this,
recording the same bet as "yes" and "Yes" produces two rows that scoring
then counts as two independent wins.
"""

from __future__ import annotations

import hashlib
import math
import sqlite3

from tools import provenance
from tools.db import utcnow, write

LIVE_RUN_ID = "live"
VALID_DISPOSITIONS = ("screened", "endorsed", "rejected")
VALID_USER_ACTIONS = ("untouched", "taken", "skipped")
VALID_EDGE_BASES = ("measured", "prior", "model")

#: Prefix marking a synthetic header ticker for a multi-leg position.
BASKET_PREFIX = "BASKET:"


def basket_key(legs: list[dict]) -> str:
    """A stable synthetic `kalshi_ticker` for a multi-leg position.

    The header row needs a ticker: the column is NOT NULL and the dedup key
    is built from it. A basket resolves to several real tickers, so the
    header carries a hash of them and the tradeability guarantee moves to
    `opportunity_legs`, where every row has a real one.

    Sorted and case-normalized so the same basket produces the same key on
    every scan regardless of leg ordering. That is what preserves the
    re-sighting rule -- a basket that stays mispriced for a week is one bet
    seen seven times, not seven bets.
    """
    parts = sorted(
        f"{(leg['kalshi_ticker'] or '').strip().upper()}:"
        f"{(leg['outcome'] or '').strip().lower()}"
        for leg in legs
    )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"{BASKET_PREFIX}{digest[:16]}"


def _validate_entry_price(entry_price: object) -> None:
    """Prices are decimal dollars in [0, 1] — enforced at the only entry point.

    The mistake this catches is passing cents. `entry_price=40` is accepted
    silently by SQLite and produces a calibration edge of -3900 points.
    """
    if isinstance(entry_price, bool) or not isinstance(
        entry_price, (int, float)
    ):
        raise ValueError(
            f"entry_price must be a number in decimal dollars [0, 1], "
            f"got {entry_price!r}"
        )
    if isinstance(entry_price, float) and math.isnan(entry_price):
        # NaN compares False to every `>`/`<` check below, so it would
        # otherwise sail through this validator. It is only caught by
        # accident downstream: sqlite3 binds a NaN float as SQL NULL, which
        # then trips the NOT NULL constraint on entry_price and raises a
        # confusing IntegrityError instead of this purpose-built ValueError.
        raise ValueError(
            f"entry_price must be a number in decimal dollars [0, 1], "
            f"got {entry_price!r}"
        )
    if entry_price > 1.0:
        raise ValueError(
            f"entry_price {entry_price!r} is above 1.0; prices are decimal "
            f"dollars in [0, 1], not cents — {entry_price} probably means "
            f"{entry_price / 100.0}"
        )
    if entry_price < 0.0:
        raise ValueError(
            f"entry_price {entry_price!r} is below 0.0; prices are decimal "
            f"dollars in [0, 1]"
        )


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
    if run_mode == "backtest" and run_id == LIVE_RUN_ID:
        raise ValueError(
            f"run_id {LIVE_RUN_ID!r} is a reserved sentinel for live scans; "
            "a backtest using it would collide with, and silently overwrite, "
            "the live row for the same ticker. Give the backtest its own "
            "run_id."
        )
    if edge_basis not in VALID_EDGE_BASES:
        raise ValueError(
            f"invalid edge_basis {edge_basis!r}; "
            f"expected one of {VALID_EDGE_BASES}"
        )
    _validate_entry_price(entry_price)

    # A theory that declares LLM judgment must have recorded which model and
    # which prompt produced it before any opportunity lands. Otherwise the
    # theory's version number promises a decision procedure nobody wrote
    # down, and an edge it finds cannot be reproduced.
    provenance.require_provenance(
        conn, theory_id, theory_version, run_id or LIVE_RUN_ID
    )

    # Normalize before the dedup key is built, so the same bet written with
    # different casing lands on one row rather than several.
    if isinstance(kalshi_ticker, str):
        kalshi_ticker = kalshi_ticker.strip().upper()
    if isinstance(outcome, str):
        outcome = outcome.strip().lower()

    resolved_run_id = run_id or LIVE_RUN_ID
    stamp = now or utcnow()

    # One atomic statement: a SELECT-then-INSERT pair would let a concurrent
    # writer slip between them and turn a re-sighting into an IntegrityError.
    # The DO UPDATE clause deliberately leaves entry_price, first_seen_at and
    # screen_edge_pts_net alone — those record the first sighting and must
    # not drift.
    with write(conn):
        conn.execute(
            """
            INSERT INTO opportunities (
                theory_id, theory_version, run_mode, run_id, scan_id,
                kalshi_ticker, outcome, entry_price, spread_at_call,
                volume_at_call, model_prob, edge_pts_gross, fee_pts,
                screen_edge_pts_net, edge_pts_net, edge_basis, disposition,
                confidence, judged_blind,
                rationale, suggested_size, evidence_source,
                evidence_market_id,
                user_action, first_seen_at, last_seen_at, times_seen,
                extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      'screened', ?, ?, ?, ?, ?, ?, 'untouched', ?, ?, 1, ?)
            ON CONFLICT (theory_id, theory_version, run_id, kalshi_ticker,
                         outcome) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                times_seen = opportunities.times_seen + 1,
                -- Once research has spoken, it supersedes the mechanical
                -- screen: screen_edge_pts_net already preserves the original
                -- screen claim, and there is deliberately no column for
                -- "latest screen value" — the interpretation is the current
                -- best estimate, which is precisely what edge_pts_net means.
                -- So a re-sighting only refreshes edge_pts_net from the new
                -- screen while the row is still uninterpreted; once
                -- interpreted_at is set, the researched value stands.
                edge_pts_net = CASE
                    WHEN opportunities.interpreted_at IS NULL
                        THEN excluded.edge_pts_net
                    ELSE opportunities.edge_pts_net
                END,
                model_prob =
                    COALESCE(excluded.model_prob, opportunities.model_prob),
                edge_pts_gross = COALESCE(excluded.edge_pts_gross,
                                          opportunities.edge_pts_gross),
                fee_pts = COALESCE(excluded.fee_pts, opportunities.fee_pts),
                spread_at_call = COALESCE(excluded.spread_at_call,
                                          opportunities.spread_at_call),
                volume_at_call = COALESCE(excluded.volume_at_call,
                                          opportunities.volume_at_call),
                confidence =
                    COALESCE(excluded.confidence, opportunities.confidence),
                rationale =
                    COALESCE(excluded.rationale, opportunities.rationale),
                suggested_size = COALESCE(excluded.suggested_size,
                                          opportunities.suggested_size)
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

    # `times_seen` is the reliable witness: the insert path writes 1, the
    # update path always increments to at least 2. `cursor.lastrowid` is not
    # meaningful when the conflict clause fired.
    row = conn.execute(
        """
        SELECT id, times_seen FROM opportunities
        WHERE theory_id = ? AND theory_version = ? AND run_id = ?
          AND kalshi_ticker = ? AND outcome = ?
        """,
        (theory_id, theory_version, resolved_run_id, kalshi_ticker, outcome),
    ).fetchone()
    return row["id"], row["times_seen"] == 1


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
    unsettled_only: bool = False,
) -> list[sqlite3.Row]:
    """List opportunities, optionally narrowed by theory/run_mode/disposition.

    `unsettled_only=True` drops any row whose ticker already has a
    `settlements` entry. A re-quote loop (score-theories' "find what has
    resolved" step) only needs to check tickers that have not settled yet;
    without this filter that loop re-quotes every opportunity ever recorded,
    unbounded, on every run.
    """
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
    if unsettled_only:
        clauses.append(
            "kalshi_ticker NOT IN (SELECT kalshi_ticker FROM settlements)"
        )
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return conn.execute(
        f"SELECT * FROM opportunities{where} ORDER BY id", params
    ).fetchall()


def interpret(
    conn: sqlite3.Connection,
    opportunity_id: int,
    disposition: str,
    interpretation: str,
    revised_edge_pts_net: float | None = None,
    now: str | None = None,
) -> None:
    """Record a stage-2 research verdict (spec section 7).

    Rejections are recorded, not deleted: they are the control group that
    makes the value of interpretation measurable. `screen_edge_pts_net` is
    never touched here, so a revised edge stays comparable to what the
    mechanical screen originally claimed.
    """
    if disposition not in VALID_DISPOSITIONS:
        raise ValueError(
            f"invalid disposition {disposition!r}; "
            f"expected one of {VALID_DISPOSITIONS}"
        )
    if get_opportunity(conn, opportunity_id) is None:
        raise KeyError(opportunity_id)

    stamp = now or utcnow()
    with write(conn):
        if revised_edge_pts_net is None:
            conn.execute(
                """
                UPDATE opportunities
                SET disposition = ?, interpretation = ?, interpreted_at = ?
                WHERE id = ?
                """,
                (disposition, interpretation, stamp, opportunity_id),
            )
        else:
            conn.execute(
                """
                UPDATE opportunities
                SET disposition = ?, interpretation = ?, interpreted_at = ?,
                    edge_pts_net = ?
                WHERE id = ?
                """,
                (
                    disposition,
                    interpretation,
                    stamp,
                    revised_edge_pts_net,
                    opportunity_id,
                ),
            )


def mark_user_action(
    conn: sqlite3.Connection,
    opportunity_id: int,
    action: str,
    size: float | None = None,
    reason: str | None = None,
) -> None:
    """Record what the user actually did (spec sections 6 and 7).

    The reason matters: divergence between what the system endorsed and what
    the user bet is usually an unencoded heuristic, and those get mined into
    new theory candidates.
    """
    if action not in VALID_USER_ACTIONS:
        raise ValueError(
            f"invalid action {action!r}; expected one of {VALID_USER_ACTIONS}"
        )
    if get_opportunity(conn, opportunity_id) is None:
        raise KeyError(opportunity_id)
    with write(conn):
        conn.execute(
            """
            UPDATE opportunities
            SET user_action = ?, user_size = ?, user_reason = ?
            WHERE id = ?
            """,
            (action, size, reason, opportunity_id),
        )
