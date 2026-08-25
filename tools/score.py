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

import math
import sqlite3

from tools.db import utcnow, write
from tools.ledger import EXPERIMENT_RUN_PREFIX
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
    "riskless_n": 0,
    "riskless_roi": None,
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
    else:
        # Pooled scoring never sees experiments (OOP spec section 3.3a):
        # a variant being tried must not contaminate the record it will
        # be judged against.
        sql += " AND o.run_id NOT LIKE ?"
        params.append(EXPERIMENT_RUN_PREFIX + "%")
    return sql, params


def _single_leg_observations(
    conn: sqlite3.Connection, theory_id: str, theory_version: int,
    run_mode: str, disposition: str, run_id: str | None,
) -> list[dict]:
    """One observation per settled single-leg position.

    It exists as its own function so that single positions and baskets can
    be built into one common observation shape -- implied_rate, won, cost,
    payout, fee_pts, edge_pts_net, user_action -- which `_aggregate` then
    consumes without knowing which kind it is holding. That shared shape is
    what lets a basket pool alongside singles as exactly one observation
    instead of forking the aggregation into two nearly-identical copies.
    """
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
            # A single position can always resolve against you -- there is
            # no floor to fall back on -- so it is never riskless.
            "riskless": False,
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
        " o.leg_count, o.max_payout, o.min_payout FROM opportunities o"
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
        # Explicit accumulator, not sum(): this quantity feeds mean_fee_pts
        # in _aggregate, whose contract (see the comment there) is exact
        # equivalence under CPython's naive += rather than sum()'s
        # compensated summation. Two terms happen to agree either way, but
        # a 3+-leg basket would silently diverge if this were sum().
        fee = 0.0
        for leg in legs:
            fee += fee_pts(leg["entry_price"])
        max_payout = header["max_payout"]
        min_payout = header["min_payout"]

        # A theory declares its own floor because only it knows its payoff
        # shape -- safe precisely because the claim is checkable here. A
        # payout beneath the declared floor means the declaration was
        # false, and a false floor would understate the at-risk cost and
        # overstate the edge.
        if payout < min_payout - 1e-9:
            raise ValueError(
                f"opportunity {header['id']}: settled payout {payout:.4f} is "
                f"below its declared min_payout {min_payout:.4f}. The floor "
                "is a claim about what the contracts guarantee and it did "
                "not hold, so the position cannot be scored against it. Fix "
                "the theory's declaration, not this check."
            )

        # The at-risk decomposition assumes the at-risk portion is binary:
        # the position pays either its floor or its ceiling. A basket that
        # can land in between (three legs of a possible three, say) has no
        # single event `won` can name, exactly as before this generalized
        # from {0, max_payout}. At min_payout = 0 -- every row recorded
        # before floors existed -- this is the identical condition.
        if not (
            math.isclose(payout, min_payout, rel_tol=1e-9, abs_tol=1e-9)
            or math.isclose(payout, max_payout, rel_tol=1e-9, abs_tol=1e-9)
        ):
            raise ValueError(
                f"opportunity {header['id']}: basket payout {payout:.4f} is "
                f"neither its min_payout {min_payout:.4f} nor its "
                f"max_payout {max_payout:.4f}. Scoring grades the portion "
                "of a position that is at risk, which assumes that portion "
                "is all-or-nothing. See docs/superpowers/specs/"
                "2026-08-24-multi-leg-positions-design.md section 3.6"
            )

        cost = header["entry_price"] + fee / 100.0

        # A position whose cost is covered by its guaranteed floor cannot
        # lose. Calibration is undefined for it -- a win rate over things
        # that always win is 1.0 by construction and measures nothing --
        # so it is flagged here and scored on return only (section 3.6.1).
        # Riskless-ness is judged on `cost` (fee included): a fee is real
        # cash paid, so it can turn an otherwise-covered floor into a loss.
        riskless = cost <= min_payout
        at_risk_payoff = max_payout - min_payout
        if riskless or at_risk_payoff <= 0:
            riskless = True
            implied_rate = None
            won = False
        else:
            # implied_rate is the market's rate, not the trader's cost --
            # fee is a transaction cost, not a market price, and stays out
            # for the same reason _single_leg_observations builds
            # implied_rate from `price` rather than `cost`. It is
            # normalized by header entry_price (pre-fee), matching the
            # single-leg convention and keeping fee out of this number so
            # `_aggregate` subtracts it exactly once, via mean_fee_pts, not
            # twice. At min_payout = 0 this is header['entry_price'] /
            # max_payout -- byte-identical to the pre-floor formula.
            implied_rate = (
                (header["entry_price"] - min_payout) / at_risk_payoff
            )
            won = math.isclose(payout, max_payout,
                               rel_tol=1e-9, abs_tol=1e-9)

        out.append({
            "implied_rate": implied_rate,
            "won": won,
            "cost": cost,
            "payout": payout,
            # Fees share implied_rate's scale, so they are normalized by
            # the same at-risk denominator. A riskless position has no
            # such scale; Task 4 keeps it out of the fee mean entirely.
            "fee_pts": fee if riskless else fee / at_risk_payoff,
            "edge_pts_net": header["edge_pts_net"],
            "user_action": header["user_action"],
            "riskless": riskless,
        })
    return out


def _aggregate(rows: list[dict]) -> dict:
    """Turn observations into the score dict. Shared by every position kind.

    A riskless observation (see `_basket_observations`) is split out first,
    before any arithmetic touches `implied_rate` -- a riskless row's
    `implied_rate` is None, and `price_implied_rate` below sums that field
    unconditionally, so summing before the split would raise `TypeError`.

    Riskless positions contribute to `roi_all` and `roi_taken` and nothing
    else. Those two measure money, and a covered floor is still real money
    returned. Every other figure here -- `n`, `win_rate`,
    `price_implied_rate`, `calibration_edge(_net)`, `mean_claimed_edge`,
    `mean_fee_pts`, `realization` -- measures whether the theory's judgment
    was right, and a position that cannot lose was never a bet on anything:
    a win rate computed over positions that always win is 1.0 by
    construction, and folding a certain return in with a predictive edge
    would average two different animals into a number that describes
    neither. They are reported instead as `riskless_n` and `riskless_roi`.
    """
    riskless = [r for r in rows if r.get("riskless")]
    rows = [r for r in rows if not r.get("riskless")]

    riskless_n = len(riskless)
    # Hand-rolled accumulation, not sum(), for the same reason as the loop
    # below: this function's contract is exact arithmetic equivalence with
    # the pre-refactor implementation, and mixing accumulation styles would
    # make the riskless and calibrated totals round differently before
    # they are folded together.
    riskless_cost = 0.0
    riskless_return = 0.0
    riskless_taken_cost = 0.0
    riskless_taken_return = 0.0
    riskless_has_taken = False
    for r in riskless:
        riskless_cost += r["cost"]
        riskless_return += r["payout"]
        if r["user_action"] == "taken":
            riskless_has_taken = True
            riskless_taken_cost += r["cost"]
            riskless_taken_return += r["payout"]
    riskless_roi = (
        (riskless_return - riskless_cost) / riskless_cost
        if riskless_cost else None
    )

    if not rows:
        # Nothing calibrated ran, but arbitrage still moved money -- a
        # theory that produced only riskless positions must still report
        # its return rather than disappearing into EMPTY_SCORE's roi_all
        # of None.
        result = dict(EMPTY_SCORE)
        result["riskless_n"] = riskless_n
        result["riskless_roi"] = riskless_roi
        result["roi_all"] = riskless_roi
        result["roi_taken"] = (
            (riskless_taken_return - riskless_taken_cost) / riskless_taken_cost
            if riskless_has_taken and riskless_taken_cost
            else None
        )
        return result

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

    # Riskless cost and payout fold into ROI only -- the money figures --
    # never into the counts or rates above, which is what keeps a certain
    # arbitrage return from inflating a predictive win rate.
    all_cost = total_cost + riskless_cost
    all_return = total_return + riskless_return
    all_taken_cost = taken_cost + riskless_taken_cost
    all_taken_return = taken_return + riskless_taken_return
    all_has_taken = has_taken or riskless_has_taken

    roi_all = (all_return - all_cost) / all_cost if all_cost else None
    roi_taken = (
        (all_taken_return - all_taken_cost) / all_taken_cost
        if all_has_taken and all_taken_cost
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
        "riskless_n": riskless_n,
        "riskless_roi": riskless_roi,
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
                mean_claimed_edge, realization, roi_all, roi_taken,
                riskless_n, riskless_roi, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                result["riskless_n"],
                result["riskless_roi"],
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
    # Baskets are excluded deliberately: a basket's header carries the
    # synthetic BASKET:<hash> ticker, which never appears in `settlements`,
    # so this join could only ever drop them. The predicate says so out
    # loud rather than leaving the exclusion to be inferred from the join.
    sql = """
        SELECT o.confidence, o.outcome, o.entry_price, s.result
        FROM opportunities o
        JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
        WHERE o.theory_id = ? AND o.theory_version = ? AND o.run_mode = ?
          AND o.position_kind = 'single'
          AND o.confidence IS NOT NULL AND o.confidence != ''
    """
    params: list[object] = [theory_id, theory_version, run_mode]
    if run_id is not None:
        sql += " AND o.run_id = ?"
        params.append(run_id)
    else:
        # Pooled scoring never sees experiments (OOP spec section 3.3a):
        # a variant being tried must not contaminate the record it will
        # be judged against.
        sql += " AND o.run_id NOT LIKE ?"
        params.append(EXPERIMENT_RUN_PREFIX + "%")

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
