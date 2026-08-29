# Enforcing surfaces: making the rules bind

Two halves. **§1–6** give an enforcing surface to five norms `CLAUDE.md`
states but nothing checks. **§7** addresses the other ~30 rules, which are
fine as written and simply arrive at the wrong moment — by loading them where
they bind, deleting none of them.

**Date:** 2026-08-29. **Status:** design proposed, implementation not started.
**Scope:** `tools/` + `db/schema.sql` + ~370 net new words in `CLAUDE.md`,
substantial additions to four skills, plus a one-time migration of
`RESEARCH_LOG.md` (§6).
**Base:** `ff4318a` (registered slices). `CLAUDE.md` is 6,388 words as of that
commit; every budget below is against it.
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
| Net new words in `CLAUDE.md` | **≤ 370** (5.8% of the current 6,388) |
| New top-level `CLAUDE.md` sections | **0** — every edit lands inside an existing section |
| Rules **removed** from `CLAUDE.md` | **0** — and removal needs per-rule user approval (§7.7) |
| New doctrine | **1** — §7.5's skill-invocation rule, flagged as such |
| Deletions offsetting the additions | 2 (§3.4, §6.7) — both rewrites in place, no rule lost |

For §1–6 the unifying observation is that **every defect is a norm `CLAUDE.md`
already states, which has no surface that makes omitting it impossible.** The
document names the correct pattern itself, in the provenance section:

> After that `record_opportunity` **refuses** to write a row for a run with no
> provenance — the omission is made impossible rather than discouraged.

That is the template. Five norms have not received it yet. Nothing in §1–6 asks
an agent to believe anything new; each item takes a sentence that is already
law and gives it a table, a refusal, or a test.

§7 is the one place this spec adds doctrine rather than enforcement, and it
does so to make the *existing* rules land at the right moment. It removes
nothing.

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

### 1.7 Registered slices are the natural choke point (added after `ff4318a`)

`ff4318a` landed registered slices, and `CLAUDE.md`'s mining paragraph now
names slice registration as the concrete pre-registration act for a mined
pattern. That is exactly the boundary §1.4 was looking for: **the moment a
pattern gets registered is the moment its question count is knowable**, and
registration is already mandatory for a mined slice to earn ranking evidence.

`theory_slices.origin` carries the provenance today as prose. Two additive
columns turn it into the counted surface:

```sql
ALTER TABLE theory_slices ADD COLUMN window_slug TEXT REFERENCES data_windows(slug);
ALTER TABLE theory_slices ADD COLUMN n_examined INTEGER;   -- partitions considered before this one was chosen
```

`n_examined` is the honest denominator — "this cell was the best of 16" is the
fact that makes a Wilson bound readable, and it is currently recoverable only
by reading a study. `slices register` prompts for it; `segment_report` prints
it beside the slice's edge. No behaviour changes, and `hypothesis_tests` rows
can be written by `slices register` rather than by a separate call an agent
must remember.

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

### 2.8 Slice segments pool across a carry-chain too (added after `ff4318a`)

Slices are per-version like scores, so they inherit this defect exactly.
`slices.segment_report` moves to the same `pool="version" | "chain"` switch as
`compute_score`, defaulting to `"version"`. Under a *proven* carry, a
predecessor's segment pools into its successor mechanically instead of being
cited by a rule someone has to remember.

**`insider_judgment` v3→v4 is the natural first `prove_carry` target, and its
own record says it will prove `breaking`.** Three divergences, each
individually fatal to exact reproduction (raised by session 9a, verified
against the theory's files):

1. **v4's gate reads resolution rules**, not ticker prefixes — 130 survivors →
   18 (`NOTES.md` 2026-08-29 "defect 3 closed"; `THEORY.md` Version 4(a)).
   Eligibility is decided differently for most v3 events.
2. **v4 changed bucket pricing semantics** — "a bucket contributes an edge, not
   a probability" (`NOTES.md` 2026-08-29). `edge_pts_net` and `edge_basis`
   move on judged rows even where the verdict would not.
3. **The ratified v4 procedure is NO-side-only with award families gated**
   (`THEORY.md` Learnings 2026-08-26). Every v3 YES row is decided
   differently — not proposed at all.

**This is the mechanism working, not failing.** `breaking` is the
epistemically correct answer here: v3's slice evidence backs v3's procedure,
and v4's segment is already accruing its own rows and flips on at 10
out-of-sample clusters / 5 days. The section earns its place by making that
verdict *mechanical and recorded* rather than a judgement call — but the spec
must not predict the outcome of its own proof, which is what an earlier draft
of this subsection did.

Scope note: only half the current disclosure is manual. `slices match` at v4
already returns the below-gates annotation and empty rank inputs; it is the
"also cite v3" half that is hand-maintained.

**Considered and deferred: segment-scoped carry.** A narrower rule — exact
reproduction proven over slice-matched rows only, rather than the whole
procedure — is the obvious refinement, and it does not help here either: v4's
gate change alters which events reach judgment, so even the slice's populations
differ across the bump. Recorded so a future session does not re-derive it;
left unspecified until a candidate case actually needs it.

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

## 6. The log carries theory-local content, and the rule against it is four days old

### 6.1 The problem, measured

`RESEARCH_LOG.md` is **64 entries / 24,812 words**. Theory notebooks already
hold **16,896 words across 7 files** — `insider_judgment` 4,332,
`structural_arb` 4,316, `calibration_harvest` 4,293, `deadline_drift` 1,608,
`no_side_premium` 1,517, `mention_family` 556.

So the defect is **not** that theories fail to keep notebooks. They keep them.
The log is 24,812 words *in addition*, and `CLAUDE.md` already forbids the
duplication:

> `RESEARCH_LOG.md` stays cross-theory: when a session's work sits inside one
> theory, the log entry is a pointer to that theory's `NOTES.md` entry, **not a
> copy of it**.

Every entry is classified, per row, in the companion file
`2026-08-29-enforcing-surfaces-log-classification.md` — the migration acts on
that table, not on this summary, so any single row can be disputed:

| class | entries | words | share |
|---|---:|---:|---:|
| **T** — theory-local; belongs in a `NOTES.md` | 22 | 9,484 | 38% |
| **M** — theory work carrying a repo-level fact | 14 | 5,958 | 24% |
| **X** — cross-cutting: architecture, tooling, governance | 28 | 9,370 | 38% |

*(Measuring turned up a formatting defect worth fixing on the way through:
**three headings are written as two consecutive `## ` lines**, so every
heading-based count of this file — including the "66 entries" figure this spec
quoted before the table existed — is wrong until they are joined.)*

**The M column is the whole risk of this migration**, and it is a quarter of
the log. Those entries look theory-local and are not: the ~60-day Kalshi
archive limit, settlement-day clustering confounding both live theories, the
Holm + event-clustering precedent, the politics retraction, the version-bump
gap that produced §2 of this spec. Moved wholesale into a notebook, each
becomes exactly what `CLAUDE.md` names as broken:

> A theory whose true status is discoverable only by reading its `NOTES.md` has
> broken that surface, and the fix is distillation upward.

### 6.2 This reverses a prior decision, deliberately

`docs/superpowers/plans/2026-08-25-theory-locality.md` §22 decided the
opposite:

> **No migration of existing notes.** Content already in `THEORY.md` Learnings
> and `RESEARCH_LOG.md` stays exactly where it is; the convention is
> forward-only and the seeded `NOTES.md` files point at the old locations
> rather than absorbing them.

That was a reasonable call on 2026-08-25 — migration is risk, and forward-only
is free if the convention holds. **It did not hold.** Of the 44 entries written
*after* the locality convention landed, **16 are pure theory-local, totalling
5,838 words** (plus 11 mixed at 4,616). Four days, one convention, 5,838 words
of the exact thing it forbade.

That is the evidence that this is not a discipline problem to be solved by
restating the rule a third time. Forward-only was tried and produced 5,838
words of the thing it forbade.

### 6.3 Why it failed: the incentive, not the rule

The log is what the next session reads — `CLAUDE.md` says "read its tail" and
the `go` skill says "the last ~30 lines". A pointer does not get read; a copy
does. Every session therefore chooses between following the rule and being seen
by the next session, and picks being seen. That is rational, not sloppy.

**So the promotion bar cannot be the first change.** Raise the bar while the
log is still the only thing read at orientation, and sessions will either
violate the higher bar or lose their work into files nobody opens. §3's `state`
surface is the prerequisite: once orientation reads the DB and theory notes,
writing to `NOTES.md` becomes the way to be seen, and the bar costs nothing to
hold because nobody wants to write to the log anyway.

### 6.4 Three documents, currently two files

The log fuses two things with opposite growth requirements:

| | grows | read | bounded by |
|---|---|---|---|
| **Journal** (`RESEARCH_LOG.md`) | forever, harmlessly | on demand, for one entry's reasoning | nothing — and that is fine |
| **Canon** (`rulings` + `theory_facts` + `state`) | slowly | every session, whole | supersession — entries drop out |
| **Notebook** (`NOTES.md`) | per theory | when working that theory | the theory's own lifetime |

The problem was never that the journal is big. **It is that the canon is
embedded inside the journal**, so reading the canon requires reading the
journal. Extract the canon and a 200 KB journal is harmless.

### 6.5 Two rulings this section needs — *proposed, not decided here*

Per the standing delegation, both go to the supervisor session as one packet.

**Ruling 1 — reverse `2026-08-25-theory-locality.md` §22.** Raised by session
9a: §22 is a documented decision, and reversing it must be *ruled on*, not
inherited implicitly by shipping a migration that contradicts it. The case is
§6.2 — forward-only produced 5,838 words of the thing it forbade across 44
entries in four days. If the ruling goes the other way, §6.6 does not run and
§6.7's `CLAUDE.md` edit stands alone as a forward-only restatement with the
`state` surface behind it.

**Ruling 2 — the promotion bar.** Proposed wording, so there is something
concrete to rule on:

> **A log entry is earned by a fact that changes how a session that never
> touched this theory would act.** Everything else is a pointer. Concretely, an
> entry is warranted for: a repo-level mechanism or defect; a ruling; a
> methodological precedent; a data-source constraint; a cross-theory finding; a
> correction to something previously published. A result inside one theory is a
> one-line headline plus a pointer into that theory's `NOTES.md` — never the
> narrative, the tables, or the numbers, which live in the notebook and the
> ledger.

The test case already exists: `ff4318a`'s own entry is cross-cutting (a new
repo-wide mechanism) with theory-local numbers distilled to a headline plus a
pointer. It passes the proposed bar as written, which is the cheapest available
evidence that the bar is not too strict to comply with.

### 6.6 The migration

**T entries** move to the owning theory's `NOTES.md`, in date order, verbatim —
the notebook is append-only and raw, so nothing is rewritten or summarised on
the way in. The owner is the companion table's `owner` column, recorded per
row; the one entry spanning two theories (2026-08-24 "Two follow-ups") moves
whole to the majority owner, with a dated pointer in the other notebook, per
that row's pairing note.

**M entries** split: the repo-level fact is extracted upward into `rulings`,
`theory_facts`, or a one-paragraph log entry; the theory narrative moves to the
notebook. **This is the only judgement-bearing step in the migration**, so it
is done one entry at a time with the extraction written down, never in bulk.
A row whose owner is a `studies/` folder splits the same way, with the study's
own write-up as the notebook-equivalent — those entries are study work, and no
theory `NOTES.md` exists to receive them.

**X entries** stay. Entries appended after `ff4318a` are classified under the
same legend into the companion file's addendum before anything moves; the
table pins its revision, the log does not stop.

**Every moved entry leaves a stub at its original anchor** — date, heading, and
the pointer to where the content went. The journal stays append-only and its
line numbering stays meaningful; a stub is an edit *in place*, not a deletion.

**A correction never separates from its target.** The 2026-08-29 politics
correction retracts its target *by position* ("the entry two above") — exactly
the reference a stub silently falsifies. A correction's narrative lands
adjacent to wherever its target landed, in date order, never in a different
file, and its stub names the target by date and heading, not position. The
companion table's pairing notes bind the known pair.

#### The citation sweep (flagged by session 9a — do this first, not last)

Prose citations point *into* the content being moved, and unlike
`prompt_path`, nothing test-enforces them. Known classes:

- `theory_slices.origin` — cites `THEORY.md Learnings 2026-08-26` and
  `backtests/<run>/RESULTS.md` (confirmed present on
  `insider_judgment/strong-moderate-no`).
- `judgment_runs.prompt_path` — test-enforced already, but repointing rules
  apply if a prompt moves with a notebook.
- `NOTES.md` / `THEORY.md` entries cross-citing each other **by date**, which
  a move silently breaks because the date still exists somewhere else.
- `docs/superpowers/plans/*` and `docs/DEDUP_PLAN.md`, which cite log content
  by description.
- Positional cross-references *within the log itself* ("the entry two above"),
  which the dated-citation grep cannot see. Four instances enumerated in the
  companion file; only the politics correction crosses a move boundary.

Sweep before moving anything:

```bash
grep -rn 'THEORY.md Learnings\|NOTES.md 20\|RESEARCH_LOG' --include='*.md' --include='*.py' .
grep -n 'entry above\|entry two above\|entries above\|see above' RESEARCH_LOG.md
python -m tools.cli slices list --show-origin
```

Then the durable guard, in the idiom of
`test_every_recorded_prompt_path_still_resolves`: extend §5.1's docs-path test
to assert that every `theory_slices.origin` and every dated cross-citation
names a file that exists **and still contains that date heading**. A stub
satisfies it; a silent move does not.

### 6.7 `CLAUDE.md` edit (net ≈ 0 words, inside "What lives in a theory")

The existing sentence is edited in place, not appended to:

> `RESEARCH_LOG.md` stays cross-theory: a log entry is earned by a fact that
> changes how a session that never touched this theory would act — a mechanism,
> a ruling, a precedent, a constraint, a correction. A result inside one theory
> is a headline and a pointer into its `NOTES.md`, never a copy. This was
> forward-only from 2026-08-25 and produced 5,838 words of copies anyway,
> because the log was what got read; it binds now because `state` is.

**This is the second offsetting deletion.** It replaces the existing
pointer-not-copy sentence rather than adding to it.

---

## 7. Rule delivery: load the rule where it binds, delete nothing

### 7.1 The problem, stated correctly

`CLAUDE.md` is 6,388 words carrying ~36 rules. **6,388 words is ~8k tokens —
that is not a context problem**, and any version of this section justified by
load cost is solving the wrong thing.

The cost is **dilution**. Rules compete for attention inside one document that
is read once, at session start, whatever the session turns out to do. A rule
about structural-gate conditions is read by a session that will never
backtest, and — the part that matters — is read *hours before* the session
that will backtest reaches the moment it binds.

So the target is not a shorter file. It is: **every rule is in front of the
model at the moment it is about to violate it.**

### 7.2 The principle: relocation, never deletion

These rules are hard-won. Most exist because something went wrong once, and
the hedges inside them are scar tissue from specific misreadings. **Nothing in
this section removes a rule, and no rule leaves `CLAUDE.md` without explicit
per-rule approval from the user** (§7.7).

That flips the earlier framing in this spec's own out-of-scope list. The
question is not "what can be cut to raise rule density" — it is "what can be
*additionally delivered* at the point of use." **Duplication is acceptable and
often correct here**: a rule may live in `CLAUDE.md` *and* be restated inside
the skill that owns the activity. The redundancy costs tokens; a rule that
fails to bind costs a contaminated track record. That trade is not close.

### 7.3 Three tiers, by how a rule binds

| tier | what it is | where the text lives |
|---|---|---|
| **Enforced** (13) | code refuses or a test fails | `CLAUDE.md` keeps the rule; the *argument* may move. The enforcement already teaches it |
| **Constitutional** (~9) | unenforceable, always binding, disaster if violated unaware | `CLAUDE.md`, in full, with worked examples — untouched |
| **Task-time** (~15) | unenforceable, binds during one activity | `CLAUDE.md` **and** the owning skill, quoted verbatim (§7.6) |

**Enforced:** 1 ticker, 2 provenance, 5 basket, 6 arb-scoring, 9 Verdict,
16 retirement, 21 `finish()`, 22 sibling imports, 23 contract, 26 prompts on
disk, 27 `exp/` runs, 28 one board, 34 slice registration.

**Constitutional:** 3 `edge_basis`, 4 record rejections, 7 ask-not-mid,
8 never introspect, 14 version bump, 15 status is evidence, 25 no backtest
engine, 31 SQLite is truth, 33 ranking formula.

**Task-time, by owner:**

| skill | rules |
|---|---|
| `backtest-theory` | 13 web search off, 19 structural-gate five conditions, 20 record the tier claim |
| `find-edge` | 10 judge blind, 11 buckets from the deep stage only, 12 batch and dedupe |
| `propose-theory` | 17 facts are data, 35 search the registry, 36 record with a `revisit_angle` |
| `go` | 32 notes/theory/log split |
| `score-theories` | 18's *reading* half — what a tier means when trusting a number |
| (none yet) | 24 elevate at 2+ callers, 29 raw payloads, 30 record incrementally |

### 7.4 The test that decides constitutional vs task-time

**Would violating this rule while the owning skill is not loaded be a
disaster?** If yes, it is constitutional regardless of which activity it
mentions. Skills are discretionary; `CLAUDE.md` is guaranteed.

Two rules look task-time and fail the test, which is why the test earns its
place:

- **25 — no shared backtest engine.** Reads like a backtesting rule. The
  moment someone builds one is during a *refactor*, when `backtest-theory` is
  not loaded. Constitutional.
- **18 — tier definitions.** Reads like a backtesting rule. But tiers are
  *read* when ranking, reporting and deciding what to trust. The definitions
  stay constitutional; only the five structural-gate conditions (19) are
  task-time.

### 7.5 The skill-invocation rule — **new doctrine, flagged as such**

Relocation is only safe if the skill actually loads. So `CLAUDE.md` gains one
rule that is genuinely new rather than an enforcement of something already
written:

> **When a task has a skill, invoke it before starting.** Backtesting →
> `backtest-theory`. Choosing bets → `find-edge`. New hypothesis →
> `propose-theory`. Settling and scoring → `score-theories`. Comparing →
> `compare-theories`. A session → `go`. The skills carry rules this file does
> not repeat, loaded at the moment they bind. **Prefer loading a skill to not
> loading one**: the cost of reading one you did not strictly need is a few
> hundred tokens, and the cost of skipping one is a rule you never saw.

This is the only new doctrine in this spec, and it breaks §0's "0 new
doctrine" budget line deliberately. It is also load-bearing: without it, §7.3
moves rules into documents that may never open.

### 7.6 Anti-drift: quoted blocks, checked by a test

Duplication's failure mode is divergence — two copies of a rule that no longer
say the same thing, with nothing to say which governs.

So a task-time rule restated in a skill is **quoted, not paraphrased**, inside
a marked block naming its `CLAUDE.md` anchor:

```markdown
<!-- rule: structural-gate-conditions (CLAUDE.md § Backtest tiers) -->
> A judging stage is structural — and does not cost tier A — only when all
> of the following hold...
<!-- /rule -->
```

New in `tests/test_conventions.py`, in the idiom of
`test_every_recorded_prompt_path_still_resolves`:

```python
def test_every_quoted_rule_matches_its_source():
    """A skill that quotes a CLAUDE.md rule must quote it exactly. Two
    copies that disagree are worse than one copy nobody read: nothing
    says which governs. Fails at the commit that forks them."""
```

That makes duplication safe, which is what lets §7.2 prefer it.

### 7.7 What requires explicit approval

- **Removing any rule from `CLAUDE.md`** — per rule, from the user, never in
  bulk and never as a side effect of relocation. The default outcome of this
  section is that `CLAUDE.md` gets *slightly longer* (§7.5's rule) and the
  skills get substantially longer.
- **Consolidating the prefer-mechanical argument** (lines 38, 73–75, 297,
  546–551, 596 — five statements with separately accumulated hedges). This is
  a rewrite of existing text, not a relocation, so it is proposed and not
  performed: state it once, completely, with all four hedges, and leave
  pointers. Needs approval because a hedge dropped in the merge is a rule
  silently weakened.
- **Any change to the `Subset edges` subsection** — session 9a's text (§8).

### 7.8 `CLAUDE.md` edit (≈120 words — §7.5's rule, inside "How the user drives this")

Net additive. §7.3's relocations add nothing to `CLAUDE.md` and subtract
nothing from it; only the skills grow.

---

## 8. Explicitly out of scope

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
  and this spec does not treat it as such — §7 explicitly removes nothing and
  expects the file to get slightly *longer*.
- **Consolidating the prefer-mechanical argument** (lines 38, 73–75, 297,
  546–551, 596). Proposed in §7.7, deliberately not performed: it is a rewrite
  of existing text rather than a relocation, and a hedge dropped during the
  merge is a rule silently weakened. Needs the user's approval first.
- **The `Subset edges — registered slices` subsection of `CLAUDE.md`**
  (`ff4318a`, line 331). Session 9a owns that text; §1.7 and §2.8 above add
  columns and a pooling switch around it and reword none of it. If the §6.5
  bar, once ruled, would require changing it, that goes back to 9a first.

---

## 9. Sequencing

Each phase is independently shippable and independently useful.

| Phase | Contents | Why this order |
|---|---|---|
| 1 | §5.1 hygiene, §4.2 `--ticker`, §3.2 `state` | Zero doctrine, zero schema risk, immediate orientation payoff |
| 2 | §3.3 `rulings` + backfill | Makes the four buried rulings survivable before the next session loses them |
| 3 | §6.6 citation sweep + the citation test | Read-only; must precede any move, and is useful even if the migration never runs |
| 4 | §6.6 T-entry migration + stubs | Mechanical once the sweep is clean; 22 entries / 9,484 words, no judgement |
| 5 | §6.6 M-entry split, one at a time | The judgement-bearing quarter; only safe once `rulings` (phase 2) exists to receive the extractions |
| 6 | §2 carry/breaking + backfill + `rank`/`segment_report` disclosure | The evidence bleed; largest payoff, needs the disclosure precedent |
| 7 | §1 question budget + §1.7 slice columns | Needs windows registered, easiest once `state` renders them |
| 8 | §5.2 DB split | Pure operations; safe to defer, unsafe to defer indefinitely |
| **A** | §7.5 skill-invocation rule + §7.6 quoted-rule test | **Independent of everything above — ship first if desired.** The rule is worthless until the test makes duplication safe, so they land together |
| **B** | §7.3 task-time rules quoted into `backtest-theory`, `find-edge`, `propose-theory`, `go`, `score-theories` | One skill per commit, each verified by the §7.6 test. No `CLAUDE.md` change, so it cannot regress the guaranteed layer |
| — | §6.5 rulings 1 & 2 (§22 reversal, promotion bar) | **Blocked on the supervisor.** Ruling 1 gates phases 4–5; ruling 2 also gates on phase 1, per §6.3 |
| — | §4.3 paper lane | Blocked on the user's ruling |

Phases 3–5 are the migration. **Phase 1 gates all of them** (§6.3): raising the
bar or emptying the log before `state` exists just moves work into files nobody
reads.

## 10. Testing

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
- Extended docs-path test (§6.6) — every `theory_slices.origin` and every dated
  cross-citation names a file that exists *and still contains that date
  heading*. A stub passes; a silent move fails. This is the migration's only
  real safety net, and it must land **before** phase 4.
- New `test_every_quoted_rule_matches_its_source` (§7.6) — a skill quoting a
  `CLAUDE.md` rule must quote it exactly; the test fails at the commit that
  forks the two copies. This is what makes §7.2's deliberate duplication safe,
  and it must land **with** phase A, not after it.

## 11. What this spec does not change

The mission, the theory contract, `finish()` as the ledger boundary, the
credibility formula, the tier definitions, the no-introspected-probability
rule, the ranking arithmetic, `edge_basis`, the disposition vocabulary, "only
the user retires a theory", or the size and voice of `CLAUDE.md`.

`RESEARCH_LOG.md` in particular **stays append-only and stays the audit
trail**. §6 moves content out of it and leaves a stub at every anchor; it does
not compress it, rewrite it, delete from it, or cap its growth. A journal is
supposed to grow. The change is that the canon stops living inside it.

**And no rule is removed from `CLAUDE.md`.** §7 relocates *delivery*, never
authority: a task-time rule is restated in the skill that owns the activity
*in addition to* remaining where it is, held identical by a test. Every rule in
that file was paid for by something going wrong once; none of them is cut here,
and cutting one later needs the user's approval, per rule (§7.7).

Five sentences the document already contains get a table, a refusal and a test.
One rule is added, so the other thirty arrive when they matter. That is the
whole change.
