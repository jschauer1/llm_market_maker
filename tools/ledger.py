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


def lane_for(run_id: str | None) -> str:
    """Which track record a run's rows belong to.

    Experiments are quarantined by run id, so a variant being tried never
    merges into the record it is meant to be measured against. Everything
    else shares the 'main' lane, which is what makes a position one row
    across all of a theory version's real runs.
    """
    resolved = run_id or LIVE_RUN_ID
    if resolved.startswith(EXPERIMENT_RUN_PREFIX):
        return resolved
    return "main"


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


def _record_attempt(
    conn: sqlite3.Connection,
    opportunity_id: int,
    decision_date: str,
    run_id: str,
    recorded_at: str,
    entry_price: float,
    edge_pts_net: float,
    *,
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
) -> None:
    """Record one proposal of a position, and refresh its attempt count.

    Called inside the caller's `write` block. Re-recording the same decision
    in the same run updates that attempt rather than adding one, which is
    what makes two recordings an hour apart count once.

    Full parity (attempt-fidelity spec section 4): every non-identity
    argument `record_opportunity`/`record_basket` accepts has a column here,
    enforced by
    tests/test_conventions.py::test_every_record_opportunity_param_has_an_attempt_column.
    Everything past `edge_pts_net` is keyword-only on purpose -- with this
    many same-typed columns (three REALs in a row, three more further down)
    a positional slip is silent and corrupting, and keyword-only args make
    that class of bug a TypeError instead of a wrong number in the ledger.

    The ON CONFLICT rule splits the columns into two groups:

    - Last-writer-wins (`excluded.<col>`) for everything that describes
      market/call conditions at the moment of recording -- entry_price,
      spread_at_call, volume_at_call, model_prob, edge_pts_gross, fee_pts,
      edge_pts_net, edge_basis, suggested_size, evidence_source,
      evidence_market_id, extra_json, scan_id, recorded_at.
      A second recording of the same (opportunity, decision_date, run_id)
      is a correction to what was measured, not a second opinion to
      reconcile -- the caller re-ran and has a newer number, so the newer
      number should win outright.
    - COALESCE for the judgment fields -- confidence, judged_blind,
      rationale -- so a later judging pass can add a label without erasing
      one a caller already wrote. These are the fields a human or an LLM
      supplies rather than the harness measuring, and a re-recording that
      omits them (e.g. a mechanical re-score with no judge in the loop)
      must not blank out judgment that already happened.
    - Untouched: `disposition`. It is on the attempt specifically to hold a
      per-row value (attempt-fidelity spec section 7 -- 371 legacy rows
      carry a real one), and this INSERT can only ever supply the literal
      `'screened'`, since `record_opportunity` has no disposition argument
      and stage-2 research writes through `ledger.interpret` on the
      position. Refreshing it from `excluded` would therefore mean a second
      session re-screening a dated run id silently downgrading every
      endorsement and rejection under it back to `screened` -- writing a
      value nobody supplied over one somebody did.
    """
    conn.execute(
        """
        INSERT INTO opportunity_attempts (
            opportunity_id, decision_date, run_id, recorded_at, scan_id,
            entry_price, spread_at_call, volume_at_call, model_prob,
            edge_pts_gross, fee_pts, edge_pts_net, edge_basis, disposition,
            confidence, judged_blind, rationale, suggested_size,
            evidence_source, evidence_market_id, extra_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'screened',
                  ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (opportunity_id, decision_date, run_id) DO UPDATE SET
            recorded_at        = excluded.recorded_at,
            scan_id            = excluded.scan_id,
            entry_price        = excluded.entry_price,
            spread_at_call     = excluded.spread_at_call,
            volume_at_call     = excluded.volume_at_call,
            model_prob         = excluded.model_prob,
            edge_pts_gross     = excluded.edge_pts_gross,
            fee_pts            = excluded.fee_pts,
            edge_pts_net       = excluded.edge_pts_net,
            edge_basis         = excluded.edge_basis,
            suggested_size     = excluded.suggested_size,
            evidence_source    = excluded.evidence_source,
            evidence_market_id = excluded.evidence_market_id,
            extra_json         = excluded.extra_json,
            confidence   = COALESCE(excluded.confidence,
                                    opportunity_attempts.confidence),
            judged_blind = COALESCE(excluded.judged_blind,
                                    opportunity_attempts.judged_blind),
            rationale    = COALESCE(excluded.rationale,
                                    opportunity_attempts.rationale)
        """,
        (
            opportunity_id, decision_date, run_id, recorded_at, scan_id,
            entry_price, spread_at_call, volume_at_call, model_prob,
            edge_pts_gross, fee_pts, edge_pts_net, edge_basis,
            confidence,
            1 if judged_blind else (0 if judged_blind is not None else None),
            rationale, suggested_size, evidence_source, evidence_market_id,
            extra_json,
        ),
    )
    # times_seen counts distinct attempts, never recordings -- the whole
    # point of the attempt table is that repetition is counted once per
    # decision.
    conn.execute(
        """
        UPDATE opportunities SET times_seen =
            (SELECT COUNT(*) FROM opportunity_attempts
             WHERE opportunity_id = ?)
        WHERE id = ?
        """,
        (opportunity_id, opportunity_id),
    )


def attempts(
    conn: sqlite3.Connection, opportunity_id: int
) -> list[sqlite3.Row]:
    """Every recorded proposal of a position, oldest first."""
    return conn.execute(
        """
        SELECT * FROM opportunity_attempts WHERE opportunity_id = ?
        ORDER BY decision_date, recorded_at
        """,
        (opportunity_id,),
    ).fetchall()


def attempt_dates(conn: sqlite3.Connection, opportunity_id: int) -> list[str]:
    """The distinct days a position was proposed, oldest first.

    Derived rather than stored: `len(attempt_dates(...))` is the persistence
    signal, and keeping it beside the attempt table would be two places
    holding overlapping truth.
    """
    return [
        row["decision_date"]
        for row in conn.execute(
            """
            SELECT DISTINCT decision_date FROM opportunity_attempts
            WHERE opportunity_id = ? ORDER BY decision_date
            """,
            (opportunity_id,),
        ).fetchall()
    ]


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
    decision_date: str | None = None,
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
    if run_mode == "backtest" and not decision_date:
        raise ValueError(
            "decision_date is required for backtest runs: without it every "
            "replayed day falls back to the wall-clock date, so a replay "
            "that covers many days stamps every attempt with the same "
            "(decision_date, run_id) and the primary key on "
            "opportunity_attempts silently collapses them into one row. "
            "Pass the as-of day the theory is deciding about."
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
    lane = lane_for(resolved_run_id)
    # The as-of day of the decision, not the wall-clock recording time. Two
    # runs an hour apart replaying the same day are one decision.
    day = decision_date or stamp[:10]

    with write(conn):
        # INSERT ... DO NOTHING RETURNING is an atomic creation test: no
        # SELECT-then-INSERT window for a concurrent writer to slip through,
        # and an unambiguous answer to "was this the first sighting" that
        # does not depend on reading a counter back.
        created = conn.execute(
            """
            INSERT INTO opportunities (
                theory_id, theory_version, run_mode, run_id, lane, scan_id,
                kalshi_ticker, outcome, entry_price, spread_at_call,
                volume_at_call, model_prob, edge_pts_gross, fee_pts,
                screen_edge_pts_net, edge_pts_net, edge_basis, disposition,
                confidence, judged_blind,
                rationale, suggested_size, evidence_source,
                evidence_market_id,
                user_action, first_seen_at, last_seen_at, times_seen,
                extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      'screened', ?, ?, ?, ?, ?, ?, 'untouched', ?, ?, 1, ?)
            ON CONFLICT (theory_id, theory_version, run_mode, lane,
                         kalshi_ticker, outcome) DO NOTHING
            RETURNING id
            """,
            (
                theory_id, theory_version, run_mode, resolved_run_id, lane,
                scan_id, kalshi_ticker, outcome, entry_price, spread_at_call,
                volume_at_call, model_prob, edge_pts_gross, fee_pts,
                edge_pts_net, edge_pts_net, edge_basis, confidence,
                1 if judged_blind else (0 if judged_blind is not None else None),
                rationale, suggested_size, evidence_source,
                evidence_market_id, stamp, stamp, extra_json,
            ),
        ).fetchone()

        if created is not None:
            opportunity_id = created["id"]
        else:
            # A re-sighting. entry_price, first_seen_at, run_id and
            # screen_edge_pts_net are deliberately absent from this UPDATE:
            # they record the first sighting and must not drift.
            #
            # Once research has spoken, it supersedes the mechanical screen:
            # screen_edge_pts_net already preserves the original screen
            # claim, and there is deliberately no column for "latest screen
            # value" — the interpretation is the current best estimate,
            # which is precisely what edge_pts_net means. So a re-sighting
            # only refreshes edge_pts_net from the new screen while the row
            # is still uninterpreted; once interpreted_at is set, the
            # researched value stands.
            #
            # judged_blind is COALESCEd alongside confidence, never left
            # behind: a screen run records neither, a later judging run
            # records both, and refreshing the label without the flag leaves
            # the rollup claiming `strong` while claiming nothing is known
            # about how it was judged -- the same wrong state the migration
            # fixes for history in attempt-fidelity spec section 8c.
            conn.execute(
                """
                UPDATE opportunities SET
                    last_seen_at = ?,
                    edge_pts_net = CASE
                        WHEN interpreted_at IS NULL THEN ?
                        ELSE edge_pts_net
                    END,
                    model_prob = COALESCE(?, model_prob),
                    edge_pts_gross = COALESCE(?, edge_pts_gross),
                    fee_pts = COALESCE(?, fee_pts),
                    spread_at_call = COALESCE(?, spread_at_call),
                    volume_at_call = COALESCE(?, volume_at_call),
                    confidence = COALESCE(?, confidence),
                    judged_blind = COALESCE(?, judged_blind),
                    rationale = COALESCE(?, rationale),
                    suggested_size = COALESCE(?, suggested_size)
                WHERE theory_id = ? AND theory_version = ? AND run_mode = ?
                  AND lane = ? AND kalshi_ticker = ? AND outcome = ?
                """,
                (
                    stamp, edge_pts_net, model_prob, edge_pts_gross, fee_pts,
                    spread_at_call, volume_at_call, confidence,
                    1 if judged_blind
                    else (0 if judged_blind is not None else None),
                    rationale,
                    suggested_size,
                    theory_id, theory_version, run_mode, lane,
                    kalshi_ticker, outcome,
                ),
            )
            opportunity_id = conn.execute(
                """
                SELECT id FROM opportunities
                WHERE theory_id = ? AND theory_version = ? AND run_mode = ?
                  AND lane = ? AND kalshi_ticker = ? AND outcome = ?
                """,
                (theory_id, theory_version, run_mode, lane, kalshi_ticker,
                 outcome),
            ).fetchone()["id"]

        _record_attempt(
            conn, opportunity_id, day, resolved_run_id, stamp, entry_price,
            edge_pts_net,
            scan_id=scan_id,
            spread_at_call=spread_at_call,
            volume_at_call=volume_at_call,
            model_prob=model_prob,
            edge_pts_gross=edge_pts_gross,
            fee_pts=fee_pts,
            edge_basis=edge_basis,
            confidence=confidence,
            judged_blind=judged_blind,
            rationale=rationale,
            suggested_size=suggested_size,
            evidence_source=evidence_source,
            evidence_market_id=evidence_market_id,
            extra_json=extra_json,
        )

    return opportunity_id, created is not None


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
    decision_date: str | None = None,
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
    rows: the row is identified by (theory_id, theory_version, run_mode,
    lane, kalshi_ticker, outcome) -- not by run_id -- so two different runs
    that both propose the same basket land on one header row, not two.
    `entry_price` is frozen at first sighting on *both* the header and every
    leg, along with each leg's `kalshi_ticker`, `outcome`, and `leg_index`
    -- they record the entry actually available when the basket was first
    seen and must not drift. `min_payout` is frozen the same way, for the
    same reason. Only `last_seen_at`, `edge_pts_net` (while uninterpreted),
    and the legs' `spread_at_call` / `volume_at_call` refresh on a
    re-sighting. `times_seen` is no longer bumped in this UPDATE -- it is
    recomputed by `_record_attempt` from the distinct (decision_date,
    run_id) attempts recorded in `opportunity_attempts`, so that two runs
    re-proposing the same basket on the same day count as one attempt, not
    two.
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
    if run_mode == "backtest" and not decision_date:
        raise ValueError(
            "decision_date is required for backtest runs: without it every "
            "replayed day falls back to the wall-clock date, so a replay "
            "that covers many days stamps every attempt with the same "
            "(decision_date, run_id) and the primary key on "
            "opportunity_attempts silently collapses them into one row. "
            "Pass the as-of day the theory is deciding about."
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
    lane = lane_for(resolved_run_id)
    # The as-of day of the decision, not the wall-clock recording time. Two
    # runs an hour apart replaying the same day are one decision.
    day = decision_date or stamp[:10]

    with write(conn):
        # Same atomic creation test record_opportunity uses: INSERT ... DO
        # NOTHING RETURNING id, so "was this the first sighting" is answered
        # by the presence of a row rather than a counter read back after the
        # fact.
        created = conn.execute(
            """
            INSERT INTO opportunities (
                theory_id, theory_version, run_mode, run_id, lane, scan_id,
                kalshi_ticker, outcome, entry_price, position_kind,
                leg_count, max_payout, min_payout, model_prob, edge_pts_gross,
                fee_pts, screen_edge_pts_net, edge_pts_net, edge_basis,
                disposition, confidence, judged_blind, rationale,
                suggested_size, evidence_source, evidence_market_id,
                user_action, first_seen_at, last_seen_at, times_seen,
                extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'basket', ?, 'basket', ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, 'screened', ?, ?, ?, ?, ?, ?, 'untouched',
                      ?, ?, 1, ?)
            ON CONFLICT (theory_id, theory_version, run_mode, lane,
                         kalshi_ticker, outcome) DO NOTHING
            RETURNING id
            """,
            (
                theory_id, theory_version, run_mode, resolved_run_id, lane,
                scan_id, header_ticker, cost, len(norm), max_payout,
                min_payout, model_prob, edge_pts_gross, fee_pts, edge_pts_net,
                edge_pts_net, edge_basis, confidence,
                1 if judged_blind else (0 if judged_blind is not None else None),
                rationale, suggested_size, evidence_source,
                evidence_market_id, stamp, stamp, extra_json,
            ),
        ).fetchone()

        if created is not None:
            opportunity_id = created["id"]
        else:
            # A re-sighting. entry_price (the header's frozen cost),
            # first_seen_at, run_id and screen_edge_pts_net are deliberately
            # absent from this UPDATE, for the same reason record_opportunity
            # leaves them alone: they record the first sighting and must not
            # drift. times_seen is not bumped here either -- it is
            # recomputed below by _record_attempt from the distinct attempts
            # on file, so two runs re-proposing this basket on the same day
            # count once, not twice.
            conn.execute(
                """
                UPDATE opportunities SET
                    last_seen_at = ?,
                    edge_pts_net = CASE
                        WHEN interpreted_at IS NULL THEN ?
                        ELSE edge_pts_net
                    END,
                    model_prob = COALESCE(?, model_prob),
                    edge_pts_gross = COALESCE(?, edge_pts_gross),
                    fee_pts = COALESCE(?, fee_pts),
                    confidence = COALESCE(?, confidence),
                    judged_blind = COALESCE(?, judged_blind),
                    rationale = COALESCE(?, rationale),
                    suggested_size = COALESCE(?, suggested_size)
                WHERE theory_id = ? AND theory_version = ? AND run_mode = ?
                  AND lane = ? AND kalshi_ticker = ? AND outcome = 'basket'
                """,
                (
                    stamp, edge_pts_net, model_prob, edge_pts_gross, fee_pts,
                    confidence,
                    1 if judged_blind
                    else (0 if judged_blind is not None else None),
                    rationale, suggested_size,
                    theory_id, theory_version, run_mode, lane, header_ticker,
                ),
            )
            opportunity_id = conn.execute(
                """
                SELECT id FROM opportunities
                WHERE theory_id = ? AND theory_version = ? AND run_mode = ?
                  AND lane = ? AND kalshi_ticker = ? AND outcome = 'basket'
                """,
                (theory_id, theory_version, run_mode, lane, header_ticker),
            ).fetchone()["id"]

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
                (opportunity_id, i, leg["kalshi_ticker"], leg["outcome"],
                 leg["entry_price"], leg["spread_at_call"],
                 leg["volume_at_call"])
                for i, leg in enumerate(norm)
            ],
        )

        # The basket's attempt entry_price is its total cost -- the header
        # row's entry_price -- not any individual leg's price. There is no
        # basket-level spread_at_call/volume_at_call to pass through: those
        # describe one market's order book and live per-leg on
        # opportunity_legs, which record_basket has no top-level parameter
        # for either -- so both are left at their None default here, same
        # as on the header row.
        _record_attempt(
            conn, opportunity_id, day, resolved_run_id, stamp, cost,
            edge_pts_net,
            scan_id=scan_id,
            model_prob=model_prob,
            edge_pts_gross=edge_pts_gross,
            fee_pts=fee_pts,
            edge_basis=edge_basis,
            confidence=confidence,
            judged_blind=judged_blind,
            rationale=rationale,
            suggested_size=suggested_size,
            evidence_source=evidence_source,
            evidence_market_id=evidence_market_id,
            extra_json=extra_json,
        )

    return opportunity_id, created is not None


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


def resolve_ticker(
    conn: sqlite3.Connection, ticker: str, theory_id: str | None = None
) -> sqlite3.Row:
    """The latest live-lane sighting of `ticker` `mark-taken --ticker` acts on.

    Only the money record can be marked taken, so the lookup is pinned to
    `run_mode = 'live' AND lane = 'main'` before anything else -- a backtest
    replay or an `exp/` variant sighting of the same ticker has no real
    money behind it and must never be mistaken for the live position.
    Nothing here filters on settlement; a settled ticker is still returned.

    Among what survives that filter, most recent sighting (by
    `last_seen_at`) wins. More than one theory open on the ticker -- or one
    theory open on more than one outcome of the ticker -- is a refusal, not
    a guess -- marking the wrong theory's or the wrong side's row corrupts
    the only realized-ROI signal this system gets -- so the error names
    each candidate and the flag that disambiguates. A theory that fanned
    across versions on the same (theory, outcome) pair is not ambiguous:
    that is one theory whose procedure was bumped mid-track, and the
    newest sighting is the position still open.
    """
    rows = conn.execute(
        """
        SELECT * FROM opportunities
         WHERE kalshi_ticker = ? AND run_mode = 'live' AND lane = 'main'
           AND (? IS NULL OR theory_id = ?)
         ORDER BY last_seen_at DESC
        """,
        (ticker, theory_id, theory_id),
    ).fetchall()
    if not rows:
        raise KeyError(ticker)
    combos = {(r["theory_id"], r["outcome"]) for r in rows}
    if len(combos) > 1:
        names = ", ".join(
            f"{r['theory_id']}:{r['outcome']}:{r['id']}" for r in rows
        )
        raise ValueError(
            f"{ticker} has open positions under more than one "
            f"theory/outcome ({names}); pass --theory to say which one you "
            "acted on"
        )
    return rows[0]


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
        # Stamp the attempt this verdict belongs to, not just the position.
        #
        # `compute_score` groups by the POSITION's disposition, so a
        # position re-judged by a later run moves between the endorsed and
        # rejected pools wholesale -- and those two pools are exactly what
        # `interpretation_value` compares. Three live positions had already
        # gone endorsed -> rejected across runs by 2026-08-29 (9184, 9186,
        # 9203), all settling within days.
        #
        # This does NOT decide which disposition such a position should be
        # scored under; that is a semantics question with two defensible
        # answers. It makes sure the per-attempt history is complete enough
        # that either answer stays computable, instead of the earlier run's
        # verdict being lost the moment a later one disagrees.
        conn.execute(
            """
            UPDATE opportunity_attempts
            SET disposition = ?
            WHERE opportunity_id = ?
              AND rowid = (SELECT rowid FROM opportunity_attempts
                            WHERE opportunity_id = ?
                            ORDER BY decision_date DESC, recorded_at DESC
                            LIMIT 1)
            """,
            (disposition, opportunity_id, opportunity_id),
        )


def mark_user_action(
    conn: sqlite3.Connection,
    opportunity_id: int,
    action: str,
    size: float | None = None,
    reason: str | None = None,
    *,
    theory_id: str | None = None,
    price: float | None = None,
    filled_on: str | None = None,
    now: str | None = None,
) -> None:
    """Record what the user actually did with a bet.

    Taking names the theory it is taken for. Two theories proposing one
    market are two forecasts and one bet: both stay graded on calibration,
    but only the named one books the money, so `roi_taken` counts a single
    purchase once.

    A take appends a fill rather than overwriting, so scaling into a
    position keeps both entries. `user_action` and `user_size` on the
    position are maintained rollups of the fills.

    The reason matters: divergence between what the system endorsed and what
    the user bet is usually an unencoded heuristic, and those get mined into
    new theory candidates.
    """
    if action not in VALID_USER_ACTIONS:
        raise ValueError(
            f"invalid action {action!r}; expected one of {VALID_USER_ACTIONS}"
        )
    row = get_opportunity(conn, opportunity_id)
    if row is None:
        raise KeyError(opportunity_id)

    stamp = now or utcnow()

    if action == "taken":
        if not theory_id:
            raise ValueError(
                "taking a bet must name the theory it is taken for: pass "
                "--theory. Two theories can propose one market, and only "
                "the named one books the money."
            )
        if theory_id != row["theory_id"]:
            raise ValueError(
                f"opportunity {opportunity_id} belongs to "
                f"{row['theory_id']!r}, not {theory_id!r}"
            )
        holder = conn.execute(
            """
            SELECT id, theory_id FROM opportunities
            WHERE kalshi_ticker = ? AND outcome = ? AND user_action = 'taken'
              AND id != ?
            """,
            (row["kalshi_ticker"], row["outcome"], opportunity_id),
        ).fetchone()
        if holder is not None:
            raise ValueError(
                f"{row['kalshi_ticker']} {row['outcome']} is already taken "
                f"under theory {holder['theory_id']!r} (opportunity "
                f"{holder['id']}). One real position, one theory credited -- "
                f"unmark that one first if the attribution is wrong."
            )
        if size is None:
            raise ValueError("taking a bet requires --size")
        # price is the same unit as entry_price -- decimal dollars in
        # [0, 1] -- and Task 6 computes roi_taken directly off it, so the
        # cents-vs-dollars mistake _validate_entry_price already guards
        # against (entry_price=40 silently producing a -3900pt edge) is
        # just as live here. None is allowed: a take with no --price falls
        # back to the proposed ask at scoring time.
        if price is not None:
            _validate_entry_price(price)

    with write(conn):
        if action == "taken":
            conn.execute(
                """
                INSERT INTO opportunity_fills (
                    opportunity_id, filled_on, size, price, reason,
                    recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (opportunity_id, filled_on or stamp[:10], size, price,
                 reason, stamp),
            )
        else:
            # Skipping or unmarking retires the money record: a position the
            # user is no longer in has no fills.
            conn.execute(
                "DELETE FROM opportunity_fills WHERE opportunity_id = ?",
                (opportunity_id,),
            )
        if action == "untouched":
            # No money and no reason either: user_reason must go back to
            # NULL, not just user_size. compare-theories mines divergences
            # off any row with a non-NULL user_reason and does not check
            # user_action at all, so a stale "too thin" surviving from a
            # prior skip/take would be mined as a live signal for a
            # position the user is no longer in.
            reason_sql, reason_params = "NULL", ()
        else:
            # taken/skipped: COALESCE so re-taking (or re-skipping) without
            # --reason does not wipe out the reason already on file.
            reason_sql, reason_params = "COALESCE(?, user_reason)", (reason,)
        conn.execute(
            f"""
            UPDATE opportunities SET
                user_action = ?,
                user_size = (SELECT SUM(size) FROM opportunity_fills
                             WHERE opportunity_id = ?),
                user_reason = {reason_sql}
            WHERE id = ?
            """,
            (action, opportunity_id, *reason_params, opportunity_id),
        )


def fills(conn: sqlite3.Connection, opportunity_id: int) -> list[sqlite3.Row]:
    """Every recorded purchase of a position, oldest first."""
    return conn.execute(
        """
        SELECT * FROM opportunity_fills WHERE opportunity_id = ?
        ORDER BY filled_on, id
        """,
        (opportunity_id,),
    ).fetchall()
