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


def event_key(c) -> str:
    """Event identity of a screen candidate, dict- and domain-shaped.

    Phase 0 candidates are dicts; from Task 12 they are domain.Candidate.
    Harness plumbing handles both so the golden FILES never change.
    """
    if isinstance(c, dict):
        return c.get("event_ticker") or c.get("ticker")
    return c.key


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
    keys = {cz.event_key(s) for s in survivors}
    kept = [c for c in candidates if cz.event_key(c) in keys]
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

---

### Task 1: Domain value types — `tools/domain.py` (Phase 1a)

**Files:**
- Create: `tools/domain.py`
- Test: `tests/test_domain.py`

**Interfaces:**
- Consumes: `tools.buckets.edge_for(bucket, entry_price, rates, priors) -> tuple[float, str]` (existing, unchanged).
- Produces: `Fetch` (Protocol), `Market`, `PolymarketMarket`, `Leg`, `Candidate`, `Edge`, `Verdict`, `ScoredCandidate`, `ScreenResult`, `ScanResult` — every later task's vocabulary. Exact definitions below; later tasks use these names and signatures verbatim.

- [ ] **Step 1: Write the failing test**

Create `tests/test_domain.py`:

```python
import math
from dataclasses import FrozenInstanceError, fields

import pytest

from tools import domain
from tools.domain import (Candidate, Edge, Leg, Market, ScoredCandidate,
                          ScreenResult, Verdict)


def mk(ticker="KXT-26", **over):
    base = dict(platform="kalshi", ticker=ticker, title="t", yes_ask=0.8,
                no_ask=0.25, mid=0.78, spread=0.04, volume=900.0,
                is_open=True, close_time="2026-09-01T00:00:00Z",
                event_ticker="KXT", series_ticker="KXT",
                raw={"ticker": ticker})
    base.update(over)
    return Market(**base)


def leg(ticker="KXT-26", side="yes", price=0.8):
    return Leg(market=mk(ticker), side=side, price=price)


def single(**over):
    return Candidate(legs=(leg(),), days_to_close=3.0, **over)


def basket():
    return Candidate(legs=(leg("KXB-26", "yes", 0.4),
                           leg("KXA-26", "no", 0.5)), days_to_close=3.0)


def test_market_requires_a_ticker():
    with pytest.raises(ValueError, match="ticker"):
        mk(ticker="")


def test_market_is_frozen():
    with pytest.raises(FrozenInstanceError):
        mk().ticker = "X"


def test_market_raw_is_passed_through_by_identity_and_excluded_from_eq():
    payload = {"ticker": "KXT-26", "anything": [1, 2]}
    a, b = mk(raw=payload), mk(raw={})
    assert a.raw is payload
    assert a == b            # compare=False on raw


def test_market_from_mapping_round_trips():
    m = mk()
    from dataclasses import asdict
    assert Market.from_mapping(asdict(m)) == m


def test_leg_validates_side_and_price():
    with pytest.raises(ValueError, match="side"):
        Leg(market=mk(), side="over", price=0.5)
    with pytest.raises(ValueError, match="decimal dollars"):
        Leg(market=mk(), side="yes", price=40)
    with pytest.raises(ValueError, match="decimal dollars"):
        Leg(market=mk(), side="yes", price=float("nan"))
    with pytest.raises(ValueError, match="decimal dollars"):
        Leg(market=mk(), side="yes", price=True)


def test_candidate_needs_a_leg():
    with pytest.raises(ValueError, match="leg"):
        Candidate(legs=(), days_to_close=1.0)


def test_single_leg_conveniences():
    c = single()
    assert (c.ticker, c.fav_side, c.entry_price) == ("KXT-26", "yes", 0.8)
    assert c.is_basket is False
    assert c.cost == pytest.approx(0.8)
    assert c.key == "KXT"            # event_ticker wins
    assert c.event_key == "KXT"
    assert c.max_payout == 1.0


def test_key_falls_back_to_ticker_without_an_event():
    c = Candidate(legs=(Leg(market=mk(event_ticker=None), side="yes",
                            price=0.8),), days_to_close=1.0)
    assert c.key == "KXT-26"


def test_basket_conveniences_raise_rather_than_guess():
    b = basket()
    assert b.is_basket is True
    assert b.cost == pytest.approx(0.9)
    assert b.key == "KXA-26+KXB-26"  # sorted leg tickers
    for prop in ("ticker", "entry_price", "fav_side", "title", "event_key"):
        with pytest.raises(ValueError, match="basket"):
            getattr(b, prop)


def test_edge_validates_basis():
    with pytest.raises(ValueError, match="basis"):
        Edge(pts_net=1.0, basis="vibes")


def test_edge_from_bucket_measured_and_prior():
    rates = {"strong": {"n": 20, "win_rate": 0.9, "mean_entry_price": 0.8}}
    priors = {"strong": 4.0, "weak": 0.0}
    e = Edge.from_bucket("strong", 0.8, rates, priors)
    assert e.basis == "measured"
    assert e.model_prob == pytest.approx(0.9)
    from tools.sizing import fee_pts
    assert e.pts_net == pytest.approx((0.9 - 0.8) * 100.0 - fee_pts(0.8))
    p = Edge.from_bucket("weak", 0.8, rates, priors)
    assert (p.basis, p.pts_net, p.model_prob) == ("prior", 0.0, None)


def test_verdict_requires_a_bucket_and_carries_no_number():
    with pytest.raises(ValueError, match="bucket"):
        Verdict(bucket="  ")
    names = {f.name for f in fields(Verdict)}
    assert names == {"bucket", "rationale"}


def test_scored_candidate_validates_disposition():
    with pytest.raises(ValueError, match="disposition"):
        ScoredCandidate(candidate=single(), edge=Edge(1.0, "model"),
                        disposition="maybe")


def test_screen_result_defaults():
    sr = ScreenResult(candidates=(single(),))
    assert sr.funnel == {} and sr.gate_removed == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_domain.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.domain'`.

- [ ] **Step 3: Write `tools/domain.py`**

```python
"""Domain value types for the theory layer (OOP spec section 4.1).

Frozen dataclasses, composition over inheritance. `Market` is the unified
Kalshi shape (`PolymarketMarket` is deliberately its own type -- the field
sets genuinely differ, and a lossy union would be worse). `Candidate`
composes markets into a position with legs; `Verdict` is the only thing an
out-of-process judge may return; `ScoredCandidate` is the only thing the
ledger path accepts. The types make omissions impossible rather than
discouraged: an unscored candidate cannot reach the ledger, and a judge has
no numeric field to hand a probability back in.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from typing import Protocol

from tools.buckets import edge_for

VALID_EDGE_BASES = ("measured", "model", "prior")
VALID_DISPOSITIONS = ("screened", "endorsed", "rejected")


class Fetch(Protocol):
    """The transport seam every client fetcher takes (spec section 4.8)."""

    def __call__(self, url: str, params: dict | None = None,
                 timeout: int = 30) -> dict | list: ...


def _validate_price(price: object) -> None:
    """Leg prices are decimal dollars in [0, 1], checked at construction.

    Same rules as ledger._validate_entry_price (which is retained -- the
    ledger stays defensive); this is the earlier, additional line.
    """
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        raise ValueError(
            f"price must be a number in decimal dollars [0, 1], got {price!r}"
        )
    if isinstance(price, float) and math.isnan(price):
        raise ValueError(
            f"price must be a number in decimal dollars [0, 1], got {price!r}"
        )
    if not 0.0 <= price <= 1.0:
        raise ValueError(
            f"price {price!r} is outside [0, 1]; prices are decimal dollars, "
            f"not cents -- {price} probably means {float(price) / 100.0}"
        )


@dataclass(frozen=True, slots=True)
class Market:
    """One Kalshi market, exactly as `kalshi.markets.normalize` shapes it.

    Field set mirrors the historical normalize() dict one-to-one (including
    last_price and volume_24h, which existing tests assert). `raw` is the
    complete wire payload, passed through untouched, excluded from equality
    and repr -- see the board's cache-fidelity contract.
    """

    platform: str
    ticker: str
    title: str | None = None
    yes_bid: float | None = None
    yes_ask: float | None = None
    no_bid: float | None = None
    no_ask: float | None = None
    mid: float | None = None
    spread: float | None = None
    last_price: float | None = None
    volume: float | None = None
    volume_24h: float | None = None
    open_interest: float | None = None
    status: str | None = None
    is_open: bool = False
    close_time: str | None = None
    open_time: str | None = None
    result: str | None = None
    rules_primary: str | None = None
    event_ticker: str | None = None
    series_ticker: str | None = None
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self):
        if not self.ticker:
            raise ValueError("Market.ticker must be non-empty")

    @classmethod
    def from_mapping(cls, m) -> "Market":
        """Build from a normalize()-shaped mapping. Unknown keys ignored."""
        names = {f.name for f in fields(cls)}
        return cls(**{k: m[k] for k in m.keys() if k in names})


@dataclass(frozen=True, slots=True)
class PolymarketMarket:
    """One Polymarket market, as `polymarket.markets.normalize` shapes it.

    Deliberately not unified with `Market` (spec open question 2, resolved):
    the platforms disagree on nearly every field, and Polymarket is a
    research source, never a bet destination. Same field names as the
    historical dict; `outcomes`/`outcome_prices` stay lists so existing
    equality assertions hold.
    """

    platform: str
    market_id: str
    question: str | None = None
    slug: str | None = None
    outcomes: list = field(default_factory=list)
    outcome_prices: list = field(default_factory=list)
    implied_prob_yes: float | None = None
    best_bid: float | None = None
    best_ask: float | None = None
    volume: float | None = None
    liquidity: float | None = None
    end_date: str | None = None
    closed: bool = False
    description: str | None = None
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self):
        if not self.market_id:
            raise ValueError("PolymarketMarket.market_id must be non-empty")


@dataclass(frozen=True, slots=True)
class Leg:
    market: Market
    side: str                     # "yes" | "no"
    price: float                  # the ask actually payable, never the mid

    def __post_init__(self):
        if self.side not in ("yes", "no"):
            raise ValueError(f"Leg.side must be 'yes' or 'no', got {self.side!r}")
        _validate_price(self.price)


@dataclass(frozen=True, slots=True)
class Candidate:
    """A position: one leg normally, several for a basket (multi-leg spec).

    `max_payout` is the basket's declared joint payout, handed through to
    `ledger.record_basket`; 1.0 -- a single contract's payout -- for singles.
    """

    legs: tuple[Leg, ...]
    days_to_close: float
    max_payout: float = 1.0

    def __post_init__(self):
        if not self.legs:
            raise ValueError("Candidate needs at least one leg")

    @property
    def is_basket(self) -> bool:
        return len(self.legs) > 1

    @property
    def cost(self) -> float:
        return sum(l.price for l in self.legs)

    @property
    def key(self) -> str:
        """Stable identity for verdict routing and dedupe, every shape:
        the event key for a single leg, sorted leg tickers joined with '+'
        for a basket. Siblings deduped into one judgment share it."""
        if not self.is_basket:
            m = self.legs[0].market
            return m.event_ticker or m.ticker
        return "+".join(sorted(l.market.ticker for l in self.legs))

    def _single(self) -> Leg:
        if self.is_basket:
            raise ValueError(
                "single-leg convenience called on a basket; use .legs/.cost"
            )
        return self.legs[0]

    @property
    def ticker(self) -> str:
        return self._single().market.ticker

    @property
    def entry_price(self) -> float:
        return self._single().price

    @property
    def fav_side(self) -> str:
        return self._single().side

    @property
    def title(self) -> str | None:
        return self._single().market.title

    @property
    def event_key(self) -> str:
        self._single()
        return self.key


@dataclass(frozen=True, slots=True)
class Edge:
    pts_net: float
    basis: str                    # "measured" | "model" | "prior"
    pts_gross: float | None = None
    fee_pts: float | None = None
    model_prob: float | None = None

    def __post_init__(self):
        if self.basis not in VALID_EDGE_BASES:
            raise ValueError(
                f"invalid basis {self.basis!r}; expected one of "
                f"{VALID_EDGE_BASES}"
            )

    @classmethod
    def from_bucket(cls, bucket: str, entry_price: float,
                    rates: dict, priors: dict) -> "Edge":
        """Wraps tools.buckets.edge_for; that function stays pure."""
        pts_net, basis = edge_for(bucket, entry_price, rates, priors)
        measured = rates.get(bucket) if basis == "measured" else None
        return cls(pts_net=pts_net, basis=basis,
                   model_prob=measured["win_rate"] if measured else None)


@dataclass(frozen=True, slots=True)
class Verdict:
    """What an out-of-process judge may say about a candidate.

    Deliberately NO numeric field, and a conventions test keeps it that
    way: the judge classifies against a stated definition and picks a
    bucket from the theory's declared scale. There is no channel through
    which it could hand back a probability, a confidence percentage, or an
    edge. Numbers enter downstream, mechanically (Edge.from_bucket).
    """

    bucket: str
    rationale: str | None = None

    def __post_init__(self):
        if not self.bucket or not self.bucket.strip():
            raise ValueError("Verdict.bucket must be non-empty")


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: Candidate
    edge: Edge
    confidence: str | None = None      # the theory's own bucket label
    rationale: str | None = None
    judged_blind: bool | None = None
    disposition: str = "screened"      # screened | endorsed | rejected

    def __post_init__(self):
        if self.disposition not in VALID_DISPOSITIONS:
            raise ValueError(
                f"invalid disposition {self.disposition!r}; expected one of "
                f"{VALID_DISPOSITIONS}"
            )


@dataclass(frozen=True, slots=True)
class ScreenResult:
    """Everything screen() produced: candidates plus the counts describing
    how it got them. The channel between screen() and the run -- a stateless
    Theory has nowhere else to put its funnel (spec section 4.4)."""

    candidates: tuple[Candidate, ...]
    funnel: dict = field(default_factory=dict)
    gate_removed: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScanResult:
    """What one theory produced in one run. Uniform across every theory."""

    theory_id: str
    theory_version: int
    status: str                        # the DB registry status
    scored: tuple[ScoredCandidate, ...]
    opportunity_ids: tuple[int, ...]
    funnel: dict                       # board -> screened -> ... -> recorded
    gate_removed: dict                 # by category; {} when no gate
    judged: bool                       # did stage 2 actually run
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_domain.py -q`
Expected: PASS (all).

- [ ] **Step 5: Full suite and goldens**

Run: `python -m pytest -m "not network" -q`
Expected: All PASS (this task is purely additive).

- [ ] **Step 6: Commit**

```bash
git add tools/domain.py tests/test_domain.py
git commit -m "feat: frozen domain value types for the theory layer (OOP phase 1)"
```

---

### Task 2: The migration shim (Phase 1b)

**Files:**
- Modify: `tools/domain.py`
- Test: `tests/test_domain.py` (append)

**Interfaces:**
- Consumes: Task 1's dataclasses.
- Produces: dict-style access on `Market`, `PolymarketMarket`, and `Candidate` — `m["ticker"]`, `m.get("spread")`, `dict(market)` — plus `domain.SHIM_CALLERS`, a set of caller-module names the conventions test (Task 9) checks against an allowlist. **Deleted in Task 14.**

`keys()` is not optional: `theories/insider_bias/screen.py:133` builds candidates with `dict(market)`, which needs the mapping protocol, not just item access. `Candidate`'s dict view is the *flattened* legacy candidate shape (market fields + `fav_side`/`entry_price`/`days_to_close`), because that is the dict it replaces.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_domain.py`:

```python
def test_shim_market_dict_access():
    m = mk()
    assert m["ticker"] == "KXT-26"
    assert m.get("spread") == pytest.approx(0.04)
    assert m.get("no_such_key") is None
    assert m.get("no_such_key", 7) == 7
    with pytest.raises(KeyError):
        m["no_such_key"]


def test_shim_dict_market_matches_asdict_shape():
    from dataclasses import asdict
    m = mk()
    assert dict(m) == asdict(m)          # keys() drives dict(); raw included


def test_shim_candidate_presents_the_flattened_legacy_shape():
    c = single()
    assert c["fav_side"] == "yes"
    assert c["entry_price"] == pytest.approx(0.8)
    assert c["days_to_close"] == pytest.approx(3.0)
    assert c["ticker"] == "KXT-26"       # market fields delegate
    assert c.get("rules_secondary") is None   # unknown key -> None, like dict
    d = dict(c)
    assert set(d) == {f.name for f in fields(Market)} | {
        "fav_side", "entry_price", "days_to_close"}


def test_shim_records_its_callers():
    domain.SHIM_CALLERS.clear()
    mk()["ticker"]
    assert __name__ in domain.SHIM_CALLERS


def test_slots_prevent_attribute_injection():
    with pytest.raises((AttributeError, TypeError)):
        object.__setattr__(mk(), "new_key", 1)
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `python -m pytest tests/test_domain.py -k shim -q`
Expected: FAIL — `TypeError: 'Market' object is not subscriptable`.

- [ ] **Step 3: Add the shim to `tools/domain.py`**

Insert after `_validate_price` (before `Market`):

```python
# TODO(oop-migration): the mapping shim below is a strangler seam for one
# migration window (spec section 4.2) and is DELETED in Phase 5. It lets
# existing dict-style call sites (screen.py's `dict(market)`,
# mention_bucket's c["entry_price"], snapshot's m["ticker"]) keep working
# while call sites convert incrementally. SHIM_CALLERS records which modules
# still lean on it; tests/test_conventions.py holds the allowlist.

#: Module names observed calling the shim. Populated at runtime, checked
#: against an allowlist by the conventions test, deleted with the shim.
SHIM_CALLERS: set[str] = set()


def _note_caller() -> None:
    import sys
    SHIM_CALLERS.add(sys._getframe(2).f_globals.get("__name__", "?"))


class _MappingShim:
    __slots__ = ()                # keep dataclass slots airtight

    def keys(self):
        _note_caller()
        return tuple(f.name for f in fields(self))

    def __getitem__(self, key):
        _note_caller()
        if key in tuple(f.name for f in fields(self)):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        _note_caller()
        if key in tuple(f.name for f in fields(self)):
            return getattr(self, key)
        return default
```

Then change the three class declarations to inherit it:

```python
class Market(_MappingShim):          # was: class Market:
class PolymarketMarket(_MappingShim):
class Candidate(_MappingShim):
```

(keeping each `@dataclass(frozen=True, slots=True)` decorator), and add the flattened-view overrides at the **end** of `Candidate`:

```python
    # -- shim overrides (TODO(oop-migration), deleted in Phase 5): the
    # flattened legacy candidate-dict view, single-leg only --
    _SHIM_EXTRA = ("fav_side", "entry_price", "days_to_close")

    def keys(self):
        _note_caller()
        return tuple(f.name for f in fields(Market)) + self._SHIM_EXTRA

    def __getitem__(self, key):
        _note_caller()
        if key in self._SHIM_EXTRA:
            return getattr(self, key)
        return self._single().market[key]

    def get(self, key, default=None):
        _note_caller()
        if key in self._SHIM_EXTRA:
            return getattr(self, key)
        return self._single().market.get(key, default)
```

Note: `_SHIM_EXTRA` has no type annotation on purpose — an annotated name would become a dataclass field.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_domain.py -q`
Expected: PASS (all, including Task 1's — the mixin must not change equality, slots, or frozen-ness).

- [ ] **Step 5: Full suite**

Run: `python -m pytest -m "not network" -q`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/domain.py tests/test_domain.py
git commit -m "feat: temporary mapping shim on domain types with caller tracking"
```

---

### Task 3: `theory_facts` table and the `construction` provenance stage (Phase 1c)

**Files:**
- Modify: `db/schema.sql`, `tools/db.py`, `tools/provenance.py`
- Test: `tests/test_theory_facts.py` (create)

**Interfaces:**
- Consumes: `db.init_db`, `db.schema_statement`, `provenance.record_judgment_run` (existing).
- Produces: table `theory_facts(theory_id, kind, key, value_json, evidence_json, established_at, provenance_id)`; `provenance.VALID_STAGES` includes `"construction"`. **No Python facts API yet** (plan decision 5) — the first pair-store theory adds one.

**The versioning rule this table exists under (spec §4.5a), stated for the record:** facts are data, not procedure. Adding a confirmed pair does not bump a theory's version; changing how facts are *derived* does.

- [ ] **Step 1: Write the failing test**

Create `tests/test_theory_facts.py`:

```python
"""theory_facts: durable per-theory facts (OOP spec section 4.5a/4.5b).

Facts are data, not procedure: adding one never bumps a version. A fact a
model established carries a construction-stage provenance row, keyed to the
fact rather than to a run. Deliberately no Python API yet -- these tests
speak SQL, and the first pair-store theory earns the helpers.
"""

import json

import pytest

from tools import db, provenance, theories

TS = "2026-08-24T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    theories.register(c, "pairs", "Pair Store", "theories/pairs", now=TS)
    yield c
    c.close()


def _put(conn, provenance_id=None):
    with db.write(conn):
        conn.execute(
            "INSERT INTO theory_facts (theory_id, kind, key, value_json,"
            " evidence_json, established_at, provenance_id)"
            " VALUES ('pairs', 'market_pair', 'KXCPI-26|0xabc', ?, ?, ?, ?)",
            (json.dumps({"kalshi": "KXCPI-26", "poly": "0xabc"}),
             json.dumps({"how": "resolution text compared"}), TS,
             provenance_id),
        )


def test_a_fact_round_trips(conn):
    _put(conn)
    row = conn.execute(
        "SELECT * FROM theory_facts WHERE theory_id='pairs'"
    ).fetchone()
    assert json.loads(row["value_json"])["kalshi"] == "KXCPI-26"
    assert row["established_at"] == TS


def test_the_same_key_cannot_be_inserted_twice(conn):
    import sqlite3
    _put(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _put(conn)


def test_adding_a_fact_does_not_bump_the_version(conn):
    before = theories.get(conn, "pairs")["version"]
    _put(conn)
    assert theories.get(conn, "pairs")["version"] == before


def test_construction_is_a_valid_provenance_stage(conn):
    pid = provenance.record_judgment_run(
        conn, run_id="setup-2026-08-24", theory_id="pairs",
        theory_version=1, stage="construction",
        model="claude-opus-5", prompt_text="propose matching market pairs",
        now=TS,
    )
    _put(conn, provenance_id=pid)
    row = conn.execute(
        "SELECT j.stage FROM theory_facts f"
        " JOIN judgment_runs j ON j.id = f.provenance_id"
    ).fetchone()
    assert row["stage"] == "construction"


def test_a_legacy_database_is_migrated_to_accept_construction(tmp_path):
    """A DB created before this task carries the old CHECK; init_db rebuilds."""
    import sqlite3
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE theories (id TEXT PRIMARY KEY, name TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed','testing','active',
                                  'under_review','paused','retired')),
            path TEXT NOT NULL, retirement_proposed_at TEXT,
            retirement_rationale TEXT,
            uses_llm_judgment INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE judgment_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            theory_id TEXT NOT NULL REFERENCES theories(id),
            theory_version INTEGER NOT NULL,
            stage TEXT NOT NULL
                CHECK (stage IN ('gate','analysis','final_review','other')),
            model TEXT NOT NULL, effort TEXT, prompt_path TEXT,
            prompt_sha256 TEXT NOT NULL, prompt_text TEXT,
            web_search INTEGER, n_items INTEGER, notes TEXT,
            created_at TEXT NOT NULL,
            CHECK (prompt_path IS NOT NULL OR prompt_text IS NOT NULL),
            UNIQUE (run_id, theory_id, theory_version, stage, model,
                    prompt_sha256));
        INSERT INTO theories VALUES ('t','T',1,'testing','p',NULL,NULL,0,
                                     '2026-01-01T00:00:00Z',
                                     '2026-01-01T00:00:00Z');
        INSERT INTO judgment_runs (run_id, theory_id, theory_version, stage,
            model, prompt_sha256, prompt_text, created_at)
        VALUES ('r','t',1,'analysis','m','sha','p','2026-01-01T00:00:00Z');
    """)
    old.commit()
    old.close()

    conn = db.connect(path)
    db.init_db(conn)
    # The pre-existing row survived the rebuild...
    assert conn.execute("SELECT COUNT(*) FROM judgment_runs").fetchone()[0] == 1
    # ...and the widened CHECK accepts construction.
    provenance.record_judgment_run(
        conn, run_id="r2", theory_id="t", theory_version=1,
        stage="construction", model="m", prompt_text="x", now=TS)
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_theory_facts.py -q`
Expected: FAIL — `no such table: theory_facts`, and `invalid stage 'construction'`.

- [ ] **Step 3: Add the table and widen the CHECK in `db/schema.sql`**

In the `judgment_runs` CREATE TABLE, change the stage CHECK line to:

```sql
    stage          TEXT NOT NULL
                   CHECK (stage IN ('gate','analysis','final_review',
                                    'construction','other')),
```

After the `idx_judgment_runs_run` index at the end of the file, add:

```sql
-- Durable per-theory facts (OOP spec section 4.5a): confirmed market
-- pairs, implication edges, wallet scores. Facts are DATA, not procedure --
-- adding one never bumps a theory's version; changing how facts are
-- derived does. provenance_id records the construction-stage judgment
-- that established a model-proposed fact (section 4.5b).
CREATE TABLE IF NOT EXISTS theory_facts (
    theory_id      TEXT NOT NULL REFERENCES theories(id),
    kind           TEXT NOT NULL,      -- 'market_pair', 'implication', ...
    key            TEXT NOT NULL,
    value_json     TEXT NOT NULL,
    evidence_json  TEXT,
    established_at TEXT NOT NULL,
    provenance_id  INTEGER REFERENCES judgment_runs(id),
    PRIMARY KEY (theory_id, kind, key)
);
```

- [ ] **Step 4: Update `tools/provenance.py`**

```python
VALID_STAGES = ("gate", "analysis", "final_review", "construction", "other")
```

Also extend the module docstring's stage list with one line: `construction` — judgment that established durable `theory_facts` (pair confirmation, implication edges) rather than a per-run verdict.

- [ ] **Step 5: Add `_migrate_judgment_runs` to `tools/db.py`**

The CHECK is baked into existing databases; `CREATE TABLE IF NOT EXISTS` will not touch them, so rebuild exactly as `_migrate_theories` does. Add after `_migrate_theories` and call it from `init_db` right after the `_migrate_theories(conn)` line:

```python
def _migrate_judgment_runs(conn: sqlite3.Connection) -> None:
    """Widen an old judgment_runs stage CHECK to accept 'construction'.

    Same rebuild pattern as _migrate_theories: SQLite cannot alter a CHECK
    in place. Rows carry over unchanged; the UNIQUE constraint lives inside
    the table DDL and survives, and the external index is recreated because
    dropping the renamed table takes it along.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='judgment_runs'"
    ).fetchone()
    if row is None or "construction" in (row[0] or ""):
        return

    ddl = schema_statement("judgment_runs")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute("BEGIN")
        try:
            conn.execute(
                "ALTER TABLE judgment_runs RENAME TO judgment_runs_legacy")
            conn.execute(ddl)
            conn.execute(
                """
                INSERT INTO judgment_runs
                    (id, run_id, theory_id, theory_version, stage, model,
                     effort, prompt_path, prompt_sha256, prompt_text,
                     web_search, n_items, notes, created_at)
                SELECT id, run_id, theory_id, theory_version, stage, model,
                       effort, prompt_path, prompt_sha256, prompt_text,
                       web_search, n_items, notes, created_at
                FROM judgment_runs_legacy
                """
            )
            conn.execute("DROP TABLE judgment_runs_legacy")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_judgment_runs_run"
                " ON judgment_runs (theory_id, theory_version, run_id)")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.execute("PRAGMA foreign_keys = ON")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_theory_facts.py tests/test_provenance.py tests/test_db.py -q`
Expected: PASS. Then `python -m pytest -m "not network" -q` — all PASS (the live DB migration runs on the next `init_db`; nothing else changes).

- [ ] **Step 7: Commit**

```bash
git add db/schema.sql tools/db.py tools/provenance.py tests/test_theory_facts.py
git commit -m "feat: theory_facts table and construction provenance stage"
```

---

### Task 4: Kalshi client returns `Market`; the `fetch` seam (Phase 2a)

**Files:**
- Modify: `tools/kalshi/markets.py`, `tools/board.py` (annotations/docstring only), `tools/snapshot.py` (annotation only)
- Test: `tests/kalshi/test_markets.py` (append), `tests/test_board.py` (append)

**Interfaces:**
- Consumes: `domain.Market`, `domain.Fetch`, the shim (Task 2).
- Produces: `normalize(raw) -> Market`; `list_open(limit=200, *, fetch: Fetch | None = None) -> list[Market]`; `list_settled(..., fetch: Fetch | None = None)`; `quotes(tickers, *, fetch: Fetch | None = None)`. `board.get_board` therefore returns `list[Market]` with no change to its own code.

**Two correctness details that are the point of this task:**

1. **The `fetch` default is `None`, resolved to `get_json` at call time** (`fetch = fetch or get_json` in the body). A def-time default (`fetch: Fetch = get_json`) would freeze the original function object into the signature and silently break every existing `monkeypatch.setattr(markets, "get_json", fake)` test — the spec's promise that monkeypatch tests keep passing holds only with call-time resolution.
2. **`list_open`'s event enrichment must use `dataclasses.replace`** — `Market` is frozen; the current `market["event_ticker"] = ...` mutation becomes a `replace(...)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/kalshi/test_markets.py`:

```python
def test_normalize_returns_a_market_with_raw_by_identity():
    from tools.domain import Market
    m = markets.normalize(RAW)
    assert isinstance(m, Market)
    assert m.raw is RAW
    assert m.yes_ask == pytest.approx(0.93)   # attribute access works too


def test_list_open_accepts_an_injected_fetch_without_monkeypatch():
    calls = []

    def fake(url, params=None, timeout=30):
        calls.append(url)
        return {"events": [{"event_ticker": "KXOAIANTH-40",
                            "title": "evt", "markets": [dict(RAW)]}],
                "cursor": ""}

    got = markets.list_open(fetch=fake)
    assert [m.ticker for m in got] == ["KXOAIANTH-40-ANTH"]
    assert calls and "events" in calls[0]


def test_list_open_enriches_missing_event_fields_from_the_event():
    raw = {k: v for k, v in RAW.items() if k != "event_ticker"}

    def fake(url, params=None, timeout=30):
        return {"events": [{"event_ticker": "KXFROMEVT", "title": "evt",
                            "markets": [raw]}], "cursor": ""}

    got = markets.list_open(fetch=fake)
    assert got[0].event_ticker == "KXFROMEVT"
```

Append to `tests/test_board.py` (the spec §8.1 raw-fidelity proof):

```python
def test_cache_and_fetch_boards_are_identical_raw_included(conn, monkeypatch):
    fetched = _board(3)
    monkeypatch.setattr(board.kalshi_markets, "list_open", lambda: fetched)
    first = board.get_board(conn, force=True, now=NOW)     # fetch + snapshot
    rebuilt = board.get_board(conn, now=NOW)               # cache hit
    assert rebuilt == first
    for a, b in zip(first, rebuilt):
        assert a.raw == b.raw          # compare=False, so check explicitly
```

(`_board(n)` already builds via `markets.normalize`, so it now yields `Market` objects with `raw` attached — no fixture change needed.)

- [ ] **Step 2: Run to verify the new tests fail**

Run: `python -m pytest tests/kalshi/test_markets.py tests/test_board.py -q`
Expected: the new tests FAIL (`normalize` returns a dict; `list_open` rejects `fetch=`); every pre-existing test still passes.

- [ ] **Step 3: Convert `tools/kalshi/markets.py`**

At the top:

```python
from dataclasses import replace

from tools.domain import Fetch, Market
from tools.http import get_json
```

`normalize` keeps its validation and `_price` parsing exactly as-is and ends by constructing the dataclass instead of the dict — same field names, same values, `raw=raw`:

```python
    return Market(
        platform="kalshi",
        ticker=ticker,
        event_ticker=raw.get("event_ticker"),
        series_ticker=raw.get("series_ticker"),
        title=raw.get("title"),
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=_price(raw, "no_bid_dollars"),
        no_ask=_price(raw, "no_ask_dollars"),
        mid=mid,
        spread=spread,
        last_price=_price(raw, "last_price_dollars"),
        volume=_price(raw, "volume_fp"),
        volume_24h=_price(raw, "volume_24h_fp"),
        open_interest=_price(raw, "open_interest_fp"),
        status=status,
        is_open=status in OPEN_STATUSES,
        close_time=raw.get("close_time"),
        open_time=raw.get("open_time"),
        result=raw.get("result") or None,
        rules_primary=raw.get("rules_primary"),
        raw=raw,
    )
```

`list_open` gains the seam and swaps mutation for `replace`:

```python
def list_open(limit: int = 200, *,
              fetch: Fetch | None = None) -> list[Market]:
```

body: `fetch = fetch or get_json`; every `get_json(...)` call becomes `fetch(...)`; the enrichment block becomes:

```python
            for raw in event.get("markets", []):
                market = normalize(raw)
                if market.ticker in seen_tickers:
                    continue
                seen_tickers.add(market.ticker)
                patch = {}
                if not market.event_ticker:
                    patch["event_ticker"] = event.get("event_ticker")
                if not market.series_ticker:
                    patch["series_ticker"] = event.get("series_ticker")
                if not market.title:
                    patch["title"] = event.get("title")
                if patch:
                    market = replace(market, **patch)
                out.append(market)
```

`list_settled` and `quotes` get the same `fetch: Fetch | None = None` keyword and call-time resolution; their return annotations become `list[Market]` / `dict[str, Market]` (`quotes` keys by `market.ticker`). Update the module docstring's "one stable dict of floats" phrase to "one stable `Market`".

In `tools/board.py` and `tools/snapshot.py`, update only annotations and docstrings (`list[dict]` → `list[Market]` where boards flow); their code reads through the shim untouched.

**One consumer WRITES to normalize output and must be fixed here or it breaks at import-and-run time:** `theories/insider_bias/insider_judgment/backtest.py:175-177` (`iter_settled_survivors`) tags each survivor with `s["series_ticker"] = ticker` — item assignment on a frozen `Market` raises `TypeError`. Replace the loop with:

```python
        survivors = [replace(s, series_ticker=ticker) for s in survivors]
        yield ticker, survivors
```

adding `from dataclasses import replace` to that module's imports. This is a shape fix at the boundary, not a decision-logic change — the tagged value is identical. Every other consumer only *reads* (verify: `grep -rn '\] *=' theories/ tools/ | grep -v "_legacy\|tests"` shows no other subscript assignment into a normalized market).

- [ ] **Step 4: Run the target tests, goldens, and full suite**

Run: `python -m pytest tests/kalshi tests/test_board.py tests/test_snapshot.py tests/characterization -q`
Expected: PASS — in particular `test_normalize_matches_golden_for_every_fixture_row` (the projection turns a `Market` into exactly the old dict) and every monkeypatch test, unmodified.

Run: `python -m pytest -m "not network" -q`
Expected: All PASS. `screen.screen` consumes the fixture dicts in the goldens and live `Market`s in production — both satisfy `.get()` until Task 12.

- [ ] **Step 5: Commit**

```bash
git add tools/kalshi/markets.py tools/board.py tools/snapshot.py theories/insider_bias/insider_judgment/backtest.py tests/kalshi/test_markets.py tests/test_board.py
git commit -m "feat: kalshi normalize returns Market; injectable fetch seam"
```

---

### Task 5: Polymarket client returns `PolymarketMarket`; its `fetch` seam (Phase 2b)

**Files:**
- Modify: `tools/polymarket/markets.py`
- Test: `tests/polymarket/test_markets.py` (append)

**Interfaces:**
- Consumes: `domain.PolymarketMarket`, `domain.Fetch`.
- Produces: `normalize(raw) -> PolymarketMarket`; `_fetch(params, fetch=None)`; `list_open(..., *, fetch=None)`, `list_resolved(..., *, fetch=None)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/polymarket/test_markets.py` (reuse its existing RAW-style fixture dict; if it has none, build a minimal Gamma payload inline as below):

```python
def test_normalize_returns_a_polymarket_market():
    from tools.domain import PolymarketMarket
    raw = {"conditionId": "0xabc", "question": "Will X?",
           "outcomes": '["Yes", "No"]', "outcomePrices": '["0.6", "0.4"]',
           "bestBid": "0.59", "bestAsk": "0.61", "volumeNum": 1000,
           "endDate": "2026-09-01T00:00:00Z", "closed": False}
    m = markets.normalize(raw)
    assert isinstance(m, PolymarketMarket)
    assert m.market_id == "0xabc"
    assert m["question"] == "Will X?"          # shim access
    assert m.outcomes == ["Yes", "No"]         # stays a list
    assert m.implied_prob_yes == pytest.approx(0.6)
    assert m.raw is raw


def test_fetch_seam_injects_without_monkeypatch():
    def fake(url, params=None, timeout=30):
        return [{"conditionId": "0x1", "question": "q",
                 "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]'}]
    got = markets.list_open(fetch=fake)
    assert [m.market_id for m in got] == ["0x1"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/polymarket/test_markets.py -q`
Expected: new tests FAIL; existing ones pass.

- [ ] **Step 3: Convert `tools/polymarket/markets.py`**

`normalize` keeps `_string_array`/`_number`/implied-yes logic verbatim and returns:

```python
    return PolymarketMarket(
        platform="polymarket",
        market_id=market_id,
        question=raw.get("question"),
        slug=raw.get("slug"),
        outcomes=outcomes,
        outcome_prices=prices,
        implied_prob_yes=implied_yes,
        best_bid=_number(raw, "bestBid"),
        best_ask=_number(raw, "bestAsk"),
        volume=_number(raw, "volumeNum"),
        liquidity=_number(raw, "liquidityNum"),
        end_date=raw.get("endDate"),
        closed=bool(raw.get("closed")),
        description=raw.get("description"),
        raw=raw,
    )
```

`_fetch` gains `fetch: Fetch | None = None` (call-time `fetch = fetch or get_json`, same reasoning as Task 4); `list_open` and `list_resolved` gain `*, fetch: Fetch | None = None` and pass it through. `save_polymarket` and `match_market.py` read through the shim untouched.

- [ ] **Step 4: Run tests and full suite**

Run: `python -m pytest tests/polymarket tests/test_snapshot.py tests/test_match_market.py -q` then `python -m pytest -m "not network" -q`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/polymarket/markets.py tests/polymarket/test_markets.py
git commit -m "feat: polymarket normalize returns PolymarketMarket; fetch seam"
```

---

### Task 6: The theory contract — `tools/theory.py` (Phase 3a)

**Files:**
- Create: `tools/theory.py`
- Test: `tests/test_theory.py`, `tests/test_theory_run.py`, `tests/test_context.py`, `tests/test_stub_theory.py`

**Interfaces:**
- Consumes: everything from `tools/domain.py`; `ledger.record_opportunity`, `ledger.record_basket`, `ledger.interpret`; `provenance.record_judgment_run`; `theories.get`; `score.bucket_rates`.
- Produces (used verbatim by Tasks 7–10):
  - `TheoryContext(conn, board, now, run_id="live", run_mode="live", judge_model=None, bucket_rates=None)` and `TheoryContext.build(conn, board, now, *, run_id="live", run_mode="live", judge_model=None)`
  - `Theory` ABC: ClassVars `id/name/version/uses_llm_judgment/prompts`; abstract `screen(ctx) -> list[Candidate] | ScreenResult` and `price(ctx, cands, verdicts=None) -> list[ScoredCandidate]`; optional `judgment_payload(cands) -> list[dict] | None`; concrete `start(ctx) -> TheoryRun`.
  - `TheoryRun`: `.needs_judgment`, `.payload`, `.candidates`, `.apply(verdicts) -> TheoryRun`, `.finish(dry_run=False) -> ScanResult`.

Design rules carried from the spec, enforced here: `Theory` is stateless — all per-run state on `TheoryRun`; verdicts travel on the run, never on frozen candidates; `finish()` is the single ledger/provenance path and raises rather than record an unjudged judgment theory; provenance is written for any theory with a non-empty `prompts` ClassVar (plan decision 7), with `judge_model` mandatory when `uses_llm_judgment` and defaulting to `"none (deterministic)"` otherwise.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_theory.py`:

```python
from datetime import datetime, timezone

import pytest

from tools import db, theories
from tools.domain import (Candidate, Edge, Leg, Market, ScoredCandidate,
                          ScreenResult, Verdict)
from tools.theory import Theory, TheoryContext

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
TS = "2026-08-24T12:00:00Z"


def mkm(ticker="KXT-26", yes_ask=0.4, event="KXT"):
    return Market(platform="kalshi", ticker=ticker, yes_ask=yes_ask,
                  is_open=True, event_ticker=event, raw={})


def cand(ticker="KXT-26", event="KXT"):
    return Candidate(legs=(Leg(market=mkm(ticker, event=event), side="yes",
                               price=0.4),), days_to_close=2.0)


class Mechanical(Theory):
    id = "stub_mech"
    name = "Stub Mechanical"
    version = 1

    def screen(self, ctx):
        return [Candidate(legs=(Leg(market=m, side="yes", price=m.yes_ask),),
                          days_to_close=1.0)
                for m in ctx.board if (m.yes_ask or 1.0) <= 0.5]

    def price(self, ctx, cands, verdicts=None):
        return [ScoredCandidate(candidate=c, edge=Edge(pts_net=5.0,
                                                       basis="model"))
                for c in cands]


class Judged(Theory):
    id = "stub_judged"
    name = "Stub Judged"
    version = 1
    uses_llm_judgment = True
    # Any committed file works as a prompt path for a test stub; provenance
    # hashes whatever is on disk.
    prompts = {"analysis": "theories/_TEMPLATE/THEORY.md"}

    def screen(self, ctx):
        return ScreenResult(candidates=(cand(),),
                            funnel={"board_markets": len(ctx.board)})

    def judgment_payload(self, cands):
        return [{"key": c.key, "title": c.title} for c in cands] or None

    def price(self, ctx, cands, verdicts=None):
        verdicts = verdicts or {}
        return [ScoredCandidate(candidate=c,
                                edge=Edge(pts_net=4.0, basis="prior"),
                                confidence=verdicts[c.key].bucket,
                                judged_blind=True)
                for c in cands if c.key in verdicts]


def fake_ctx(board=(), conn=None, judge_model=None):
    return TheoryContext(conn=conn, board=list(board), now=NOW,
                         judge_model=judge_model)


def test_theory_is_abstract():
    with pytest.raises(TypeError):
        Theory()


def test_a_subclass_missing_price_cannot_instantiate():
    class Half(Theory):
        id, name, version = "half", "Half", 1

        def screen(self, ctx):
            return []

    with pytest.raises(TypeError):
        Half()


def test_start_wraps_a_bare_list_into_a_screen_result():
    run = Mechanical().start(fake_ctx([mkm()]))
    assert isinstance(run.screen_result, ScreenResult)
    assert run.needs_judgment is False


def test_finish_refuses_an_unjudged_judgment_run():
    run = Judged().start(fake_ctx([mkm()]))
    assert run.needs_judgment is True
    with pytest.raises(RuntimeError, match="verdicts"):
        run.finish(dry_run=True)


def test_apply_rejects_a_verdict_key_matching_no_candidate():
    run = Judged().start(fake_ctx([mkm()]))
    with pytest.raises(ValueError, match="no candidate"):
        run.apply({"NOPE": Verdict(bucket="strong")})


def test_apply_rejects_a_non_verdict_value():
    run = Judged().start(fake_ctx([mkm()]))
    with pytest.raises(TypeError, match="category, never a number"):
        run.apply({"KXT": 0.78})


def test_dry_run_scores_without_writing():
    run = Judged().start(fake_ctx([mkm()]))     # conn=None: any DB touch throws
    result = run.apply({"KXT": Verdict(bucket="strong")}).finish(dry_run=True)
    assert result.judged is True
    assert result.opportunity_ids == ()
    assert [s.confidence for s in result.scored] == ["strong"]
    assert result.funnel["recorded"] == 0


def test_finish_requires_judge_model_for_an_llm_theory(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_judged", "Stub", "x", now=TS)
    theories.set_uses_llm_judgment(conn, "stub_judged", True)
    run = Judged().start(fake_ctx([mkm()], conn=conn))
    run.apply({"KXT": Verdict(bucket="strong")})
    with pytest.raises(RuntimeError, match="judge_model"):
        run.finish()
    conn.close()
```

Create `tests/test_theory_run.py`:

```python
"""Statelessness: the regression tests for the _last_funnel bug the spec's
section 4.4 describes. One Theory instance, many runs, no shared state."""

from tests.test_theory import Judged, Mechanical, fake_ctx, mkm
from tools.domain import Verdict


def test_the_same_instance_started_twice_yields_independent_runs():
    theory = Judged()
    run1 = theory.start(fake_ctx([mkm()]))
    run2 = theory.start(fake_ctx([mkm(), mkm("KXU-26", event="KXU")]))
    assert run1 is not run2
    assert run1.screen_result is not run2.screen_result
    assert run1.screen_result.funnel is not run2.screen_result.funnel
    assert run1.screen_result.funnel == {"board_markets": 1}
    assert run2.screen_result.funnel == {"board_markets": 2}
    run1.apply({"KXT": Verdict(bucket="strong")})
    assert run2.verdicts is None


def test_two_theories_interleaved_do_not_corrupt_each_other():
    a, b = Mechanical(), Judged()
    ra = a.start(fake_ctx([mkm(yes_ask=0.3)]))
    rb = b.start(fake_ctx([mkm()]))
    fa = ra.finish(dry_run=True)
    rb.apply({"KXT": Verdict(bucket="weak")})
    fb = rb.finish(dry_run=True)
    assert fa.theory_id == "stub_mech" and fb.theory_id == "stub_judged"
    assert fa.judged is False and fb.judged is True
```

Create `tests/test_context.py`:

```python
"""A theory runs against a fake TheoryContext: ten hand-built markets, no
live connection, no network, no monkeypatch (spec section 7)."""

from datetime import datetime, timezone

from tests.test_theory import Mechanical, fake_ctx, mkm
from tools import db
from tools.theory import TheoryContext

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def test_a_theory_runs_on_a_ten_market_fake_board():
    board = [mkm(f"KXT-{i}", yes_ask=0.30 + i * 0.05) for i in range(10)]
    result = Mechanical().start(fake_ctx(board)).finish(dry_run=True)
    assert result.funnel["candidates"] == 5      # asks 0.30..0.50 inclusive
    assert all(s.edge.basis == "model" for s in result.scored)


def test_build_binds_bucket_rates_to_the_connection(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    ctx = TheoryContext.build(conn=conn, board=[], now=NOW)
    assert ctx.bucket_rates("nonexistent_theory", 1) == {}
    conn.close()


def test_fetch_injection_needs_no_monkeypatch():
    from tools.kalshi import markets

    def fake(url, params=None, timeout=30):
        return {"events": [], "cursor": ""}

    assert markets.list_open(fetch=fake) == []
```

Create `tests/test_stub_theory.py`:

```python
"""The spec section 3.2 litmus test, mechanised: a stub implementing only
screen() and price() runs end to end and records; a stub that ignores ctx
entirely still runs. The contract is a floor, not a cage."""

import pytest

from tests.test_theory import NOW, TS, Mechanical, fake_ctx, mkm
from tools import db, ledger, theories
from tools.domain import Candidate, Edge, Leg, Market, ScoredCandidate
from tools.theory import Theory, TheoryContext


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    theories.register(c, "stub_mech", "Stub Mechanical", "x",
                      status="proposed", now=TS)
    theories.set_status(c, "stub_mech", "testing", now=TS)
    yield c
    c.close()


def test_two_required_methods_are_enough_to_record(conn):
    board = [mkm("KXT-1", yes_ask=0.4, event="KXE1"),
             mkm("KXT-2", yes_ask=0.9, event="KXE2")]
    ctx = TheoryContext.build(conn=conn, board=board, now=NOW)
    result = Mechanical().start(ctx).finish()
    assert result.status == "testing"
    assert len(result.opportunity_ids) == 1
    row = ledger.get_opportunity(conn, result.opportunity_ids[0])
    assert row["kalshi_ticker"] == "KXT-1"
    assert row["outcome"] == "yes"
    assert row["entry_price"] == pytest.approx(0.4)
    assert row["edge_basis"] == "model"
    assert row["run_id"] == "live"


def test_a_theory_may_ignore_ctx_and_bring_its_own_data():
    class OwnSource(Theory):
        id, name, version = "own_source", "Own Source", 1

        def screen(self, ctx):
            m = Market(platform="kalshi", ticker="KXW-26", is_open=True,
                       raw={})          # from anywhere: a file, an API, ...
            return [Candidate(legs=(Leg(market=m, side="no", price=0.2),),
                              days_to_close=1.0)]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(candidate=c,
                                    edge=Edge(pts_net=3.0, basis="model"))
                    for c in cands]

    result = OwnSource().start(fake_ctx()).finish(dry_run=True)
    assert result.funnel["scored"] == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_theory.py tests/test_theory_run.py tests/test_context.py tests/test_stub_theory.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.theory'`.

- [ ] **Step 3: Write `tools/theory.py`**

```python
"""The theory contract (OOP spec sections 4.3-4.5).

A theory inherits *what to do* (`start`, `finish` -- the Template Method
half) and is handed *what it may touch* (`TheoryContext` -- the injection
half). Never a toolbox base class: publishing self.list_open() on every
theory would make the forbidden path (bypassing the shared board) the most
discoverable thing on the object.

`Theory` is stateless. All per-run state -- the ScreenResult, the stage-2
payload, applied verdicts -- lives on `TheoryRun`, so one instance can run
twice, or interleave with other theories, without corruption.

The contract is OPTIONAL FOR RUNNING and MANDATORY FOR RECORDING. Every
tool stays directly callable; ad-hoc research needs none of this. The one
non-negotiable is the ledger boundary: when a finding is recorded as
evidence, provenance, an honest edge_basis, and a Kalshi ticker hold
without exception. finish() is that boundary, and no subclass overrides it.

A verdict is a category, never a number: the judge's entire output channel
is `Verdict` (bucket + rationale). Probabilities enter downstream via
measured bucket rates or a mechanical model -- never from the judge.
"""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Callable, ClassVar

from tools import ledger, provenance
from tools.domain import (Candidate, ScanResult, ScoredCandidate,
                          ScreenResult, Verdict)


@dataclass(frozen=True, slots=True)
class TheoryContext:
    """What the harness offers a theory -- not a whitelist of what it may
    touch. A theory whose thesis needs more (a weather feed, an on-chain
    query) reaches further; ctx.conn and the Fetch convention are there."""

    conn: sqlite3.Connection | None
    board: list
    now: datetime
    run_id: str = "live"
    run_mode: str = "live"
    judge_model: str | None = None     # set by the dispatching parent (4.9)
    bucket_rates: Callable | None = None

    @classmethod
    def build(cls, conn, board, now, *, run_id: str = "live",
              run_mode: str = "live",
              judge_model: str | None = None) -> "TheoryContext":
        """The live constructor: binds score.bucket_rates to the connection
        (a per-instance binding cannot be a dataclass default). Tests build
        the dataclass directly with fakes."""
        from tools import score
        return cls(conn=conn, board=board, now=now, run_id=run_id,
                   run_mode=run_mode, judge_model=judge_model,
                   bucket_rates=partial(score.bucket_rates, conn))


class Theory(ABC):
    """Two required methods; everything else has a default (spec 3.2)."""

    id: ClassVar[str]
    name: ClassVar[str]
    version: ClassVar[int]
    uses_llm_judgment: ClassVar[bool] = False
    prompts: ClassVar[dict[str, str]] = {}   # stage -> repo-relative path

    # ---- the two methods a new theory must write ----

    @abstractmethod
    def screen(self, ctx: TheoryContext) -> "list[Candidate] | ScreenResult":
        """Stage 1. Mechanical, no model in the decision path. Return a
        bare list, or a ScreenResult when there are funnel or gate counts
        to report; start() wraps a bare list."""

    @abstractmethod
    def price(self, ctx: TheoryContext, cands: list[Candidate],
              verdicts: dict[str, Verdict] | None = None,
              ) -> list[ScoredCandidate]:
        """Attach an Edge. verdicts is None on a mechanical run; for a
        judgment theory it maps Candidate.key -> Verdict. Must set
        edge.basis honestly. A candidate the judge did not rule on is this
        method's call -- drop it or mark it rejected -- but never price it
        as if it had been judged."""

    # ---- optional stage 2 ----

    def judgment_payload(self, cands: list[Candidate]) -> list[dict] | None:
        """Stage 2 input, or None when the theory has no stage 2 (or
        nothing survived to judge). Payloads must be blind where the
        theory's procedure requires it -- build them by whitelist."""
        return None

    # ---- the workflow, inherited and never overridden ----

    def start(self, ctx: TheoryContext) -> "TheoryRun":
        result = self.screen(ctx)
        if isinstance(result, list):
            result = ScreenResult(candidates=tuple(result))
        return TheoryRun(self, ctx, result)


@dataclass(frozen=True)
class OpportunityRecord:
    """One scored candidate, assembled by finish() and ready for the
    ledger. Internal -- never part of a theory's surface (spec 4.1)."""

    single: dict | None      # record_opportunity kwargs, or None
    basket: dict | None      # record_basket kwargs, or None

    @classmethod
    def from_scored(cls, sc: ScoredCandidate, theory: "Theory",
                    ctx: TheoryContext) -> "OpportunityRecord":
        c, e = sc.candidate, sc.edge
        common = dict(
            theory_id=theory.id, theory_version=theory.version,
            edge_pts_net=e.pts_net, edge_basis=e.basis,
            model_prob=e.model_prob, edge_pts_gross=e.pts_gross,
            fee_pts=e.fee_pts, confidence=sc.confidence,
            judged_blind=sc.judged_blind, rationale=sc.rationale,
            run_mode=ctx.run_mode, run_id=ctx.run_id,
            evidence_source="kalshi",
        )
        if c.is_basket:
            legs = [dict(kalshi_ticker=l.market.ticker, outcome=l.side,
                         entry_price=l.price, spread_at_call=l.market.spread,
                         volume_at_call=l.market.volume) for l in c.legs]
            return cls(single=None,
                       basket=dict(common, legs=legs,
                                   max_payout=c.max_payout))
        leg = c.legs[0]
        return cls(basket=None,
                   single=dict(common, kalshi_ticker=leg.market.ticker,
                               outcome=leg.side, entry_price=leg.price,
                               spread_at_call=leg.market.spread,
                               volume_at_call=leg.market.volume))

    def write(self, conn: sqlite3.Connection) -> int:
        if self.basket is not None:
            opp_id, _ = ledger.record_basket(conn, **self.basket)
        else:
            opp_id, _ = ledger.record_opportunity(conn, **self.single)
        return opp_id


class TheoryRun:
    """One execution of one theory. Holds ALL per-run state."""

    def __init__(self, theory: Theory, ctx: TheoryContext,
                 screen_result: ScreenResult):
        self.theory = theory
        self.ctx = ctx
        self.screen_result = screen_result
        self.candidates: list[Candidate] = list(screen_result.candidates)
        self.payload = theory.judgment_payload(self.candidates)
        self.verdicts: dict[str, Verdict] | None = None

    @property
    def needs_judgment(self) -> bool:
        return self.payload is not None

    def apply(self, verdicts: dict[str, Verdict]) -> "TheoryRun":
        """Store out-of-process verdicts on the run. Chainable."""
        for value in verdicts.values():
            if not isinstance(value, Verdict):
                raise TypeError(
                    f"verdict values must be Verdict, got {value!r} -- a "
                    "judge returns a category, never a number"
                )
        known = {c.key for c in self.candidates}
        unknown = sorted(set(verdicts) - known)
        if unknown:
            raise ValueError(
                f"verdict keys match no candidate: {unknown}; keys are "
                "Candidate.key values from this run's screen"
            )
        self.verdicts = dict(verdicts)
        return self

    def finish(self, *, dry_run: bool = False) -> ScanResult:
        """price -> provenance -> ledger -> ScanResult. Never overridden.

        dry_run scores without writing anything -- the exploratory escape
        hatch (spec 3.2)."""
        if self.needs_judgment and self.verdicts is None:
            raise RuntimeError(
                f"{self.theory.id} produced a judgment payload but no "
                "verdicts were applied; silently recording unjudged screen "
                "output would misstate edge_basis and judged_blind on every "
                "row. Call run.apply(verdicts) first, or finish(dry_run=True)."
            )
        scored = list(self.theory.price(self.ctx, self.candidates,
                                        self.verdicts))
        ids: list[int] = []
        if not dry_run and scored:
            if self.theory.prompts:
                self._record_provenance()
            for sc in scored:
                rec = OpportunityRecord.from_scored(sc, self.theory, self.ctx)
                opp_id = rec.write(self.ctx.conn)
                if sc.disposition != "screened":
                    ledger.interpret(self.ctx.conn, opp_id, sc.disposition,
                                     sc.rationale or "")
                ids.append(opp_id)
        funnel = dict(self.screen_result.funnel)
        funnel.update({"candidates": len(self.candidates),
                       "scored": len(scored), "recorded": len(ids)})
        return ScanResult(
            theory_id=self.theory.id, theory_version=self.theory.version,
            status=self._registry_status(), scored=tuple(scored),
            opportunity_ids=tuple(ids), funnel=funnel,
            gate_removed=dict(self.screen_result.gate_removed),
            judged=self.verdicts is not None,
        )

    def _record_provenance(self) -> None:
        """Model + prompt per judging stage, before any row lands.

        The model recorded is the JUDGING model (ctx.judge_model -- the
        subagent's, when one was dispatched), never implicitly this
        process's. A mechanical theory with a prompts entry records
        'none (deterministic)', preserving voluntary self-documentation."""
        model = self.ctx.judge_model
        if self.theory.uses_llm_judgment:
            if not model:
                raise RuntimeError(
                    f"{self.theory.id} uses LLM judgment but "
                    "ctx.judge_model is not set; recording the parent's "
                    "model for a judgment it did not make would corrupt "
                    "provenance (spec 4.9)"
                )
        else:
            model = model or "none (deterministic)"
        web = False if self.ctx.run_mode == "backtest" else None
        for stage, path in self.theory.prompts.items():
            provenance.record_judgment_run(
                self.ctx.conn, run_id=self.ctx.run_id,
                theory_id=self.theory.id,
                theory_version=self.theory.version,
                stage=stage, model=model, prompt_path=path, web_search=web,
            )

    def _registry_status(self) -> str:
        try:
            from tools import theories as theories_db
            row = theories_db.get(self.ctx.conn, self.theory.id)
            return row["status"] if row is not None else "unregistered"
        except Exception:
            return "unregistered"      # fake context in tests: no DB
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_theory.py tests/test_theory_run.py tests/test_context.py tests/test_stub_theory.py -q`
Expected: PASS (all).

- [ ] **Step 5: Full suite and goldens**

Run: `python -m pytest -m "not network" -q`
Expected: All PASS (additive task).

- [ ] **Step 6: Commit**

```bash
git add tools/theory.py tests/test_theory.py tests/test_theory_run.py tests/test_context.py tests/test_stub_theory.py
git commit -m "feat: Theory/TheoryRun/TheoryContext contract with unskippable finish()"
```

---

### Task 7: `insider_judgment` adapter (Phase 3b)

**Files:**
- Modify: `theories/insider_bias/insider_judgment/pipeline.py` (**one added key** — the only theory-module edit before Phase 5, spec §4.7)
- Create: `theories/insider_bias/insider_judgment/theory.py`
- Modify: `theories/insider_bias/insider_judgment/__init__.py`
- Test: `tests/theories/test_insider_judgment_theory.py`

**Interfaces:**
- Consumes: `pipeline.run_mechanical_stages`, `pipeline.dedupe_by_event`, `pipeline.build_blind_payload`, `gate.PLAUSIBLE`, `Theory`/`ScreenResult`/`Verdict`/`Edge.from_bucket`, `Market.from_mapping`.
- Produces: `InsiderJudgmentTheory` (id `insider_judgment`, version **3**, `uses_llm_judgment=True`, prompts for `analysis` and `final_review`); package-level `THEORY` singleton; `pipeline.run_mechanical_stages` gains `"survivor_candidates"` in its returned dict.

**Golden rule for this task (spec §4.7): adding a key to the funnel dict is permitted; changing any existing key's value is not.** The Phase-0 golden for `run_mechanical_stages` is a subset match for exactly this reason; every other golden stays whole-value.

- [ ] **Step 1: Add the `survivor_candidates` key**

In `pipeline.run_mechanical_stages`, extend the returned dict (after `"survivor_markets": len(kept),`):

```python
        "survivor_candidates": kept,
```

and add the key to the docstring's listed shape. This changes no computation — `kept` already exists at `pipeline.py:124` and was previously discarded after being counted.

Run: `python -m pytest tests/characterization -q` — Expected: PASS (subset match admits the new key).

- [ ] **Step 2: Write the failing adapter tests**

Create `tests/theories/test_insider_judgment_theory.py`:

```python
from datetime import datetime, timezone

import pytest

from tests.characterization import conftest as cz
from tools import db, ledger, provenance, theories
from tools.domain import ScreenResult, Verdict
from tools.theory import TheoryContext

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
TS = "2026-08-24T12:00:00Z"


def _theory():
    from theories.insider_bias.insider_judgment import THEORY
    return THEORY


def fake_ctx(board, conn=None, judge_model=None):
    return TheoryContext(conn=conn, board=board, now=cz.frozen_now(),
                         judge_model=judge_model)


def test_screen_reproduces_the_golden_funnel():
    result = _theory().screen(fake_ctx(cz.board_input()))
    assert isinstance(result, ScreenResult)
    want = cz.load_golden("run_mechanical_stages")
    for key in ("board_markets", "screened_markets", "events", "gated_out",
                "survivors", "survivor_markets"):
        assert result.funnel[key] == want[key]
    # gate_removed: every category except PLAUSIBLE, summing to gated_out
    assert "PLAUSIBLE" not in result.gate_removed
    assert sum(result.gate_removed.values()) == want["gated_out"]
    assert len(result.candidates) == want["survivor_markets"]


def test_judgment_payload_equals_the_golden_blind_payload():
    theory = _theory()
    run = theory.start(fake_ctx(cz.board_input()))
    assert run.payload == cz.load_golden("blind_payload")


def test_judgment_payload_is_none_when_nothing_survives():
    assert _theory().judgment_payload([]) is None


def _seed(conn):
    theories.register(conn, "insider_judgment", "Insider Judgment",
                      "theories/insider_bias/insider_judgment", now=TS)
    with db.write(conn):
        conn.execute(
            "UPDATE theories SET version = 3, status = 'testing' "
            "WHERE id = 'insider_judgment'")
    theories.set_uses_llm_judgment(conn, "insider_judgment", True)


def _tiny_board():
    """Two sibling strikes on one event that clear every screen threshold
    and the gate (KXFAKE matches no NO_RULES family)."""
    from tools.domain import Market
    def m(ticker):
        return Market(platform="kalshi", ticker=ticker, title="t?",
                      yes_bid=0.78, yes_ask=0.80, no_bid=0.20, no_ask=0.22,
                      mid=0.79, spread=0.02, volume=900.0, is_open=True,
                      close_time="2026-08-26T00:00:00Z", status="active",
                      event_ticker="KXFAKE-26", series_ticker="KXFAKE",
                      rules_primary="r", raw={"ticker": ticker})
    return [m("KXFAKE-26-A"), m("KXFAKE-26-B")]


def test_one_verdict_reaches_every_sibling_and_records(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    _seed(conn)
    ctx = TheoryContext.build(conn=conn, board=_tiny_board(), now=NOW,
                              judge_model="test-model")
    run = _theory().start(ctx)
    assert run.needs_judgment and len(run.candidates) == 2
    result = run.apply(
        {"KXFAKE-26": Verdict(bucket="strong", rationale="pre-taped")}
    ).finish()
    assert len(result.opportunity_ids) == 2       # siblings share the verdict
    for opp_id in result.opportunity_ids:
        row = ledger.get_opportunity(conn, opp_id)
        assert row["confidence"] == "strong"
        assert row["judged_blind"] == 1
        assert row["edge_basis"] == "prior"       # no measured rates yet
        assert row["edge_pts_net"] == pytest.approx(4.0)   # THEORY.md prior
        assert row["theory_version"] == 3
    runs = provenance.list_judgment_runs(conn, theory_id="insider_judgment")
    assert {r["stage"] for r in runs} == {"analysis", "final_review"}
    assert all(r["model"] == "test-model" for r in runs)
    conn.close()


def test_an_unknown_bucket_is_refused(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    _seed(conn)
    ctx = TheoryContext.build(conn=conn, board=_tiny_board(), now=NOW,
                              judge_model="test-model")
    run = _theory().start(ctx)
    run.apply({"KXFAKE-26": Verdict(bucket="certain")})
    with pytest.raises(ValueError, match="scale"):
        run.finish(dry_run=True)
    conn.close()
```

- [ ] **Step 3: Run to verify they fail**

Run: `python -m pytest tests/theories/test_insider_judgment_theory.py -q`
Expected: FAIL — `ImportError: cannot import name 'THEORY'`.

- [ ] **Step 4: Write the adapter**

Create `theories/insider_bias/insider_judgment/theory.py`:

```python
"""Contract adapter (OOP spec section 4.7): wraps the existing pipeline,
moves NO decision logic. screen.py, gate.py and the pipeline internals are
untouched; this file only converts shapes at the boundary.

Buckets and priors are lifted VERBATIM from THEORY.md's "Confidence
buckets" table. Changing either is a decision-procedure change and bumps
the version -- exactly like a threshold.

Note what is NOT here: no instance state. The funnel travels on the
ScreenResult, verdicts travel on the TheoryRun (see the spec's
_last_funnel post-mortem, section 4.4).
"""

from __future__ import annotations

from theories.insider_bias.insider_judgment import gate, pipeline
from tools.domain import (Candidate, Edge, Leg, Market, ScoredCandidate,
                          ScreenResult, Verdict)
from tools.theory import Theory, TheoryContext

#: THEORY.md "Confidence buckets": conservative priors, standing in only
#: until a bucket has MIN_BUCKET_N settled results.
PRIORS = {"strong": 4.0, "moderate": 2.0, "weak": 0.0}
BUCKETS = tuple(PRIORS)

FUNNEL_KEYS = ("board_markets", "screened_markets", "events", "gated_out",
               "survivors", "survivor_markets")


def _to_candidate(c: dict) -> Candidate:
    return Candidate(
        legs=(Leg(market=Market.from_mapping(c), side=c["fav_side"],
                  price=c["entry_price"]),),
        days_to_close=c["days_to_close"],
    )


class InsiderJudgmentTheory(Theory):
    id = "insider_judgment"
    name = "Insider Judgment"
    version = 3
    uses_llm_judgment = True
    prompts = {
        "analysis":
            "theories/insider_bias/insider_judgment/prompts/analysis.md",
        "final_review":
            "theories/insider_bias/insider_judgment/prompts/final_review.md",
    }

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        funnel = pipeline.run_mechanical_stages(ctx.board, ctx.now)
        return ScreenResult(
            candidates=tuple(_to_candidate(c)
                             for c in funnel["survivor_candidates"]),
            funnel={k: funnel[k] for k in FUNNEL_KEYS},
            gate_removed={k: v for k, v in funnel["gate_counts"].items()
                          if k != gate.PLAUSIBLE},
        )

    def judgment_payload(self, cands):
        if not cands:
            return None
        # Rebuilt from the candidates handed in -- no instance state. The
        # payload is blind by whitelist; assert_blind re-checks inside.
        return pipeline.build_blind_payload(
            pipeline.dedupe_by_event(cands), cands)

    def price(self, ctx, cands, verdicts=None):
        verdicts = verdicts or {}
        rates = (ctx.bucket_rates(self.id, self.version)
                 if ctx.bucket_rates else {})
        out = []
        for c in cands:
            v = verdicts.get(c.key)
            if v is None:
                continue        # unjudged this run: unassessed remainder
            if v.bucket not in BUCKETS:
                raise ValueError(
                    f"unknown bucket {v.bucket!r}; this theory's declared "
                    f"scale is {BUCKETS}"
                )
            out.append(ScoredCandidate(
                candidate=c,
                edge=Edge.from_bucket(v.bucket, c.entry_price, rates, PRIORS),
                confidence=v.bucket,
                rationale=v.rationale,
                judged_blind=True,      # the payload provably carried no price
            ))
        return out
```

Set `theories/insider_bias/insider_judgment/__init__.py` (currently empty) to:

```python
from theories.insider_bias.insider_judgment.theory import InsiderJudgmentTheory

THEORY = InsiderJudgmentTheory()
```

- [ ] **Step 5: Run tests, goldens, full suite**

Run: `python -m pytest tests/theories/test_insider_judgment_theory.py tests/characterization -q` then `python -m pytest -m "not network" -q`
Expected: All PASS. The goldens prove the added dict key changed no existing value.

- [ ] **Step 6: Commit**

```bash
git add theories/insider_bias/insider_judgment tests/theories/test_insider_judgment_theory.py
git commit -m "feat: insider_judgment adapter; pipeline exposes survivor_candidates"
```

---

### Task 8: `mention_family` adapter (Phase 3c)

**Files:**
- Create: `theories/insider_bias/mention_family/theory.py`
- Modify: `theories/insider_bias/mention_family/__init__.py`
- Test: `tests/theories/test_mention_family_theory.py`

**Interfaces:**
- Consumes: `mention_bucket.find_candidates`, `mention_bucket.rank`, `mention_bucket.measured_rate`, `mention_bucket.MEASURED_RATE_RUN_ID`, `screen.MAX_DAYS_AHEAD`.
- Produces: `MentionFamilyTheory` (id `mention_family`, version 1, `uses_llm_judgment=False`, `prompts={"other": "theories/insider_bias/mention_family/mention_bucket.py"}` — decision 7 makes `finish()` write the voluntary deterministic provenance row); package `THEORY` singleton.

**What survives untouched, on purpose (spec §3.1):** `rank` and `rank_preview` stay two separate functions — the adapter's contract path uses only `rank` (the validated 14-day horizon, empty `confidence_suffix`); `rank_preview` remains a directly-callable ad-hoc path, and `mention_bucket.record()` keeps working for it.

- [ ] **Step 1: Write the failing tests**

Create `tests/theories/test_mention_family_theory.py`:

```python
from datetime import datetime, timezone

import pytest

from tests.characterization import conftest as cz
from theories.insider_bias.mention_family import mention_bucket
from tools import db, ledger, theories
from tools.theory import TheoryContext

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
TS = "2026-08-24T12:00:00Z"


def _theory():
    from theories.insider_bias.mention_family import THEORY
    return THEORY


@pytest.fixture
def frozen_rates(monkeypatch):
    monkeypatch.setattr(mention_bucket, "measured_rate",
                        lambda conn: cz.frozen_rates())
    return cz.frozen_rates()


def test_price_reproduces_the_golden_rank(frozen_rates):
    ctx = TheoryContext(conn=None, board=cz.board_input(),
                        now=cz.frozen_now())
    result = _theory().start(ctx).finish(dry_run=True)
    assert result.judged is False
    assert cz.proj(list(result.scored)) == cz.load_golden("mention_rank")
    assert all(s.confidence for s in result.scored)


def _seed(conn):
    theories.register(conn, "mention_family", "Mention Family",
                      "theories/insider_bias/mention_family", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET status='testing'"
                     " WHERE id='mention_family'")


def test_finish_writes_the_same_rows_record_would(tmp_path, frozen_rates):
    board = cz.board_input()
    ranked = mention_bucket.rank(
        mention_bucket.find_candidates(board, now=cz.frozen_now()),
        cz.frozen_rates())
    if not ranked:
        pytest.skip("fixture holds no live mention-family candidates")

    via_record = db.connect(tmp_path / "a.db"); db.init_db(via_record)
    _seed(via_record)
    mention_bucket.record(via_record, ranked, run_id="live")

    via_finish = db.connect(tmp_path / "b.db"); db.init_db(via_finish)
    _seed(via_finish)
    ctx = TheoryContext.build(conn=via_finish, board=board,
                              now=cz.frozen_now())
    _theory().start(ctx).finish()

    fields = ("kalshi_ticker, outcome, entry_price, edge_pts_net, "
              "edge_basis, confidence, rationale, spread_at_call, "
              "volume_at_call")
    sql = f"SELECT {fields} FROM opportunities ORDER BY kalshi_ticker"
    a = [tuple(r) for r in via_record.execute(sql).fetchall()]
    b = [tuple(r) for r in via_finish.execute(sql).fetchall()]
    assert a == b
    via_record.close(); via_finish.close()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/theories/test_mention_family_theory.py -q`
Expected: FAIL — `ImportError: cannot import name 'THEORY'`.

- [ ] **Step 3: Write the adapter**

Create `theories/insider_bias/mention_family/theory.py`:

```python
"""Contract adapter for the fully mechanical mention_family theory.

Wraps find_candidates/rank unchanged. The contract path is the VALIDATED
14-day horizon only (empty confidence_suffix); rank_preview and its
"_preview_*" suffixes remain a deliberate, directly-callable ad-hoc path
outside the contract -- a wider horizon changes what edge_basis a caller
may honestly attach, which is why they are two functions (spec 3.1).

The rationale strings replicate mention_bucket.record()'s exactly, so a
row written through finish() is indistinguishable from one written through
record() -- tested against the ledger, not assumed.
"""

from __future__ import annotations

from theories.insider_bias import screen
from theories.insider_bias.mention_family import mention_bucket
from tools.domain import (Candidate, Edge, Leg, Market, ScoredCandidate,
                         ScreenResult)
from tools.theory import Theory, TheoryContext


def _to_candidate(c: dict) -> Candidate:
    return Candidate(
        legs=(Leg(market=Market.from_mapping(c), side=c["fav_side"],
                  price=c["entry_price"]),),
        days_to_close=c["days_to_close"],
    )


def _rationale(r: dict) -> str:
    """Byte-for-byte the text mention_bucket.record() writes."""
    bin_rate_note = (f"measured rate for bucket {r['bucket']} "
                     f"({mention_bucket.MEASURED_RATE_RUN_ID})")
    basis_note = (
        f"{bin_rate_note}, applied directly"
        if r["edge_basis"] == "measured"
        else (
            f"{bin_rate_note} APPLIED AS AN EXTRAPOLATION to a "
            f"days-to-close horizon the backtest never tested "
            f"(>{screen.MAX_DAYS_AHEAD:.0f} days) -- a modeling "
            f"assumption, not a measurement of this population"
        )
    )
    return (
        f"Mechanical mention_family bucket, no judgment applied: "
        f"{basis_note}. Volume (${r.get('volume', 0):,.0f}) is a "
        f"tiebreaker only, not part of the edge -- see "
        f"mention_bucket.py module docstring."
    )


class MentionFamilyTheory(Theory):
    id = "mention_family"
    name = "Mention Family"
    version = 1
    uses_llm_judgment = False
    # Voluntary self-documentation: the deciding artifact is this module's
    # code. finish() records it with model='none (deterministic)', matching
    # mention_bucket.record_provenance's long-standing convention.
    prompts = {"other":
               "theories/insider_bias/mention_family/mention_bucket.py"}

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        hits = mention_bucket.find_candidates(ctx.board, now=ctx.now)
        return ScreenResult(
            candidates=tuple(_to_candidate(h) for h in hits),
            funnel={"board_markets": len(ctx.board),
                    "family_candidates": len(hits)},
        )

    def price(self, ctx, cands, verdicts=None):
        rates = mention_bucket.measured_rate(ctx.conn)
        ranked = mention_bucket.rank([dict(c) for c in cands], rates)
        out = []
        for r in ranked:
            measured = rates.get(r["bucket"]) or {}
            out.append(ScoredCandidate(
                candidate=_to_candidate(r),
                edge=Edge(pts_net=r["edge_pts_net"], basis=r["edge_basis"],
                          model_prob=measured.get("win_rate")),
                confidence=r["bucket"],
                rationale=_rationale(r),
            ))
        return out
```

Set `theories/insider_bias/mention_family/__init__.py` to:

```python
from theories.insider_bias.mention_family.theory import MentionFamilyTheory

THEORY = MentionFamilyTheory()
```

- [ ] **Step 4: Run tests, goldens, full suite**

Run: `python -m pytest tests/theories -q` then `python -m pytest -m "not network" -q`
Expected: All PASS. If the row-equivalence test fails on `rationale`, the adapter's `_rationale` drifted from `record()` — fix the adapter, never `record()`.

Note for the equivalence test: `record()`'s `model_prob` is not written by `record()` at all while `finish()` writes it — that is why `model_prob` is deliberately absent from the compared field list. It is additional information on the new path, not a divergence in shared fields.

- [ ] **Step 5: Commit**

```bash
git add theories/insider_bias/mention_family tests/theories/test_mention_family_theory.py
git commit -m "feat: mention_family adapter riding the shared finish() path"
```

---

### Task 9: Discovery — `tools/registry.py` and the conventions tests (Phase 3d)

**Files:**
- Create: `tools/registry.py`
- Test: `tests/test_registry.py`, `tests/test_conventions.py`

**Interfaces:**
- Consumes: `Theory`, `theories.list_theories`, `theories.SCANNABLE_STATUSES`, `db.REPO_ROOT`, both `THEORY` singletons.
- Produces: `registry.discover() -> dict[str, Theory]`, `registry.running(conn) -> list[Theory]`, `registry.check_drift(conn) -> list[str]`.

**Separation of authority (spec §4.6):** the database owns *status and version*; the Python class owns *procedure*. `running()` joins them and fails loudly on drift. `check_drift` detects four mismatch kinds: class-with-no-row, scannable-row-with-no-class, version disagreement, `uses_llm_judgment` disagreement (the fourth routes dispatch and gates provenance, so drift in it misroutes silently).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_registry.py`:

```python
import pytest

from tools import db, registry, theories

TS = "2026-08-24T12:00:00Z"


def test_discover_finds_both_real_theories():
    found = registry.discover()
    assert set(found) >= {"insider_judgment", "mention_family"}
    assert found["insider_judgment"].version == 3
    assert found["insider_judgment"].uses_llm_judgment is True
    assert found["mention_family"].uses_llm_judgment is False


def test_theory_packages_skips_template_and_studies(tmp_path):
    (tmp_path / "real_one").mkdir()
    (tmp_path / "real_one" / "THEORY.md").write_text("h", encoding="utf-8")
    (tmp_path / "_TEMPLATE").mkdir()
    (tmp_path / "_TEMPLATE" / "THEORY.md").write_text("t", encoding="utf-8")
    (tmp_path / "a_study").mkdir()
    (tmp_path / "a_study" / "THEORY.md").write_text("s", encoding="utf-8")
    (tmp_path / "a_study" / "STUDY.md").write_text("s", encoding="utf-8")
    got = registry._theory_packages(root=tmp_path)
    assert got == [f"{tmp_path.name}.real_one"]


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    yield c
    c.close()


def _register_matching(conn):
    for tid, name, version, uses in (
        ("insider_judgment", "Insider Judgment", 3, True),
        ("mention_family", "Mention Family", 1, False),
    ):
        theories.register(conn, tid, name, f"theories/{tid}", now=TS)
        with db.write(conn):
            conn.execute("UPDATE theories SET version=?, status='testing'"
                         " WHERE id=?", (version, tid))
        theories.set_uses_llm_judgment(conn, tid, uses, now=TS)


def test_check_drift_is_empty_when_code_and_db_agree(conn):
    _register_matching(conn)
    assert registry.check_drift(conn) == []


def test_check_drift_catches_all_four_mismatch_kinds(conn):
    # 1. class with no DB row (nothing registered yet)
    problems = registry.check_drift(conn)
    assert any("no DB registry row" in p for p in problems)

    _register_matching(conn)

    # 2. version disagreement
    with db.write(conn):
        conn.execute("UPDATE theories SET version=99"
                     " WHERE id='mention_family'")
    assert any("version" in p for p in registry.check_drift(conn))
    with db.write(conn):
        conn.execute("UPDATE theories SET version=1"
                     " WHERE id='mention_family'")

    # 3. uses_llm_judgment disagreement
    theories.set_uses_llm_judgment(conn, "mention_family", True, now=TS)
    assert any("uses_llm_judgment" in p for p in registry.check_drift(conn))
    theories.set_uses_llm_judgment(conn, "mention_family", False, now=TS)

    # 4. scannable DB row with no class
    theories.register(conn, "ghost", "Ghost", "theories/ghost", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET status='testing' WHERE id='ghost'")
    assert any("ghost" in p for p in registry.check_drift(conn))


def test_a_proposed_row_without_code_is_not_drift(conn):
    _register_matching(conn)
    theories.register(conn, "someday", "Someday", "theories/someday", now=TS)
    assert registry.check_drift(conn) == []      # proposed: no code required


def test_running_returns_scannable_theories_and_raises_on_drift(conn):
    _register_matching(conn)
    ids = [t.id for t in registry.running(conn)]
    assert ids == ["insider_judgment", "mention_family"]
    with db.write(conn):
        conn.execute("UPDATE theories SET version=99"
                     " WHERE id='mention_family'")
    with pytest.raises(RuntimeError, match="drift"):
        registry.running(conn)
```

Create `tests/test_conventions.py`:

```python
"""Repo-wide conventions the OOP layer promises (spec sections 3.2, 4.2,
4.5c, 9): every theory package exposes a proper singleton, nobody
overrides the workflow, a Verdict can never grow a number, and the
migration shim is only exercised from allowlisted modules."""

from dataclasses import fields

from tools import domain, registry
from tools.theory import Theory, TheoryRun


def test_every_theory_package_exposes_a_conforming_singleton():
    for tid, theory in registry.discover().items():
        assert isinstance(theory, Theory)
        assert theory.id == tid
        assert isinstance(theory.version, int)
        for stage, path in theory.prompts.items():
            from tools.provenance import VALID_STAGES
            assert stage in VALID_STAGES


def test_no_theory_overrides_the_inherited_workflow():
    for theory in registry.discover().values():
        for cls in type(theory).__mro__[:-3]:       # up to (not incl.) Theory
            assert "start" not in vars(cls)
            assert "finish" not in vars(cls)
    assert TheoryRun.__subclasses__() == []


def test_verdict_declares_no_numeric_field():
    """CLAUDE.md's 'never state a probability you introspected', as a type
    property: an out-of-process judge has no channel to hand back a number."""
    for f in fields(domain.Verdict):
        annotation = str(f.type)
        assert "float" not in annotation and "int" not in annotation, (
            f"Verdict.{f.name} is numeric -- a judge returns a category, "
            "never a number"
        )


#: Modules still permitted to use dict-style access on domain objects.
#: Tasks 12-13 shrink this list as call sites port; Task 14 empties it and
#: deletes the shim. Test modules are exempt (they test the shim itself).
SHIM_ALLOWLIST = {
    "tools.board",
    "tools.snapshot",
    "tools.match_market",
    "theories.insider_bias.screen",
    "theories.insider_bias.insider_judgment.gate",
    "theories.insider_bias.insider_judgment.pipeline",
    "theories.insider_bias.insider_judgment.theory",
    "theories.insider_bias.insider_judgment.backtest",
    "theories.insider_bias.mention_family.mention_bucket",
    "theories.insider_bias.mention_family.theory",
}


def test_shim_is_exercised_only_from_allowlisted_modules():
    from tests.characterization import conftest as cz
    from theories.insider_bias.insider_judgment import THEORY as ij
    from theories.insider_bias.mention_family import THEORY as mf
    from tools.theory import TheoryContext

    domain.SHIM_CALLERS.clear()
    ctx = TheoryContext(conn=None, board=cz.board_input(),
                        now=cz.frozen_now())
    run = ij.start(ctx)                       # exercises the whole pipeline
    mf.screen(ctx)
    prod = {m for m in domain.SHIM_CALLERS
            if m.startswith(("tools.", "theories."))}
    assert prod <= SHIM_ALLOWLIST, sorted(prod - SHIM_ALLOWLIST)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_registry.py tests/test_conventions.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.registry'`.

- [ ] **Step 3: Write `tools/registry.py`**

```python
"""Discovery: join each theory's code with its DB registry row.

Separation of authority (spec section 4.6): the database is the source of
truth for a theory's STATUS and VERSION; the Python class is the source of
truth for its PROCEDURE. running() joins them; check_drift() fails loudly
when they disagree, because silent drift lets a session run v3 code while
recording v2 rows -- the silent-merge failure the versioning rule exists
to prevent.

What is discovered: every folder under theories/ carrying a THEORY.md,
excluding _TEMPLATE and any folder that also carries STUDY.md -- a study
produces theories, not bets, and stays a plain script (spec section 4.5c).
"""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

from tools import theories as theories_db
from tools.db import REPO_ROOT
from tools.theory import Theory

THEORIES_ROOT = REPO_ROOT / "theories"


def _theory_packages(root: Path = THEORIES_ROOT) -> list[str]:
    """Dotted module paths for every theory package under `root`."""
    out = []
    for marker in sorted(root.rglob("THEORY.md")):
        folder = marker.parent
        if folder.name == "_TEMPLATE" or (folder / "STUDY.md").exists():
            continue
        rel = folder.relative_to(root.parent)
        out.append(".".join(rel.parts))
    return out


def discover() -> dict[str, Theory]:
    """Import every theory package and collect its THEORY singleton."""
    found: dict[str, Theory] = {}
    for module_path in _theory_packages():
        module = importlib.import_module(module_path)
        instance = getattr(module, "THEORY", None)
        if instance is None:
            raise RuntimeError(
                f"{module_path} has a THEORY.md but exposes no THEORY "
                "singleton; add `THEORY = <YourTheory>()` to its "
                "__init__.py, or mark the folder as a study with STUDY.md"
            )
        if not isinstance(instance, Theory):
            raise RuntimeError(f"{module_path}.THEORY is not a Theory")
        if instance.id in found:
            raise RuntimeError(f"duplicate theory id {instance.id!r}")
        found[instance.id] = instance
    return found


def check_drift(conn: sqlite3.Connection) -> list[str]:
    """Mismatches between code and DB. Empty means healthy.

    The class side is checked unconditionally; the DB side only for
    SCANNABLE_STATUSES -- a proposed or paused row legitimately has no
    code yet, but a scannable one with no class cannot run and a version
    or uses_llm_judgment disagreement records rows under the wrong
    procedure identity.
    """
    problems: list[str] = []
    by_id = discover()
    rows = {r["id"]: r for r in theories_db.list_theories(conn)}
    for tid, theory in sorted(by_id.items()):
        row = rows.get(tid)
        if row is None:
            problems.append(f"class {tid!r} has no DB registry row")
            continue
        if theory.version != row["version"]:
            problems.append(
                f"{tid}: class version {theory.version} != DB version "
                f"{row['version']}")
        if bool(theory.uses_llm_judgment) != bool(row["uses_llm_judgment"]):
            problems.append(
                f"{tid}: uses_llm_judgment ClassVar "
                f"{theory.uses_llm_judgment} != DB flag "
                f"{bool(row['uses_llm_judgment'])}")
    for tid, row in sorted(rows.items()):
        if (row["status"] in theories_db.SCANNABLE_STATUSES
                and tid not in by_id):
            problems.append(
                f"DB row {tid!r} is {row['status']} but has no class")
    return problems


def running(conn: sqlite3.Connection) -> list[Theory]:
    """Discovered theories restricted to SCANNABLE_STATUSES, drift-checked."""
    problems = check_drift(conn)
    if problems:
        raise RuntimeError("registry drift: " + "; ".join(problems))
    by_id = discover()
    return [by_id[r["id"]]
            for r in theories_db.list_theories(conn, running_only=True)
            if r["id"] in by_id]
```

- [ ] **Step 4: Run tests and full suite**

Run: `python -m pytest tests/test_registry.py tests/test_conventions.py -q` then `python -m pytest -m "not network" -q`
Expected: All PASS.

- [ ] **Step 5: Verify drift against the LIVE database**

```bash
python -c "from tools import db, registry; c = db.connect(); print(registry.check_drift(c) or 'no drift')"
```

Expected: `no drift` (live rows: insider_judgment v3 uses_llm=1, mention_family v1 uses_llm=0). If anything prints, stop and report — do not edit the DB to make it pass.

- [ ] **Step 6: Commit**

```bash
git add tools/registry.py tests/test_registry.py tests/test_conventions.py
git commit -m "feat: theory discovery with four-way drift check against the registry"
```

---

### Task 10: Cross-cutting proofs — parallel writes, blind leak, backlog fit (Phase 3e)

**Files:**
- Create: `tests/test_parallel_writes.py`, `tests/test_backlog_fit.py`
- Modify: `tests/theories/test_insider_judgment_theory.py` (append the leak test)

**Interfaces:**
- Consumes: everything from Tasks 1–9; `ledger.record_basket`, `ledger.get_legs`; the `theory_facts` table.
- Produces: nothing — these are the spec §7 proofs that the claims in §4.9, §8.3, and §3.2 hold in code rather than in prose.

- [ ] **Step 1: Write the parallel-writes test**

Create `tests/test_parallel_writes.py`:

```python
"""Verifies -- not assumes -- the spec section 4.9 concurrency claim: WAL
plus the 30s busy timeout let N connections, each recording a DIFFERENT
theory's rows, all commit. Each thread opens its own connection; a
sqlite3.Connection is never shared across the boundary."""

import threading

from tools import db, ledger, theories

TS = "2026-08-24T12:00:00Z"


def test_concurrent_connections_each_writing_their_own_theory_all_commit(tmp_path):
    path = tmp_path / "t.db"
    setup = db.connect(path)
    db.init_db(setup)
    for i in range(4):
        theories.register(setup, f"t{i}", f"T{i}", "x", now=TS)
    setup.close()

    errors: list[Exception] = []

    def work(i: int) -> None:
        try:
            conn = db.connect(path)
            for j in range(5):
                ledger.record_opportunity(
                    conn, theory_id=f"t{i}", theory_version=1,
                    kalshi_ticker=f"KX{i}-{j}", outcome="yes",
                    entry_price=0.5, edge_pts_net=3.0, now=TS)
            conn.close()
        except Exception as exc:          # surfaced below, never swallowed
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    check = db.connect(path)
    n = check.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
    assert n == 20
    check.close()
```

- [ ] **Step 2: Write the blind-leak test (spec §8.3)**

Append to `tests/theories/test_insider_judgment_theory.py`:

```python
def test_naively_serializing_a_candidate_trips_assert_blind():
    """A Candidate composes a Market carrying every price field. Dumping
    one into a judgment payload must trip the guard -- this proves the
    refactor made the mistake easier to commit but no easier to get away
    with (spec section 8.3)."""
    from dataclasses import asdict

    from theories.insider_bias.insider_judgment import pipeline
    from tools.domain import Candidate, Leg

    cand = Candidate(legs=(Leg(market=_tiny_board()[0], side="yes",
                               price=0.80),), days_to_close=2.0)
    with pytest.raises(pipeline.BlindPayloadError):
        pipeline.assert_blind([asdict(cand)])
```

- [ ] **Step 3: Write the backlog-fit stubs (spec §7, criteria 17–19)**

Create `tests/test_backlog_fit.py`:

```python
"""The section 3.2 litmus test widened: one stub per shape the backlog
review found the first draft could not express. A test is how the four
shapes STAY expressible -- if a change to the contract breaks one of these,
the contract got tighter than the backlog allows, and the contract is what
is wrong (spec section 8.6)."""

import json

import pytest

from tools import db, ledger, theories
from tools.domain import Candidate, Edge, Leg, Market, ScoredCandidate
from tools.theory import Theory, TheoryContext

from tests.test_theory import NOW, TS, fake_ctx, mkm


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    yield c
    c.close()


def _seed(conn, tid):
    theories.register(conn, tid, tid, "x", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET status='testing' WHERE id=?",
                     (tid,))


def test_a_basket_producer_records_one_position_with_legs(conn):
    """structural-arb-like: a NO pair whose asks sum under the payout."""

    class BasketArb(Theory):
        id, name, version = "stub_basket", "Stub Basket", 1

        def screen(self, ctx):
            legs = tuple(Leg(market=m, side="no", price=m.no_ask)
                         for m in ctx.board)
            return [Candidate(legs=legs, days_to_close=1.0, max_payout=1.0)]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(
                candidate=c,
                edge=Edge(pts_net=(c.max_payout - c.cost) * 100.0,
                          basis="model"))
                for c in cands if c.cost < c.max_payout]

    _seed(conn, "stub_basket")
    board = [mkm("KXA-26", event="KXE"), mkm("KXB-26", event="KXE")]
    board = [Market(platform="kalshi", ticker=m.ticker, no_ask=0.45,
                    is_open=True, event_ticker="KXE", raw={}) for m in board]
    ctx = TheoryContext.build(conn=conn, board=board, now=NOW)
    result = BasketArb().start(ctx).finish()
    assert len(result.opportunity_ids) == 1
    row = ledger.get_opportunity(conn, result.opportunity_ids[0])
    assert row["position_kind"] == "basket"
    assert row["leg_count"] == 2
    assert row["entry_price"] == pytest.approx(0.90)
    assert len(ledger.get_legs(conn, result.opportunity_ids[0])) == 2


def test_an_external_source_theory_takes_fetch(conn):
    """vol-crossing-like: fetches Coinbase-style candles through the Fetch
    seam; a canned payload replaces the network with no monkeypatch."""

    class VolCrossing(Theory):
        id, name, version = "stub_vol", "Stub Vol", 1

        def __init__(self, fetch):
            self.fetch = fetch          # instance CONFIG, not run state

        def screen(self, ctx):
            candles = self.fetch("https://example.invalid/candles")
            if max(c["high"] for c in candles) < 60000:
                return []
            m = Market(platform="kalshi", ticker="KXBTC-26", is_open=True,
                       raw={})
            return [Candidate(legs=(Leg(market=m, side="yes", price=0.3),),
                              days_to_close=1.0)]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(candidate=c,
                                    edge=Edge(pts_net=6.0, basis="model"))
                    for c in cands]

    canned = lambda url, params=None, timeout=30: [
        {"high": 61000}, {"high": 59000}]
    result = VolCrossing(canned).start(fake_ctx()).finish(dry_run=True)
    assert result.funnel["scored"] == 1


def test_a_pair_store_theory_reads_theory_facts_mechanically(conn):
    """metaculus-gap-like: a model confirmed the pair once at construction
    time; every per-run decision is pure arithmetic, so
    uses_llm_judgment=False and the run needs no per-run provenance."""
    _seed(conn, "stub_pairs")
    with db.write(conn):
        conn.execute(
            "INSERT INTO theory_facts (theory_id, kind, key, value_json,"
            " established_at) VALUES ('stub_pairs', 'market_pair',"
            " 'KXCPI-26', ?, ?)",
            (json.dumps({"kalshi": "KXCPI-26", "external_prob": 0.62}), TS))

    class PairStore(Theory):
        id, name, version = "stub_pairs", "Stub Pairs", 1

        def screen(self, ctx):
            rows = ctx.conn.execute(
                "SELECT value_json FROM theory_facts"
                " WHERE theory_id='stub_pairs' AND kind='market_pair'"
            ).fetchall()
            out = []
            for r in rows:
                pair = json.loads(r["value_json"])
                m = Market(platform="kalshi", ticker=pair["kalshi"],
                           is_open=True, raw={})
                out.append(Candidate(
                    legs=(Leg(market=m, side="yes", price=0.5),),
                    days_to_close=2.0))
            return out

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(candidate=c,
                                    edge=Edge(pts_net=12.0, basis="model",
                                              model_prob=0.62))
                    for c in cands]

    ctx = TheoryContext.build(conn=conn, board=[], now=NOW)
    result = PairStore().start(ctx).finish()
    assert len(result.opportunity_ids) == 1
    assert ledger.get_opportunity(
        conn, result.opportunity_ids[0])["kalshi_ticker"] == "KXCPI-26"


def test_a_non_board_theory_ignores_ctx_board_entirely():
    """whale-follow-like: its universe is Polymarket flow, not the board."""

    class WhaleFollow(Theory):
        id, name, version = "stub_whale", "Stub Whale", 1

        def screen(self, ctx):
            assert ctx.board == []      # never touched; nothing to touch
            m = Market(platform="kalshi", ticker="KXWHALE-26", is_open=True,
                       raw={})
            return [Candidate(legs=(Leg(market=m, side="yes", price=0.4),),
                              days_to_close=3.0)]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(candidate=c,
                                    edge=Edge(pts_net=5.0, basis="model"))
                    for c in cands]

    result = WhaleFollow().start(fake_ctx()).finish(dry_run=True)
    assert result.funnel["scored"] == 1
```

- [ ] **Step 4: Run the new tests, then everything**

Run: `python -m pytest tests/test_parallel_writes.py tests/test_backlog_fit.py tests/theories/test_insider_judgment_theory.py -q`
Expected: PASS.

Run: `python -m pytest -m "not network" -q`
Expected: All PASS. Also run the two real adapters **sequentially in one process** as spec §8.7 requires before any parallel dispatch is documented:

```bash
python -c "
from tests.characterization import conftest as cz
from tools.theory import TheoryContext
from theories.insider_bias.insider_judgment import THEORY as ij
from theories.insider_bias.mention_family import THEORY as mf
ctx = TheoryContext(conn=None, board=cz.board_input(), now=cz.frozen_now())
r1 = ij.start(ctx)
print('ij candidates:', len(r1.candidates), 'needs_judgment:', r1.needs_judgment)
r2 = mf.start(ctx)
print('mf candidates:', len(r2.candidates), 'needs_judgment:', r2.needs_judgment)
"
```

Expected: both counts print, `ij` needs judgment, `mf` does not, no cross-talk.

- [ ] **Step 5: Commit**

```bash
git add tests/test_parallel_writes.py tests/test_backlog_fit.py tests/theories/test_insider_judgment_theory.py
git commit -m "test: parallel writes, blind-leak guard, and the four backlog shapes"
```

---

### Task 11: Documentation and skills rewrite (Phase 4)

**Files:**
- Modify: `tools/README.md`, `CLAUDE.md`, `.claude/skills/find-edge/SKILL.md`, `.claude/skills/propose-theory/SKILL.md`, `.claude/skills/go/SKILL.md`, `.claude/skills/backtest-theory/SKILL.md`

**Interfaces:** consumes everything; produces no code.

**Phase 4 lands before Phase 5 deliberately (spec §6):** the conventions must be written down before the largest code change, or a session interrupted between them reads the current "no base class" text and reverts the work.

- [ ] **Step 1: Rewrite `tools/README.md`'s opening**

Replace the first paragraph ("Small, single-purpose scripts. Not a framework — there is no base class to learn and no plugin registry. Read one tool end to end and you know how to write the next one.") with:

```markdown
Small, single-purpose scripts, plus one deliberate exception. Leaf tools
are plain functions — read one end to end and you know how to write the
next one, and there is still no framework to learn at that layer. The
**theory layer** (`domain.py`, `theory.py`, `registry.py`) has a base
class, because this file's own promotion criterion — more than one real
caller — was met: two theories with unrelated entry points, and twenty-two
more specced. A theory inherits *what to do* (`start`, `finish`) and is
handed *what it may touch* (`TheoryContext`); everything below that
boundary stays plain functions, and every tool remains directly callable
without the contract.
```

- [ ] **Step 2: Extend `tools/README.md` conventions and tool map**

Add to the Conventions list:

```markdown
- **Any code that fetches external data takes `fetch: Fetch | None = None`**
  (resolved to `http.get_json` at call time). One parameter makes a theory
  testable against a canned payload with no network and no monkeypatch —
  the same discipline as injectable `now`, applied to transports.
- **Facts are data, not procedure.** A theory's durable facts live in
  `theory_facts`; adding one (a confirmed pair, an implication edge) never
  bumps its version. Changing how facts are *derived* does. A
  model-established fact carries `construction`-stage provenance.
- **`Theory` is for things that produce bets.** A study produces theories
  (mark its folder with `STUDY.md`; discovery skips it); an execution
  policy decorates candidates. Neither is a `Theory` subclass.
```

Add rows to the tool map table:

```markdown
| `domain.py` | Frozen value types: `Market`, `Candidate`, `Verdict`, `Edge`, `ScanResult` |
| `theory.py` | The theory contract: `Theory`, `TheoryRun`, `TheoryContext` |
| `registry.py` | Discovery; drift check between code and the DB registry |
```

- [ ] **Step 3: Add the conventions section to `CLAUDE.md`**

Insert a new section after "Pipelines propose, judgment disposes":

```markdown
## The theory contract

**The researcher is not bound by any of this.** Every tool stays directly
callable, ad-hoc exploration is first-class, and "just asking" needs none
of it — `python -m tools.cli` is still the front door for questions. The
contract is optional for running and mandatory only for recording: when a
finding lands in the ledger, provenance, an honest `edge_basis`, and a
Kalshi ticker hold without exception. Everything upstream of `finish()` is
yours to arrange.

- A theory **inherits what to do** (`start`, `finish`) and **is handed
  what it may touch** (`TheoryContext`). Never a toolbox base class —
  `self.list_open()` on every theory would make the forbidden path the
  most discoverable thing on the object.
- `Theory` is stateless; per-run state lives on the `TheoryRun`.
- Domain values are frozen dataclasses from `tools/domain.py`; bare dicts
  are confined to the API and JSON boundaries.
- `finish()` is never overridden — it is what makes the provenance and
  ledger contract unskippable.
- **A judge returns `Verdict`s — a bucket label and a rationale, never a
  number.** The type has no numeric field on purpose; `tools/buckets.py`
  turns labels into probabilities from measured rates.
- The contract is a **floor, not a ceiling**: `screen()` and `price()` are
  required, and a theory may add anything else it needs — its own methods,
  its own data sources, its own module layout.
- **Facts are data, not procedure** — adding a confirmed pair to
  `theory_facts` does not bump a version; changing how facts are derived
  does.
- **`Theory` is for things that produce bets.** A study produces theories
  (`STUDY.md` marks its folder); an execution policy decorates candidates.
- Any theory fetching external data takes `fetch: Fetch | None = None`.
```

- [ ] **Step 4: Rewrite `find-edge` step 2 and the stage-2 mechanics**

In `.claude/skills/find-edge/SKILL.md`, replace section "2. Run each theory's stage 1" (the THEORY.md-prose instruction) with:

````markdown
## 2. Run every theory through the contract

No `THEORY.md` reading is needed to run stage 1. The parent session pulls
the board once, then runs mechanical theories inline and dispatches one
subagent per judgment theory:

```python
from datetime import datetime, timezone

from tools import board as board_tool, db, registry
from tools.theory import TheoryContext

conn = db.connect(); db.init_db(conn)
board = board_tool.get_board(conn)          # cached if fresh; go's Orient
                                            # makes the one force=True pull
ctx = TheoryContext.build(conn=conn, board=board,
                          now=datetime.now(timezone.utc), run_id="live")

results = []
for theory in registry.running(conn):
    if theory.uses_llm_judgment:
        dispatch(theory.id)                 # subagent; see the model below
    else:
        results.append(theory.start(ctx).finish())   # inline, no model
```

**Dispatch model.** The unit dispatched is a theory id, not a payload. The
subagent instructions MUST state: the board is already pulled — call
`get_board(conn)` **without** `force`; open your own `db.connect()`; build
your context with `TheoryContext.build(..., judge_model="<the exact model
you are>")`, because `finish()` stamps provenance with the judging model,
not the parent's. Inside the subagent:

```python
from datetime import datetime, timezone

from tools import board as board_tool, db, registry
from tools.theory import TheoryContext

conn = db.connect()
ctx = TheoryContext.build(conn=conn, board=board_tool.get_board(conn),
                          now=datetime.now(timezone.utc), run_id="live",
                          judge_model="<the exact model you are>")
theory = registry.discover()["<id>"]
run = theory.start(ctx)                # cache hit: no second board pull
# Judge run.payload against theory.prompts, then build
# {Candidate.key: Verdict(bucket=..., rationale=...)} — a bucket from the
# theory's declared scale plus a rationale. Never a probability; a Verdict
# has no numeric field to put one in.
result = run.apply(verdicts).finish()  # price + provenance + ledger
```

The subagent's durable output is the ledger rows; its final message is a
compact summary of the ScanResult. Read the rows back with
`ledger.list_opportunities(run_id=...)` rather than trusting the prose.
Final cross-theory selection stays with the parent — credibility ranking
compares theories against each other, which no single-theory agent can do.
````

In section 5, replace the "First check whether this theory has a stage 2 at all" paragraph's mechanism with: *the discriminator is `theory.uses_llm_judgment` (drift-checked against the DB by `registry.check_drift`); a mechanical theory ran inline in step 2 and its candidates arrive scored.* Replace the manual `record_opportunity` snippet with the `run.apply(verdicts).finish()` flow above, and keep the existing "Never ask a subagent for a probability" and blind-judgment paragraphs — they are now enforced by the `Verdict` type and the `judged_blind` field.

- [ ] **Step 5: Update `propose-theory`**

In `.claude/skills/propose-theory/SKILL.md`, where it scaffolds a free-function module, scaffold instead:

```python
# theories/<slug>/theory.py
from tools.domain import Candidate, Edge, ScoredCandidate
from tools.theory import Theory, TheoryContext


class <Name>Theory(Theory):
    id = "<slug>"
    name = "<Name>"
    version = 1
    # uses_llm_judgment = True and prompts={...} only if a model judges

    def screen(self, ctx: TheoryContext) -> list[Candidate]:
        ...

    def price(self, ctx, cands, verdicts=None) -> list[ScoredCandidate]:
        ...

# theories/<slug>/__init__.py
THEORY = <Name>Theory()
```

and say plainly: **only `screen()` and `price()` are required**; register the DB row with a version matching the ClassVar or `check_drift` will fail the conventions test.

- [ ] **Step 6: Audit `go` and `backtest-theory`**

Run: `grep -n "THEORY.md\|Stage 1\|stage 1\|list_open\|record_opportunity" .claude/skills/go/SKILL.md .claude/skills/backtest-theory/SKILL.md`

Update every hit that describes *how a theory is invoked* to the contract flow (`registry.running`, `theory.start(ctx)`, `run.finish()`); leave hits about reading a theory's hypothesis or history alone. In `backtest-theory`, note that `TheoryContext(run_mode="backtest")` is what dispatch keys on and that web search stays off in every backtest judgment subagent (existing rule, now stated against the contract).

- [ ] **Step 7: Verify and commit**

Run: `grep -rn "no base class to learn" tools/README.md` — expected: no hits.
Run: `python -m pytest -m "not network" -q` — all PASS (docs only).

```bash
git add tools/README.md CLAUDE.md .claude/skills
git commit -m "docs: theory-layer conventions; skills invoke theories through the contract"
```

---

### Task 12: Port `insider_bias` internals to native domain types (Phase 5a)

**Files:**
- Modify: `theories/insider_bias/screen.py`, `theories/insider_bias/insider_judgment/gate.py`, `theories/insider_bias/insider_judgment/pipeline.py`, `theories/insider_bias/insider_judgment/backtest.py`, `theories/insider_bias/insider_judgment/theory.py`
- Modify: `tests/characterization/conftest.py` (`board_input` switch), `tests/theories/test_insider_bias_screen.py`, `tests/theories/test_insider_bias_gate.py`, `tests/theories/test_insider_bias_pipeline.py`, `tests/theories/test_insider_bias_backtest.py` (**input construction only**), `tests/test_conventions.py` (shrink allowlist)

**Interfaces:**
- Consumes: `Market`, `Candidate`, `Leg`, `Market.from_mapping`.
- Produces: `screen.screen(markets: list[Market], ...) -> list[Candidate]`; `pipeline.dedupe_by_event(cands: list[Candidate])`; `gate.partition(cands: list[Candidate])`; `run_mechanical_stages(board: list[Market], now)` whose `survivor_candidates` are now `Candidate` objects; `replay_market` builds a `Market` for its point-in-time view (plan decision 3).

**The goldens are the whole safety net here.** Every function's *output values* are locked by Task 0 through the projection; only the carrying types change. Test-file edits update object **construction** (dict fixtures → `Market(...)`/`Candidate(...)`); every assertion stays byte-identical — dict-style *reads* in tests still work through the shim until Task 14.

- [ ] **Step 1: Switch the harness input shape**

In `tests/characterization/conftest.py`, change `board_input` to:

```python
def board_input() -> list:
    from tools.domain import Market
    return [Market.from_mapping(m) for m in load_fixture()]
```

Run: `python -m pytest tests/characterization -q` — Expected: **PASS already**, before any port: `screen.screen` still reads `.get()`, which `Market` serves via the shim. This proves the switch itself changes nothing; the port below happens under a green harness.

- [ ] **Step 2: Port `screen.py`**

`is_excluded` and `days_until` are unchanged. Replace `favorite` and `screen`:

```python
from tools.domain import Candidate, Leg, Market


def favorite(market: Market) -> tuple[str, float] | None:
    """The favored side and the price you would actually pay for it.

    Uses the ask, not the mid. An edge measured against the mid is an edge
    against a price nobody will fill.
    """
    if market.mid is None:
        return None
    if market.mid >= 0.5:
        side, price = "yes", market.yes_ask
    else:
        side, price = "no", market.no_ask
    if price is None:
        return None
    return side, price


def screen(
    markets: list[Market],
    now: datetime | None = None,
    min_favorite_price: float = MIN_FAVORITE_PRICE,
    max_favorite_price: float = MAX_FAVORITE_PRICE,
    max_spread: float = MAX_SPREAD,
    min_volume: float = MIN_VOLUME,
    max_days_ahead: float = MAX_DAYS_AHEAD,
) -> list[Candidate]:
    """Narrow normalized Kalshi markets to tradeable-favorite candidates."""
    candidates = []
    for market in markets:
        if not market.is_open or is_excluded(market.ticker):
            continue

        fav = favorite(market)
        if fav is None:
            continue
        side, entry_price = fav
        if not min_favorite_price <= entry_price <= max_favorite_price:
            continue

        if market.spread is None or market.spread > max_spread:
            continue
        if market.volume is None or market.volume < min_volume:
            continue

        days = days_until(market.close_time, now=now)
        if days is None or days < 0 or days > max_days_ahead:
            continue

        candidates.append(Candidate(
            legs=(Leg(market=market, side=side, price=entry_price),),
            days_to_close=days,
        ))
    return candidates
```

(The `dict(market)` + three-key spread — the pattern the spec's section 2 identified as the latent abstraction — is now the `Candidate` constructor.)

- [ ] **Step 3: Port `gate.partition` and the pipeline**

`gate.classify`/`is_gated_out` are unchanged (they take a string). In `partition`, the one access line becomes:

```python
        label = classify(candidate.legs[0].market.series_ticker)
```

with the signature annotated `candidates: list[Candidate]`.

In `pipeline.py`:

```python
def dedupe_by_event(candidates: list[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    out: list[Candidate] = []
    for c in candidates:
        if c.key in seen:
            continue
        seen.add(c.key)
        out.append(c)
    return out


def build_blind_payload(events: list[Candidate],
                        candidates: list[Candidate]) -> list[dict]:
    by_event: dict[str, list[Candidate]] = {}
    for c in candidates:
        by_event.setdefault(c.key, []).append(c)

    payload = []
    for e in events:
        rep = e.legs[0].market
        entry = {f: getattr(rep, f, None) for f in EVENT_FIELDS}
        entry["markets"] = [
            {f: getattr(c.legs[0].market, f, None) for f in MARKET_FIELDS}
            for c in by_event.get(e.key, [])
        ]
        payload.append(entry)
    assert_blind(payload)
    return payload
```

`getattr(..., f, None)` reproduces the old `.get(f)` semantics exactly — `rules_secondary` is not a `Market` field and stays `None` in the payload, as the golden requires (reading it out of `raw` instead would *change* payload content and judgment input: a version bump, so don't).

In `run_mechanical_stages`, the two key-derivation lines become:

```python
    survivor_keys = {s.key for s in survivors}
    kept = [c for c in candidates if c.key in survivor_keys]
```

Docstrings updated; every count and the payload build are otherwise untouched.

- [ ] **Step 4: Port `backtest.replay_market`**

The hand-built `market_view` dict becomes a `Market` (decision 3), and the hit is read by attribute:

```python
        market_view = Market(
            platform="kalshi",
            ticker=settled.ticker,
            is_open=True,
            mid=(yes_bid + yes_ask) / 2.0,
            yes_ask=yes_ask,
            no_ask=1.0 - yes_bid,
            spread=yes_ask - yes_bid,
            volume=running_volume,
            close_time=settled.close_time,
            raw={},
        )
        as_of = datetime.fromtimestamp(candle["end_ts"], tz=timezone.utc)
        hits = screen.screen([market_view], now=as_of)
        if hits:
            hit = hits[0]
            return {
                "ticker": settled.ticker,
                "event_ticker": settled.event_ticker,
                "series_ticker": series_ticker,
                "entry_day_ts": candle["end_ts"],
                "fav_side": hit.fav_side,
                "entry_price": hit.entry_price,
                "spread_at_call": hit.legs[0].market.spread,
                "volume_at_call": hit.legs[0].market.volume,
                "days_to_close": hit.days_to_close,
                "result": settled.result,
            }
```

(`settled` is a `Market` since Task 4; `replay_market`'s returned dict keeps its exact historical keys.) Also update `settled.get("close_time")` at the top of the function to `settled.close_time`.

- [ ] **Step 5: Simplify the adapter**

In `theories/insider_bias/insider_judgment/theory.py`, `survivor_candidates` are now `Candidate` objects — delete `_to_candidate` and use them directly:

```python
            candidates=tuple(funnel["survivor_candidates"]),
```

- [ ] **Step 6: Update theory-test fixtures (construction only)**

In `tests/theories/test_insider_bias_screen.py`, `..._gate.py`, `..._pipeline.py`, `..._backtest.py`: wherever a test builds a market dict to feed `screen`/`partition`/`run_mechanical_stages`/`replay_market`, construct it as `Market.from_mapping({...the same dict...})` (or feed candidate inputs through `screen.screen` itself). **Diff review rule: the diff in these four files may touch only object construction — if any `assert` line changes, stop and escalate.** Dict-style *reads* on results (`hits[0]["fav_side"]`) still pass through the shim and are left alone until Task 14.

- [ ] **Step 7: Shrink the shim allowlist**

In `tests/test_conventions.py`, remove from `SHIM_ALLOWLIST`: `tools.board` (it never called the shim), `theories.insider_bias.screen`, `theories.insider_bias.insider_judgment.gate`, `theories.insider_bias.insider_judgment.pipeline`, `theories.insider_bias.insider_judgment.backtest`, `theories.insider_bias.insider_judgment.theory`. Remaining: `tools.snapshot`, `tools.match_market`, `theories.insider_bias.mention_family.mention_bucket`, `theories.insider_bias.mention_family.theory`.

- [ ] **Step 8: Run everything**

Run: `python -m pytest tests/characterization -q` — every golden passes unchanged: same candidates, same counts, same payload, byte-identical through the projection.
Run: `python -m pytest -m "not network" -q` — all PASS.

- [ ] **Step 9: Commit**

```bash
git add theories/insider_bias tests/characterization/conftest.py tests/theories tests/test_conventions.py
git commit -m "refactor: insider_bias internals speak Market/Candidate natively"
```

---

### Task 13: Port `mention_family` and the remaining tools consumers (Phase 5b)

**Files:**
- Modify: `theories/insider_bias/mention_family/mention_bucket.py`, `theories/insider_bias/mention_family/theory.py`, `tools/snapshot.py`, `tools/match_market.py`
- Modify: `tests/theories/test_mention_family_mention_bucket.py`, `tests/theories/test_mention_family_theory.py`, `tests/test_match_market.py` (construction and access syntax; values unchanged), `tests/test_conventions.py` (allowlist → empty)

**Interfaces:**
- Consumes: `Candidate`, `ScoredCandidate`, `Edge`, `dataclasses.replace`.
- Produces: `mention_bucket.rank(candidates: list[Candidate], rates, top_n=20) -> list[ScoredCandidate]` (same for `rank_preview`); `mention_bucket.record(conn, ranked: list[ScoredCandidate], ...)`; `mention_bucket._rationale_for(sc) -> str` shared by `record()` and the adapter; `snapshot.save_kalshi`/`save_polymarket` read attributes.

**Stated exception invoked here:** `rank`'s return type changes from dicts to `ScoredCandidate`, so its tests change *access syntax* (`r["edge_pts_net"]` → `r.edge.pts_net`) — every compared value stays identical, and the `mention_rank` golden (whole-value, via projection) is the proof.

- [ ] **Step 1: Port `mention_bucket.py`**

`find_candidates` — `screen.screen` now returns `Candidate`s; the family filter reads the market:

```python
    hits = screen.screen(board, now=now, max_days_ahead=max_days_ahead)
    return [
        h for h in hits
        if is_mention_family(h.legs[0].market.series_ticker
                             or h.legs[0].market.ticker)
    ]
```

`rank` / `rank_preview` — same math, typed carrier (`{**c, ...}` cannot survive `slots=True`, which is the point):

```python
from dataclasses import replace

from tools.domain import Candidate, Edge, ScoredCandidate


def _sort_key(sc: ScoredCandidate):
    return (sc.edge.pts_net, sc.candidate.legs[0].market.volume or 0.0)


def rank(candidates: list[Candidate], rates: dict,
         top_n: int = 20) -> list[ScoredCandidate]:
    scored = []
    for c in candidates:
        bucket = bucket_for_price(c.entry_price)
        edge_pts_net, edge_basis = buckets.edge_for(
            bucket, c.entry_price, rates, PRIORS
        )
        measured = rates.get(bucket) or {}
        scored.append(ScoredCandidate(
            candidate=c,
            edge=Edge(pts_net=edge_pts_net, basis=edge_basis,
                      model_prob=measured.get("win_rate")
                      if edge_basis == "measured" else None),
            confidence=bucket,
        ))
    scored.sort(key=_sort_key, reverse=True)
    return scored[:top_n]
```

`rank_preview` gets the same treatment — its `edge_basis` stays the literal `"model"` and its docstring is untouched; the two functions remain deliberately separate:

```python
def rank_preview(
    candidates: list[Candidate],
    validated_rates: dict,
    top_n: int = 20,
) -> list[ScoredCandidate]:
    scored = []
    for c in candidates:
        bucket = bucket_for_price(c.entry_price)
        measured = validated_rates.get(bucket)
        if measured and measured.get("n", 0) >= buckets.MIN_BUCKET_N:
            gross = (measured["win_rate"] - c.entry_price) * 100.0
            edge_pts_net = gross - fee_pts(c.entry_price)
        else:
            edge_pts_net = 0.0
        scored.append(ScoredCandidate(
            candidate=c,
            edge=Edge(pts_net=edge_pts_net, basis="model"),
            confidence=bucket,
        ))
    scored.sort(key=_sort_key, reverse=True)
    return scored[:top_n]
```

Add the shared rationale builder (byte-for-byte the strings `record()` writes today — move them, do not retype them):

```python
def _rationale_for(sc: ScoredCandidate) -> str:
    bucket, basis = sc.confidence, sc.edge.basis
    bin_rate_note = (f"measured rate for bucket {bucket} "
                     f"({MEASURED_RATE_RUN_ID})")
    basis_note = (
        f"{bin_rate_note}, applied directly"
        if basis == "measured"
        else (
            f"{bin_rate_note} APPLIED AS AN EXTRAPOLATION to a "
            f"days-to-close horizon the backtest never tested "
            f"(>{screen.MAX_DAYS_AHEAD:.0f} days) -- a modeling "
            f"assumption, not a measurement of this population"
        )
    )
    volume = sc.candidate.legs[0].market.volume or 0
    return (
        f"Mechanical mention_family bucket, no judgment applied: "
        f"{basis_note}. Volume (${volume:,.0f}) is a "
        f"tiebreaker only, not part of the edge -- see "
        f"mention_bucket.py module docstring."
    )
```

`record()` keeps its signature and behavior, reading from the typed carrier:

```python
    record_provenance(conn, run_id)
    ids = []
    for sc in ranked:
        m = sc.candidate.legs[0].market
        opp_id, _ = ledger.record_opportunity(
            conn,
            theory_id=THEORY_ID,
            theory_version=THEORY_VERSION,
            kalshi_ticker=sc.candidate.ticker,
            outcome=sc.candidate.fav_side,
            entry_price=sc.candidate.entry_price,
            edge_pts_net=sc.edge.pts_net,
            run_mode=run_mode,
            run_id=run_id,
            spread_at_call=m.spread,
            volume_at_call=m.volume,
            edge_basis=sc.edge.basis,
            confidence=f"{sc.confidence}{confidence_suffix}",
            rationale=_rationale_for(sc),
            evidence_source="kalshi",
        )
        ids.append(opp_id)
    return ids
```

- [ ] **Step 2: Simplify the adapter**

`theories/insider_bias/mention_family/theory.py`: delete its `_to_candidate` and `_rationale`; `screen` uses the hits directly; `price` becomes:

```python
    def price(self, ctx, cands, verdicts=None):
        rates = mention_bucket.measured_rate(ctx.conn)
        ranked = mention_bucket.rank(list(cands), rates)
        return [replace(sc, rationale=mention_bucket._rationale_for(sc))
                for sc in ranked]
```

(with `from dataclasses import replace`). The Task 8 row-equivalence test now passes trivially — both paths share `_rationale_for`.

- [ ] **Step 3: Port `tools/snapshot.py` and `tools/match_market.py`**

`save_kalshi` row tuples read attributes: `m.ticker`, `m.title`, `m.mid`, `m.yes_bid`, `m.yes_ask`, `m.volume`, `m.open_interest`, `m.close_time`, `json.dumps(m.raw or {})`; `_kalshi_snapshot_status` reads `m.status`. `save_polymarket` likewise: `m.market_id`, `m.question`, `m.implied_prob_yes`, `m.best_bid`, `m.best_ask`, `m.volume`, `m.end_date`, `m.closed`, `m.raw`.

For `match_market.py`, first enumerate every access:

```bash
grep -n '\.get(\|\[["'"'"']' tools/match_market.py
```

Port each dual-platform read to attribute access with a `getattr` default, e.g.:

```python
    return getattr(market, "question", None) or getattr(market, "title", None) or ""
    return getattr(market, "end_date", None) or getattr(market, "close_time", None)
```

(`getattr` with a default works on slots classes and expresses "this platform's type may not carry that field" without the shim.)

- [ ] **Step 4: Update tests (construction and access syntax only)**

`tests/theories/test_mention_family_mention_bucket.py`: inputs become `Candidate`s (build via `screen.screen` or the `Candidate`/`Leg` constructors); reads on `rank` output become attribute access. `tests/test_match_market.py`: market fixtures become `Market.from_mapping(...)` / `PolymarketMarket(...)`. Same diff-review rule as Task 12: compared *values* may not change.

- [ ] **Step 5: Empty the allowlist**

In `tests/test_conventions.py`: `SHIM_ALLOWLIST = set()`. The conventions test now proves no production module touches the shim — which is the precondition Task 14 deletes it under.

- [ ] **Step 6: Run everything**

Run: `python -m pytest tests/characterization -q` — the `mention_find_candidates` and `mention_rank` goldens pass unchanged through the projection.
Run: `python -m pytest -m "not network" -q` — all PASS.

- [ ] **Step 7: Commit**

```bash
git add theories/insider_bias/mention_family tools/snapshot.py tools/match_market.py tests/theories tests/test_match_market.py tests/test_conventions.py
git commit -m "refactor: mention_family and tools consumers speak domain types natively"
```

---

### Task 14: Delete the shim; final verification sweep (Phase 5c)

**Files:**
- Modify: `tools/domain.py` (delete the shim), `tests/test_domain.py`, `tests/test_conventions.py`, `tests/kalshi/test_markets.py`, `tests/polymarket/test_markets.py`, `tests/test_board.py`, remaining `tests/theories/*` dict-style reads
- Modify: `docs/superpowers/specs/2026-08-24-theory-layer-oop-design.md` (status line), `RESEARCH_LOG.md`

**The one place tests are deleted, called out in advance:** the shim's own tests (`test_shim_*` in `tests/test_domain.py` and the allowlist-exercise test in `tests/test_conventions.py`) are deleted **together with the feature they test** — the shim was specced as a temporary strangler seam whose deletion is Phase 5's deliverable (spec §4.2). No other test is deleted anywhere in this plan.

- [ ] **Step 1: Delete the shim from `tools/domain.py`**

Remove: the `TODO(oop-migration)` comment block, `SHIM_CALLERS`, `_note_caller`, the `_MappingShim` class, the `(_MappingShim)` base from `Market`, `PolymarketMarket`, and `Candidate`, and `Candidate`'s `_SHIM_EXTRA`/`keys`/`__getitem__`/`get` overrides. `Market.from_mapping` **stays** — it consumes plain dicts at the JSON boundary (fixtures, snapshots), not the shim.

- [ ] **Step 2: Update the tests that exercised it**

- `tests/test_domain.py`: delete the five `test_shim_*` tests; keep `test_slots_prevent_attribute_injection`.
- `tests/test_conventions.py`: delete `SHIM_ALLOWLIST` and `test_shim_is_exercised_only_from_allowlisted_modules`; add the terminal form of the guarantee:

```python
def test_the_migration_shim_is_gone():
    """Phase 5 delivered: domain objects are not mappings. Dict-style
    access anywhere in production code is now a TypeError, not a wart."""
    for cls in (domain.Market, domain.PolymarketMarket, domain.Candidate):
        assert not hasattr(cls, "__getitem__")
        assert not hasattr(cls, "keys")
    assert not hasattr(domain, "SHIM_CALLERS")
```

- Convert remaining dict-style *reads* in tests to attributes, values unchanged: `tests/kalshi/test_markets.py` (`m["yes_bid"]` → `m.yes_bid`, etc.), `tests/test_board.py` (`m["ticker"]` → `m.ticker`), `tests/polymarket/test_markets.py` (`m["question"]` → `m.question`), and any residue in `tests/theories/`. Find them mechanically — run the suite; every leftover fails with `'Market' object is not subscriptable`, and:

```bash
grep -rn '\[["'"'"']\(ticker\|title\|mid\|spread\|yes_\|no_\|volume\|fav_side\|entry_price\|question\|market_id\)' tests/ | grep -v characterization
```

(`tests/characterization/` needs nothing: `proj`, `event_key`, and `board_input` already speak both shapes, and the fixture/goldens are plain JSON.)

- [ ] **Step 3: Run the full suite and goldens**

Run: `python -m pytest -m "not network" -q`
Expected: All PASS — this run **is** the proof the shim had no remaining production caller.

- [ ] **Step 4: Final verification sweep — the spec's success criteria**

Work through these in order; every item must hold. Any failure stops the task and is reported, not patched around.

```bash
# 1-2. Non-regression: suite green, goldens byte-identical through proj
python -m pytest -m "not network" -q
python -m pytest tests/characterization -q

# 3. CLI emits identical JSON (its imports never changed; smoke it)
python -m tools.cli theories list
python -m tools.cli opportunities list
python -m tools.cli score report insider_judgment

# 4. No version bump, no drift, both theories runnable end to end
python -c "
from tools import db, registry
c = db.connect()
print('drift:', registry.check_drift(c) or 'none')
rows = c.execute('SELECT id, version, status FROM theories').fetchall()
print([dict(r) for r in rows])   # insider_judgment v3, mention_family v1
"

# 5-7. Contract in use: both theories start->finish on the fixture board
python -c "
from tests.characterization import conftest as cz
from tools import db, registry
from tools.theory import TheoryContext
c = db.connect()
ctx = TheoryContext.build(conn=c, board=cz.board_input(), now=cz.frozen_now())
for t in registry.running(c):
    run = t.start(ctx)
    print(t.id, 'needs_judgment:', run.needs_judgment,
          'candidates:', len(run.candidates))
"

# 10. Restraint: no new classes outside the theory layer
grep -n "^class " tools/sizing.py tools/buckets.py tools/rank.py tools/db.py tools/cli.py
# expected: no output

# 13-14. Researcher freedom: plain functions still work, CLI answers alone
python -c "
from tests.characterization import conftest as cz
from theories.insider_bias import screen
print('standalone screen:', len(screen.screen(cz.board_input(),
                                              now=cz.frozen_now())))
"
```

Criteria 11–12 and 17–19 are `tests/test_stub_theory.py`, `tests/test_backlog_fit.py`, and `tests/test_theory_facts.py`, already green in step 3. Criterion 9 (docs no longer contradict code) was Task 11; spot-check: `grep -rn "no base class" tools/README.md` returns only the leaf-tools phrasing.

- [ ] **Step 5: Close the record**

- In `docs/superpowers/specs/2026-08-24-theory-layer-oop-design.md`, change the `Status:` line to `implemented — see docs/superpowers/plans/2026-08-24-theory-layer-oop.md`.
- Append to `RESEARCH_LOG.md`: date, one paragraph — theory layer landed (domain types, contract, registry, both theories adapted then ported, shim removed), no version bumps, goldens held throughout, and the `Verdict` type now enforces category-not-number at the judge boundary.

- [ ] **Step 6: Commit**

```bash
git add tools/domain.py tests/ docs/superpowers/specs/2026-08-24-theory-layer-oop-design.md RESEARCH_LOG.md
git commit -m "refactor: delete the migration shim; theory-layer OOP complete"
```

---

## Verification Checklist (spec §9, run after Task 14)

- [ ] Existing suite passes at every task; only the shim's own tests were ever deleted, with the shim.
- [ ] Every characterization golden passes unchanged, at every task, through the canonical projection.
- [ ] `tools/cli.py` subcommands emit identical JSON (its imports were never touched).
- [ ] Both theories run end to end at versions 3 and 1 — no bump, no lost capability: `rank`/`rank_preview` still two functions, `confidence_suffix` honoured, full funnel with per-category `gate_counts` reported.
- [ ] `find-edge` runs both theories with no `THEORY.md` read; a subagent handed a theory id can run start→judge→finish; `uses_llm_judgment` is the dispatch discriminator, drift-checked.
- [ ] `registry.check_drift(conn)` empty on the live DB; conventions test enforces it stays so.
- [ ] No new class in `sizing`/`buckets`/`rank`/`db`/`cli`; theory #3 needs only `screen()`+`price()` (stub-proven); a ctx-ignoring stub runs (floor, not cage).
- [ ] Every tool callable standalone; "just asking" still needs only `python -m tools.cli`; ad-hoc exploration unpenalised; the ledger boundary holds on every path.
- [ ] All four backlog shapes run as stubs; facts round-trip without version bumps and carry `construction` provenance; studies and execution policies are documented as not-a-`Theory`.
- [ ] `Verdict` has no numeric field — enforced by `tests/test_conventions.py`, stated in `CLAUDE.md`.

## Open questions carried from the spec

Recorded, not resolved here. Raise with the user if implementation forces any of them.

1. **Side-aware `implied_prob`** on `Leg`/single-leg `Candidate` (spec OQ1): deferred; neither current theory needs it. `Market.mid` stays yes-denominated.
2. **`maker-mode-execution`** needs its own spec (spec OQ4): the taker ask remains the recorded baseline everywhere in this plan.
3. **Continuous detectors** (spec OQ5): `screen(ctx)` re-deriving alerts per session is accepted for v1; a second streaming theory triggers the scheduled-detector design conversation.
4. **`theory_facts` Python API** (plan decision 5): deliberately not built; the first pair-store theory builds it against real needs.
