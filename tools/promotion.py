"""The promotion key evaluator — which rung a recorded candidate sits on.

`docs/promotion-key.md` is the authority this module implements; the two
are held to the same version and rung set by tests/test_promotion.py.
Sessions cite the rung this module returns for every bet reported and
every bet withheld — the key exists so that decision is never a
per-session judgment call, and this module exists so nobody applies the
key's numeric predicates by eye (that is where the documented row-mixing
failures live).

Every rank input comes from the one segment row
`tools/slices.py::ranking_segment` selects (chain pool), so slice-over-
aggregate precedence and the no-mixing rule hold by construction.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Mapping

from tools import ledger, rank, sizing, slices, theories

KEY_VERSION = 2

RUNGS = {
    "R1": "RECOMMENDED",
    "R2": "RISKLESS",
    "R3": "PROVISIONAL",
    "R4": "ACCRUING",
    "R5": "MEASURED-AGAINST",
    "R6": "CONTROL",
}

# Evidence gates for a segment to count as measured — the same floors the
# slice-readiness machinery uses, applied to every segment kind so a
# complement or aggregate is never held to a softer bar than a slice.
GATE_CLUSTERS = rank.PROBATION_N
GATE_DAYS = slices.MIN_SLICE_DAYS
# Ruling 14 (2026-08-30): a calibration figure spanning fewer settlement
# days than this has no usable error bar and supports no rung above R4.
MIN_DAYS_MEASURABLE = 3


@dataclass(frozen=True)
class Promotion:
    opportunity_id: int
    kalshi_ticker: str
    outcome: str
    theory_id: str
    theory_version: int
    rung: str
    rung_name: str
    segment: str | None
    rank_inputs: dict | None
    ranked_edge: float | None
    claimed_edge_pts: float | None
    quoted: bool
    reasons: list[str] = field(default_factory=list)
    chain_versions: list[int] | None = None
    key_version: int = KEY_VERSION


def _mget(market, key: str):
    if isinstance(market, Mapping):
        return market.get(key)
    return getattr(market, key, None)


def _side_quote(outcome: str, market) -> tuple[float | None, float | None]:
    """(ask for this side, spread in pts). NO trades at 1 - the YES book."""
    yes_bid, yes_ask = _mget(market, "yes_bid"), _mget(market, "yes_ask")
    if str(outcome).lower() == "yes":
        ask, bid = yes_ask, yes_bid
    else:
        ask = None if yes_bid is None else 1.0 - yes_bid
        bid = None if yes_ask is None else 1.0 - yes_ask
    spread = None
    if ask is not None and bid is not None:
        spread = max(0.0, ask - bid) * 100.0
    return ask, spread


def _claimed_at_ask(row: sqlite3.Row, ask: float) -> float:
    """Recorded net claim adjusted to today's ask: price delta + fee delta."""
    entry = row["entry_price"]
    return (
        row["edge_pts_net"]
        - (ask - entry) * 100.0
        - (sizing.fee_pts(ask) - sizing.fee_pts(entry))
    )


def _is_settled(conn: sqlite3.Connection, row: sqlite3.Row) -> bool:
    """Same semantics as ledger.list_opportunities(unsettled_only=True)."""
    if row["position_kind"] == "basket":
        done = conn.execute(
            "SELECT COUNT(*) AS c FROM opportunity_legs l"
            " WHERE l.opportunity_id = ?"
            "   AND l.kalshi_ticker IN (SELECT kalshi_ticker FROM settlements)",
            (row["id"],),
        ).fetchone()["c"]
        return done >= row["leg_count"]
    hit = conn.execute(
        "SELECT 1 FROM settlements WHERE kalshi_ticker = ?",
        (row["kalshi_ticker"],),
    ).fetchone()
    return hit is not None


def _basket_cost_with_fees(conn: sqlite3.Connection, row: sqlite3.Row) -> float:
    cost = row["entry_price"]
    if row["fee_pts"] is not None:
        return cost + row["fee_pts"] / 100.0
    fees = sum(
        sizing.fee_pts(leg["entry_price"]) / 100.0
        for leg in ledger.get_legs(conn, row["id"])
    )
    return cost + fees


def promote(
    conn: sqlite3.Connection,
    opportunity_id: int,
    *,
    market=None,
    report: dict | None = None,
) -> Promotion:
    """Classify one recorded candidate onto its promotion-key rung.

    `market` is an optional current quote for the row's ticker (a Mapping
    or `domain.Market` carrying `yes_bid`/`yes_ask`). Without it, R1/R3
    are evaluated on the recorded entry price and flagged `unquoted` —
    the caller must re-quote before acting on the bet. `report` is an
    optional pre-built `slices.segment_report` for the row's (theory,
    version), for batch callers.
    """
    row = ledger.get_opportunity(conn, opportunity_id)
    if row is None:
        raise KeyError(opportunity_id)

    def result(rung, *, segment=None, rank_inputs=None, ranked=None,
               claimed=None, quoted=False, reasons=(), chain=None):
        return Promotion(
            opportunity_id=row["id"],
            kalshi_ticker=row["kalshi_ticker"],
            outcome=row["outcome"],
            theory_id=row["theory_id"],
            theory_version=row["theory_version"],
            rung=rung,
            rung_name=RUNGS[rung],
            segment=segment,
            rank_inputs=rank_inputs,
            ranked_edge=ranked,
            claimed_edge_pts=claimed,
            quoted=quoted,
            reasons=list(reasons),
            chain_versions=chain,
        )

    # --- R6: rows that are never bets -------------------------------------
    if _is_settled(conn, row):
        return result("R6", reasons=["position already settled — not promotable"])
    if row["disposition"] == "rejected":
        return result("R6", reasons=["rejected at stage 2 — control group"])
    if row["edge_pts_net"] is None or row["edge_pts_net"] <= 0:
        return result("R6", reasons=[
            "no positive claimed edge — observation/control row (ruling 13)"
        ])

    # --- R2: an arbitrage is not a forecast --------------------------------
    if row["position_kind"] == "basket":
        cost = _basket_cost_with_fees(conn, row)
        if cost <= row["min_payout"] + 1e-9:
            return result("R2", claimed=row["edge_pts_net"], reasons=[
                f"riskless: cost with fees {cost:.4f} <= "
                f"min payout {row['min_payout']:.4f}"
            ])

    # --- gate: a judgment theory's candidate needs stage 2 -----------------
    trow = theories.get(conn, row["theory_id"])
    if trow is not None and trow["uses_llm_judgment"] \
            and row["disposition"] != "endorsed":
        return result("R4", claimed=row["edge_pts_net"], reasons=[
            "awaiting stage-2 endorsement — judgment theory, "
            f"disposition {row['disposition']!r}"
        ])

    # --- the segment that ranks this candidate -----------------------------
    seg = slices.ranking_segment(conn, row, pool="chain", report=report)
    seg_score = seg["score"]
    n = seg_score.get("n_clusters") or 0
    days = seg_score.get("n_days") or 0
    cal = seg_score.get("calibration_edge_net")
    mean_claimed = seg_score.get("mean_claimed_edge")
    rank_inputs = seg["rank_inputs"]
    chain = seg.get("chain_versions")
    reasons: list[str] = []
    if seg.get("note"):
        reasons.append(seg["note"])
    # Disclosure, never a discount: a backtested edge counts exactly as a
    # forward-settled one (ruling 2026-08-31), and no rung below reads
    # this. It is here because the user asked to be told when the record
    # promoting a bet is replayed history rather than settlements that
    # came in forward.
    n_backtest = seg_score.get("n_backtest") or 0
    if n_backtest:
        rows_total = seg_score.get("n") or 0
        reasons.append(
            f"evidence is {n_backtest}/{rows_total} rows replayed from "
            "backtest history (tier A/B; counts as evidence in full)"
        )

    def ranked(claimed):
        return rank.ranked_edge(claimed, n, cal, mean_claimed)

    common = dict(segment=seg["segment"], rank_inputs=rank_inputs, chain=chain)

    gates_met = n >= GATE_CLUSTERS and days >= GATE_DAYS
    if gates_met and (cal is None or cal <= 0):
        return result("R5", claimed=row["edge_pts_net"],
                      ranked=ranked(row["edge_pts_net"]), reasons=reasons + [
                          f"measured against: calibration_edge_net {cal} "
                          f"over n_clusters={n}, n_days={days} — the record "
                          "outranks the claim"
                      ], **common)

    if cal is not None and cal > 0 and days >= MIN_DAYS_MEASURABLE:
        candidate = "R1" if gates_met else "R3"
        if candidate == "R3":
            reasons.append(
                f"below gates: n_clusters {n}/{GATE_CLUSTERS}, "
                f"n_days {days}/{GATE_DAYS}"
            )
    else:
        return result("R4", claimed=row["edge_pts_net"], reasons=reasons + [
            f"no measurable positive out-of-sample record on segment "
            f"{seg['segment']} (calibration_edge_net={cal}, n_clusters={n}, "
            f"n_days={days}; ruling 14 floor {MIN_DAYS_MEASURABLE} days)"
        ], **common)

    # --- R1/R3 preconditions: today's ask, executability -------------------
    claimed = row["edge_pts_net"]
    quoted = False
    if market is not None:
        ask, spread = _side_quote(row["outcome"], market)
        if ask is None:
            return result("R4", claimed=claimed, quoted=True,
                          reasons=reasons + ["not takeable: no ask in "
                                             "today's quote"], **common)
        quoted = True
        claimed = _claimed_at_ask(row, ask)
        if claimed <= 0:
            return result("R4", claimed=claimed, quoted=True,
                          ranked=ranked(claimed), reasons=reasons + [
                              f"edge gone at today's ask {ask:.2f} "
                              f"(claimed {claimed:.2f} pts)"
                          ], **common)
        if spread is not None and spread >= claimed:
            return result("R4", claimed=claimed, quoted=True,
                          ranked=ranked(claimed), reasons=reasons + [
                              f"not takeable: spread {spread:.2f} pts >= "
                              f"claimed edge {claimed:.2f} pts"
                          ], **common)
    else:
        reasons.append(
            "unquoted: rung assumes recorded entry price — verify at "
            "today's ask before acting"
        )

    return result(candidate, claimed=claimed, quoted=quoted,
                  ranked=ranked(claimed), reasons=reasons, **common)


def promote_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    markets: Mapping | None = None,
) -> list[Promotion]:
    """Promote every position the run touched, one Promotion per position.

    Keyed on `opportunity_attempts`, never `opportunities.run_id` — the
    position rollup freezes run_id at first sighting, so a query keyed on
    it silently misses every re-proposed position (the standing hazard,
    bitten three times by 2026-08-30). `markets`, when given, maps ticker
    -> current quote.
    """
    ids = [
        r["opportunity_id"] for r in conn.execute(
            "SELECT DISTINCT opportunity_id FROM opportunity_attempts"
            " WHERE run_id = ? ORDER BY opportunity_id",
            (run_id,),
        )
    ]
    reports: dict[tuple[str, int], dict] = {}
    results = []
    for oid in ids:
        row = ledger.get_opportunity(conn, oid)
        key = (row["theory_id"], row["theory_version"])
        if key not in reports:
            reports[key] = slices.segment_report(
                conn, key[0], key[1], pool="chain"
            )
        market = markets.get(row["kalshi_ticker"]) if markets else None
        results.append(
            promote(conn, oid, market=market, report=reports[key])
        )
    return results


def orphaned_evidence(
    conn: sqlite3.Connection,
    theory_id: str,
    current_version: int | None = None,
) -> list[dict]:
    """Ready slices whose evidence has no bet path at the current version.

    A slice READY out of sample at a prior theory version, while the
    current version's own segment is not ready and no chain pools the
    two, is a demonstrated edge the current procedure cannot reach.

    **The fix is to relink the chain, not to adopt the rule.** An orphan
    is a versioning fact -- almost always a bump recorded `breaking`
    under the pre-2026-08-31 default, correctable with
    `theories.reclassify_bump`, after which the sub-theory is ready at
    the current version and routes its own bets unchanged.
    insider_judgment's `strong-moderate-no` was the worked example and is
    the worked resolution: reclassifying v2-v4 to `continues` relinked
    v1-v4 and the orphan disappeared without touching the screen.
    Absorbing a slice into the parent buys no different bet and costs the
    complement and the out-of-sample split (CLAUDE.md, "A sub-theory is
    maintained, not absorbed"). Every entry is an
    escalation for the report's "For your ruling" section — adoption is a
    version-bump decision, never a session's.
    """
    trow = theories.get(conn, theory_id)
    if trow is None:
        raise ValueError(f"unknown theory {theory_id!r}")
    if current_version is None:
        current_version = trow["version"]
    current = slices.segment_report(
        conn, theory_id, current_version, pool="chain"
    )
    ready_now = {
        s["slug"] for s in current["slices"]
        if s["ready"] and s["status"] == "registered"
    }
    pooled = set(current.get("chain_versions", [current_version]))
    versions = [
        r["theory_version"] for r in conn.execute(
            "SELECT DISTINCT theory_version FROM opportunities"
            " WHERE theory_id = ? ORDER BY theory_version DESC",
            (theory_id,),
        ) if r["theory_version"] not in pooled
        and r["theory_version"] != current_version
    ]
    orphans: list[dict] = []
    seen: set[str] = set()
    for version in versions:
        # Deliberately per-version: this scan is looking at versions
        # OUTSIDE the current chain, so pooling would fold them back
        # into the pool whose readiness we just measured.
        report = slices.segment_report(
            conn, theory_id, version, pool="version")
        for s in report["slices"]:
            if (s["status"] == "registered" and s["ready"]
                    and s["slug"] not in ready_now
                    and s["slug"] not in seen):
                seen.add(s["slug"])
                orphans.append({
                    "theory_id": theory_id,
                    "slug": s["slug"],
                    "ready_at_version": version,
                    "current_version": current_version,
                    "hypothesis": s["hypothesis"],
                    "oos": s["oos"],
                })
    return orphans
