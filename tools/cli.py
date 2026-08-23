"""Unified command line over the data layer.

Skills invoke these commands rather than writing inline Python, so the
mechanical half of every workflow is code that has tests. Everything prints
JSON to stdout so a skill can parse the result reliably.

Run `python -m tools.cli --help` for the command list.
"""

from __future__ import annotations

import argparse
import json
import sys

from tools import db, ideas, ledger, rank, score, theories


def _emit(payload) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _rows(rows) -> list[dict]:
    return [dict(row) for row in rows]


def _connect(args):
    conn = db.connect(args.db) if args.db else db.connect()
    db.init_db(conn)
    return conn


def _cmd_init(args) -> int:
    conn = _connect(args)
    conn.close()
    _emit({"ok": True, "db": str(args.db or db.DEFAULT_DB_PATH)})
    return 0


def _cmd_theories(args) -> int:
    conn = _connect(args)
    try:
        if args.action == "list":
            _emit(_rows(theories.list_theories(conn, status=args.status)))
        elif args.action == "register":
            theories.register(conn, args.id, args.name, args.path)
            _emit(dict(theories.get(conn, args.id)))
        elif args.action == "status":
            theories.set_status(conn, args.id, args.value)
            _emit(dict(theories.get(conn, args.id)))
        elif args.action == "bump":
            version = theories.bump_version(conn, args.id)
            _emit({"id": args.id, "version": version})
    finally:
        conn.close()
    return 0


def _cmd_ideas(args) -> int:
    conn = _connect(args)
    try:
        if args.action == "search":
            _emit(_rows(ideas.search(conn, args.keyword)))
        elif args.action == "record":
            ideas.record(
                conn, args.slug, args.title,
                description=args.description or "", source=args.source,
            )
            _emit(dict(ideas.get(conn, args.slug)))
        elif args.action == "status":
            ideas.update_status(
                conn, args.slug, args.value,
                what_was_tried=args.what_was_tried,
                outcome=args.outcome,
                revisit_angle=args.revisit_angle,
                revisit_after=args.revisit_after,
                theory_id=args.theory_id,
            )
            _emit(dict(ideas.get(conn, args.slug)))
        elif args.action == "revisitable":
            _emit(_rows(ideas.list_revisitable(conn)))
    finally:
        conn.close()
    return 0


def _cmd_opportunities(args) -> int:
    conn = _connect(args)
    try:
        _emit(
            _rows(
                ledger.list_opportunities(
                    conn,
                    theory_id=args.theory,
                    run_mode=args.run_mode,
                    disposition=args.disposition,
                )
            )
        )
    finally:
        conn.close()
    return 0


def _cmd_score(args) -> int:
    conn = _connect(args)
    try:
        if args.action == "report":
            theory = theories.get(conn, args.theory_id)
            version = args.version or (theory["version"] if theory else 1)
            _emit(
                {
                    disposition: score.compute_score(
                        conn, args.theory_id, version, args.run_mode,
                        disposition,
                    )
                    for disposition in ("all", "screened", "endorsed",
                                        "rejected")
                }
            )
        elif args.action == "settle-one":
            score.record_settlement(
                conn, args.ticker, args.result, resolved_at=args.resolved_at
            )
            _emit({"ok": True, "ticker": args.ticker, "result": args.result})
    finally:
        conn.close()
    return 0


def _cmd_rank(args) -> int:
    credibility = rank.credibility(
        args.n, args.calibration_edge_net, args.mean_claimed_edge
    )
    _emit(
        {
            "edge_pts_net": args.edge,
            "n": args.n,
            "credibility": credibility,
            "realization": rank.realization(
                args.calibration_edge_net, args.mean_claimed_edge
            ),
            "ranked_edge": args.edge * credibility,
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tools.cli")
    parser.add_argument("--db", default=None, help="path to the database")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the database").set_defaults(
        func=_cmd_init
    )

    p = sub.add_parser("theories", help="theory registry")
    p.set_defaults(func=_cmd_theories)
    ts = p.add_subparsers(dest="action", required=True)
    listing = ts.add_parser("list")
    listing.add_argument("--status", default=None)
    reg = ts.add_parser("register")
    reg.add_argument("id")
    reg.add_argument("name")
    reg.add_argument("path")
    st = ts.add_parser("status")
    st.add_argument("id")
    st.add_argument("value", choices=theories.VALID_STATUSES)
    bump = ts.add_parser("bump")
    bump.add_argument("id")

    p = sub.add_parser("ideas", help="research memory")
    p.set_defaults(func=_cmd_ideas)
    isub = p.add_subparsers(dest="action", required=True)
    search = isub.add_parser("search")
    search.add_argument("keyword")
    rec = isub.add_parser("record")
    rec.add_argument("slug")
    rec.add_argument("title")
    rec.add_argument("--description", default="")
    rec.add_argument("--source", default="claude")
    ist = isub.add_parser("status")
    ist.add_argument("slug")
    ist.add_argument("value", choices=ideas.VALID_STATUSES)
    ist.add_argument("--what-was-tried", dest="what_was_tried", default=None)
    ist.add_argument("--outcome", default=None)
    ist.add_argument("--revisit-angle", dest="revisit_angle", default=None)
    ist.add_argument("--revisit-after", dest="revisit_after", default=None)
    ist.add_argument("--theory-id", dest="theory_id", default=None)
    isub.add_parser("revisitable")

    p = sub.add_parser("opportunities", help="recorded opportunities")
    p.set_defaults(func=_cmd_opportunities)
    osub = p.add_subparsers(dest="action", required=True)
    olist = osub.add_parser("list")
    olist.add_argument("--theory", default=None)
    olist.add_argument("--run-mode", dest="run_mode", default=None)
    olist.add_argument("--disposition", default=None)

    p = sub.add_parser("score", help="calibration and settlement")
    p.set_defaults(func=_cmd_score)
    ssub = p.add_subparsers(dest="action", required=True)
    report = ssub.add_parser("report")
    report.add_argument("theory_id")
    report.add_argument("--version", type=int, default=None)
    report.add_argument("--run-mode", dest="run_mode", default="live")
    settle = ssub.add_parser("settle-one")
    settle.add_argument("ticker")
    settle.add_argument("result")
    settle.add_argument("--resolved-at", dest="resolved_at", default=None)

    p = sub.add_parser("rank", help="credibility-weighted edge")
    p.set_defaults(func=_cmd_rank)
    p.add_argument("--edge", type=float, required=True)
    p.add_argument("--n", type=int, required=True)
    p.add_argument(
        "--calibration-edge-net", dest="calibration_edge_net",
        type=float, default=None,
        help=(
            "The theory's measured calibration edge, NET of fees (the "
            "calibration_edge_net key from `score report`) — not the gross "
            "calibration_edge. The rest of this system compares net "
            "figures against net claims; passing the gross edge here "
            "overstates realization and inflates the credibility weight."
        ),
    )
    p.add_argument("--mean-claimed-edge", dest="mean_claimed_edge",
                   type=float, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
