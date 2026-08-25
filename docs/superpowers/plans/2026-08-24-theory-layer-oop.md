# Theory-Layer OOP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every theory becomes an object a subagent can be handed and run start-to-finish, returning one uniform `ScanResult` — two required methods, everything else defaulted, nothing that exists today lost.

**Architecture:** Characterization goldens lock current behavior first (Phase 0), then the layers land bottom-up: frozen value types in `tools/domain.py` with a temporary dict-compatibility shim, the platform clients return typed values through an injectable transport, the `Theory`/`TheoryRun`/`TheoryContext` contract wraps the two existing theories as adapters, discovery joins code to the DB registry, docs are rewritten, and only then are theory internals ported and the shim deleted. Every phase is independently green and independently revertible.

**Tech Stack:** Python 3 stdlib (`dataclasses`, `abc`, `sqlite3`, `importlib`), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-24-theory-layer-oop-design.md` — the plan argues from the spec; read both. Sections cited as (spec §N).

## Global Constraints

- **No functionality may regress (spec §3.1).** The existing suite passes at every task with no test deleted, skipped, or weakened. Exception, stated in advance: Tasks 12–14 change the *input types* of theory-internal functions, so existing tests in `tests/theories/` may update **object construction only** — every assertion stays byte-identical, and the characterization goldens are the proof of behavior identity. Any assertion that must change is an escalation, not an edit.
- **Golden files are immutable after Task 0.** A golden diff is a behavior change: fix the code or escalate to the user as a version-bump decision (spec §8.2). Never regenerate.
- **No version bump for either theory.** `insider_judgment` stays 3, `mention_family` stays 1. Thresholds, prompts, gate categories, bucket boundaries, and screen predicates are frozen (spec §3.4).
- **A `Verdict` carries no number.** The judge classifies; probabilities come from measured bucket rates (`buckets.edge_for`) or a mechanical model. No field named like a probability, confidence-percent, or edge may ever be added to `Verdict` — a conventions test enforces this.
- **Prices are decimal dollars in [0, 1]; edge in percentage points; entry prices are the ask, never the mid; timestamps UTC ISO-8601.**
- **No credentials, no API keys.** All endpoints are public.
- Run tests with `python -m pytest -m "not network" -q` (the `network` marker deselects live calls). Windows environment: invoke Python as `python`, paths with forward slashes work in Git Bash.
- Commit after every task with the message given in that task.

## Preconditions

The multi-leg positions plan (`docs/superpowers/plans/2026-08-24-multi-leg-positions.md`) executes **first** and is in progress on this branch (`feat/multi-leg-positions`; Task 1 landed as commit `36e0760`). **Do not start this plan until it is complete.** Verify:

```bash
python -m pytest tests/test_baskets.py -q          # exists and passes
python -c "from tools.ledger import record_basket, get_legs, basket_key"
```

If either fails, stop and report — this plan consumes `record_basket` in Task 6.

## Decisions locked in during planning

These resolve the spec's open questions and close gaps found while auditing the code. Implementers follow them; do not re-litigate silently.

1. **`Market` carries `last_price` and `volume_24h`** beyond the spec §4.1 field list. Forced by non-regression: `tests/kalshi/test_markets.py:29` asserts `m["last_price"]`, and `normalize()` emits both today. `Market`'s fields mirror `normalize()`'s dict keys exactly — 22 fields including `raw`.
2. **Polymarket gets its own `PolymarketMarket` type** (spec open question 2, resolved via its sanctioned fallback: "a separate type is acceptable and better than a lossy union"). Same field names as today's dict — no renaming — so `snapshot.save_polymarket` and `match_market.py` keep working through the shim. `outcomes`/`outcome_prices` stay `list`, not `tuple`, so existing equality assertions hold.
3. **Backtest path (spec open question 3), assessed:** `replay_market` (`theories/insider_bias/insider_judgment/backtest.py:232-241`) hand-builds a point-in-time `market_view` dict and never calls `normalize()`. Resolution: it constructs a `Market` directly in Task 12. `point_in_time`/`candlesticks` return candle dicts, not markets — out of scope, unchanged.
4. **`Candidate` gains `max_payout: float = 1.0`.** The multi-leg spec makes `max_payout` a caller declaration on `record_basket`; a basket `Candidate` is that caller, so the declaration rides on the position. Harmless default for singles.
5. **`theory_facts` is schema + provenance stage only — no Python API yet.** No current theory keeps facts; the five pair-store theories are backlog. The round-trip test uses SQL. The first pair-store theory adds the helper functions (YAGNI, per `tools/README.md`'s promotion rule).
6. **`judgment_runs` needs a table rebuild** to accept `stage='construction'`: its CHECK constraint is baked into existing databases, so Task 3 adds a `_migrate_judgment_runs` following the `_migrate_theories` pattern in `tools/db.py`.
7. **`finish()` records provenance for any theory with a non-empty `prompts` ClassVar**, not only `uses_llm_judgment` ones — model defaults to `"none (deterministic)"` for a mechanical theory. This preserves `mention_family`'s voluntary self-documentation (its `record_provenance`) through the generic path, and correctly skips it on `dry_run`.
8. **The shim-containment conventions test is a source grep with an explicit allowlist** of modules still using dict-style access on domain objects. Tasks 12–14 shrink the allowlist; Task 14 empties it and deletes the shim. This is the mechanically checkable form of spec §4.2's "exercised only from listed modules".
9. **`check_drift` checks the class side unconditionally and the DB side only for `SCANNABLE_STATUSES` rows** — a `proposed` or `paused` registry row legitimately has no code yet. Current DB state (verified 2026-08-24): exactly `insider_judgment` (v3, testing, uses_llm=1) and `mention_family` (v1, testing, uses_llm=0); no legacy rows.
10. **insider_judgment's bucket scale and priors** are lifted verbatim from `THEORY.md` ("Confidence buckets" table): `strong` 4.0, `moderate` 2.0, `weak` 0.0. Copying prose into constants is encoding, not changing — but any deviation from that table is a version-bump escalation.
11. **Goldens are compared through a canonical projection** (`proj()` in the characterization conftest). Golden JSON never changes; `proj()` grows branches as domain types appear (dict → itself; `Market` → `asdict`; `Candidate` → the flattened legacy candidate dict; `ScoredCandidate` → flattened + `edge_pts_net`/`edge_basis`/`bucket`). The projection lives in the harness, not the code under test.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `tests/characterization/` (`build_fixture.py`, `generate_goldens.py`, `conftest.py`, `test_goldens.py`, `fixtures/`, `goldens/`) | Behavior lock for the whole migration | Create (Task 0) |
| `tools/domain.py` | All frozen value types + `Fetch` protocol + shim | Create (Tasks 1–2) |
| `db/schema.sql`, `tools/db.py`, `tools/provenance.py` | `theory_facts` table, `construction` stage, CHECK migration | Modify (Task 3) |
| `tools/kalshi/markets.py`, `tools/board.py`, `tools/snapshot.py` | `normalize() -> Market`, `fetch` seam | Modify (Task 4) |
| `tools/polymarket/markets.py` | `normalize() -> PolymarketMarket`, `fetch` seam | Modify (Task 5) |
| `tools/theory.py` | `Theory` ABC, `TheoryRun`, `TheoryContext` | Create (Task 6) |
| `theories/insider_bias/insider_judgment/theory.py` + `__init__.py`; `pipeline.py` | Adapter + `survivor_candidates` key | Create/Modify (Task 7) |
| `theories/insider_bias/mention_family/theory.py` + `__init__.py` | Adapter | Create (Task 8) |
| `tools/registry.py` | Discovery, `running()`, `check_drift` | Create (Task 9) |
| `tests/test_parallel_writes.py`, `tests/test_backlog_fit.py`, `tests/test_theory_facts.py` | Cross-cutting proofs | Create (Tasks 3, 10) |
| `tools/README.md`, `CLAUDE.md`, `.claude/skills/{find-edge,propose-theory,go,backtest-theory}/SKILL.md` | Conventions rewrite | Modify (Task 11) |
| `theories/insider_bias/screen.py`, `insider_judgment/{gate,pipeline,backtest}.py` | Native `Market`/`Candidate` port | Modify (Task 12) |
| `theories/insider_bias/mention_family/mention_bucket.py`, `tools/match_market.py`, `tools/snapshot.py`, `tools/board.py` | Native port of remaining consumers | Modify (Task 13) |
| `tools/domain.py`, `tests/test_conventions.py` | Shim deletion, empty allowlist, final sweep | Modify (Task 14) |

---

### Task 0: Characterization harness (Phase 0)

**Files:**
- Create: `tests/characterization/__init__.py` (empty), `tests/characterization/build_fixture.py`, `tests/characterization/generate_goldens.py`, `tests/characterization/conftest.py`, `tests/characterization/test_goldens.py`
- Create (generated, committed): `tests/characterization/fixtures/board_sample.json`, `tests/characterization/fixtures/meta.json`, `tests/characterization/goldens/*.json`

**Interfaces:**
- Consumes: `board.get_board`, `screen.screen`, `pipeline.*`, `gate.partition`, `mention_bucket.*`, `backtest.systematic_sample`, `kalshi.markets.normalize` — all current code, unchanged.
- Produces: `conftest.proj(x)`, `conftest.board_input()`, `conftest.frozen_now()`, `conftest.frozen_rates()`, `conftest.load_golden(name)` — every later task's regression oracle.

**No production code changes in this task.** Phase 0 gates everything (spec §6).

- [ ] **Step 1: Write the fixture builder**

Create `tests/characterization/build_fixture.py`:

```python
"""Build the characterization fixture from the live board. Run ONCE, at
Phase 0, from the repo root, with network access:

    python -m tests.characterization.build_fixture

Contents: every market that survives screen.screen() (so the goldens cover
every candidate the current code produces) plus a systematic sample of
2,000 non-survivors (reject paths and every gate.classify category),
deduped, sorted by ticker, written with sort_keys=True. The frozen `now`
is the pull moment; frozen bucket rates come from the live DB
(mention_family's measured backtest rates). generate_goldens.py then works
from this file alone -- no network, no DB, forever reproducible.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from theories.insider_bias import screen
from theories.insider_bias.insider_judgment.backtest import systematic_sample
from theories.insider_bias.mention_family import mention_bucket
from tools import board as board_tool, db

FIXTURES = Path(__file__).parent / "fixtures"


def main() -> None:
    conn = db.connect()
    db.init_db(conn)
    board = board_tool.get_board(conn, force=True)   # the one deliberate pull
    frozen_now = db.utcnow()
    now_dt = datetime.fromisoformat(frozen_now.replace("Z", "+00:00"))

    survivor_tickers = {c["ticker"] for c in screen.screen(board, now=now_dt)}
    keep = [m for m in board if m["ticker"] in survivor_tickers]
    rest = [m for m in board if m["ticker"] not in survivor_tickers]
    keep += systematic_sample(rest, 2000)

    by_ticker = {m["ticker"]: m for m in keep}
    fixture = [by_ticker[t] for t in sorted(by_ticker)]

    FIXTURES.mkdir(exist_ok=True)
    (FIXTURES / "board_sample.json").write_text(
        json.dumps(fixture, sort_keys=True, indent=1), encoding="utf-8"
    )
    (FIXTURES / "meta.json").write_text(
        json.dumps(
            {"frozen_now": frozen_now,
             "full_board_size": len(board),
             "rates": mention_bucket.measured_rate(conn)},
            sort_keys=True, indent=1,
        ),
        encoding="utf-8",
    )
    print(f"fixture: {len(fixture)} markets, frozen_now={frozen_now}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it once**

Run: `python -m tests.characterization.build_fixture`
Expected: prints a fixture size of roughly 2,000–3,000 markets. This performs one full board pull (~13s). If the pull fails, retry; do not hand-edit the output.

- [ ] **Step 3: Write the conftest with the canonical projection**

Create `tests/characterization/conftest.py`:

```python
"""Shared loaders and the canonical projection (plan decision 11).

Goldens are stored as JSON. Live values are projected to the same JSON
before comparison: a dict projects as itself; the domain dataclasses that
appear from Task 1 onward project to the legacy dict shapes they replace.
The golden files NEVER change after Task 0; this projection grows branches.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
GOLDENS = HERE / "goldens"


def load_fixture() -> list[dict]:
    return json.loads((FIXTURES / "board_sample.json").read_text("utf-8"))


def _meta() -> dict:
    return json.loads((FIXTURES / "meta.json").read_text("utf-8"))


def frozen_now() -> datetime:
    return datetime.fromisoformat(_meta()["frozen_now"].replace("Z", "+00:00"))


def frozen_rates() -> dict:
    return _meta()["rates"]


def board_input() -> list:
    """The fixture in whatever shape the current screen consumes.

    Until Task 12 the screen reads dicts, so this returns the fixture as-is.
    Task 12 switches it to construct domain.Market objects. The golden
    files are untouched by that switch; proj() guarantees comparability.
    """
    return load_fixture()


def load_golden(name: str):
    return json.loads((GOLDENS / f"{name}.json").read_text("utf-8"))


def dump_golden(name: str, value) -> None:
    GOLDENS.mkdir(exist_ok=True)
    path = GOLDENS / f"{name}.json"
    if path.exists():
        raise RuntimeError(
            f"golden {name} already exists. Goldens are immutable after "
            "Phase 0: a diff is a behavior change to fix or escalate, "
            "never a file to regenerate (spec section 8.2)."
        )
    path.write_text(json.dumps(proj(value), sort_keys=True, indent=1),
                    encoding="utf-8")


def proj(x):
    try:
        from tools import domain
    except ImportError:
        domain = None
    if domain is not None:
        if isinstance(x, domain.ScoredCandidate):
            return {**proj(x.candidate), "edge_pts_net": x.edge.pts_net,
                    "edge_basis": x.edge.basis, "bucket": x.confidence}
        if isinstance(x, domain.Candidate):
            leg = x.legs[0]
            return {**proj(leg.market), "fav_side": leg.side,
                    "entry_price": leg.price,
                    "days_to_close": x.days_to_close}
        if isinstance(x, domain.Market):
            from dataclasses import asdict
            return proj(asdict(x))
    if isinstance(x, dict):
        return {k: proj(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [proj(v) for v in x]
    return x
```

(Note: `conftest.py` here is used as a plain importable module by the tests via `from tests.characterization import conftest` — import it explicitly rather than relying on pytest injection, so `generate_goldens.py` can use it too.)

- [ ] **Step 4: Write the golden generator**

Create `tests/characterization/generate_goldens.py`:

```python
"""Generate every golden from the committed fixture. Run ONCE at Phase 0:

    python -m tests.characterization.generate_goldens

Refuses to overwrite (see conftest.dump_golden). No network, no DB.
"""

from __future__ import annotations

from theories.insider_bias import screen
from theories.insider_bias.insider_judgment import gate, pipeline
from theories.insider_bias.mention_family import mention_bucket
from tools.kalshi import markets
from tests.characterization import conftest as cz


def main() -> None:
    board = cz.board_input()
    now = cz.frozen_now()
    rates = cz.frozen_rates()

    candidates = screen.screen(board, now=now)
    cz.dump_golden("screen", candidates)

    events = pipeline.dedupe_by_event(candidates)
    cz.dump_golden("dedupe_by_event", events)

    survivors, counts = gate.partition(events)
    cz.dump_golden("gate_partition",
                   {"survivors": survivors, "counts": counts})

    survivor_keys = {s.get("event_ticker") or s.get("ticker")
                     for s in survivors}
    kept = [c for c in candidates
            if (c.get("event_ticker") or c.get("ticker")) in survivor_keys]
    cz.dump_golden("blind_payload",
                   pipeline.build_blind_payload(survivors, kept))

    cz.dump_golden("run_mechanical_stages",
                   pipeline.run_mechanical_stages(board, now))

    family = mention_bucket.find_candidates(board, now=now)
    cz.dump_golden("mention_find_candidates", family)
    cz.dump_golden("mention_rank", mention_bucket.rank(family, rates))

    cz.dump_golden("normalize",
                   {m["ticker"]: markets.normalize(m["raw"])
                    for m in cz.load_fixture()})


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the generator**

Run: `python -m tests.characterization.generate_goldens`
Expected: eight files appear under `tests/characterization/goldens/`.

- [ ] **Step 6: Write the golden tests**

Create `tests/characterization/test_goldens.py`:

```python
"""The pass condition for every phase of the OOP migration (spec section 7).

Whole-value equality everywhere except run_mechanical_stages, which is a
subset match on its Phase-0 keys: Task 7 is licensed to ADD the
survivor_candidates key, and only to add (spec section 4.7).
"""

from __future__ import annotations

from theories.insider_bias import screen
from theories.insider_bias.insider_judgment import gate, pipeline
from theories.insider_bias.mention_family import mention_bucket
from tools.kalshi import markets
from tests.characterization import conftest as cz


def test_screen_matches_golden():
    got = screen.screen(cz.board_input(), now=cz.frozen_now())
    assert cz.proj(got) == cz.load_golden("screen")


def test_dedupe_matches_golden():
    candidates = screen.screen(cz.board_input(), now=cz.frozen_now())
    got = pipeline.dedupe_by_event(candidates)
    assert cz.proj(got) == cz.load_golden("dedupe_by_event")


def test_gate_partition_matches_golden():
    candidates = screen.screen(cz.board_input(), now=cz.frozen_now())
    survivors, counts = gate.partition(pipeline.dedupe_by_event(candidates))
    want = cz.load_golden("gate_partition")
    assert cz.proj(survivors) == want["survivors"]
    assert cz.proj(counts) == want["counts"]


def test_blind_payload_matches_golden():
    candidates = screen.screen(cz.board_input(), now=cz.frozen_now())
    survivors, _ = gate.partition(pipeline.dedupe_by_event(candidates))
    keys = {s.get("event_ticker") or s.get("ticker") for s in survivors}
    kept = [c for c in candidates
            if (c.get("event_ticker") or c.get("ticker")) in keys]
    got = pipeline.build_blind_payload(survivors, kept)
    assert cz.proj(got) == cz.load_golden("blind_payload")


def test_run_mechanical_stages_subset_matches_golden():
    got = cz.proj(pipeline.run_mechanical_stages(cz.board_input(),
                                                 cz.frozen_now()))
    for key, want in cz.load_golden("run_mechanical_stages").items():
        assert got[key] == want, f"funnel key {key!r} changed"


def test_mention_family_matches_goldens():
    family = mention_bucket.find_candidates(cz.board_input(),
                                            now=cz.frozen_now())
    assert cz.proj(family) == cz.load_golden("mention_find_candidates")
    got = mention_bucket.rank(family, cz.frozen_rates())
    assert cz.proj(got) == cz.load_golden("mention_rank")


def test_normalize_matches_golden_for_every_fixture_row():
    want = cz.load_golden("normalize")
    for row in cz.load_fixture():
        assert cz.proj(markets.normalize(row["raw"])) == want[row["ticker"]]
```

- [ ] **Step 7: Run the characterization suite and the full suite**

Run: `python -m pytest tests/characterization -q`
Expected: PASS (7 tests).

Run: `python -m pytest -m "not network" -q`
Expected: All PASS.

Caveat to verify here, not assume: `screen.screen` compares `days >= 0` against the frozen `now`, and every path above passes `now` explicitly — nothing in the harness may read the wall clock. If any golden test is time-sensitive, that is a bug in the harness; fix it now.

- [ ] **Step 8: Commit**

```bash
git add tests/characterization
git commit -m "test: characterization fixture and goldens lock current behavior (OOP phase 0)"
```
