# Multi-Leg Positions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the ledger store, settle, and score a basket of Kalshi markets as one position with a joint payoff, so `structural-arb`, `calendar-arb`, and `implication-graph` can accrue honest evidence.

**Architecture:** Additive throughout. `opportunities` gains three defaulted columns and a child table `opportunity_legs`; single-leg rows never get leg rows and keep every existing code path unchanged. A new `record_basket()` sits beside the untouched `record_opportunity()`. `compute_score` is first refactored into "build observations, then aggregate" with provably identical output, and only then gains a basket branch.

**Tech Stack:** Python 3, stdlib `sqlite3`, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-24-multi-leg-positions-design.md`

## Global Constraints

- **Prices are decimal dollars in [0, 1]. Edge is in percentage points.** A basket's `entry_price` is its *cost* and may exceed 1.0 — it is bounded by `max_payout`, not by 1.0.
- **Entry prices are the ask you would actually pay, never the mid.**
- **Timestamps are UTC ISO-8601.** Any function needing a clock takes `now: str | None = None` defaulting to real UTC.
- **Fail loudly.** A missing or unparseable required field raises. Never let a schema change turn silently into `0.0`.
- **No functionality may regress.** The existing test suite passes at every task with no test deleted, skipped, or weakened. A test that must change to accommodate this work is a red flag to examine, not edit. Tests may be added freely.
- **Single-leg behavior is bit-for-bit unchanged.** This is the primary correctness claim of the whole plan.
- **No credentials.** Never add an API key or send a user identifier anywhere.
- **`edge_basis`** is one of `measured` / `model` / `prior`. There is deliberately no basis meaning "it felt about right".
- Run tests with `python -m pytest`. Deselect live-network tests with `-m "not network"`.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `db/schema.sql` | Table definitions; single source of DDL | Modify — 3 columns + 1 table + 1 index |
| `tools/db.py` | Connection, schema, migrations | Modify — 3 `_add_column_if_missing` calls in `init_db` |
| `tools/ledger.py` | The opportunity contract | Modify — add `basket_key`, `record_basket`, `get_legs` |
| `tools/score.py` | Settlement, calibration, ROI | Modify — refactor to observations, add basket branch |
| `tools/cli.py` | JSON command line | Modify — legs in `opportunities list` output |
| `tests/test_ledger.py` | Existing ledger tests | Untouched (non-regression witness) |
| `tests/test_score.py` | Existing score tests | Untouched (non-regression witness) |
| `tests/test_baskets.py` | All new basket behavior | Create |
| `tests/test_score_characterization.py` | Locks current scoring math before refactor | Create |

**Why `record_basket` is a separate function rather than overloading `record_opportunity`:** `record_opportunity` has 24 keyword arguments and is called by every existing theory. Adding a `legs=` parameter that changes the meaning of `kalshi_ticker`, `outcome`, and `entry_price` would put a mode switch inside the most safety-critical function in the repo. A sibling function shares the internals and leaves the existing signature untouched.

**Legs are plain dicts in this plan, not dataclasses — deliberately.** The spec's section 3.1 shows `Leg` and `Candidate` as frozen dataclasses in `tools/domain.py`. That module does not exist yet: it is created by the [theory-layer OOP migration](../specs/2026-08-24-theory-layer-oop-design.md), which runs **after** this work and which adopts the leg shape defined here. Creating `domain.py` now would drag the OOP migration's first phase into a persistence change and forfeit the clean separation both specs argue for. So this plan uses `{"kalshi_ticker", "outcome", "entry_price", "spread_at_call", "volume_at_call"}` dicts at the ledger boundary — the same shape the future `Leg` dataclass will carry — and the OOP migration swaps the type in without touching the schema.

**Do not create `tools/domain.py`, `tools/theory.py`, or `tools/registry.py` in this plan.** If a task seems to need them, stop and re-read this note.

---

### Task 1: Schema and migration

**Files:**
- Modify: `db/schema.sql:74-112` (the `opportunities` table and its indexes)
- Modify: `tools/db.py:57-70` (`init_db`)
- Test: `tests/test_baskets.py`

**Interfaces:**
- Consumes: `db.init_db(conn)`, `db._add_column_if_missing(conn, table, column, decl)` — both already exist.
- Produces: `opportunities.position_kind` (TEXT, `'single'`|`'basket'`, default `'single'`), `opportunities.leg_count` (INTEGER, default 1), `opportunities.max_payout` (REAL, default 1.0), and table `opportunity_legs(opportunity_id, leg_index, kalshi_ticker, outcome, entry_price, spread_at_call, volume_at_call)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_baskets.py`:

```python
import sqlite3

import pytest

from tools import db, ledger, theories

TS = "2026-08-23T12:00:00Z"
LATER = "2026-08-24T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_opportunities_has_the_basket_columns(conn):
    cols = _columns(conn, "opportunities")
    assert {"position_kind", "leg_count", "max_payout"} <= cols


def test_opportunity_legs_table_exists(conn):
    cols = _columns(conn, "opportunity_legs")
    assert cols == {
        "opportunity_id", "leg_index", "kalshi_ticker", "outcome",
        "entry_price", "spread_at_call", "volume_at_call",
    }


def test_existing_single_leg_row_defaults_are_correct(conn):
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXTEST-26",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, now=TS,
    )
    row = ledger.get_opportunity(conn, opp_id)
    assert row["position_kind"] == "single"
    assert row["leg_count"] == 1
    assert row["max_payout"] == pytest.approx(1.0)


def test_position_kind_rejects_an_unknown_value(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO opportunities (theory_id, theory_version, run_mode,"
            " run_id, kalshi_ticker, outcome, entry_price,"
            " screen_edge_pts_net, edge_pts_net, position_kind,"
            " first_seen_at, last_seen_at)"
            " VALUES ('t1', 1, 'live', 'live', 'X', 'yes', 0.4, 1.0, 1.0,"
            " 'combo', ?, ?)",
            (TS, TS),
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_baskets.py -v`
Expected: FAIL — `test_opportunities_has_the_basket_columns` asserts a set that is not a subset; `test_opportunity_legs_table_exists` raises `sqlite3.OperationalError: no such table`.

- [ ] **Step 3: Add the columns and table to `db/schema.sql`**

In the `opportunities` table, immediately after the `entry_price REAL NOT NULL,` line, add:

```sql
    position_kind       TEXT NOT NULL DEFAULT 'single'
                        CHECK (position_kind IN ('single','basket')),
    leg_count           INTEGER NOT NULL DEFAULT 1,
    max_payout          REAL NOT NULL DEFAULT 1.0,
```

After the `idx_opportunities_ticker` index (schema.sql:115-116), add:

```sql
CREATE TABLE IF NOT EXISTS opportunity_legs (
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id)
                   ON DELETE CASCADE,
    leg_index      INTEGER NOT NULL,
    kalshi_ticker  TEXT NOT NULL,
    outcome        TEXT NOT NULL,
    entry_price    REAL NOT NULL,
    spread_at_call REAL,
    volume_at_call REAL,
    PRIMARY KEY (opportunity_id, leg_index)
);

CREATE INDEX IF NOT EXISTS idx_opportunity_legs_ticker
    ON opportunity_legs (kalshi_ticker);
```

- [ ] **Step 4: Add the migration calls in `tools/db.py`**

In `init_db`, after the existing `_add_column_if_missing(conn, "theories", ...)` call, add:

```python
    # Additive: every pre-existing row is a single-leg position, and these
    # defaults describe it exactly, so there is no backfill.
    _add_column_if_missing(
        conn, "opportunities", "position_kind", "TEXT NOT NULL DEFAULT 'single'"
    )
    _add_column_if_missing(
        conn, "opportunities", "leg_count", "INTEGER NOT NULL DEFAULT 1"
    )
    _add_column_if_missing(
        conn, "opportunities", "max_payout", "REAL NOT NULL DEFAULT 1.0"
    )
```

Note: `ALTER TABLE ADD COLUMN` cannot carry the CHECK constraint, so a database migrated in place enforces `position_kind` only in application code, while a freshly created one enforces it in SQL too. This is acceptable — `record_basket` is the only writer — and it is why `test_position_kind_rejects_an_unknown_value` runs against a fresh database.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_baskets.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Run the full suite for non-regression**

Run: `python -m pytest -m "not network" -q`
Expected: All existing tests PASS, none skipped or failed.

- [ ] **Step 7: Commit**

```bash
git add db/schema.sql tools/db.py tests/test_baskets.py
git commit -m "feat: opportunity_legs table and basket columns on opportunities"
```

---

### Task 2: Deterministic basket key

**Files:**
- Modify: `tools/ledger.py` (add near the top, after the constants)
- Test: `tests/test_baskets.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `ledger.basket_key(legs: list[dict]) -> str`, returning `"BASKET:"` plus 16 lowercase hex characters. Each leg dict has at least `{"kalshi_ticker": str, "outcome": str}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_baskets.py`:

```python
def test_basket_key_is_stable_across_leg_order():
    a = [{"kalshi_ticker": "AAA", "outcome": "yes"},
         {"kalshi_ticker": "BBB", "outcome": "no"}]
    b = list(reversed(a))
    assert ledger.basket_key(a) == ledger.basket_key(b)


def test_basket_key_normalizes_case():
    a = [{"kalshi_ticker": "aaa", "outcome": "YES"}]
    b = [{"kalshi_ticker": "AAA", "outcome": "yes"}]
    assert ledger.basket_key(a) == ledger.basket_key(b)


def test_basket_key_differs_on_different_legs():
    a = [{"kalshi_ticker": "AAA", "outcome": "yes"}]
    b = [{"kalshi_ticker": "AAA", "outcome": "no"}]
    assert ledger.basket_key(a) != ledger.basket_key(b)


def test_basket_key_shape():
    key = ledger.basket_key([{"kalshi_ticker": "AAA", "outcome": "yes"}])
    assert key.startswith("BASKET:")
    assert len(key) == len("BASKET:") + 16
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_baskets.py -k basket_key -v`
Expected: FAIL with `AttributeError: module 'tools.ledger' has no attribute 'basket_key'`

- [ ] **Step 3: Implement `basket_key`**

Add `import hashlib` to the imports in `tools/ledger.py`, then add after `VALID_EDGE_BASES`:

```python
#: Prefix marking a synthetic header ticker for a multi-leg position.
BASKET_PREFIX = "BASKET:"


def basket_key(legs: list[dict]) -> str:
    """A stable synthetic `kalshi_ticker` for a multi-leg position.

    The header row needs a ticker: the column is NOT NULL and the dedup key
    is built from it. A basket resolves to several real tickers, so the
    header carries a hash of them and the tradeability guarantee moves to
    `opportunity_legs`, where every row has a real one.

    Sorted and case-normalized so the same basket produces the same key on
    every scan regardless of leg ordering. That is what preserves the
    re-sighting rule -- a basket that stays mispriced for a week is one bet
    seen seven times, not seven bets.
    """
    parts = sorted(
        f"{(leg['kalshi_ticker'] or '').strip().upper()}:"
        f"{(leg['outcome'] or '').strip().lower()}"
        for leg in legs
    )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"{BASKET_PREFIX}{digest[:16]}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_baskets.py -k basket_key -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/ledger.py tests/test_baskets.py
git commit -m "feat: deterministic basket key for multi-leg header rows"
```

---

### Task 3: `record_basket()`

**Files:**
- Modify: `tools/ledger.py` (add after `record_opportunity`, around line 243)
- Test: `tests/test_baskets.py`

**Interfaces:**
- Consumes: `ledger.basket_key(legs)` from Task 2; `provenance.require_provenance`, `db.write`, `db.utcnow` (all existing).
- Produces:
  - `ledger.record_basket(conn, *, theory_id, theory_version, legs, edge_pts_net, max_payout=1.0, run_mode="live", run_id=None, scan_id=None, model_prob=None, edge_pts_gross=None, fee_pts=None, edge_basis="prior", confidence=None, judged_blind=None, rationale=None, suggested_size=None, evidence_source=None, evidence_market_id=None, extra_json=None, now=None) -> tuple[int, bool]` — returns `(opportunity_id, was_created)`.
  - `ledger.get_legs(conn, opportunity_id) -> list[sqlite3.Row]` ordered by `leg_index`.
  - Each `leg` dict: `{"kalshi_ticker": str, "outcome": str, "entry_price": float, "spread_at_call": float|None, "volume_at_call": float|None}`. The last two are optional.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_baskets.py`:

```python
def _legs():
    return [
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.40},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.55},
    ]


def _basket(conn, **overrides):
    kwargs = dict(
        theory_id="t1", theory_version=1, legs=_legs(),
        edge_pts_net=5.0, edge_basis="model", now=TS,
    )
    kwargs.update(overrides)
    return ledger.record_basket(conn, **kwargs)


def test_basket_writes_one_header_and_n_leg_rows(conn):
    opp_id, created = _basket(conn)
    assert created is True
    row = ledger.get_opportunity(conn, opp_id)
    assert row["position_kind"] == "basket"
    assert row["leg_count"] == 2
    assert row["outcome"] == "basket"
    assert row["kalshi_ticker"].startswith("BASKET:")
    assert len(ledger.get_legs(conn, opp_id)) == 2


def test_basket_entry_price_is_the_summed_cost(conn):
    opp_id, _ = _basket(conn)
    row = ledger.get_opportunity(conn, opp_id)
    assert row["entry_price"] == pytest.approx(0.95)


def test_basket_legs_are_normalized_and_ordered(conn):
    opp_id, _ = _basket(conn, legs=[
        {"kalshi_ticker": " kxa-26 ", "outcome": "YES", "entry_price": 0.40},
        {"kalshi_ticker": "KXB-26", "outcome": " No ", "entry_price": 0.55},
    ])
    legs = ledger.get_legs(conn, opp_id)
    assert [l["leg_index"] for l in legs] == [0, 1]
    assert legs[0]["kalshi_ticker"] == "KXA-26"
    assert legs[0]["outcome"] == "yes"
    assert legs[1]["outcome"] == "no"


def test_resighting_a_basket_updates_rather_than_inserts(conn):
    first, created_a = _basket(conn)
    second, created_b = _basket(conn, now=LATER, edge_pts_net=7.0)
    assert created_a is True and created_b is False
    assert first == second
    row = ledger.get_opportunity(conn, first)
    assert row["times_seen"] == 2
    assert row["last_seen_at"] == LATER
    assert len(ledger.get_legs(conn, first)) == 2


def test_resighting_with_reordered_legs_is_the_same_basket(conn):
    first, _ = _basket(conn)
    second, created = _basket(conn, legs=list(reversed(_legs())), now=LATER)
    assert created is False
    assert first == second


def test_basket_cost_above_one_is_allowed_when_payout_allows_it(conn):
    opp_id, _ = _basket(conn, max_payout=2.0, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "no", "entry_price": 0.80},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.85},
    ])
    assert ledger.get_opportunity(conn, opp_id)["entry_price"] == pytest.approx(1.65)


def test_basket_cost_above_max_payout_is_refused(conn):
    with pytest.raises(ValueError, match="max_payout"):
        _basket(conn, max_payout=1.0, legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "no", "entry_price": 0.80},
            {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.85},
        ])


def test_basket_refuses_empty_legs(conn):
    with pytest.raises(ValueError, match="at least one leg"):
        _basket(conn, legs=[])


def test_basket_refuses_a_leg_with_no_ticker(conn):
    with pytest.raises(ValueError, match="kalshi_ticker"):
        _basket(conn, legs=[
            {"kalshi_ticker": "", "outcome": "yes", "entry_price": 0.40},
        ])


def test_basket_refuses_a_leg_price_in_cents(conn):
    with pytest.raises(ValueError, match="decimal dollars"):
        _basket(conn, legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 40},
        ])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_baskets.py -k basket -v`
Expected: FAIL with `AttributeError: module 'tools.ledger' has no attribute 'record_basket'`

- [ ] **Step 3: Implement `record_basket` and `get_legs`**

Add to `tools/ledger.py` after `record_opportunity`:

```python
def _normalize_legs(legs: list[dict], max_payout: float) -> list[dict]:
    """Validate and normalize legs, returning them in a stable order.

    Every leg price goes through the same [0, 1] validator single positions
    use -- a leg is an ordinary Kalshi contract and the cents-vs-dollars
    mistake is just as costly here. The *basket* cost is checked against
    max_payout instead of 1.0, because a NO-basket over k outcomes can
    legitimately cost more than a dollar while paying (k-1).
    """
    if not legs:
        raise ValueError(
            "a basket needs at least one leg: the tradeability guarantee "
            "lives on the legs, so a basket with none has no Kalshi market"
        )
    out = []
    for i, leg in enumerate(legs):
        ticker = (leg.get("kalshi_ticker") or "").strip().upper()
        if not ticker:
            raise ValueError(
                f"leg {i} has no kalshi_ticker: every leg must resolve to a "
                "tradeable Kalshi market"
            )
        _validate_entry_price(leg.get("entry_price"))
        out.append({
            "kalshi_ticker": ticker,
            "outcome": (leg.get("outcome") or "").strip().lower(),
            "entry_price": float(leg["entry_price"]),
            "spread_at_call": leg.get("spread_at_call"),
            "volume_at_call": leg.get("volume_at_call"),
        })

    cost = sum(leg["entry_price"] for leg in out)
    if cost > max_payout:
        raise ValueError(
            f"basket cost {cost:.4f} exceeds max_payout {max_payout:.4f}; "
            "a position that cannot profit in any branch is not an edge"
        )
    # Sorted so leg_index is deterministic across re-sightings, matching
    # basket_key's ordering.
    out.sort(key=lambda leg: (leg["kalshi_ticker"], leg["outcome"]))
    return out


def record_basket(
    conn: sqlite3.Connection,
    *,
    theory_id: str,
    theory_version: int,
    legs: list[dict],
    edge_pts_net: float,
    max_payout: float = 1.0,
    run_mode: str = "live",
    run_id: str | None = None,
    scan_id: str | None = None,
    model_prob: float | None = None,
    edge_pts_gross: float | None = None,
    fee_pts: float | None = None,
    edge_basis: str = "prior",
    confidence: str | None = None,
    judged_blind: bool | None = None,
    rationale: str | None = None,
    suggested_size: float | None = None,
    evidence_source: str | None = None,
    evidence_market_id: str | None = None,
    extra_json: str | None = None,
    now: str | None = None,
) -> tuple[int, bool]:
    """Record or refresh a multi-leg position. Returns (id, was_created).

    The header row carries the aggregate -- `entry_price` is the basket's
    total cost, `leg_count` is N, `max_payout` is the most it can pay -- and
    `opportunity_legs` carries the tradeable tickers.
    """
    if edge_pts_net is None:
        raise ValueError(
            "edge_pts_net is required: it is the common currency used to "
            "rank across theories"
        )
    if run_mode not in ("live", "backtest"):
        raise ValueError(f"invalid run_mode {run_mode!r}")
    if run_mode == "backtest" and not run_id:
        raise ValueError("run_id is required for backtest runs")
    if run_mode == "backtest" and run_id == LIVE_RUN_ID:
        raise ValueError(
            f"run_id {LIVE_RUN_ID!r} is a reserved sentinel for live scans"
        )
    if edge_basis not in VALID_EDGE_BASES:
        raise ValueError(
            f"invalid edge_basis {edge_basis!r}; "
            f"expected one of {VALID_EDGE_BASES}"
        )

    norm = _normalize_legs(legs, max_payout)
    provenance.require_provenance(
        conn, theory_id, theory_version, run_id or LIVE_RUN_ID
    )

    header_ticker = basket_key(norm)
    cost = sum(leg["entry_price"] for leg in norm)
    resolved_run_id = run_id or LIVE_RUN_ID
    stamp = now or utcnow()

    with write(conn):
        conn.execute(
            """
            INSERT INTO opportunities (
                theory_id, theory_version, run_mode, run_id, scan_id,
                kalshi_ticker, outcome, entry_price, position_kind,
                leg_count, max_payout, model_prob, edge_pts_gross, fee_pts,
                screen_edge_pts_net, edge_pts_net, edge_basis, disposition,
                confidence, judged_blind, rationale, suggested_size,
                evidence_source, evidence_market_id, user_action,
                first_seen_at, last_seen_at, times_seen, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, 'basket', ?, 'basket', ?, ?, ?, ?, ?,
                      ?, ?, ?, 'screened', ?, ?, ?, ?, ?, ?, 'untouched',
                      ?, ?, 1, ?)
            ON CONFLICT (theory_id, theory_version, run_id, kalshi_ticker,
                         outcome) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                times_seen = opportunities.times_seen + 1,
                edge_pts_net = CASE
                    WHEN opportunities.interpreted_at IS NULL
                        THEN excluded.edge_pts_net
                    ELSE opportunities.edge_pts_net
                END,
                model_prob =
                    COALESCE(excluded.model_prob, opportunities.model_prob),
                edge_pts_gross = COALESCE(excluded.edge_pts_gross,
                                          opportunities.edge_pts_gross),
                fee_pts = COALESCE(excluded.fee_pts, opportunities.fee_pts),
                confidence =
                    COALESCE(excluded.confidence, opportunities.confidence),
                rationale =
                    COALESCE(excluded.rationale, opportunities.rationale),
                suggested_size = COALESCE(excluded.suggested_size,
                                          opportunities.suggested_size)
            """,
            (
                theory_id, theory_version, run_mode, resolved_run_id, scan_id,
                header_ticker, cost, len(norm), max_payout, model_prob,
                edge_pts_gross, fee_pts, edge_pts_net, edge_pts_net,
                edge_basis, confidence,
                1 if judged_blind else (0 if judged_blind is not None else None),
                rationale, suggested_size, evidence_source,
                evidence_market_id, stamp, stamp, extra_json,
            ),
        )

        row = conn.execute(
            """
            SELECT id, times_seen FROM opportunities
            WHERE theory_id = ? AND theory_version = ? AND run_id = ?
              AND kalshi_ticker = ? AND outcome = 'basket'
            """,
            (theory_id, theory_version, resolved_run_id, header_ticker),
        ).fetchone()

        # Legs are rewritten wholesale on every sighting. The basket key is
        # derived from the legs, so a re-sighting has identical legs by
        # construction; rewriting keeps quotes fresh without a diffing step
        # that could leave a stale leg behind.
        conn.execute(
            "DELETE FROM opportunity_legs WHERE opportunity_id = ?",
            (row["id"],),
        )
        conn.executemany(
            """
            INSERT INTO opportunity_legs (
                opportunity_id, leg_index, kalshi_ticker, outcome,
                entry_price, spread_at_call, volume_at_call
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (row["id"], i, leg["kalshi_ticker"], leg["outcome"],
                 leg["entry_price"], leg["spread_at_call"],
                 leg["volume_at_call"])
                for i, leg in enumerate(norm)
            ],
        )

    return row["id"], row["times_seen"] == 1


def get_legs(
    conn: sqlite3.Connection, opportunity_id: int
) -> list[sqlite3.Row]:
    """Every leg of a position, in stable order. Empty for a single."""
    return conn.execute(
        "SELECT * FROM opportunity_legs WHERE opportunity_id = ?"
        " ORDER BY leg_index",
        (opportunity_id,),
    ).fetchall()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_baskets.py -v`
Expected: PASS (all tests, including Tasks 1 and 2)

- [ ] **Step 5: Run the full suite for non-regression**

Run: `python -m pytest -m "not network" -q`
Expected: All existing tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/ledger.py tests/test_baskets.py
git commit -m "feat: record_basket writes a header plus its legs atomically"
```

---

### Task 4: Lock and refactor `compute_score` — no behavior change

**Files:**
- Create: `tests/test_score_characterization.py`
- Modify: `tools/score.py:81-165` (`compute_score`)

**Interfaces:**
- Consumes: `score.compute_score(conn, theory_id, theory_version, run_mode="live", disposition="all", *, run_id=None) -> dict` — signature unchanged.
- Produces: internal `score._Observation` (a `dict` with keys `implied_rate`, `won`, `cost`, `payout`, `fee_pts`, `edge_pts_net`, `user_action`) and `score._single_leg_observations(conn, sql_filters) -> list[dict]`. Task 5 adds the basket sibling.

**This task changes no behavior.** It exists so Task 5 has a seam to add baskets to, and so any accidental change is caught by a test written *before* the refactor.

- [ ] **Step 1: Write the characterization test**

Create `tests/test_score_characterization.py`:

```python
"""Locks compute_score's exact arithmetic before the basket refactor.

These numbers are not derived from the implementation -- they are computed
by hand from the documented fee model and the definitions in the spec, so a
refactor that changes them fails here rather than silently shifting every
theory's calibration_edge_net.
"""

import pytest

from tools import db, ledger, score, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _bet(conn, ticker, entry_price, edge, outcome="yes"):
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker=ticker,
        outcome=outcome, entry_price=entry_price, edge_pts_net=edge, now=TS,
    )
    return opp_id


def test_four_settled_singles_produce_exact_numbers(conn):
    # Two winners at 0.50, one winner at 0.80, one loser at 0.20.
    _bet(conn, "A", 0.50, 6.0)
    _bet(conn, "B", 0.50, 6.0)
    _bet(conn, "C", 0.80, 4.0)
    _bet(conn, "D", 0.20, 8.0)
    for ticker, result in (("A", "yes"), ("B", "yes"),
                           ("C", "yes"), ("D", "no")):
        score.record_settlement(conn, ticker, result, resolved_at=TS)

    r = score.compute_score(conn, "t1", 1)

    assert r["n"] == 4
    assert r["win_rate"] == pytest.approx(0.75)
    assert r["price_implied_rate"] == pytest.approx(0.50)
    assert r["calibration_edge"] == pytest.approx(25.0)
    assert r["mean_claimed_edge"] == pytest.approx(6.0)
    # Fees and the net edge come from tools.sizing.fee_pts; assert the
    # relationship rather than a hardcoded constant so the fee model stays
    # the single source of truth.
    assert r["calibration_edge_net"] == pytest.approx(
        r["calibration_edge"] - r["mean_fee_pts"]
    )
    assert r["mean_fee_pts"] > 0


def test_roi_all_uses_cost_including_fees(conn):
    _bet(conn, "A", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes", resolved_at=TS)
    r = score.compute_score(conn, "t1", 1)
    from tools.sizing import fee_pts
    cost = 0.50 + fee_pts(0.50) / 100.0
    assert r["roi_all"] == pytest.approx((1.0 - cost) / cost)


def test_unsettled_rows_are_excluded(conn):
    _bet(conn, "A", 0.50, 6.0)
    _bet(conn, "B", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes", resolved_at=TS)
    assert score.compute_score(conn, "t1", 1)["n"] == 1
```

- [ ] **Step 2: Run test to verify it PASSES**

Run: `python -m pytest tests/test_score_characterization.py -v`
Expected: PASS — this locks *current* behavior. If it fails, stop: the hand-computed expectations disagree with the implementation and that must be understood before refactoring.

- [ ] **Step 3: Refactor `compute_score` into observations**

Replace the body of `compute_score` in `tools/score.py` (lines 96-165, from `sql = """` to the closing `}` of the return) with:

```python
    obs = _single_leg_observations(
        conn, theory_id, theory_version, run_mode, disposition, run_id
    )
    return _aggregate(obs)


def _segment_filter(
    theory_id: str, theory_version: int, run_mode: str,
    disposition: str, run_id: str | None,
) -> tuple[str, list[object]]:
    """The WHERE clause every observation query shares."""
    sql = " WHERE o.theory_id = ? AND o.theory_version = ? AND o.run_mode = ?"
    params: list[object] = [theory_id, theory_version, run_mode]
    if disposition != "all":
        sql += " AND o.disposition = ?"
        params.append(disposition)
    if run_id is not None:
        sql += " AND o.run_id = ?"
        params.append(run_id)
    return sql, params


def _single_leg_observations(
    conn: sqlite3.Connection, theory_id: str, theory_version: int,
    run_mode: str, disposition: str, run_id: str | None,
) -> list[dict]:
    """One observation per settled single-leg position."""
    where, params = _segment_filter(
        theory_id, theory_version, run_mode, disposition, run_id
    )
    sql = (
        "SELECT o.outcome, o.entry_price, o.edge_pts_net, o.user_action,"
        " s.result FROM opportunities o"
        " JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker"
        + where
        + " AND o.position_kind = 'single'"
    )
    out = []
    for row in conn.execute(sql, params).fetchall():
        won = _won(row["outcome"], row["result"])
        price = row["entry_price"]
        fee = fee_pts(price)
        out.append({
            "implied_rate": price,
            "won": won,
            "cost": price + fee / 100.0,
            "payout": 1.0 if won else 0.0,
            "fee_pts": fee,
            "edge_pts_net": row["edge_pts_net"],
            "user_action": row["user_action"],
        })
    return out


def _aggregate(rows: list[dict]) -> dict:
    """Turn observations into the score dict. Shared by every position kind."""
    if not rows:
        return dict(EMPTY_SCORE)

    n = len(rows)
    wins = sum(1 for r in rows if r["won"])
    total_cost = sum(r["cost"] for r in rows)
    total_return = sum(r["payout"] for r in rows)
    total_fee_pts = sum(r["fee_pts"] for r in rows)

    taken = [r for r in rows if r["user_action"] == "taken"]
    taken_cost = sum(r["cost"] for r in taken)
    taken_return = sum(r["payout"] for r in taken)

    win_rate = wins / n
    price_implied_rate = sum(r["implied_rate"] for r in rows) / n
    calibration_edge = (win_rate - price_implied_rate) * 100.0
    mean_fee_pts = total_fee_pts / n
    calibration_edge_net = calibration_edge - mean_fee_pts
    mean_claimed_edge = sum(r["edge_pts_net"] for r in rows) / n

    roi_all = (total_return - total_cost) / total_cost if total_cost else None
    roi_taken = (
        (taken_return - taken_cost) / taken_cost
        if taken and taken_cost
        else None
    )

    return {
        "n": n,
        "win_rate": win_rate,
        "price_implied_rate": price_implied_rate,
        "calibration_edge": calibration_edge,
        "calibration_edge_net": calibration_edge_net,
        "mean_claimed_edge": mean_claimed_edge,
        "mean_fee_pts": mean_fee_pts,
        "realization": _realization(calibration_edge_net, mean_claimed_edge),
        "roi_all": roi_all,
        "roi_taken": roi_taken,
    }
```

Keep `compute_score`'s docstring and signature exactly as they are.

- [ ] **Step 4: Run the characterization test and the full suite**

Run: `python -m pytest tests/test_score_characterization.py tests/test_score.py -v`
Expected: PASS — identical numbers before and after the refactor.

Run: `python -m pytest -m "not network" -q`
Expected: All PASS.

- [ ] **Step 5: Verify parity against the live database**

```bash
python -c "
from tools import db, score, theories
c = db.connect()
for t in theories.list_theories(c):
    print(t['id'], t['version'], score.compute_score(c, t['id'], t['version']))
"
```

Record the output. Compare it to the same command run from `git stash`-ed pre-refactor code. Expected: byte-identical. This is spec success criterion 1.

- [ ] **Step 6: Commit**

```bash
git add tools/score.py tests/test_score_characterization.py
git commit -m "refactor: compute_score builds observations then aggregates"
```

---

### Task 5: Basket settlement and scoring

**Files:**
- Modify: `tools/score.py` (`compute_score`, plus a new `_basket_observations`)
- Test: `tests/test_baskets.py`

**Interfaces:**
- Consumes: `score._segment_filter`, `score._aggregate`, `score._single_leg_observations` from Task 4; `ledger.record_basket` from Task 3.
- Produces: `score._basket_observations(conn, theory_id, theory_version, run_mode, disposition, run_id) -> list[dict]`, returning the same observation shape.

- [ ] **Step 1: Write the failing test**

First widen the import line at the top of `tests/test_baskets.py` from
`from tools import db, ledger, theories` to:

```python
from tools import db, ledger, score, theories
from tools.sizing import fee_pts
```

Then append:

```python
def _settle(conn, pairs):
    for ticker, result in pairs:
        score.record_settlement(conn, ticker, result, resolved_at=TS)


def test_basket_with_an_unsettled_leg_is_excluded(conn):
    _basket(conn)
    _settle(conn, [("KXA-26", "yes")])
    assert score.compute_score(conn, "t1", 1)["n"] == 0


def test_fully_settled_basket_counts_once(conn):
    _basket(conn)
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "yes")])
    assert score.compute_score(conn, "t1", 1)["n"] == 1


def test_profitable_basket_scores_as_a_win(conn):
    # legs cost 0.95; KXA yes wins ($1), KXB no loses ($0). Payout 1.00.
    _basket(conn)
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "yes")])
    r = score.compute_score(conn, "t1", 1)
    assert r["win_rate"] == pytest.approx(1.0)
    cost = 0.95 + (fee_pts(0.40) + fee_pts(0.55)) / 100.0
    assert r["roi_all"] == pytest.approx((1.0 - cost) / cost)


def test_losing_basket_scores_as_a_loss(conn):
    # Both legs lose: KXA settles no (we hold yes), KXB settles yes (we hold no).
    _basket(conn)
    _settle(conn, [("KXA-26", "no"), ("KXB-26", "yes")])
    r = score.compute_score(conn, "t1", 1)
    assert r["win_rate"] == pytest.approx(0.0)
    assert r["roi_all"] < 0


def test_basket_implied_rate_is_normalized_by_max_payout(conn):
    _basket(conn, max_payout=2.0, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "no", "entry_price": 0.80},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.85},
    ])
    _settle(conn, [("KXA-26", "no"), ("KXB-26", "no")])
    r = score.compute_score(conn, "t1", 1)
    assert r["price_implied_rate"] == pytest.approx(1.65 / 2.0)


def test_baskets_and_singles_pool_into_one_score(conn):
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXS-26",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS,
    )
    _basket(conn)
    _settle(conn, [("KXS-26", "yes"), ("KXA-26", "yes"), ("KXB-26", "yes")])
    assert score.compute_score(conn, "t1", 1)["n"] == 2


def test_a_basket_missing_a_leg_row_raises_rather_than_scoring(conn):
    opp_id, _ = _basket(conn)
    conn.execute(
        "DELETE FROM opportunity_legs WHERE opportunity_id = ? AND leg_index = 1",
        (opp_id,),
    )
    conn.commit()
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "yes")])
    with pytest.raises(ValueError, match="leg_count"):
        score.compute_score(conn, "t1", 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_baskets.py -k "basket and (settled or scores or implied or pool or missing)" -v`
Expected: FAIL — `n == 0` where 1 is expected, because `_single_leg_observations` filters to `position_kind = 'single'` and nothing reads baskets yet.

- [ ] **Step 3: Implement `_basket_observations` and wire it in**

In `tools/score.py`, change `compute_score`'s body to:

```python
    obs = _single_leg_observations(
        conn, theory_id, theory_version, run_mode, disposition, run_id
    ) + _basket_observations(
        conn, theory_id, theory_version, run_mode, disposition, run_id
    )
    return _aggregate(obs)
```

and add after `_single_leg_observations`:

```python
def _basket_observations(
    conn: sqlite3.Connection, theory_id: str, theory_version: int,
    run_mode: str, disposition: str, run_id: str | None,
) -> list[dict]:
    """One observation per fully-settled basket.

    A basket is one position with a joint payoff, so it contributes exactly
    one observation however many legs it has. Recording it as N rows would
    make a riskless arbitrage -- one winning leg, one losing leg, a certain
    $1 payout -- read as a 50% win rate.

    A basket with any unsettled leg is excluded, exactly as an unsettled
    single position is: its payoff is not yet known.
    """
    where, params = _segment_filter(
        theory_id, theory_version, run_mode, disposition, run_id
    )
    headers = conn.execute(
        "SELECT o.id, o.entry_price, o.edge_pts_net, o.user_action,"
        " o.leg_count, o.max_payout FROM opportunities o"
        + where
        + " AND o.position_kind = 'basket'",
        params,
    ).fetchall()

    out = []
    for header in headers:
        legs = conn.execute(
            "SELECT l.kalshi_ticker, l.outcome, l.entry_price, s.result"
            "  FROM opportunity_legs l"
            "  LEFT JOIN settlements s ON s.kalshi_ticker = l.kalshi_ticker"
            " WHERE l.opportunity_id = ? ORDER BY l.leg_index",
            (header["id"],),
        ).fetchall()

        # A leg row lost between write and read would make the basket look
        # cheaper than it was. Fail loudly rather than score a partial one.
        if len(legs) != header["leg_count"]:
            raise ValueError(
                f"opportunity {header['id']} declares leg_count "
                f"{header['leg_count']} but has {len(legs)} leg rows; "
                "refusing to score a partial basket"
            )

        if any(leg["result"] is None for leg in legs):
            continue

        payout = sum(
            1.0 for leg in legs if _won(leg["outcome"], leg["result"])
        )
        fee = sum(fee_pts(leg["entry_price"]) for leg in legs)
        cost = header["entry_price"] + fee / 100.0
        max_payout = header["max_payout"] or 1.0

        out.append({
            # Normalized so a basket's implied rate is comparable with a
            # single position's price. For max_payout = 1.0 this is the
            # cost itself, which is what a single leg contributes.
            "implied_rate": header["entry_price"] / max_payout,
            "won": payout > cost,
            "cost": cost,
            "payout": payout,
            "fee_pts": fee,
            "edge_pts_net": header["edge_pts_net"],
            "user_action": header["user_action"],
        })
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_baskets.py -v`
Expected: PASS (all)

- [ ] **Step 5: Run the full suite plus the characterization lock**

Run: `python -m pytest -m "not network" -q`
Expected: All PASS — in particular `tests/test_score.py` and `tests/test_score_characterization.py` unchanged, proving single-leg math did not move.

- [ ] **Step 6: Commit**

```bash
git add tools/score.py tests/test_baskets.py
git commit -m "feat: score a basket as one position with a joint payoff"
```

---

### Task 6: The `calendar-arb` payoff property

**Files:**
- Test: `tests/test_baskets.py`

**Interfaces:**
- Consumes: `ledger.record_basket`, `score.compute_score`, `score.record_settlement`.
- Produces: nothing — this is the end-to-end audit the spec asks for.

The `calendar-arb` spec claims a nesting-valid basket "pays ≥ $1 in all three [outcome branches] exactly when nesting holds", and says "any basket that would have lost is a classifier bug". This task turns that prose into an executable property.

- [ ] **Step 1: Write the test**

Append to `tests/test_baskets.py`:

```python
@pytest.mark.parametrize(
    "early_result,late_result",
    [
        ("no", "no"),    # event never happens: NO-early wins, YES-late loses
        ("no", "yes"),   # happens between deadlines: both win
        ("yes", "yes"),  # happens before the early deadline: YES-late wins
    ],
)
def test_nesting_valid_basket_pays_at_least_one_in_every_branch(
    conn, early_result, late_result
):
    """The calendar-arb payoff matrix, as an executable property.

    Legs: buy YES on the later deadline, buy NO on the earlier one. Under
    nesting (early YES implies late YES) the impossible branch is
    (early=yes, late=no), which is why it is absent from the parametrize
    list rather than expected to fail.
    """
    ledger.record_basket(
        conn, theory_id="t1", theory_version=1, edge_pts_net=4.0,
        edge_basis="model", now=TS,
        legs=[
            {"kalshi_ticker": "KXLATE-26", "outcome": "yes",
             "entry_price": 0.60},
            {"kalshi_ticker": "KXEARLY-26", "outcome": "no",
             "entry_price": 0.35},
        ],
    )
    _settle(conn, [("KXEARLY-26", early_result), ("KXLATE-26", late_result)])

    obs = score._basket_observations(conn, "t1", 1, "live", "all", None)
    assert len(obs) == 1
    assert obs[0]["payout"] >= 1.0


def test_a_basket_that_would_have_lost_is_visible_as_a_loss(conn):
    """The classifier-bug detector: a mis-classified pair scores negative."""
    ledger.record_basket(
        conn, theory_id="t1", theory_version=1, edge_pts_net=4.0,
        edge_basis="model", now=TS,
        legs=[
            {"kalshi_ticker": "KXP-26", "outcome": "yes", "entry_price": 0.60},
            {"kalshi_ticker": "KXQ-26", "outcome": "yes", "entry_price": 0.35},
        ],
    )
    # Both legs lose -- no nesting relationship held.
    _settle(conn, [("KXP-26", "no"), ("KXQ-26", "no")])
    r = score.compute_score(conn, "t1", 1)
    assert r["n"] == 1
    assert r["win_rate"] == pytest.approx(0.0)
    assert r["roi_all"] == pytest.approx(-1.0)
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/test_baskets.py -k "nesting or would_have_lost" -v`
Expected: PASS (4 tests — three parametrized branches plus the loss case). If a branch fails, the payoff arithmetic in `_basket_observations` is wrong, not the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_baskets.py
git commit -m "test: calendar-arb payoff property holds in all three branches"
```

---

### Task 7: Legs in the CLI output

**Files:**
- Modify: `tools/cli.py` (the `opportunities list` handler and its parser)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `ledger.get_legs(conn, opportunity_id)` from Task 3.
- Produces: `python -m tools.cli opportunities list --with-legs` emits each row with a `"legs"` array; without the flag, output is byte-identical to today.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py` already has a `dbpath` fixture and a `_run(capsys, *args)` helper (file lines 10-22). Reuse both. Append:

```python
def _seed_positions(dbpath):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXS-26",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS,
    )
    ledger.record_basket(
        conn, theory_id="t1", theory_version=1, edge_pts_net=5.0,
        edge_basis="model", now=TS,
        legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "yes",
             "entry_price": 0.40},
            {"kalshi_ticker": "KXB-26", "outcome": "no",
             "entry_price": 0.55},
        ],
    )
    conn.close()


def test_opportunities_list_omits_legs_by_default(dbpath, capsys):
    _seed_positions(dbpath)
    code, payload = _run(capsys, "--db", dbpath, "opportunities", "list")
    assert code == 0
    assert len(payload) == 2
    assert all("legs" not in row for row in payload)


def test_opportunities_list_with_legs_includes_them(dbpath, capsys):
    _seed_positions(dbpath)
    code, payload = _run(
        capsys, "--db", dbpath, "opportunities", "list", "--with-legs"
    )
    assert code == 0
    basket = [r for r in payload if r["position_kind"] == "basket"][0]
    assert len(basket["legs"]) == basket["leg_count"] == 2
    assert all(leg["kalshi_ticker"] for leg in basket["legs"])
    single = [r for r in payload if r["position_kind"] == "single"][0]
    assert single["legs"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -k legs -v`
Expected: FAIL — `unrecognized arguments: --with-legs`

- [ ] **Step 3: Add the flag and the enrichment**

In `tools/cli.py`, on the `olist` parser (around line 323), add:

```python
    olist.add_argument(
        "--with-legs", action="store_true",
        help="include each position's legs (empty for single positions)",
    )
```

Restructure the `list` branch of `_cmd_opportunities` (`tools/cli.py:127-137`) so the rows are named before emitting:

```python
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
```

Default output is untouched — without the flag no `legs` key is added — so every existing CLI consumer keeps working.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -m "not network" -q`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/cli.py tests/test_cli.py
git commit -m "feat: opportunities list --with-legs exposes basket legs"
```

---

### Task 8: Documentation

**Files:**
- Modify: `tools/README.md` (the `ledger.py` row in the tool map, and the conventions list)
- Modify: `CLAUDE.md` (the data conventions section)

**Interfaces:**
- Consumes: everything above.
- Produces: no code.

- [ ] **Step 1: Update `tools/README.md`**

Change the `ledger.py` row of the tool map to:

```markdown
| `ledger.py` | `record_opportunity`, `record_basket`, interpretation, user actions |
```

Add to the Conventions list, after the "Prices are decimal dollars" bullet:

```markdown
- **A position may have legs.** `record_opportunity` writes a single
  position; `record_basket` writes a multi-leg one whose payoff is joint.
  A basket's `entry_price` is its total cost and is bounded by `max_payout`,
  not by 1.0. Scoring counts a basket once, and excludes it until every leg
  has settled — recording an arbitrage as N independent bets makes a certain
  payout read as a coin flip.
```

- [ ] **Step 2: Update `CLAUDE.md`**

In the Data conventions section, after the "Prices are decimal dollars in [0, 1]" bullet, add:

```markdown
- **A basket is one position, not N bets.** Theories whose edge is a sum
  over legs (`structural-arb`, `calendar-arb`, `implication-graph`) record
  with `ledger.record_basket`, which writes one header plus its legs and is
  scored as a single joint payoff. Execution risk across legs is *reported*
  to the user, never modelled — present every leg with its own ask and tell
  the user to verify all legs before entering.
```

- [ ] **Step 3: Verify no stale claims remain**

Run: `grep -rn "one leg per row\|single position only\|kalshi_ticker is required" tools/README.md CLAUDE.md docs/superpowers/specs/2026-08-24-multi-leg-positions-design.md`
Expected: no hits that contradict the new behavior. Fix any that do.

- [ ] **Step 4: Commit**

```bash
git add tools/README.md CLAUDE.md
git commit -m "docs: baskets are one position with a joint payoff"
```

---

## Verification Checklist

Run after the final task. Every item is a spec success criterion.

- [ ] `python -m pytest -m "not network" -q` — all pass, none skipped or deleted.
- [ ] Live-database parity: `compute_score` returns identical numbers to pre-change code for every existing theory (Task 4, Step 5).
- [ ] A two-leg `calendar-arb` basket records as one position, settles jointly, and pays ≥ $1 in all three branches (Task 6).
- [ ] A basket contributes exactly one observation to `n` (Task 5).
- [ ] A basket with a missing or unsettled leg is excluded or raises, never scored partially (Task 5).
- [ ] `settlements` is unchanged; `git diff` touches no line of that table.
- [ ] No new concept beyond `Leg`-shaped dicts, three columns, and one table.

## Open Questions Carried From The Spec

These are recorded, not resolved. Raise them with the user if implementation forces the issue.

1. **NO-basket payout.** `max_payout` is declared by the caller rather than derived, because exhaustiveness of a mutually-exclusive set is a theory-level guard. If a theory declares it wrongly, scoring normalizes wrongly — worth a follow-up validation once `structural-arb` exists.
2. **Fees on a basket.** This plan sums `fee_pts` per leg. Confirm against Kalshi's published fee schedule before the first real basket is bet; if Kalshi charges per-order rather than per-contract, `_basket_observations` needs one line changed.
3. **Partial user fills.** `mark-taken` records one size for the whole position. Per-leg user actions are deliberately not built — no basket has been taken yet, and speculating would build a schema nobody has needed.
