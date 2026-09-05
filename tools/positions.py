"""Shared settlement and supersession facts for recorded positions."""

from __future__ import annotations

import re
import sqlite3


def _alias(alias: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", alias):
        raise ValueError("position table alias must be a SQL identifier")
    return alias


def settled_sql(alias: str = "o") -> str:
    """SQL predicate: a single settles by ticker, a basket by all its legs.

    A basket missing recorded legs remains visible until at least leg_count
    legs have settlements. Callers keep their own other selection filters.
    """
    o = _alias(alias)
    return f"""CASE WHEN {o}.position_kind = 'basket' THEN
        (SELECT COUNT(*) FROM opportunity_legs position_leg
          JOIN settlements leg_settlement
            ON leg_settlement.kalshi_ticker = position_leg.kalshi_ticker
         WHERE position_leg.opportunity_id = {o}.id) >= {o}.leg_count
        ELSE EXISTS (SELECT 1 FROM settlements position_settlement
                     WHERE position_settlement.kalshi_ticker = {o}.kalshi_ticker)
        END"""


def superseder_id_sql(alias: str = "o") -> str:
    """Scalar SQL: current-version successor for the same position, or NULL.

    Only older versions can be superseded. Mode, experiment lane and side
    are identity: another position never replaces this one's decision.
    """
    o = _alias(alias)
    return f"""(SELECT successor.id
        FROM opportunities successor
        JOIN theories current_theory ON current_theory.id = successor.theory_id
        WHERE successor.theory_id = {o}.theory_id
          AND {o}.theory_version < current_theory.version
          AND successor.theory_version = current_theory.version
          AND successor.run_mode = {o}.run_mode
          AND successor.lane = {o}.lane
          AND successor.kalshi_ticker = {o}.kalshi_ticker
          AND successor.outcome = {o}.outcome
          AND successor.id != {o}.id
        ORDER BY successor.id DESC LIMIT 1)"""


def is_settled(conn: sqlite3.Connection, opportunity_id: int) -> bool:
    row = conn.execute(
        f"SELECT {settled_sql()} FROM opportunities o WHERE o.id = ?",
        (opportunity_id,),
    ).fetchone()
    if row is None:
        raise KeyError(opportunity_id)
    return bool(row[0])


def superseded_by(conn: sqlite3.Connection, opportunity_id: int) -> sqlite3.Row | None:
    return conn.execute(
        f"""SELECT replacement.* FROM opportunities o
            JOIN opportunities replacement ON replacement.id = {superseder_id_sql()}
            WHERE o.id = ?""",
        (opportunity_id,),
    ).fetchone()
