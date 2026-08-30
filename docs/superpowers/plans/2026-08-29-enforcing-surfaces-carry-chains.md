# Enforcing Surfaces — Plan: Carry Chains (phase 6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make version bumps declare `breaking` vs `carry`, refuse unproven carries structurally, pool evidence across proven carry-chains in scoring/slices/ranking, and backfill every historical bump as `breaking`.

**Architecture:** A new `theory_versions` table records every bump's kind with a CHECK making unproven carries uninsertable. `theories.bump_version` gains `kind`/`justification`/`equivalence` and writes the row. `theories.prove_carry` replays a theory-supplied `decide` callable over the predecessor's stored attempts and compares decision *outputs* field-exactly. `score.compute_score` and `slices.segment_report` gain `pool="version"|"chain"` (default `"version"` — today's behavior, no caller changes meaning); `rank` adopts `"chain"` with a one-time before/after disclosure. No shared replay engine is built — `prove_carry` inverts no control; the theory hands it one function.

**Tech Stack:** Python stdlib + sqlite3, pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-enforcing-surfaces-design.md` §2 (all), §10 (tests). The equivalence field list is §2.4's, verbatim: side (`outcome`, joined from the parent position), `disposition`, `model_prob`, `confidence`, `edge_pts_gross`, `edge_pts_net`, `edge_basis`, plus any `extra_json` key a registered slice predicates on. `decision_date` and `entry_price` are replay inputs, never proven.

## Global Constraints

- Suite green throughout (baseline at plan start: run `python -m pytest -q` and record it).
- `pool="version"` must reproduce today's numbers exactly — characterization-tested before anything adopts `"chain"`.
- **tests/test_conventions.py is HELD by the peer session (llm-market-identifier-5d) until they signal clear** — Task 6's conventions test lands only after that signal; everything else avoids the file.
- Timestamps UTC ISO-8601 (`tools.db.utcnow`); writes wrapped in `db.write`; new tables via `db/schema.sql` + `executescript` (no migration helper needed for new tables).
- Every commit message ends with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 1: `theory_versions` schema + `bump_version(kind=…)`

**Files:**
- Modify: `db/schema.sql` (after `rulings`), `tools/theories.py:270` (`bump_version`), `tools/theories.py` (`register` writes the v1 row), `tools/cli.py` (the `theories bump` parser + handler)
- Test: `tests/test_theories.py` (append; reuse its fixtures)

**Interfaces:**
- Produces: `theories.bump_version(conn, theory_id, now=None, *, kind="breaking", justification, equivalence=None) -> int` — `justification` is required (keyword-only, no default → `TypeError` if omitted at call sites; update the one CLI caller and any test callers); `kind="carry"` refuses (`ValueError`) unless `equivalence` is a passing `EquivalenceResult` (Task 2's type; until Task 2 lands, the parameter accepts any object with `.passed` and `.label` — define a tiny `_CarryProof` protocol comment). Writes the `theory_versions` row in the same transaction as the version update.
- Produces: `theories.list_versions(conn, theory_id) -> list[sqlite3.Row]` ordered by version.

- [ ] **Step 1: schema** — append to `db/schema.sql` (spec §2.3 verbatim):

```sql
-- Every version bump's declared relationship to its predecessor
-- (enforcing-surfaces spec 2.3). 'breaking' resets the track record and is
-- the default; 'carry' pools evidence forward and is uninsertable without
-- an equivalence_run -- the proof is the permission.
CREATE TABLE IF NOT EXISTS theory_versions (
    theory_id       TEXT NOT NULL,
    version         INTEGER NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('breaking','carry')),
    predecessor     INTEGER,
    justification   TEXT NOT NULL,
    equivalence_run TEXT,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (theory_id, version),
    CHECK (kind <> 'carry' OR equivalence_run IS NOT NULL)
);
```

- [ ] **Step 2: failing tests** (append to `tests/test_theories.py`, matching its fixture style):

```python
def test_bump_requires_justification_and_defaults_breaking(conn):
    theories.register(conn, "t1", "T1", "theories/t1")
    v = theories.bump_version(conn, "t1", justification="new gate")
    assert v == 2
    rows = theories.list_versions(conn, "t1")
    assert [(r["version"], r["kind"]) for r in rows] == [
        (1, "breaking"), (2, "breaking")]
    assert rows[-1]["predecessor"] == 1


def test_carry_refuses_without_a_passing_proof(conn):
    theories.register(conn, "t1", "T1", "theories/t1")
    with pytest.raises(ValueError, match="proof"):
        theories.bump_version(conn, "t1", kind="carry",
                              justification="plumbing only")


class _Proof:
    passed = True
    label = "carry-proof/t1-v1-to-v2"


def test_carry_records_the_equivalence_run(conn):
    theories.register(conn, "t1", "T1", "theories/t1")
    v = theories.bump_version(conn, "t1", kind="carry",
                              justification="plumbing only",
                              equivalence=_Proof())
    row = theories.list_versions(conn, "t1")[-1]
    assert (v, row["kind"], row["equivalence_run"]) == (
        2, "carry", "carry-proof/t1-v1-to-v2")


def test_register_writes_the_v1_row(conn):
    theories.register(conn, "t1", "T1", "theories/t1")
    rows = theories.list_versions(conn, "t1")
    assert [(r["version"], r["kind"], r["predecessor"]) for r in rows] == [
        (1, "breaking", None)]
```

- [ ] **Step 3: implement.** `bump_version` new body: validate kind; for `carry`, `if equivalence is None or not getattr(equivalence, "passed", False): raise ValueError("carry needs a passing equivalence proof — the proof is the permission (spec 2.4)")`; single `with write(conn)` doing the theories UPDATE plus `INSERT INTO theory_versions (theory_id, version, kind, predecessor, justification, equivalence_run, created_at) VALUES (?,?,?,?,?,?,?)` with `equivalence_run = getattr(equivalence, "label", None)`. `register` inserts the v1 row (`kind='breaking'`, `predecessor NULL`, `justification='initial version'`) inside its existing transaction. `list_versions` is a plain SELECT ordered by version. CLI: `bump` gains `--kind {breaking,carry}` (default breaking) and required `--justification`; carry via CLI is refused with a message naming `prove_carry` (the CLI cannot carry a proof object — that is deliberate; carries happen from Python where the proof ran).
- [ ] **Step 4:** run new tests (fail → implement → pass), then full suite — fix any existing caller of `bump_version` the keyword-only change breaks (grep first: `grep -rn "bump_version" tools/ tests/`).
- [ ] **Step 5: the §2.7 CLAUDE.md edit** — append after the existing bump paragraph in "## Theory lifecycle and versioning" (verbatim from the spec):

```markdown
**A bump declares whether it breaks the track record.** `breaking` is the
default and resets it. `carry` — for a change that provably could not alter
the decision on rows already recorded — keeps it, and is refused unless a
replay over the predecessor's own attempts reproduces every recorded decision
exactly. Assertion does not qualify; the proof is the permission. This does
not soften the bump rule, it makes the rule affordable: a theory still being
improved could otherwise never accumulate evidence, which is how three of
the four running theories reached n=0.
```

- [ ] **Step 6: Commit** — `feat: theory_versions — bumps declare breaking/carry, carry needs proof (spec 2.3, 2.4, 2.7)`

---

### Task 2: `prove_carry`

**Files:**
- Modify: `tools/theories.py` (append), `tools/domain.py` (the result dataclass)
- Test: `tests/test_carry_chain.py` (new)

**Interfaces:**
- Produces: `domain.EquivalenceResult` frozen dataclass: `theory_id: str`, `from_version: int`, `n_attempts: int`, `divergences: tuple` (each a `(opportunity_id, decision_date, field, recorded, replayed)` tuple, capped at 50), `n_divergent: int`, `label: str`, and property `passed -> bool` (`n_divergent == 0 and n_attempts > 0`).
- Produces: `theories.prove_carry(conn, theory_id, from_version, decide, *, slice_extra_keys=None, now=None) -> EquivalenceResult` where `decide: Callable[[sqlite3.Row], Mapping]` is **theory-supplied** — it receives one joined attempt row (attempt columns plus the parent position's `kalshi_ticker` and `outcome`) and returns the current code's decision outputs for that market given the stored `decision_date`/`entry_price`. The harness never knows how to decide; it only selects the fixture, compares, and reports. This is the spec's no-engine rule: the theory owns the replay, the harness owns bookkeeping.

- [ ] **Step 1: failing tests** — build a fixture DB with `_record`-style rows at v1 (live mode), then:

```python
def _echo_decide(row):
    """A decide that reproduces the recorded outputs exactly."""
    return {
        "outcome": row["outcome"], "disposition": row["disposition"],
        "model_prob": row["model_prob"], "confidence": row["confidence"],
        "edge_pts_gross": row["edge_pts_gross"],
        "edge_pts_net": row["edge_pts_net"], "edge_basis": row["edge_basis"],
    }


def test_identical_replay_passes(conn):
    # two recorded live attempts at v1
    ...
    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed and res.n_attempts == 2 and res.n_divergent == 0
    assert res.label.startswith("carry-proof/t1-v1-")


def test_single_divergence_fails_whatever_the_field(conn):
    def flip(row):
        out = _echo_decide(row)
        out["edge_basis"] = "model"
        return out
    res = theories.prove_carry(conn, "t1", 1, flip)
    assert not res.passed and res.n_divergent >= 1
    assert res.divergences[0][2] == "edge_basis"


def test_slice_predicated_extra_keys_are_compared(conn):
    # attempt recorded with extra_json {"family": "awards"}; decide returns
    # {"family": "sports"} under extra -> divergence on "extra.family"
    ...
    res = theories.prove_carry(conn, "t1", 1, decide,
                               slice_extra_keys=("family",))
    assert not res.passed and res.divergences[0][2] == "extra.family"


def test_empty_fixture_never_passes(conn):
    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.n_attempts == 0 and not res.passed
```

- [ ] **Step 2: implement.** Fixture query: attempts joined to positions at `(theory_id, from_version)`, `run_mode='live' AND lane='main'` plus **tier-A/B backtest attempts** (`run_mode='backtest'`) — both pools carry evidence; exclude `lane != 'main'`. `slice_extra_keys` defaults to the keys named by `extra` clauses in the theory's registered slice predicates (`SELECT predicate_json FROM theory_slices WHERE theory_id=?` → parse, collect `extra` keys) — the parameter overrides for tests. Compare per field with float tolerance `1e-9` for the numeric fields, exact for the rest; missing key in `decide`'s output = divergence `(field, recorded, "<absent>")`. Label: `carry-proof/{theory_id}-v{from_version}-{YYYYMMDD}`.
- [ ] **Step 3:** tests green; full suite green.
- [ ] **Step 4: Commit** — `feat: prove_carry — a carry claim is a replay result, never an assertion (spec 2.4)`

---

### Task 3: chain pooling in `compute_score`

**Files:**
- Modify: `tools/theories.py` (chain resolver), `tools/score.py:298` (`compute_score`) and `tools/score.py` `_segment_filter`
- Test: `tests/test_carry_chain.py` (append), `tests/test_score_characterization.py` (one test)

**Interfaces:**
- Produces: `theories.carry_chain(conn, theory_id, version) -> list[int]` — the maximal run of consecutive versions linked by `carry` rows ending at `version` (walk `theory_versions` backwards; a `breaking` row or a missing row terminates; always includes `version` itself).
- Produces: `compute_score(..., pool="version")` — under `"chain"`, `_segment_filter`'s `o.theory_version = ?` becomes `o.theory_version IN (…)` over the chain; the returned dict gains `"chain_versions": [..]` **only when** more than one version contributed (spec §2.5: a pooled number can never be read without seeing what was pooled).

- [ ] **Step 1: failing tests** — chain walk (breaking terminates; carry links; v1 alone), pooling (rows at v1+v2 with a carry row at v2 pool under `"chain"`, don't under `"version"`), and the characterization guard:

```python
def test_pool_version_is_byte_identical_to_before(conn):
    # same fixture scored with and without the new parameter's default
    assert score.compute_score(conn, "t1", 2) == \
           score.compute_score(conn, "t1", 2, pool="version")
    assert "chain_versions" not in score.compute_score(conn, "t1", 2)
```

- [ ] **Step 2: implement** (`_segment_filter` gains a `versions: list[int]` parameter; `compute_score` resolves the chain when `pool=="chain"`). `settlement_day_clusters` and `observations` route through the same filter — thread `pool` through whichever of them `compute_score` calls (read `_aggregate`/`observations` first; keep the change at the filter seam so every consumer widens together).
- [ ] **Step 3:** green; full suite; **also** run `python -m tools.cli score report insider_judgment` against the live DB and confirm output is unchanged vs before the commit (paste both in the report).
- [ ] **Step 4: Commit** — `feat: compute_score pools across proven carry-chains behind pool="chain" (spec 2.5)`

---

### Task 4: chain pooling in `slices.segment_report`

Same seam, same shape: `segment_report(conn, theory_id, version, ..., pool="version")` widens its version filter over `theories.carry_chain` under `"chain"` and reports `chain_versions` the same way (spec §2.8). Test: a slice segment at v1 pools into v2 under a proven carry, and never under `"version"`. Read `tools/slices.py:430`'s filtering before writing the test — mirror whatever version predicate it uses today. Commit: `feat: segment_report pools slice evidence across carry-chains (spec 2.8)`.

---

### Task 5: `rank` adopts chains + the disclosure

**Files:** whatever `tools/rank.py` reads scores through (read it first — if it takes numbers as arguments, the adoption point is its *callers* in the skills' documented flow plus `find-edge`'s usage; the spec's requirement is that ranking uses chain-pooled score rows in the same commit as a **full before/after ranked-edge table for every running theory with any probation flip called out**).

- [ ] **Step 1**: read `tools/rank.py` and `grep -rn "compute_score" tools/ .claude/skills/` to find where ranking sources its score inputs; make that path request `pool="chain"`.
- [ ] **Step 2**: generate the disclosure: for each running theory, `credibility`/`ranked_edge` inputs under `pool="version"` vs `pool="chain"`, printed as a table. With every historical bump backfilled `breaking` (Task 6 not yet run — order note below) the two columns are identical today; the table proves that and the commit message says so. Save the table into the task report and the closing log entry.
- [ ] **Step 3: Commit** — `feat: ranking reads chain-pooled evidence; before/after disclosure shows zero movement today (spec 2.5)`

**Order note:** Task 5 runs after Task 6's backfill so the disclosure reads real rows, not an empty table.

---

### Task 6: backfill + conventions test — **partially GATED on the peer**

- [ ] **Step 1 (backfill, not gated)**: one-off script step against the live DB: for each theory, `INSERT OR IGNORE` rows `(theory_id, v, 'breaking', v-1 or NULL, 'pre-dates the carry ruling; not adjudicated', NULL, utcnow())` for v in 1..current_version (spec §2.6 — enumerate versions, never mine rows; `structural_arb` v3 has no rows and still gets one). Then `python -m tools.cli state` — THEORIES panel's chain column may now light up; verify it renders.
- [ ] **Step 2 (GATED on peer clearing tests/test_conventions.py)**: append the belt-and-braces conventions test (spec §10): read-only against the live DB, skip-if-missing — every `theory_versions` row with `kind='carry'` has a non-null `equivalence_run`, and every running theory's current version has a `theory_versions` row.
- [ ] **Step 3: Commit** — `feat: theory_versions backfill (all historical bumps breaking) + conventions guard (spec 2.6)`

---

### Task 7: closeout

- [ ] Full suite; `python -m tools.cli rulings list` — nothing to flip here (the carry ruling is spec-borne, not in the rulings backfill); message the peer, then append the phase-6 log entry (chain machinery live; all history `breaking`; first real `prove_carry` candidate is `insider_judgment` v3→v4, expected `breaking` per spec §2.8 — that proof is research work, not this plan's).
