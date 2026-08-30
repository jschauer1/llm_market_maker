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

**Scoring follows DECISIONS, not positions** (ruling 2026-08-29). Four
rules, implemented in `_DECISION_ATTEMPTS` and tested in
`tests/test_attempt_scoring.py`:

1. An **attempt** joins the pool of **its own** disposition. A position
   endorsed on Monday and rejected on Tuesday earns settlement feedback
   in *both* pools, because two decisions really were made.
2. Each run of consecutive same-disposition attempts collapses to its
   **first**. Re-affirmations at drifted prices are the standing decision
   re-observed. Keyed on *changes*, so endorsed -> rejected -> endorsed
   scores both endorsements.
3. A `screened` attempt on a position already carrying an interpreted
   verdict is a **non-decision**: retained in the ledger, skipped by
   scoring. A `screened` attempt *before* any interpretation still
   scores -- that is the genuine stage-1 baseline.
4. `opportunities.disposition` is the **current view only** -- display
   and live decisions. It is never a scoring key. Grouping on it let a
   later run retroactively erase an earlier run's published decision,
   which is the disposition-form of the silent merge the versioning rule
   exists to prevent.

Scores are computed per (theory, version, run_mode, disposition), and
optionally per run_id. The disposition split is what makes the value of
stage-2 interpretation measurable: endorsed versus rejected, with rejected
candidates serving as a free control group. The run_id filter keeps a
re-run backtest from pooling into one inflated sample.
"""

from __future__ import annotations

import json
import math
import sqlite3
import statistics

from tools.db import utcnow, write
from tools.rank import realization as _realization
from tools.sizing import fee_pts
from tools import theories

VALID_TIERS = ("A", "B", "C")

# One row per (opportunity_id, run_id) -- the earliest attempt by
# (decision_date, recorded_at) -- for a LEFT JOIN to price a run-scoped
# observation without fanning it out.
#
# opportunity_attempts' primary key is (opportunity_id, decision_date,
# run_id): one run proposing a position on two different decision dates is
# the normal case, not an edge case, and produces two attempt rows sharing
# an opportunity_id and run_id. Joining on (opportunity_id, run_id) alone
# would match both and multiply that position into two observations under
# `--run-id` -- the exact per-recording double counting this branch exists
# to remove, just relocated from the position row to the join. Ranked with
# ROW_NUMBER rather than aggregated with MIN/MAX, because the ledger's
# "first sighting owns entry_price" rule (`record_opportunity`'s re-sighting
# UPDATE) needs the whole earliest row's entry_price and edge_pts_net
# together, not a column-wise blend that could pair one attempt's price
# with another's edge.
_EARLIEST_ATTEMPT_PER_RUN = """
    SELECT opportunity_id, entry_price, edge_pts_net, decision_date FROM (
        SELECT opportunity_id, entry_price, edge_pts_net, decision_date,
               ROW_NUMBER() OVER (
                   PARTITION BY opportunity_id
                   ORDER BY decision_date, recorded_at
               ) AS rn
        FROM opportunity_attempts
        WHERE run_id = ?
    ) WHERE rn = 1
"""

#: The attempts that are DECISIONS, one row per decision (ruling
#: 2026-08-29). Scoring follows decisions, not positions: the position's
#: own `disposition` column is the CURRENT view only -- display and live
#: use -- and is never a scoring key. Grouping on it let a later run
#: retroactively erase an earlier run's published decision, which is the
#: disposition-form of the silent merge the versioning rule exists to
#: prevent: re-see your losers, flip them to `rejected`, launder the
#: endorsed pool.
#:
#: Three rules, all visible in the SQL below:
#:
#: 1. CONSECUTIVE-RUN DEDUPE. A decision happens when the verdict
#:    CHANGES, so each run of same-disposition attempts collapses to its
#:    first. Re-affirmations at drifted prices are the standing decision
#:    re-observed, not new decisions -- position 9249 on the live data was
#:    `screened` four times over three days at four prices. Keyed on
#:    changes rather than on (position, disposition) globally so that
#:    endorsed -> rejected -> endorsed scores BOTH endorsements: a
#:    changed mind is a real decision at its own price.
#: 2. FIRST OF RUN, not last -- the earliest price is the least
#:    contaminated by drift toward resolution.
#: 3. POST-INTERPRETATION `screened` ROWS ARE NON-DECISIONS. A `screened`
#:    attempt on a position already carrying an interpreted verdict at or
#:    before that date records the scan re-seeing the market without
#:    stage 2 engaging -- the absence of a new judgment, not a judgment.
#:    Scoring it would put one settlement into three pools, pollute the
#:    stage-1 baseline with exactly the subpopulation stage 2 engaged on,
#:    and make the screened pool's composition depend on scan cadence.
#:    The row stays in the ledger (it is a true record of what the scan
#:    saw); it is only unscored. A `screened` attempt BEFORE any
#:    interpretation still scores -- that is the genuine stage-1 baseline,
#:    and dropping it would bias the screened pool toward
#:    never-interpreted positions. For a fully mechanical theory there are
#:    no interpreted attempts, so this rule is a no-op.
_DECISION_ATTEMPTS = """
    SELECT opportunity_id, disposition, entry_price, edge_pts_net,
           confidence, decision_date, run_id
    FROM (
        SELECT opportunity_id, disposition, entry_price, edge_pts_net,
               confidence, decision_date, run_id,
               LAG(disposition) OVER (
                   PARTITION BY opportunity_id
                   ORDER BY decision_date, recorded_at
               ) AS prev_disposition
        FROM opportunity_attempts
    ) t
    WHERE (prev_disposition IS NULL OR prev_disposition <> disposition)
      AND NOT (
        t.disposition = 'screened'
        AND EXISTS (
            SELECT 1 FROM opportunity_attempts pi
            WHERE pi.opportunity_id = t.opportunity_id
              AND pi.disposition IN ('endorsed', 'rejected')
              AND pi.decision_date <= t.decision_date
        )
      )
"""

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
    "n_attempts": 0,
    "n_clusters": 0,
    "clustered_se": None,
    "unclustered_rows": 0,
}


def cluster_key(row: sqlite3.Row) -> tuple[str, bool]:
    """(cluster id, was it recoverable) for one observation.

    Sibling markets of ONE Kalshi event share an outcome driver, so
    pooling them as independent draws manufactures precision: session
    78's hazard estimate ran z~9 naive against 1.34 once clustered, on
    2,805 rows that were only 48 clusters. Uncertainty is therefore
    clustered at the EVENT level, and `n_clusters` -- not the row count --
    is what feeds credibility, so a theory holding fifty siblings of one
    event cannot rank as n=50.

    `opportunity_attempts` carries no event ticker, so it is derived:
    `extra_json.event_ticker` where the theory recorded one, else the
    ticker with its last dash-segment stripped, which is Kalshi's own
    event/strike convention. An unrecoverable row falls back to its own
    ticker -- a cluster of one, which is conservative in the right
    direction (it never merges two events) but does not shrink n; those
    rows are counted and reported as `unclustered_rows` rather than
    silently bucketed.
    """
    raw = row["extra_json"] if "extra_json" in row.keys() else None
    if raw:
        try:
            ev = json.loads(raw).get("event_ticker")
            if ev:
                return str(ev), True
        except (ValueError, TypeError):
            pass
    ticker = row["kalshi_ticker"] or ""
    if "-" in ticker:
        return ticker.rsplit("-", 1)[0], True
    return ticker, False


def _clustered_stats(rows: list[dict]) -> tuple[int, float | None, int]:
    """(n_clusters, clustered SE of the net calibration edge, unrecoverable).

    Outcomes are aggregated WITHIN each cluster first, then the SE is the
    between-cluster standard error of those cluster means. `None` below
    two clusters: one cluster carries no information about spread, and
    returning the row-level SE there is precisely the overstatement this
    exists to correct.
    """
    by: dict[str, list[dict]] = {}
    unrecoverable = 0
    for r in rows:
        key = r.get("cluster")
        if not r.get("cluster_ok", True):
            unrecoverable += 1
        by.setdefault(key or "", []).append(r)
    means = []
    for group in by.values():
        edges = [(r["won"] - r["implied_rate"]) * 100.0 - r["fee_pts"]
                 for r in group if r.get("implied_rate") is not None]
        if edges:
            means.append(statistics.mean(edges))
    if len(means) < 2:
        return len(by), None, unrecoverable
    se = statistics.stdev(means) / len(means) ** 0.5
    return len(by), se, unrecoverable


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


def observations(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
    disposition: str = "all",
    *,
    run_id: str | None = None,
    pool: str = "version",
) -> list[dict]:
    """Every settled observation for the segment, one dict per unit.

    The public seam between the scoring SQL and any consumer that needs
    to partition observations before aggregating — `tools/slices.py` is
    the caller this exists for. Each dict carries what `aggregate`
    consumes plus the identity fields a slice predicate and its
    out-of-sample split key on: `position_kind`, `outcome`,
    `confidence`, `entry_price`, `extra` (parsed `extra_json`),
    `decision_date`, `run_id`, `run_ids` (every run that proposed the
    position — the first seer alone would hide a judged re-proposal),
    and `resolved_day`. Partitioning this list
    and calling `aggregate` on a part is exactly `compute_score` on that
    part — same identity, decision, and cluster semantics, because it is
    the same rows.

    `pool="version"` (default) scopes to `theory_version` alone, exactly
    as before this parameter existed. `pool="chain"` resolves
    `theories.carry_chain` and widens the segment to every version a
    proven `carry` bump links back to `theory_version` (spec 2.5).
    """
    versions = (
        theories.carry_chain(conn, theory_id, theory_version)
        if pool == "chain" else None
    )
    return _single_leg_observations(
        conn, theory_id, theory_version, run_mode, disposition, run_id,
        versions=versions,
    ) + _basket_observations(
        conn, theory_id, theory_version, run_mode, disposition, run_id,
        versions=versions,
    )


def aggregate(rows: list[dict]) -> dict:
    """Turn a list of observations into the score dict.

    Public counterpart of `_aggregate` for consumers of `observations`.
    """
    return _aggregate(rows)


def compute_score(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
    disposition: str = "all",
    *,
    run_id: str | None = None,
    pool: str = "version",
) -> dict:
    """Score every settled opportunity matching the given segment.

    Pass `run_id` to score a single run. Without it every run of the same
    theory version pools together, so re-running a backtest over the same
    markets multiplies `n` without adding a single real bet.

    `pool="version"` (default) is today's behaviour, unchanged — no
    existing caller's meaning moves. `pool="chain"` widens the segment to
    the maximal run of consecutive versions a proven `carry` bump links
    back to `theory_version` (spec 2.5); the returned dict then gains
    `chain_versions` so a pooled number can never be read without seeing
    what was pooled into it. A chain of one version (nothing proven
    carry) adds no key, since nothing was pooled.
    """
    if pool not in ("version", "chain"):
        raise ValueError(f"invalid pool {pool!r}; expected 'version' or 'chain'")
    result = _aggregate(
        observations(
            conn, theory_id, theory_version, run_mode, disposition,
            run_id=run_id, pool=pool,
        )
    )
    if pool == "chain":
        chain = theories.carry_chain(conn, theory_id, theory_version)
        if len(chain) > 1:
            result["chain_versions"] = chain
    return result


def _segment_filter(
    theory_id: str, theory_version: int, run_mode: str,
    disposition: str, run_id: str | None,
    *, versions: list[int] | None = None,
) -> tuple[str, list[object]]:
    """The WHERE clause every observation query shares.

    `versions`, when given (a proven carry-chain, spec 2.5), widens the
    version predicate from an exact match to `IN (...)` over the whole
    chain. `theory_version` alone -- the path every caller already used
    -- builds the identical SQL text and params it always has, so
    `pool="version"` stays byte-identical to before this parameter
    existed.
    """
    if versions:
        placeholders = ",".join("?" * len(versions))
        sql = (
            " WHERE o.theory_id = ? AND o.theory_version IN"
            f" ({placeholders}) AND o.run_mode = ?"
        )
        params: list[object] = [theory_id, *versions, run_mode]
    else:
        sql = " WHERE o.theory_id = ? AND o.theory_version = ? AND o.run_mode = ?"
        params = [theory_id, theory_version, run_mode]
    if disposition != "all":
        # Filtering is done by the decision join in the observation
        # builders, which yields one row per DECISION rather than one per
        # position -- see _DECISION_ATTEMPTS. Nothing is filtered here.
        pass
    if run_id is not None:
        # A position is in a run if any attempt named that run. The join in
        # the observation queries supplies the attempt; this only narrows.
        sql += " AND EXISTS (SELECT 1 FROM opportunity_attempts a" \
               " WHERE a.opportunity_id = o.id AND a.run_id = ?)"
        params.append(run_id)
    else:
        # Pooled scoring never sees experiments (OOP spec section 3.3a):
        # a variant being tried must not contaminate the record it will
        # be judged against. Keyed on the stored lane rather than on the
        # run_id prefix, because after a merge the surviving row's run_id
        # is whichever run saw it first.
        sql += " AND o.lane = 'main'"
    return sql, params


def _single_leg_observations(
    conn: sqlite3.Connection, theory_id: str, theory_version: int,
    run_mode: str, disposition: str, run_id: str | None,
    *, versions: list[int] | None = None,
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
        theory_id, theory_version, run_mode, disposition, run_id,
        versions=versions,
    )
    # Pooled (run_id is None), n_attempts is the position's LIFETIME
    # attempt count across every run that ever proposed it -- the intended
    # reveal of the collapse (position-identity spec section 2: 3,195
    # positions / 4,759 attempts on the real data), and that reading must
    # not change. Scoped to one run it must count only that run's own
    # attempts, or `score report --run-id <run>` reports every OTHER run
    # that ever touched the position as if it belonged to this one too --
    # a run that made 704 attempts would show n_attempts=1408 the moment a
    # second run had ever seen the same markets.
    n_attempts_sql, n_attempts_params = (
        ("(SELECT COUNT(*) FROM opportunity_attempts x"
         " WHERE x.opportunity_id = o.id) AS n_attempts,", [])
        if run_id is None else
        ("(SELECT COUNT(*) FROM opportunity_attempts x"
         " WHERE x.opportunity_id = o.id AND x.run_id = ?) AS n_attempts,",
         [run_id])
    )
    # The LEFT JOIN prices a run-scoped observation at that run's own
    # (earliest) attempt rather than the position's (possibly earlier)
    # entry_price. When run_id is None the derived table's WHERE run_id = ?
    # matches nothing -- SQL equality against a bound NULL is never true --
    # so both COALESCEs fall through to the position row and pooled scoring
    # reads exactly what it read before this join existed.
    sql = (
        "SELECT o.outcome, o.user_action, o.kalshi_ticker, o.extra_json,"
        " COALESCE(a.entry_price, d.entry_price, o.entry_price) AS entry_price,"
        " COALESCE(a.edge_pts_net, d.edge_pts_net, o.edge_pts_net) AS edge_pts_net,"
        # Observation identity for consumers of `observations()` (slice
        # scoring needs the fields a predicate and the out-of-sample split
        # key on). Position-level values serve the 'all' path; the decision
        # join's own values serve a named pool, so a flip-back's two
        # decisions each carry their own confidence, date, and run.
        " o.confidence AS position_confidence, o.run_id AS position_run_id,"
        " d.confidence AS decision_confidence,"
        " d.decision_date AS decision_decision_date,"
        " d.run_id AS decision_run_id,"
        " a.decision_date AS run_decision_date,"
        " (SELECT MIN(x.decision_date) FROM opportunity_attempts x"
        "  WHERE x.opportunity_id = o.id) AS first_decision_date,"
        # EVERY run that ever proposed this position, not just the first
        # seer. A position's own run_id is first-sighting only, and slice
        # out-of-sample designation must see a judged re-proposal: the
        # insider_judgment shape is a mechanical screen run recording the
        # position first and a designated judged run labeling it later.
        " (SELECT GROUP_CONCAT(DISTINCT x.run_id)"
        "    FROM opportunity_attempts x"
        "   WHERE x.opportunity_id = o.id) AS attempt_run_ids,"
        " " + n_attempts_sql +
        # The fallback inside COALESCE must match the same run-scoped price
        # `cost` below is built from -- bare o.entry_price would blend an
        # unpriced fill at the wrong reference under --run-id, where the
        # attempt's a.entry_price differs from the position row's own.
        # Nesting COALESCE inside COALESCE just tries f.price, then
        # a.entry_price, then o.entry_price -- SQL flattens it exactly like
        # the `entry_price` column above.
        " (SELECT SUM(f.size *"
        "         COALESCE(f.price, a.entry_price, d.entry_price, o.entry_price))"
        "    / NULLIF(SUM(f.size), 0)"
        "  FROM opportunity_fills f"
        "  WHERE f.opportunity_id = o.id) AS fill_price,"
        " s.result, s.resolved_at FROM opportunities o"
        " JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker"
        " LEFT JOIN (" + _EARLIEST_ATTEMPT_PER_RUN + ") a"
        "   ON a.opportunity_id = o.id"
        # One row per DECISION when a pool is named; when disposition is
        # "all" this degenerates to one row per position, so the whole
        # population is still counted once.
        # Always joined so the COALESCEs above resolve; when disposition
        # is "all" nothing matches (no attempt is stamped 'all'), d is
        # NULL throughout, and the whole population is counted once per
        # position exactly as before. When a pool IS named the NOT NULL
        # filter below turns this into an inner join, yielding one row per
        # DECISION -- so a flip-back contributes two rows to its pool.
        + " LEFT JOIN (" + _DECISION_ATTEMPTS + ") d"
          "   ON d.opportunity_id = o.id AND d.disposition = ?"
        + where
        + " AND o.position_kind = 'single'"
        + ("" if disposition == "all" else " AND d.opportunity_id IS NOT NULL")
    )
    rows = conn.execute(
        sql, n_attempts_params + [run_id, disposition] + params
    ).fetchall()
    out = []
    for row in rows:
        won = _won(row["outcome"], row["result"])
        cluster, cluster_ok = cluster_key(row)
        price = row["entry_price"]
        fee = fee_pts(price)
        paid = row["fill_price"]
        # Which confidence/date/run identifies this observation depends on
        # which unit it is: a named pool's row IS one decision, so the
        # decision attempt's own values apply; the 'all' path counts each
        # position once, priced at its earliest attempt, so the earliest
        # date and the first-seeing run apply.
        if disposition == "all":
            confidence = row["position_confidence"]
            decision_date = (
                row["run_decision_date"] if run_id is not None
                else row["first_decision_date"]
            )
            obs_run = run_id if run_id is not None else row["position_run_id"]
            # A named pool's row is one decision by one run; an 'all'-path
            # row is the whole position, which any number of runs touched.
            if run_id is not None:
                run_ids = [run_id]
            else:
                run_ids = [
                    r for r in (row["attempt_run_ids"] or "").split(",") if r
                ] or [row["position_run_id"]]
        else:
            confidence = row["decision_confidence"]
            decision_date = row["decision_decision_date"]
            obs_run = row["decision_run_id"]
            run_ids = [obs_run] if obs_run else []
        try:
            extra = json.loads(row["extra_json"]) if row["extra_json"] else {}
            if not isinstance(extra, dict):
                extra = {}
        except (ValueError, TypeError):
            extra = {}
        resolved = row["resolved_at"]
        out.append({
            "position_kind": "single",
            "outcome": row["outcome"],
            "confidence": confidence,
            "entry_price": price,
            "extra": extra,
            "decision_date": decision_date,
            "run_id": obs_run,
            "run_ids": run_ids,
            "resolved_day": str(resolved)[:10] if resolved else None,
            "implied_rate": price,
            "won": won,
            "cost": price + fee / 100.0,
            "payout": 1.0 if won else 0.0,
            "fee_pts": fee,
            "edge_pts_net": row["edge_pts_net"],
            "user_action": row["user_action"],
            "n_attempts": row["n_attempts"],
            "cluster": cluster,
            "cluster_ok": cluster_ok,
            "fill_price": paid,
            # The fee actually paid, at the recorded price. A single
            # position has one leg, so this is just fee_pts of that price
            # -- unlike a basket, there is no per-leg sum to preserve. When
            # a fill never recorded a price, `paid` falls back (in SQL) to
            # this row's own reference price, so fill_fee_pts here
            # reproduces `fee` above exactly and `_aggregate` never sees a
            # difference.
            "fill_fee_pts": None if paid is None else fee_pts(paid),
            # A single position can always resolve against you -- there is
            # no floor to fall back on -- so it is never riskless.
            "riskless": False,
        })
    return out


def _basket_observations(
    conn: sqlite3.Connection, theory_id: str, theory_version: int,
    run_mode: str, disposition: str, run_id: str | None,
    *, versions: list[int] | None = None,
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
        theory_id, theory_version, run_mode, disposition, run_id,
        versions=versions,
    )
    # Same run/pooled split as _single_leg_observations, and the same
    # reason: pooled n_attempts must stay the position's lifetime count
    # across every run, while a run-scoped count must not fold in attempts
    # made by other runs that happened to see the same basket.
    n_attempts_sql, n_attempts_params = (
        ("(SELECT COUNT(*) FROM opportunity_attempts x"
         " WHERE x.opportunity_id = o.id) AS n_attempts,", [])
        if run_id is None else
        ("(SELECT COUNT(*) FROM opportunity_attempts x"
         " WHERE x.opportunity_id = o.id AND x.run_id = ?) AS n_attempts,",
         [run_id])
    )
    # Same LEFT JOIN + COALESCE as _single_leg_observations, and the same
    # reason: price a run-scoped basket at that run's own earliest attempt,
    # while pooled scoring (run_id is None, so the derived table matches
    # nothing) reads the position row unchanged.
    headers = conn.execute(
        "SELECT o.id, o.user_action, o.leg_count, o.max_payout, o.min_payout,"
        " COALESCE(a.entry_price, d.entry_price, o.entry_price) AS entry_price,"
        " COALESCE(a.edge_pts_net, d.edge_pts_net, o.edge_pts_net) AS edge_pts_net,"
        " " + n_attempts_sql +
        # Same run-scoped fallback as _single_leg_observations: an unpriced
        # fill must blend at this basket's own COALESCE(a.entry_price,
        # o.entry_price), not the bare position-row price, or a partially
        # priced basket scored under --run-id would blend its unpriced fill
        # at the wrong reference.
        " (SELECT SUM(f.size *"
        "         COALESCE(f.price, a.entry_price, d.entry_price, o.entry_price))"
        "    / NULLIF(SUM(f.size), 0)"
        "  FROM opportunity_fills f"
        "  WHERE f.opportunity_id = o.id) AS fill_price"
        " FROM opportunities o"
        " LEFT JOIN (" + _EARLIEST_ATTEMPT_PER_RUN + ") a"
        "   ON a.opportunity_id = o.id"
        # One row per DECISION when a pool is named; when disposition is
        # "all" this degenerates to one row per position, so the whole
        # population is still counted once.
        # Always joined so the COALESCEs above resolve; when disposition
        # is "all" nothing matches (no attempt is stamped 'all'), d is
        # NULL throughout, and the whole population is counted once per
        # position exactly as before. When a pool IS named the NOT NULL
        # filter below turns this into an inner join, yielding one row per
        # DECISION -- so a flip-back contributes two rows to its pool.
        + " LEFT JOIN (" + _DECISION_ATTEMPTS + ") d"
          "   ON d.opportunity_id = o.id AND d.disposition = ?"
        + where
        + " AND o.position_kind = 'basket'"
        + ("" if disposition == "all" else " AND d.opportunity_id IS NOT NULL"),
        n_attempts_params + [run_id, disposition] + params,
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

        # The fee actually paid, at the price actually paid -- for a
        # basket's taken-money leg of `_aggregate`, not for `cost` above,
        # which stays the proposal's fee and never changes. A basket has no
        # per-leg fill data (`opportunity_fills` records one blended price
        # per position, not per leg), so there is no way to know which leg
        # absorbed the price move. This scales every leg's own price by the
        # same ratio the blended price moved by and re-sums fee_pts over
        # the scaled legs -- an approximation that assumes the legs moved
        # together between the call and the fill, which is the best a
        # single blended number can support. It is exact, not approximate,
        # in the common case where no price was ever recorded: then `paid`
        # equals header["entry_price"] (SQL's own fallback), the scale
        # factor is 1, and this reproduces `fee` above term for term -- so
        # a taken position with no fill price still costs exactly `cost`,
        # with no separate flag required to say so.
        paid = header["fill_price"]
        fill_fee_pts = None
        if paid is not None:
            ref = header["entry_price"]
            if ref == 0:
                # A zero-cost basket has nothing to scale a ratio against.
                # Real baskets never land here -- a basket that cost
                # nothing would already be riskless -- but the guard must
                # not raise. Fall back to the single-leg approximation:
                # fee on the blended price alone.
                fill_fee_pts = fee_pts(paid)
            else:
                scale = paid / ref
                fill_fee_pts = sum(
                    fee_pts(leg["entry_price"] * scale) for leg in legs
                )

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
            # A basket has no single outcome, confidence, or leg price, so
            # it carries only its kind: slice predicates (tools/slices.py)
            # never match a basket, by construction of their vocabulary.
            "position_kind": "basket",
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
            "n_attempts": header["n_attempts"],
            "fill_price": paid,
            "fill_fee_pts": fill_fee_pts,
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
    # Captured before the riskless split below so the n_attempts sum -- built
    # from this list, not from `rows` -- covers both groups. Summing after
    # the split would silently drop riskless positions' attempts.
    all_rows = list(rows)
    n_clusters, clustered_se, unclustered = _clustered_stats(
        [r for r in rows if not r.get("riskless")])

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
            # The money number uses what was actually paid. `cost` prices
            # the proposal; a fill prices the purchase, with its fee
            # supplied by the observation builder as `fill_fee_pts` --
            # only the builder holds the per-position-kind knowledge (a
            # basket's per-leg prices) the quadratic fee model needs to
            # price a fill correctly. They differ whenever the market moved
            # between the call and the entry.
            paid = r.get("fill_price")
            riskless_taken_cost += (
                r["cost"] if paid is None
                else paid + r["fill_fee_pts"] / 100.0
            )
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
        # How many proposals stand behind these positions. n counts
        # positions, because one settlement is one draw; this makes the
        # collapse visible instead of silent.
        result["n_attempts"] = sum(r.get("n_attempts", 1) for r in all_rows)
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
            # The money number uses what was actually paid. `cost` prices
            # the proposal; a fill prices the purchase, with its fee
            # supplied by the observation builder as `fill_fee_pts` --
            # only the builder holds the per-position-kind knowledge (a
            # basket's per-leg prices) the quadratic fee model needs to
            # price a fill correctly. They differ whenever the market moved
            # between the call and the entry.
            paid = r.get("fill_price")
            taken_cost += (
                r["cost"] if paid is None
                else paid + r["fill_fee_pts"] / 100.0
            )
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
        # How many proposals stand behind these positions. n counts
        # positions, because one settlement is one draw; this makes the
        # collapse visible instead of silent.
        "n_attempts": sum(r.get("n_attempts", 1) for r in all_rows),
        # The EFFECTIVE sample size. Sibling markets of one event share an
        # outcome driver, so `n` (rows) overstates evidence by roughly the
        # sibling count -- this is what credibility keys on, so fifty
        # siblings of one event cannot rank as n=50.
        "n_clusters": n_clusters,
        # Between-cluster SE of the net calibration edge. None below two
        # clusters, deliberately: one cluster says nothing about spread.
        "clustered_se": clustered_se,
        # Rows whose event could not be recovered and so cluster alone.
        # Conservative (never merges two events) but does not shrink n,
        # so it is reported rather than hidden.
        "unclustered_rows": unclustered,
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
                riskless_n, riskless_roi, computed_at, n_clusters,
                clustered_se
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                result.get("n_clusters"),
                result.get("clustered_se"),
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
        SELECT o.confidence, o.outcome, o.entry_price, s.result,
               s.resolved_at
        FROM opportunities o
        JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
        WHERE o.theory_id = ? AND o.theory_version = ? AND o.run_mode = ?
          AND o.position_kind = 'single'
          AND o.confidence IS NOT NULL AND o.confidence != ''
    """
    params: list[object] = [theory_id, theory_version, run_mode]
    if run_id is not None:
        sql += (
            " AND EXISTS (SELECT 1 FROM opportunity_attempts a"
            " WHERE a.opportunity_id = o.id AND a.run_id = ?)"
        )
        params.append(run_id)
    else:
        # Pooled scoring never sees experiments (OOP spec section 3.3a):
        # a variant being tried must not contaminate the record it will
        # be judged against. Keyed on lane, not on the run_id prefix --
        # after a merge the surviving row's run_id is whichever run saw
        # the position first.
        sql += " AND o.lane = 'main'"

    rows = conn.execute(sql, params).fetchall()

    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row["confidence"], []).append(row)

    def _n_days(members: list) -> int | None:
        """Distinct settlement days behind a bucket's rate, or None.

        None when no member carries a `resolved_at` -- older backtest rows
        settled without one. Unknown must read as unknown rather than as
        zero or one, because `buckets.measured_gross` fails closed on it:
        a day count that cannot be checked is not a day count.
        """
        days = {m["resolved_at"][:10] for m in members if m["resolved_at"]}
        return len(days) or None

    return {
        bucket: {
            "n": len(members),
            "win_rate": sum(
                1 for m in members if _won(m["outcome"], m["result"])
            )
            / len(members),
            "mean_entry_price": sum(m["entry_price"] for m in members)
            / len(members),
            # Rows are not independent draws; a bucket measured on one
            # settlement day has one draw behind it however many rows it
            # holds. See tools/buckets.MIN_BUCKET_DAYS.
            "n_days": _n_days(members),
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
         data["mean_entry_price"], data.get("n_days"), stamp)
        for bucket, data in rates.items()
    ]
    if not rows:
        return 0
    with write(conn):
        conn.executemany(
            """
            INSERT INTO bucket_rates (theory_id, theory_version, confidence,
                                      n, win_rate, mean_entry_price,
                                      n_days, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def settlement_day_clusters(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
    disposition: str = "all",
    *,
    run_id: str | None = None,
    pool: str = "version",
) -> dict:
    """Calibration edge broken out by settlement day, with a clustered SE.

    `compute_score`'s `n` counts rows, and treats them as independent draws.
    They are not. Kalshi markets settle in day-clumps -- a screen's whole
    near-term board resolves within hours of itself -- and a day on which
    favorites overperform lifts every row that settled on it at once.
    Measured on the shared insider_bias screen population over three
    consecutive close-days (2026-08-25/26/27, n=215, whole population, not
    a theory's picks), the day-level favorite edge ran +5.00, -6.30, +6.14
    net, and the YES/NO split reversed outright between days: YES -0.61 /
    NO +8.67 on the 25th against YES +12.89 / NO -2.30 on the 27th. That
    swing is wider than any edge either live theory claims, so a score
    drawn from one settlement day measures the day, not the theory.

    So the honest unit of evidence is the day, not the row:

    - `n_days` is the effective sample size. One day is one draw, whatever
      `n` says.
    - `day_clustered_se` is the standard error of the per-day edges about
      their mean (between-cluster, unweighted). It is `None` below two
      days, because a single cluster carries no information about spread
      -- returning the row-level SE there would be precisely the
      overstatement this function exists to correct.

    Days are equally weighted rather than row-weighted: the question is how
    much the edge moves between days, and a heavy day is still one draw
    from that distribution.

    Riskless positions are excluded for `_aggregate`'s reason -- they have
    no implied rate and no forecast to be right about. Baskets are excluded
    for `bucket_rates`' reason: a basket header's synthetic ticker never
    appears in `settlements`.

    Priced the same way `compute_score` is, and for the same reason: under
    `--run-id` this reads that run's own earliest attempt (via the same
    `_EARLIEST_ATTEMPT_PER_RUN` join `_single_leg_observations` uses), not
    the position row's `entry_price`, which can be a different run's first
    sighting. `_segment_filter` already scopes both to the same rows; this
    is what keeps them priced alike too, so this never silently disagrees
    with `compute_score` on the price behind the edge it reports.

    `pool="version"` (default) is today's behaviour, unchanged -- no
    existing caller's meaning moves. `pool="chain"` widens the segment
    the same way `compute_score(pool="chain")` does (spec 2.5): every
    version a proven `carry` bump links back to `theory_version` pools
    into the same day-clusters, and the returned dict gains
    `chain_versions` so a pooled day-count can never be read without
    seeing what was pooled into it. A chain of one version (nothing
    proven carry) adds no key, since nothing was pooled. Pooling widens
    which *rows* fall into each day, not the day-clustering logic
    itself -- a day that only v1 settled on and a day that only v2
    settled on both still cluster independently, exactly as they would
    if two runs of one version had produced them.
    """
    if pool not in ("version", "chain"):
        raise ValueError(f"invalid pool {pool!r}; expected 'version' or 'chain'")
    versions = (
        theories.carry_chain(conn, theory_id, theory_version)
        if pool == "chain" else None
    )
    where, params = _segment_filter(
        theory_id, theory_version, run_mode, disposition, run_id,
        versions=versions,
    )
    # Same LEFT JOIN + COALESCE as _single_leg_observations, and the same
    # reason: under --run-id this must price at that run's own earliest
    # attempt, not the position row's (possibly earlier, possibly later)
    # entry_price -- `_segment_filter` already scopes both functions to the
    # same rows, and this join is what keeps them priced alike too. When
    # run_id is None the derived table matches nothing and this reads
    # o.entry_price unchanged, exactly as before this join existed.
    sql = (
        "SELECT o.outcome, COALESCE(a.entry_price, o.entry_price)"
        " AS entry_price, s.result,"
        " SUBSTR(COALESCE(s.resolved_at, ''), 1, 10) AS day"
        " FROM opportunities o"
        " JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker"
        " LEFT JOIN (" + _EARLIEST_ATTEMPT_PER_RUN + ") a"
        "   ON a.opportunity_id = o.id"
        # Same decision join as compute_score, so the day breakdown always
        # describes exactly the rows the score describes.
        " LEFT JOIN (" + _DECISION_ATTEMPTS + ") d"
        "   ON d.opportunity_id = o.id AND d.disposition = ?"
        + where
        + " AND o.position_kind = 'single'"
        + ("" if disposition == "all" else " AND d.opportunity_id IS NOT NULL")
    )

    grouped: dict[str, list[dict]] = {}
    total = 0
    for row in conn.execute(sql, [run_id, disposition] + params).fetchall():
        # A settlement with no resolved_at cannot be assigned to a day. It
        # still counts in `n` so this never silently disagrees with
        # `compute_score`, but it forms no cluster.
        total += 1
        day = row["day"]
        if not day:
            continue
        price = row["entry_price"]
        grouped.setdefault(day, []).append({
            "won": _won(row["outcome"], row["result"]),
            "implied_rate": price,
            "fee_pts": fee_pts(price),
        })

    days = []
    for day in sorted(grouped):
        members = grouped[day]
        count = len(members)
        win_rate = sum(1 for m in members if m["won"]) / count
        implied = sum(m["implied_rate"] for m in members) / count
        fee = sum(m["fee_pts"] for m in members) / count
        edge = (win_rate - implied) * 100.0
        days.append({
            "day": day,
            "n": count,
            "win_rate": win_rate,
            "price_implied_rate": implied,
            "calibration_edge": edge,
            "calibration_edge_net": edge - fee,
        })

    n_days = len(days)
    if n_days == 0:
        mean_edge = mean_edge_net = None
        clustered_se = None
    else:
        mean_edge = sum(d["calibration_edge"] for d in days) / n_days
        mean_edge_net = sum(
            d["calibration_edge_net"] for d in days
        ) / n_days
        if n_days < 2:
            clustered_se = None
        else:
            variance = sum(
                (d["calibration_edge"] - mean_edge) ** 2 for d in days
            ) / (n_days - 1)
            clustered_se = math.sqrt(variance / n_days)

    result = {
        "n": total,
        "n_days": n_days,
        "days": days,
        # Day-weighted, so this deliberately differs from `compute_score`'s
        # row-weighted `calibration_edge`. Both are correct answers to
        # different questions; this one answers "what does a typical day
        # look like", which is the one `n_days` can put an error bar on.
        "calibration_edge": mean_edge,
        "calibration_edge_net": mean_edge_net,
        "day_clustered_se": clustered_se,
    }
    if pool == "chain" and versions and len(versions) > 1:
        result["chain_versions"] = versions
    return result
