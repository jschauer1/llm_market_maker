"""The session's orientation surface, rendered from the DB (spec 3.2).

Replaces "read the last ~30 lines of RESEARCH_LOG.md": the log is the
audit trail, this is the state. Each panel names its table and renders a
one-line stub when that table has not shipped yet -- the shape is stable
from day one, panels light up as phases land. Text output on purpose:
this is the one CLI surface built for human orientation, not parsing.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from tools import theories
from tools.db import utcnow, _table_exists

_STUB = "  (not yet tracked — table {table} has not shipped)"


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))


def _age_days(stamp: str | None, now: str) -> str:
    if not stamp:
        return "never"
    days = max(0.0, (_parse(now) - _parse(stamp)).total_seconds() / 86400.0)
    return f"{days:.1f}d ago ({stamp})"


def _one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _theories_panel(conn) -> list[str]:
    lines = []
    for t in theories.list_theories(conn):
        settled = _one(conn, """
            SELECT COUNT(DISTINCT o.kalshi_ticker) FROM opportunities o
              JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
             WHERE o.theory_id = ? AND o.theory_version = ?
        """, (t["id"], t["version"]))
        rows = _one(conn,
                    "SELECT COUNT(*) FROM opportunities"
                    " WHERE theory_id = ? AND theory_version = ?",
                    (t["id"], t["version"]))
        chain = "chain n/a"
        if _table_exists(conn, "theory_versions"):
            chain = "chain ready"          # phase 6 replaces this with chain n
        lines.append(
            f"  {t['id']:<22} {t['status']:<13} v{t['version']}"
            f"  rows {rows}  settled {settled}  [{chain}]"
        )
    return lines or ["  (no theories registered)"]


def _standing_panel(conn) -> list[str]:
    lines = []
    for t in theories.list_pending_retirement(conn):
        lines.append(f"  pending retirement: {t['id']} — {t['retirement_rationale']}")
    if _table_exists(conn, "rulings"):
        for r in conn.execute(
            "SELECT ruled_at, authority, subject, ruling FROM rulings"
            " WHERE status = 'binding' ORDER BY ruled_at"
        ):
            lines.append(
                f"  ruling [{r['subject']}] ({r['authority']},"
                f" {str(r['ruled_at'])[:10]}): {r['ruling'][:100]}"
            )
    else:
        lines.append(_STUB.format(table="rulings"))
    parked = _one(conn, "SELECT COUNT(*) FROM ideas WHERE status = 'parked'")
    paused = _one(conn, "SELECT COUNT(*) FROM theories WHERE status = 'paused'")
    lines.append(f"  blocked: {parked or 0} parked idea(s), {paused or 0} paused theory(ies)")
    return lines


def _evidence_panel(conn) -> list[str]:
    lines = []
    for t in theories.list_theories(conn, running_only=True):
        row = conn.execute(
            """
            SELECT calibration_edge_net, n, n_clusters FROM scores
             WHERE theory_id = ? AND theory_version = ?
               AND run_mode = 'live' AND disposition = 'all'
             ORDER BY computed_at DESC LIMIT 1
            """,
            (t["id"], t["version"]),
        ).fetchone()
        tier = _one(conn,
                    "SELECT tier FROM backtest_runs WHERE theory_id = ?"
                    " ORDER BY created_at DESC LIMIT 1", (t["id"],))
        if row is None:
            lines.append(f"  {t['id']:<22} no live score at v{t['version']}"
                         f"  [best backtest tier {tier or '—'}]")
        else:
            lines.append(
                f"  {t['id']:<22} edge_net {row['calibration_edge_net']}"
                f"  n {row['n']}  clusters {row['n_clusters']}"
                f"  [tier {tier or '—'}]"
            )
    return lines or ["  (no running theories)"]


def _windows_panel(conn) -> list[str]:
    if not _table_exists(conn, "data_windows"):
        return [_STUB.format(table="data_windows")]
    return [
        f"  {w['slug']:<40} questions {q}"
        for w in conn.execute("SELECT slug FROM data_windows ORDER BY slug")
        for q in [_one(conn,
                       "SELECT COUNT(*) FROM hypothesis_tests"
                       " WHERE window_slug = ?", (w["slug"],))]
    ] or ["  (no windows registered)"]


def _queue_panel(conn) -> list[str]:
    rows = conn.execute(
        """
        SELECT o.id, o.theory_id, o.kalshi_ticker, o.first_seen_at
          FROM opportunities o
          LEFT JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
         WHERE o.disposition = 'endorsed' AND o.user_action = 'untouched'
           AND s.kalshi_ticker IS NULL
         ORDER BY o.first_seen_at DESC LIMIT 10
        """
    ).fetchall()
    total = _one(conn, """
        SELECT COUNT(*) FROM opportunities o
          LEFT JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
         WHERE o.disposition = 'endorsed' AND o.user_action = 'untouched'
           AND s.kalshi_ticker IS NULL
    """)
    lines = [f"  {r['id']:>6}  {r['theory_id']:<22} {r['kalshi_ticker']}"
             f"  since {str(r['first_seen_at'])[:10]}" for r in rows]
    lines.append(f"  ({total or 0} endorsed, untouched, unsettled in total)")
    return lines


def _freshness_panel(conn, now: str) -> list[str]:
    board = _one(conn, "SELECT MAX(captured_at) FROM market_snapshots"
                       " WHERE platform = 'kalshi'")
    settle = _one(conn, "SELECT MAX(computed_at) FROM scores")
    taken = _one(conn, "SELECT MAX(recorded_at) FROM opportunity_fills") \
        if _table_exists(conn, "opportunity_fills") else None
    return [
        f"  last board pull:  {_age_days(board, now)}",
        f"  last settle run:  {_age_days(settle, now)}",
        f"  last mark-taken:  {_age_days(taken, now)}",
        "  last bets render: (not yet tracked — raise-lane spec)",
    ]


def render_state(conn: sqlite3.Connection, now: str | None = None) -> str:
    now = now or utcnow()
    sections = (
        ("THEORIES", _theories_panel(conn)),
        ("STANDING", _standing_panel(conn)),
        ("EVIDENCE", _evidence_panel(conn)),
        ("WINDOWS", _windows_panel(conn)),
        ("QUEUE", _queue_panel(conn)),
        ("FRESHNESS", _freshness_panel(conn, now)),
    )
    out = [f"# state @ {now}"]
    for name, lines in sections:
        out.append(f"\n{name}")
        out.extend(lines)
    return "\n".join(out) + "\n"


def write_state(conn: sqlite3.Connection, now: str | None = None) -> Path:
    path = Path("STATE.md")
    path.write_text(render_state(conn, now=now), encoding="utf-8")
    return path
