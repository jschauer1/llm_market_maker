"""Settlement recording and calibration scoring (spec sections 5 and 7).

The headline metric is calibration edge: realized win rate minus the
price-implied rate, in percentage points. It answers the only question that
matters about a theory — did markets it picked resolve in its favour more
often than their prices implied.

Calibration edge comes in two flavours and the difference matters.
`calibration_edge` is GROSS: it measures how wrong the market's prices were,
which is a real quantity worth reporting on its own. `calibration_edge_net`
subtracts the mean per-contract fee, so it measures what a trader actually
kept. Only the net figure may be compared against `mean_claimed_edge`, which
is net of fees by definition — comparing the gross figure against a net claim
inflates realization and lets a theory that breaks exactly even after fees
report a positive edge.

Scores are computed per (theory, version, run_mode, disposition), and
optionally per run_id. The disposition split is what makes the value of
stage-2 interpretation measurable: endorsed versus rejected, with rejected
candidates serving as a free control group. The run_id filter keeps a
re-run backtest from pooling into one inflated sample.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow, write
from tools.rank import realization as _realization
from tools.sizing import fee_pts

VALID_TIERS = ("A", "B", "C")

EMPTY_SCORE = {
    "n": 0,
    "win_rate": None,
    "price_implied_rate": None,
    "calibration_edge": None,
    "calibration_edge_net": None,
    "mean_claimed_edge": None,
    "mean_fee_pts": None,
    "realization": None,
    "roi_all": None,
    "roi_taken": None,
}


def _won(outcome: object, result: object) -> bool:
    """Did the settlement resolve the side this opportunity took?

    Case-insensitive on both sides. `ledger.record_opportunity` already
    lowercases `outcome` on entry; settlements arrive from a connector and
    are not normalized, so the comparison stays defensive.
    """
    return str(result).lower() == str(outcome).lower()


def record_settlement(
    conn: sqlite3.Connection,
    kalshi_ticker: str,
    result: str,
    resolved_at: str | None = None,
    settle_price: float | None = None,
) -> None:
    """Record how a Kalshi market resolved. Latest write wins."""
    with write(conn):
        conn.execute(
            """
            INSERT INTO settlements (kalshi_ticker, resolved_at, result,
                                     settle_price)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(kalshi_ticker) DO UPDATE SET
                resolved_at = excluded.resolved_at,
                result = excluded.result,
                settle_price = excluded.settle_price
            """,
            (kalshi_ticker, resolved_at, result, settle_price),
        )


def compute_score(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
    disposition: str = "all",
    *,
    run_id: str | None = None,
) -> dict:
    """Score every settled opportunity matching the given segment.

    Pass `run_id` to score a single run. Without it every run of the same
    theory version pools together, so re-running a backtest over the same
    markets multiplies `n` without adding a single real bet.
    """
    obs = _single_leg_observations(
        conn, theory_id, theory_version, run_mode, disposition, run_id
    ) + _basket_observations(
        conn, theory_id, theory_version, run_mode, disposition, run_id
    )
    return _aggregate(obs)


def _segment_filter(
    theory_id: str, theory_version: int, run_mode: str,
    disposition: str, run_id: str | None,
) -> tuple[str, list[object]]:
    """The WHERE clause every observation query shares."""
    sql = " WHERE o.theory_id = ? AND o.theory_version = ? AND o.run_mode = ?"
    params: list[object] = [theory_id, theory_version, run_mode]
    if disposition != "all":
        sql += " AND o.disposition = ?"
        params.append(disposition)
    if run_id is not None:
        sql += " AND o.run_id = ?"
        params.append(run_id)
    return sql, params


def _single_leg_observations(
    conn: sqlite3.Connection, theory_id: str, theory_version: int,
    run_mode: str, disposition: str, run_id: str | None,
) -> list[dict]:
    """One observation per settled single-leg position."""
    where, params = _segment_filter(
        theory_id, theory_version, run_mode, disposition, run_id
    )
    sql = (
        "SELECT o.outcome, o.entry_price, o.edge_pts_net, o.user_action,"
        " s.result FROM opportunities o"
        " JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker"
        + where
        + " AND o.position_kind = 'single'"
    )
    out = []
    for row in conn.execute(sql, params).fetchall():
        won = _won(row["outcome"], row["result"])
        price = row["entry_price"]
        fee = fee_pts(price)
        out.append({
            "implied_rate": price,
            "won": won,
            "cost": price + fee / 100.0,
            "payout": 1.0 if won else 0.0,
            "fee_pts": fee,
            "edge_pts_net": row["edge_pts_net"],
            "user_action": row["user_action"],
        })
    return out


def _basket_observations(
    conn: sqlite3.Connection, theory_id: str, theory_version: int,
    run_mode: str, disposition: str, run_id: str | None,
) -> list[dict]:
    """One observation per fully-settled basket.

    A basket is one position with a joint payoff, so it contributes exactly
    one observation however many legs it has. Recording it as N rows would
    make a riskless arbitrage -- one winning leg, one losing leg, a certain
    $1 payout -- read as a 50% win rate.

    A basket with any unsettled leg is excluded, exactly as an unsettled
    single position is: its payoff is not yet known.
    """
    where, params = _segment_filter(
        theory_id, theory_version, run_mode, disposition, run_id
    )
    headers = conn.execute(
        "SELECT o.id, o.entry_price, o.edge_pts_net, o.user_action,"
        " o.leg_count, o.max_payout FROM opportunities o"
        + where
        + " AND o.position_kind = 'basket'",
        params,
    ).fetchall()

    out = []
    for header in headers:
        legs = conn.execute(
            "SELECT l.kalshi_ticker, l.outcome, l.entry_price, s.result"
            "  FROM opportunity_legs l"
            "  LEFT JOIN settlements s ON s.kalshi_ticker = l.kalshi_ticker"
            " WHERE l.opportunity_id = ? ORDER BY l.leg_index",
            (header["id"],),
        ).fetchall()

        # A leg row lost between write and read would make the basket look
        # cheaper than it was. Fail loudly rather than score a partial one.
        if len(legs) != header["leg_count"]:
            raise ValueError(
                f"opportunity {header['id']} declares leg_count "
                f"{header['leg_count']} but has {len(legs)} leg rows; "
                "refusing to score a partial basket"
            )

        if any(leg["result"] is None for leg in legs):
            continue

        payout = sum(
            1.0 for leg in legs if _won(leg["outcome"], leg["result"])
        )
        fee = sum(fee_pts(leg["entry_price"]) for leg in legs)
        cost = header["entry_price"] + fee / 100.0
        max_payout = header["max_payout"] or 1.0

        out.append({
            # Normalized so a basket's implied rate is comparable with a
            # single position's price. For max_payout = 1.0 this is the
            # cost itself, which is what a single leg contributes.
            "implied_rate": header["entry_price"] / max_payout,
            "won": payout > cost,
            "cost": cost,
            "payout": payout,
            "fee_pts": fee,
            "edge_pts_net": header["edge_pts_net"],
            "user_action": header["user_action"],
        })
    return out


def _aggregate(rows: list[dict]) -> dict:
    """Turn observations into the score dict. Shared by every position kind."""
    if not rows:
        return dict(EMPTY_SCORE)

    n = len(rows)
    # Deliberately a hand-rolled loop, not sum(): CPython >=3.12 gives
    # sum() Neumaier compensated summation while += stays naive (gh-100425),
    # so the two accumulation styles round differently in the last bit on
    # different interpreter versions. This function's contract is exact
    # arithmetic equivalence with the pre-refactor implementation -- which
    # used a loop -- so it keeps the loop rather than "modernizing" it.
    wins = 0
    total_cost = 0.0
    total_return = 0.0
    total_fee_pts = 0.0
    taken_cost = 0.0
    taken_return = 0.0
    has_taken = False
    for r in rows:
        if r["won"]:
            wins += 1
        total_cost += r["cost"]
        total_return += r["payout"]
        total_fee_pts += r["fee_pts"]
        if r["user_action"] == "taken":
            has_taken = True
            taken_cost += r["cost"]
            taken_return += r["payout"]

    win_rate = wins / n
    price_implied_rate = sum(r["implied_rate"] for r in rows) / n
    calibration_edge = (win_rate - price_implied_rate) * 100.0
    mean_fee_pts = total_fee_pts / n
    # Net of fees, so it is comparable with mean_claimed_edge, which is
    # net by definition. Realization must use this one.
    calibration_edge_net = calibration_edge - mean_fee_pts
    mean_claimed_edge = sum(r["edge_pts_net"] for r in rows) / n

    roi_all = (total_return - total_cost) / total_cost if total_cost else None
    roi_taken = (
        (taken_return - taken_cost) / taken_cost
        if has_taken and taken_cost
        else None
    )

    return {
        "n": n,
        "win_rate": win_rate,
        "price_implied_rate": price_implied_rate,
        "calibration_edge": calibration_edge,
        "calibration_edge_net": calibration_edge_net,
        "mean_claimed_edge": mean_claimed_edge,
        "mean_fee_pts": mean_fee_pts,
        "realization": _realization(calibration_edge_net, mean_claimed_edge),
        "roi_all": roi_all,
        "roi_taken": roi_taken,
    }


def save_score(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str,
    disposition: str,
    result: dict,
    now: str | None = None,
) -> int:
    """Persist a computed score. Returns the new row id."""
    with write(conn):
        cursor = conn.execute(
            """
            INSERT INTO scores (
                theory_id, theory_version, run_mode, disposition, n, win_rate,
                price_implied_rate, calibration_edge, calibration_edge_net,
                mean_claimed_edge, realization, roi_all, roi_taken, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                theory_id,
                theory_version,
                run_mode,
                disposition,
                result["n"],
                result["win_rate"],
                result["price_implied_rate"],
                result["calibration_edge"],
                result["calibration_edge_net"],
                result["mean_claimed_edge"],
                result["realization"],
                result["roi_all"],
                result["roi_taken"],
                now or utcnow(),
            ),
        )
    return cursor.lastrowid


def record_backtest_run(
    conn: sqlite3.Connection,
    run_id: str,
    theory_id: str,
    theory_version: int,
    *,
    as_of_start: str | None = None,
    as_of_end: str | None = None,
    tier: str | None = None,
    uses_llm_judgment: bool | None = None,
    model_cutoff: str | None = None,
    notes: str | None = None,
    now: str | None = None,
) -> None:
    """Record a backtest run's provenance (spec section 9).

    `backtest_runs` is the only record of *how* a backtest was produced —
    its tier, whether LLM judgment was in the decision path, and the model
    cutoff that tier depended on. Without this row a `run_id` in
    `opportunities` is just an opaque string with no way to recover whether
    its results are trustworthy evidence or a tier-C sanity check.
    """
    if tier is not None and tier not in VALID_TIERS:
        raise ValueError(
            f"invalid tier {tier!r}; expected one of {VALID_TIERS}"
        )
    with write(conn):
        conn.execute(
            """
            INSERT INTO backtest_runs (
                run_id, theory_id, theory_version, as_of_start, as_of_end,
                tier, uses_llm_judgment, model_cutoff, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                theory_id,
                theory_version,
                as_of_start,
                as_of_end,
                tier,
                None if uses_llm_judgment is None
                else (1 if uses_llm_judgment else 0),
                model_cutoff,
                notes,
                now or utcnow(),
            ),
        )


def interpretation_value(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
) -> dict:
    """Did stage-2 judgment earn its keep (spec section 7)?

    `delta` is endorsed calibration edge NET minus rejected calibration edge
    NET, in points. Net, not gross, because the rest of the system compares
    net-to-net (see the module docstring); comparing the gross figures would
    let a difference in the two groups' mean fees masquerade as a difference
    in interpretation quality. Positive means interpretation is adding edge;
    near zero means it is adding nothing; negative means it is destroying
    value. It is None until both groups have settled results to compare.
    """
    endorsed = compute_score(
        conn, theory_id, theory_version, run_mode, "endorsed"
    )
    rejected = compute_score(
        conn, theory_id, theory_version, run_mode, "rejected"
    )
    delta = None
    if endorsed["n"] and rejected["n"]:
        delta = (
            endorsed["calibration_edge_net"] - rejected["calibration_edge_net"]
        )
    return {"endorsed": endorsed, "rejected": rejected, "delta": delta}


def bucket_rates(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
    *,
    run_id: str | None = None,
) -> dict[str, dict]:
    """Realized win rate per confidence bucket (spec section 7).

    This is what a theory's confidence labels actually MEAN, measured rather
    than asserted. Only settled opportunities carrying a bucket count. As
    with `compute_score`, pass `run_id` to measure a single run rather than
    every run of this theory version pooled together.
    """
    sql = """
        SELECT o.confidence, o.outcome, o.entry_price, s.result
        FROM opportunities o
        JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
        WHERE o.theory_id = ? AND o.theory_version = ? AND o.run_mode = ?
          AND o.confidence IS NOT NULL AND o.confidence != ''
    """
    params: list[object] = [theory_id, theory_version, run_mode]
    if run_id is not None:
        sql += " AND o.run_id = ?"
        params.append(run_id)

    rows = conn.execute(sql, params).fetchall()

    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row["confidence"], []).append(row)

    return {
        bucket: {
            "n": len(members),
            "win_rate": sum(
                1 for m in members if _won(m["outcome"], m["result"])
            )
            / len(members),
            "mean_entry_price": sum(m["entry_price"] for m in members)
            / len(members),
        }
        for bucket, members in grouped.items()
    }


def save_bucket_rates(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    rates: dict,
    now: str | None = None,
) -> int:
    """Persist computed bucket rates. Returns rows written."""
    stamp = now or utcnow()
    rows = [
        (theory_id, theory_version, bucket, data["n"], data["win_rate"],
         data["mean_entry_price"], stamp)
        for bucket, data in rates.items()
    ]
    if not rows:
        return 0
    with write(conn):
        conn.executemany(
            """
            INSERT INTO bucket_rates (theory_id, theory_version, confidence,
                                      n, win_rate, mean_entry_price,
                                      computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)
