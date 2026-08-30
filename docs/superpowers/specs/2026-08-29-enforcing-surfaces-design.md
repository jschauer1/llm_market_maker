# Enforcing surfaces: making the rules bind

Two halves. **§1–6** give an enforcing surface to five norms `CLAUDE.md`
states but nothing checks. **§7** addresses the other ~30 rules, which are
fine as written and simply arrive at the wrong moment — by moving each to
where it binds, losing none of them.

**Date:** 2026-08-29. **Status:** design proposed, implementation not started.
Reviewed and corrected against the live repo and DB the same day; eight
rulings were issued directly by the user during that review — §6.5's two,
the §4.3 no, the §5.2 phase-1 relocation, the §5.3 force floor, §7.7's
division-of-labour reframing (performed), §7.2's single-home relocation
of the task-time rules, and §7.9's expert-agent architecture. No questions
remain open in this document.
**Scope:** `tools/` + `db/schema.sql` + ~370 net new words in `CLAUDE.md`,
substantial additions to five skills, plus a one-time migration of
`RESEARCH_LOG.md` (§6).
**Base:** `ff4318a` (registered slices). `CLAUDE.md` was 6,388 words at that
commit; the §7.7 division-of-labour consolidation (user-ruled, performed
2026-08-29, `9770e0e`) has since taken it to 6,671. That change was outside
the budget below, which governs §1–7's own edits and applies against the
post-consolidation file.
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
| Net new words in `CLAUDE.md` | additions capped at **≤ 370**; with §7's relocation the *net* change is expected to be negative |
| New top-level `CLAUDE.md` sections | **0** — every edit lands inside an existing section |
| Rules **removed** from `CLAUDE.md` | **the ten owned task-time rules** — moved, never lost: user-approved 2026-08-29 (§7.7), each enumerated in the same commit that lands it in its owning skill |
| New doctrine | **2** — §7.5's skill-invocation rule, and §7.9's expert-agent architecture (an in-place promotion of a paragraph already present); both flagged as such |
| Deletions offsetting the additions | 2 rewrites in place (§3.4, §6.7) plus §7.3's ten relocations — no rule lost anywhere |

For §1–6 the unifying observation is that **every defect is a norm `CLAUDE.md`
already states, which has no surface that makes omitting it impossible.** The
document names the correct pattern itself, in the provenance section:

> After that `record_opportunity` **refuses** to write a row for a run with no
> provenance — the omission is made impossible rather than discouraged.

That is the template. Five norms have not received it yet. Nothing in §1–6 asks
an agent to believe anything new; each item takes a sentence that is already
law and gives it a table, a refusal, or a test.

§7 is the one place this spec adds doctrine rather than enforcement, and it
does so to make the *existing* rules land at the right moment. It moves ten
rules to the skills that own them and loses none (§7.2).

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

`score.record_backtest_run()` (`tools/score.py`) gains a required
`window_slug`. This is the
narrow analogue of `record_opportunity` refusing a row with no Kalshi ticker:
one boundary, one field, no judgement involved. Studies are not ledger writes,
so they get a CLI call plus a conventions test rather than a refusal — and
because `test_conventions.py` reads files, not the live DB, the test is
file-shaped: every `studies/` folder dated after this ruling must name its
`window_slug` and its registered question in its own write-up. (A study that
names them but never ran `questions ask` is caught by the number on the
`state` WINDOWS panel not moving, which is the same visibility this whole
section exists to buy.)

```bash
python -m tools.cli windows register <slug> --source kalshi_settled \
    --close-start 2026-06-22 --close-end 2026-08-25 --population "<filter>"
python -m tools.cli windows list
python -m tools.cli questions ask <window-slug> --by <study-or-theory> \
    --hypothesis "<one sentence>" [--pre-registered --at <sha>]
python -m tools.cli questions count <window-slug>
```

**Backfill is in scope, once, best-effort.** The count is only honest if the
questions already asked are in it: the existing `studies/` folders, the eight
`backtest_runs` rows, and every registered slice's origin get one
`hypothesis_tests` row each against the windows they used, `pre_registered=0`
except where a registration commit can be cited, with `notes='backfilled
2026-XX-XX from <source>'`. An unknowable historical question is skipped and
listed in the backfill commit message — the figure is a floor either way, and
a floor beats the current unknown.

### 1.5 The disclosure

`score.compute_score()` gains two keys, computed not asserted:

- `window_slug` — the window the settled rows came from. Derivable means:
  backtest pools read it off the run's `backtest_runs.window_slug`; live
  pools carry none and the key stays null — no guessing a window from date
  arithmetic.
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
by reading a study. `slices register` takes it as a `--n-examined` argument —
an interactive prompt would block the non-interactive agent sessions that do
the registering — and `segment_report` prints
it beside the slice's edge. No behaviour changes, and `slices register` is the
**sole writer** of `hypothesis_tests` rows for slice registrations — running
`questions ask` as well for the same registration would count one question
twice, so `questions ask` is reserved for the moments with no registration
act: studies and backtests. Belt and braces: `questions ask` warns on an
exact `(window_slug, asked_by, hypothesis)` duplicate.

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

Three of the four theories currently allowed to run (`deadline_drift` is
`proposed` and does not run; `mention_family` is retired) score `n=0`.
`structural_arb` has been bumped
twice past every row it has ever recorded. `score report insider_judgment`
returns nulls across the board while 96 settled live-mode rows sit in the
table at v3 (3,675 more settled there under backtest runs).

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
    equivalence_run TEXT,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (theory_id, version),
    CHECK (kind <> 'carry' OR equivalence_run IS NOT NULL)
);
```

The `CHECK` is the refusal in the repo's own idiom — `judgment_runs` already
constrains prompts this way — so an unproven `carry` cannot be inserted at
all; the §10 conventions test stays as belt and braces over old databases.

- **`breaking`** — the decision path changed. Track record resets. This is the
  default and stays the default; an agent that does not think about it gets
  today's behaviour exactly.
- **`carry`** — the change cannot alter the decision for prior rows. Evidence
  carries forward across the bump.

### 2.4 `carry` must be proven, never asserted

`theories.bump_version(..., kind="carry")` **refuses without an
`equivalence_run`**: a replay of the new code over a pinned fixture of the
predecessor version's recorded rows, which must reproduce every decision
*output* exactly — the side (`outcome`, which lives on the parent
`opportunities` row, so the fixture joins attempts to their positions),
`disposition`, `model_prob`, `confidence`, `edge_pts_gross`, `edge_pts_net`,
`edge_basis`, and **any `extra_json` key a registered slice predicates on**.
That last item is load-bearing for §2.8: slice predicates run over outcome,
confidence bucket, price band and `extra_json` features, so an equivalence
check that skipped them could pass a carry that silently changes slice
membership — pooling a slice's evidence across a bump that changed the
slice's own inputs. `decision_date` and `entry_price` are the replay's
stored *inputs*, not things it proves. Any single divergence makes the bump
`breaking`, whatever the author intended.

This is the load-bearing half. Without it `carry` becomes a self-granted
exemption and reintroduces the silent merge through the front door.

Shipped implementation (phase 6, amended from the original
`theory_instance` proposal): `tools/theories.py::prove_carry(conn,
theory_id, from_version, decide) -> EquivalenceResult`, where `decide` is a
**theory-supplied callable** mapping one stored attempt row (joined to its
parent position) to the current code's decision outputs. A `theory_instance`
parameter would have required the harness to know how to drive a theory —
the engine this repo forbids; the callable keeps the replay theory-owned and
the harness's role to fixture selection, comparison, and reporting. The
replay uses each attempt's stored `decision_date` and `entry_price` and must
not consult a fresh board; point-in-time market state comes from snapshots.

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
adjudicated'` (v1 rows say `'initial version'`, matching what `register()`
writes, so the backfill stays idempotent against future registrations). The registry stores only the *current* version and some past
versions recorded zero rows (`structural_arb` v3 has none), so the backfill
does not mine rows for history: it enumerates `1..current_version` per theory
and stamps every step `breaking`. If a past bump was genuinely a carry, it can be proven later by
running `prove_carry` against the fixture — evidence, not recollection. Nothing
is rewritten in place.

### 2.7 `CLAUDE.md` edit (≈90 words, after the existing bump paragraph — which lives inside "An underperforming theory is a research object", not "Theory lifecycle and versioning" as this heading originally claimed; corrected at implementation, 2026-08-29)

Appended after the existing bump paragraph:

> **A bump declares whether it breaks the track record.** `breaking` is the
> default and resets it. `carry` — for a change that provably could not alter
> the decision on rows already recorded — keeps it, and is refused unless a
> replay over the predecessor's own attempts reproduces every recorded decision
> exactly. Assertion does not qualify; the proof is the permission. This does
> not soften the bump rule, it makes the rule affordable: a theory still being
> improved could otherwise never accumulate evidence, which is how three of
> the four running theories reached n=0.

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

`RESEARCH_LOG.md` is 171 KB / 24,812 words across 64 entries (the §6.1
classification's measurement, 2026-08-29 — the file grows every session, so
quote that table's figures, not a fresh count). `CLAUDE.md` says
"read its tail when starting" and the `go` skill says "read the last ~30
lines". Thirty lines of a 64-entry log is now roughly the last two hours of one
session.

The consequence is not merely inefficiency. **Binding rulings are discoverable
only by reading the whole file.** The attempt-level scoring ruling, the
cluster-`n` schema ruling, the `bucket_rates` out-of-scope carve-out, and four
pending skill edits blocked on permissions all live as prose in the log tail.
An agent that reads thirty lines next week will not find them, and `CLAUDE.md`'s
own rule — the supervisor's contract, as §7.9 names it — is explicit that
this must not happen:

> ...every fact the supervisor needs in order to supervise surfaces in a
> shared structure.

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
FRESHNESS    last board pull · last settle run · last mark-taken · last bets render
```

Every panel has a named DB source, and `state` ships in §9's phase 1 while
three of those sources land later — so **each panel renders from its table if
it exists and prints a one-line `not yet tracked` stub if not**. The shape is
stable from day one; panels light up as phases land:

| panel | source | exists at phase 1? |
|---|---|---|
| THEORIES | `theories`, `opportunities`, `settlements`; chain n from `theory_versions` (§2, phase 6) | yes, minus chain n |
| STANDING | pending retirements; `rulings` (§3.3, phase 2); `parked` ideas + `paused` theories | partially |
| EVIDENCE | `scores`, `backtest_runs` | yes |
| WINDOWS | `data_windows` + `hypothesis_tests` (§1, phase 7) | no — stub |
| QUEUE | `opportunities` | yes |
| FRESHNESS | `market_snapshots`, `scores.computed_at`, `opportunity_fills.recorded_at`; "last bets render" comes from the raise-lane spec and stubs until that ships | yes, minus bets |

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
carries the binding text. Backfill is the twelve rulings currently on record
— the four in the log tail (attempt-level scoring, cluster-`n` schema, the
`bucket_rates` carve-out, the blocked skill edits) plus the eight the user
issued 2026-08-29 during this spec's review: §6.5's two (migrate the log;
adopt the promotion bar), the §4.3 paper-lane no, the §5.2 phase-1
relocation choice, the §5.3 force floor, §7.7's division-of-labour
reframing, §7.2's single-home relocation, and §7.9's expert-agent
architecture — a ten-minute job that is the whole payoff.

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

The other half of the loop — a surface that tells the user a bet is worth
placing at all — is specified separately in
`2026-08-29-bets-raise-lane-design.md` (the raise lane, user-requested).
Its raised-but-never-taken population is the divergence input this section
has been missing.

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

### 4.3 A paper lane — **ruled NO by the user, 2026-08-29**

The proposal (a third `user_action` value `paper`, feeding a segregated
`roi_paper`) was put to the user as the one item touching what the project
*means*, and the answer was no: the user places every bet, and a lane that
looks like betting without being betting is not worth the narrative erosion.
Per the section's own terms the design is deleted; this stub records the
ruling so it is never re-proposed as if undecided (backfill it into
`rulings` with §3.3). The divergence machinery still gets its input — the
raise lane's raised-but-never-taken population (§4.1) serves that purpose
without a hypothetical-fill lane.

### 4.4 `CLAUDE.md` edit

None — §4.2 is a CLI ergonomics change to a command the document already
documents, and §4.3 was ruled out, so its ~40-word contingency returns to
the budget.

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
  as live entry points (fixed by the foundation plan: both now live in
  `attic/kalshi_trader_migration/`).

The durable fix is one conventions test, in the exact idiom of
`test_every_recorded_prompt_path_still_resolves`:

```python
def test_every_repo_path_named_in_docs_resolves():
    """A doc that names a path nobody can open is worse than no doc: it
    sends the next session somewhere that does not exist. Fails at the
    commit that breaks the path, not months later."""
```

Scanning `README.md`, `CLAUDE.md`, `tools/README.md`, every `THEORY.md`,
and every `theories/*/CLAUDE.md` once §7.9 seeds them,
matching backticked strings that look like repo paths.

### 5.2 The snapshot store: back up, de-sync, dedup, compress — then split

*Rewritten 2026-08-29 from a measured handoff supplied by the user; all
figures measured that day against `db/market_edge.db`. The section as first
written was wrong in two ways: it understated the growth rate, and it
proposed the least important fix first.*

**Corrections to the original text.** A board pull writes **~400 MB**, not
~200: 1,390,328 rows at 2,815 bytes average (`raw_json` 2,192 +
`event_json` 622), ~100k markets per pull. Growth is **~1.3–1.8 GB per
active day** (~13 pulls over 3 active days) — **~50 GB/month at the current
rate** — not a per-pull cost to be shrugged at. Journal mode is WAL, inside
a OneDrive sync root; no conflict copies yet and checkpointing is clean,
which is luck holding, not safety.

**The finding that changes the plan: 56.5% of snapshot rows record nothing
new.** Measured with `LAG` over `(market_id ORDER BY captured_at)`
comparing `yes_bid`, `yes_ask`, `volume`, `open_interest`, `status`:

| rows | |
|---|---:|
| total | 1,390,328 |
| first capture (must keep) | 202,690 |
| unchanged repeats | **785,343 (56.5%)** |
| genuine changes | 402,295 |

That is ~2.2 GB of the 5.5 GB; 71,783 markets have all 13 captures stored.
The unique index is `(platform, market_id, captured_at)` — a row per market
per pull, unconditionally. This is the same shape as the position-identity
work in `f6a1047`: re-proposing a bet stopped writing a duplicate row and
started writing an attempt with `times_seen` on the position.
`market_snapshots` never got that treatment.

**Phase 0 — back up the ledger.** Blocks nothing; do it first. `.dump` of
every table except `market_snapshots`, gzipped, written outside OneDrive —
~30 MB. Default destination `%LOCALAPPDATA%\market_edge\backups\` (any
non-synced local path the user prefers overrides it); one-time now, with a
recurring cadence decided at phase 4 where the split makes per-file cadences
meaningful. The entire track record currently exists in exactly one 5.5 GB
WAL-mode file inside a sync root, gitignored. That is a total-loss single
point of failure, and it is the only item here with an irreversible
downside.

**Phase 1 — get `db/` out of OneDrive's sync path.** Ruled 2026-08-29: the
user chose **relocation plus junction** — move the directory to a non-synced
local path (default `%LOCALAPPDATA%\market_edge\db\`) and leave an NTFS
junction at `db/` so every repo path keeps working. Two cautions are part of
the procedure, not optional: (a) OneDrive clients have historically
*followed* directory junctions and synced the target's content anyway — after
creating the junction, verify OneDrive is not uploading `db/`; if it is,
fall back to OneDrive's folder-exclusion setting or point `tools/db.py` at
the new path directly and drop the junction. (b) The move runs only after
phase 0's backup exists and only while **no session holds the DB open** —
concurrent sessions are normal here (§5.3), and relocating a live WAL-mode
file is exactly the corruption this phase exists to prevent.

**Phase 2 — dedup on write.** Add `last_seen_at`; backfill
`= captured_at`. In `snapshot.save_kalshi`, compare each market against its
latest stored row: unchanged → `UPDATE last_seen_at`; changed → `INSERT`.
(The existing `ON CONFLICT (platform, market_id, captured_at)` clause is
same-timestamp idempotency only; this is new machinery, not a duplicate of
it.) Board rebuild becomes "latest row per market at or before T" instead of
"all rows where `captured_at = T`" — **and batch semantics change with it**:
a pull where a market moved nothing writes no row, so "the freshest batch"
is no longer ~100k rows. `board_info` must derive size as "markets with
`last_seen_at` >= the latest batch time" and age from `MAX(last_seen_at)`.
Three tests encode the old row-per-pull shape and keep their *intent* while
their fixtures update — `test_re_saving_updates_rather_than_duplicating`,
`test_separate_seconds_are_separate_batches`,
`test_board_info_uses_only_the_freshest_batch`. Only those three may change
meaning in this phase; the four fidelity tests below may not.

**Design gate — do not skip.** "Unchanged" must be decided by hashing the
full `raw_json` + `event_json`, never by the five material columns above —
or edits to rules text and `close_time` are silently dropped and
`CLAUDE.md`'s save-everything rule is violated. Measure the hash-based
dedup rate before committing to the design: it will be lower than 56.5%,
and if it is poor, find which field jitters and justify excluding it
explicitly rather than quietly.

**Phase 3 — compress `raw_json`/`event_json`.** zlib BLOBs, ~8× on the
remaining JSON. Needs a codec column or magic-prefix sniff so old and new
rows coexist. **There is no single accessor today** — the column is read by
direct `SELECT` + `json.loads` in `tools/board.py`, `tools/kalshi/
markets.py`, `tests/test_board.py`/`test_snapshot.py`, and four `studies/`
scripts (e.g. `2026-08-29-structural-gate-payload-version/measure.py`). So
this phase ships a decode helper in `tools/snapshot.py` (accepting both
plain text and compressed rows), repoints every `tools/` and `tests/`
reader through it, and takes an explicit stance on studies: they are
historical artifacts, so they are **not** rewritten — instead each affected
study's write-up gains a one-line note that re-running its probe against
compressed rows requires the helper. The sweep that finds the readers is
`grep -rn "raw_json\|event_json" --include='*.py' .`, run again at ship
time, because this list rots.

**Phase 4 — the split, as this section originally proposed.** Move
`market_snapshots` to `db/snapshots.db`, `ATTACH`ed by `tools/db.connect()`
so every existing query keeps working unqualified, letting the
precious-and-small file and the large one have different backup cadences.
`python -m tools.cli db stats` (per-table bytes via `dbstat`, falling back
to page-count estimation where the module is not compiled in) and a WAL
checkpoint on close ride along here. After phases 0–3 this is
backup-granularity convenience, not risk reduction — which is the ordering
the original section got wrong.

Projected: 5.5 GB → ~3.3 GB (dedup) → ~0.5 GB (compressed). **Zero
information loss** — `CLAUDE.md`'s "save as much as you can, while you can"
stays correct and untouched.

**The safety net — non-negotiable.** These four already exist and must pass
**unchanged — assertions and fixtures both — at every phase**; they are
precisely the golden tests for this migration. (The three batch-semantics
tests named in phase 2 are the only board tests allowed to change, and only
there.)

```
tests/test_board.py::test_cache_and_fetch_boards_are_identical_raw_included
                   ::test_rebuilt_board_matches_the_fetched_one
                   ::test_uncommon_fields_survive_the_cache_round_trip
                   ::test_snapshot_stores_the_complete_raw_payload
```

And the structural-gate point-in-time guarantee must survive the rebuild
rephrasing: "market text at time T" now resolves via the row whose
`[captured_at, last_seen_at]` interval spans T.

### 5.3 `get_board(force=True)` bypasses freshness — separate item, do not bundle

`force=True` refetches unconditionally, skipping the 4-hour window
(`DEFAULT_MAX_AGE_MINUTES` in `tools/board.py`). With one `go` session a
day that is correct; with 4–5 concurrent sessions it is ~2 GB/day — and,
the real issue, concurrent sessions reasoning over *different boards*.
Fix: make `force` honor a short floor (~30 minutes). The storage saving is
incidental; comparability is the point. Kept out of §5.2's phases
deliberately — it adjusts the behavior behind a documented convention
("`go`'s Orient makes the one deliberate refresh"), so it needed its own
ruling. **Ruled 2026-08-29: adopted.** Ships as its own commit, any time —
it changes board reuse, not any theory's decision procedure, so no version
bumps; `test_force_refetches_even_when_fresh` updates to assert the floor.

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

### 6.5 Two rulings this section needed — **ruled by the user, 2026-08-29**

Both were drafted for the supervisor under the standing delegation; the user
ruled directly before the packet went out, which outranks it. Recorded here
so the migration can cite its authority; both belong in the `rulings` table
the moment §3.3 ships.

**Ruling 1 — reverse `2026-08-25-theory-locality.md` §22: RULED, migrate.**
The user's words: "I do want to migrate the research.md information into
local theory when possible." *When possible* maps exactly onto §6.6's
structure — T entries move wholesale, M entries split one at a time with the
repo-level fact extracted upward first, X entries stay. The case that got it
here is §6.2 — forward-only produced 5,838 words of the thing it forbade
across 44 entries in four days. (Raised by session 9a: §22 was a documented
decision and needed to be *ruled on*, not reversed implicitly by shipping a
migration that contradicts it. It now has been.)

**Ruling 2 — the promotion bar: RULED, adopted.** The user's words: the log
"should only be information that is very useful generally or breakthroughs."
The wording below was proposed as the concrete form and is adopted as the
binding text — it is the user's sentence made checkable:

> **A log entry is earned by a fact that changes how a session that never
> touched this theory would act.** Everything else is a pointer. Concretely, an
> entry is warranted for: a repo-level mechanism or defect; a ruling; a
> methodological precedent; a data-source constraint; a cross-theory finding; a
> breakthrough result; a correction to something previously published. A result
> inside one theory is a one-line headline plus a pointer into that theory's
> `NOTES.md` — never the narrative, the tables, or the numbers, which live in
> the notebook and the ledger.

The test case already exists: `ff4318a`'s own entry is cross-cutting (a new
repo-wide mechanism) with theory-local numbers distilled to a headline plus a
pointer. It passes the bar as written, which is the cheapest available
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
python -m tools.cli slices list   # rows carry `origin`; no flag needed
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
> a ruling, a precedent, a constraint, a breakthrough, a correction. A result inside one theory
> is a headline and a pointer into its `NOTES.md`, never a copy. This was
> forward-only from 2026-08-25 and produced 5,838 words of copies anyway,
> because the log was what got read; it binds now because `state` is.

**This is the second offsetting deletion.** It replaces the existing
pointer-not-copy sentence rather than adding to it.

### 6.8 The migration procedure, step by step

Written so a session that never saw this spec can execute it, in order, with
a checkable exit condition per step. Prerequisites are §9's phases 1–3:
`state` exists (or moved content vanishes from orientation — §6.3), `rulings`
exists (or M extractions have nowhere to land), and the citation sweep is
clean.

1. **Pin the classification.** Extend the companion file's addendum to cover
   every entry appended since `ff4318a`, classified under the same T/M/X
   legend, and cite the companion file's revision in the migration commits.
   The table is the migration's input; the log keeps growing while the work
   runs, and anything newer than the pin is out of scope for this pass.
2. **Join the three double-`## ` headings** (lines 290, 359, 471 as of the
   classification) into single lines, as its own commit. Every count and
   every stub anchor keys on headings; fix the anchors before anything moves.
3. **Run the citation sweep** (§6.6's three commands) and land the extended
   citation test. Exit condition: sweep output saved alongside the companion
   file, test green. Nothing moves before this.
4. **Move T entries, in date order, one commit per owning theory.** Verbatim
   append to that theory's `NOTES.md` under
   `## <original date> — <original heading> (migrated from RESEARCH_LOG.md)`.
   Leave the stub at the original anchor — date, heading, one pointer line.
   Apply the pairing rules as recorded per row: the politics correction lands
   adjacent to its target, and the one two-theory entry goes to the majority
   owner with a dated pointer in the other notebook.
5. **Run the citation test and the full suite after each theory's commit**,
   never once at the end — a broken citation must surface while the move that
   broke it is still the newest commit.
6. **Split M entries one at a time**, each its own commit: the repo-level
   fact goes up — into `rulings` if it is a ruling, `theory_facts` if it is a
   durable theory fact, or a one-paragraph replacement entry if it is
   narrative context — and the theory narrative goes to the notebook (or the
   study's write-up, for study-owned rows). Record what was extracted and
   where in the companion table row. Never batch these; §6.6 marks this the
   only judgement-bearing step.
7. **X entries: untouched.**
8. **Reconcile.** Stub count equals moved-row count in the companion table;
   `state` renders; suite green. The log gets one migration entry carrying
   those reconciliation numbers — it passes the §6.5 bar on its own terms,
   being a repo-level change.
9. **The bar binds from that commit forward.** New entries follow §6.7's
   `CLAUDE.md` text: mechanisms, rulings, precedents, constraints,
   breakthroughs, corrections — generally useful facts only, per the user's
   ruling. Everything theory-local is a headline plus a pointer into
   `NOTES.md`. The citation test is the enforcement: dated citations into the
   log must keep resolving, so a copy pasted where a pointer belongs has no
   gap to hide in — and `state`, not the log tail, is what the next session
   reads, so the incentive §6.3 diagnosed points the same way the rule does.

---

## 7. Rule delivery: each rule lives where it binds, and none is lost

### 7.1 The problem, stated correctly

`CLAUDE.md` is 6,671 words (post-consolidation) carrying ~36 rules. **That
is ~8k tokens —
that is not a context problem**, and any version of this section justified by
load cost is solving the wrong thing.

The cost is **dilution**. Rules compete for attention inside one document that
is read once, at session start, whatever the session turns out to do. A rule
about structural-gate conditions is read by a session that will never
backtest, and — the part that matters — is read *hours before* the session
that will backtest reaches the moment it binds.

So the target is not a shorter file. It is: **every rule is in front of the
model at the moment it is about to violate it.**

### 7.2 The principle: one home per rule — **ruled by the user, 2026-08-29**

These rules are hard-won. Most exist because something went wrong once, and
the hedges inside them are scar tissue from specific misreadings. **No rule
is ever lost** — but this section's earlier draft chose duplication
(`CLAUDE.md` *and* the skill, held identical by a test), and the user
rejected that for the dilution it preserves: `CLAUDE.md` should carry a
non-diluted cardinal core, and a task-time rule should live in exactly one
place — the skill that owns its activity.

So the ruling: **the owned task-time rules move, they are not copied.**
`CLAUDE.md` keeps the enforced and constitutional tiers in full plus §7.5's
skill map, and sheds the task-time text. Two mechanics make removal safe
rather than brave:

- **Atomicity.** A rule leaves `CLAUDE.md` only in the same commit that
  lands it in its owning skill. At every commit in history, every rule has
  exactly one authoritative home; there is never a window where a rule
  exists nowhere.
- **The single-home test** (§7.6). A conventions test holds the manifest:
  every moved rule is present in its owning skill, and `CLAUDE.md`'s skill
  map names every skill that carries rules. A silently dropped rule fails
  the suite at the commit that dropped it.

The known risk is stated, not hidden: skills load on invocation and
`CLAUDE.md` is guaranteed, so a session that skips its skill never sees the
moved rules. §7.4's test is what bounds that risk — anything whose
violation outside the skill would be a disaster stays constitutional — and
§7.5's invocation rule, now genuinely load-bearing, is the enforcement
that skills actually open.

### 7.3 Three tiers, by how a rule binds

| tier | what it is | where the text lives |
|---|---|---|
| **Enforced** (13) | code refuses or a test fails | `CLAUDE.md` keeps the rule; the *argument* may move. The enforcement already teaches it |
| **Constitutional** (~9) | unenforceable, always binding, disaster if violated unaware | `CLAUDE.md`, in full, with worked examples — untouched |
| **Task-time** (~15) | unenforceable, binds during one activity | **the owning skill, in full — moved there, not copied** (§7.2 ruling); `CLAUDE.md` keeps only §7.5's map |

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

Skill text lives at `.claude/skills/<name>/SKILL.md`; all six named skills
exist there today. **The removal scope is exactly the ten owned rules** (13,
19, 20; 10, 11, 12; 17, 35, 36; 32). Two carve-outs, both already implied by
the classification: the three rules with no owning skill (24, 29, 30) stay
in `CLAUDE.md` — nowhere to move, no new skill invented for them — and
`score-theories`' row is an *explainer* of rule 18, whose text stays
constitutional; nothing is removed for it. Where a moved rule is embedded in
a `CLAUDE.md` narrative that survives (19's five conditions sit inside the
Backtest tiers story), the removal leaves the section coherent with one
pointer sentence — the sentence is a pointer, never a paraphrase of the
moved rule.

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

This is one of the two doctrine changes §0's budget table allocates (§7.9
is the other). It is also load-bearing: without it, §7.3 moves rules into
documents that may never open.

### 7.6 The single-home test: a manifest, checked by a test

With one home per rule, drift between copies is impossible — the failure
modes that remain are a rule silently dropped during its move, and a rule
quietly edited under cover of relocation. Both get the same treatment.

A moved rule lands in its skill **verbatim from `ff4318a`'s `CLAUDE.md`
text**, inside a marked block naming its origin:

```markdown
<!-- rule: structural-gate-conditions (moved from CLAUDE.md § Backtest tiers, 2026-08-29) -->
> A judging stage is structural — and does not cost tier A — only when all
> of the following hold...
<!-- /rule -->
```

Changing a moved rule's *content* after the move is a normal governance act
— it just happens in the skill now, reviewed in `git diff` like any prompt
change. The move itself must be content-neutral, which the commit diff
shows by construction: text deleted here, identical text added there.

New in `tests/test_conventions.py`, in the idiom of
`test_every_recorded_prompt_path_still_resolves`, over a manifest of the
ten moved slugs and their owners:

```python
def test_every_moved_rule_lives_in_its_owning_skill():
    """Each relocated rule has exactly one home: its marked block exists
    in the owning skill, and CLAUDE.md's skill map still names that
    skill. A rule dropped in a move fails at the dropping commit."""
```

That makes removal safe, which is what lets §7.2 prefer a non-diluted
`CLAUDE.md` over duplication.

### 7.7 What requires explicit approval

- **Removing any rule from `CLAUDE.md`** — per rule, from the user, never as
  a side effect. **Granted 2026-08-29 for exactly the ten owned task-time
  rules enumerated in §7.3**, the user's stated aim being a non-diluted
  cardinal core; each implementing commit still lists the rules it moves, so
  the approval stays auditable per rule. Any removal beyond those ten —
  constitutional, enforced, or the three unowned — needs fresh approval;
  nothing here is a precedent for it.
- **Consolidating the prefer-mechanical argument — approved and performed,
  2026-08-29, with a reframing the user required.** The user rejected the
  old "prefer statistics / mechanical-first" framing and recentred the rule
  as a **division of labour**: a model can only categorize (good vs bad, a
  bucket, a side) — it can never emit a number like "0.5% edge" — and any
  edge an LLM-judged theory claims must trace to backtesting or settled
  history, never the model guessing. Interpretive theories stay explicitly
  first-class. The canonical statement now lives under "Never state a
  probability you introspected" with all four hedges kept as numbered
  riders; the other sites keep their local substance plus a pointer. The
  machinery already enforced this (Verdict has no numeric field,
  `buckets.py` converts via realized rates, `edge_basis` has no
  felt-about-right option) — the rewrite makes the constitution say what
  the code enforces.
- **Any change to the `Subset edges` subsection** — session 9a's text (§8).

### 7.8 `CLAUDE.md` edit (≈120 words added — §7.5's rule, inside "How the user drives this")

The ~120-word skill map plus §7.9's ~60-word rewrite are the section's only
additions; §7.3's relocations then subtract the ten task-time rules, so §7's
net effect on `CLAUDE.md` is **negative** — the cardinal core, undiluted,
plus a map that says where the rest went.

### 7.9 Theory-level context and skills — the expert-agent architecture (**ruled by the user, 2026-08-29**)

The user promoted a latent option to the repo's stated architecture: **it
must always be possible to initialize a strong agent inside one theory —
hand it the cardinal `CLAUDE.md`, the skills, and the theory's own folder —
and have it operate as that theory's expert**: investigate, solve problems,
run the procedure, extend the notebook. Above the experts sits a supervisor
that understands every theory abstractly and never needs a notebook: it
reads only the shared structures — `state`, `THEORY.md`, the DB,
`RESEARCH_LOG.md`.

Both interfaces were already law, which is why this lands as a §7 delivery
extension rather than new machinery — and on the user's instruction the two
rules are **rephrased in the architecture's own vocabulary**, named as its
contracts: the old "any fact the repo level needs must surface in a shared
structure" is now **the supervisor's contract**, and the old "a theory
folder must stay self-sufficient to run" is now **the expert's contract**,
each stated in `CLAUDE.md` with its substance (distillation upward, the
sibling-import ban, the shared-parent escape, the enforcing test) intact.
§6's migration is this architecture's backfill — it moves each theory's
context into the folder where its expert will look. Two mechanisms extend §7's ladder one
level down, both native to the harness:

- **Theory-level contextualization: `theories/<slug>/CLAUDE.md`.** The
  harness auto-loads a directory's `CLAUDE.md` when working under it, so a
  theory's cardinal context rides the same mechanism as the repo's. It is a
  distillate with the repo file's own philosophy — the thesis in one
  breath, the current version and what bumped it, standing constraints and
  data-source quirks, pointers to `RUNBOOK.md` and `NOTES.md` — and it is
  never a second notebook: raw narrative stays in `NOTES.md`, and the §6.5
  promotion-bar philosophy applies inside the theory exactly as it does at
  the repo level.
- **Theory-level skills.** A skill useful to exactly one theory lives
  directory-scoped to that theory's folder (the skill listing shows it
  path-prefixed; the scoped variant wins inside its directory). Elevation
  to the global skill set follows the same rule as code elevating to
  `tools/`: two or more real theory callers, as a migration, never a copy.

**`CLAUDE.md` edit (~75 words net, rewrite in place — doctrine change #2,
flagged in §0): PERFORMED 2026-08-29.** The "This shape also supports —
without requiring — a repo-level agent…" paragraph in "What lives in a
theory" is rewritten from *option held open* to *stated architecture*:
design every addition so a theory expert can be initialized from the
cardinal file, the skills, and the folder — and so the supervisor can
supervise from shared structures alone — with the two rules restated as
the supervisor's and the expert's contracts per the block above. Their
substance is unchanged; they were this architecture all along, unnamed.

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
- **Any rewrite of `CLAUDE.md` for length.** The cardinal core's size is a
  deliberate purchase of cross-session consistency, not technical debt. §7
  does shrink the file, but as a byproduct of single-home delivery — the
  motive is undiluted cardinal rules, never a word count, and the
  constitutional and enforced text is not compressed by so much as a hedge.
- ~~Consolidating the prefer-mechanical argument~~ — no longer out of scope:
  approved, reframed and performed 2026-08-29 on the user's ruling (§7.7).
- **The `Subset edges — registered slices` subsection of `CLAUDE.md`**
  (`ff4318a`, line 331). Session 9a owns that text; §1.7 and §2.8 above add
  columns and a pooling switch around it and reword none of it. If the §6.5
  bar, once ruled, would require changing it, that goes back to 9a first.

---

## 9. Sequencing

Each phase is independently shippable and independently useful.

| Phase | Contents | Why this order |
|---|---|---|
| 0 | §5.2 phases 0–1: ledger backup + `db/` out of OneDrive | The repo's only total-loss risk; blocks nothing, ships in minutes |
| 1 | §5.1 hygiene, §4.2 `--ticker`, §3.2 `state` | Zero doctrine, zero schema risk, immediate orientation payoff |
| 1b | §5.3 force floor | **Ruled 2026-08-29: adopted.** One-commit behavior change, independent of the storage phases |
| 2 | §3.3 `rulings` + backfill | Makes the ten buried rulings survivable before the next session loses them |
| 3 | §6.8 steps 1–3: pin, heading fix, citation sweep + test | Read-only bar the heading join; must precede any move, and is useful even if the migration never runs |
| 4 | §6.8 steps 4–5: T-entry migration + stubs | Mechanical once the sweep is clean; 22 entries / 9,484 words, no judgement |
| 5 | §6.8 steps 6–8: M-entry split + reconcile | The judgement-bearing quarter; only safe once `rulings` (phase 2) exists to receive the extractions |
| 6 | §2 carry/breaking + backfill + `rank`/`segment_report` disclosure | The evidence bleed; largest payoff, needs the disclosure precedent |
| 7 | §1 question budget + §1.7 slice columns | Needs windows registered, easiest once `state` renders them |
| 8 | §5.2 phases 2–4: dedup → compress → split | Pure operations once phase 0 has a backup; the design gate (measure the hash-based dedup rate) precedes phase 2 |
| **A** | §7.5 skill-invocation rule + §7.6 single-home test + manifest | **Must precede B.** The map and the test are what make removal survivable, so no rule moves before they exist |
| **B** | §7.3's ten task-time rules moved into `backtest-theory`, `find-edge`, `propose-theory`, `go` (+ the rule-18 explainer in `score-theories`) | One skill per commit; each commit adds the marked blocks to the skill **and removes the same text from `CLAUDE.md` atomically**, enumerating the rules it moves, verified by the §7.6 test |
| **C** | §7.9: `theories/<slug>/CLAUDE.md` seeded per running theory; theory-skill scoping convention documented in `tools/README.md` (the architecture rewrite in `CLAUDE.md` was **performed 2026-08-29**) | The seeds are best after phases 4–5 (the migrated notebooks are their source), one theory per commit, distillate only — a theory's cardinal core, never a second notebook |
| — | §6.5 rulings 1 & 2 (§22 reversal, promotion bar) | **Ruled by the user, 2026-08-29** — migrate, and the bar is adopted. Phases 4–5 now gate only on phases 1–3; the bar still *binds* only once phase 1 ships, per §6.3 |
| — | §4.3 paper lane | **Ruled NO by the user, 2026-08-29** — nothing ships; §4.2 stands |

Phases 3–5 are the migration. **Phase 1 gates all of them** (§6.3): raising the
bar or emptying the log before `state` exists just moves work into files nobody
reads.

## 10. Testing

Every item ships with tests in the existing suite (1,005 passing in 42s,
re-measured 2026-08-29 at review):

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
- New `test_state.py` — `state` renders from a fixture DB with no network,
  including the stub line for every panel whose table is absent (§3.2's
  degradation contract is behaviour, so it is tested).
- `mark-taken --ticker` (§4.2) — resolves the latest attempt, and the
  ambiguous-ticker case (two theories open on one ticker) asks rather than
  guessing.
- Extended docs-path test (§6.6) — every `theory_slices.origin` and every dated
  cross-citation names a file that exists *and still contains that date
  heading*. A stub passes; a silent move fails. This is the migration's only
  real safety net, and it must land **before** phase 4.
- New `test_every_moved_rule_lives_in_its_owning_skill` (§7.6) — each of the
  ten relocated rules has its marked block in its owning skill and an entry
  in `CLAUDE.md`'s skill map; a rule dropped in a move fails at the dropping
  commit. This is what makes §7.2's removal safe, and it must land **with**
  phase A, before any rule moves.

## 11. What this spec does not change

The mission, the theory contract, `finish()` as the ledger boundary, the
credibility formula, the tier definitions, the no-introspected-probability
rule, the ranking arithmetic, `edge_basis`, the disposition vocabulary, "only
the user retires a theory", or the voice of `CLAUDE.md` (its size now shrinks
by design — §7.2).

`RESEARCH_LOG.md` in particular **stays append-only and stays the audit
trail**. §6 moves content out of it and leaves a stub at every anchor; it does
not compress it, rewrite it, delete from it, or cap its growth. A journal is
supposed to grow. The change is that the canon stops living inside it.

**And no rule is lost.** §7 moves the ten owned task-time rules into the
skills that own their activities — with the user's explicit approval, each
move atomic and content-neutral, each rule's single home held by a test —
and `CLAUDE.md` keeps the enforced and constitutional tiers in full plus the
map that says where the rest went. Every rule in that file was paid for by
something going wrong once; every one still exists, in exactly one place,
and removing anything beyond those ten needs fresh approval, per rule
(§7.7).

Five sentences the document already contains get a table, a refusal and a
test. One rule is added and ten are moved to where they bind, so the
cardinal core reads undiluted and the rest arrives when it matters. That is
the whole change.
