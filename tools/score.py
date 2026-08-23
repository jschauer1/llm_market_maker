"""Settlement recording and calibration scoring (spec sections 5 and 7).

The headline metric is calibration edge: realized win rate minus the
price-implied rate, in percentage points. It answers the only question that
matters about a theory — did markets it picked resolve in its favour more
often than their prices implied.

Scores are computed per (theory, version, run_mode, disposition). The
disposition split is what makes the value of stage-2 interpretation
measurable: endorsed versus rejected, with rejected candidates serving as a
free control group.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow
from tools.rank import realization as _realization
from tools.sizing import fee_pts

EMPTY_SCORE = {
    "n": 0,
    "win_rate": None,
    "price_implied_rate": None,
    "calibration_edge": None,
    "mean_claimed_edge": None,
    "realization": None,
    "roi_all": None,
    "roi_taken": None,
}


def record_settlement(
    conn: sqlite3.Connection,
    kalshi_ticker: str,
    result: str,
    resolved_at: str | None = None,
    settle_price: float | None = None,
) -> None:
    """Record how a Kalshi market resolved. Latest write wins."""
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
    conn.commit()


def compute_score(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
    disposition: str = "all",
) -> dict:
    """Score every settled opportunity matching the given segment."""
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

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return dict(EMPTY_SCORE)

    n = len(rows)
    wins = 0
    total_cost = 0.0
    total_return = 0.0
    taken_cost = 0.0
    taken_return = 0.0
    has_taken = False

    for row in rows:
        won = str(row["result"]).lower() == str(row["outcome"]).lower()
        price = row["entry_price"]
        cost = price + fee_pts(price) / 100.0
        payout = 1.0 if won else 0.0

        wins += 1 if won else 0
        total_cost += cost
        total_return += payout

        if row["user_action"] == "taken":
            has_taken = True
            taken_cost += cost
            taken_return += payout

    win_rate = wins / n
    price_implied_rate = sum(r["entry_price"] for r in rows) / n
    calibration_edge = (win_rate - price_implied_rate) * 100.0
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
        "mean_claimed_edge": mean_claimed_edge,
        "realization": _realization(calibration_edge, mean_claimed_edge),
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
    cursor = conn.execute(
        """
        INSERT INTO scores (
            theory_id, theory_version, run_mode, disposition, n, win_rate,
            price_implied_rate, calibration_edge, mean_claimed_edge,
            realization, roi_all, roi_taken, computed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            result["mean_claimed_edge"],
            result["realization"],
            result["roi_all"],
            result["roi_taken"],
            now or utcnow(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def interpretation_value(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
) -> dict:
    """Did stage-2 judgment earn its keep (spec section 7)?

    `delta` is endorsed calibration edge minus rejected calibration edge, in
    points. Positive means interpretation is adding edge; near zero means it
    is adding nothing; negative means it is destroying value. It is None
    until both groups have settled results to compare.
    """
    endorsed = compute_score(
        conn, theory_id, theory_version, run_mode, "endorsed"
    )
    rejected = compute_score(
        conn, theory_id, theory_version, run_mode, "rejected"
    )
    delta = None
    if endorsed["n"] and rejected["n"]:
        delta = endorsed["calibration_edge"] - rejected["calibration_edge"]
    return {"endorsed": endorsed, "rejected": rejected, "delta": delta}


def bucket_rates(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
) -> dict[str, dict]:
    """Realized win rate per confidence bucket (spec section 7).

    This is what a theory's confidence labels actually MEAN, measured rather
    than asserted. Only settled opportunities carrying a bucket count.
    """
    rows = conn.execute(
        """
        SELECT o.confidence, o.outcome, o.entry_price, s.result
        FROM opportunities o
        JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
        WHERE o.theory_id = ? AND o.theory_version = ? AND o.run_mode = ?
          AND o.confidence IS NOT NULL AND o.confidence != ''
        """,
        (theory_id, theory_version, run_mode),
    ).fetchall()

    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row["confidence"], []).append(row)

    return {
        bucket: {
            "n": len(members),
            "win_rate": sum(
                1
                for m in members
                if str(m["result"]).lower() == str(m["outcome"]).lower()
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
    conn.executemany(
        """
        INSERT INTO bucket_rates (theory_id, theory_version, confidence, n,
                                  win_rate, mean_entry_price, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return len(rows)
