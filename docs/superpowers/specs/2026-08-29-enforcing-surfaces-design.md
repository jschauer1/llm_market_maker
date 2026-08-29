# Enforcing surfaces: four norms that exist only as prose

**Date:** 2026-08-29. **Status:** design proposed, implementation not started.
**Scope:** `tools/` + `db/schema.sql` + ~170 net new words in `CLAUDE.md`.
**Non-goal:** changing what this project believes.

---

## 0. The constraint this design is built around

`CLAUDE.md` is large on purpose. It is not documentation — it is the runtime
for a fleet of agents that will never meet each other, and its size buys
behavioural consistency across sessions that share no context. Rewriting it is
not a refactor; it is a change of governing law, and narrative drift there is
more expensive than any defect listed below.

So this spec adopts a hard budget and honours the repo's own construction rule
— **a rule states the behaviour and the reason, in that order**:

| Constraint | Value |
|---|---|
| Net new words in `CLAUDE.md` | **≤ 170** (2.9% of the current 5,902) |
| New top-level `CLAUDE.md` sections | **0** — every edit lands inside an existing section |
| New doctrine | **0** — every item below enforces a rule the document already states |
| Deletions offsetting the additions | 1 (§3.4) |

The unifying observation is that **every defect here is a norm `CLAUDE.md`
already states, which has no surface that makes omitting it impossible.** The
document names the correct pattern itself, in the provenance section:

> After that `record_opportunity` **refuses** to write a row for a run with no
> provenance — the omission is made impossible rather than discouraged.

That is the template. Four norms have not received it yet. Nothing below asks
an agent to believe anything new; each item takes a sentence that is already
law and gives it a table, a refusal, or a test.

---

## 1. The question budget

### 1.1 The problem

`CLAUDE.md` requires multiple-comparison awareness:

> ...with honest p-values, event-clustered checks, and multiple-comparison
> awareness, before concluding nothing is there.

Clustering got a surface (`n_clusters`, `clustered_se`, a schema ruling, a
test). Multiple comparisons got a word. **Nothing in the repo counts how many
questions have been asked of the same data.**

The count is not small. Ten `studies/` folders, five theories, and every
slicing pass in the corpus have been run against essentially one Kalshi
settled-history window (~60 days reachable) and one board. The per-study
discipline is real and the pairing rule is honoured *within* a study; what is
missing is any figure for the corpus. The family-wise error rate of this
project is currently unknown and structurally unknowable.

This is not hypothetical here. The corpus already contains one confirmed
instance of the exact failure this would catch: idea 2's retracted
long-vs-short contrast was **the best of three split points**, reported as
pre-registered. Peer review caught it. That is luck, not a system.

### 1.2 What is deliberately *not* proposed

**No change to the credibility formula.** `ranked_edge = edge_pts_net ×
credibility` is doctrine, it is quoted in the README and three skills, and
bolting a Šidák correction onto it would be exactly the narrative shift this
spec exists to avoid. Phase 1 counts and discloses. Binding the count
numerically is a later ruling with its own evidence, not this one.

### 1.3 Schema

```sql
CREATE TABLE data_windows (
    slug          TEXT PRIMARY KEY,       -- 'kalshi-settled-2026-06-22-to-08-25'
    source        TEXT NOT NULL,          -- 'kalshi_settled' | 'board_snapshots' | ...
    close_start   TEXT,                   -- UTC ISO-8601, nullable for snapshot windows
    close_end     TEXT,
    population    TEXT NOT NULL,          -- prose: what filter defines membership
    created_at    TEXT NOT NULL
);

CREATE TABLE hypothesis_tests (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    window_slug    TEXT NOT NULL REFERENCES data_windows(slug),
    asked_by       TEXT NOT NULL,          -- study dir, theory_id, or backtest run_id
    hypothesis     TEXT NOT NULL,          -- the claim, one sentence
    pre_registered INTEGER NOT NULL,       -- 0/1
    registered_at  TEXT,                   -- commit SHA or ISO-8601; required when pre_registered=1
    outcome        TEXT,                   -- 'supported' | 'failed' | 'inconclusive' | NULL if open
    notes          TEXT,
    created_at     TEXT NOT NULL
);

ALTER TABLE backtest_runs ADD COLUMN window_slug TEXT REFERENCES data_windows(slug);
```

Additive only. `window_slug` is nullable so the eight historical
`backtest_runs` rows stay valid and are never rewritten — the same treatment
`n_clusters` received.

### 1.4 The refusal

`ledger.record_backtest_run()` gains a required `window_slug`. This is the
narrow analogue of `record_opportunity` refusing a row with no Kalshi ticker:
one boundary, one field, no judgement involved. Studies are not ledger writes,
so they get a CLI call plus a conventions test rather than a refusal.

```bash
python -m tools.cli windows register <slug> --source kalshi_settled \
    --close-start 2026-06-22 --close-end 2026-08-25 --population "<filter>"
python -m tools.cli windows list
python -m tools.cli questions ask <window-slug> --by <study-or-theory> \
    --hypothesis "<one sentence>" [--pre-registered --at <sha>]
python -m tools.cli questions count <window-slug>
```

### 1.5 The disclosure

`score.compute_score()` gains two keys, computed not asserted:

- `window_slug` — the window the settled rows came from, where derivable.
- `questions_asked_of_window` — `SELECT COUNT(*) FROM hypothesis_tests WHERE
  window_slug = ?`.

`score report` prints them. `find-edge` and `compare-theories` print one line
when the count exceeds 5:

> `window kalshi-settled-2026-06-22-to-08-25: 23 questions asked. A nominal
> p=0.05 on this window is not a 5% false-positive rate.`

Blunt, factual, unmissable, and it changes no number.

### 1.6 `CLAUDE.md` edit (≈80 words, inside "An underperforming theory is a research object")

Appended to the paragraph that already ends with the pairing discipline:

> **And count the questions.** Every slicing pass, study and backtest registers
> what it asked of which data window (`questions ask`), because a corpus that
> has asked one window twenty questions has a nominal p=0.05 that means
> nothing, and no session can see that from inside its own study. The count is
> disclosed beside every score; it does not yet adjust one. Idea 2's retraction
> is the instance this exists to catch without luck.

---

## 2. Version bumps outrun settlements

### 2.1 The problem

Measured 2026-08-29 against `db/market_edge.db`:

| theory | registry version | rows at that version | settled |
|---|---|---|---|
| `insider_judgment` | 4 | 35 | 0 |
| `calibration_harvest` | 2 | 10,269 | 0 |
| `structural_arb` | 4 | 0 | 0 |
| `no_side_premium` | 1 | 137 | 46 |
| `mention_family` (retired) | 1 | 3,476 | 3,464 |

Three of five running theories score `n=0`. `structural_arb` has been bumped
twice past every row it has ever recorded. `score report insider_judgment`
returns nulls across the board while 96 settled rows sit in the table at v3.

The versioning rule is correct and must not be weakened — it is the only thing
standing between this project and tuning until the history looks good. But it
currently treats **every** change as decision-altering, so a theory can never
accumulate evidence while it is still being improved, and improvement is most
of what happens in week one.

### 2.2 The principle

The rule's stated purpose is precise:

> Without this, tweaking a theory silently merges two different theories into
> one track record.

A merge is only silent if it is *unproven*. A change that provably could not
have altered the decision for already-recorded rows merges nothing — it is the
same theory with better plumbing. The fix is not to relax the bump; it is to
**make the claim of harmlessness checkable, and refuse it when unproven.**

Version numbering is untouched. Every change still bumps. What is added is a
declared, *evidenced* relationship between consecutive versions.

### 2.3 Schema

```sql
CREATE TABLE theory_versions (
    theory_id       TEXT NOT NULL,
    version         INTEGER NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('breaking','carry')),
    predecessor     INTEGER,                -- NULL for v1
    justification   TEXT NOT NULL,
    equivalence_run TEXT,                   -- REQUIRED when kind='carry'
    created_at      TEXT NOT NULL,
    PRIMARY KEY (theory_id, version)
);
```

- **`breaking`** — the decision path changed. Track record resets. This is the
  default and stays the default; an agent that does not think about it gets
  today's behaviour exactly.
- **`carry`** — the change cannot alter the decision for prior rows. Evidence
  carries forward across the bump.

### 2.4 `carry` must be proven, never asserted

`theories.bump_version(..., kind="carry")` **refuses without an
`equivalence_run`**: a replay of the new code over a pinned fixture of the
predecessor version's recorded rows, which must reproduce every one of
`disposition`, `outcome`, `entry_price`, `edge_pts_net` and `edge_basis`
exactly. Any single divergence makes the bump `breaking`, whatever the author
intended.

This is the load-bearing half. Without it `carry` becomes a self-granted
exemption and reintroduces the silent merge through the front door.

Reference implementation: `tools/theories.py::prove_carry(conn, theory_id,
from_version, theory_instance) -> EquivalenceResult`, replaying against
`opportunity_attempts` rows at `from_version` using each attempt's stored
`decision_date` and `entry_price`, so no fresh board is needed and the proof is
reproducible offline.

### 2.5 Scoring across a carry-chain

`score.compute_score()` gains `pool="version" | "chain"`, defaulting to
`"version"` — **today's behaviour is the default and no existing caller changes
meaning.** Under `"chain"` the segment filter widens to the maximal run of
consecutive versions linked by `carry` ending at the requested version.
`breaking` terminates a chain.

Output gains `chain_versions: [3, 4]` whenever more than one version
contributed, so a pooled number can never be read without seeing what was
pooled. `rank.py` moves to `pool="chain"` in the same commit, with the
disclosure the clustering ruling established as precedent: **the full
before/after ranked-edge table for every theory, and explicit callout of any
probation flip.**

### 2.6 Backfill

The five existing theories' historical bumps are **not** retro-classified by an
agent. Every pre-existing `(theory_id, version)` gets a row with
`kind='breaking'` and `justification='pre-dates the carry ruling; not
adjudicated'`. If a past bump was genuinely a carry, it can be proven later by
running `prove_carry` against the fixture — evidence, not recollection. Nothing
is rewritten in place.

### 2.7 `CLAUDE.md` edit (≈90 words, inside "Theory lifecycle and versioning")

Appended after the existing bump paragraph:

> **A bump declares whether it breaks the track record.** `breaking` is the
> default and resets it. `carry` — for a change that provably could not alter
> the decision on rows already recorded — keeps it, and is refused unless a
> replay over the predecessor's own attempts reproduces every recorded decision
> exactly. Assertion does not qualify; the proof is the permission. This does
> not soften the bump rule, it makes the rule affordable: a theory still being
> improved could otherwise never accumulate evidence, which is how three of
> five theories reached n=0.

---

## 3. Orientation has outgrown its surface

### 3.1 The problem

`RESEARCH_LOG.md` is 168 KB / 24,341 words across 66 entries. `CLAUDE.md` says
"read its tail when starting" and the `go` skill says "read the last ~30
lines". Thirty lines of a 66-entry log is now roughly the last two hours of one
session.

The consequence is not merely inefficiency. **Binding rulings are discoverable
only by reading the whole file.** The attempt-level scoring ruling, the
cluster-`n` schema ruling, the `bucket_rates` out-of-scope carve-out, and four
pending skill edits blocked on permissions all live as prose in the log tail.
An agent that reads thirty lines next week will not find them, and `CLAUDE.md`'s
own rule is explicit that this must not happen:

> ...any fact the repo level needs must surface in a shared structure.

The log is the audit trail and must stay append-only and unedited. What is
missing is the distillation the repo already requires of theories, applied to
the repo itself — and it should be **generated**, so it cannot drift.

### 3.2 `python -m tools.cli state`

One command, rendered from the DB, no hand-maintained file:

```
THEORIES     status · version · chain n · settled · next settlement
STANDING     pending retirements · open rulings · blocked items
EVIDENCE     per running theory: calibration_edge_net, n_clusters, tier
WINDOWS      each data window and its question count            (§1)
QUEUE        endorsed + untouched + unsettled, with age and close time
FRESHNESS    last board pull · last settle run · last mark-taken
```

Optionally written to `STATE.md` by `--write` for humans; that file is
gitignored, because a tracked generated file drifts the moment someone edits
it. The DB is the source of truth, as it already is for everything else
structured.

### 3.3 Rulings become rows

```sql
CREATE TABLE rulings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ruled_at  TEXT NOT NULL,
    authority TEXT NOT NULL,          -- 'user' | 'supervisor'
    subject   TEXT NOT NULL,          -- 'scoring' | 'schema' | 'lifecycle' | ...
    ruling    TEXT NOT NULL,
    scope_out TEXT,                   -- what was explicitly excluded
    status    TEXT NOT NULL,          -- 'binding' | 'implemented' | 'superseded'
    log_entry TEXT                    -- date heading in RESEARCH_LOG.md
);
```

`log_entry` points back at the narrative; the log keeps the reasoning, the row
carries the binding text. Backfill is the four rulings currently in the log
tail — a ten-minute job that is the whole payoff.

### 3.4 `CLAUDE.md` edit (net ≈ 0 words, inside "Data conventions")

The existing bullet is edited, not extended:

> - **`RESEARCH_LOG.md`** carries continuity between sessions — append when
>   finishing. It is append-only and now too large to read; orient with
>   `python -m tools.cli state`, which renders current state from the DB, and
>   read the log for the reasoning behind a specific ruling it names.

The `go` skill's "read the last ~30 lines" becomes the `state` call. **This is
the deletion that offsets §1 and §2.**

---

## 4. The realized-ROI loop is dead code

### 4.1 The problem

32,607 opportunity rows. `user_action='taken'` on **2**. `roi_taken` is `null`
for every theory, and the user-divergence signal `compare-theories` is built to
mine has never had an input.

Some of this is simply that the user places few bets, which is not a defect.
But part is friction the repo can remove: `mark-taken` requires an opportunity
id, which means first running a listing and reading it. Nobody does that after
placing a bet on their phone.

### 4.2 Friction removal (uncontroversial, do this regardless)

```bash
python -m tools.cli opportunities mark-taken --ticker KXFOO-26AUG29-T1 taken \
    --theory insider_judgment --size 25 --reason "<why>"
```

`--ticker` resolves to the most recent attempt on that ticker, printing what it
matched and asking for confirmation when more than one theory has an open
position on it. Same command, one less lookup.

Second: `state` (§3.2) reports days-since-last-`mark-taken` under FRESHNESS, so
a decaying loop is visible in every orient rather than discoverable only by
someone who thinks to query for it.

### 4.3 A paper lane — **open decision for the user, not proposed unilaterally**

A third `user_action` value, `paper`: a declared hypothetical fill at the
recorded ask, feeding a separate `roi_paper` that **never** contributes to
`roi_taken`, `calibration_edge`, or credibility.

- **For:** it exercises the divergence machinery, which is otherwise untested
  code that will be wrong the first time it carries real data.
- **Against:** `CLAUDE.md` is emphatic that the user places every bet and that
  `roi_taken` is the real signal. A lane that looks like betting without being
  betting is exactly the kind of thing that erodes a narrative by inches.

**Recommendation: yes, with the separation enforced in `score.py` rather than
by convention** — but this is the one item in this spec that touches what the
project *means*, so it should be the user's call and is written here as a
question, not a task. If the answer is no, §4.2 still stands and this section
is deleted.

### 4.4 `CLAUDE.md` edit

None for §4.2 — it is a CLI ergonomics change to a command the document already
documents. §4.3 needs ~40 words if adopted, and counts against the budget only
in that case.

---

## 5. Hygiene (no `CLAUDE.md` edits, no doctrine)

### 5.1 Doc drift, and a test that catches the next one

- `README.md` points at `docs/theory-specs/`, which does not exist. The real
  path is `docs/superpowers/specs/theories/`.
- `docs/DEDUP_PLAN.md` reads "implementation not started" for work that landed
  in `f6a1047`. It is already superseded by
  `2026-08-27-position-identity-design.md`; its header should say so.
- `migrate_kalshi_trader.py` (root) and `db/opportunities.json` (532 KB) are
  one-time migration artifacts still tracked at the top level, where they read
  as live entry points.

The durable fix is one conventions test, in the exact idiom of
`test_every_recorded_prompt_path_still_resolves`:

```python
def test_every_repo_path_named_in_docs_resolves():
    """A doc that names a path nobody can open is worse than no doc: it
    sends the next session somewhere that does not exist. Fails at the
    commit that breaks the path, not months later."""
```

Scanning `README.md`, `CLAUDE.md`, `tools/README.md` and every `THEORY.md`,
matching backticked strings that look like repo paths.

### 5.2 Split the snapshot store

`db/market_edge.db` is 5.5 GB, ~1.39M `market_snapshots` rows, growing ~200 MB
per board pull, **inside a OneDrive sync root**. The ledger — the
irreplaceable, small, frequently-written part — is a few tens of MB of that and
is currently hostage to it: every backup, copy and sync moves 5.5 GB to protect
30 MB.

Move `market_snapshots` to `db/snapshots.db`, `ATTACH`ed by
`tools/db.connect()` so every existing query keeps working unqualified. This
changes no policy: `CLAUDE.md`'s "save as much as you can, while you can" is
correct and snapshots stay complete and raw. It only stops the
precious-and-small file from inheriting the operational profile of the large
one, and lets the two have different backup cadences.

Add `python -m tools.cli db stats` (per-table bytes via `dbstat` — note the
module is not compiled into the current interpreter's SQLite, so fall back to
page-count estimation), and a WAL checkpoint on close.

Recommend to the user, cannot be done in code: exclude `db/` from OneDrive
sync.

---

## 6. Explicitly out of scope

- **Execution realism for `structural_arb`.** Already done, and better than
  this spec would have specified:
  `studies/2026-08-29-structural-arb-violation-liquidity/` replays the geometry
  over 11 snapshots, validates the v2 depth gate, and reports a tradeable
  firing rate of zero with a structural reason. No further work.
- **Peer review is model-correlated.** Real, but the fix is measurement first:
  record review passes as a `peer_review` stage in `provenance` with the
  reviewing model, and read the dissent rate after ~20 reviews. A review
  process that never dissents is decorative; one that dissents at a measurable
  rate has earned an argument about independence. Nothing to design until that
  number exists.
- **Adjusting credibility for the question budget** (§1.2).
- **`bucket_rates` clustering** — already carved out by a standing ruling.
- **Any rewrite of `CLAUDE.md` for length.** The document's size is a
  deliberate purchase of cross-session consistency. It is not technical debt
  and this spec does not treat it as such.

---

## 7. Sequencing

Each phase is independently shippable and independently useful.

| Phase | Contents | Why this order |
|---|---|---|
| 1 | §5.1 hygiene, §4.2 `--ticker`, §3.2 `state` | Zero doctrine, zero schema risk, immediate orientation payoff |
| 2 | §3.3 `rulings` + backfill | Makes the four buried rulings survivable before the next session loses them |
| 3 | §2 carry/breaking + backfill + `rank` disclosure | The evidence bleed; largest payoff, needs the disclosure precedent |
| 4 | §1 question budget | Needs windows registered, easiest once `state` renders them |
| 5 | §5.2 DB split | Pure operations; safe to defer, unsafe to defer indefinitely |
| — | §4.3 paper lane | Blocked on the user's ruling |

## 8. Testing

Every item ships with tests in the existing suite (986 passing, 64s):

- `test_conventions.py` — docs paths resolve (§5.1); every `carry` row has an
  `equivalence_run` (§2.4); every `backtest_runs` row created after the ruling
  names a `window_slug` (§1.4).
- `test_score_characterization.py` — `pool="version"` reproduces today's
  numbers exactly on both row generations, the way the `n_clusters` extension
  was covered.
- New `test_carry_chain.py` — a proven carry pools; an unproven one refuses; a
  single divergent attempt forces `breaking`; a `breaking` bump terminates a
  chain mid-run.
- New `test_question_budget.py` — count rises with registration, the disclosure
  line fires above threshold, `record_backtest_run` refuses without a window.
- New `test_state.py` — `state` renders from a fixture DB with no network.

## 9. What this spec does not change

The mission, the theory contract, `finish()` as the ledger boundary, the
credibility formula, the tier definitions, the no-introspected-probability
rule, the ranking arithmetic, `edge_basis`, the disposition vocabulary, "only
the user retires a theory", or the size and voice of `CLAUDE.md`.

Four sentences the document already contains get a table, a refusal and a test.
That is the whole change.
