# Foundation Layer Implementation Plan (Plan 1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the storage, math, and ledger core that every theory and skill in the market-edge system depends on — a working, fully-tested engine for recording opportunities, interpreting them, and scoring them against real settlements.

**Architecture:** A SQLite database (`db/market_edge.db`) created from a declarative schema, plus five small single-responsibility Python modules under `tools/`. Everything in this plan is pure logic with zero network calls, so it is entirely unit-testable with fixtures. Plan 2 adds the platform data connectors that feed this layer; Plan 3 adds the theory harness and skills that drive it.

**Tech Stack:** Python 3.11, sqlite3 (stdlib), pytest 8.3. No third-party runtime dependencies in this plan.

**Spec:** `docs/superpowers/specs/2026-08-23-llm-market-edge-finder-design.md`

## Roadmap (context for this plan)

- **Plan 1 — Foundation (this document):** schema, db, sizing, rank, theories registry, ledger, score.
- **Plan 2 — Data connectors:** `tools/kalshi/*`, `tools/polymarket/*`, `snapshot.py`, `match_market.py`.
- **Plan 3 — Theory harness and operating modes:** `_TEMPLATE`, ported `insider_bias`, `migrate_kalshi_trader.py`, the six skills (`go`, `find-edge`, `propose-theory`, `backtest-theory`, `score-theories`, `compare-theories`), `RESEARCH_LOG.md`, `CLAUDE.md`, `tools/README.md`.

## Global Constraints

- Python 3.11. Standard library only for this plan — no `requests`, no ORM.
- All timestamps are **UTC ISO-8601 strings** (`2026-08-23T17:30:00Z`). Store as TEXT. Never store naive local time.
- All prices are **decimal dollars in [0, 1]** (`0.93` = 93 cents). Never integer cents. Kalshi's API returns decimal-dollar strings; conversion happens in Plan 2's connectors, so this layer only ever sees floats.
- All edge values are in **percentage points** (`6.0` = 6 points = 0.06 probability). This includes `calibration_edge`, which is stored as `(win_rate − price_implied_rate) × 100` so it is directly comparable to `mean_claimed_edge`. (Spec section 5 writes the formula without the ×100; points are the consistent unit and this plan is the authority on it.)
- `PRAGMA foreign_keys = ON` on every connection.
- Every function that needs "now" accepts an injectable `now` parameter defaulting to `None` → real UTC. Tests always pass an explicit timestamp; never assert against wall-clock time.
- Kalshi fee model (verified 2026-08-23): per-contract fee = `min(0.07 × P × (1−P), 0.035)` dollars; an actual order's charged fee rounds **up to the whole cent** across all contracts. Cap is $0.035/contract.
- Test files live in `tests/` mirroring the `tools/` layout. Run with `python -m pytest`.
- Commit after every task with a `feat:` or `test:` prefixed message.

---

### Task 1: Project scaffolding, schema, and database connection

**Files:**
- Create: `.gitignore`
- Create: `db/schema.sql`
- Create: `tools/__init__.py`
- Create: `tools/db.py`
- Create: `tests/__init__.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - `tools.db.connect(path: str | Path) -> sqlite3.Connection` — opens a connection with `foreign_keys` ON and `row_factory = sqlite3.Row`
  - `tools.db.init_db(conn: sqlite3.Connection) -> None` — executes `db/schema.sql`; idempotent
  - `tools.db.utcnow() -> str` — current UTC as `YYYY-MM-DDTHH:MM:SSZ`
  - `tools.db.SCHEMA_PATH: Path` — absolute path to `db/schema.sql`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
db/*.db
.venv/
```

- [ ] **Step 2: Write `db/schema.sql`**

```sql
-- Market Edge Finder schema.
-- All timestamps are UTC ISO-8601 TEXT. All prices are decimal dollars in [0,1].
-- All edge values are in percentage points.

CREATE TABLE IF NOT EXISTS theories (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed','active','paused','retired')),
    path        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    platform         TEXT NOT NULL CHECK (platform IN ('kalshi','polymarket')),
    market_id        TEXT NOT NULL,
    captured_at      TEXT NOT NULL,
    title            TEXT,
    implied_prob_yes REAL,
    yes_bid          REAL,
    yes_ask          REAL,
    volume           REAL,
    open_interest    REAL,
    close_time       TEXT,
    status           TEXT,
    raw_json         TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshots_market
    ON market_snapshots (platform, market_id, captured_at);

CREATE TABLE IF NOT EXISTS opportunities (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    theory_id           TEXT NOT NULL REFERENCES theories(id),
    theory_version      INTEGER NOT NULL,
    run_mode            TEXT NOT NULL CHECK (run_mode IN ('live','backtest')),
    run_id              TEXT NOT NULL,
    scan_id             TEXT,
    kalshi_ticker       TEXT NOT NULL,
    outcome             TEXT NOT NULL,
    entry_price         REAL NOT NULL,
    spread_at_call      REAL,
    volume_at_call      REAL,
    model_prob          REAL,
    edge_pts_gross      REAL,
    fee_pts             REAL,
    screen_edge_pts_net REAL NOT NULL,
    edge_pts_net        REAL NOT NULL,
    disposition         TEXT NOT NULL DEFAULT 'screened'
                        CHECK (disposition IN ('screened','endorsed','rejected')),
    interpretation      TEXT,
    interpreted_at      TEXT,
    confidence          TEXT,
    rationale           TEXT,
    suggested_size      REAL,
    evidence_source     TEXT,
    evidence_market_id  TEXT,
    user_action         TEXT NOT NULL DEFAULT 'untouched'
                        CHECK (user_action IN ('untouched','taken','skipped')),
    user_size           REAL,
    user_reason         TEXT,
    first_seen_at       TEXT NOT NULL,
    last_seen_at        TEXT NOT NULL,
    times_seen          INTEGER NOT NULL DEFAULT 1,
    extra_json          TEXT,
    UNIQUE (theory_id, theory_version, run_id, kalshi_ticker, outcome)
);

CREATE INDEX IF NOT EXISTS idx_opportunities_theory
    ON opportunities (theory_id, theory_version, run_mode, disposition);

CREATE INDEX IF NOT EXISTS idx_opportunities_ticker
    ON opportunities (kalshi_ticker);

CREATE TABLE IF NOT EXISTS settlements (
    kalshi_ticker TEXT PRIMARY KEY,
    resolved_at   TEXT,
    result        TEXT NOT NULL,
    settle_price  REAL
);

CREATE TABLE IF NOT EXISTS scores (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    theory_id          TEXT NOT NULL REFERENCES theories(id),
    theory_version     INTEGER NOT NULL,
    run_mode           TEXT NOT NULL,
    disposition        TEXT NOT NULL,
    backtest_tier      TEXT,
    window_start       TEXT,
    window_end         TEXT,
    n                  INTEGER NOT NULL,
    win_rate           REAL,
    price_implied_rate REAL,
    calibration_edge   REAL,
    mean_claimed_edge  REAL,
    realization        REAL,
    roi_all            REAL,
    roi_taken          REAL,
    computed_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id            TEXT PRIMARY KEY,
    theory_id         TEXT NOT NULL REFERENCES theories(id),
    theory_version    INTEGER NOT NULL,
    as_of_start       TEXT,
    as_of_end         TEXT,
    tier              TEXT CHECK (tier IN ('A','B','C')),
    uses_llm_judgment INTEGER,
    model_cutoff      TEXT,
    notes             TEXT,
    created_at        TEXT NOT NULL
);
```

- [ ] **Step 3: Write the failing test**

Create `tests/__init__.py` (empty) and `tools/__init__.py` (empty), then `tests/test_db.py`:

```python
import sqlite3

import pytest

from tools import db


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def test_all_tables_created(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in rows}
    expected = {
        "theories",
        "market_snapshots",
        "opportunities",
        "settlements",
        "scores",
        "backtest_runs",
    }
    assert expected <= names


def test_init_db_is_idempotent(conn):
    db.init_db(conn)
    db.init_db(conn)
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table'"
    ).fetchone()["n"]
    assert count >= 6


def test_foreign_keys_are_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO opportunities ("
            " theory_id, theory_version, run_mode, run_id, kalshi_ticker,"
            " outcome, entry_price, screen_edge_pts_net, edge_pts_net,"
            " first_seen_at, last_seen_at"
            ") VALUES ('nonexistent', 1, 'live', 'live', 'TICK', 'yes',"
            " 0.5, 1.0, 1.0, '2026-08-23T00:00:00Z', '2026-08-23T00:00:00Z')"
        )
        conn.commit()


def test_rows_are_accessible_by_column_name(conn):
    conn.execute(
        "INSERT INTO theories (id, name, version, status, path,"
        " created_at, updated_at)"
        " VALUES ('t1', 'Test', 1, 'proposed', 'theories/t1',"
        " '2026-08-23T00:00:00Z', '2026-08-23T00:00:00Z')"
    )
    row = conn.execute("SELECT * FROM theories WHERE id='t1'").fetchone()
    assert row["name"] == "Test"


def test_utcnow_format():
    stamp = db.utcnow()
    assert stamp.endswith("Z")
    assert len(stamp) == 20
    assert stamp[4] == "-" and stamp[10] == "T"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.db'`

- [ ] **Step 5: Write `tools/db.py`**

```python
"""SQLite connection and schema management for the market edge finder.

Every connection enforces foreign keys and returns dict-like rows.
All timestamps produced here are UTC ISO-8601 with a trailing Z.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"
DEFAULT_DB_PATH = REPO_ROOT / "db" / "market_edge.db"


def utcnow() -> str:
    """Current UTC time as an ISO-8601 string, e.g. 2026-08-23T17:30:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and named row access."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create any missing tables. Safe to call repeatedly."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_db.py -v`
Expected: PASS — 5 passed

- [ ] **Step 7: Commit**

```bash
git add .gitignore db/schema.sql tools/__init__.py tools/db.py tests/__init__.py tests/test_db.py
git commit -m "feat: add SQLite schema and connection layer"
```

---

### Task 2: Fee model and position sizing

**Files:**
- Create: `tools/sizing.py`
- Create: `tests/test_sizing.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `tools.sizing.fee_pts(price: float) -> float` — per-contract fee in percentage points
  - `tools.sizing.order_fee_dollars(price: float, contracts: int) -> float` — actual charged fee, rounded up to the cent
  - `tools.sizing.net_edge_pts(model_prob: float, entry_price: float) -> float` — the `edge_pts_net` value the ledger requires
  - `tools.sizing.kelly_stake(model_prob: float, entry_price: float, fraction: float = 0.25, max_stake: float = 0.10) -> float` — bankroll fraction
  - `tools.sizing.blend_q(model_prob: float, market_mid: float, shrink: float = 0.5, max_edge_pts: float = 10.0, prob_cap: float = 0.985) -> float`
  - Constants: `FEE_RATE = 0.07`, `FEE_CAP_DOLLARS = 0.035`, `KELLY_FRACTION = 0.25`, `MAX_STAKE_FRACTION = 0.10`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sizing.py`:

```python
import pytest

from tools import sizing


def test_fee_pts_is_maximal_at_fifty_cents():
    # 0.07 * 0.5 * 0.5 = 0.0175 dollars = 1.75 points
    assert sizing.fee_pts(0.50) == pytest.approx(1.75)


def test_fee_pts_is_smaller_at_the_extremes():
    assert sizing.fee_pts(0.10) == pytest.approx(0.63, abs=0.01)
    assert sizing.fee_pts(0.95) == pytest.approx(0.3325, abs=0.001)


def test_fee_pts_respects_the_cap():
    # The cap is $0.035/contract = 3.5 points; the curve never exceeds
    # 1.75 points, so the cap is a safety rail, not an active limit.
    for price in (0.01, 0.25, 0.5, 0.75, 0.99):
        assert sizing.fee_pts(price) <= 3.5


def test_fee_pts_at_certainty_is_zero():
    assert sizing.fee_pts(0.0) == pytest.approx(0.0)
    assert sizing.fee_pts(1.0) == pytest.approx(0.0)


def test_order_fee_dollars_rounds_up_to_the_cent():
    # 1 contract at 0.50: 0.0175 -> rounds up to 0.02
    assert sizing.order_fee_dollars(0.50, 1) == pytest.approx(0.02)
    # 100 contracts at 0.50: 1.75 -> already whole cents
    assert sizing.order_fee_dollars(0.50, 100) == pytest.approx(1.75)


def test_net_edge_subtracts_the_fee():
    # model 0.60 vs price 0.50 = 10 points gross, minus 1.75 fee
    assert sizing.net_edge_pts(0.60, 0.50) == pytest.approx(8.25)


def test_net_edge_can_be_negative():
    assert sizing.net_edge_pts(0.50, 0.50) == pytest.approx(-1.75)


def test_kelly_stake_is_zero_without_edge():
    assert sizing.kelly_stake(0.50, 0.50) == 0.0
    assert sizing.kelly_stake(0.40, 0.50) == 0.0


def test_kelly_stake_is_positive_with_edge():
    stake = sizing.kelly_stake(0.70, 0.50)
    assert 0.0 < stake <= 0.10


def test_kelly_stake_respects_max_stake():
    # A huge edge must still be capped.
    assert sizing.kelly_stake(0.99, 0.10) == pytest.approx(0.10)


def test_kelly_stake_handles_price_at_one():
    assert sizing.kelly_stake(0.99, 1.0) == 0.0


def test_blend_q_shrinks_halfway_toward_the_market():
    # model 0.70, mid 0.50, 50% shrink -> 0.60
    assert sizing.blend_q(0.70, 0.50) == pytest.approx(0.60)


def test_blend_q_caps_claimed_edge():
    # model 0.99 vs mid 0.50 would blend to 0.745, but edge caps at 10 points
    assert sizing.blend_q(0.99, 0.50) == pytest.approx(0.60)


def test_blend_q_caps_probability():
    assert sizing.blend_q(1.0, 0.99) <= 0.985
    assert sizing.blend_q(0.0, 0.01) >= 0.015


def test_blend_q_works_downward():
    # model 0.30, mid 0.50 -> 0.40
    assert sizing.blend_q(0.30, 0.50) == pytest.approx(0.40)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sizing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.sizing'`

- [ ] **Step 3: Write `tools/sizing.py`**

```python
"""Kalshi fee model and position sizing.

Fee model verified against Kalshi's published schedule on 2026-08-23:
per-contract fee is 0.07 * P * (1-P) dollars, capped at $0.035, and an
actual order's total fee rounds UP to the whole cent.

Two fee functions exist on purpose. `fee_pts` is the unrounded per-contract
rate in percentage points, used for edge math at screen time when the
contract count is not yet known. `order_fee_dollars` is what an order is
actually charged.
"""

from __future__ import annotations

import math

FEE_RATE = 0.07
FEE_CAP_DOLLARS = 0.035
KELLY_FRACTION = 0.25
MAX_STAKE_FRACTION = 0.10


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def fee_pts(price: float) -> float:
    """Per-contract fee in percentage points for a contract at `price`."""
    p = _clamp(price, 0.0, 1.0)
    per_contract = min(FEE_RATE * p * (1.0 - p), FEE_CAP_DOLLARS)
    return per_contract * 100.0


def order_fee_dollars(price: float, contracts: int) -> float:
    """Total fee actually charged for an order, rounded up to the cent."""
    p = _clamp(price, 0.0, 1.0)
    per_contract = min(FEE_RATE * p * (1.0 - p), FEE_CAP_DOLLARS)
    return math.ceil(per_contract * contracts * 100.0) / 100.0


def net_edge_pts(model_prob: float, entry_price: float) -> float:
    """Edge in percentage points after fees, at an executable entry price."""
    gross = (model_prob - entry_price) * 100.0
    return gross - fee_pts(entry_price)


def kelly_stake(
    model_prob: float,
    entry_price: float,
    fraction: float = KELLY_FRACTION,
    max_stake: float = MAX_STAKE_FRACTION,
) -> float:
    """Fractional-Kelly bankroll fraction for a binary contract.

    A contract costing p pays 1 on a win, so full Kelly is (q - p) / (1 - p).
    The fee is folded into an effective price.
    """
    p_eff = entry_price + min(
        FEE_RATE * entry_price * (1.0 - entry_price), FEE_CAP_DOLLARS
    )
    if p_eff >= 1.0:
        return 0.0
    full = (model_prob - p_eff) / (1.0 - p_eff)
    if full <= 0.0:
        return 0.0
    return min(full * fraction, max_stake)


def blend_q(
    model_prob: float,
    market_mid: float,
    shrink: float = 0.5,
    max_edge_pts: float = 10.0,
    prob_cap: float = 0.985,
) -> float:
    """Shrink a model probability toward the market and cap claimed edge.

    Ported from kalshi_trader. A model that disagrees wildly with a liquid
    market is usually wrong, so claimed edge is bounded in both directions.
    """
    blended = market_mid + (model_prob - market_mid) * (1.0 - shrink)
    max_edge = max_edge_pts / 100.0
    blended = _clamp(blended, market_mid - max_edge, market_mid + max_edge)
    return _clamp(blended, 1.0 - prob_cap, prob_cap)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sizing.py -v`
Expected: PASS — 15 passed

- [ ] **Step 5: Commit**

```bash
git add tools/sizing.py tests/test_sizing.py
git commit -m "feat: add Kalshi fee model and Kelly sizing"
```

---

### Task 3: Credibility-weighted ranking

Implements spec section 8. This is the module that stops a confident brand-new theory from outranking a proven one.

**Files:**
- Create: `tools/rank.py`
- Create: `tests/test_rank.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `tools.rank.realization(calibration_edge: float | None, mean_claimed_edge: float | None) -> float`
  - `tools.rank.credibility(n: int, calibration_edge: float | None = None, mean_claimed_edge: float | None = None) -> float`
  - `tools.rank.ranked_edge(edge_pts_net: float, n: int, calibration_edge: float | None = None, mean_claimed_edge: float | None = None) -> float`
  - Constants: `PROBATION_N = 10`, `PROBATION_CREDIBILITY = 0.25`, `SHRINK_DENOM = 20`, `REALIZATION_CLAMP = 1.5`

- [ ] **Step 1: Write the failing test**

Create `tests/test_rank.py`:

```python
import pytest

from tools import rank


def test_untested_theory_gets_the_probation_floor():
    assert rank.credibility(0) == pytest.approx(0.25)
    assert rank.credibility(9) == pytest.approx(0.25)


def test_new_theory_edge_is_shrunk_but_visible():
    # 12 claimed points at the 0.25 floor -> 3.0
    assert rank.ranked_edge(12.0, n=0) == pytest.approx(3.0)


def test_proven_theory_that_delivers_gets_high_credibility():
    # n=40, realized exactly what it claimed -> 40/60 * 1.0
    cred = rank.credibility(40, calibration_edge=6.0, mean_claimed_edge=6.0)
    assert cred == pytest.approx(40 / 60)


def test_proven_theory_ranks_a_six_point_claim_near_four():
    ranked = rank.ranked_edge(
        6.0, n=40, calibration_edge=6.0, mean_claimed_edge=6.0
    )
    assert ranked == pytest.approx(4.0, abs=0.01)


def test_disproven_theory_sinks_below_the_floor():
    # This is the case the floor must NOT protect: measured and found wanting.
    cred = rank.credibility(40, calibration_edge=0.0, mean_claimed_edge=8.0)
    assert cred == pytest.approx(0.0)
    assert rank.ranked_edge(
        10.0, n=40, calibration_edge=0.0, mean_claimed_edge=8.0
    ) == pytest.approx(0.0)


def test_negative_calibration_clamps_to_zero_not_negative():
    cred = rank.credibility(40, calibration_edge=-5.0, mean_claimed_edge=8.0)
    assert cred == pytest.approx(0.0)


def test_overdelivering_theory_is_boosted_but_bounded():
    # Realized 3x its claim, but realization clamps at 1.5
    assert rank.realization(24.0, 8.0) == pytest.approx(1.5)


def test_realization_defaults_to_one_without_measurement():
    assert rank.realization(None, None) == pytest.approx(1.0)
    assert rank.realization(5.0, None) == pytest.approx(1.0)


def test_realization_handles_zero_or_negative_claimed_edge():
    # Avoid divide-by-zero; an unclaimed edge cannot be under- or over-realized.
    assert rank.realization(3.0, 0.0) == pytest.approx(1.0)
    assert rank.realization(3.0, -2.0) == pytest.approx(1.0)


def test_new_theory_can_beat_a_weak_proven_suggestion():
    new = rank.ranked_edge(12.0, n=0)
    proven_weak = rank.ranked_edge(
        2.0, n=40, calibration_edge=6.0, mean_claimed_edge=6.0
    )
    assert new > proven_weak


def test_new_theory_cannot_beat_a_strong_proven_suggestion():
    new = rank.ranked_edge(12.0, n=0)
    proven_strong = rank.ranked_edge(
        8.0, n=40, calibration_edge=8.0, mean_claimed_edge=8.0
    )
    assert proven_strong > new


def test_credibility_grows_with_sample_size():
    small = rank.credibility(10, calibration_edge=5.0, mean_claimed_edge=5.0)
    large = rank.credibility(100, calibration_edge=5.0, mean_claimed_edge=5.0)
    assert large > small
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rank.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.rank'`

- [ ] **Step 3: Write `tools/rank.py`**

```python
"""Credibility-weighted ranking (spec section 8).

A theory's claimed edge is shrunk toward what it has actually demonstrated.
Below PROBATION_N settled bets a fixed floor applies so untested ideas stay
visible without dominating; at or above it the floor is withdrawn, so a
theory that has been measured and found wanting sinks to zero rather than
resting on newcomer protection.

All edge values are in percentage points, including calibration_edge.
"""

from __future__ import annotations

PROBATION_N = 10
PROBATION_CREDIBILITY = 0.25
SHRINK_DENOM = 20
REALIZATION_CLAMP = 1.5


def realization(
    calibration_edge: float | None,
    mean_claimed_edge: float | None,
) -> float:
    """How much of its claimed edge a theory actually delivered.

    Returns 1.0 (neutral) when there is nothing to measure against.
    """
    if calibration_edge is None:
        return 1.0
    if mean_claimed_edge is None or mean_claimed_edge <= 0.0:
        return 1.0
    ratio = calibration_edge / mean_claimed_edge
    return max(0.0, min(ratio, REALIZATION_CLAMP))


def credibility(
    n: int,
    calibration_edge: float | None = None,
    mean_claimed_edge: float | None = None,
) -> float:
    """Weight in [0, 1.5] to apply to a theory's claimed edge."""
    if n < PROBATION_N:
        return PROBATION_CREDIBILITY
    sample_weight = n / (n + SHRINK_DENOM)
    return sample_weight * realization(calibration_edge, mean_claimed_edge)


def ranked_edge(
    edge_pts_net: float,
    n: int,
    calibration_edge: float | None = None,
    mean_claimed_edge: float | None = None,
) -> float:
    """The number find-edge sorts on."""
    return edge_pts_net * credibility(n, calibration_edge, mean_claimed_edge)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rank.py -v`
Expected: PASS — 12 passed

- [ ] **Step 5: Commit**

```bash
git add tools/rank.py tests/test_rank.py
git commit -m "feat: add credibility-weighted ranking"
```

---

### Task 4: Theory registry

**Files:**
- Create: `tools/theories.py`
- Create: `tests/test_theories.py`

**Interfaces:**
- Consumes: `tools.db.connect`, `tools.db.utcnow`
- Produces:
  - `tools.theories.register(conn, theory_id: str, name: str, path: str, status: str = "proposed", now: str | None = None) -> None`
  - `tools.theories.get(conn, theory_id: str) -> sqlite3.Row | None`
  - `tools.theories.list_theories(conn, status: str | None = None) -> list[sqlite3.Row]`
  - `tools.theories.set_status(conn, theory_id: str, status: str, now: str | None = None) -> None`
  - `tools.theories.bump_version(conn, theory_id: str, now: str | None = None) -> int` — returns the new version
  - `tools.theories.VALID_STATUSES: tuple[str, ...]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_theories.py`:

```python
import pytest

from tools import db, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def test_register_creates_a_theory_at_version_one(conn):
    theories.register(conn, "insider_bias", "Insider Bias",
                      "theories/insider_bias", now=TS)
    row = theories.get(conn, "insider_bias")
    assert row["name"] == "Insider Bias"
    assert row["version"] == 1
    assert row["status"] == "proposed"
    assert row["created_at"] == TS


def test_get_returns_none_for_unknown_theory(conn):
    assert theories.get(conn, "nope") is None


def test_register_is_idempotent(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.register(conn, "t1", "One Renamed", "theories/t1", now=TS)
    assert theories.get(conn, "t1")["name"] == "One Renamed"
    assert len(theories.list_theories(conn)) == 1


def test_register_does_not_reset_version(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.bump_version(conn, "t1", now=TS)
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    assert theories.get(conn, "t1")["version"] == 2


def test_set_status_updates_status_and_timestamp(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.set_status(conn, "t1", "active", now="2026-08-24T00:00:00Z")
    row = theories.get(conn, "t1")
    assert row["status"] == "active"
    assert row["updated_at"] == "2026-08-24T00:00:00Z"


def test_set_status_rejects_invalid_status(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    with pytest.raises(ValueError):
        theories.set_status(conn, "t1", "banana")


def test_bump_version_increments_and_returns(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    assert theories.bump_version(conn, "t1", now=TS) == 2
    assert theories.bump_version(conn, "t1", now=TS) == 3
    assert theories.get(conn, "t1")["version"] == 3


def test_bump_version_rejects_unknown_theory(conn):
    with pytest.raises(KeyError):
        theories.bump_version(conn, "nope")


def test_list_filters_by_status(conn):
    theories.register(conn, "a", "A", "theories/a", status="active", now=TS)
    theories.register(conn, "b", "B", "theories/b", status="retired", now=TS)
    active = theories.list_theories(conn, status="active")
    assert [r["id"] for r in active] == ["a"]
    assert len(theories.list_theories(conn)) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_theories.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.theories'`

- [ ] **Step 3: Write `tools/theories.py`**

```python
"""Theory registry (spec sections 5, 10, 11).

This table is an index, not the source of truth. A theory's hypothesis and
procedure live in its THEORY.md; what lives here is enough to discover
theories programmatically and to track lifecycle state and version.

Version matters: any change to a theory's decision procedure must bump it,
so that scoring can segment on it and a mid-stream change cannot silently
merge two different theories into one track record.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow

VALID_STATUSES = ("proposed", "active", "paused", "retired")


def register(
    conn: sqlite3.Connection,
    theory_id: str,
    name: str,
    path: str,
    status: str = "proposed",
    now: str | None = None,
) -> None:
    """Create or update a theory's registry entry. Never resets version."""
    if status not in VALID_STATUSES:
        raise ValueError(
            f"invalid status {status!r}; expected one of {VALID_STATUSES}"
        )
    stamp = now or utcnow()
    conn.execute(
        """
        INSERT INTO theories (id, name, version, status, path,
                              created_at, updated_at)
        VALUES (?, ?, 1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            path = excluded.path,
            updated_at = excluded.updated_at
        """,
        (theory_id, name, status, path, stamp, stamp),
    )
    conn.commit()


def get(conn: sqlite3.Connection, theory_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM theories WHERE id = ?", (theory_id,)
    ).fetchone()


def list_theories(
    conn: sqlite3.Connection, status: str | None = None
) -> list[sqlite3.Row]:
    if status is None:
        return conn.execute("SELECT * FROM theories ORDER BY id").fetchall()
    return conn.execute(
        "SELECT * FROM theories WHERE status = ? ORDER BY id", (status,)
    ).fetchall()


def set_status(
    conn: sqlite3.Connection,
    theory_id: str,
    status: str,
    now: str | None = None,
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(
            f"invalid status {status!r}; expected one of {VALID_STATUSES}"
        )
    if get(conn, theory_id) is None:
        raise KeyError(theory_id)
    conn.execute(
        "UPDATE theories SET status = ?, updated_at = ? WHERE id = ?",
        (status, now or utcnow(), theory_id),
    )
    conn.commit()


def bump_version(
    conn: sqlite3.Connection, theory_id: str, now: str | None = None
) -> int:
    """Increment the theory's version and return the new value."""
    row = get(conn, theory_id)
    if row is None:
        raise KeyError(theory_id)
    new_version = row["version"] + 1
    conn.execute(
        "UPDATE theories SET version = ?, updated_at = ? WHERE id = ?",
        (new_version, now or utcnow(), theory_id),
    )
    conn.commit()
    return new_version
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_theories.py -v`
Expected: PASS — 9 passed

- [ ] **Step 5: Commit**

```bash
git add tools/theories.py tests/test_theories.py
git commit -m "feat: add theory registry with versioning"
```

---

### Task 5: `record_opportunity` — the shared contract

Implements spec section 6. The upsert semantics here are the fix for the duplicate-recommendation bug that would otherwise corrupt all calibration scoring.

**Files:**
- Create: `tools/ledger.py`
- Create: `tests/test_ledger.py`

**Interfaces:**
- Consumes: `tools.db.utcnow`, `tools.theories`
- Produces:
  - `tools.ledger.record_opportunity(conn, *, theory_id, theory_version, kalshi_ticker, outcome, entry_price, edge_pts_net, run_mode="live", run_id=None, scan_id=None, spread_at_call=None, volume_at_call=None, model_prob=None, edge_pts_gross=None, fee_pts=None, confidence=None, rationale=None, suggested_size=None, evidence_source=None, evidence_market_id=None, extra_json=None, now=None) -> tuple[int, bool]` — returns `(opportunity_id, was_created)`
  - `tools.ledger.get_opportunity(conn, opportunity_id: int) -> sqlite3.Row | None`
  - `tools.ledger.list_opportunities(conn, theory_id=None, run_mode=None, disposition=None) -> list[sqlite3.Row]`
  - `tools.ledger.LIVE_RUN_ID = "live"`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ledger.py`:

```python
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


def _record(conn, **overrides):
    kwargs = dict(
        theory_id="t1",
        theory_version=1,
        kalshi_ticker="KXTEST-26",
        outcome="yes",
        entry_price=0.40,
        edge_pts_net=6.0,
        rationale="looks mispriced",
        now=TS,
    )
    kwargs.update(overrides)
    return ledger.record_opportunity(conn, **kwargs)


def test_record_creates_a_row(conn):
    opp_id, created = _record(conn)
    assert created is True
    row = ledger.get_opportunity(conn, opp_id)
    assert row["kalshi_ticker"] == "KXTEST-26"
    assert row["entry_price"] == pytest.approx(0.40)
    assert row["times_seen"] == 1
    assert row["disposition"] == "screened"
    assert row["user_action"] == "untouched"
    assert row["run_id"] == "live"


def test_screen_edge_is_frozen_at_record_time(conn):
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    row = ledger.get_opportunity(conn, opp_id)
    assert row["screen_edge_pts_net"] == pytest.approx(6.0)
    assert row["edge_pts_net"] == pytest.approx(6.0)


def test_resighting_updates_instead_of_duplicating(conn):
    first_id, first_created = _record(conn)
    second_id, second_created = _record(conn, now=LATER, edge_pts_net=7.5)

    assert second_created is False
    assert second_id == first_id
    assert len(ledger.list_opportunities(conn)) == 1


def test_resighting_preserves_the_original_entry(conn):
    opp_id, _ = _record(conn, entry_price=0.40)
    _record(conn, entry_price=0.55, now=LATER)

    row = ledger.get_opportunity(conn, opp_id)
    assert row["entry_price"] == pytest.approx(0.40), "entry must not drift"
    assert row["first_seen_at"] == TS
    assert row["last_seen_at"] == LATER
    assert row["times_seen"] == 2


def test_resighting_preserves_the_frozen_screen_edge(conn):
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    _record(conn, edge_pts_net=9.0, now=LATER)

    row = ledger.get_opportunity(conn, opp_id)
    assert row["screen_edge_pts_net"] == pytest.approx(6.0)
    assert row["edge_pts_net"] == pytest.approx(9.0), "current edge refreshes"


def test_different_outcome_is_a_different_opportunity(conn):
    _record(conn, outcome="yes")
    _record(conn, outcome="no")
    assert len(ledger.list_opportunities(conn)) == 2


def test_different_theory_version_is_a_different_opportunity(conn):
    _record(conn, theory_version=1)
    _record(conn, theory_version=2)
    assert len(ledger.list_opportunities(conn)) == 2


def test_backtest_runs_are_deduped_per_run(conn):
    _record(conn, run_mode="backtest", run_id="run-a")
    _record(conn, run_mode="backtest", run_id="run-a")
    _record(conn, run_mode="backtest", run_id="run-b")
    assert len(ledger.list_opportunities(conn, run_mode="backtest")) == 2


def test_missing_kalshi_ticker_is_rejected(conn):
    with pytest.raises(ValueError, match="kalshi_ticker"):
        _record(conn, kalshi_ticker="")
    with pytest.raises(ValueError, match="kalshi_ticker"):
        _record(conn, kalshi_ticker=None)


def test_missing_edge_is_rejected(conn):
    with pytest.raises(ValueError, match="edge_pts_net"):
        _record(conn, edge_pts_net=None)


def test_backtest_without_run_id_is_rejected(conn):
    with pytest.raises(ValueError, match="run_id"):
        _record(conn, run_mode="backtest", run_id=None)


def test_polymarket_evidence_is_recorded_against_a_kalshi_ticker(conn):
    opp_id, _ = _record(
        conn,
        evidence_source="polymarket",
        evidence_market_id="0xabc123",
    )
    row = ledger.get_opportunity(conn, opp_id)
    assert row["kalshi_ticker"] == "KXTEST-26"
    assert row["evidence_source"] == "polymarket"
    assert row["evidence_market_id"] == "0xabc123"


def test_list_filters_by_theory_and_disposition(conn):
    _record(conn, kalshi_ticker="A")
    _record(conn, kalshi_ticker="B")
    assert len(ledger.list_opportunities(conn, theory_id="t1")) == 2
    assert len(ledger.list_opportunities(conn, theory_id="other")) == 0
    assert len(ledger.list_opportunities(conn, disposition="screened")) == 2
    assert len(ledger.list_opportunities(conn, disposition="endorsed")) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ledger.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.ledger'`

- [ ] **Step 3: Write `tools/ledger.py`**

```python
"""The opportunity contract (spec section 6).

Every theory, however it works internally, ends by calling
record_opportunity. Two rules are enforced here rather than in prose:

1. Every suggestion must be tradeable on Kalshi. A Polymarket-sourced
   finding keeps its provenance in evidence_source/evidence_market_id but
   still requires a kalshi_ticker.

2. Re-sighting the same thesis updates the existing row rather than
   inserting a new one. A market that stays mispriced for a week is one
   bet seen seven times, not seven bets. entry_price and first_seen_at
   preserve the entry actually available at first sighting, so scoring
   measures a real position rather than an average of repeated looks.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow

LIVE_RUN_ID = "live"


def record_opportunity(
    conn: sqlite3.Connection,
    *,
    theory_id: str,
    theory_version: int,
    kalshi_ticker: str,
    outcome: str,
    entry_price: float,
    edge_pts_net: float,
    run_mode: str = "live",
    run_id: str | None = None,
    scan_id: str | None = None,
    spread_at_call: float | None = None,
    volume_at_call: float | None = None,
    model_prob: float | None = None,
    edge_pts_gross: float | None = None,
    fee_pts: float | None = None,
    confidence: str | None = None,
    rationale: str | None = None,
    suggested_size: float | None = None,
    evidence_source: str | None = None,
    evidence_market_id: str | None = None,
    extra_json: str | None = None,
    now: str | None = None,
) -> tuple[int, bool]:
    """Record or refresh an opportunity. Returns (id, was_created)."""
    if not kalshi_ticker:
        raise ValueError(
            "kalshi_ticker is required: every suggestion must resolve to a "
            "tradeable Kalshi market"
        )
    if edge_pts_net is None:
        raise ValueError(
            "edge_pts_net is required: it is the common currency used to "
            "rank across theories"
        )
    if run_mode not in ("live", "backtest"):
        raise ValueError(f"invalid run_mode {run_mode!r}")
    if run_mode == "backtest" and not run_id:
        raise ValueError("run_id is required for backtest runs")

    resolved_run_id = run_id or LIVE_RUN_ID
    stamp = now or utcnow()

    existing = conn.execute(
        """
        SELECT id FROM opportunities
        WHERE theory_id = ? AND theory_version = ? AND run_id = ?
          AND kalshi_ticker = ? AND outcome = ?
        """,
        (theory_id, theory_version, resolved_run_id, kalshi_ticker, outcome),
    ).fetchone()

    if existing is not None:
        conn.execute(
            """
            UPDATE opportunities SET
                last_seen_at = ?,
                times_seen = times_seen + 1,
                edge_pts_net = ?,
                model_prob = COALESCE(?, model_prob),
                edge_pts_gross = COALESCE(?, edge_pts_gross),
                fee_pts = COALESCE(?, fee_pts),
                spread_at_call = COALESCE(?, spread_at_call),
                volume_at_call = COALESCE(?, volume_at_call),
                confidence = COALESCE(?, confidence),
                rationale = COALESCE(?, rationale),
                suggested_size = COALESCE(?, suggested_size)
            WHERE id = ?
            """,
            (
                stamp,
                edge_pts_net,
                model_prob,
                edge_pts_gross,
                fee_pts,
                spread_at_call,
                volume_at_call,
                confidence,
                rationale,
                suggested_size,
                existing["id"],
            ),
        )
        conn.commit()
        return existing["id"], False

    cursor = conn.execute(
        """
        INSERT INTO opportunities (
            theory_id, theory_version, run_mode, run_id, scan_id,
            kalshi_ticker, outcome, entry_price, spread_at_call,
            volume_at_call, model_prob, edge_pts_gross, fee_pts,
            screen_edge_pts_net, edge_pts_net, disposition, confidence,
            rationale, suggested_size, evidence_source, evidence_market_id,
            user_action, first_seen_at, last_seen_at, times_seen, extra_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  'screened', ?, ?, ?, ?, ?, 'untouched', ?, ?, 1, ?)
        """,
        (
            theory_id,
            theory_version,
            run_mode,
            resolved_run_id,
            scan_id,
            kalshi_ticker,
            outcome,
            entry_price,
            spread_at_call,
            volume_at_call,
            model_prob,
            edge_pts_gross,
            fee_pts,
            edge_pts_net,
            edge_pts_net,
            confidence,
            rationale,
            suggested_size,
            evidence_source,
            evidence_market_id,
            stamp,
            stamp,
            extra_json,
        ),
    )
    conn.commit()
    return cursor.lastrowid, True


def get_opportunity(
    conn: sqlite3.Connection, opportunity_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)
    ).fetchone()


def list_opportunities(
    conn: sqlite3.Connection,
    theory_id: str | None = None,
    run_mode: str | None = None,
    disposition: str | None = None,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[object] = []
    if theory_id is not None:
        clauses.append("theory_id = ?")
        params.append(theory_id)
    if run_mode is not None:
        clauses.append("run_mode = ?")
        params.append(run_mode)
    if disposition is not None:
        clauses.append("disposition = ?")
        params.append(disposition)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return conn.execute(
        f"SELECT * FROM opportunities{where} ORDER BY id", params
    ).fetchall()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ledger.py -v`
Expected: PASS — 13 passed

- [ ] **Step 5: Commit**

```bash
git add tools/ledger.py tests/test_ledger.py
git commit -m "feat: add record_opportunity with upsert dedup semantics"
```

---

### Task 6: Interpretation and user action

Implements the stage-2 half of spec section 7. `interpret` is how Claude's research verdict gets recorded; recording rejections is what makes the value of interpretation measurable later.

**Files:**
- Modify: `tools/ledger.py` (append functions)
- Modify: `tests/test_ledger.py` (append tests)

**Interfaces:**
- Consumes: everything from Task 5
- Produces:
  - `tools.ledger.interpret(conn, opportunity_id: int, disposition: str, interpretation: str, revised_edge_pts_net: float | None = None, now: str | None = None) -> None`
  - `tools.ledger.mark_user_action(conn, opportunity_id: int, action: str, size: float | None = None, reason: str | None = None) -> None`
  - `tools.ledger.VALID_DISPOSITIONS: tuple[str, ...]`
  - `tools.ledger.VALID_USER_ACTIONS: tuple[str, ...]`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ledger.py`:

```python
def test_interpret_endorses_an_opportunity(conn):
    opp_id, _ = _record(conn)
    ledger.interpret(
        conn, opp_id, "endorsed",
        "Reality TV market; resolution language is unusually loose.",
        now=LATER,
    )
    row = ledger.get_opportunity(conn, opp_id)
    assert row["disposition"] == "endorsed"
    assert "Reality TV" in row["interpretation"]
    assert row["interpreted_at"] == LATER


def test_interpret_rejects_and_keeps_the_row_as_a_control(conn):
    opp_id, _ = _record(conn)
    ledger.interpret(conn, opp_id, "rejected", "Resolution requires an "
                     "official source that rarely publishes in time.")
    row = ledger.get_opportunity(conn, opp_id)
    assert row["disposition"] == "rejected"
    # The row must survive: rejected candidates are the control group.
    assert len(ledger.list_opportunities(conn)) == 1


def test_interpret_can_revise_the_edge_without_touching_the_screen_edge(conn):
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    ledger.interpret(conn, opp_id, "endorsed", "Stronger than the screen "
                     "thought.", revised_edge_pts_net=9.0)
    row = ledger.get_opportunity(conn, opp_id)
    assert row["edge_pts_net"] == pytest.approx(9.0)
    assert row["screen_edge_pts_net"] == pytest.approx(6.0)


def test_interpret_without_revision_leaves_edge_alone(conn):
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    ledger.interpret(conn, opp_id, "endorsed", "Confirmed as screened.")
    row = ledger.get_opportunity(conn, opp_id)
    assert row["edge_pts_net"] == pytest.approx(6.0)


def test_interpret_rejects_invalid_disposition(conn):
    opp_id, _ = _record(conn)
    with pytest.raises(ValueError):
        ledger.interpret(conn, opp_id, "maybe", "hmm")


def test_interpret_rejects_unknown_opportunity(conn):
    with pytest.raises(KeyError):
        ledger.interpret(conn, 9999, "endorsed", "nope")


def test_mark_user_action_records_a_taken_bet(conn):
    opp_id, _ = _record(conn)
    ledger.mark_user_action(conn, opp_id, "taken", size=25.0,
                            reason="reality TV markets are soft")
    row = ledger.get_opportunity(conn, opp_id)
    assert row["user_action"] == "taken"
    assert row["user_size"] == pytest.approx(25.0)
    assert row["user_reason"] == "reality TV markets are soft"


def test_mark_user_action_records_a_skip_with_reason(conn):
    opp_id, _ = _record(conn)
    ledger.mark_user_action(conn, opp_id, "skipped", reason="too illiquid")
    row = ledger.get_opportunity(conn, opp_id)
    assert row["user_action"] == "skipped"
    assert row["user_reason"] == "too illiquid"


def test_mark_user_action_rejects_invalid_action(conn):
    opp_id, _ = _record(conn)
    with pytest.raises(ValueError):
        ledger.mark_user_action(conn, opp_id, "pondered")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ledger.py -v`
Expected: FAIL — `AttributeError: module 'tools.ledger' has no attribute 'interpret'`

- [ ] **Step 3: Append to `tools/ledger.py`**

Add these constants directly below `LIVE_RUN_ID = "live"`:

```python
VALID_DISPOSITIONS = ("screened", "endorsed", "rejected")
VALID_USER_ACTIONS = ("untouched", "taken", "skipped")
```

Then append these functions to the end of the file:

```python
def interpret(
    conn: sqlite3.Connection,
    opportunity_id: int,
    disposition: str,
    interpretation: str,
    revised_edge_pts_net: float | None = None,
    now: str | None = None,
) -> None:
    """Record a stage-2 research verdict (spec section 7).

    Rejections are recorded, not deleted: they are the control group that
    makes the value of interpretation measurable. `screen_edge_pts_net` is
    never touched here, so a revised edge stays comparable to what the
    mechanical screen originally claimed.
    """
    if disposition not in VALID_DISPOSITIONS:
        raise ValueError(
            f"invalid disposition {disposition!r}; "
            f"expected one of {VALID_DISPOSITIONS}"
        )
    if get_opportunity(conn, opportunity_id) is None:
        raise KeyError(opportunity_id)

    stamp = now or utcnow()
    if revised_edge_pts_net is None:
        conn.execute(
            """
            UPDATE opportunities
            SET disposition = ?, interpretation = ?, interpreted_at = ?
            WHERE id = ?
            """,
            (disposition, interpretation, stamp, opportunity_id),
        )
    else:
        conn.execute(
            """
            UPDATE opportunities
            SET disposition = ?, interpretation = ?, interpreted_at = ?,
                edge_pts_net = ?
            WHERE id = ?
            """,
            (
                disposition,
                interpretation,
                stamp,
                revised_edge_pts_net,
                opportunity_id,
            ),
        )
    conn.commit()


def mark_user_action(
    conn: sqlite3.Connection,
    opportunity_id: int,
    action: str,
    size: float | None = None,
    reason: str | None = None,
) -> None:
    """Record what the user actually did (spec sections 6 and 7).

    The reason matters: divergence between what the system endorsed and what
    the user bet is usually an unencoded heuristic, and those get mined into
    new theory candidates.
    """
    if action not in VALID_USER_ACTIONS:
        raise ValueError(
            f"invalid action {action!r}; expected one of {VALID_USER_ACTIONS}"
        )
    if get_opportunity(conn, opportunity_id) is None:
        raise KeyError(opportunity_id)
    conn.execute(
        """
        UPDATE opportunities
        SET user_action = ?, user_size = ?, user_reason = ?
        WHERE id = ?
        """,
        (action, size, reason, opportunity_id),
    )
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ledger.py -v`
Expected: PASS — 22 passed

- [ ] **Step 5: Commit**

```bash
git add tools/ledger.py tests/test_ledger.py
git commit -m "feat: add interpretation and user-action recording"
```

---

### Task 7: Settlement and scoring

Implements spec sections 5 and 7. The disposition split is what answers "does interpretation earn its keep."

**Files:**
- Create: `tools/score.py`
- Create: `tests/test_score.py`

**Interfaces:**
- Consumes: `tools.db.utcnow`, `tools.rank.realization`, `tools.sizing.fee_pts`
- Produces:
  - `tools.score.record_settlement(conn, kalshi_ticker: str, result: str, resolved_at: str | None = None, settle_price: float | None = None) -> None`
  - `tools.score.compute_score(conn, theory_id: str, theory_version: int, run_mode: str = "live", disposition: str = "all") -> dict` — returns a dict with keys `n`, `win_rate`, `price_implied_rate`, `calibration_edge`, `mean_claimed_edge`, `realization`, `roi_all`, `roi_taken`
  - `tools.score.save_score(conn, theory_id: str, theory_version: int, run_mode: str, disposition: str, result: dict, now: str | None = None) -> int`
  - `tools.score.interpretation_value(conn, theory_id: str, theory_version: int, run_mode: str = "live") -> dict` — returns `{"endorsed": {...}, "rejected": {...}, "delta": float | None}`

- [ ] **Step 1: Write the failing test**

Create `tests/test_score.py`:

```python
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


def _bet(conn, ticker, entry_price, edge, outcome="yes",
         disposition="screened"):
    opp_id, _ = ledger.record_opportunity(
        conn,
        theory_id="t1",
        theory_version=1,
        kalshi_ticker=ticker,
        outcome=outcome,
        entry_price=entry_price,
        edge_pts_net=edge,
        now=TS,
    )
    if disposition != "screened":
        ledger.interpret(conn, opp_id, disposition, "test", now=TS)
    return opp_id


def test_unsettled_opportunities_score_as_empty(conn):
    _bet(conn, "A", 0.50, 6.0)
    result = score.compute_score(conn, "t1", 1)
    assert result["n"] == 0
    assert result["win_rate"] is None


def test_win_rate_counts_matching_outcomes(conn):
    _bet(conn, "A", 0.50, 6.0, outcome="yes")
    _bet(conn, "B", 0.50, 6.0, outcome="yes")
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")

    result = score.compute_score(conn, "t1", 1)
    assert result["n"] == 2
    assert result["win_rate"] == pytest.approx(0.5)


def test_no_side_bets_win_when_market_resolves_no(conn):
    _bet(conn, "A", 0.30, 5.0, outcome="no")
    score.record_settlement(conn, "A", "no")
    result = score.compute_score(conn, "t1", 1)
    assert result["win_rate"] == pytest.approx(1.0)


def test_calibration_edge_is_in_points(conn):
    # Two bets at 0.50, one wins -> win_rate 0.50, implied 0.50, edge 0 points
    _bet(conn, "A", 0.50, 6.0)
    _bet(conn, "B", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")

    result = score.compute_score(conn, "t1", 1)
    assert result["price_implied_rate"] == pytest.approx(0.50)
    assert result["calibration_edge"] == pytest.approx(0.0)


def test_positive_calibration_edge(conn):
    # Four bets at 0.50, three win -> 75% vs 50% implied = 25 points
    for ticker in "ABCD":
        _bet(conn, ticker, 0.50, 6.0)
    for ticker in "ABC":
        score.record_settlement(conn, ticker, "yes")
    score.record_settlement(conn, "D", "no")

    result = score.compute_score(conn, "t1", 1)
    assert result["calibration_edge"] == pytest.approx(25.0)


def test_realization_compares_delivered_to_claimed(conn):
    # 25 points delivered against a 25 point claim -> realization 1.0
    for ticker in "ABCD":
        _bet(conn, ticker, 0.50, 25.0)
    for ticker in "ABC":
        score.record_settlement(conn, ticker, "yes")
    score.record_settlement(conn, "D", "no")

    result = score.compute_score(conn, "t1", 1)
    assert result["mean_claimed_edge"] == pytest.approx(25.0)
    assert result["realization"] == pytest.approx(1.0)


def test_roi_is_net_of_fees(conn):
    # One bet at 0.50 that wins. Cost = 0.50 + 0.0175 fee = 0.5175.
    # Return = 1.00. ROI = (1.00 - 0.5175) / 0.5175
    _bet(conn, "A", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes")
    result = score.compute_score(conn, "t1", 1)
    expected = (1.0 - 0.5175) / 0.5175
    assert result["roi_all"] == pytest.approx(expected, rel=1e-3)


def test_roi_taken_only_counts_taken_bets(conn):
    winner = _bet(conn, "A", 0.50, 6.0)
    _bet(conn, "B", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")
    ledger.mark_user_action(conn, winner, "taken", size=10.0)

    result = score.compute_score(conn, "t1", 1)
    assert result["roi_all"] < result["roi_taken"]
    assert result["roi_taken"] > 0


def test_roi_taken_is_none_when_nothing_was_taken(conn):
    _bet(conn, "A", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes")
    assert score.compute_score(conn, "t1", 1)["roi_taken"] is None


def test_disposition_filter_segments_the_sample(conn):
    _bet(conn, "A", 0.50, 6.0, disposition="endorsed")
    _bet(conn, "B", 0.50, 6.0, disposition="rejected")
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")

    assert score.compute_score(conn, "t1", 1, disposition="all")["n"] == 2
    endorsed = score.compute_score(conn, "t1", 1, disposition="endorsed")
    rejected = score.compute_score(conn, "t1", 1, disposition="rejected")
    assert endorsed["n"] == 1
    assert endorsed["win_rate"] == pytest.approx(1.0)
    assert rejected["win_rate"] == pytest.approx(0.0)


def test_interpretation_value_reports_the_delta(conn):
    # Endorsed picks win, rejected ones lose: interpretation is adding edge.
    for ticker in ("A", "B"):
        _bet(conn, ticker, 0.50, 6.0, disposition="endorsed")
        score.record_settlement(conn, ticker, "yes")
    for ticker in ("C", "D"):
        _bet(conn, ticker, 0.50, 6.0, disposition="rejected")
        score.record_settlement(conn, ticker, "no")

    value = score.interpretation_value(conn, "t1", 1)
    assert value["endorsed"]["win_rate"] == pytest.approx(1.0)
    assert value["rejected"]["win_rate"] == pytest.approx(0.0)
    assert value["delta"] == pytest.approx(100.0)


def test_interpretation_value_delta_is_none_without_a_control(conn):
    _bet(conn, "A", 0.50, 6.0, disposition="endorsed")
    score.record_settlement(conn, "A", "yes")
    assert score.interpretation_value(conn, "t1", 1)["delta"] is None


def test_scores_are_segmented_by_theory_version(conn):
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="A",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS,
    )
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=2, kalshi_ticker="B",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS,
    )
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")

    assert score.compute_score(conn, "t1", 1)["win_rate"] == pytest.approx(1.0)
    assert score.compute_score(conn, "t1", 2)["win_rate"] == pytest.approx(0.0)


def test_save_score_persists_a_row(conn):
    _bet(conn, "A", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes")
    result = score.compute_score(conn, "t1", 1)
    row_id = score.save_score(conn, "t1", 1, "live", "all", result, now=TS)

    saved = conn.execute(
        "SELECT * FROM scores WHERE id = ?", (row_id,)
    ).fetchone()
    assert saved["theory_id"] == "t1"
    assert saved["disposition"] == "all"
    assert saved["n"] == 1
    assert saved["computed_at"] == TS


def test_record_settlement_is_idempotent(conn):
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "A", "no")
    row = conn.execute(
        "SELECT * FROM settlements WHERE kalshi_ticker = 'A'"
    ).fetchone()
    assert row["result"] == "no"
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM settlements"
    ).fetchone()["n"]
    assert count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_score.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.score'`

- [ ] **Step 3: Write `tools/score.py`**

```python
"""Settlement recording and calibration scoring (spec sections 5 and 7).

The headline metric is calibration edge: realized win rate minus the
price-implied rate, in percentage points. It answers the only question that
matters about a theory — did markets it picked resolve in its favour more
often than their prices implied.

Scores are computed per (theory, version, run_mode, disposition). The
disposition split is what makes the value of stage-2 interpretation
measurable: endorsed versus rejected, with rejected candidates serving as a
free control group.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow
from tools.rank import realization as _realization
from tools.sizing import fee_pts

EMPTY_SCORE = {
    "n": 0,
    "win_rate": None,
    "price_implied_rate": None,
    "calibration_edge": None,
    "mean_claimed_edge": None,
    "realization": None,
    "roi_all": None,
    "roi_taken": None,
}


def record_settlement(
    conn: sqlite3.Connection,
    kalshi_ticker: str,
    result: str,
    resolved_at: str | None = None,
    settle_price: float | None = None,
) -> None:
    """Record how a Kalshi market resolved. Latest write wins."""
    conn.execute(
        """
        INSERT INTO settlements (kalshi_ticker, resolved_at, result,
                                 settle_price)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(kalshi_ticker) DO UPDATE SET
            resolved_at = excluded.resolved_at,
            result = excluded.result,
            settle_price = excluded.settle_price
        """,
        (kalshi_ticker, resolved_at, result, settle_price),
    )
    conn.commit()


def compute_score(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
    disposition: str = "all",
) -> dict:
    """Score every settled opportunity matching the given segment."""
    sql = """
        SELECT o.outcome, o.entry_price, o.edge_pts_net, o.user_action,
               s.result
        FROM opportunities o
        JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
        WHERE o.theory_id = ? AND o.theory_version = ? AND o.run_mode = ?
    """
    params: list[object] = [theory_id, theory_version, run_mode]
    if disposition != "all":
        sql += " AND o.disposition = ?"
        params.append(disposition)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return dict(EMPTY_SCORE)

    n = len(rows)
    wins = 0
    total_cost = 0.0
    total_return = 0.0
    taken_cost = 0.0
    taken_return = 0.0
    has_taken = False

    for row in rows:
        won = str(row["result"]).lower() == str(row["outcome"]).lower()
        price = row["entry_price"]
        cost = price + fee_pts(price) / 100.0
        payout = 1.0 if won else 0.0

        wins += 1 if won else 0
        total_cost += cost
        total_return += payout

        if row["user_action"] == "taken":
            has_taken = True
            taken_cost += cost
            taken_return += payout

    win_rate = wins / n
    price_implied_rate = sum(r["entry_price"] for r in rows) / n
    calibration_edge = (win_rate - price_implied_rate) * 100.0
    mean_claimed_edge = sum(r["edge_pts_net"] for r in rows) / n

    roi_all = (total_return - total_cost) / total_cost if total_cost else None
    roi_taken = (
        (taken_return - taken_cost) / taken_cost
        if has_taken and taken_cost
        else None
    )

    return {
        "n": n,
        "win_rate": win_rate,
        "price_implied_rate": price_implied_rate,
        "calibration_edge": calibration_edge,
        "mean_claimed_edge": mean_claimed_edge,
        "realization": _realization(calibration_edge, mean_claimed_edge),
        "roi_all": roi_all,
        "roi_taken": roi_taken,
    }


def save_score(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str,
    disposition: str,
    result: dict,
    now: str | None = None,
) -> int:
    """Persist a computed score. Returns the new row id."""
    cursor = conn.execute(
        """
        INSERT INTO scores (
            theory_id, theory_version, run_mode, disposition, n, win_rate,
            price_implied_rate, calibration_edge, mean_claimed_edge,
            realization, roi_all, roi_taken, computed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            theory_id,
            theory_version,
            run_mode,
            disposition,
            result["n"],
            result["win_rate"],
            result["price_implied_rate"],
            result["calibration_edge"],
            result["mean_claimed_edge"],
            result["realization"],
            result["roi_all"],
            result["roi_taken"],
            now or utcnow(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def interpretation_value(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int,
    run_mode: str = "live",
) -> dict:
    """Did stage-2 judgment earn its keep (spec section 7)?

    `delta` is endorsed calibration edge minus rejected calibration edge, in
    points. Positive means interpretation is adding edge; near zero means it
    is adding nothing; negative means it is destroying value. It is None
    until both groups have settled results to compare.
    """
    endorsed = compute_score(
        conn, theory_id, theory_version, run_mode, "endorsed"
    )
    rejected = compute_score(
        conn, theory_id, theory_version, run_mode, "rejected"
    )
    delta = None
    if endorsed["n"] and rejected["n"]:
        delta = endorsed["calibration_edge"] - rejected["calibration_edge"]
    return {"endorsed": endorsed, "rejected": rejected, "delta": delta}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_score.py -v`
Expected: PASS — 15 passed

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -v`
Expected: PASS — 78 passed (5 db + 15 sizing + 12 rank + 9 theories + 22 ledger + 15 score)

- [ ] **Step 6: Commit**

```bash
git add tools/score.py tests/test_score.py
git commit -m "feat: add settlement scoring with disposition split"
```

---

## Definition of done for Plan 1

- `python -m pytest` passes with no failures.
- `db/schema.sql` creates all six tables and both indexes.
- `record_opportunity` refuses a call with no `kalshi_ticker` or no `edge_pts_net`, and a re-sighting increments `times_seen` without changing `entry_price` or `screen_edge_pts_net`.
- `compute_score` returns calibration edge in percentage points, segmented by theory version and disposition, with ROI net of fees and a separate taken-only ROI.
- `interpretation_value` returns a delta once both endorsed and rejected samples have settled.
- No network calls anywhere in `tools/` yet — that is Plan 2.
