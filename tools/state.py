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


def _evidence_versions(conn, theory_id: str, version: int) -> list[int]:
    """The versions whose evidence counts toward `version`, ascending.

    Every panel below counts over this rather than over the current
    version alone. Until the 2026-08-31 ruling they counted at
    `theory_version = <current>` exactly, which was right while
    `breaking` was the default bump kind: a bump severed, so a theory's
    record genuinely did restart. `continues` is the default now, a bump
    no longer discards evidence, and those queries kept running against
    the old vocabulary -- reporting a whole record as zero the moment
    anyone bumped.

    Measured on the real DB the day two `continues` bumps landed:
    `calibration_harvest` (chain [1,2,3], 14,473 + 14,436 ledger rows) and
    `insider_judgment` (chain [1,2,3,4,5], 128 + 4,084 + 63) both rendered
    `rows 0`, and `insider_judgment`'s `strong-moderate-no` sub-theory --
    the best-evidenced result in the repo -- vanished from EVIDENCE.

    `carry_chain` stops at an explicit `breaking` row, so a severed
    predecessor is still correctly excluded; this widens what pools, it
    does not pool everything. Falls back to the bare version on a DB
    predating `theory_versions`, matching every other panel's stub
    behaviour.
    """
    if not _table_exists(conn, "theory_versions"):
        return [version]
    return theories.carry_chain(conn, theory_id, version)


def _theories_panel(conn) -> list[str]:
    lines = []
    for t in theories.list_theories(conn):
        versions = _evidence_versions(conn, t["id"], t["version"])
        marks = ",".join("?" * len(versions))
        settled = _one(conn, f"""
            SELECT COUNT(DISTINCT o.kalshi_ticker) FROM opportunities o
              JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
             WHERE o.theory_id = ? AND o.theory_version IN ({marks})
        """, (t["id"], *versions))
        rows = _one(conn,
                    "SELECT COUNT(*) FROM opportunities"
                    f" WHERE theory_id = ? AND theory_version IN ({marks})",
                    (t["id"], *versions))
        chain = "chain n/a"
        if _table_exists(conn, "theory_versions"):
            chain = f"chain {len(versions)}"
        lines.append(
            f"  {t['id']:<22} {t['status']:<13} v{t['version']}"
            f"  rows {rows}  settled {settled}  [{chain}]"
        )
    return lines or ["  (no theories registered)"]


def _truncate(text: str, limit: int = 100) -> str:
    """The first `limit` chars, with a trailing ellipsis only if cut short.

    A ruling shorter than the limit must render exactly as written -- the
    ellipsis is a promise that text was dropped, and a false promise sends
    the reader to `rulings list` to find nothing more than what they
    already saw.
    """
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


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
                f" {str(r['ruled_at'])[:10]}): {_truncate(r['ruling'])}"
            )
    else:
        lines.append(_STUB.format(table="rulings"))
    parked = _one(conn, "SELECT COUNT(*) FROM ideas WHERE status = 'parked'")
    paused = _one(conn, "SELECT COUNT(*) FROM theories WHERE status = 'paused'")
    lines.append(f"  blocked: {parked or 0} parked idea(s), {paused or 0} paused theory(ies)")
    lines.append(
        "  full text: python -m tools.cli rulings list --status binding"
    )
    return lines


def _evidence_panel(conn) -> list[str]:
    lines = []
    # Zero rows in `scores` means score-theories has never run at all --
    # that is a different fact from "this particular theory/version has no
    # live score yet" (which can be true even after scoring has run many
    # times for other theories), and conflating the two under "no live
    # score at vN" reads as a per-theory gap when the real problem is that
    # nobody has run score-theories this session.
    scores_written = _one(conn, "SELECT COUNT(*) FROM scores")
    for t in theories.list_theories(conn, running_only=True):
        row = None
        if scores_written:
            # `segment = 'aggregate'` is load-bearing, not decoration: a
            # sub-theory's score lives in this same table, and without the
            # filter a subset written a second later is served as the
            # theory's own record -- a strong slice would read as a strong
            # theory, which is the precise confusion sub-theory scoring
            # exists to prevent. Pre-segment rows default to 'aggregate',
            # so this never hides a legacy score.
            # Newest score anywhere in the evidence chain, current
            # version first. A `continues` bump keeps the predecessor's
            # score standing -- reporting "no live score" there would
            # hide a record the ruling says still counts -- but the
            # reader is told which version produced the number, because
            # "the evidence pools" and "this was measured at the
            # procedure now running" are different claims.
            versions = _evidence_versions(conn, t["id"], t["version"])
            marks = ",".join("?" * len(versions))
            row = conn.execute(
                f"""
                SELECT calibration_edge_net, n, n_clusters, n_backtest,
                       pooled_versions, theory_version FROM scores
                 WHERE theory_id = ? AND theory_version IN ({marks})
                   AND disposition = 'all'
                   AND segment = 'aggregate'
                 ORDER BY theory_version = ? DESC, computed_at DESC
                 LIMIT 1
                """,
                (t["id"], *versions, t["version"]),
            ).fetchone()
        tier = _one(conn,
                    "SELECT tier FROM backtest_runs WHERE theory_id = ?"
                    " ORDER BY created_at DESC LIMIT 1", (t["id"],))
        if not scores_written:
            lines.append(
                f"  {t['id']:<22} scores never written — run score-theories"
                f"  [best backtest tier {tier or '—'}]"
            )
        elif row is None:
            lines.append(f"  {t['id']:<22} no live score at v{t['version']}"
                         f"  [best backtest tier {tier or '—'}]")
        else:
            at = ("" if row["theory_version"] == t["version"]
                  else f"  [scored at v{row['theory_version']}]")
            lines.append(
                f"  {t['id']:<22} edge_net {row['calibration_edge_net']}"
                f"  n {row['n']}{_backtest_note(row)}"
                f"  clusters {row['n_clusters']}"
                f"{_pooled_note(row)}{at}  [tier {tier or '—'}]"
            )
        lines.extend(_sub_theory_lines(conn, t))
    return lines or ["  (no running theories)"]


def _sub_theory_lines(conn, t) -> list[str]:
    """One line per sub-theory under its parent.

    A sub-theory's record is its own — it can be strong while the parent
    it sits inside is flat, which is exactly the case a session must not
    miss. Showing only the parent is how a proven subset goes unbet:
    `insider_judgment`'s strong/moderate-NO slice was the repo's
    best-evidenced result while its parent read as breakeven.
    """
    if not _column_exists(conn, "scores", "segment"):
        return []
    # Over the evidence chain, not the current version: a `continues`
    # bump made `insider_judgment`'s `strong-moderate-no` disappear from
    # this panel, and that slice is the best-evidenced result in the repo.
    # A sub-theory is versioned with its parent, so it carries exactly
    # what the parent carries.
    versions = _evidence_versions(conn, t["id"], t["version"])
    marks = ",".join("?" * len(versions))
    rows = conn.execute(
        f"""
        -- exactly ONE min/max aggregate, deliberately: SQLite only
        -- guarantees the bare columns come from the matching row when
        -- there is a single min()/max() in the select list. A second one
        -- (MAX(theory_version), say) silently forfeits that and can pair
        -- one row's edge with another row's timestamp.
        SELECT segment, calibration_edge_net, n, n_clusters, n_backtest,
               MAX(computed_at) AS computed_at
          FROM scores
         WHERE theory_id = ? AND theory_version IN ({marks})
           AND disposition = 'all'
           AND segment != 'aggregate'
         GROUP BY segment
         ORDER BY segment
        """,
        (t["id"], *versions),
    ).fetchall()
    out = []
    for r in rows:
        label = r["segment"]
        if label.startswith("slice:"):
            label = "  sub: " + label[len("slice:"):]
        else:
            label = "  sub: " + label
        out.append(
            f"    {label:<28} edge_net {r['calibration_edge_net']}"
            f"  n {r['n']}{_backtest_note(r)}"
            f"  clusters {r['n_clusters']}"
        )
    return out


def _backtest_note(row) -> str:
    """How much of a record came from replay, shown beside n.

    Disclosure, never a discount: a backtested edge counts in full (user
    ruling 2026-08-31). It is here because backtesting is often the
    reason a theory has any evidence at all, and a single total hides
    that -- a session should be able to see which theories are earning
    their record by being replayed, and go do the same for the others.
    """
    try:
        n_backtest = row["n_backtest"]
    except (IndexError, KeyError):
        return ""
    return f" ({n_backtest} backtested)" if n_backtest else ""


def _pooled_note(row) -> str:
    """Which versions a score pooled, shown only when it spans more than
    one -- a pooled number and a single-version one are different claims."""
    try:
        pooled = row["pooled_versions"]
    except (IndexError, KeyError):
        return ""
    if not pooled or "," not in str(pooled):
        return ""
    return f"  [v{pooled.replace(',', '+v')}]"


def _column_exists(conn, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        return False
    return any(
        row[1] == column
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    )


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
    # last_seen_at, not captured_at: an unchanged pull extends a row's
    # interval without inserting (spec 5.2 phase 2), so captured_at alone
    # can be stale even though the board was just re-pulled. COALESCE
    # covers a row written before last_seen_at existed and not yet
    # touched by init_db's backfill.
    board = _one(conn, "SELECT MAX(COALESCE(last_seen_at, captured_at))"
                       " FROM market_snapshots WHERE platform = 'kalshi'")
    settle = _one(conn, "SELECT MAX(computed_at) FROM scores")
    taken = _one(conn, "SELECT MAX(recorded_at) FROM opportunity_fills") \
        if _table_exists(conn, "opportunity_fills") else None
    lines = [
        f"  last board pull:  {_age_days(board, now)}",
        f"  last settle run:  {_age_days(settle, now)}",
        f"  last mark-taken:  {_age_days(taken, now)}",
        "  last bets render: (not yet tracked — raise-lane spec)",
    ]
    # The first thing a session needs to know: run the floor, or research?
    # It reads from a row rather than from a peer's message, so a session
    # that received no message at all still gets the right answer.
    if _table_exists(conn, "floor_runs"):
        from tools import floor

        st = floor.status(conn, now=now)
        flag = "DUE — claim it" if st["due"] else "not due"
        lines.append(f"  floor duty:       {flag} — {st['reason']}")
        if st["last_completed_by"]:
            lines.append(
                f"    last floor:     {st['last_completed_by']} at "
                f"{st['last_completed_at']}"
                + (f" -> {st['last_report_path']}"
                   if st["last_report_path"] else "")
            )
    else:
        lines.append("  floor duty:       (not yet tracked — table floor_runs)")

    # Long-running collections. A collector outlives the session that
    # starts it, so a stall is invisible unless something reports it --
    # the series-bias backfill sat dead for 5.7 hours twice before a
    # session found it by hand, against data that ages out upstream.
    # Wrapped because this reads other studies' SQLite files, and
    # orientation must survive any of them being missing, odd or locked.
    lines.append("  collections:")
    try:
        from tools import collectors

        rendered = collectors.render(collectors.REGISTRY, now)
    except Exception as exc:  # noqa: BLE001 - orientation must not fail
        rendered = [f"    (unreadable: {exc})"]
    lines.extend(rendered or ["    (none registered)"])
    return lines


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


def write_state(
    conn: sqlite3.Connection, now: str | None = None, text: str | None = None
) -> Path:
    """Write STATE.md. Pass `text` to reuse an already-rendered string.

    Without it, a caller that also prints `render_state(conn)` to the
    terminal would trigger a second render here -- and since `now`
    defaults to the real clock, the printed text and the file would
    disagree, each stamped with a different `now`. `tools/cli.py`'s
    `state --write` renders once and passes the result through for
    exactly this reason.
    """
    path = Path("STATE.md")
    path.write_text(text if text is not None else render_state(conn, now=now),
                     encoding="utf-8")
    return path
