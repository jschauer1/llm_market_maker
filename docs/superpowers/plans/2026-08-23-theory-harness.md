# Theory Harness and Operating Modes Implementation Plan (Plan 3 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the tools from Plans 1 and 2 into a system a Claude session can actually operate — a CLI over the data layer, the theory format, the ported `insider_bias` reference theory with its real track record, the six skills, and the `CLAUDE.md` briefing that makes "open the repo and say `go`" work.

**Architecture:** A single `python -m tools.cli` entry point gives skills concrete, testable commands instead of ad-hoc inline Python. Theories are folders owning their own code; `insider_bias` ships its deterministic stage-1 screen as Python and its unencodable heuristics as stage-2 prose. Skills are markdown procedures — they carry judgment, not logic, and everything mechanical they invoke is already tested code.

**Tech Stack:** Python 3.11, pytest, markdown.

**Spec:** `docs/superpowers/specs/2026-08-23-llm-market-edge-finder-design.md`

**Depends on:** Plans 1 and 2 complete, `python -m pytest -m "not network"` green (191 tests).

## Global Constraints

- Everything from Plans 1 and 2 applies: UTC ISO-8601 strings, decimal-dollar prices, edge in percentage points, no API keys, fail loudly on schema drift.
- **Skills carry judgment; tools carry logic.** If a skill instructs Claude to compute something, that computation belongs in a tested tool instead. A skill may say "rank these" only because `tools/rank.py` exists.
- **Recording requires an edge.** `record_opportunity` demands `edge_pts_net`. Two valid patterns follow from this:
  - A theory whose stage 1 computes edge mechanically (structural arbitrage, price rules) records at screen time with `disposition='screened'`, then interprets later.
  - A theory whose edge depends on a probability only judgment can supply (`insider_bias`) records *after* stage-2 judgment, immediately setting `endorsed` or `rejected`. Candidates never reached within the scan budget are reported as a count, not recorded.
- **Never fabricate a track record.** Migrated `kalshi_trader` rows are real history; nothing else may be back-filled or invented.
- Commit after every task.

---

### Task 1: Unified CLI over the data layer

Skills need concrete commands. This wraps the Plan 1/2 modules in one argparse entry point so a `SKILL.md` can say "run this" rather than "write some Python".

**Files:**
- Create: `tools/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `tools.db`, `tools.theories`, `tools.ideas`, `tools.ledger`, `tools.score`, `tools.rank`
- Produces:
  - `tools.cli.main(argv: list[str] | None = None) -> int` — exit code
  - Commands: `init`, `theories list|register|status|bump`, `ideas search|record|status|revisitable`, `opportunities list`, `score report|settle-one`, `rank`
  - All output is JSON on stdout, so skills can read it reliably.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
import json

import pytest

from tools import cli, db, ideas, ledger, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def dbpath(tmp_path):
    path = tmp_path / "test.db"
    conn = db.connect(path)
    db.init_db(conn)
    theories.register(conn, "t1", "Theory One", "theories/t1", now=TS)
    conn.close()
    return str(path)


def _run(capsys, *args):
    code = cli.main(list(args))
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip() else None


def test_init_creates_the_database(tmp_path, capsys):
    path = tmp_path / "fresh.db"
    code, payload = _run(capsys, "--db", str(path), "init")
    assert code == 0
    assert payload["ok"] is True
    assert path.exists()


def test_theories_list_outputs_json(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "theories", "list")
    assert code == 0
    assert [t["id"] for t in payload] == ["t1"]


def test_theories_list_filters_by_status(dbpath, capsys):
    _run(capsys, "--db", dbpath, "theories", "status", "t1", "active")
    code, payload = _run(
        capsys, "--db", dbpath, "theories", "list", "--status", "active"
    )
    assert [t["id"] for t in payload] == ["t1"]

    code, payload = _run(
        capsys, "--db", dbpath, "theories", "list", "--status", "retired"
    )
    assert payload == []


def test_theories_register_creates_one(dbpath, capsys):
    _run(capsys, "--db", dbpath, "theories", "register", "t2", "Two",
         "theories/t2")
    code, payload = _run(capsys, "--db", dbpath, "theories", "list")
    assert {t["id"] for t in payload} == {"t1", "t2"}


def test_theories_bump_increments_version(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "theories", "bump", "t1")
    assert payload["version"] == 2


def test_ideas_record_and_search(dbpath, capsys):
    _run(capsys, "--db", dbpath, "ideas", "record", "whale-copy",
         "Copy Polymarket whales", "--description", "Follow large traders.")
    code, payload = _run(capsys, "--db", dbpath, "ideas", "search", "whale")
    assert [i["slug"] for i in payload] == ["whale-copy"]


def test_ideas_search_returns_empty_for_no_match(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "ideas", "search", "nothing")
    assert payload == []


def test_ideas_status_records_the_outcome(dbpath, capsys):
    _run(capsys, "--db", dbpath, "ideas", "record", "i1", "Idea one")
    _run(capsys, "--db", dbpath, "ideas", "status", "i1", "dead",
         "--outcome", "No signal found.",
         "--revisit-angle", "Retry with better matching.")
    code, payload = _run(capsys, "--db", dbpath, "ideas", "revisitable")
    assert payload[0]["slug"] == "i1"
    assert "better matching" in payload[0]["revisit_angle"]


def test_opportunities_list_is_empty_initially(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "opportunities", "list")
    assert payload == []


def test_opportunities_list_shows_recorded_rows(dbpath, capsys):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXA",
        outcome="yes", entry_price=0.4, edge_pts_net=6.0, now=TS,
    )
    conn.close()
    code, payload = _run(capsys, "--db", dbpath, "opportunities", "list")
    assert payload[0]["kalshi_ticker"] == "KXA"


def test_rank_applies_credibility_shrinkage(capsys):
    code, payload = _run(capsys, "rank", "--edge", "12", "--n", "0")
    assert payload["ranked_edge"] == pytest.approx(3.0)
    assert payload["credibility"] == pytest.approx(0.25)


def test_rank_uses_measured_realization(capsys):
    code, payload = _run(
        capsys, "rank", "--edge", "6", "--n", "40",
        "--calibration-edge", "6", "--mean-claimed-edge", "6",
    )
    assert payload["ranked_edge"] == pytest.approx(4.0, abs=0.01)


def test_score_report_outputs_all_dispositions(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1")
    assert set(payload) >= {"all", "endorsed", "rejected"}
    assert payload["all"]["n"] == 0


def test_unknown_command_returns_nonzero(capsys):
    with pytest.raises(SystemExit):
        cli.main(["nonsense"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.cli'`

- [ ] **Step 3: Write `tools/cli.py`**

```python
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
        args.n, args.calibration_edge, args.mean_claimed_edge
    )
    _emit(
        {
            "edge_pts_net": args.edge,
            "n": args.n,
            "credibility": credibility,
            "realization": rank.realization(
                args.calibration_edge, args.mean_claimed_edge
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
    p.add_argument("--calibration-edge", dest="calibration_edge",
                   type=float, default=None)
    p.add_argument("--mean-claimed-edge", dest="mean_claimed_edge",
                   type=float, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS — 14 passed

- [ ] **Step 5: Commit**

```bash
git add tools/cli.py tests/test_cli.py
git commit -m "feat: add unified CLI over the data layer"
```

---

### Task 2: Tool conventions and the promotion path

**Files:**
- Create: `tools/README.md`

**Interfaces:**
- Consumes: nothing
- Produces: documentation only

- [ ] **Step 1: Write `tools/README.md`**

````markdown
# Tools

Small, single-purpose scripts. Not a framework — there is no base class to
learn and no plugin registry. Read one tool end to end and you know how to
write the next one.

## Conventions

- **One responsibility per file.** If you cannot describe a tool in one
  sentence, it is two tools.
- **JSON or SQLite in, JSON or SQLite out.** Nothing prints prose for a human
  to parse; `tools/cli.py` is where human-facing formatting happens.
- **A module docstring that says what it does and why.** The "why" matters
  more than the "what" — the next reader needs to know what problem this
  existed to solve.
- **Injectable `now`.** Any function that needs a timestamp takes
  `now: str | None = None` defaulting to real UTC, so tests never assert
  against a wall clock.
- **Fail loudly.** A required field that is missing or unparseable raises.
  Never let a schema change turn silently into `0.0` — a wrong number is far
  worse than an exception, because it looks like an answer.
- **Prices are decimal dollars in [0, 1]. Edge is in percentage points.**
  Conversion happens at the API boundary; no provider's wire format escapes
  its client module.
- **No credentials.** Every endpoint this project uses is public. Never add
  an API key, and never send any user identifier in a header, URL, or body.

## Writing a new tool

Copy the shape of an existing one. `tools/ideas.py` is a good model for a
database tool; `tools/polymarket/markets.py` is a good model for an API
client. Add tests in `tests/` mirroring the path.

## Where new code lives — and how it gets promoted

**New code starts in the theory that needs it.** A theory folder can hold any
Python it wants. Most theory code is specific to one hypothesis and belongs
nowhere else; generalizing early produces a shared layer full of
single-caller abstractions, which is worse than a little duplication.

**Promotion to `tools/` is earned.** A theory-local script becomes a
candidate when it actually has more than one real caller, or when a new
theory would obviously reach for it. This is a judgment call, not a rule that
fires on the second use — sometimes two theories want subtly different things
and should keep their own versions.

When you do promote:

1. Move it to `tools/`, generalizing only as far as the real callers require.
2. Give it the treatment above: docstring, tests, JSON/SQLite boundaries.
3. Update every theory that used a local copy to call the shared one, and
   delete the local copies. One implementation, not two.
4. Note it in each affected theory's `THEORY.md` changelog. If behavior
   changed at all in the move, that is a decision-procedure change — bump the
   theory version.

This mirrors how a heuristic graduates from stage 2 to stage 1: prove it in a
narrow context, then promote it once there is evidence it belongs.

## Tool map

| Tool | What it does |
|---|---|
| `cli.py` | Unified command line over everything below |
| `db.py` | Connection, schema, UTC timestamps |
| `theories.py` | Theory registry, lifecycle status, versioning |
| `ideas.py` | Research memory — every hypothesis considered, and why it died |
| `ledger.py` | `record_opportunity`, interpretation, user actions |
| `score.py` | Settlements, calibration edge, ROI, interpretation value |
| `rank.py` | Credibility-weighted ranking |
| `sizing.py` | Kalshi fee model, Kelly sizing |
| `snapshot.py` | First-party market history capture |
| `match_market.py` | Non-Kalshi finding → Kalshi ticker shortlist |
| `http.py` | Retrying HTTP for the public APIs |
| `kalshi/markets.py` | Open/settled markets, live quotes, resolution rules |
| `kalshi/history.py` | Candlesticks, point-in-time reconstruction |
| `polymarket/markets.py` | Open/resolved markets |
| `polymarket/trades.py` | Trades, whale detection, holders |
````

- [ ] **Step 2: Commit**

```bash
git add tools/README.md
git commit -m "docs: add tool conventions and promotion path"
```

---

### Task 3: Theory template

**Files:**
- Create: `theories/_TEMPLATE/THEORY.md`

- [ ] **Step 1: Write `theories/_TEMPLATE/THEORY.md`**

````markdown
# <Theory name>

> Delete this quote block when you fill the template in.
>
> A theory is a folder. Beyond this file, its shape is entirely yours: Python
> scripts, prompts, notebooks, fixture data — whatever the hypothesis needs.
> There is no required function, no pipeline to conform to, no base class.
>
> `insider_bias` happens to be a filter-then-judge theory. That is one shape,
> not the shape. A structural arbitrage theory might be pure deterministic
> math with an empty stage 2. A whale-following theory might be almost
> entirely judgment across two platforms. Build what the idea needs.
>
> The one thing every theory must do is call `record_opportunity` with a
> tradeable Kalshi ticker and a net edge in percentage points. That single
> contract is what makes theories comparable to each other.

## Hypothesis

What is the thesis? What mistake is the market making, and why does it
persist rather than getting arbitraged away?

## Data sources

Which platforms and tools does this use?

## Status

`proposed` — with a journal of status changes and the reason for each.

## Version

1 — changelog of what changed at each bump. Any change to the decision
procedure bumps this, including migrating a stage-2 heuristic into stage 1.

## Stage 1 — mechanical screen

What can be encoded deterministically: which tools to call, what filters and
thresholds, how candidates are produced. Push as much here as possible —
anything in code is repeatable, testable, and free to run over thousands of
markets.

If the signal originates outside Kalshi, this must include the
`tools/match_market.py` step that resolves it to a Kalshi ticker.
`record_opportunity` has no Kalshi-less path.

## Stage 2 — what needs judgment

What cannot be encoded, and what Claude should look for when reading this
theory's output. Market types that are structurally soft or dangerous,
resolution-language traps, context worth researching before endorsing.

Be concrete. "Use good judgment" helps nobody; "check whether the resolution
source publishes on a schedule that can miss the close" is a real instruction.

**Ask for classifications and a confidence bucket, never a probability.** An
LLM-introspected number is mostly an anchor on whatever price was in context.
State here whether judgment runs blind to price — it should, wherever the
theory allows.

Anything here that keeps proving itself should eventually migrate into
stage 1 as code.

## Confidence buckets

The ordinal scale this theory's judgment step uses, with a conservative prior
edge in points for each. Priors apply only until a bucket has 10+ settled
results; after that its own realized win rate replaces them. Treat the priors
as placeholders — the point of the mechanism is that measurement overrides
them, including measuring that a bucket is worth nothing.

| bucket | meaning | prior edge (pts) |
|---|---|---|
| `strong` | | |
| `moderate` | | |
| `weak` | | 0.0 |

A theory whose edge comes from a mechanical model rather than judgment can
skip this section — record `edge_basis="model"` instead.

## How to backtest

A procedure using the point-in-time tools. State plainly whether the decision
path uses LLM judgment, because that determines the tier:

- **Tier A** — no LLM in the decision path. Backtest over all history.
- **Tier B** — LLM judgment, restricted to markets that resolved after the
  model's knowledge cutoff, web search off.
- **Tier C** — LLM judgment on pre-cutoff markets. Contaminated; indicative
  only, and excluded from credibility.

## Learnings

Running journal — what worked, what did not, what surprised you.
````

- [ ] **Step 2: Commit**

```bash
git add theories/_TEMPLATE/THEORY.md
git commit -m "feat: add theory template"
```

---

### Task 4: Port insider_bias

The reference theory. Its stage-1 screen is a faithful port of `kalshi_trader`'s deterministic filter; its stage-2 section captures what that project's prompts could not encode — including the reality-TV vulnerability the user actually trades on.

**Files:**
- Create: `theories/insider_bias/THEORY.md`
- Create: `theories/insider_bias/screen.py`
- Create: `tests/theories/__init__.py`
- Create: `tests/theories/test_insider_bias_screen.py`

**Interfaces:**
- Consumes: `tools.kalshi.markets`, `tools.sizing`
- Produces:
  - `theories.insider_bias.screen.favorite(market: dict) -> tuple[str, float] | None` — `(side, executable_price)`
  - `theories.insider_bias.screen.is_excluded(ticker: str) -> bool`
  - `theories.insider_bias.screen.days_until(close_time: str, now: datetime | None = None) -> float | None`
  - `theories.insider_bias.screen.screen(markets: list[dict], now: datetime | None = None, **overrides) -> list[dict]` — each candidate adds `fav_side`, `entry_price`, `days_to_close`
  - Constants: `MIN_FAVORITE_PRICE = 0.65`, `MAX_FAVORITE_PRICE = 0.97`, `MAX_SPREAD = 0.07`, `MIN_VOLUME = 500`, `MAX_DAYS_AHEAD = 14`, `EXCLUDED_PREFIXES`

- [ ] **Step 1: Write the failing test**

Create `tests/theories/__init__.py` (empty), `theories/__init__.py` (empty), `theories/insider_bias/__init__.py` (empty), then `tests/theories/test_insider_bias_screen.py`:

```python
from datetime import datetime, timezone

import pytest

from theories.insider_bias import screen

NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)


def _market(**overrides):
    base = {
        "platform": "kalshi",
        "ticker": "KXTRAITORS-26-WINNER",
        "title": "Will contestant X win The Traitors?",
        "yes_bid": 0.78,
        "yes_ask": 0.80,
        "no_bid": 0.20,
        "no_ask": 0.22,
        "mid": 0.79,
        "spread": 0.02,
        "volume": 5000.0,
        "close_time": "2026-08-30T00:00:00Z",
        "is_open": True,
        "rules_primary": "Resolves Yes if X is named winner.",
    }
    base.update(overrides)
    return base


def test_favorite_is_yes_when_mid_above_half():
    side, price = screen.favorite(_market(mid=0.79))
    assert side == "yes"
    assert price == pytest.approx(0.80), "must use the ask you would pay"


def test_favorite_is_no_when_mid_below_half():
    side, price = screen.favorite(_market(mid=0.21))
    assert side == "no"
    assert price == pytest.approx(0.22)


def test_favorite_returns_none_without_a_mid():
    assert screen.favorite(_market(mid=None)) is None


def test_favorite_returns_none_without_an_executable_price():
    assert screen.favorite(_market(mid=0.79, yes_ask=None)) is None


def test_days_until_computes_a_horizon():
    assert screen.days_until("2026-08-30T00:00:00Z", now=NOW) == \
        pytest.approx(7.0, abs=0.1)


def test_days_until_handles_missing_or_bad_input():
    assert screen.days_until(None, now=NOW) is None
    assert screen.days_until("not-a-date", now=NOW) is None


def test_is_excluded_matches_sports_prefixes():
    assert screen.is_excluded("KXNFLGAME-26") is True
    assert screen.is_excluded("KXMVECROSS-1") is True
    assert screen.is_excluded("KXATP-26") is True


def test_is_excluded_allows_non_sports_tickers():
    assert screen.is_excluded("KXTRAITORS-26-WINNER") is False
    assert screen.is_excluded("KXCABINET-26") is False


def test_screen_accepts_a_clean_candidate():
    result = screen.screen([_market()], now=NOW)
    assert len(result) == 1
    assert result[0]["fav_side"] == "yes"
    assert result[0]["entry_price"] == pytest.approx(0.80)
    assert result[0]["days_to_close"] == pytest.approx(7.0, abs=0.1)


def test_screen_rejects_excluded_sports_tickers():
    assert screen.screen([_market(ticker="KXNFLGAME-26")], now=NOW) == []


def test_screen_rejects_prices_below_the_favorite_band():
    assert screen.screen(
        [_market(mid=0.55, yes_ask=0.56)], now=NOW
    ) == []


def test_screen_rejects_prices_above_the_favorite_band():
    # Too little room left to be worth the fee.
    assert screen.screen(
        [_market(mid=0.99, yes_ask=0.99)], now=NOW
    ) == []


def test_screen_rejects_wide_spreads():
    assert screen.screen(
        [_market(spread=0.12, yes_bid=0.70, yes_ask=0.82)], now=NOW
    ) == []


def test_screen_rejects_thin_volume():
    assert screen.screen([_market(volume=50.0)], now=NOW) == []


def test_screen_rejects_markets_closing_too_far_out():
    assert screen.screen(
        [_market(close_time="2027-08-30T00:00:00Z")], now=NOW
    ) == []


def test_screen_rejects_already_closed_markets():
    assert screen.screen(
        [_market(close_time="2026-08-01T00:00:00Z")], now=NOW
    ) == []


def test_screen_rejects_closed_markets():
    assert screen.screen([_market(is_open=False)], now=NOW) == []


def test_screen_thresholds_are_overridable():
    thin = _market(volume=100.0)
    assert screen.screen([thin], now=NOW) == []
    assert len(screen.screen([thin], now=NOW, min_volume=50)) == 1


def test_screen_keeps_resolution_rules_for_stage_two():
    result = screen.screen([_market()], now=NOW)
    assert "named winner" in result[0]["rules_primary"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/theories/test_insider_bias_screen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'theories.insider_bias.screen'`

- [ ] **Step 3: Write `theories/insider_bias/screen.py`**

```python
"""insider_bias — stage 1 mechanical screen.

Ported from kalshi_trader's deterministic filter. This narrows the whole
Kalshi board to markets where the insider thesis is even possible: a clear
favorite with room left after fees, a tight enough spread to trade, real
volume, and a near-term close.

It deliberately makes no probability estimate. This theory's edge depends on
judging whether a specific group of humans already knows the answer, and no
threshold can decide that. Stage 2 supplies the probability; see THEORY.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

MIN_FAVORITE_PRICE = 0.65
MAX_FAVORITE_PRICE = 0.97
MAX_SPREAD = 0.07
MIN_VOLUME = 500.0
MAX_DAYS_AHEAD = 14.0

# Sports, esports, and multi-variate parlays: outcomes nobody can know in
# advance, so the insider thesis cannot apply by construction.
EXCLUDED_PREFIXES = (
    "KXMVE",
    "KXMLB", "KXNBA", "KXNFL", "KXNHL",
    "KXEPL", "KXLALIGA", "KXBUNDESLIGA", "KXSERIE", "KXMLS", "KXLIGUE",
    "KXEFL", "KXEREDIVISIE", "KXALLSVENSKAN", "KXBRASILEIRO",
    "KXARGPREMDIV", "KXLIGAMX", "KXLIGAPORTUGAL", "KXSAUDIPL",
    "KXSUPERLIG", "KXJLEAGUE", "KXCZEFL", "KXUCLW",
    "KXATP", "KXWTA", "KXITF",
    "KXPGA", "KXLPGA", "KXDPWORLD", "KXCHAMPTOUR",
    "KXBOXING", "KXUFC", "KXNCAA",
    "KXAFL", "KXNASCAR", "KXF1", "KXIPL",
    "KXBSL", "KXSHL", "KXVTB",
    "KXCS2", "KXLOL", "KXCOD", "KXDOTA2",
)


def is_excluded(ticker: str) -> bool:
    """True for market families the thesis cannot apply to."""
    return any(ticker.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def favorite(market: dict) -> tuple[str, float] | None:
    """The favored side and the price you would actually pay for it.

    Uses the ask, not the mid. An edge measured against the mid is an edge
    against a price nobody will fill.
    """
    mid = market.get("mid")
    if mid is None:
        return None
    if mid >= 0.5:
        price = market.get("yes_ask")
        side = "yes"
    else:
        price = market.get("no_ask")
        side = "no"
    if price is None:
        return None
    return side, price


def days_until(close_time: str | None, now: datetime | None = None) -> float | None:
    """Days from now until close, or None if unparseable."""
    if not close_time:
        return None
    try:
        closes = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
    except ValueError:
        return None
    reference = now or datetime.now(timezone.utc)
    return (closes - reference).total_seconds() / 86400.0


def screen(
    markets: list[dict],
    now: datetime | None = None,
    min_favorite_price: float = MIN_FAVORITE_PRICE,
    max_favorite_price: float = MAX_FAVORITE_PRICE,
    max_spread: float = MAX_SPREAD,
    min_volume: float = MIN_VOLUME,
    max_days_ahead: float = MAX_DAYS_AHEAD,
) -> list[dict]:
    """Narrow normalized Kalshi markets to insider-thesis candidates."""
    candidates = []
    for market in markets:
        ticker = market.get("ticker") or ""
        if not market.get("is_open") or is_excluded(ticker):
            continue

        fav = favorite(market)
        if fav is None:
            continue
        side, entry_price = fav
        if not min_favorite_price <= entry_price <= max_favorite_price:
            continue

        spread = market.get("spread")
        if spread is None or spread > max_spread:
            continue

        volume = market.get("volume")
        if volume is None or volume < min_volume:
            continue

        days = days_until(market.get("close_time"), now=now)
        if days is None or days < 0 or days > max_days_ahead:
            continue

        candidate = dict(market)
        candidate["fav_side"] = side
        candidate["entry_price"] = entry_price
        candidate["days_to_close"] = days
        candidates.append(candidate)

    return candidates
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/theories/test_insider_bias_screen.py -v`
Expected: PASS — 19 passed

- [ ] **Step 5: Write `theories/insider_bias/THEORY.md`**

````markdown
# Insider Bias

## Hypothesis

Some Kalshi markets resolve on facts a specific, identifiable group of humans
already knows while the public does not — pre-taped reality TV, award votes
already cast, executive hires the board has already made, appointments
reporters already have sourced. When that private knowledge is real, the
public price still leaves room, and buying the favorite captures the gap.

Why it persists: the crowd cannot verify the private information, so it prices
on public uncertainty. The edge is not a smarter forecast — it is recognizing
which markets have an informed minority at all.

Ported from `kalshi_trader`, where it ran from May to July 2026 and produced
the imported track record.

## Data sources

Kalshi only (`tools/kalshi/markets.py`). No Polymarket dependency.

## Status

`active` — imported with real history from `kalshi_trader`.

## Version

1 — initial port. Stage 1 is a faithful port of the original deterministic
filter. Stage 2 replaces the OpenAI classify/pick calls with Claude/subagent
judgment.

## Stage 1 — mechanical screen

`python -c "from theories.insider_bias import screen"` — or call
`screen.screen(markets)` directly on the output of
`tools.kalshi.markets.list_open()`.

Filters, all overridable per run:

- Excluded ticker prefixes: sports, esports, multi-variate parlays. The
  thesis cannot apply where nobody can know the outcome in advance.
- Favorite price in [0.65, 0.97] at the **ask**. Below the band there is no
  favorite worth calling informed; above it there is no room left after fees.
- Spread ≤ 0.07 and volume ≥ 500. An edge inside the spread is not an edge.
- Closes within 14 days and has not already closed.

The screen deliberately produces **no probability estimate**. Nothing is
recorded to the ledger at this stage.

## Stage 2 — what needs judgment

The screen finds tradeable favorites. It cannot tell you whether anyone
actually knows the answer. That is the whole thesis, and it is judgment.

**The gating question.** Is there a specific, identifiable group of humans who
probably already know the outcome, while the public does not? Not "could
someone guess well" — *does a production crew, a board, a voting body, or a
reporter's source already know*.

Say yes for: pre-taped competition TV (finales, reunions, eliminations),
award winners after a small voting body has voted, product launches and
release dates known to supply chain and press, executive hires and firings,
M&A closings awaiting only a date, cabinet and judicial appointments,
pardons and executive orders with circulated drafts, coaching hires, and
anything resolving on a discretionary decision a small group has already made
but not announced.

Say no for: live sports and fights, any future price (stocks, crypto, FX,
commodities), weather, scheduled economic indicators computed later from data
not yet collected, live election-day outcomes, random draws, and anything
resolving on the aggregate behavior of many independent people.

**Reality TV is the strongest sub-case, and the screen cannot see it.** The
original classifier listed pre-taped competition TV as one item among twelve
equally-weighted YES examples. In practice it is not one among twelve — a
pre-taped show has a *known taping date*, a *large crew*, and an *active leak
community*, which is a far more concrete informed group than "reporters may
have sources." When a candidate is a pre-taped competition show, weight it
well above the flat prompt's treatment. This heuristic came from the user's
own trading, not from the pipeline. **If it keeps proving out in the endorsed
vs. rejected split, encode it in stage 1 as a ticker-family boost and bump the
version.**

**Do not estimate a probability.** Never answer "I think this is about 85%".
That number would be an anchor on the price you just read, not a belief.
Instead assign a **confidence bucket** from the scale below, and let
`tools/buckets.py` convert it using what that bucket has actually been worth.

**Judge blind to price.** Run the judgment on the market question and its
resolution rules *without* the price, mid, or spread in context. Reveal the
price afterwards and compute edge mechanically. Record `judged_blind=True`
when you do. The screen has already guaranteed the price is in a sane band,
so the judgment step does not need it.

**Warning signs that lower the bucket:** a vague insider story ("someone
probably knows"), resolution rules that differ from what the title implies, a
resolution source that may not publish before close, and — when you do look at
price data — momentum moving *away* from the favorite, which is informed flow
leaving.

**Recording.** Because edge depends on the bucket's measured rate, record after
judging:

```python
from tools import buckets, ledger, score
rates = score.bucket_rates(conn, "insider_bias", version)
edge, basis = buckets.edge_for(bucket, entry_price, rates, PRIORS)
opp_id, _ = ledger.record_opportunity(
    conn, ..., edge_pts_net=edge, edge_basis=basis,
    confidence=bucket, judged_blind=True,
)
ledger.interpret(conn, opp_id, "endorsed" if edge > 0 else "rejected", notes)
```

**Record the rejections too** — they are the control group that measures
whether this judgment is worth anything, and they are also what teaches the
`weak` bucket its rate. Candidates never reached within the scan budget are
reported as a count, not recorded.

## Confidence buckets

Priors are deliberately conservative and apply only until a bucket has 10+
settled results. After that the bucket's own realized win rate replaces them.

| bucket | meaning | prior edge (pts) |
|---|---|---|
| `strong` | A specific named group already knows — pre-taped show with a known taping date, a board that has voted, a signed deal awaiting announcement | 4.0 |
| `moderate` | A plausible informed group exists but is less specific — "reporters likely have sources" | 2.0 |
| `weak` | The thesis is a stretch; no concrete group identified | 0.0 |

**These priors are guesses and should be treated as placeholders.** The whole
point of the bucket mechanism is that they get replaced by measurement. If
`strong` turns out to be worth 9 points, the data will say so; if it turns out
to be worth nothing, the data will say that too — which is the outcome this
design most needs to be able to detect.

## How to backtest

**Tier B or C** — the decision path uses LLM judgment, so it is contaminated
on any market that resolved before the judging model's knowledge cutoff.

Prefer tier B: restrict replay to markets resolving after the cutoff, with
web search disabled. For tier C runs, use the contamination probe first — ask
a subagent the outcome with only the market question and no price data; if it
knows, discard that market.

The stage-1 screen alone is tier A and can be backtested over full history
using `tools/kalshi/history.py`. That measures whether the *filter* selects
markets that beat their price — useful on its own, and uncontaminated.

## Learnings

- 2026-08-23 — Ported from `kalshi_trader`. The reality-TV weighting is
  recorded here as a stage-2 heuristic rather than encoded, because it has not
  yet been measured against the endorsed/rejected split. Migrate it into
  stage 1 only once there is evidence.
````

- [ ] **Step 6: Commit**

```bash
git add theories/ tests/theories/
git commit -m "feat: port insider_bias as the reference theory"
```

---

### Task 5: Migrate the kalshi_trader track record

Imports real history so `insider_bias` starts with evidence rather than at zero. Applies the dedup rule — the source ledger contains repeat recommendations across runs, and importing them naively would import the exact duplication bug the design fixes.

**Files:**
- Create: `migrate_kalshi_trader.py`
- Create: `tests/test_migrate.py`

**Interfaces:**
- Consumes: `tools.db`, `tools.ledger`, `tools.theories`, `tools.score`
- Produces:
  - `migrate_kalshi_trader.parse_ledger_row(row: dict) -> dict | None`
  - `migrate_kalshi_trader.migrate(conn, ledger_rows: list[dict], scored_rows: list[dict] | None = None, now: str | None = None) -> dict` — returns `{"imported", "deduped", "settlements", "skipped"}`
  - `migrate_kalshi_trader.main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_migrate.py`:

```python
import pytest

import migrate_kalshi_trader as mig
from tools import db, ledger, score, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def _row(ticker="KXA", side="yes", price="0.80", q="0.90",
         ts="2026-06-01T12:00:00Z", rationale="insider story"):
    return {
        "ticker": ticker,
        "bet_side": side,
        "price": price,
        "q": q,
        "timestamp": ts,
        "rationale": rationale,
    }


def test_parse_extracts_the_core_fields():
    parsed = mig.parse_ledger_row(_row())
    assert parsed["kalshi_ticker"] == "KXA"
    assert parsed["outcome"] == "yes"
    assert parsed["entry_price"] == pytest.approx(0.80)
    assert parsed["model_prob"] == pytest.approx(0.90)


def test_parse_computes_net_edge_from_q_and_price():
    # q 0.90 vs price 0.80 = 10 points gross, minus the fee at 0.80
    parsed = mig.parse_ledger_row(_row(price="0.80", q="0.90"))
    assert parsed["edge_pts_net"] == pytest.approx(10.0 - 1.12, abs=0.01)


def test_parse_returns_none_without_a_ticker():
    assert mig.parse_ledger_row(_row(ticker="")) is None


def test_parse_returns_none_on_unparseable_price():
    assert mig.parse_ledger_row(_row(price="n/a")) is None


def test_parse_handles_integer_cent_prices():
    # The old schema stored cents; anything above 1 is cents, not dollars.
    parsed = mig.parse_ledger_row(_row(price="80", q="90"))
    assert parsed["entry_price"] == pytest.approx(0.80)
    assert parsed["model_prob"] == pytest.approx(0.90)


def test_migrate_imports_rows(conn):
    result = mig.migrate(conn, [_row("KXA"), _row("KXB")], now=TS)
    assert result["imported"] == 2
    assert len(ledger.list_opportunities(conn)) == 2


def test_migrate_registers_the_theory(conn):
    mig.migrate(conn, [_row()], now=TS)
    theory = theories.get(conn, "insider_bias")
    assert theory is not None
    assert theory["version"] == 1


def test_migrate_dedupes_repeat_recommendations(conn):
    # The source ledger appends the same bet on every run. One real bet.
    rows = [
        _row("KXA", ts="2026-06-01T12:00:00Z", price="0.80"),
        _row("KXA", ts="2026-06-02T12:00:00Z", price="0.85"),
        _row("KXA", ts="2026-06-03T12:00:00Z", price="0.88"),
    ]
    result = mig.migrate(conn, rows, now=TS)
    assert result["imported"] == 1
    assert result["deduped"] == 2

    rows_out = ledger.list_opportunities(conn)
    assert len(rows_out) == 1
    assert rows_out[0]["times_seen"] == 3


def test_migrate_keeps_the_earliest_entry_price(conn):
    rows = [
        _row("KXA", ts="2026-06-03T12:00:00Z", price="0.88"),
        _row("KXA", ts="2026-06-01T12:00:00Z", price="0.80"),
    ]
    mig.migrate(conn, rows, now=TS)
    row = ledger.list_opportunities(conn)[0]
    assert row["entry_price"] == pytest.approx(0.80), \
        "earliest sighting is the entry that was actually available"
    assert row["first_seen_at"] == "2026-06-01T12:00:00Z"


def test_migrate_treats_opposite_sides_as_distinct(conn):
    result = mig.migrate(
        conn, [_row("KXA", side="yes"), _row("KXA", side="no")], now=TS
    )
    assert result["imported"] == 2


def test_migrate_marks_rows_as_untouched_and_screened(conn):
    # The historical ledger records what was SUGGESTED. The user has said
    # they did not bet it as given, so nothing may be marked taken.
    mig.migrate(conn, [_row()], now=TS)
    row = ledger.list_opportunities(conn)[0]
    assert row["user_action"] == "untouched"
    assert row["disposition"] == "screened"


def test_migrate_preserves_original_timestamps(conn):
    mig.migrate(conn, [_row(ts="2026-06-01T12:00:00Z")], now=TS)
    row = ledger.list_opportunities(conn)[0]
    assert row["first_seen_at"] == "2026-06-01T12:00:00Z"


def test_migrate_imports_settlements(conn):
    mig.migrate(
        conn,
        [_row("KXA")],
        scored_rows=[{"ticker": "KXA", "result": "yes",
                      "resolved_at": "2026-06-15T00:00:00Z"}],
        now=TS,
    )
    result = score.compute_score(conn, "insider_bias", 1)
    assert result["n"] == 1
    assert result["win_rate"] == pytest.approx(1.0)


def test_migrate_skips_unparseable_rows(conn):
    result = mig.migrate(conn, [_row(), _row(ticker="")], now=TS)
    assert result["imported"] == 1
    assert result["skipped"] == 1


def test_migrate_is_rerunnable_without_duplicating(conn):
    mig.migrate(conn, [_row("KXA")], now=TS)
    mig.migrate(conn, [_row("KXA")], now=TS)
    assert len(ledger.list_opportunities(conn)) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_migrate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'migrate_kalshi_trader'`

- [ ] **Step 3: Write `migrate_kalshi_trader.py`**

```python
"""One-time import of kalshi_trader's real track record.

insider_bias should start with evidence rather than at zero, so its ledger
and scored results come across into the new schema.

The important part is the dedup. kalshi_trader appended a row every time a
run recommended a bet, so a market that stayed attractive for a week appears
five times. Importing that naively would import the exact duplication bug
this design exists to prevent — five rows for one real position, and a
calibration number that counts the same market five times. record_opportunity
upserts, so repeat rows collapse into one with times_seen incremented, and
rows are imported oldest-first so the surviving entry_price is the one that
was actually available at first sighting.

Usage:
    python migrate_kalshi_trader.py --source <path-to-kalshi_trader>
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import sys

from tools import db, ledger, score, theories
from tools.sizing import net_edge_pts

THEORY_ID = "insider_bias"
THEORY_NAME = "Insider Bias"
THEORY_PATH = "theories/insider_bias"


def _price(value: str | None) -> float | None:
    """Parse a price that may be decimal dollars or integer cents."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1.0:
        number = number / 100.0
    if not 0.0 <= number <= 1.0:
        return None
    return number


def _first(row: dict, *keys: str) -> str | None:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return None


def parse_ledger_row(row: dict) -> dict | None:
    """Convert a kalshi_trader ledger row into record_opportunity kwargs."""
    ticker = _first(row, "ticker", "market_ticker")
    if not ticker:
        return None

    entry_price = _price(_first(row, "price", "fav_price_exec", "fav_price"))
    if entry_price is None:
        return None

    model_prob = _price(_first(row, "q", "model_q", "blended_q"))
    # A historical row with no recorded q has no claimable edge. Record it at
    # zero rather than inventing one — it still counts toward calibration,
    # which is what the imported history is for.
    edge = (
        net_edge_pts(model_prob, entry_price) if model_prob is not None else 0.0
    )

    return {
        "kalshi_ticker": ticker,
        "outcome": (_first(row, "bet_side", "side") or "yes").lower(),
        "entry_price": entry_price,
        "model_prob": model_prob,
        "edge_pts_net": edge,
        "rationale": _first(row, "rationale", "reason"),
        "timestamp": _first(row, "timestamp", "created_at", "ts"),
    }


def migrate(
    conn,
    ledger_rows: list[dict],
    scored_rows: list[dict] | None = None,
    now: str | None = None,
) -> dict:
    """Import ledger rows and settlements. Returns a summary."""
    theories.register(conn, THEORY_ID, THEORY_NAME, THEORY_PATH,
                      status="active", now=now)

    parsed = []
    skipped = 0
    for row in ledger_rows:
        entry = parse_ledger_row(row)
        if entry is None:
            skipped += 1
            continue
        parsed.append(entry)

    # Oldest first, so the surviving entry_price is the one that was actually
    # available when this bet was first recommended.
    parsed.sort(key=lambda e: e["timestamp"] or "")

    imported = 0
    deduped = 0
    for entry in parsed:
        _, created = ledger.record_opportunity(
            conn,
            theory_id=THEORY_ID,
            theory_version=1,
            kalshi_ticker=entry["kalshi_ticker"],
            outcome=entry["outcome"],
            entry_price=entry["entry_price"],
            edge_pts_net=entry["edge_pts_net"],
            model_prob=entry["model_prob"],
            rationale=entry["rationale"],
            now=entry["timestamp"] or now,
        )
        if created:
            imported += 1
        else:
            deduped += 1

    settlements = 0
    for row in scored_rows or []:
        ticker = _first(row, "ticker", "market_ticker")
        result = _first(row, "result", "settlement_result", "outcome")
        if not ticker or not result:
            continue
        score.record_settlement(
            conn, ticker, str(result).lower(),
            resolved_at=_first(row, "resolved_at", "settled_at", "timestamp"),
        )
        settlements += 1

    return {
        "imported": imported,
        "deduped": deduped,
        "settlements": settlements,
        "skipped": skipped,
    }


def _read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True,
                        help="path to the kalshi_trader repo")
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)

    ledger_path = os.path.join(args.source, "ledger", "bets_ledger.csv")
    if not os.path.exists(ledger_path):
        print(f"no ledger at {ledger_path}", file=sys.stderr)
        return 1

    scored: list[dict] = []
    for path in sorted(
        glob.glob(os.path.join(args.source, "kalshi_data_backtest",
                               "scored_*.csv"))
    ):
        scored.extend(_read_csv(path))

    conn = db.connect(args.db) if args.db else db.connect()
    db.init_db(conn)
    try:
        summary = migrate(conn, _read_csv(ledger_path), scored)
    finally:
        conn.close()

    print(
        f"imported {summary['imported']} opportunities "
        f"({summary['deduped']} repeat sightings collapsed, "
        f"{summary['skipped']} unparseable rows skipped), "
        f"{summary['settlements']} settlements"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_migrate.py -v`
Expected: PASS — 15 passed

- [ ] **Step 5: Run the real migration**

```bash
python migrate_kalshi_trader.py --source "C:/Users/jbs00/OneDrive/Documents/Current_Work/kalshi/kalshi_trader"
```

Expected: a summary line reporting imported / collapsed / skipped counts. Inspect the result before trusting it:

```bash
python -m tools.cli opportunities list --theory insider_bias
python -m tools.cli score report insider_bias
```

If the collapsed count is zero, the source ledger's column names differ from what `parse_ledger_row` expects — check the CSV header and extend the `_first(...)` key lists rather than assuming there were no duplicates.

- [ ] **Step 6: Commit**

```bash
git add migrate_kalshi_trader.py tests/test_migrate.py
git commit -m "feat: migrate kalshi_trader track record with dedup"
```

---

### Task 6: The `go` and `find-edge` skills

**Files:**
- Create: `.claude/skills/go/SKILL.md`
- Create: `.claude/skills/find-edge/SKILL.md`
- Create: `RESEARCH_LOG.md`

- [ ] **Step 1: Write `.claude/skills/go/SKILL.md`**

````markdown
---
name: go
description: Run an autonomous research session — orient on current state, choose the highest-value work, do it, log it, and report. Use when the user says "go", or asks you to work on finding edge without specifying what to do.
---

# Autonomous Research Session

You are the researcher. Nobody is going to tell you what to test.

## 1. Orient (always, and cheaply)

```bash
python -m tools.cli theories list
python -m tools.cli opportunities list --disposition endorsed
python -m tools.cli ideas revisitable
```

Read the last ~30 lines of `RESEARCH_LOG.md` for what the previous session
was doing. For each active theory, `python -m tools.cli score report <id>`.

This is mechanical and costs almost nothing. Do it before deciding anything.

## 2. Choose where the value is

This is the judgment call that makes the session worth running. The standing
menu:

- **Settle and score** what has resolved (`score-theories`).
- **Hunt for live edge** with the active theories (`find-edge`).
- **Backtest** a theory running on claims rather than evidence
  (`backtest-theory`).
- **Propose a new theory** (`propose-theory`) — from a market pattern you
  noticed, a gap in what current theories cover, or a recurring `user_reason`
  divergence.
- **Revisit a parked or dead idea** whose `revisit_after` condition may now be
  met, or that carries a `revisit_angle` worth trying differently.
- **Tighten a theory** — migrate a stage-2 heuristic that keeps proving itself
  into stage 1 code (bump the version), or promote a theory-local tool that
  now has multiple callers.
- **Pause or retire** a theory the evidence has killed — and record why
  against its originating idea.

**Prefer work that changes a decision.** If nothing settled since yesterday,
re-scoring is busywork — go hunt. If every active theory is unproven, another
scan adds unproven suggestions while a backtest adds evidence. If the same
theory has been scanned three sessions running with nothing settled yet, the
marginal value is in a *new* theory, not a fourth scan of the old one.

State which you picked and why in one line, so the user can redirect cheaply.

A short session is fine. "Nothing settled, no theory needs backtesting, I
researched two candidates and rejected both, here's why" is a good outcome.
Do not manufacture work.

## 3. Log it

Append to `RESEARCH_LOG.md`:

```markdown
## YYYY-MM-DD — <one-line summary>

**Did:** what you actually did.
**Learned:** what you now know that you didn't.
**Next:** what is worth picking up next session.
```

Theory-specific findings also go in that theory's `THEORY.md` Learnings.
This log is what makes a year of sessions accumulate instead of repeat.

## 4. Report for a human

End with what the user needs: bets worth placing now, anything that changed
about a theory's standing, anything needing their judgment. Not a transcript
of tool calls.

## Rules

- Never present unresearched screen output as a recommended bet.
- Never retire a theory without recording why it failed against its idea.
- Search the idea registry before proposing anything new.
````

- [ ] **Step 2: Write `.claude/skills/find-edge/SKILL.md`**

````markdown
---
name: find-edge
description: Scan active theories for live opportunities, research the top candidates, and report a credibility-ranked list of the best bets. Use when the user asks what to bet, where the edge is, or what looks mispriced right now.
---

# Find Edge

Pipeline output is a **candidate set, not a recommendation**. Your job is to
narrow mechanically, then research, then rank honestly.

## 1. Select theories

Default to `status=active`, best-credibility first:

```bash
python -m tools.cli theories list --status active
python -m tools.cli score report <theory_id>
```

Honor a user scope override ("just insider_bias", "all theories").

## 2. Run each theory's stage 1

Open the theory's `THEORY.md` and follow its **Stage 1 — mechanical screen**
section. Fetch markets once and reuse across theories:

```python
from tools.kalshi import markets
board = markets.list_open()
```

Write snapshots as a side effect so history accrues:

```python
from tools import db, snapshot
conn = db.connect(); db.init_db(conn)
snapshot.save_kalshi(conn, board)
```

## 3. Filter for executability

Drop candidates that are not really takeable — spread too wide relative to
the claimed edge, or volume too thin to fill. **Report how many you dropped**
so nothing disappears silently.

## 4. Collapse duplicates across theories

If several theories surface the same ticker and side, that is **one bet with
corroboration**, not three bets. Merge them and note the agreement — it is a
genuine positive signal. Also flag when top candidates cluster on correlated
markets; a portfolio of correlated bets is not diversified.

## 5. Research the top candidates (stage 2)

Within your scan budget, research the highest-ranked candidates by following
the theory's **Stage 2** section. Batch this — tens of candidates per subagent
call, never one subagent per candidate.

**Never ask a subagent for a probability.** Ask for a classification, the
structural features the theory cares about, and a confidence bucket from the
theory's declared scale. A number an LLM introspects is mostly an anchor on
whatever price was in its context — see the theory's stage 2 section and spec
section 7.

**Judge blind to price where the theory allows it.** Send the market question
and resolution rules without the price; reveal it afterwards and compute edge
mechanically. Record `judged_blind=True`.

Convert the bucket to an edge using its measured track record, then record:

```python
from tools import buckets, ledger, score
rates = score.bucket_rates(conn, theory_id, version)
edge, basis = buckets.edge_for(bucket, entry_price, rates, theory_priors)
opp_id, _ = ledger.record_opportunity(
    conn, theory_id=..., theory_version=..., kalshi_ticker=...,
    outcome=..., entry_price=..., edge_pts_net=edge, edge_basis=basis,
    confidence=bucket, judged_blind=True, rationale=...,
)
ledger.interpret(conn, opp_id, "endorsed", "<your reasoning>")
```

**Record rejections too.** They are the control group that measures whether
your judgment is worth anything — and they are what teaches the lower buckets
their rates. Without them, neither the endorsed-vs-rejected comparison nor the
bucket calibration ever becomes possible.

## 6. Rank

Never sort on raw claimed edge. Use credibility shrinkage:

```bash
python -m tools.cli rank --edge <edge_pts_net> --n <settled_n> \
    --calibration-edge <cal> --mean-claimed-edge <claimed>
```

Use the theory's *endorsed* score row for realization when ranking an
endorsed opportunity.

## 7. Report in two layers

**Endorsed bets** — a table: ticker, side, entry price, confidence bucket,
claimed edge, **edge basis**, ranked edge, `n`, realization, theory, suggested
size, and your interpretation.

**Unresearched remainder** — a count, plus the top few by screen edge.

Always show claimed edge next to ranked edge, and always show the edge basis.
`prior` means the number is a placeholder nobody has measured yet; `measured`
means the bucket has earned it. If a theory has no track record, say so
plainly — a 12-point claim from a theory with `n=0` ranks as 3 points for a
reason, and the user should see why.

Rejected candidates and reasons are available on request.
````

- [ ] **Step 3: Create `RESEARCH_LOG.md`**

```markdown
# Research Log

Append-only. Newest entries at the bottom. One entry per research session.

This is what gives sessions continuity — read the tail before starting work,
append before finishing. Without it every session starts cold and the system
repeats itself instead of accumulating.

Format:

## YYYY-MM-DD — one-line summary

**Did:** what actually happened.
**Learned:** what you now know that you didn't.
**Next:** what is worth picking up next session.

---

## 2026-08-23 — Repo built

**Did:** Built the harness — data layer, tools, theory format, skills. Ported
`insider_bias` from `kalshi_trader` with its real track record.

**Learned:** Kalshi candlesticks carry historical bid/ask and reach back ~12
months, so tier A backtests can use executable prices. Kalshi's field schema
has changed since `kalshi_trader` (decimal-dollar strings, `_fp` sizes).
Polymarket exposes per-trade wallet identity and server-side size filtering.

**Next:** Nothing has settled under the new system yet. The highest-value work
is a tier A backtest of the `insider_bias` stage-1 screen — it is
uncontaminated, has a year of history available, and would give the first real
evidence in the ledger.
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/go .claude/skills/find-edge RESEARCH_LOG.md
git commit -m "feat: add go and find-edge skills"
```

---

### Task 7: The remaining four skills

**Files:**
- Create: `.claude/skills/propose-theory/SKILL.md`
- Create: `.claude/skills/backtest-theory/SKILL.md`
- Create: `.claude/skills/score-theories/SKILL.md`
- Create: `.claude/skills/compare-theories/SKILL.md`

- [ ] **Step 1: Write `.claude/skills/propose-theory/SKILL.md`**

````markdown
---
name: propose-theory
description: Formalize a new trading hypothesis into a theory folder, after checking it has not already been tried. Use when you have an idea worth testing, or the user asks for a new strategy.
---

# Propose a Theory

## 1. Check the research memory FIRST

Before any other work:

```bash
python -m tools.cli ideas search "<keyword>"
python -m tools.cli ideas search "<another keyword>"
```

Search several phrasings — the same idea wears different words.

- **Matches a `dead` idea?** Read its `outcome` and `revisit_angle`. Without a
  genuinely different angle, stop and tell the user it was tried and why it
  failed. Repeating a known dead end is the failure this registry exists to
  prevent.
- **Matches a `parked` idea?** Check `revisit_after`. If the condition is now
  met, this is high-value work — proceed and say why it is newly viable.
- **Matches a `promoted` idea?** The theory already exists. Improve it instead.

## 2. Record the idea

```bash
python -m tools.cli ideas record <slug> "<title>" \
    --description "<the hypothesis in a sentence or two>" \
    --source claude
```

Record it even if you end up dropping it — an idea investigated and abandoned
is exactly what a future session needs to know about.

## 3. Interrogate the hypothesis

- What mistake is the market making, and **why does it persist** rather than
  being arbitraged away? A thesis with no answer here is usually wrong.
- **What would falsify it?** Not what would confirm it. If you cannot state a
  result that would kill this theory, it is not testable.
- Which data sources? Does anything exist to support it?
- If the signal is not from Kalshi, how does it reach a Kalshi ticker?

## 4. Split stage 1 from stage 2

Explicitly decide what is mechanical and what needs judgment. Push as much as
possible into stage 1 — code is repeatable and free to run at scale. Be
concrete about stage 2: "check whether the resolution source publishes on a
schedule that can miss the close" is useful; "use good judgment" is not.

## 5. Scaffold

```bash
mkdir -p theories/<slug>
cp theories/_TEMPLATE/THEORY.md theories/<slug>/THEORY.md
python -m tools.cli theories register <slug> "<Name>" theories/<slug>
python -m tools.cli ideas status <idea-slug> promoted --theory-id <slug>
```

Fill in `THEORY.md` completely. Write any stage-1 code in the theory folder,
with tests. Theory-local code stays local until it earns promotion — see
`tools/README.md`.

## 6. Stay at `proposed`

A new theory does not become `active` until a tier A or B backtest shows
positive calibration edge, or the user explicitly overrides. Say what evidence
you would need to promote it.

## If you drop the idea instead

```bash
python -m tools.cli ideas status <slug> dead \
    --what-was-tried "<what you actually did>" \
    --outcome "<why it does not work>" \
    --revisit-angle "<what a different approach would look like, or omit>"
```

Omit `--revisit-angle` only if the idea is genuinely exhausted.
````

- [ ] **Step 2: Write `.claude/skills/backtest-theory/SKILL.md`**

````markdown
---
name: backtest-theory
description: Replay a theory against historical markets without lookahead bias, assigning a contamination tier. Use when a theory needs evidence, or the user asks how a strategy would have performed.
---

# Backtest a Theory

## 1. Determine the tier — derived, never self-reported

Two facts decide it:

1. Does the theory's decision path invoke LLM judgment? Read its `THEORY.md`.
2. Did the markets resolve before or after the judging model's knowledge
   cutoff?

| Tier | Condition | Trust |
|---|---|---|
| **A** | No LLM in the decision path | Full evidence, all history |
| **B** | LLM judgment, markets resolved *after* the cutoff, web search off | Valid, small sample |
| **C** | LLM judgment, markets resolved *before* the cutoff | Contaminated — indicative only |

A tier A backtest of a judgment theory's *screen alone* is often the best
available evidence: uncontaminated, and it measures whether the filter selects
markets that beat their price.

## 2. Enforce the rules

- **Web search must be off** in any backtest judgment subagent, every tier.
  Live search reveals historical outcomes trivially.
- Use `tools/kalshi/history.py` `point_in_time` for market state. It never
  returns a candle after your `as_of_ts` — that property is the basis of a
  lookahead-free replay.
- Price entries at the **historical ask** (`yes_ask_close`), not the mid.

## 3. Contamination probe (tier C only)

Before trusting any tier C result, per market: ask a subagent to state the
outcome given only the market question, with no price data. If it knows,
discard that market. This turns an unfalsifiable worry into a measurement and
can rescue genuinely obscure markets.

## 4. Run it

Record every replayed decision with `run_mode="backtest"` and a real `run_id`
(a uuid, not `"live"`), so dedup is per-run and results stay separable from
live. Record rejections as well as endorsements.

Insert a `backtest_runs` row with the tier, `uses_llm_judgment`, and the
`model_cutoff` you used.

## 5. Score and caveat

```bash
python -m tools.cli score report <theory_id> --run-mode backtest
```

Report the tier alongside every number. Tier C results are **excluded from
credibility** — never present them as evidence of edge, only as a sanity check
on the screening stage.
````

- [ ] **Step 3: Write `.claude/skills/score-theories/SKILL.md`**

````markdown
---
name: score-theories
description: Settle resolved opportunities and recompute calibration scores. Use when checking how recommendations performed, or as part of a research session.
---

# Score Theories

## 1. Find what has resolved

```python
from tools import db, ledger
from tools.kalshi import markets
conn = db.connect(); db.init_db(conn)
open_rows = [r for r in ledger.list_opportunities(conn)]
quotes = markets.quotes([r["kalshi_ticker"] for r in open_rows])
```

A Kalshi market is settled when its status is `finalized` and `result` is set.

## 2. Record settlements

```python
from tools import score
score.record_settlement(conn, ticker, result, resolved_at=...)
```

## 3. Recompute scores and bucket rates

```bash
python -m tools.cli score report <theory_id>
```

Then recompute what each confidence bucket is actually worth — this is what
replaces guessed probabilities with measured ones:

```python
rates = score.bucket_rates(conn, theory_id, version)
score.save_bucket_rates(conn, theory_id, version, rates)
```

Report any bucket that crossed 10 settled results: it has just graduated from
a declared prior to a measurement, which changes every future edge that theory
claims. If a bucket's measured rate is far from its prior, say so — a `strong`
bucket that turns out to be worth nothing is one of the most valuable findings
this system can produce, and the theory's priors in `THEORY.md` should be
updated to match reality.

The score report returns all four dispositions. The one that matters most:

```python
score.interpretation_value(conn, theory_id, version)
```

- **Positive delta** — interpretation is adding edge. The pipeline is a
  candidate generator; your judgment is the product.
- **Near zero** — interpretation adds nothing. Strengthen stage 1 or trust the
  pipeline and save the research time.
- **Negative** — interpretation is destroying value. Say so plainly.

It is `None` until both endorsed and rejected samples have settled.

## 4. Apply lifecycle flags

- `n = 20` with calibration edge ≤ 0 → flag for review.
- `n = 50` with calibration edge ≤ 0 → pause. **First check the disposition
  split**: a theory whose *endorsed* subset performs well while the overall
  screen does not is not dead, it needs a tighter stage 1.
- Retiring? Record why against the originating idea:
  ```bash
  python -m tools.cli ideas status <slug> dead \
      --outcome "<why it failed>" --revisit-angle "<or omit>"
  ```

## 5. Report both ROI numbers

`roi_all` is hypothetical — it assumes every suggestion was taken. `roi_taken`
is real money. Never present the first as if it were the second.
````

- [ ] **Step 4: Write `.claude/skills/compare-theories/SKILL.md`**

````markdown
---
name: compare-theories
description: Compare theories by demonstrated performance, including whether interpretation adds value and what user divergences suggest. Use when asked which strategy works best or how theories stack up.
---

# Compare Theories

## 1. Gather

```bash
python -m tools.cli theories list
python -m tools.cli score report <id>   # for each
```

## 2. Keep separate what is different

- **Versions.** A v1 and v2 track record are different theories. Never merge.
- **Live vs. backtest.** Never blend.
- **Tier C backtests.** Mark clearly; excluded from credibility.
- **Small `n`.** Below 20 settled, say so beside every number. Below 10, the
  theory is on probation and its credibility is a floor, not a measurement.

## 3. Rank on demonstrated edge

Sort by `calibration_edge` with `n` shown, not by claimed edge. Include
`realization` — how much of what a theory claimed it actually delivered. A
theory claiming 10 points and realizing 2 is worse than one claiming 3 and
realizing 3.

## 4. Report the interpretation-value breakdown

For each theory, endorsed vs. rejected vs. all. This is often the most
actionable number in the system: it says whether the research step is earning
its cost.

## 5. Mine divergences for new theories

```python
rows = ledger.list_opportunities(conn)
reasons = [(r["user_action"], r["user_reason"]) for r in rows
           if r["user_reason"]]
```

Where the user took something you did not endorse, or skipped something you
did, the reason usually encodes an unwritten heuristic. Recurring patterns are
candidate theories — run `propose-theory` on them (which will check the idea
registry first).

This is one of the most direct routes from tacit intuition to a testable
theory.
````

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/
git commit -m "feat: add theory lifecycle skills"
```

---

### Task 8: CLAUDE.md and end-to-end verification

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write `CLAUDE.md`**

````markdown
# Market Edge Finder

You are the researcher here. This repo gives you tools to find Kalshi markets
with the largest edge — and expects you to come up with your own ideas about
where that edge is, rather than waiting to be told.

## Mission

Find Kalshi markets with a real, evidence-backed edge. Invent hypotheses, test
them, kill the ones that fail, and accumulate a track record that makes "this
is the best bet available" a claim with proof behind it.

## What ships here — and what doesn't

No fixed strategy ships. One reference theory (`insider_bias`, ported from an
earlier project with its real history) exists to prove the harness works.
Everything else is yours to propose. Two ideas that motivated this project —
research-driven forecast-gap bets, and copying Polymarket whale activity into
equivalent Kalshi markets — are illustrations of the *kind* of idea to
generate, not a backlog to implement.

## Platform roles

**Kalshi is where bets get placed.** The user can only wager there.
**Polymarket is an equally first-class research tool** — it exposes per-trade
wallet identity and holder positions that Kalshi does not.

**Every suggestion must resolve to a specific Kalshi ticker.** A
Polymarket-sourced finding is not an opportunity until `tools/match_market.py`
gives you candidates and you confirm a match — comparing *resolution criteria*,
not just topic. `record_opportunity` enforces this: no Kalshi ticker, no
record.

## How the user drives this

- **`go`** — an autonomous research session. Orient, choose the highest-value
  work, do it, log it, report.
- **Just asking** — "how is insider_bias holding up?", "what's the best bet
  right now?" Answer directly with the tools. No loop, no ceremony.

Both are normal.

## Pipelines propose, judgment disposes

The aspiration is a deterministic pipeline: run it, get a bet with an edge.
Push toward that — anything encoded in code is repeatable and scales for free.

The reality is that pipeline output is a **candidate set, not a
recommendation**. `insider_bias` is the worked example: its picks are not bet
as given. A human reads the output and recognizes that a reality-TV market is
structurally vulnerable in a way the screen never encoded. The edge lives
partly in the pipeline and partly in the pattern recognition applied to it.

So every theory has two stages: a **mechanical screen** and **interpretive
judgment**. Never present unresearched screen output as a recommended bet.

**Record your rejections.** Every opportunity carries a `disposition` —
`screened`, `endorsed`, or `rejected`. Rejected candidates still settle, which
makes them a free control group. That is the only way to find out whether your
judgment adds edge, adds nothing, or destroys value.

## Never state a probability you introspected

You are not a calibrated probability estimator. You cluster on round numbers,
drift with phrasing, and — the real problem — anchor hard on any number already
in your context. Asked for `q` while looking at a price of 0.80, you will
produce something near 0.80 and it will feel like analysis. It is not.

So this system never asks you for one. Instead:

- **Classify** against a stated definition — "is there a specific identifiable
  group who already knows?"
- **Extract structural features** — is it pre-taped, do the rules diverge from
  the title, can the resolution source miss the close.
- **Assign a confidence bucket** from the theory's declared scale.
- **Rank** candidates against each other.

Then `tools/buckets.py` turns that bucket into a number using the bucket's own
realized win rate. "When this theory says `strong`, it wins 78% of the time" is
a fact; your felt sense of 78% is not.

**Judge blind to price wherever the theory allows it.** Get the classification
first, reveal the price second, compute edge mechanically. Record
`judged_blind=True`. This costs nothing and removes the largest contaminant.

Every recorded edge carries an `edge_basis`: `measured` (the bucket earned it),
`model` (a mechanical calculation), or `prior` (a placeholder awaiting data).
There is deliberately no basis meaning "it felt about right".

**Mechanical probabilities are welcome.** The objection is to introspection,
not arithmetic. A theory computing a probability from base rates, a Poisson
process, or sibling-strike monotonicity should absolutely do so — that is
reproducible and auditable, it records as `model`, and it backtests at tier A.
A theory resting on a mechanical model is generally *stronger* than one resting
on judgment.

## Research memory

Search the idea registry **before** proposing anything:

```bash
python -m tools.cli ideas search "<keyword>"
```

Record every idea you consider, including ones you drop, with what you
actually tried and why it did not work. Write a `revisit_angle` — the
difference between "don't try this again" and "don't try this again *the same
way*" — rather than closing a door permanently. Never retire a theory without
recording why it failed.

## How ranking works

Claimed edge is shrunk toward demonstrated edge:

```
ranked_edge = edge_pts_net × credibility
credibility = 0.25                          if n < 10   (probation)
            = (n / (n + 20)) × realization  if n >= 10
```

A new theory claiming 12 points ranks as 3 — visible, not dominant. A theory
measured at n=40 that delivered nothing ranks at zero; the floor does not
protect a theory that has been tested and found wanting. Show claimed and
ranked edge side by side. Do not game this.

## Toolkit

`python -m tools.cli --help` for the command line. See `tools/README.md` for
conventions and the full map. Highlights:

- `tools/kalshi/markets.py` — open/settled markets, quotes, resolution rules
- `tools/kalshi/history.py` — candlesticks with historical bid/ask, ~12 months
- `tools/polymarket/markets.py`, `trades.py` — markets, whales, holders
- `tools/match_market.py` — non-Kalshi finding → Kalshi ticker shortlist
- `tools/ledger.py` — the opportunity contract
- `tools/score.py` — calibration, ROI, interpretation value
- `tools/rank.py`, `tools/sizing.py` — ranking and Kalshi fee/Kelly math
- `tools/snapshot.py` — first-party history

**New code starts in the theory that needs it** and moves to `tools/` only
once it has more than one real caller. That is a judgment call, not an
automatic rule.

## Theory lifecycle and versioning

`proposed` → `active` (needs a tier A/B backtest with positive calibration
edge) → review at `n=20` if edge ≤ 0 → `paused` at `n=50` → `retired`.

**Any change to a theory's decision procedure bumps its version.** Thresholds,
prompts, scan logic, or migrating a stage-2 heuristic into stage-1 code.
Without this, tweaking a theory silently merges two different theories into
one track record — which destroys the long-horizon testing this project exists
for and invites tuning until the history looks good.

## Backtest tiers

- **A** — no LLM in the decision path. Full evidence, all history.
- **B** — LLM judgment, markets resolved after the model's knowledge cutoff,
  web search off. Valid but small.
- **C** — LLM judgment on pre-cutoff markets. Contaminated; excluded from
  credibility. Use the contamination probe before trusting anything from it.

Web search stays off in every backtest judgment subagent.

## Subagents

Spawn subagents for judgment: does this market fit the thesis, which
candidates are best, are these two markets really the same. **Batch them** —
tens of candidates per call, never one subagent per candidate. This runs on
the user's Claude subscription; there are no API keys anywhere in this repo,
and none should be added.

## Data conventions

- **SQLite** (`db/market_edge.db`) is the source of truth for structured facts.
- **`THEORY.md`** is the source of truth for a hypothesis and its procedure.
- **`RESEARCH_LOG.md`** carries continuity between sessions — read its tail
  when starting, append when finishing.
- Prices are decimal dollars in [0, 1]. Edge is in percentage points. Entry
  prices are the **ask** you would actually pay, never the mid. Timestamps are
  UTC ISO-8601.

## Getting started

Say `go` for a research session, or just ask a question.
````

- [ ] **Step 2: Run the full offline suite**

Run: `python -m pytest -m "not network" -v`
Expected: PASS — 239 passed (191 from Plans 1–2, plus 14 cli + 19 insider_bias screen + 15 migrate)

- [ ] **Step 3: Verify the CLI end to end**

```bash
python -m tools.cli init
python -m tools.cli theories list
python -m tools.cli score report insider_bias
python -m tools.cli ideas search whale
```

Expected: valid JSON from each. `theories list` shows `insider_bias` as
`active` with imported history.

- [ ] **Step 4: Dry-run `find-edge`**

Follow `.claude/skills/find-edge/SKILL.md` against the live board, limited to
`insider_bias`. Verify that it fetches markets, screens them, reports how many
candidates survived and how many were dropped for executability, records both
endorsements and rejections, and ranks with credibility shrinkage visible
beside claimed edge.

This is the acceptance test for the whole system. If the report presents
unresearched screen output as recommended bets, or omits the shrinkage, fix
the skill.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md briefing"
```

---

## Definition of done for Plan 3

- `python -m pytest -m "not network"` passes with no failures.
- `python -m tools.cli --help` lists every command, and each emits valid JSON.
- `insider_bias` is registered `active`, with imported `kalshi_trader` history — and the migration's dedup collapsed repeat recommendations rather than importing them as separate bets.
- `theories/_TEMPLATE/THEORY.md` makes clear that a theory's shape is its own, with `record_opportunity` as the only contract.
- All six skills exist with frontmatter, and `find-edge` reports endorsed bets separately from the unresearched remainder.
- `CLAUDE.md` covers mission, platform roles, both operating modes, the two-stage model, research memory, ranking, lifecycle, tiers, subagents, and data conventions.
- A `find-edge` dry run produces a ranked report with claimed and ranked edge side by side, and records rejections as well as endorsements.
