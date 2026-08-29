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

from tools import db, ideas, ledger, provenance, rank, score, slices, theories


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


def _cmd_migrate_positions(args) -> int:
    # Deliberately not routed through `_connect`: that helper calls
    # `init_db` (tools/cli.py:29), and `init_db` refuses a legacy database
    # on purpose. This command is the thing that fixes it.
    conn = db.connect(args.db) if args.db else db.connect()
    try:
        _emit(db.migrate_positions(conn, dry_run=args.dry_run))
    finally:
        conn.close()
    return 0


def _cmd_theories(args) -> int:
    conn = _connect(args)
    try:
        if args.action == "list":
            _emit(
                _rows(
                    theories.list_theories(
                        conn, status=args.status, running_only=args.running
                    )
                )
            )
        elif args.action == "register":
            theories.register(conn, args.id, args.name, args.path)
            _emit(dict(theories.get(conn, args.id)))
        elif args.action == "status":
            theories.set_status(
                conn, args.id, args.value, authorized_by=args.authorized_by
            )
            _emit(dict(theories.get(conn, args.id)))
        elif args.action == "propose-retirement":
            theories.propose_retirement(conn, args.id, args.rationale)
            _emit(dict(theories.get(conn, args.id)))
        elif args.action == "withdraw-retirement":
            theories.withdraw_retirement(conn, args.id)
            _emit(dict(theories.get(conn, args.id)))
        elif args.action == "pending-retirement":
            _emit(_rows(theories.list_pending_retirement(conn)))
        elif args.action == "bump":
            version = theories.bump_version(conn, args.id)
            _emit({"id": args.id, "version": version})
    finally:
        conn.close()
    return 0


def _cmd_provenance(args) -> int:
    conn = _connect(args)
    try:
        if args.action == "list":
            _emit(_rows(provenance.list_judgment_runs(
                conn, theory_id=args.theory, run_id=args.run)))
        elif args.action == "record":
            provenance.record_judgment_run(
                conn, run_id=args.run, theory_id=args.theory,
                theory_version=args.version, stage=args.stage,
                model=args.model, prompt_path=args.prompt_path,
                effort=args.effort, web_search=args.web_search,
                n_items=args.n_items, notes=args.notes,
            )
            _emit(_rows(provenance.list_judgment_runs(
                conn, theory_id=args.theory, run_id=args.run)))
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
        if args.action == "list":
            rows = _rows(
                ledger.list_opportunities(
                    conn,
                    theory_id=args.theory,
                    run_mode=args.run_mode,
                    disposition=args.disposition,
                )
            )
            if args.with_legs:
                for row in rows:
                    row["legs"] = [
                        dict(leg) for leg in ledger.get_legs(conn, row["id"])
                    ]
            _emit(rows)
        elif args.action == "mark-taken":
            ledger.mark_user_action(
                conn, args.id, args.value, size=args.size,
                reason=args.reason, theory_id=args.mark_theory,
                price=args.price,
            )
            _emit(dict(ledger.get_opportunity(conn, args.id)))
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
                    "theory_version": version,
                    **{
                        disposition: score.compute_score(
                            conn, args.theory_id, version, args.run_mode,
                            disposition, run_id=args.run_id,
                        )
                        for disposition in ("all", "screened", "endorsed",
                                            "rejected")
                    },
                    # Reported alongside, never instead: `all` above counts
                    # rows, and rows that settled the same day are one draw
                    # wearing many rows' clothes. `n_days` is the sample
                    # size a reader should believe.
                    "settlement_days": {
                        disposition: score.settlement_day_clusters(
                            conn, args.theory_id, version, args.run_mode,
                            disposition, run_id=args.run_id,
                        )
                        for disposition in ("all", "screened", "endorsed",
                                            "rejected")
                    },
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


def _cmd_backtest(args) -> int:
    conn = _connect(args)
    try:
        if args.action == "record":
            score.record_backtest_run(
                conn, args.run_id, args.theory_id, args.theory_version,
                as_of_start=args.as_of_start, as_of_end=args.as_of_end,
                tier=args.tier, uses_llm_judgment=args.uses_llm_judgment,
                model_cutoff=args.model_cutoff, notes=args.notes,
            )
            row = conn.execute(
                "SELECT * FROM backtest_runs WHERE run_id = ?",
                (args.run_id,),
            ).fetchone()
            _emit(dict(row))
    finally:
        conn.close()
    return 0


def _cmd_slices(args) -> int:
    conn = _connect(args)
    try:
        if args.action == "register":
            slices.register_slice(
                conn, args.theory_id, args.slug,
                predicate=json.loads(args.predicate),
                hypothesis=args.hypothesis, origin=args.origin,
                oos_run_ids=args.oos_run or (),
                priority=args.priority,
                registered_at=args.registered_at,
            )
            _emit(dict(slices.get_slice(conn, args.theory_id, args.slug)))
        elif args.action == "list":
            _emit(_rows(slices.list_slices(conn, theory_id=args.theory)))
        elif args.action == "report":
            _emit(
                slices.segment_report(
                    conn, args.theory_id, args.version,
                    disposition=args.disposition,
                    run_modes=tuple(args.run_modes.split(",")),
                )
            )
        elif args.action == "match":
            row = ledger.get_opportunity(conn, args.opportunity_id)
            if row is None:
                raise SystemExit(f"no opportunity {args.opportunity_id}")
            _emit(
                slices.ranking_segment(
                    conn, row, disposition=args.disposition
                )
            )
        elif args.action == "retire":
            slices.retire_slice(
                conn, args.theory_id, args.slug, reason=args.reason
            )
            _emit(dict(slices.get_slice(conn, args.theory_id, args.slug)))
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

    mp = sub.add_parser(
        "migrate-positions",
        help="collapse run-scoped opportunity rows into positions",
    )
    mp.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="report what would change without writing",
    )
    mp.set_defaults(func=_cmd_migrate_positions)

    p = sub.add_parser("theories", help="theory registry")
    p.set_defaults(func=_cmd_theories)
    ts = p.add_subparsers(dest="action", required=True)
    listing = ts.add_parser("list")
    listing_filter = listing.add_mutually_exclusive_group()
    listing_filter.add_argument("--status", default=None)
    listing_filter.add_argument(
        "--running",
        action="store_true",
        help=(
            "only theories that run: testing, active, under_review "
            "(under_review keeps running while it is diagnosed)"
        ),
    )
    reg = ts.add_parser("register")
    reg.add_argument("id")
    reg.add_argument("name")
    reg.add_argument("path")
    st = ts.add_parser("status")
    st.add_argument("id")
    st.add_argument("value", choices=theories.VALID_STATUSES)
    st.add_argument(
        "--authorized-by",
        dest="authorized_by",
        default="claude",
        choices=("claude", "user"),
        help=(
            "who is making this call. 'retired' requires 'user' -- only the "
            "user declares a theory dead"
        ),
    )
    pr = ts.add_parser(
        "propose-retirement",
        help="suggest to the user that a theory is dead (does not retire it)",
    )
    pr.add_argument("id")
    pr.add_argument(
        "--rationale", required=True,
        help="what you diagnosed and what you ruled out",
    )
    wr = ts.add_parser(
        "withdraw-retirement", help="clear a standing retirement proposal"
    )
    wr.add_argument("id")
    ts.add_parser(
        "pending-retirement", help="retirement proposals awaiting the user"
    )
    bump = ts.add_parser("bump")
    bump.add_argument("id")

    p = sub.add_parser(
        "provenance",
        help="what model and prompt judged -- required for LLM theories")
    p.set_defaults(func=_cmd_provenance)
    pv = p.add_subparsers(dest="action", required=True)
    pvl = pv.add_parser("list")
    pvl.add_argument("--theory", default=None)
    pvl.add_argument("--run", default=None)
    pvr = pv.add_parser("record")
    pvr.add_argument("--theory", required=True)
    pvr.add_argument("--version", type=int, required=True)
    pvr.add_argument("--run", required=True)
    pvr.add_argument("--stage", required=True,
                     choices=provenance.VALID_STAGES)
    pvr.add_argument("--model", required=True,
                     help="exact model id that judged, e.g. claude-opus-5")
    pvr.add_argument("--prompt-path", dest="prompt_path", required=True,
                     help="repo path to the prompt file, so a change is "
                          "reviewable in git diff")
    pvr.add_argument("--effort", default=None)
    pvr.add_argument("--web-search", dest="web_search", type=int, default=None,
                     choices=(0, 1))
    pvr.add_argument("--n-items", dest="n_items", type=int, default=None)
    pvr.add_argument("--notes", default=None)

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
    olist.add_argument(
        "--with-legs", dest="with_legs", action="store_true",
        help="include each position's legs (empty for single positions)",
    )
    mark = osub.add_parser(
        "mark-taken", help="record what the user actually did with a bet"
    )
    mark.add_argument("id", type=int)
    mark.add_argument("value", choices=ledger.VALID_USER_ACTIONS)
    mark.add_argument("--size", type=float, default=None)
    mark.add_argument("--reason", default=None)
    mark.add_argument(
        "--theory", dest="mark_theory", default=None,
        help="theory this bet is taken for; required for 'taken'",
    )
    mark.add_argument(
        "--price", type=float, default=None,
        help="what you actually paid; if omitted, scoring falls back to "
             "the proposed ask",
    )

    p = sub.add_parser("score", help="calibration and settlement")
    p.set_defaults(func=_cmd_score)
    ssub = p.add_subparsers(dest="action", required=True)
    report = ssub.add_parser("report")
    report.add_argument("theory_id")
    report.add_argument("--version", type=int, default=None)
    report.add_argument("--run-mode", dest="run_mode", default="live")
    report.add_argument(
        "--run-id", dest="run_id", default=None,
        help=(
            "score a single run rather than pooling every run of this "
            "theory version -- required to avoid multiplying n when "
            "re-scoring a re-run backtest"
        ),
    )
    settle = ssub.add_parser("settle-one")
    settle.add_argument("ticker")
    settle.add_argument("result")
    settle.add_argument("--resolved-at", dest="resolved_at", default=None)

    p = sub.add_parser("backtest", help="backtest run provenance")
    p.set_defaults(func=_cmd_backtest)
    btsub = p.add_subparsers(dest="action", required=True)
    btrec = btsub.add_parser("record")
    btrec.add_argument("run_id")
    btrec.add_argument("theory_id")
    btrec.add_argument("theory_version", type=int)
    btrec.add_argument("--as-of-start", dest="as_of_start", default=None)
    btrec.add_argument("--as-of-end", dest="as_of_end", default=None)
    btrec.add_argument("--tier", choices=score.VALID_TIERS, default=None)
    btrec.add_argument(
        "--uses-llm-judgment", dest="uses_llm_judgment",
        action=argparse.BooleanOptionalAction, default=None,
    )
    btrec.add_argument("--model-cutoff", dest="model_cutoff", default=None)
    btrec.add_argument("--notes", default=None)

    p = sub.add_parser(
        "slices", help="registered subset edges (tools/slices.py)"
    )
    p.set_defaults(func=_cmd_slices)
    slsub = p.add_subparsers(dest="action", required=True)
    slreg = slsub.add_parser("register")
    slreg.add_argument("theory_id")
    slreg.add_argument("slug")
    slreg.add_argument(
        "--predicate", required=True,
        help=(
            "JSON dict of AND clauses over recorded fields, e.g. "
            '{"outcome": ["no"], "confidence": ["strong", "moderate"]}; '
            "also supports entry_price {min,max} and extra {key: value}"
        ),
    )
    slreg.add_argument(
        "--hypothesis", required=True,
        help="the mechanism claim — why this subset should differ",
    )
    slreg.add_argument(
        "--origin", required=True,
        help=(
            "where the pattern was found; must also cite the record for "
            "any --registered-at earlier than today and for every --oos-run"
        ),
    )
    slreg.add_argument(
        "--oos-run", dest="oos_run", action="append", default=[],
        help="run_id designated out-of-sample at registration (repeatable)",
    )
    slreg.add_argument("--priority", type=int, default=0)
    slreg.add_argument(
        "--registered-at", dest="registered_at", default=None,
        help=(
            "backdate the registration to a documented pre-registration; "
            "the citation goes in --origin"
        ),
    )
    sllist = slsub.add_parser("list")
    sllist.add_argument("--theory", default=None)
    slrep = slsub.add_parser("report")
    slrep.add_argument("theory_id")
    slrep.add_argument("--version", type=int, default=None)
    slrep.add_argument("--disposition", default="all")
    slrep.add_argument(
        "--run-modes", dest="run_modes", default="live,backtest",
        help="comma-separated evidence pool; tier-C rows are always excluded",
    )
    slmatch = slsub.add_parser("match")
    slmatch.add_argument("opportunity_id", type=int)
    slmatch.add_argument("--disposition", default="all")
    slret = slsub.add_parser("retire")
    slret.add_argument("theory_id")
    slret.add_argument("slug")
    slret.add_argument(
        "--reason", required=True,
        help="governance call — user/supervisor authorizes, like a theory",
    )

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
