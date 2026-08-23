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
    sql = """
        SELECT o.outcome, o.entry_price, o.edge_pts_net, o.user_action,
               s.result
        FROM opportunities o
        JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
        WHERE o.theory_id = ? AND o.theory_version = ? AND o.run_mode = ?
    """
    params: list[object] = [theory_id, theory_version, run_mode]
    if disposition != "all":
        sql += " AND o.disposition = ?"
        params.append(disposition)
    if run_id is not None:
        sql += " AND o.run_id = ?"
        params.append(run_id)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return dict(EMPTY_SCORE)

    n = len(rows)
    wins = 0
    total_cost = 0.0
    total_return = 0.0
    total_fee_pts = 0.0
    taken_cost = 0.0
    taken_return = 0.0
    has_taken = False

    for row in rows:
        won = _won(row["outcome"], row["result"])
        price = row["entry_price"]
        fee = fee_pts(price)
        cost = price + fee / 100.0
        payout = 1.0 if won else 0.0

        wins += 1 if won else 0
        total_cost += cost
        total_return += payout
        total_fee_pts += fee

        if row["user_action"] == "taken":
            has_taken = True
            taken_cost += cost
            taken_return += payout

    win_rate = wins / n
    price_implied_rate = sum(r["entry_price"] for r in rows) / n
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
