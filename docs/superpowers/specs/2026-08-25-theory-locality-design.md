# Theory locality — what lives in a theory, what gets elevated

Date: 2026-08-25
Status: proposed (awaiting user review)

## Problem

Two forces pull code and notes out of theory folders and into shared,
repo-level homes, and both produce worse outcomes than they promise:

1. **Backtesting.** The obvious move — "theories need backtests, so build
   `tools/backtest.py`" — is wrong, and this repo already has the evidence.
   `theories/insider_bias/insider_judgment/backtest.py` spent most of its
   design budget on problems no second theory will share: one combinatorial
   series (`KXMVECROSSCATEGORY`) settles 400k+ markets a day and must be
   scoped around before any fetch; Kalshi candle volume is per-day, not
   cumulative, so lifetime volume has to be reconstructed with a warm-up
   window; the category pre-filter is a fetch-scoping decision that must not
   leak into the screen being tested. A `mention_family` backtest shares
   none of those problems and has its own. A generic replay engine would
   either anticipate every such quirk (it cannot) or paper over them
   (silently, which is worse). Yet each theory writing its own backtest
   from bare HTTP calls would be waste too — the *time* primitives
   (point-in-time candles, snapshots) and the *bookkeeping* (run ids,
   tiers, scoring) genuinely are shared.

2. **Research notes.** Today a theory's findings scatter across
   `THEORY.md` Learnings, `RUNBOOK.md`, and the repo-level
   `RESEARCH_LOG.md`. Without a stated rule, session logs accumulate
   one-theory internals — the 2026-08-24 tier-A backtest entry is a
   single theory's backtest narrative living in the session log, and the
   Big Brother follow-up entry the same — and theory folders have no
   designated place for raw working notes, so they either bloat
   THEORY.md or evaporate. (Cross-cutting entries like the 2026-08-25
   OOP-migration narrative are the log doing its actual job, and stay.)

Behind both is one architectural intent: it should be possible to run
**one repo-level agent** that understands every theory from a high level
(what it claims, what it has demonstrated, what state it is in) and
**theory-level agents** that understand one theory in full depth and
report upward. That structure is not being built or enforced now — but
every convention below is chosen so that it works when wanted, and none
below would have to be undone.

## Decisions at a glance

1. **Backtests live in the theory.** The harness owns *time, bookkeeping,
   and scoring*; the theory owns the *replay*. There will be no
   `tools/backtest.py` replay engine and no `Theory.backtest()` contract
   method — ever, absent a new spec that overturns this one.
2. **Raw research notes live in the theory** (`NOTES.md`, a dated
   append-only lab notebook per theory). `THEORY.md` carries only the
   distilled version. `RESEARCH_LOG.md` stays repo-level and
   cross-cutting. **Anyone may read anything** — segregation governs
   where things are *written*, never who may read.
3. **The two-level agent structure is supported by surfaces, not
   enforced by code.** Each theory folder is self-sufficient for a
   theory-level agent; everything a repo-level agent needs surfaces in
   shared structures (THEORY.md, the DB, the CLI) without descending
   into any theory's internals.

## 1. The locality rule

**Everything starts in the theory that needs it, and elevation is earned,
never anticipatory.** `tools/README.md` already says this for code; this
spec extends it to every artifact kind and states the elevation trigger
for each:

| Artifact | Lives in the theory | Elevated to | Elevation trigger |
|---|---|---|---|
| Screen / pricing / pipeline code | yes — any layout | `tools/` | >1 real caller, or a new theory would obviously reach for it (judgment call, per `tools/README.md`) |
| Backtest replay code | yes — `backtest.py` by convention | `tools/` (helpers only, never the replay) | same >1-real-caller rule, helper by helper |
| Judging prompts | yes — `prompts/` | never | prompts are part of one theory's decision procedure by definition |
| Raw research notes | yes — `NOTES.md` | never elevated; *distilled* into `THEORY.md` | a note that changes what the theory claims or how it runs graduates into THEORY.md / RUNBOOK.md |
| Run procedure | yes — `RUNBOOK.md` | never | — |
| Hypothesis, status, learnings | yes — `THEORY.md` | is itself the repo-level surface | — |
| Durable facts (confirmed pairs, implication edges) | no | `theory_facts` in the DB | always — facts are data, not procedure |
| Opportunities, verdicts, scores, backtest runs | no | the DB via the ledger | always — this is the non-negotiable contract |
| Ideas considered and dropped | no | the ideas registry | always — dedup across theories requires one registry |
| Session continuity | no | `RESEARCH_LOG.md` | always — it is the only cross-session, cross-theory narrative |
| Tests and test fixtures | no | `tests/theories/`, `tests/characterization/` | always — the repo runs one suite, and every theory test, golden, and fixture already lives there |
| Research data (cached pulls, canned payloads a replay or analysis reads) | yes | — | never — it is input, not evidence; anything it *produces* lands in the DB |

Two asymmetries worth naming:

- **Code elevates by caller count; knowledge elevates by audience.** A
  helper moves to `tools/` when a second theory calls it. A note moves
  up when the *repo level* needs it to orient — into THEORY.md if it
  changes the theory's claims, into the DB if it is a fact or a result,
  into RESEARCH_LOG.md if it is session narrative. Raw notes never move;
  they get summarized.
- **Elevation of code is a migration (one implementation, delete the
  local copy); elevation of knowledge is a distillation (the raw note
  stays in NOTES.md as the audit trail for the summary).**

## 2. Backtesting — the harness owns time; the theory owns the replay

### What the harness provides (exists today, now named as the whole of it)

- **Point-in-time truth:** `tools/kalshi/history.py` (`candlesticks`,
  `point_in_time` — never returns a candle past `as_of`), and
  `tools/snapshot.py` (first-party capture that grows the tier B window).
- **Run bookkeeping:** `TheoryContext(run_mode="backtest", run_id=...)`
  propagating through `finish()` to every row; the `backtest_runs` table
  and `python -m tools.cli backtest record` with tier and model cutoff.
- **Tier rules:** A/B/C as defined in CLAUDE.md and the `backtest-theory`
  skill — a documented derivation rule (from `uses_llm_judgment` and the
  later of the judging models' cutoffs) that the *session* applies; the
  harness stores the label and validates it against the three valid
  tiers (`record_backtest_run`), it does not derive it.
- **Scoring:** `python -m tools.cli score report --run-mode backtest
  --run-id <id>`.

That list is the harness's **complete** contribution. It is the
infrastructure every replay needs and no replay differs on: what was
true when, which rows belong to which run, how trustworthy the evidence
tier is, and what the numbers came out to.

### What each theory owns

**The replay itself: how to reconstruct this theory's decision at a past
moment without lookahead, over a fetchable slice of history, and which
approximations that reconstruction accepts.** Those three questions are
thesis-specific — they depend on what data the screen reads, which
markets the thesis touches, and what the historical API can and cannot
answer — which is exactly why no shared engine can answer them.

Conventions (all optional-for-running, following the theory contract):

- A theory that backtests puts its replay in **`backtest.py`** in its
  folder. Any internal shape is fine; `insider_judgment/backtest.py` is
  the worked example (scope the fetch, reconstruct state, run the *real
  unmodified* screen with `now` pinned).
- **`THEORY.md`'s "How to backtest" section remains the procedure's
  source of truth** — it states the tier and the known biases of the
  reconstruction (e.g. "volume can only be undercounted, so eligibility
  errs conservative"). A replay whose biases are not written down is a
  replay whose results cannot be caveated.
- The replay **calls the same functions the live path calls.** A
  backtest of a reimplementation of the screen is a backtest of nothing.
- Backtest *results* land in the DB like any run (rows with
  `run_mode="backtest"`, a `backtest_runs` record). Backtest *narrative*
  — what was tried, what broke, why the window is what it is — goes in
  the theory's `NOTES.md`.

### What is explicitly forbidden

- **No `tools/backtest.py` replay engine.** No shared function that
  takes a theory and "runs its backtest."
- **No `backtest()` method on the `Theory` contract**, abstract or
  defaulted. The contract stays two required methods; a backtest is a
  driver script that builds a backtest-mode context and calls the same
  `screen()`/`price()` as live. Adding a contract method would impose
  one replay shape on theories whose replays legitimately differ —
  the exact failure this spec exists to prevent.

This prohibition binds future sessions (and future models) doing
"obvious" refactors: a second theory-local backtest that resembles the
first is **not** sufficient grounds to build an engine. What may be
promoted, helper by helper under the normal >1-caller rule, are narrow
primitives — `systematic_sample`, a checkpointed per-series iterator, a
candle-walk state reconstructor — each as a plain function in `tools/`,
never as a framework that inverts control over the theory.

## 3. Research notes — NOTES.md per theory, distillation upward

### The three documents of a theory, and the new fourth

| File | Question it answers | Written when |
|---|---|---|
| `THEORY.md` | what does this theory believe, what is its procedure, what has it learned (distilled) | when the claim, procedure, status, or distilled learnings change |
| `RUNBOOK.md` | how does a run happen, mechanically | when the run procedure changes |
| `NOTES.md` (**new**) | what happened while researching this theory — raw | continuously, append-only |
| `prompts/` | what exactly the judge was asked | with a version bump |

**`NOTES.md` format:** dated `## YYYY-MM-DD — <topic>` sections, newest
last, append-only in spirit (correcting an error is fine; rewriting
history is not). Contents: dead ends and why they died, data-source
quirks discovered, backtest narratives, hunches not yet worth a version
bump, links to relevant `run_id`s and idea-registry entries. It is a lab
notebook: allowed to be messy, allowed to be wrong, allowed to be
illegible to someone who has not read the rest of the folder.

**The distillation rule:** when a note changes what the theory *claims*
or *does*, the change lands in THEORY.md (Learnings, Status, or a
version bump) — and the raw note stays behind as the audit trail.
THEORY.md's Learnings section becomes a summary with pointers, not a
journal. This is the same shape as stage 2 → stage 1 migration: proven
in the messy layer, promoted to the authoritative one.

### What stays repo-level, and why

- **`RESEARCH_LOG.md`** — session continuity: what a session did, across
  theories and infrastructure. When a session's work is mostly inside
  one theory, the log entry is a few lines plus a pointer to that
  theory's NOTES.md entry — not a copy of it.
- **The ideas registry** — every hypothesis considered, including
  dropped ones, with `revisit_angle`. Central because its whole job is
  cross-theory dedup ("has anything like this been tried?"), which
  per-theory notes cannot answer without reading every folder.
- **The DB** — everything measured.

### Cross-theory reading is explicitly open

Any session or agent may read any theory's NOTES.md, code, or prompts at
any time, and connecting dots across theories is encouraged — the
mention-family discovery came from exactly that kind of sideways look.
The segregation above is about *write* discipline (one home per kind of
information), never about read access. There is no notion of a private
note anywhere in this repo.

## 4. Agent surfaces — supported, not enforced

The target shape: a **repo-level agent** that orients, compares,
composes, and dispatches; **theory-level agents** that each know one
theory in depth. Nothing in this spec builds that orchestration, and no
current workflow requires it. What this spec guarantees is that the
information architecture already matches it:

**The repo-level surface** — everything a repo-level agent needs without
opening any theory's internals:

- `THEORY.md` per theory: hypothesis, status (an evidence level),
  version + changelog, distilled learnings.
- The DB via the CLI: scores, calibration, bucket rates, backtest tiers,
  ranking, retirement proposals, the ideas registry.
- `RESEARCH_LOG.md`: what recent sessions did.

**The theory-level surface** — everything a theory-level agent needs,
all inside one folder plus the shared `tools/`:

- The folder's code, `RUNBOOK.md`, `NOTES.md`, `prompts/`, and the
  theory's own DB rows.
- A theory folder must stay **self-sufficient to run**: no imports from
  a sibling theory's folder. Shared ancestry goes through a shared
  parent module (as `theories/insider_bias/screen.py` already does) or
  through `tools/`.

**The one load-bearing rule** that keeps both surfaces honest: **any
fact the repo level needs must surface in a shared structure** —
THEORY.md, the DB, or the session log. A theory whose true status is
discoverable only by reading its NOTES.md has broken the surface, and
the fix is distillation upward, not a repo-level agent that reads every
notebook. Symmetrically, the repo level never needs to *forbid* itself
from reading theory internals — it just must never be *required* to.

Communication, when the structure is eventually used: downward, a
dispatch brief is "your folder, the shared tools, this question";
upward, a report is ledger rows, THEORY.md/NOTES.md updates, and a
summary. Both channels already exist as files and DB rows, which is why
no protocol needs designing now.

## 5. Concrete changes

Documentation and convention changes only — no behavior, schema, or
contract changes anywhere.

1. **`theories/_TEMPLATE/NOTES.md`** — new template file: the format
   rules (dated sections, append-only, distillation rule) in a short
   header quote, then an empty first entry.
2. **`theories/_TEMPLATE/THEORY.md`** — Learnings section reworded:
   distilled summary with pointers into NOTES.md, not a running journal.
   A sentence added to "How to backtest": the replay lives in this
   folder as `backtest.py`; the harness supplies time, bookkeeping, and
   scoring only.
3. **`NOTES.md` seeded** for `insider_judgment` and `mention_family` —
   header plus a pointer to where their history currently lives
   (THEORY.md Learnings, RESEARCH_LOG.md entries). Existing content is
   not migrated; the convention applies going forward.
4. **`CLAUDE.md`** — a short "What lives in a theory" section: the
   locality table's headline rules, the backtest ownership split
   (harness owns time/bookkeeping/scoring; theory owns the replay; no
   global engine), the NOTES.md convention, the open-read rule, and one
   paragraph on the two-level agent surfaces.
5. **`tools/README.md`** — two conventions added: the backtest
   prohibition (with the named promotable-helper examples), and the
   knowledge-vs-code elevation asymmetry.
6. **`.claude/skills/backtest-theory/SKILL.md`** — one addition: the
   replay code lives in the theory's folder (`backtest.py` by
   convention); never write or extend a shared replay engine.
7. **`.claude/skills/go/SKILL.md`** — the "Log it" step currently says
   "Theory-specific findings also go in that theory's `THEORY.md`
   Learnings", which is exactly the behavior this spec replaces.
   Reworded: theory-specific findings go in that theory's `NOTES.md`;
   `THEORY.md` changes only when the claim, procedure, or status
   changes; the log entry carries a pointer, not a copy.
8. **`.claude/skills/score-theories/SKILL.md`** — same treatment: its
   "belongs in `THEORY.md` Learnings" line becomes "belongs in that
   theory's `NOTES.md`, distilled into `THEORY.md` if it changes the
   theory's standing."
9. **`RESEARCH_LOG.md`** — this decision logged; future entries follow
   the pointer rule.

## 6. Non-goals

- No orchestration code, agent framework, or dispatch protocol for the
  two-level structure. Surfaces only.
- No migration of existing notes out of THEORY.md or RESEARCH_LOG.md.
- No new DB tables. Backtest bookkeeping (`backtest_runs`) already
  exists.
- No changes to the `Theory` contract, the ledger, or scoring.
- No per-theory private/hidden anything.

## 7. Success criteria

1. A session asked to "backtest theory X" writes
   `theories/<...>/X/backtest.py` against the harness primitives and
   records a tiered `backtest_runs` row — and does not create or extend
   any shared replay engine, because two documents (CLAUDE.md,
   tools/README.md) and the skill now say not to.
2. A session that discovers something mid-research writes it to the
   theory's NOTES.md; THEORY.md changes only when the claim or procedure
   changes; RESEARCH_LOG.md gets a pointer, not a copy.
3. A repo-level orientation (`go`'s Orient, `compare-theories`) can be
   completed from THEORY.md files, the CLI, and RESEARCH_LOG.md alone —
   verified by inspection: no fact needed for orientation lives only in
   a NOTES.md.
4. A theory-level deep dive needs only the theory folder and `tools/` —
   no sibling-theory imports anywhere (`grep` for cross-theory imports
   stays clean, shared parents excepted).
