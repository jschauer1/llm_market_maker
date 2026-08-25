# At-Risk Basket Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a position declare its payout floor so scoring grades only the portion actually at risk — unblocking `calendar-arb`, which today cannot accrue any evidence.

**Architecture:** Additive throughout. `opportunities` gains one defaulted column, `min_payout REAL NOT NULL DEFAULT 0.0`. Scoring's basket branch computes `implied_rate = (cost − min) / (max − min)` and `won = payout == max`; with `min = 0` that is byte-identical to the formula running today, so no existing row is re-scored. A position that cannot lose (`cost <= min_payout`) is diverted to a riskless bucket scored on return only and never pooled into `calibration_edge`.

**Tech Stack:** Python 3 stdlib (`sqlite3`, `dataclasses`, `math`), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-24-multi-leg-positions-design.md` — sections 3.6, 3.6.1, and 10.1 are the authority for this work. Read them before Task 1.

## Global Constraints

- **No functionality may regress.** The existing suite passes at every task with no test deleted, skipped, or weakened. Current baseline: `python -m pytest -m "not network" -q` → **623 passed, 4 deselected**. Tests may be added freely. If an existing assertion must change to accommodate this work, STOP and report it rather than editing it.
- **Every number scored today must be identical afterwards.** `min_payout` defaults to `0.0`, and `(cost − 0) / (max − 0)` is exactly the formula already in use. `tests/test_score.py`, `tests/test_baskets.py`, and `tests/test_score_characterization.py` are the witnesses — they must pass untouched.
- **The characterization goldens must pass unchanged** (`python -m pytest tests/characterization -q`). Never regenerate a golden; a diff means behavior moved.
- **The guard is generalized, not removed.** Today `_basket_observations` raises when a settled basket's payout is neither `0` nor `max_payout`. It must keep raising, on the generalized condition (neither `min_payout` nor `max_payout`) — see Task 3. A basket whose payout lands strictly between its floor and its ceiling is still unsupported, because the at-risk decomposition assumes the at-risk portion is binary.
- **`min_payout` is checked against reality.** An observed payout below the declared floor means the declaration was wrong: raise, never absorb. This is what makes it safe for a theory to declare its own floor.
- Prices are decimal dollars in [0, 1]; a basket's cost and payouts are in dollars and may exceed 1.0. Edge is in percentage points. Timestamps UTC ISO-8601. `edge_basis` is measured/model/prior.
- **No theory version bumped.** `insider_judgment` stays 3, `mention_family` stays 1. No theory's decision logic changes.
- **No credentials.** All endpoints public.
- Commit after every task with the message given in that task.

## Background an implementer needs

Read the spec sections above; this is the short version.

A basket costing `C` that pays at least `min` and at most `max` bundles a guaranteed return of `min` with a lottery on the difference. Strip out the guaranteed part and what remains is an ordinary bet on `max − min`, bought for `C − min`. That is the whole idea.

Why the *theory* declares the floor: only the theory knows its own payoff shape. That is normally alarming — a theory that declares both its edge and how to grade it marks its own homework. It is safe here because `min_payout` is a **structural fact, checkable against settlements**, not a verdict: scoring already sees how every leg resolved, so a false floor is caught. Verdicts stay with scoring.

Why riskless positions are separated: when `C <= min` the position cannot lose. A win rate over positions that always win is 1.0 by construction and measures nothing. Averaging a certain 5% return into the same `calibration_edge_net` as a 5-point predictive edge describes neither, and that number is what `rank.py` weights every theory by.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `db/schema.sql` | Table definitions | Modify — one column on `opportunities`, two on `scores` |
| `tools/db.py` | Connection, schema, migrations | Modify — three `_add_column_if_missing` calls |
| `tools/ledger.py` | The opportunity contract | Modify — `record_basket` takes and validates `min_payout` |
| `tools/domain.py` | Value types | Modify — `Candidate.min_payout` |
| `tools/theory.py` | Contract; the single ledger path | Modify — pass `min_payout` through |
| `tools/score.py` | Settlement, calibration, ROI | Modify — at-risk decomposition, riskless bucket |
| `tests/test_at_risk_scoring.py` | All new behavior | Create |
| `tests/test_baskets.py` | Existing basket tests | Modify — ONE test transforms (Task 3) |
| `CLAUDE.md`, `tools/README.md` | Conventions | Modify (Task 5) |

---

### Task 1: Schema, migration, and `min_payout` on the ledger

**Files:**
- Modify: `db/schema.sql` (the `opportunities` table)
- Modify: `tools/db.py` (`init_db`)
- Modify: `tools/ledger.py` (`record_basket`, `_normalize_legs` caller)
- Test: `tests/test_at_risk_scoring.py` (create)

**Interfaces:**
- Consumes: `db._add_column_if_missing(conn, table, column, decl)`, `ledger.record_basket` (existing).
- Produces: `opportunities.min_payout` (REAL, NOT NULL, default 0.0); `record_basket(..., min_payout: float = 0.0, ...)` which validates and persists it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_at_risk_scoring.py`:

```python
"""Scoring a position by the portion of it that is actually at risk.

A position costing C that pays at least `min` and at most `max` bundles a
guaranteed return of `min` with a lottery on the difference. Grading the
lottery alone is what makes a floor basket scoreable at all -- see the
multi-leg spec's sections 3.6 and 3.6.1.
"""

import sqlite3

import pytest

from tools import db, ledger, score, theories

TS = "2026-08-25T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _legs(a=0.60, b=0.35):
    return [
        {"kalshi_ticker": "KXLATE-26", "outcome": "yes", "entry_price": a},
        {"kalshi_ticker": "KXEARLY-26", "outcome": "no", "entry_price": b},
    ]


def _basket(conn, **over):
    kwargs = dict(theory_id="t1", theory_version=1, legs=_legs(),
                  edge_pts_net=4.0, edge_basis="model", now=TS)
    kwargs.update(over)
    return ledger.record_basket(conn, **kwargs)


def test_opportunities_has_min_payout_defaulting_to_zero(conn):
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(opportunities)").fetchall()}
    assert "min_payout" in cols
    opp_id, _ = _basket(conn)
    assert ledger.get_opportunity(conn, opp_id)["min_payout"] == \
        pytest.approx(0.0)


def test_a_single_position_defaults_to_a_zero_floor(conn):
    """The default is what makes this change a no-op for existing rows."""
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXS-26",
        outcome="yes", entry_price=0.5, edge_pts_net=6.0, now=TS)
    assert ledger.get_opportunity(conn, opp_id)["min_payout"] == \
        pytest.approx(0.0)


def test_record_basket_persists_a_declared_floor(conn):
    opp_id, _ = _basket(conn, min_payout=1.0, max_payout=2.0)
    row = ledger.get_opportunity(conn, opp_id)
    assert row["min_payout"] == pytest.approx(1.0)
    assert row["max_payout"] == pytest.approx(2.0)


@pytest.mark.parametrize("bad", [-0.5, None, "1.0", True, float("nan")])
def test_a_nonsense_floor_is_refused(conn, bad):
    with pytest.raises(ValueError, match="min_payout"):
        _basket(conn, min_payout=bad, max_payout=2.0)


def test_a_floor_above_the_ceiling_is_refused(conn):
    with pytest.raises(ValueError, match="min_payout"):
        _basket(conn, min_payout=2.5, max_payout=2.0)


def test_a_floor_equal_to_the_ceiling_is_allowed(conn):
    """A position that always pays the same amount is a bond. If it costs
    less than it pays that is a real, if unusual, arbitrage -- and the
    riskless branch handles it before any at-risk division is reached."""
    opp_id, _ = _basket(conn, min_payout=1.0, max_payout=1.0)
    assert ledger.get_opportunity(conn, opp_id)["min_payout"] == \
        pytest.approx(1.0)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_at_risk_scoring.py -q`
Expected: FAIL — `min_payout` is not a column and not a parameter.

- [ ] **Step 3: Add the column to `db/schema.sql`**

In the `opportunities` table, immediately after `max_payout REAL NOT NULL DEFAULT 1.0,`, add:

```sql
    -- The least this position can pay. Scoring grades only the portion
    -- above it: implied_rate = (cost - min_payout) / (max_payout -
    -- min_payout). Default 0.0 makes that identical to the plain
    -- cost/max_payout every existing row was scored by. Unlike
    -- max_payout, which is only a declaration, this one is checked
    -- against settlements -- a payout below the declared floor means the
    -- declaration was wrong and scoring raises.
    min_payout          REAL NOT NULL DEFAULT 0.0,
```

- [ ] **Step 4: Add the migration in `tools/db.py`**

In `init_db`, beside the other `opportunities` additive migrations:

```python
    _add_column_if_missing(
        conn, "opportunities", "min_payout", "REAL NOT NULL DEFAULT 0.0"
    )
```

- [ ] **Step 5: Take and validate `min_payout` in `record_basket`**

Add the keyword parameter `min_payout: float = 0.0` to `record_basket`, immediately after `max_payout`. Validate it beside the existing `max_payout` check, and add `min_payout` to the INSERT column list, its placeholder, and the params tuple. The `ON CONFLICT DO UPDATE` clause does **not** touch it — like `entry_price`, a re-sighting must not rewrite what the position was when first seen.

```python
    if (isinstance(min_payout, bool)
            or not isinstance(min_payout, (int, float))
            or (isinstance(min_payout, float) and math.isnan(min_payout))
            or min_payout < 0):
        raise ValueError(
            f"min_payout must be a non-negative number, got {min_payout!r}"
        )
    if min_payout > max_payout:
        raise ValueError(
            f"min_payout {min_payout!r} exceeds max_payout {max_payout!r}; "
            "a position cannot guarantee more than it can pay"
        )
```

Extend `record_basket`'s docstring to say what the floor is for, in one or two sentences, citing the spec section.

- [ ] **Step 6: Run tests and the full suite**

Run: `python -m pytest tests/test_at_risk_scoring.py tests/test_baskets.py -q` — expect all pass.
Run: `python -m pytest -m "not network" -q` — expect 623 + the new tests, none failing.

- [ ] **Step 7: Commit**

```bash
git add db/schema.sql tools/db.py tools/ledger.py tests/test_at_risk_scoring.py
git commit -m "feat: positions declare a payout floor"
```

---

### Task 2: `min_payout` through the domain type and the contract

**Files:**
- Modify: `tools/domain.py` (`Candidate`)
- Modify: `tools/theory.py` (`OpportunityRecord.from_scored`)
- Test: `tests/test_domain.py` (append), `tests/test_theory.py` (append)

**Interfaces:**
- Consumes: `Candidate` (fields `legs`, `days_to_close`, `max_payout`), `OpportunityRecord.from_scored`.
- Produces: `Candidate.min_payout: float = 0.0`, validated in `__post_init__`; `from_scored` passes it to `record_basket`.

`Candidate` already validates `max_payout` in `__post_init__` — mirror that for `min_payout`, and add the cross-check. This is the "earlier, additional line of defence" relationship the ledger validators already have; the ledger check is retained, not moved.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_domain.py`:

```python
def test_candidate_defaults_to_a_zero_floor():
    assert single().min_payout == 0.0


@pytest.mark.parametrize("bad", [-0.5, None, "0.0", True, float("nan")])
def test_candidate_rejects_a_nonsense_min_payout(bad):
    with pytest.raises(ValueError, match="min_payout"):
        Candidate(legs=(leg(),), days_to_close=1.0, min_payout=bad)


def test_candidate_rejects_a_floor_above_its_ceiling():
    with pytest.raises(ValueError, match="min_payout"):
        Candidate(legs=(leg(),), days_to_close=1.0,
                  min_payout=2.0, max_payout=1.0)


def test_candidate_allows_a_floor_equal_to_its_ceiling():
    c = Candidate(legs=(leg(),), days_to_close=1.0,
                  min_payout=1.0, max_payout=1.0)
    assert c.min_payout == c.max_payout == 1.0
```

Append to `tests/test_theory.py`:

```python
def test_a_basket_candidates_floor_reaches_the_ledger(tmp_path):
    """finish() is the single ledger path, so a floor declared on the
    position must survive it -- otherwise a floor basket would record as
    all-or-nothing and be scored on the wrong event."""
    from tools import ledger, theories
    from tools.domain import Candidate, Edge, Leg, ScoredCandidate

    class FloorBasket(Theory):
        id, name, version = "stub_floor", "Stub Floor", 1

        def screen(self, ctx):
            legs = tuple(Leg(market=m, side="yes", price=0.5)
                         for m in ctx.board)
            return [Candidate(legs=legs, days_to_close=1.0,
                              min_payout=1.0, max_payout=2.0)]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(candidate=c,
                                    edge=Edge(pts_net=4.0, basis="model"))
                    for c in cands]

    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_floor", "Stub Floor", "x", now=TS)
    ctx = TheoryContext.build(
        conn=conn, board=[mkm("KXA-26"), mkm("KXB-26")], now=NOW)
    result = FloorBasket().start(ctx).finish()
    row = ledger.get_opportunity(conn, result.opportunity_ids[0])
    assert row["min_payout"] == pytest.approx(1.0)
    assert row["max_payout"] == pytest.approx(2.0)
    conn.close()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_domain.py tests/test_theory.py -q`
Expected: FAIL — `Candidate` has no `min_payout`.

- [ ] **Step 3: Add the field to `Candidate`**

Add `min_payout: float = 0.0` after `max_payout`. In `__post_init__`, after the existing `max_payout` validation:

```python
        mn = self.min_payout
        if (isinstance(mn, bool) or not isinstance(mn, (int, float))
                or (isinstance(mn, float) and math.isnan(mn)) or mn < 0):
            raise ValueError(
                f"min_payout must be a non-negative number, got {mn!r}"
            )
        if mn > self.max_payout:
            raise ValueError(
                f"min_payout {mn!r} exceeds max_payout {self.max_payout!r}; "
                "a position cannot guarantee more than it can pay"
            )
```

Extend the class docstring with a sentence on what the floor means and that scoring grades only the portion above it.

- [ ] **Step 4: Pass it through the contract**

In `tools/theory.py`, `OpportunityRecord.from_scored`'s basket branch, add `min_payout=c.min_payout` alongside the existing `max_payout=c.max_payout`.

- [ ] **Step 5: Run tests and the full suite**

Run: `python -m pytest tests/test_domain.py tests/test_theory.py tests/test_backlog_fit.py -q` then `python -m pytest -m "not network" -q`.
Expected: all pass. The `test_backlog_fit.py` basket stub declares no floor, so it still defaults to 0.0 and behaves exactly as before.

- [ ] **Step 6: Commit**

```bash
git add tools/domain.py tools/theory.py tests/test_domain.py tests/test_theory.py
git commit -m "feat: a Candidate carries its payout floor to the ledger"
```

---

### Task 3: The at-risk decomposition in scoring

**Files:**
- Modify: `tools/score.py` (`_basket_observations`)
- Test: `tests/test_at_risk_scoring.py` (append), `tests/test_baskets.py` (ONE test transforms)

**Interfaces:**
- Consumes: `_segment_filter`, `_won`, `fee_pts`, the `min_payout` column from Task 1.
- Produces: `_basket_observations` emitting at-risk observations, plus a `riskless` flag on each observation dict that Task 4 consumes. Observation shape gains one key: `"riskless": bool`.

**This task changes the guard, and that is deliberate.** Today `_basket_observations` raises when a settled basket's payout is neither `0` nor `max_payout`. That becomes: raise when the payout is neither `min_payout` nor `max_payout`. With `min_payout = 0` — every row that exists today — the two conditions are **identical**, so nothing already recorded changes behavior.

The guard is generalized rather than removed because the at-risk decomposition assumes the at-risk portion is **binary**: the position pays either its floor or its ceiling. A three-leg basket that can pay 1 of a possible 3 still has no meaningful single `won` event, and must keep raising.

**And a new check:** an observed payout **below** the declared floor means the declaration was false. Raise, naming both figures. This is the check that makes it safe for a theory to declare its own floor.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_at_risk_scoring.py`:

```python
def _settle(conn, pairs):
    for ticker, result in pairs:
        score.record_settlement(conn, ticker, result, resolved_at=TS)


def test_at_risk_rate_prices_only_the_portion_that_can_be_lost(conn):
    # cost 1.55, floor 1.00, ceiling 2.00 -> a 0.55 bet on a 1.00 payoff.
    _basket(conn, legs=_legs(0.95, 0.60), min_payout=1.0, max_payout=2.0)
    _settle(conn, [("KXLATE-26", "yes"), ("KXEARLY-26", "no")])  # pays 2.00
    obs = score._basket_observations(conn, "t1", 1, "live", "all", None)
    assert len(obs) == 1
    from tools.sizing import fee_pts
    fee = fee_pts(0.95) + fee_pts(0.60)
    cost = 1.55 + fee / 100.0
    assert obs[0]["implied_rate"] == pytest.approx((cost - 1.0) / (2.0 - 1.0))
    assert obs[0]["won"] is True
    assert obs[0]["riskless"] is False


def test_paying_only_the_floor_is_an_at_risk_loss(conn):
    _basket(conn, legs=_legs(0.95, 0.60), min_payout=1.0, max_payout=2.0)
    _settle(conn, [("KXLATE-26", "yes"), ("KXEARLY-26", "yes")])  # pays 1.00
    obs = score._basket_observations(conn, "t1", 1, "live", "all", None)
    assert obs[0]["won"] is False
    assert obs[0]["payout"] == pytest.approx(1.0)


def test_a_zero_floor_reproduces_the_historical_formula(conn):
    """The non-regression claim, asserted directly: with no declared floor
    the at-risk rate IS cost/max_payout, which is what every existing row
    was scored by."""
    _basket(conn, legs=_legs(0.40, 0.55))          # floor 0, ceiling 1
    _settle(conn, [("KXLATE-26", "yes"), ("KXEARLY-26", "no")])
    obs = score._basket_observations(conn, "t1", 1, "live", "all", None)
    from tools.sizing import fee_pts
    cost = 0.95 + (fee_pts(0.40) + fee_pts(0.55)) / 100.0
    assert obs[0]["implied_rate"] == pytest.approx(cost / 1.0)


def test_a_payout_below_the_declared_floor_raises(conn):
    """The check that makes a theory-declared floor safe: the claim is
    verified against what actually settled."""
    _basket(conn, legs=_legs(0.60, 0.35), min_payout=1.0, max_payout=2.0)
    _settle(conn, [("KXLATE-26", "no"), ("KXEARLY-26", "yes")])  # pays 0.00
    with pytest.raises(ValueError, match="below its declared min_payout"):
        score._basket_observations(conn, "t1", 1, "live", "all", None)


def test_a_payout_between_floor_and_ceiling_still_raises(conn):
    """The at-risk decomposition assumes a binary at-risk portion. A
    three-leg basket paying 1 of a possible 3 has no single `won` event."""
    legs = [
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.30},
        {"kalshi_ticker": "KXB-26", "outcome": "yes", "entry_price": 0.30},
        {"kalshi_ticker": "KXC-26", "outcome": "yes", "entry_price": 0.30},
    ]
    _basket(conn, legs=legs, max_payout=3.0)
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "no"), ("KXC-26", "no")])
    with pytest.raises(ValueError, match="neither its min_payout"):
        score._basket_observations(conn, "t1", 1, "live", "all", None)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_at_risk_scoring.py -q`
Expected: the new tests FAIL — no `riskless` key, no floor handling.

- [ ] **Step 3: Rewrite the guard and the observation in `_basket_observations`**

Read `min_payout` in the header SELECT alongside `max_payout`. Then replace the payout guard and the observation construction:

```python
        max_payout = header["max_payout"]
        min_payout = header["min_payout"]

        # A theory declares its own floor because only it knows its payoff
        # shape -- safe precisely because the claim is checkable here. A
        # payout beneath the declared floor means the declaration was
        # false, and a false floor would understate the at-risk cost and
        # overstate the edge.
        if payout < min_payout - 1e-9:
            raise ValueError(
                f"opportunity {header['id']}: settled payout {payout:.4f} is "
                f"below its declared min_payout {min_payout:.4f}. The floor "
                "is a claim about what the contracts guarantee and it did "
                "not hold, so the position cannot be scored against it. Fix "
                "the theory's declaration, not this check."
            )

        # The at-risk decomposition assumes the at-risk portion is binary:
        # the position pays either its floor or its ceiling. A basket that
        # can land in between (three legs of a possible three, say) has no
        # single event `won` can name, exactly as before this generalized
        # from {0, max_payout}. At min_payout = 0 -- every row recorded
        # before floors existed -- this is the identical condition.
        if not (
            math.isclose(payout, min_payout, rel_tol=1e-9, abs_tol=1e-9)
            or math.isclose(payout, max_payout, rel_tol=1e-9, abs_tol=1e-9)
        ):
            raise ValueError(
                f"opportunity {header['id']}: basket payout {payout:.4f} is "
                f"neither its min_payout {min_payout:.4f} nor its "
                f"max_payout {max_payout:.4f}. Scoring grades the portion "
                "of a position that is at risk, which assumes that portion "
                "is all-or-nothing. See docs/superpowers/specs/"
                "2026-08-24-multi-leg-positions-design.md section 3.6"
            )

        cost = header["entry_price"] + fee / 100.0

        # A position whose cost is covered by its guaranteed floor cannot
        # lose. Calibration is undefined for it -- a win rate over things
        # that always win is 1.0 by construction and measures nothing --
        # so it is flagged here and scored on return only (section 3.6.1).
        riskless = cost <= min_payout
        at_risk_payoff = max_payout - min_payout
        if riskless or at_risk_payoff <= 0:
            riskless = True
            implied_rate = None
            won = False
        else:
            implied_rate = (cost - min_payout) / at_risk_payoff
            won = math.isclose(payout, max_payout,
                               rel_tol=1e-9, abs_tol=1e-9)

        out.append({
            "implied_rate": implied_rate,
            "won": won,
            "cost": cost,
            "payout": payout,
            # Fees share implied_rate's scale, so they are normalized by
            # the same at-risk denominator. A riskless position has no
            # such scale; Task 4 keeps it out of the fee mean entirely.
            "fee_pts": fee if riskless else fee / at_risk_payoff,
            "edge_pts_net": header["edge_pts_net"],
            "user_action": header["user_action"],
            "riskless": riskless,
        })
```

Note the fee normalization changed from `fee / max_payout` to `fee / at_risk_payoff`. At `min_payout = 0` those are the same value, so no existing row moves.

Add `"riskless": False` to every observation `_single_leg_observations` emits — a single position is never riskless (it can resolve against you), and `_aggregate` needs the key present on every row.

- [ ] **Step 4: Transform the pinned guard test**

`tests/test_baskets.py::test_nesting_branch_with_a_payout_floor_is_unsupported_and_raises` pins the OLD behavior. The spec says it "becomes the assertion of the section 3.6 behavior rather than being deleted." Rewrite it in place to assert the new behavior for that same position: with `min_payout` declared, a nesting branch paying its floor now scores rather than raising. Keep the test's name meaningful — rename to reflect what it now asserts — and keep the original scenario's numbers. **This is the only existing test this plan may change.** If any other existing test needs changing, STOP and report.

- [ ] **Step 5: Run tests, goldens, and the full suite**

Run: `python -m pytest tests/test_at_risk_scoring.py tests/test_baskets.py tests/test_score.py tests/test_score_characterization.py tests/characterization -q`
Expected: all pass — the score characterization tests are the proof single-leg math did not move.

Run: `python -m pytest -m "not network" -q` — all pass.

- [ ] **Step 6: Verify parity against the live database**

```bash
python -c "
from tools import db, score, theories
c = db.connect()
for t in theories.list_theories(c):
    print(t['id'], t['version'], score.compute_score(c, t['id'], t['version']))
"
```

Record the output and compare against the same command run from the previous commit (`git stash` or a worktree at HEAD~1). Expected: byte-identical. No live row declares a floor, so nothing may move.

- [ ] **Step 7: Commit**

```bash
git add tools/score.py tests/test_at_risk_scoring.py tests/test_baskets.py
git commit -m "feat: score a position by the portion of it that is at risk"
```

---

### Task 4: Riskless positions reported, never calibrated

**Files:**
- Modify: `tools/score.py` (`_aggregate`, `EMPTY_SCORE`, `save_score`), `db/schema.sql` (`scores`), `tools/db.py`
- Test: `tests/test_at_risk_scoring.py` (append)

**Interfaces:**
- Consumes: the `riskless` flag Task 3 puts on every observation.
- Produces: `compute_score` returning two extra keys — `riskless_n: int` and `riskless_roi: float | None` — with riskless observations excluded from `n`, `win_rate`, `price_implied_rate`, `calibration_edge`, `calibration_edge_net`, `mean_claimed_edge`, `mean_fee_pts`, and `realization`. `scores` gains matching columns.

**The separation is the point.** A certain 5% return and a 5-point predictive edge are different animals; pooling them produces a number that describes neither, and `rank.py` weights every theory by exactly that number.

**Deliberate decision to encode:** riskless positions **do** contribute to `roi_all` and `roi_taken`, because those measure money and money is money. They contribute to nothing else. Say so in `_aggregate`'s docstring.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_at_risk_scoring.py`:

```python
def test_a_riskless_position_is_reported_separately_not_calibrated(conn):
    # cost 0.95 against a guaranteed 1.00 -- calendar-arb's shape.
    _basket(conn, legs=_legs(0.60, 0.35), min_payout=1.0, max_payout=2.0)
    _settle(conn, [("KXLATE-26", "yes"), ("KXEARLY-26", "yes")])  # pays 1.00
    r = score.compute_score(conn, "t1", 1)

    assert r["riskless_n"] == 1
    assert r["riskless_roi"] > 0            # it made money, certainly
    # ...and contributed nothing to the calibrated population:
    assert r["n"] == 0
    assert r["win_rate"] is None
    assert r["calibration_edge_net"] is None


def test_riskless_and_calibrated_positions_do_not_pool(conn):
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXS-26",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS)
    _basket(conn, legs=_legs(0.60, 0.35), min_payout=1.0, max_payout=2.0)
    _settle(conn, [("KXS-26", "yes"), ("KXLATE-26", "yes"),
                   ("KXEARLY-26", "yes")])
    r = score.compute_score(conn, "t1", 1)

    assert r["n"] == 1                       # the single position only
    assert r["win_rate"] == pytest.approx(1.0)
    assert r["riskless_n"] == 1              # the arbitrage, kept apart
    assert r["roi_all"] is not None          # money still counts as money


def test_no_riskless_positions_leaves_the_keys_at_their_defaults(conn):
    _basket(conn, legs=_legs(0.40, 0.55))
    _settle(conn, [("KXLATE-26", "yes"), ("KXEARLY-26", "no")])
    r = score.compute_score(conn, "t1", 1)
    assert r["riskless_n"] == 0
    assert r["riskless_roi"] is None
    assert r["n"] == 1


def test_empty_score_carries_the_riskless_keys(conn):
    r = score.compute_score(conn, "t1", 1)
    assert r["n"] == 0 and r["riskless_n"] == 0
    assert r["riskless_roi"] is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_at_risk_scoring.py -k riskless -q`
Expected: FAIL — `KeyError: 'riskless_n'`.

- [ ] **Step 3: Split the population in `_aggregate`**

Add `"riskless_n": 0` and `"riskless_roi": None` to `EMPTY_SCORE`. At the top of `_aggregate`, partition:

```python
    riskless = [r for r in rows if r.get("riskless")]
    rows = [r for r in rows if not r.get("riskless")]
```

Compute the riskless figures separately:

```python
    riskless_cost = 0.0
    riskless_return = 0.0
    for r in riskless:
        riskless_cost += r["cost"]
        riskless_return += r["payout"]
    riskless_roi = (
        (riskless_return - riskless_cost) / riskless_cost
        if riskless_cost else None
    )
```

Then: if the calibrated `rows` list is empty, return `dict(EMPTY_SCORE)` updated with the riskless figures **and** with `roi_all`/`roi_taken` computed over the riskless positions — a theory that produced nothing but arbitrage must still report its return. Otherwise compute the existing figures over `rows` unchanged, and fold the riskless cost and payout into `roi_all` and `roi_taken` only.

Keep the hand-rolled accumulation loops exactly as they are — their comment explains that the loop, not `sum()`, is what preserves bit-exact equivalence with the pre-refactor implementation.

Extend `_aggregate`'s docstring: riskless positions contribute to ROI and to nothing else, and why.

- [ ] **Step 4: Persist the new figures**

Add to `db/schema.sql`'s `scores` table:

```sql
    riskless_n         INTEGER NOT NULL DEFAULT 0,
    riskless_roi       REAL,
```

Add two `_add_column_if_missing` calls in `init_db`, and extend `save_score`'s INSERT column list, placeholders, and values with `result["riskless_n"]` and `result["riskless_roi"]`.

- [ ] **Step 5: Run tests, goldens, and the full suite**

Run: `python -m pytest tests/test_at_risk_scoring.py tests/test_score.py tests/test_score_characterization.py tests/test_baskets.py tests/characterization -q` then `python -m pytest -m "not network" -q`.
Expected: all pass. `test_score_characterization.py` is the witness that single-leg math is untouched.

- [ ] **Step 6: Live-database parity, again**

Re-run the Task 3 Step 6 parity command. Expected: every pre-existing key byte-identical; `riskless_n` 0 and `riskless_roi` None everywhere, since no live row declares a floor.

- [ ] **Step 7: Commit**

```bash
git add tools/score.py db/schema.sql tools/db.py tests/test_at_risk_scoring.py
git commit -m "feat: riskless positions score on return, never on calibration"
```

---

### Task 5: Documentation, and unblocking `calendar-arb`

**Files:**
- Modify: `CLAUDE.md`, `tools/README.md`
- Modify: `docs/superpowers/specs/2026-08-24-multi-leg-positions-design.md` (status only)

**Interfaces:** consumes everything above; produces no code.

- [ ] **Step 1: `tools/README.md`**

Extend the existing "A position may have legs" convention bullet with the floor:

```markdown
- **A position declares what it can pay.** `max_payout` is the most it can
  return, `min_payout` the least. Scoring grades only the portion at risk —
  `(cost − min_payout) / (max_payout − min_payout)` — so a position with a
  guaranteed floor is priced on the part that can actually be lost. Both
  default to the single-position case (`0.0` and `1.0`), which is why every
  existing row scores identically. A position whose cost is covered by its
  floor cannot lose: it is scored on return only and reported separately,
  never pooled into `calibration_edge`.
```

- [ ] **Step 2: `CLAUDE.md`**

Extend the basket bullet in Data conventions:

```markdown
- **An arbitrage is not a forecast.** A position that cannot lose
  (`cost <= min_payout`) has no meaningful win rate — one over positions
  that always win is 1.0 by construction. Those are scored on return and
  reported in their own bucket (`riskless_n`, `riskless_roi`), never
  averaged into `calibration_edge`. When reporting a theory that produces
  both kinds, show both, and never sum them.
```

- [ ] **Step 3: Flip the spec's status**

In the multi-leg spec: change the top notice from "design written, not yet implemented" to implemented, and success criterion 2 from ⚠️ to ✅, citing `tests/test_at_risk_scoring.py`. Leave section 10.1's reasoning intact as the record of why the design is what it is.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest -m "not network" -q` — unchanged, docs only.

```bash
git add CLAUDE.md tools/README.md docs/superpowers/specs/2026-08-24-multi-leg-positions-design.md
git commit -m "docs: the at-risk rule, and arbitrage reported apart from forecasts"
```

---

## Verification Checklist

- [ ] `python -m pytest -m "not network" -q` — all pass, none skipped or deleted.
- [ ] Every characterization golden passes unchanged; none regenerated.
- [ ] Live-database parity: `compute_score` returns identical pre-existing keys for every theory, before and after.
- [ ] A basket with no declared floor scores exactly as it did before (`test_a_zero_floor_reproduces_the_historical_formula`).
- [ ] A floor basket prices only its at-risk portion, and paying the floor is a loss.
- [ ] A payout below the declared floor raises, naming both figures.
- [ ] A payout strictly between floor and ceiling still raises.
- [ ] Riskless positions contribute to ROI and to nothing else.
- [ ] No theory version bumped; `registry.check_drift(conn)` still empty.

## What this does NOT do

- **No portfolio or correlation layer.** A basket is still one position.
- **No execution modelling.** Leg-by-leg fill risk stays reported, not simulated.
- **Multi-outcome payoffs stay unsupported.** A position that can land strictly between its floor and ceiling still raises. If a real theory needs it, that is a new decision about what `won` means for a multi-outcome position — do not widen the guard to make one pass.
- **`calendar-arb` is not built here.** This unblocks it; the theory itself is separate work.
