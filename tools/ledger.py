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
import json
import math
import sqlite3

from tools import provenance
from tools.db import utcnow, write

LIVE_RUN_ID = "live"

#: Run ids opening with this prefix are EXPERIMENTS (OOP spec section
#: 3.3a): real forward-test recordings made to try a variant of a theory
#: -- usually a subclass with one method overridden -- without bumping its
#: version. Pooled scoring and pooled bucket rates exclude them, so an
#: experiment can never contaminate the track record it will be compared
#: against. Score one explicitly with run_id="exp/<slug>".
EXPERIMENT_RUN_PREFIX = "exp/"

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

    Raises ValueError if any leg is missing a kalshi_ticker or outcome field
    (after stripping whitespace).
    """
    normalized_pairs = []
    for idx, leg in enumerate(legs):
        ticker = (leg.get('kalshi_ticker') or '').strip().upper()
        outcome = (leg.get('outcome') or '').strip().lower()

        if not ticker:
            raise ValueError(
                f"leg {idx}: kalshi_ticker is required and must not be empty "
                f"(after stripping)"
            )
        if not outcome:
            raise ValueError(
                f"leg {idx}: outcome is required and must not be empty "
                f"(after stripping)"
            )

        normalized_pairs.append((ticker, outcome))

    sorted_pairs = sorted(normalized_pairs)
    digest = hashlib.sha256(
        json.dumps(sorted_pairs, separators=(',', ':')).encode("utf-8")
    ).hexdigest()
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


def _normalize_legs(legs: list[dict], max_payout: float) -> list[dict]:
    """Validate and normalize legs, returning them in a stable order.

    Every leg price goes through the same [0, 1] validator single positions
    use -- a leg is an ordinary Kalshi contract and the cents-vs-dollars
    mistake is just as costly here. The *basket* cost is checked against
    max_payout instead of 1.0, because a NO-basket over k outcomes can
    legitimately cost more than a dollar while paying (k-1).

    Ticker and outcome are both validated here, ahead of `basket_key` --
    `basket_key` only sees the already-normalized list and would otherwise
    raise the same defect, but reported from the wrong layer with a
    confusing stack.

    A repeated (kalshi_ticker, outcome) pair is refused: a basket is a set
    of distinct positions, and the same contract twice is a size-2 position
    in one leg, which this model has no way to represent. Left unchecked it
    also breaks the payout arithmetic -- two identical winning legs pay $2
    against a declared max_payout of $1 -- and `basket_key` would collapse
    the duplicate away, so two different-cost baskets would share one header.
    """
    if not legs:
        raise ValueError(
            "a basket needs at least one leg: the tradeability guarantee "
            "lives on the legs, so a basket with none has no Kalshi market"
        )
    out = []
    seen: set[tuple[str, str]] = set()
    for i, leg in enumerate(legs):
        ticker = (leg.get("kalshi_ticker") or "").strip().upper()
        if not ticker:
            raise ValueError(
                f"leg {i} has no kalshi_ticker: every leg must resolve to a "
                "tradeable Kalshi market"
            )
        outcome = (leg.get("outcome") or "").strip().lower()
        if not outcome:
            raise ValueError(
                f"leg {i} has no outcome: every leg must name the side "
                "(yes/no) it holds"
            )
        _validate_entry_price(leg.get("entry_price"))
        if (ticker, outcome) in seen:
            raise ValueError(
                f"leg {i} duplicates ({ticker}, {outcome}): a basket is a "
                "set of distinct positions, so the same contract and side "
                "may appear only once. Twice is a size-2 position, which "
                "this model does not represent"
            )
        seen.add((ticker, outcome))
        out.append({
            "kalshi_ticker": ticker,
            "outcome": outcome,
            "entry_price": float(leg["entry_price"]),
            "spread_at_call": leg.get("spread_at_call"),
            "volume_at_call": leg.get("volume_at_call"),
        })

    cost = sum(leg["entry_price"] for leg in out)
    # The equality case is separated out because float accumulation makes a
    # cost that is exactly max_payout compare as greater -- 0.1 + 0.2 is
    # 0.30000000000000004 -- which produced the self-contradicting message
    # "basket cost 0.3000 exceeds max_payout 0.3000". Both cases are still
    # refused: a basket whose best branch only returns what it cost cannot
    # profit, and fees turn break-even into a loss.
    if math.isclose(cost, max_payout, rel_tol=1e-9):
        raise ValueError(
            f"basket cost {cost:.4f} equals max_payout {max_payout:.4f}; "
            "a position whose best case is break-even is not an edge -- "
            "fees make it a loss"
        )
    if cost > max_payout:
        raise ValueError(
            f"basket cost {cost:.4f} exceeds max_payout {max_payout:.4f}; "
            "a position that cannot profit in any branch is not an edge"
        )
    # Sorted so leg_index is deterministic across re-sightings, matching
    # basket_key's ordering.
    out.sort(key=lambda leg: (leg["kalshi_ticker"], leg["outcome"]))
    return out


def record_basket(
    conn: sqlite3.Connection,
    *,
    theory_id: str,
    theory_version: int,
    legs: list[dict],
    edge_pts_net: float,
    max_payout: float = 1.0,
    min_payout: float = 0.0,
    run_mode: str = "live",
    run_id: str | None = None,
    scan_id: str | None = None,
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
    """Record or refresh a multi-leg position. Returns (id, was_created).

    The header row carries the aggregate -- `entry_price` is the basket's
    total cost, `leg_count` is N, `max_payout` is the most it can pay -- and
    `opportunity_legs` carries the tradeable tickers. `min_payout` is the
    least it can pay -- a guaranteed floor, as for a basket with an
    unconditional leg or an unhedgeable overlap between outcomes -- so that
    scoring can grade only the at-risk portion above it instead of treating
    a position that always wins as if every dollar of it were a bet (spec
    sections 3.6 and 3.6.1).

    Re-sighting contract, mirroring `record_opportunity`'s single-position
    rows: `entry_price` is frozen at first sighting on *both* the header and
    every leg, along with each leg's `kalshi_ticker`, `outcome`, and
    `leg_index` -- they record the entry actually available when the basket
    was first seen and must not drift. `min_payout` is frozen the same way,
    for the same reason. Only `last_seen_at`, `times_seen`, `edge_pts_net`
    (while uninterpreted), and the legs' `spread_at_call` / `volume_at_call`
    refresh on a re-sighting.
    """
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
            f"run_id {LIVE_RUN_ID!r} is a reserved sentinel for live scans"
        )
    if edge_basis not in VALID_EDGE_BASES:
        raise ValueError(
            f"invalid edge_basis {edge_basis!r}; "
            f"expected one of {VALID_EDGE_BASES}"
        )
    if (
        isinstance(max_payout, bool)
        or not isinstance(max_payout, (int, float))
        or (isinstance(max_payout, float) and math.isnan(max_payout))
        or max_payout <= 0
    ):
        # `_normalize_legs` only rejects cost > max_payout, which an
        # all-zero-price basket with max_payout=0.0 sails through (0.0 > 0.0
        # is False). Scoring then has no honest denominator to normalize
        # against -- a basket that can never pay anything is not a
        # position, so refuse it here rather than let a nonsense max_payout
        # reach the ledger and fabricate edge downstream.
        raise ValueError(
            f"max_payout must be a positive number, got {max_payout!r}"
        )
    if (
        isinstance(min_payout, bool)
        or not isinstance(min_payout, (int, float))
        or (isinstance(min_payout, float) and math.isnan(min_payout))
        or min_payout < 0
    ):
        raise ValueError(
            f"min_payout must be a non-negative number, got {min_payout!r}"
        )
    if min_payout > max_payout:
        raise ValueError(
            f"min_payout {min_payout!r} exceeds max_payout {max_payout!r}; "
            "a position cannot guarantee more than it can pay"
        )

    norm = _normalize_legs(legs, max_payout)
    provenance.require_provenance(
        conn, theory_id, theory_version, run_id or LIVE_RUN_ID
    )

    header_ticker = basket_key(norm)
    cost = sum(leg["entry_price"] for leg in norm)
    resolved_run_id = run_id or LIVE_RUN_ID
    stamp = now or utcnow()

    with write(conn):
        conn.execute(
            """
            INSERT INTO opportunities (
                theory_id, theory_version, run_mode, run_id, scan_id,
                kalshi_ticker, outcome, entry_price, position_kind,
                leg_count, max_payout, min_payout, model_prob, edge_pts_gross,
                fee_pts, screen_edge_pts_net, edge_pts_net, edge_basis,
                disposition, confidence, judged_blind, rationale,
                suggested_size, evidence_source, evidence_market_id,
                user_action, first_seen_at, last_seen_at, times_seen,
                extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, 'basket', ?, 'basket', ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, 'screened', ?, ?, ?, ?, ?, ?, 'untouched',
                      ?, ?, 1, ?)
            ON CONFLICT (theory_id, theory_version, run_id, kalshi_ticker,
                         outcome) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                times_seen = opportunities.times_seen + 1,
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
                confidence =
                    COALESCE(excluded.confidence, opportunities.confidence),
                rationale =
                    COALESCE(excluded.rationale, opportunities.rationale),
                suggested_size = COALESCE(excluded.suggested_size,
                                          opportunities.suggested_size)
            """,
            (
                theory_id, theory_version, run_mode, resolved_run_id, scan_id,
                header_ticker, cost, len(norm), max_payout, min_payout,
                model_prob, edge_pts_gross, fee_pts, edge_pts_net,
                edge_pts_net, edge_basis, confidence,
                1 if judged_blind else (0 if judged_blind is not None else None),
                rationale, suggested_size, evidence_source,
                evidence_market_id, stamp, stamp, extra_json,
            ),
        )

        row = conn.execute(
            """
            SELECT id, times_seen FROM opportunities
            WHERE theory_id = ? AND theory_version = ? AND run_id = ?
              AND kalshi_ticker = ? AND outcome = 'basket'
            """,
            (theory_id, theory_version, resolved_run_id, header_ticker),
        ).fetchone()

        # The leg set is identical across every sighting by construction --
        # `header_ticker` is a hash of (ticker, outcome) pairs, so a
        # different set of legs produces a different basket_key and lands on
        # a different header row entirely; there is no scenario where this
        # opportunity_id sees a changed leg set, and leg_index (sorted the
        # same way basket_key is) is therefore stable across sightings too.
        # The ON CONFLICT clause below leaves entry_price, kalshi_ticker, and
        # outcome untouched on a re-sighting -- frozen at first sighting,
        # matching the header's frozen entry_price above -- and refreshes
        # only spread_at_call/volume_at_call, which describe current market
        # conditions rather than the position taken. No DELETE is needed:
        # the leg set never changes shape, so there is no stale row to clear.
        conn.executemany(
            """
            INSERT INTO opportunity_legs (
                opportunity_id, leg_index, kalshi_ticker, outcome,
                entry_price, spread_at_call, volume_at_call
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (opportunity_id, leg_index) DO UPDATE SET
                spread_at_call = excluded.spread_at_call,
                volume_at_call = excluded.volume_at_call
            """,
            [
                (row["id"], i, leg["kalshi_ticker"], leg["outcome"],
                 leg["entry_price"], leg["spread_at_call"],
                 leg["volume_at_call"])
                for i, leg in enumerate(norm)
            ],
        )

    return row["id"], row["times_seen"] == 1


def get_legs(
    conn: sqlite3.Connection, opportunity_id: int
) -> list[sqlite3.Row]:
    """Every leg of a position, in stable order. Empty for a single."""
    return conn.execute(
        "SELECT * FROM opportunity_legs WHERE opportunity_id = ?"
        " ORDER BY leg_index",
        (opportunity_id,),
    ).fetchall()


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

    `unsettled_only=True` drops any row whose position has fully settled. A
    re-quote loop (score-theories' "find what has resolved" step) only needs
    to check positions that have not settled yet; without this filter that
    loop re-quotes every opportunity ever recorded, unbounded, on every run.

    A single position is settled when its own ticker has a `settlements`
    entry. A basket is settled only when EVERY leg has one -- its header
    ticker is the synthetic `BASKET:<hash>`, which by construction never
    appears in `settlements`, so testing the header would report even a
    fully resolved basket as unsettled forever. A basket whose leg rows are
    missing or short of `leg_count` stays unsettled too, so a corrupt row
    surfaces here rather than disappearing from the queue.

    Use `tickers_awaiting_settlement` to get the tickers to actually quote:
    a basket header's ticker is not tradeable and must never be sent to
    Kalshi.
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
            "CASE WHEN position_kind = 'basket' THEN"
            "  (SELECT COUNT(*) FROM opportunity_legs l"
            "    WHERE l.opportunity_id = opportunities.id"
            "      AND l.kalshi_ticker IN"
            "          (SELECT kalshi_ticker FROM settlements))"
            "  < opportunities.leg_count"
            " ELSE"
            "  kalshi_ticker NOT IN (SELECT kalshi_ticker FROM settlements)"
            " END"
        )
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return conn.execute(
        f"SELECT * FROM opportunities{where} ORDER BY id", params
    ).fetchall()


def tickers_awaiting_settlement(
    conn: sqlite3.Connection,
    theory_id: str | None = None,
    run_mode: str | None = None,
    disposition: str | None = None,
) -> list[str]:
    """The real Kalshi tickers this segment still needs a settlement for.

    This is the ticker list score-theories quotes when it goes looking for
    what has resolved, and it exists because a position's ticker and its
    *settleable* tickers are not the same thing. A single position settles
    on its own `kalshi_ticker`. A basket's header carries the synthetic
    `BASKET:<hash>` -- not a market, never quotable -- while the contracts
    that actually resolve live in `opportunity_legs`. Reading
    `row["kalshi_ticker"]` off the header therefore sends a hash to Kalshi
    and never asks about any leg, which is why no basket could ever settle.

    Returns a sorted list of distinct tickers that have no `settlements`
    row yet: every unsettled leg of every basket in the segment, plus the
    ticker of every unsettled single. Legs that have already settled are
    left out -- they have nothing left to check, which is the same reason
    `unsettled_only` exists at all. A basket therefore drops out of this
    list one leg at a time, and disappears entirely once its last leg
    resolves.
    """
    clauses: list[str] = []
    params: list[object] = []
    if theory_id is not None:
        clauses.append("o.theory_id = ?")
        params.append(theory_id)
    if run_mode is not None:
        clauses.append("o.run_mode = ?")
        params.append(run_mode)
    if disposition is not None:
        clauses.append("o.disposition = ?")
        params.append(disposition)
    segment = f" AND {' AND '.join(clauses)}" if clauses else ""

    # UNION over the two shapes rather than a join with a CASE: the leg side
    # is served by idx_opportunity_legs_ticker, and UNION already gives the
    # distinct set a basket sharing a leg with a single would otherwise
    # duplicate.
    sql = (
        "SELECT kalshi_ticker FROM ("
        "  SELECT o.kalshi_ticker AS kalshi_ticker FROM opportunities o"
        "   WHERE o.position_kind = 'single'" + segment +
        "  UNION"
        "  SELECT l.kalshi_ticker AS kalshi_ticker FROM opportunities o"
        "   JOIN opportunity_legs l ON l.opportunity_id = o.id"
        "   WHERE o.position_kind = 'basket'" + segment +
        ") WHERE kalshi_ticker NOT IN"
        "  (SELECT kalshi_ticker FROM settlements)"
        " ORDER BY kalshi_ticker"
    )
    return [
        row["kalshi_ticker"]
        for row in conn.execute(sql, params + params).fetchall()
    ]


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
