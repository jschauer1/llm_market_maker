"""Unified command line over the data layer.

Skills invoke these commands rather than writing inline Python, so the
mechanical half of every workflow is code that has tests. Everything prints
JSON to stdout so a skill can parse the result reliably.

Run `python -m tools.cli --help` for the command list.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from tools import (db, floor, ideas, lanes, ledger, provenance, rank,
                   score, slices, studies, theories, tickets,
                   toolkit)


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
            if args.kind == "carry":
                raise SystemExit(
                    "a carry bump needs a passing equivalence proof, which "
                    "only exists as a Python object -- run the replay with "
                    "theories.prove_carry(...) and call "
                    "theories.bump_version(kind='carry', "
                    "equivalence=<result>) directly; the CLI cannot carry "
                    "a proof object"
                )
            version = theories.bump_version(
                conn, args.id, kind=args.kind, justification=args.justification
            )
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
            rendered_prompt = (
                args.rendered_prompt_file.read_text(encoding="utf-8")
                if args.rendered_prompt_file is not None else None
            )
            provenance.record_judgment_run(
                conn, run_id=args.run, theory_id=args.theory,
                theory_version=args.version, stage=args.stage,
                model=args.model, prompt_path=args.prompt_path,
                rendered_prompt=rendered_prompt,
                effort=args.effort, web_search=args.web_search,
                n_items=args.n_items, notes=args.notes,
            )
            _emit(_rows(provenance.list_judgment_runs(
                conn, theory_id=args.theory, run_id=args.run)))
    finally:
        conn.close()
    return 0


def _cmd_rulings(args) -> int:
    from tools import rulings as rulings_mod
    conn = _connect(args)
    try:
        if args.action == "record":
            rid = rulings_mod.record(
                conn, args.ruling, authority=args.authority,
                subject=args.subject, ruled_at=args.ruled_at,
                scope_out=args.scope_out, log_entry=args.log_entry,
            )
            _emit({"id": rid})
        elif args.action == "list":
            _emit(_rows(rulings_mod.list_rulings(conn, status=args.status)))
        elif args.action == "status":
            rulings_mod.set_status(conn, args.id, args.value)
            _emit({"id": args.id, "status": args.value})
    finally:
        conn.close()
    return 0


def _cmd_tools(args) -> int:
    """What a session can reach. Text by default -- this is written to be
    read, like `state` -- with --json for anything parsing it."""
    if getattr(args, "json", False):
        _emit(toolkit.list_tools())
    else:
        print(toolkit.render())
    return 0


def _cmd_studies(args) -> int:
    rows = studies.survey(db.REPO_ROOT)
    if getattr(args, "json", False):
        _emit(rows)
    else:
        print(studies.render(rows), end="")
    return 0


def _cmd_tickets(args) -> int:
    root = db.REPO_ROOT
    if args.action == "list":
        # Brief is the DEFAULT read. A ticket carries its design in
        # full, so the bodies dominate any listing that includes them --
        # and this is the command every session runs at orient.
        rows = tickets.backlog(
            root, lane=args.lane, status=args.status, theory=args.theory,
            study=args.study, brief=not args.full)
        if args.full:
            _emit(rows)
        else:
            print(tickets.render(rows), end="")
    elif args.action == "new":
        # A theory's folder is wherever its registry row says, never
        # theories/<slug>: insider_judgment sits under a shared family
        # parent, and deriving the path from the slug filed its tickets
        # into a phantom directory holding nothing else.
        theory_path = None
        theory_status = None
        if args.theory:
            conn = _connect(args)
            try:
                trow = theories.get(conn, args.theory)
                if trow is None:
                    raise SystemExit(f"unknown theory {args.theory!r}")
                theory_path = trow["path"]
                # Same lookup carries the status, and `ticket_dir` refuses
                # a retired theory with it: you cannot queue work against a
                # dead theory, and its path would put the file somewhere
                # `test_a_retired_theory_holds_only_its_record` rejects.
                theory_status = trow["status"]
            finally:
                conn.close()
        path = tickets.create(
            root, lane=args.lane, slug=args.slug, title=args.title,
            body=args.body, theory=args.theory, theory_path=theory_path,
            theory_status=theory_status,
            created_by=args.session, author_lane=args.author_lane,
            author_focus=args.author_focus,
            author_context=args.author_context,
        )
        _emit({"created": str(path.relative_to(root)).replace("\\", "/")})
    elif args.action == "advance":
        path = tickets.advance(pathlib.Path(args.path), to=args.to,
                               note=args.note)
        _emit({"advanced": str(path), "state": args.to})
    elif args.action == "close":
        # The connection is opened for EVERY close, not only a
        # new-theory one: whether the resolution needs a registry entry
        # is decided by `tickets.close` from the ticket's own lane and
        # first word, and a caller that had to know the rule in advance
        # to pass the right arguments is a rule with two homes.
        conn = _connect(args)
        try:
            path = tickets.close(pathlib.Path(args.path),
                                 resolution=args.resolution, conn=conn)
        finally:
            conn.close()
        # `deleted` is not decoration: a `new-theory` close REMOVES the
        # spec, and the path returned is where it used to be. Printing
        # that as a destination, the way every other lane's close reads,
        # would have a session looking for a file nothing will ever put
        # there again.
        _emit({"closed": str(path), "deleted": not path.exists()})
    elif args.action == "purge":
        # A connection for every purge: the citation check reads the
        # database's free-text columns as well as the markdown tree, and
        # a purge that silently skipped half its evidence because nobody
        # passed a flag is the failure mode this whole command is built
        # to avoid.
        conn = _connect(args)
        try:
            result = tickets.purge(root, older_than=args.older_than,
                                   apply=args.apply, conn=conn)
        finally:
            conn.close()
        if args.json:
            _emit(result)
        else:
            print(tickets.render_purge(result, root), end="")
    return 0


def _cmd_lane(args) -> int:
    conn = _connect(args)
    try:
        if args.action == "status":
            _emit(lanes.status(conn))
        elif args.action == "claim":
            try:
                got = lanes.claim(conn, args.lane, args.session,
                                  focus=args.focus, join=args.join)
            except lanes.LaneHeld as held:
                # Held is an answer, not a crash: the session reads who has
                # it and goes and takes an open lane.
                _emit({"claimed": False, "reason": str(held),
                       "status": lanes.status(conn)})
                return 0
            _emit({"claimed": True, "claim": dict(got),
                   "status": lanes.status(conn)})
        elif args.action == "release":
            _emit(dict(lanes.release(conn, args.id, summary=args.summary)))
        elif args.action == "recent":
            _emit(_rows(lanes.recent(conn, limit=args.limit)))
        return 0
    finally:
        conn.close()


def _cmd_floor(args) -> int:
    conn = _connect(args)
    try:
        if args.action == "status":
            _emit(floor.status(conn))
        elif args.action == "claim":
            got = floor.claim(conn, args.session, force=args.force)
            # None is an answer, not a failure: the floor already ran or
            # someone else is running it. Exit 0 and let the session read
            # the status it also gets back.
            _emit({
                "claimed": got is not None,
                "claim": dict(got) if got is not None else None,
                "status": floor.status(conn),
            })
        elif args.action == "complete":
            try:
                row = floor.complete(
                    conn, args.id, report_path=args.report_path,
                    summary=args.summary,
                )
            except ValueError as gap:
                # A refusal here is the point: the report is missing a
                # theory or a sub-theory, and the fix is to write the
                # line, not to skip the check.
                raise SystemExit(str(gap))
            _emit(dict(row))
        elif args.action == "checklist":
            _emit(floor.required_coverage(conn))
        elif args.action == "check-report":
            text = pathlib.Path(args.report_path).read_text(encoding="utf-8")
            gaps = floor.coverage_gaps(conn, text)
            _emit({"covered": not gaps, "missing": gaps})
        elif args.action == "recent":
            _emit(_rows(floor.recent(conn, limit=args.limit)))
        return 0
    finally:
        conn.close()


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
            if args.id is not None and args.ticker:
                raise SystemExit(
                    "pass an opportunity id or --ticker, not both -- "
                    "ambiguous which one identifies the position"
                )
            opp_id = args.id
            if opp_id is None:
                if not args.ticker:
                    raise SystemExit("pass an opportunity id or --ticker")
                try:
                    row = ledger.resolve_ticker(
                        conn, args.ticker, theory_id=args.mark_theory
                    )
                except KeyError:
                    raise SystemExit(
                        f"no open live position on {args.ticker}"
                    )
                except ValueError as e:
                    raise SystemExit(str(e))
                opp_id = row["id"]
                print(
                    f"matched {row['kalshi_ticker']} {row['outcome']} -> "
                    f"opportunity {opp_id} ({row['theory_id']} "
                    f"v{row['theory_version']}, {row['run_mode']}/"
                    f"{row['lane']})",
                    file=sys.stderr,
                )
            ledger.mark_user_action(
                conn, opp_id, args.value, size=args.size,
                reason=args.reason, theory_id=args.mark_theory,
                price=args.price,
            )
            _emit(dict(ledger.get_opportunity(conn, opp_id)))
    finally:
        conn.close()
    return 0


def _cmd_score(args) -> int:
    conn = _connect(args)
    try:
        if args.action == "report":
            theory = theories.get(conn, args.theory_id)
            version = args.version or (theory["version"] if theory else 1)
            modes = (args.run_mode,) if args.run_mode else slices.DEFAULT_RUN_MODES
            # The old refusal here ("the scores table has no column for
            # what pooled") is obsolete: `scores.pooled_versions` records
            # the span, and since the 2026-08-31 ruling a bump carries
            # evidence forward by default, so --save always pools the
            # version chain. `--pool` now only scopes the PRINTED
            # figures.
            results = {
                disposition: score.compute_score(
                    conn, args.theory_id, version,
                    modes,
                    disposition, run_id=args.run_id, pool=args.pool,
                )
                for disposition in ("all", "screened", "endorsed",
                                    "rejected")
            }
            saved = None
            if getattr(args, "save", False):
                # Every segment, not just the parent: a sub-theory's
                # evidence is its own and can be strong while the theory
                # around it is flat. Saving only the aggregate is what
                # kept proven subsets out of `state` entirely.
                saved = {
                    disposition: score.save_segment_scores(
                        conn, args.theory_id, version, disposition,
                        run_modes=(args.run_mode,) if args.run_mode else None,
                    )
                    for disposition in results
                }
            # "How is this theory doing" is not answered by the parent
            # alone: a sub-theory can be strongly supported while the
            # theory around it is flat, and that is the case the whole
            # partition exists for. Report both, always.
            seg_report = slices.segment_report(
                conn, args.theory_id, version, disposition="all",
                run_modes=modes, run_id=args.run_id, pool=args.pool,
            )
            segments = {
                f"slice:{s['slug']}": {
                    **s["oos"], "ready": s["ready"], "status": s["status"],
                    "hypothesis": s["hypothesis"],
                }
                for s in seg_report["slices"]
            }
            if seg_report.get("complement"):
                segments["complement"] = seg_report["complement"]
            # Report-only annotation. A riskless bucket built entirely
            # from rejected rows states a return nobody could have taken:
            # `structural_arb` showed riskless_roi=+0.550 on `all` from
            # two findings whose own rationales read "~0.01 baskets
            # fillable at riskless prices, ~$0.00 floor profit", while
            # `state`'s EVIDENCE line showed "n 0" and hid it the other
            # way. This is NARROWER than "rejections count in roi_all",
            # which is deliberate and documented -- for a judgment theory
            # a rejected winner is real counterfactual information. A
            # DEPTH rejection differs in kind: "not fillable at any size"
            # means there was no position to take, so the counterfactual
            # is impossible rather than merely untaken. Annotating rather
            # than changing the number keeps `riskless_roi` meaning what
            # every recorded row was written under (CLAUDE.md: prefer a
            # new name to a redefined one).
            notes = []
            rl = (results["all"] or {}).get("riskless_n") or 0
            if rl and rl == ((results["rejected"] or {}).get("riskless_n") or 0):
                notes.append(
                    f"riskless_roi covers {rl} position(s), all of them "
                    "REJECTED. If they were rejected for depth ('not "
                    "fillable at any size') the counterfactual is "
                    "impossible rather than untaken -- there was no "
                    "position to take -- so this is not a return the "
                    "theory could have earned. Check the rows' "
                    "rejection rationales before quoting it."
                )
            _emit(
                {
                    "theory_version": version,
                    **results,
                    "notes": notes,
                    "segments": segments,
                    "evidence_exclusions": seg_report["evidence_exclusions"],
                    **({"saved_score_ids": saved} if saved else {}),
                    # Reported alongside, never instead: `all` above counts
                    # rows, and rows that settled the same day are one draw
                    # wearing many rows' clothes. `n_days` is the sample
                    # size a reader should believe. Same --pool as the
                    # scores above, so a chain-pooled edge is never read
                    # next to a per-version day count (spec 2.5).
                    "settlement_days": {
                        disposition: score.settlement_day_clusters(
                            conn, args.theory_id, version,
                            modes,
                            disposition, run_id=args.run_id, pool=args.pool,
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
                mined_from_run_ids=args.mined_from_run or (),
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
                    pool=args.pool,
                )
            )
        elif args.action == "match":
            row = ledger.get_opportunity(conn, args.opportunity_id)
            if row is None:
                raise SystemExit(f"no opportunity {args.opportunity_id}")
            _emit(
                slices.ranking_segment(
                    conn, row, disposition=args.disposition, pool=args.pool
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


def _cmd_promote(args) -> int:
    from dataclasses import asdict

    from tools import promotion

    conn = _connect(args)
    if args.run is None and args.opportunity_id is None:
        raise SystemExit("promote: pass an opportunity id or --run <run_id>")

    markets_by_ticker = None
    if not args.no_quote:
        from tools.kalshi import markets as kalshi_markets

        if args.run is not None:
            tickers = [
                r["kalshi_ticker"] for r in conn.execute(
                    "SELECT DISTINCT o.kalshi_ticker FROM opportunities o"
                    " JOIN opportunity_attempts a ON a.opportunity_id = o.id"
                    " WHERE a.run_id = ? AND o.position_kind = 'single'",
                    (args.run,),
                )
            ]
        else:
            row = ledger.get_opportunity(conn, args.opportunity_id)
            tickers = [row["kalshi_ticker"]] if (
                row and row["position_kind"] == "single") else []
        markets_by_ticker = kalshi_markets.quotes(tickers)

    if args.run is not None:
        results = promotion.promote_run(
            conn, args.run, markets=markets_by_ticker
        )
    else:
        market = None
        if markets_by_ticker:
            row = ledger.get_opportunity(conn, args.opportunity_id)
            market = markets_by_ticker.get(row["kalshi_ticker"])
        results = [
            promotion.promote(conn, args.opportunity_id, market=market)
        ]

    escalations = []
    for theory_id in sorted({r.theory_id for r in results}):
        escalations.extend(promotion.orphaned_evidence(conn, theory_id))
    _emit({
        "key_version": promotion.KEY_VERSION,
        "results": [asdict(r) for r in results],
        "escalations": escalations,
    })
    return 0


def _cmd_db(args) -> int:
    from tools import backup as backup_mod
    if args.action == "backup":
        _emit(backup_mod.backup_ledger(
            args.db or db.DEFAULT_DB_PATH, dest_dir=args.dest
        ))
    if args.action == "dedup-snapshots":
        from tools import snapshot as snapshot_mod
        conn = _connect(args)
        try:
            _emit(snapshot_mod.dedup_history(conn))
        finally:
            db.close(conn)
    if args.action == "compress-snapshots":
        from tools import snapshot as snapshot_mod
        conn = _connect(args)
        try:
            _emit(snapshot_mod.compress_history(conn))
        finally:
            db.close(conn)
    if args.action == "split-snapshots":
        # Deliberately NOT routed through `_connect`: that helper calls
        # `init_db` (tools/cli.py:29), and `init_db` refuses an unsplit
        # database on purpose. This is the command that fixes exactly that
        # state, so it has to be reachable from it -- a plain db.connect()
        # bypasses the refusal, matching the migrate-positions precedent.
        main_path = args.db or db.DEFAULT_DB_PATH
        backup_mod.backup_ledger(main_path)
        conn = db.connect(args.db) if args.db else db.connect()
        try:
            _emit(db.split_snapshots(conn, main_path))
        finally:
            db.close(conn)
    if args.action == "stats":
        conn = db.connect(args.db) if args.db else db.connect()
        try:
            _emit(_db_stats(conn))
        finally:
            db.close(conn)
    return 0


def _db_stats(conn) -> dict:
    """Per attached database: file path, file bytes, and per-table size.

    Per-table byte breakdown needs the `dbstat` virtual table, which is
    not compiled into every SQLite build (it is not in this project's
    bundled Python, confirmed by probe) -- when it is absent, the file's
    total byte estimate (`page_count * page_size`) still stands for the
    whole file, and `per_table_bytes` names the reason it cannot be split
    further rather than silently reporting zero.
    """
    has_dbstat = conn.execute(
        "SELECT name FROM pragma_module_list WHERE name='dbstat'"
    ).fetchone() is not None
    out = {}
    for row in conn.execute("PRAGMA database_list"):
        schema, path = row[1], row[2]
        if not path:
            continue
        page_count = conn.execute(f"PRAGMA {schema}.page_count").fetchone()[0]
        page_size = conn.execute(f"PRAGMA {schema}.page_size").fetchone()[0]
        tables = [
            r[0] for r in conn.execute(
                f"SELECT name FROM {schema}.sqlite_master"
                " WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        table_rows = {
            t: conn.execute(f'SELECT COUNT(*) FROM "{schema}"."{t}"'
                            ).fetchone()[0]
            for t in tables
        }
        if has_dbstat:
            per_table_bytes = {
                t: (conn.execute(
                    f"SELECT SUM(pgsize) FROM {schema}.dbstat WHERE name = ?",
                    (t,),
                ).fetchone()[0] or 0)
                for t in tables
            }
        else:
            per_table_bytes = "unavailable (dbstat not compiled in)"
        out[schema] = {
            "path": path,
            "file_bytes": page_count * page_size,
            "table_rows": table_rows,
            "per_table_bytes": per_table_bytes,
        }
    return out


def _cmd_state(args) -> int:
    from tools import state as state_mod
    conn = _connect(args)
    try:
        text = state_mod.render_state(conn)
        print(text)
        if args.write:
            state_mod.write_state(conn, text=text)
    finally:
        db.close(conn)
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
        default="agent",
        choices=("agent", "claude", "codex", "user"),
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
    bump.add_argument(
        "--kind", choices=("continues", "carry", "breaking"),
        default="continues",
        help=(
            "how this bump relates to the predecessor's EVIDENCE. "
            "continues (default) -- the procedure changed and the evidence "
            "stands, no proof required. carry -- the change provably could "
            "not alter any recorded decision; refused without a passing "
            "equivalence proof, which only exists as a Python object (see "
            "theories.prove_carry). breaking -- an explicit sever that "
            "resets the track record; --justification must say what makes "
            "the old evidence inapplicable."
        ),
    )
    bump.add_argument(
        "--justification", required=True,
        help="what changed and why (recorded on the theory_versions row)",
    )

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
    pvr.add_argument(
        "--model", required=True,
        help=("actual requested model identifier, or an honestly labelled "
              "runtime alias when the host does not reveal the resolved model"),
    )
    pvr.add_argument("--prompt-path", dest="prompt_path", required=True,
                     help="repo path to the prompt file, so a change is "
                          "reviewable in git diff")
    pvr.add_argument(
        "--rendered-prompt-file", type=pathlib.Path,
        help=("file containing the exact rendered prompt sent to the judge; "
              "the prompt path remains the reviewable template source"),
    )
    pvr.add_argument("--effort", default=None)
    pvr.add_argument("--web-search", dest="web_search", type=int, default=None,
                     choices=(0, 1))
    pvr.add_argument("--n-items", dest="n_items", type=int, default=None)
    pvr.add_argument("--notes", default=None)

    p = sub.add_parser("rulings", help="binding rulings extracted from prose")
    p.set_defaults(func=_cmd_rulings)
    rsub = p.add_subparsers(dest="action", required=True)
    rrec = rsub.add_parser("record")
    rrec.add_argument("ruling", help="the binding text, one sentence or two")
    rrec.add_argument("--authority", required=True,
                      choices=("user", "supervisor"))
    rrec.add_argument("--subject", required=True,
                      help="e.g. scoring | schema | lifecycle | governance")
    rrec.add_argument("--ruled-at", dest="ruled_at", default=None)
    rrec.add_argument("--scope-out", dest="scope_out", default=None,
                      help="what the ruling explicitly excluded")
    rrec.add_argument("--log-entry", dest="log_entry", default=None,
                      help="the RESEARCH_LOG.md date heading with the reasoning")
    rlist = rsub.add_parser("list")
    rlist.add_argument("--status", default=None,
                       choices=("binding", "implemented", "superseded"))
    rst = rsub.add_parser("status")
    rst.add_argument("id", type=int)
    rst.add_argument("value", choices=("binding", "implemented", "superseded"))

    p = sub.add_parser(
        "studies", help="what has been measured: every study and its verdict")
    p.set_defaults(func=_cmd_studies)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser(
        "tickets", help="the work backlog: one .md per task, oldest first")
    p.set_defaults(func=_cmd_tickets)
    tsub = p.add_subparsers(dest="action", required=True)
    tls = tsub.add_parser("list", help="the backlog a session chooses from")
    tls.add_argument("--lane", default=None, choices=tickets.LANES)
    tls.add_argument("--theory", default=None)
    tls.add_argument("--study", default=None,
                     help="tickets filed AGAINST a named study, read from "
                          "their `study:` frontmatter -- not the studies "
                          "themselves, which are `--lane study`")
    tls.add_argument("--status", default="open")
    tls.add_argument(
        "--full", action="store_true",
        help="every field including the body, as JSON. The default is a "
             "one-line-per-ticket table: a ticket carries its whole "
             "design, so the bodies swamp any listing that includes them")
    tnew = tsub.add_parser("new", help="file work you are not going to do now")
    tnew.add_argument("--lane", required=True, choices=tickets.LANES)
    tnew.add_argument("--slug", required=True)
    tnew.add_argument("--title", required=True)
    tnew.add_argument("--body", required=True,
                      help="what to do, for a session that was not here")
    tnew.add_argument("--theory", default=None,
                      help="required for --lane theory; it lives in that "
                           "theory's folder")
    tnew.add_argument("--session", default=None,
                      help="your session name as reported by the active "
                           "agent runtime")
    tnew.add_argument(
        "--author-lane", dest="author_lane", default=None,
        choices=("floor", "theory", "study", "new-theory",
                 "find-theories", "maintenance"),
        help="the lane YOU are in as you file this")
    tnew.add_argument(
        "--author-focus", dest="author_focus", default=None,
        help="what you are focused on -- the theory, the ticket slug")
    tnew.add_argument(
        "--author-context", dest="author_context", default=None,
        help="one line on what you were doing when you hit this; it is "
             "the context a reader cannot reconstruct")
    tadv = tsub.add_parser(
        "advance", help="move a ticket to its next state")
    tadv.add_argument("path")
    tadv.add_argument("--to", required=True,
                      help="the state to move into; the lane declares "
                           "which it has (study: question, investigation, "
                           "answer; new-theory: open, build)")
    tadv.add_argument("--note", required=True,
                      help="why it moved — appended to the body under a "
                           "dated heading")
    tcl = tsub.add_parser(
        "close",
        help="finish a ticket: most lanes move it into completed/; a "
             "new-theory spec is DELETED, its verdict already being in "
             "the ideas registry or in the theory it became")
    tcl.add_argument("path")
    tcl.add_argument(
        "--resolution", required=True,
        help="what happened. A new-theory spec must START with one of "
             f"{tickets.NEW_THEORY_RESOLUTIONS} (and closing one deletes "
             "it) -- `disproven` means the "
             "bar was met and the thesis failed (not re-proposable); "
             "`underpowered` means the measurement could not reach the "
             "bar, which stays re-proposable. Either of those two "
             "requires the finding in the ideas registry first")
    tpg = tsub.add_parser(
        "purge",
        help="remove long-completed tickets nothing cites — DRY RUN by "
             "default")
    tpg.add_argument(
        "--apply", action="store_true",
        help="actually remove them, via `git rm`. Without this the "
             "command only lists what it would do: deleting files must "
             "never be a side effect of a flag somebody forgot to pass")
    tpg.add_argument(
        "--older-than", dest="older_than", type=int, default=7,
        help="days a ticket must have sat in completed/ before it is a "
             "candidate (default 7)")
    tpg.add_argument("--json", action="store_true")

    p = sub.add_parser(
        "lane", help="who is working on what; claim a lane and stay in it")
    p.set_defaults(func=_cmd_lane)
    lsub = p.add_subparsers(dest="action", required=True)
    lsub.add_parser("status", help="every lane and who holds it")
    lcl = lsub.add_parser("claim")
    lcl.add_argument("--lane", required=True, choices=lanes.LANES)
    lcl.add_argument("--session", required=True)
    lcl.add_argument("--focus", default=None,
                     help="which theory, on the theory lane")
    lcl.add_argument("--join", default=None,
                     help="join a lane someone already holds -- discouraged; "
                          "the reason is recorded")
    lrl = lsub.add_parser("release")
    lrl.add_argument("id", type=int)
    lrl.add_argument("--summary", default=None)
    lrc = lsub.add_parser("recent")
    lrc.add_argument("--limit", type=int, default=20)

    p = sub.add_parser(
        "tools", help="what a session can reach, and what each tool is for")
    p.set_defaults(func=_cmd_tools)
    p.add_argument("--json", action="store_true",
                   help="machine-readable, for anything parsing this")

    p = sub.add_parser(
        "floor", help="floor duty: is it due, who holds it, mark it done")
    p.set_defaults(func=_cmd_floor)
    fsub = p.add_subparsers(dest="action", required=True)
    fsub.add_parser("status", help="is the floor due? ask before claiming")
    fcl = fsub.add_parser(
        "claim", help="take floor duty; prints null if it is not yours to take")
    fcl.add_argument("--session", required=True,
                     help="this session's name as reported by the active "
                          "agent runtime")
    fcl.add_argument(
        "--force", action="store_true",
        help="the user explicitly asked for a floor inside the 24h window; "
             "still refuses to cut in on a live claim")
    fco = fsub.add_parser("complete", help="the floor ran and the report landed")
    fco.add_argument("id", type=int, help="the claim id from `floor claim`")
    fco.add_argument("--report", dest="report_path", default=None,
                     help="path to the report written for the user")
    fco.add_argument("--summary", default=None)
    fck = fsub.add_parser(
        "checklist",
        help="every theory AND sub-theory the report must cover -- read "
             "this before writing it")
    fchk = fsub.add_parser(
        "check-report", help="what a drafted report is still missing")
    fchk.add_argument("report_path")
    frc = fsub.add_parser("recent", help="the last few floor runs")
    frc.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("ideas", help="research memory")
    p.set_defaults(func=_cmd_ideas)
    isub = p.add_subparsers(dest="action", required=True)
    search = isub.add_parser("search")
    search.add_argument("keyword")
    rec = isub.add_parser("record")
    rec.add_argument("slug")
    rec.add_argument("title")
    rec.add_argument("--description", default="")
    rec.add_argument(
        "--source", default=None,
        help=("idea origin; new ideas default to 'agent', while omission on "
              "an existing idea preserves its recorded source"),
    )
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
    mark.add_argument("id", type=int, nargs="?", default=None)
    mark.add_argument("value", choices=ledger.VALID_USER_ACTIONS)
    mark.add_argument("--size", type=float, default=None)
    mark.add_argument("--reason", default=None)
    mark.add_argument(
        "--theory", dest="mark_theory", default=None,
        help="theory this bet is taken for; required for 'taken'",
    )
    mark.add_argument(
        "--ticker", default=None,
        help="resolve the position by Kalshi ticker instead of id -- the "
             "latest live-lane sighting (run_mode='live', lane='main'); "
             "nothing here filters on settlement, and ambiguity across "
             "theories or outcomes refuses and lists candidates",
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
    report.add_argument(
        "--run-mode", dest="run_mode", default=None,
        help="scope to one run mode. The default pools live and backtest, "
             "because a replayed settlement and a forward one are the same "
             "evidence -- n_backtest says how much is which",
    )
    report.add_argument(
        "--run-id", dest="run_id", default=None,
        help=(
            "score a single run rather than pooling every run of this "
            "theory version -- required to avoid multiplying n when "
            "re-scoring a re-run backtest"
        ),
    )
    report.add_argument(
        "--pool", choices=("version", "chain"), default="chain",
        help=(
            "'chain' (default) pools every version the evidence carries "
            "across, which is what a bump does unless it declared itself "
            "breaking. 'version' scopes to theory_version alone and "
            "settlement-day segments to every version a proven carry bump "
            "links back to (spec 2.5); the response's chain_versions key "
            "shows what pooled, and is absent when nothing did"
        ),
    )
    report.add_argument(
        "--save", action="store_true",
        help=(
            "persist the computed per-version scores via save_score, so "
            "`state` EVIDENCE renders them -- the settle step passes this "
            "(per-version pool only; a chain-pooled result is refused)"
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
    slreg.add_argument(
        "--mined-from-run", dest="mined_from_run", action="append", default=[],
        help=(
            "run_id whose rows SUGGESTED this slice; excluded from its "
            "credibility permanently, whatever its tier (repeatable). A "
            "tier A/B backtest otherwise counts as evidence by default, so "
            "this is the declaration that keeps a pattern from vouching "
            "for itself"
        ),
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
    slrep.add_argument(
        "--pool", choices=("version", "chain"), default="chain",
        help=(
            "'chain' (default) pools every version the evidence carries "
            "across, which is what a bump does unless it declared itself "
            "breaking. 'version' scopes to theory_version alone -- "
            "aggregate, each slice's oos/in_sample, and the complement -- "
            "to every version a proven carry bump links back to (spec "
            "2.8); the response's chain_versions key shows what pooled, "
            "and is absent when nothing did"
        ),
    )
    slmatch = slsub.add_parser("match")
    slmatch.add_argument("opportunity_id", type=int)
    slmatch.add_argument("--disposition", default="all")
    slmatch.add_argument(
        "--pool", choices=("version", "chain"), default="chain",
        help=(
            "same pooling as 'slices report', threaded "
            "into the segment this candidate ranks on"
        ),
    )
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

    p = sub.add_parser(
        "promote",
        help="classify recorded candidates onto docs/promotion-key.md rungs",
    )
    p.set_defaults(func=_cmd_promote)
    p.add_argument("opportunity_id", type=int, nargs="?", default=None)
    p.add_argument("--run", default=None,
                   help="promote every position this run_id touched "
                        "(keyed on opportunity_attempts, never the "
                        "first-seer opportunities.run_id)")
    p.add_argument("--no-quote", action="store_true",
                   help="skip the live re-quote; rungs are then computed "
                        "on recorded entry prices and flagged unquoted")

    p = sub.add_parser("db", help="database operations")
    p.set_defaults(func=_cmd_db)
    dbsub = p.add_subparsers(dest="action", required=True)
    dbackup = dbsub.add_parser(
        "backup",
        help="gzip every table except market_snapshots to a non-synced dir",
    )
    dbackup.add_argument(
        "--dest", default=None,
        help=r"destination directory (default %LOCALAPPDATA%\market_edge\backups)",
    )
    dbsub.add_parser(
        "dedup-snapshots",
        help="collapse consecutive byte-identical snapshot rows into"
             " validity intervals (spec 5.2 phase 2, one-time)",
    )
    dbsub.add_parser(
        "compress-snapshots",
        help="zlib-compress plain-text raw_json/event_json rows in place"
             " (spec 5.2 phase 3, incremental and idempotent)",
    )
    dbsub.add_parser(
        "split-snapshots",
        help="one-time move of market_snapshots out of the main database"
             " file into db/snapshots.db, ATTACHed as snapdb (spec 5.2"
             " phase 4) -- backs up the ledger first",
    )
    dbsub.add_parser(
        "stats",
        help="per-database (main/snapdb) file size and per-table size"
             " (spec 5.2 phase 4)",
    )

    p = sub.add_parser(
        "state",
        help="current research state from the DB — the orientation surface",
    )
    p.add_argument("--write", action="store_true",
                   help="also write STATE.md (gitignored) for humans")
    p.set_defaults(func=_cmd_state)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Every command here prints prose written with em dashes and arrows,
    # and Windows consoles default to cp1252, which cannot encode them.
    # That was cosmetic for a while -- `state` rendered "[tier ?]" -- and
    # then it was not: any character with no cp1252 mapping raises
    # UnicodeEncodeError and takes the whole command down. `state` is the
    # surface every session orients on, so it must not be able to crash
    # on its own output.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):  # not a real TextIO (captured)
            pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
