# Theory Locality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write down — in the four places a future session actually reads — that a theory's backtest replay and raw research notes live in the theory folder, that the harness contributes only time, bookkeeping, and scoring to a backtest, and that reading across theories is always open.

**Architecture:** Documentation and convention changes, plus one **gated** guard test. Six documents state the rule (`CLAUDE.md`, `tools/README.md`, the theory template, and three skills) and two theory folders get a seeded `NOTES.md` — Tasks 1–6 and 8, entirely doc-only. Task 7 adds the one mechanically-checkable success criterion (no sibling-theory imports) and the one-file move that brings the repo into compliance with it; it touches another session's in-flight work, so **it does not start without the user's approval** and nothing else depends on it.

**Task order:** 1 → 2 → 3 → 4 → 5 → 6 → 8, with Task 7 inserted before Task 8 only if approved. Tasks 4, 5, and 6 are independent of each other and may run in any order after Task 3.

**Tech Stack:** Markdown; Python 3.11 + pytest for the single test task; `ast` from the standard library for import parsing.

**Spec:** `docs/superpowers/specs/2026-08-25-theory-locality-design.md`

## Global Constraints

Copied from the spec's §6 Non-goals and §1 locality rule. Every task's requirements implicitly include these.

- **No new DB tables.** `backtest_runs` already exists and is not modified.
- **No changes to the `Theory` contract, the ledger, or scoring.** Not one line of `tools/theory.py`, `tools/ledger.py`, or `tools/score.py` is touched by this plan.
- **No orchestration code, agent framework, or dispatch protocol.** The two-level agent structure is supported by surfaces, not enforced by code.
- **No migration of existing notes.** Content already in `THEORY.md` Learnings and `RESEARCH_LOG.md` stays exactly where it is; the convention is forward-only and the seeded `NOTES.md` files point at the old locations rather than absorbing them.
- **No per-theory private or hidden anything.** Every document that mentions the split must also say reading is open.
- **Prohibitions are absolute and must be worded that way:** there is no `tools/backtest.py` replay engine and no `backtest()` method on the `Theory` contract, and neither gets built absent a new spec that overturns this one.
- **Markdown wraps at ~76 characters**, matching every existing document in this repo. Do not reflow paragraphs you are not editing.
- **Today's date is 2026-08-25.** Use it verbatim in every dated entry.
- **Commit messages** use the repo's `docs:` / `feat:` / `fix:` prefix style and end with:
  ```
  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```
- **Verification for documentation tasks is `grep`, not `pytest`.** Prose cannot be unit-tested; each doc task below ends with exact `grep` commands that must match. Run the full suite (`python -m pytest -q`) at Task 7 and Task 8 to confirm nothing regressed.

---

### Task 1: The `NOTES.md` convention — template and two seeds

Creates the artifact every later task references. Nothing else in the plan makes sense until the file exists and its format rules are written down in one canonical place.

**Files:**
- Create: `theories/_TEMPLATE/NOTES.md`
- Create: `theories/insider_bias/insider_judgment/NOTES.md`
- Create: `theories/insider_bias/mention_family/NOTES.md`
- Test: none (documentation; verified by `grep` in Step 4)

**Interfaces:**
- Consumes: nothing.
- Produces: the filename `NOTES.md`, and the canonical wording of three rules that Tasks 2–6 refer back to by name — the **format rule** (`## YYYY-MM-DD — <topic>` sections, newest last, append-only in spirit), the **distillation rule** (a note that changes what the theory claims or does graduates into `THEORY.md`; the raw note stays as audit trail), and the **open-read rule** (any session may read any theory's notes; the split governs writing only).

- [ ] **Step 1: Create the template notebook**

Create `theories/_TEMPLATE/NOTES.md` with exactly this content:

```markdown
# <Theory name> — notes

> Delete this quote block when you write your first entry.
>
> This is the theory's lab notebook: raw, dated, append-only. Dead ends and
> why they died, data-source quirks discovered the hard way, backtest
> narratives, hunches not yet worth a version bump, pointers to the
> `run_id`s and idea-registry entries involved. It is allowed to be messy,
> allowed to be wrong, allowed to be illegible to someone who has not read
> the rest of this folder.
>
> **Format.** `## YYYY-MM-DD — <topic>` sections, newest last. Append-only
> in spirit: correcting an error is fine, rewriting history is not.
>
> **The distillation rule.** When a note changes what this theory *claims*
> or *does*, that change lands in `THEORY.md` — Learnings, Status, or a
> version bump — and the raw note stays here as the audit trail. Same shape
> as a stage-2 heuristic migrating into stage 1: proven in the messy layer,
> promoted to the authoritative one. `THEORY.md` gets the summary and a
> pointer, never a copy.
>
> **Nothing here is private.** Any session may read any theory's notes, and
> connecting dots across theories is encouraged — `mention_family` exists
> because someone looked sideways at `insider_judgment`'s screen backtest.
> The per-theory split is about where things get *written*, never about who
> may read them.
>
> **What does not belong here:** anything measured (the ledger and scores in
> SQLite), ideas worth deduplicating across theories (the idea registry —
> `python -m tools.cli ideas search`), and cross-cutting session narrative
> (`RESEARCH_LOG.md`).

## YYYY-MM-DD — <first entry>
```

- [ ] **Step 2: Seed `insider_judgment`'s notebook**

Create `theories/insider_bias/insider_judgment/NOTES.md` with exactly this content. It starts empty of history on purpose — the Global Constraints forbid migrating existing notes:

```markdown
# insider_judgment — notes

Lab notebook: raw, dated, append-only. The format and the distillation rule
are in `theories/_TEMPLATE/NOTES.md`. Nothing here is private — any session
may read any theory's notes.

## 2026-08-25 — Notebook opened; where this theory's history lives

This file starts empty by design. Everything written before today stayed
where it was written, and none of it was migrated:

- **`THEORY.md` Learnings** — the distilled record: the reality-TV stage-2
  heuristic deliberately left unencoded until it is measured against the
  endorsed/rejected split, the `edge_basis='prior'` imported-history
  exception (LLM-introspected `q` values from `kalshi_trader`'s pick stage,
  kept precisely because they are the only dataset that can answer whether
  introspected probabilities realize their claimed edge), and the Big
  Brother correction.
- **`RESEARCH_LOG.md`** — the session narratives: the 2026-08-24 tier A
  backtest of the stage-1 screen, including the 47-minute false start that
  preceded it, and the 2026-08-24 Big Brother / mention-family follow-ups.
- **`backtest.py`'s module docstring** — the three constraints that shape
  the replay: combinatorial-series fetch scoping, the category pre-filter's
  status as a fetch-scoping decision rather than a change to the screen
  under test, and per-day versus cumulative candle volume.

From here on, raw findings about this theory land in this file, and
`THEORY.md` changes only when the claim, the procedure, or the status
changes.
```

- [ ] **Step 3: Seed `mention_family`'s notebook**

Create `theories/insider_bias/mention_family/NOTES.md` with exactly this content:

```markdown
# mention_family — notes

Lab notebook: raw, dated, append-only. The format and the distillation rule
are in `theories/_TEMPLATE/NOTES.md`. Nothing here is private — any session
may read any theory's notes.

## 2026-08-25 — Notebook opened; where this theory's history lives

This file starts empty by design; nothing was migrated into it.

- **`THEORY.md` Learnings** — the distilled record, including the
  2026-08-25 skeptical audit of the backtest edge: the mechanics came back
  clean (no lookahead, fees included, negligible event clustering, stable
  pre-event favorites) but the statistical case is much weaker than the
  headline reads — pooled p=0.0395 gross, p=0.070 after fees, before any
  correction for this family having been *selected* as the standout slice
  of a 200-row backtest.
- **`RESEARCH_LOG.md`** — the session narratives: the 2026-08-24 split from
  `insider_judgment` into a separate theory, and the 2026-08-25 audit in
  full.

From here on, raw findings about this theory land in this file, and
`THEORY.md` changes only when the claim, the procedure, or the status
changes.
```

- [ ] **Step 4: Verify all three files exist and carry the three rules**

Run each command and confirm the expected match:

```bash
ls theories/_TEMPLATE/NOTES.md \
   theories/insider_bias/insider_judgment/NOTES.md \
   theories/insider_bias/mention_family/NOTES.md
grep -c "distillation rule" theories/_TEMPLATE/NOTES.md
grep -c "Nothing here is private" theories/_TEMPLATE/NOTES.md
grep -l "2026-08-25 — Notebook opened" theories/insider_bias/*/NOTES.md
```

Expected: all three paths listed; both `grep -c` return `1`; the last command lists exactly two paths.

- [ ] **Step 5: Confirm no test reads theory-folder structure**

The suite has no test that enumerates required files in a theory folder, so adding one is safe. Confirm:

```bash
python -m pytest -q tests/test_registry.py tests/test_conventions.py
```

Expected: PASS, no collection errors.

- [ ] **Step 6: Commit**

```bash
git add theories/_TEMPLATE/NOTES.md \
        theories/insider_bias/insider_judgment/NOTES.md \
        theories/insider_bias/mention_family/NOTES.md
git commit -m "docs: each theory gets a lab notebook

NOTES.md is raw, dated, append-only; THEORY.md keeps only the distilled
version. Seeds point at where existing history lives rather than moving
it -- the convention is forward-only.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Theory template — Learnings becomes distilled, backtest section names its owner

The template is what every future theory is copied from, so it is the highest-leverage document in the plan.

**Files:**
- Modify: `theories/_TEMPLATE/THEORY.md:128-145` (the "How to backtest" and "Learnings" sections)
- Test: none (documentation; verified by `grep` in Step 4)

**Interfaces:**
- Consumes: the `NOTES.md` filename and the distillation rule from Task 1.
- Produces: the phrase "**The replay lives in this folder**" and the harness-versus-theory split wording that Tasks 3, 4, and 5 restate for their own audiences.

- [ ] **Step 1: Add the replay-ownership paragraph to "How to backtest"**

In `theories/_TEMPLATE/THEORY.md`, find the tier list that ends the "How to backtest" section — the last line is:

```markdown
- **Tier C** — LLM judgment on pre-cutoff markets. Contaminated; indicative
  only, and excluded from credibility.
```

Insert immediately after it (leaving a blank line between):

```markdown
**The replay lives in this folder**, as `backtest.py` by convention. The
harness supplies point-in-time data (`tools/kalshi/history.py`,
`tools/snapshot.py`), run bookkeeping (`run_mode="backtest"` plus a real
`run_id`, and the `backtest_runs` table), and scoring — and nothing else.
Reconstructing *this* theory's decision at a past moment, over whatever
slice of history is actually fetchable, accepting whatever approximations
that forces, is thesis-specific work that belongs here. Two rules make the
result mean something: call the same functions the live path calls (a
backtest of a reimplemented screen is a backtest of nothing), and state the
reconstruction's known biases in this section, because a replay whose
biases are not written down produces a number nobody can caveat.
```

- [ ] **Step 2: Rewrite the Learnings section**

Find the end of the file:

```markdown
## Learnings

Running journal — what worked, what did not, what surprised you.
```

Replace those two content lines (keep the `## Learnings` heading) with:

```markdown
## Learnings

The **distilled** record: what this theory now knows that changes what it
claims or how it runs. Not a journal — raw working notes (dead ends, data
quirks, backtest narratives, hunches not yet worth a version bump) go in
`NOTES.md` in this folder, and graduate into this section only when they
change the theory's claims, procedure, or status. Summarize and point at
the `NOTES.md` entry; do not copy it.
```

- [ ] **Step 3: Verify the template teaches both rules**

```bash
grep -n "The replay lives in this folder" theories/_TEMPLATE/THEORY.md
grep -n "NOTES.md" theories/_TEMPLATE/THEORY.md
grep -c "Running journal" theories/_TEMPLATE/THEORY.md
```

Expected: the first two return line numbers (the second returns two matches — one per edited section); the third returns `0`, proving the old journal wording is gone.

- [ ] **Step 4: Commit**

```bash
git add theories/_TEMPLATE/THEORY.md
git commit -m "docs: template says where a replay lives and what Learnings is for

Learnings is the distilled record, not a journal -- the journal is
NOTES.md. The backtest section now names the harness/theory split.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `CLAUDE.md` — the authoritative statement

This is the document loaded into every session's context, so it carries the full rule. It is the single most important task in the plan: success criterion 1 depends on a session reading this before reaching for a shared backtest engine.

**Files:**
- Modify: `CLAUDE.md` — insert a new section before `## Never state a probability you introspected` (currently line 159); plus three one-line pointers at `## Toolkit` (~line 241), `## Backtest tiers` (~line 308), and `## Data conventions` (~line 387)
- Test: none (documentation; verified by `grep` in Step 5)

**Interfaces:**
- Consumes: the `NOTES.md` filename and its three rules (Task 1); the harness-versus-theory split wording (Task 2).
- Produces: the section title `## What lives in a theory, and what gets elevated`, referenced verbatim by the pointers in Steps 2–4 and by `tools/README.md` in Task 4.

- [ ] **Step 1: Insert the new section**

In `CLAUDE.md`, find the line `## Never state a probability you introspected` and insert the following immediately **before** it, with one blank line separating the new section from the preceding text and one before the existing heading:

```markdown
## What lives in a theory, and what gets elevated

**Everything starts in the theory that needs it, and elevation is earned,
never anticipatory.** Code elevates by *caller count* — a helper moves to
`tools/` once it has more than one real caller. Knowledge elevates by
*audience* — a note moves up when the repo level needs it to orient. The
two are different operations: elevating code is a **migration** (one
implementation; delete the local copy), elevating knowledge is a
**distillation** (the raw note stays behind as the audit trail).

Stays in the theory folder: screen, pricing and pipeline code; the backtest
replay (`backtest.py`); judging prompts (`prompts/`); the run procedure
(`RUNBOOK.md`); raw research notes (`NOTES.md`); and any research data the
theory reads. Always elevated: durable facts (`theory_facts`), everything
measured (the ledger and scores), ideas considered or dropped (the idea
registry, which exists to deduplicate *across* theories), tests and their
fixtures (`tests/theories/`, `tests/characterization/` — the repo runs one
suite), and cross-cutting session narrative (`RESEARCH_LOG.md`).

**Backtests: the harness owns time, bookkeeping and scoring; the theory
owns the replay.** The harness's contribution is complete, and it is small
— point-in-time data (`tools/kalshi/history.py`, `tools/snapshot.py`), run
identity (`run_mode="backtest"` and a real `run_id`, propagated everywhere
by `finish()`; the `backtest_runs` table), and scoring by run id.
Everything else is thesis-specific: which slice of history is even
fetchable, how to reconstruct this theory's decision without lookahead, and
which approximations that forces. `insider_judgment/backtest.py` spent most
of its design on problems no second theory shares — one combinatorial
series settling 400,000 markets a day that must be scoped around before any
fetch, per-day candle volume that has to be summed into a lifetime total
with a warm-up window, and a category pre-filter that must not leak into
the screen under test.

So: **there is no `tools/backtest.py` replay engine and no `backtest()`
method on the `Theory` contract, and neither gets built.** A second
theory-local backtest that resembles the first is *not* grounds for an
engine — a shared replay would have to either anticipate every such quirk
(it cannot) or paper over it silently (worse). Narrow primitives may still
be promoted one at a time under the normal rule — `systematic_sample`, a
checkpointed per-series iterator, a candle-walk state reconstructor — as
plain functions in `tools/`, never as a framework that inverts control over
the theory.

**`NOTES.md` is each theory's lab notebook** — dated, append-only, raw.
Dead ends and why they died, data-source quirks, backtest narratives,
hunches. `THEORY.md` carries only the distilled version and changes when
the claim, the procedure, or the status changes. `RESEARCH_LOG.md` stays
cross-theory: when a session's work sits inside one theory, the log entry
is a pointer to that theory's `NOTES.md` entry, not a copy of it.

**Reading is open; only writing is segregated.** Any session may read any
theory's notes, code, or prompts at any time, and connecting dots across
theories is encouraged — `mention_family` exists because someone looked
sideways at `insider_judgment`'s screen backtest. Nothing in this repo is
private.

This shape also supports — without requiring — a **repo-level agent** that
understands every theory from a high level and **theory-level agents** that
each know one theory in depth. Nothing orchestrates that today, and nothing
needs to. What holds the option open is one rule: **any fact the repo level
needs must surface in a shared structure** — `THEORY.md`, the database, or
`RESEARCH_LOG.md`. A theory whose true status is discoverable only by
reading its `NOTES.md` has broken that surface, and the fix is distillation
upward, not a repo level that reads every notebook. Symmetrically, a theory
folder must stay self-sufficient to run: **no imports from a sibling
theory's folder** — shared ancestry goes through a shared parent module (as
`theories/insider_bias/screen.py` does) or through `tools/`.
```

- [ ] **Step 2: Point the Toolkit promotion note at the full rule**

In the `## Toolkit` section, find:

```markdown
**New code starts in the theory that needs it** and moves to `tools/` only
once it has more than one real caller. That is a judgment call, not an
automatic rule.
```

Replace with:

```markdown
**New code starts in the theory that needs it** and moves to `tools/` only
once it has more than one real caller. That is a judgment call, not an
automatic rule. See "What lives in a theory, and what gets elevated" for
the whole rule, including what never elevates and what the harness
deliberately does not provide.
```

- [ ] **Step 3: Cross-reference from Backtest tiers**

At the end of the `## Backtest tiers` section, after the line:

```markdown
Web search stays off in every backtest judgment subagent.
```

add:

```markdown
Where the replay itself lives — and why there is no shared backtest engine
— is under "What lives in a theory, and what gets elevated".
```

- [ ] **Step 4: Add the `NOTES.md` bullet to Data conventions**

In `## Data conventions`, find:

```markdown
- **`THEORY.md`** is the source of truth for a hypothesis and its procedure.
```

Insert immediately after it:

```markdown
- **`NOTES.md`** in a theory folder is that theory's raw lab notebook —
  dated, append-only; the distilled version lives in its `THEORY.md`. Any
  session may read any theory's notes.
```

- [ ] **Step 5: Verify every claim landed**

```bash
grep -n "^## What lives in a theory, and what gets elevated" CLAUDE.md
grep -c "there is no \`tools/backtest.py\` replay engine" CLAUDE.md
grep -c "Reading is open; only writing is segregated" CLAUDE.md
grep -c "no imports from a sibling" CLAUDE.md
grep -n "What lives in a theory, and what gets elevated" CLAUDE.md | wc -l
grep -n "NOTES.md" CLAUDE.md | head
```

Expected: the section heading exists; the three `grep -c` each return `1`; the section name appears **3** times total (its own heading plus the two pointers from Steps 2 and 3); `NOTES.md` appears in both the new section and the Data conventions bullet.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: what lives in a theory, and what gets elevated

The harness owns time, bookkeeping and scoring for a backtest; the theory
owns the replay. No shared replay engine, no backtest() on the contract.
NOTES.md is the per-theory notebook; reads across theories stay open.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: `tools/README.md` — the prohibition where a tool author will read it

`CLAUDE.md` reaches the session; this file reaches whoever is about to *write a tool*. That is the person who would otherwise create `tools/backtest.py`, so the ban has to be here too.

**Files:**
- Modify: `tools/README.md` — append two bullets to the `## Conventions` list (which currently ends at the "A basket must still pay floor-or-ceiling" bullet, ~line 86)
- Test: none (documentation; verified by `grep` in Step 3)

**Interfaces:**
- Consumes: the section name `What lives in a theory, and what gets elevated` (Task 3); the `NOTES.md` filename (Task 1).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Append the backtest-ownership convention**

In `tools/README.md`, the `## Conventions` list ends with the bullet beginning `- **A basket must still pay floor-or-ceiling to be *scored*.**` and ending `...that is not built.` Append these two bullets immediately after it, before the `## Writing a new tool` heading:

```markdown
- **For a backtest, this layer owns time, bookkeeping and scoring; the
  theory owns the replay.** `kalshi/history.py` and `snapshot.py`
  (point-in-time truth), the `run_mode`/`run_id` plumbing through
  `theory.finish()`, the `backtest_runs` table, and `score.py` are the
  whole shared contribution. **There is no `tools/backtest.py` replay
  engine, and none gets built** — `insider_judgment/backtest.py` shows why:
  most of its design handles quirks (a combinatorial series settling
  400,000 markets a day, per-day candle volume that must be summed into a
  lifetime total, a fetch-scoping filter that must not leak into the screen
  under test) that no second theory shares. A shared engine would have to
  either anticipate every such quirk or paper over it silently, and a
  second theory-local backtest resembling the first is not evidence that it
  could. Narrow primitives still promote one at a time under the rule below
  — `systematic_sample`, a checkpointed per-series iterator, a candle-walk
  state reconstructor — as plain functions, never as a framework that
  inverts control over the theory.
- **Code elevates by caller count; knowledge elevates by audience.** The
  promotion rule below moves a helper into `tools/` when a second theory
  really calls it. A research note moves instead into whatever the *repo
  level* reads: `THEORY.md` if it changes the theory's claims, the database
  if it is a fact or a result, `RESEARCH_LOG.md` if it is session
  narrative. Raw notes (a theory's `NOTES.md`) never move at all — they get
  summarized, and the raw entry stays as the audit trail. See CLAUDE.md,
  "What lives in a theory, and what gets elevated".
```

- [ ] **Step 2: Verify**

```bash
grep -n "There is no \`tools/backtest.py\` replay engine" tools/README.md
grep -n "Code elevates by caller count" tools/README.md
grep -n "^## Writing a new tool" tools/README.md
```

Expected: all three return line numbers, and the first two line numbers are **smaller** than the third — the bullets landed inside `## Conventions`, not after it.

- [ ] **Step 3: Commit**

```bash
git add tools/README.md
git commit -m "docs: no shared backtest engine, and how knowledge elevates

Stated where a tool author reads it: this layer owns time, bookkeeping and
scoring; the replay stays in the theory. Narrow helpers still promote one
at a time.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: `backtest-theory` skill — replay location and where narrative goes

**Files:**
- Modify: `.claude/skills/backtest-theory/SKILL.md` — add a bullet at the top of `## 2. Enforce the rules`, and a closing paragraph in `## 5. Score and caveat`
- Test: none (documentation; verified by `grep` in Step 3)

**Interfaces:**
- Consumes: the replay-ownership wording (Tasks 2–4) and the `NOTES.md` filename (Task 1).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Add the replay-location rule**

In `.claude/skills/backtest-theory/SKILL.md`, find the `## 2. Enforce the rules` heading. Its first bullet currently begins:

```markdown
- **`TheoryContext(run_mode="backtest")` is what a replay keys on.**
```

Insert this bullet immediately **before** that one, so it is the first thing in the section:

```markdown
- **The replay code lives in the theory's folder**, as `backtest.py` by
  convention — `theories/insider_bias/insider_judgment/backtest.py` is the
  worked example. The harness gives you point-in-time data, run identity,
  tiers and scoring; reconstructing *this* theory's decision at a past
  moment is thesis-specific and stays local. **Never write or extend a
  shared replay engine** (`tools/backtest.py`), and never add a
  `backtest()` method to the `Theory` contract. A backtest is a driver
  script that builds a backtest-mode context and calls the same `screen()`
  and `price()` the live path calls — replaying a reimplementation of the
  screen is a backtest of nothing.
```

- [ ] **Step 2: Say where results go and where narrative goes**

At the very end of the file, after:

```markdown
Report the tier alongside every number. Tier C results are **excluded from
credibility** — never present them as evidence of edge, only as a sanity check
on the screening stage.
```

append:

```markdown
Backtest **results** live in the database: rows tagged
`run_mode="backtest"` plus the `backtest_runs` row. Backtest **narrative**
— what you tried, what broke, why the window is the window, which
approximations the reconstruction accepts and in which direction they bias
— goes in that theory's `NOTES.md`, and reaches `THEORY.md` only if the
result changes what the theory claims. The biases belong in `THEORY.md`'s
"How to backtest" section too, since they are part of the procedure.
```

- [ ] **Step 3: Verify**

```bash
grep -n "The replay code lives in the theory's folder" .claude/skills/backtest-theory/SKILL.md
grep -n "Never write or extend a shared replay engine" .claude/skills/backtest-theory/SKILL.md
grep -n "NOTES.md" .claude/skills/backtest-theory/SKILL.md
```

Expected: all three return line numbers; the first appears before the `TheoryContext(run_mode=` bullet (confirm by eye with `sed -n '35,50p'` on the file).

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/backtest-theory/SKILL.md
git commit -m "docs: backtest-theory says where the replay lives

The replay is theory-local; never build a shared engine. Results go to the
DB, narrative to the theory's NOTES.md.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: `go` and `score-theories` skills — stop routing findings to `THEORY.md`

The blocking task for success criterion 2. Both skills currently instruct the old behavior, so until this lands, the first session after the spec would break the convention in good faith while correctly following its own skill.

**Files:**
- Modify: `.claude/skills/go/SKILL.md:101-102` (end of `## 3. Log it`)
- Modify: `.claude/skills/score-theories/SKILL.md:124-125` (end of the diagnosis checklist)
- Test: none (documentation; verified by `grep` in Step 3)

**Interfaces:**
- Consumes: the `NOTES.md` filename and the distillation rule (Task 1).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Reword `go`'s logging step**

In `.claude/skills/go/SKILL.md`, find these two lines at the end of `## 3. Log it`:

```markdown
Theory-specific findings also go in that theory's `THEORY.md` Learnings.
This log is what makes a year of sessions accumulate instead of repeat.
```

Replace with:

```markdown
Keep this log cross-cutting. Theory-specific findings go in that theory's
`NOTES.md` — dated, raw, append-only — and the log entry points at them
rather than repeating them; `THEORY.md` changes only when the claim, the
procedure, or the status changes. This log is what makes a year of sessions
accumulate instead of repeat.
```

- [ ] **Step 2: Reword `score-theories`' reporting line**

In `.claude/skills/score-theories/SKILL.md`, find:

```markdown
Report what you found either way. "n=29, inside the noise, no slice tested
yet" is a real result and belongs in `THEORY.md` Learnings.
```

Replace with:

```markdown
Report what you found either way. "n=29, inside the noise, no slice tested
yet" is a real result and belongs in that theory's `NOTES.md` — distilled
into `THEORY.md` only if it changes the theory's standing: a status change,
a version bump, or a claim you can no longer make.
```

- [ ] **Step 3: Verify the old instruction is gone from both**

```bash
grep -rn "THEORY.md\` Learnings" .claude/skills/
grep -n "NOTES.md" .claude/skills/go/SKILL.md .claude/skills/score-theories/SKILL.md
```

Expected: the first command returns **nothing** (exit status 1) — no skill still routes findings to `THEORY.md` Learnings. The second returns one line-number match per file.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/go/SKILL.md .claude/skills/score-theories/SKILL.md
git commit -m "docs: session findings go to the theory's NOTES.md

Both skills routed theory-specific findings to THEORY.md Learnings, which
is the behavior the locality spec replaces. The log gets a pointer, not a
copy.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7 (GATED — needs the user's go-ahead before starting): Enforce self-sufficiency — no sibling-theory imports

> **Do not start this task without the user's explicit approval, and do not
> let it block Tasks 1–6 or Task 8, which do not depend on it.**
>
> **Why it is gated.** While this plan was being written, a probe of the
> proposed test found a real violation already in the repo:
> `theories/insider_bias/mention_family/backtest.py` (untracked, created
> 2026-08-25 by another session, possibly mid-run) contains
> `from theories.insider_bias.insider_judgment import backtest as sibling`
> and calls `sibling.candidate_series()` and `sibling.replay_market()`.
>
> That import is **deliberate and well-reasoned**, not sloppiness: its
> module docstring says the population definition and the replay must be
> reused "byte for byte" so that "a difference in results means a different
> period, not a different population rule." Duplicating the replay would
> destroy exactly the comparability the extension backtest exists to
> establish.
>
> The spec is not wrong here, and it already names the remedy: shared
> ancestry goes through a **shared parent module**, as
> `theories/insider_bias/screen.py` already does for the screen these two
> theories share. The machinery in question replays *that shared screen*,
> so it belongs beside it in `theories/insider_bias/`, not inside one
> theory's folder. Note that promoting it to `tools/` would violate the
> other half of this spec — it is a replay, and there is no shared replay
> engine. The shared **parent**, not the shared **layer**, is the correct
> destination.
>
> So this task now has two halves: the guard test, and the move that brings
> the repo into compliance with it. The move touches another session's
> in-flight, uncommitted file, which is why it needs the user's ruling
> first. If the user declines or wants to wait, **skip this task entirely**
> — Tasks 1–6 and 8 stand on their own, and success criterion 4 stays
> verified by inspection as the spec originally had it.

This is the one success criterion that is mechanically checkable. The repo already enforces conventions structurally (`tests/test_conventions.py` guards the singleton shape, the never-overridden workflow, the numeric-free `Verdict`, and registry drift), so the test belongs there rather than staying an inspection.

**Files:**
- Create: `theories/insider_bias/replay.py` (via `git mv` from `theories/insider_bias/insider_judgment/backtest.py`)
- Modify: `theories/insider_bias/mention_family/backtest.py:62` (the sibling import)
- Modify: `tests/theories/test_insider_bias_backtest.py` (import path only)
- Modify: `tests/test_conventions.py` (add imports at the top and one test at the end)
- Modify: `theories/insider_bias/insider_judgment/THEORY.md` and `theories/insider_bias/mention_family/THEORY.md` (one changelog line each)
- Modify: `docs/superpowers/specs/2026-08-25-theory-locality-design.md` (§5 gains item 10, so the spec and this plan agree)
- Test: `tests/test_conventions.py::test_no_theory_imports_a_sibling_theory`

**Interfaces:**
- Consumes: `registry.discover()` — returns `dict[str, Theory]`, already imported in this file as `from tools import db, domain, registry`.
- Produces: the module path `theories.insider_bias.replay`, exporting the names unchanged from their current home: `VOLUME_WARMUP_DAYS`, `NO_CATEGORIES`, `DEFAULT_RECENCY_DAYS`, `is_candidate(raw: dict) -> bool`, `candidate_series(now: datetime | None = None, recency_days: float = DEFAULT_RECENCY_DAYS) -> list[dict]`, `iter_settled_survivors(series_list: list[dict], min_close_ts: int, max_close_ts: int) -> Iterator[tuple[str, list[dict]]]`, `settled_survivors(min_close_ts: int, max_close_ts: int, series_list: list[dict] | None = None) -> list[dict]`, `replay_market(settled: Market, series_ticker: str) -> dict | None`, `systematic_sample(items: list[dict], n: int) -> list[dict]`.

- [ ] **Step 0: Confirm the move is safe to make right now**

The file being touched is another session's uncommitted work, and its `run` mode checkpoints to disk as it walks. Before moving anything:

```bash
git status --short theories/insider_bias/mention_family/backtest.py
ls -la theories/insider_bias/mention_family/*.json 2>/dev/null
```

If a checkpoint file exists and its mtime is within the last few minutes, a backtest is probably running — **stop and ask** rather than moving a module out from under a live process.

- [ ] **Step 1: Move the shared replay machinery to the shared parent**

The module replays `theories/insider_bias/screen.py`, which both theories share, so it belongs beside it. Preserve history with `git mv`:

```bash
git mv theories/insider_bias/insider_judgment/backtest.py \
       theories/insider_bias/replay.py
```

Then update the first line of its docstring, which currently reads:

```python
"""insider_bias — tier A backtest of the stage-1 screen alone.
```

to:

```python
"""insider_bias — tier A replay of the shared stage-1 screen.

Lives in the shared parent package, not in one theory's folder, because
the screen it replays (`theories/insider_bias/screen.py`) is shared by
every theory in this family: `insider_judgment` backtests its own stage 1
with it, and `mention_family`'s extension backtest reuses the very same
population rules and replay so a difference in results means a different
period, not a different rule. Moved here 2026-08-25 with no change to any
logic -- neither theory's version bumps.
```

Change nothing else in the file. No function body, constant, or import is edited; `from theories.insider_bias import screen` still resolves from the parent package.

- [ ] **Step 2: Repoint `mention_family`'s driver**

In `theories/insider_bias/mention_family/backtest.py`, replace line 62:

```python
from theories.insider_bias.insider_judgment import backtest as sibling
```

with:

```python
from theories.insider_bias import replay as sibling
```

Keep the local alias `sibling` so every call site (`sibling.candidate_series(...)`, `sibling.replay_market(...)`) is untouched. Then fix the two docstring phrases that now misdescribe the source — in the module docstring, `the sibling machinery's` becomes `the shared parent's` in both places (design choice 1 and design choice 2), and in `RATIONALE`, `the sibling machinery's replay_market()` becomes `the shared parent's replay_market()`.

- [ ] **Step 3: Repoint the existing tests**

In `tests/theories/test_insider_bias_backtest.py`, update the import of the moved module to `from theories.insider_bias import replay` (keeping whatever local alias the file already uses, so no assertion changes). Find every reference first:

```bash
grep -rn "insider_judgment import backtest\|insider_judgment\.backtest" \
    tests/ tools/ theories/ docs/
```

Update every hit outside `docs/` (documentation references to the old path are corrected in Step 9, not here).

- [ ] **Step 4: Prove the move changed no behavior**

Run: `python -m pytest tests/theories/ -q`
Expected: PASS, with the same number of tests as before the move. A failure here means the move was not mechanical — revert and re-do it, do not adjust an assertion to fit.

- [ ] **Step 5: Write the guard test**

Add to the top of `tests/test_conventions.py`, after `import pytest`:

```python
import ast
from pathlib import Path
```

and add this constant below the existing imports (after the `from tools.theory import Theory, TheoryRun` line):

```python
ROOT = Path(__file__).resolve().parents[1]
```

Then append this test to the end of the file:

```python
def _absolute_module(path: Path, node: ast.ImportFrom) -> str:
    """The module an ImportFrom names, resolved if it is relative.

    `from ..mention_family import x` inside insider_judgment reaches a
    sibling exactly as an absolute import would; resolving it here means
    the rule cannot be dodged by writing the import the other way.
    """
    if not node.level:
        return node.module or ""
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    base = parts[:-1]                      # the file's own package
    for _ in range(node.level - 1):
        base = base[:-1]
    return ".".join(base + ([node.module] if node.module else []))


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(_absolute_module(path, node))
    return names


def test_no_theory_imports_a_sibling_theory():
    """A theory folder stays self-sufficient to run (locality spec 4).

    Shared ancestry goes through a shared parent module
    (theories/insider_bias/screen.py) or through tools/ -- never through a
    sibling theory's folder, which would make understanding one theory
    require reading two. Parsed with ast, so checking this imports
    nothing.
    """
    packages = {
        type(theory).__module__.rsplit(".", 1)[0]
        for theory in registry.discover().values()
    }
    problems = []
    for pkg in sorted(packages):
        pkg_dir = ROOT.joinpath(*pkg.split("."))
        siblings = packages - {pkg}
        for path in sorted(pkg_dir.rglob("*.py")):
            for name in _imported_modules(path):
                for other in siblings:
                    if name == other or name.startswith(other + "."):
                        rel = path.relative_to(ROOT).as_posix()
                        problems.append(f"{rel} imports {name}")
    assert problems == [], (
        "a theory imports a sibling theory's folder -- route shared code "
        "through a shared parent module or tools/ instead:\n"
        + "\n".join(problems)
    )
```

- [ ] **Step 6: Run it — it passes only because Steps 1–3 landed**

Run: `python -m pytest tests/test_conventions.py::test_no_theory_imports_a_sibling_theory -v`
Expected: PASS.

If you skipped the move, this test **fails** with
`theories/insider_bias/mention_family/backtest.py imports theories.insider_bias.insider_judgment` — that was the state of the repo when this plan was written, and it is the whole reason this task is gated. A failure here means Step 2 did not take effect; do not weaken the test to make it green.

- [ ] **Step 7: Prove the test actually catches a violation**

Introduce a real violation, confirm the test fails, then remove it:

```bash
printf 'from theories.insider_bias.mention_family import mention_bucket  # temp\n' \
    > theories/insider_bias/insider_judgment/_violation_probe.py
python -m pytest tests/test_conventions.py::test_no_theory_imports_a_sibling_theory -v
```

Expected: **FAIL**, with the assertion message listing
`theories/insider_bias/insider_judgment/_violation_probe.py imports theories.insider_bias.mention_family`.

Then remove the probe and confirm green again:

```bash
rm theories/insider_bias/insider_judgment/_violation_probe.py
python -m pytest tests/test_conventions.py::test_no_theory_imports_a_sibling_theory -v
```

Expected: PASS. Confirm the probe file is gone with `git status --short` before continuing — it must not be committed.

- [ ] **Step 8: Run the whole suite for regressions**

Run: `python -m pytest -q`
Expected: all tests pass (the pre-existing baseline is 621 passed, 4 deselected; the count is now one higher). If anything fails, stop and diagnose — the only production change in this task is a file move with no logic edit, so any failure is either a missed import reference (Step 3) or genuinely unrelated. Do not paper over either.

- [ ] **Step 9: Record the move in both theories' changelogs**

Neither theory's version bumps — no decision logic changed, only where a module sits (`tools/README.md`: a move is a version bump only "if behavior changed at all in the move"). Add one line to the Version changelog section of each of `theories/insider_bias/insider_judgment/THEORY.md` and `theories/insider_bias/mention_family/THEORY.md`:

```markdown
- 2026-08-25 — the stage-1 screen's replay moved from
  `insider_judgment/backtest.py` to the shared parent as
  `theories/insider_bias/replay.py`, beside the `screen.py` it replays.
  No logic changed and **no version bump**: both theories call the same
  functions with the same arguments and get the same results. The move
  restores the rule that a theory folder never imports a sibling's.
```

Also fix any stale path references the Step 3 grep found in `docs/` and in either `RUNBOOK.md`.

- [ ] **Step 10: Record the test in the spec's change list**

In `docs/superpowers/specs/2026-08-25-theory-locality-design.md`, `## 5. Concrete changes`, the list currently ends with item 9 (`RESEARCH_LOG.md`). Change the opening line of that section from:

```markdown
Documentation and convention changes only — no behavior, schema, or
contract changes anywhere.
```

to:

```markdown
Documentation and convention changes, plus one guard test — no behavior,
schema, or contract changes anywhere.
```

and append item 10 to the list:

```markdown
10. **`tests/test_conventions.py`** — one added test,
    `test_no_theory_imports_a_sibling_theory`, making success criterion 4
    hold mechanically instead of by inspection. This repo already enforces
    its conventions structurally (the singleton shape, the never-overridden
    workflow, `Verdict`'s numeric-field ban, registry drift), and this rule
    is code hygiene rather than agent orchestration, so it belongs with
    them. The "supported, not enforced" stance in §4 is about orchestration
    only. Landing it required one compliance move, recorded below.
11. **`theories/insider_bias/replay.py`** — the stage-1 screen's replay,
    moved out of `insider_judgment/backtest.py` into the shared parent
    beside the `screen.py` it replays. `mention_family`'s extension
    backtest had begun importing it across the sibling boundary — a
    deliberate reuse (the population rules and the replay must be
    byte-identical for the two windows to be comparable) that this spec's
    own §4 rule already routes through a shared parent module, exactly as
    `screen.py` is. Not `tools/`: it is a replay, and there is no shared
    replay engine. No logic changed; neither theory's version bumps.
```

- [ ] **Step 11: Commit**

```bash
git add theories/insider_bias/replay.py \
        theories/insider_bias/mention_family/backtest.py \
        theories/insider_bias/insider_judgment/THEORY.md \
        theories/insider_bias/mention_family/THEORY.md \
        tests/theories/test_insider_bias_backtest.py \
        tests/test_conventions.py \
        docs/superpowers/specs/2026-08-25-theory-locality-design.md
git commit -m "refactor: the shared screen's replay moves to the shared parent

mention_family's extension backtest reuses insider_judgment's replay
byte-for-byte, on purpose -- so the module belongs beside the screen.py
both theories share, not inside one theory's folder. No logic changed,
neither version bumps.

A theory may no longer import a sibling's folder, enforced by
test_no_theory_imports_a_sibling_theory: success criterion 4 was
inspection-only, and this makes it mechanical. Relative imports are
resolved so the rule cannot be dodged by writing them the other way.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Log the decision and verify the whole plan against its own criteria

**Files:**
- Modify: `RESEARCH_LOG.md` (append one entry at the end)
- Test: full suite plus the criteria checks in Step 3

**Interfaces:**
- Consumes: everything above.
- Produces: the first log entry written under the new pointer rule — it is also the worked example of that rule.

- [ ] **Step 1: Append the log entry**

At the end of `RESEARCH_LOG.md`, append:

```markdown

---

## 2026-08-25 — Theory locality: backtests and research notes live in the
## theory, and reads stay open

Spec: `docs/superpowers/specs/2026-08-25-theory-locality-design.md`.
Plan: `docs/superpowers/plans/2026-08-25-theory-locality.md`.

**Did:** Wrote down what lives in a theory and what gets elevated, in the
places a future session actually reads: `CLAUDE.md` gained a "What lives in
a theory, and what gets elevated" section, `tools/README.md` two
conventions, `theories/_TEMPLATE/` a `NOTES.md` and a rewritten Learnings
section, and three skills (`backtest-theory`, `go`, `score-theories`) the
corrections that stop them teaching the old behavior. `insider_judgment`
and `mention_family` each got a seeded `NOTES.md`; no existing note was
migrated.

<!-- Keep the following paragraph only if Task 7 was approved and run;
     delete it entirely if Task 7 was skipped. -->
Writing the plan also turned up a live violation of the spec's own
self-sufficiency rule: `mention_family`'s new extension backtest imports
`insider_judgment`'s replay across the sibling boundary — deliberately,
since the population rules and the replay must be byte-identical for the
two windows to be comparable. The spec already prescribed the remedy, so
the replay moved to the shared parent as `theories/insider_bias/replay.py`,
beside the `screen.py` it replays, with no logic change and no version bump
on either theory. Not into `tools/`: it is a replay, and there is no shared
replay engine. A guard test —
`test_no_theory_imports_a_sibling_theory` — now keeps the boundary
mechanical rather than inspected.

**Learned:** Two of the three headline decisions were already argued from
evidence in this repo rather than from taste. The case against a shared
backtest engine is `insider_judgment/backtest.py` itself: most of its
design budget went to quirks — a combinatorial series settling 400,000
markets a day, per-day candle volume needing a warm-up sum, a fetch-scoping
category filter that must not leak into the screen under test — that no
second theory shares, so a generic engine would either anticipate all of
them or paper over them silently. A review pass also caught that two skills
still instructed the behavior the spec replaces, which would have broken
the convention on the very next `go` session in good faith; documents that
steer future sessions are load-bearing, and a spec that changes conventions
has to grep for every place the old one is taught.

**Next:** The convention is forward-only, so the first real test is the next
session that researches inside one theory — its findings belong in that
theory's `NOTES.md`, with a pointer from here, not a copy. Nothing about
theory standing, ranking, or the live board changed.
```

- [ ] **Step 2: Run the full suite one final time**

Run: `python -m pytest -q`
Expected: all pass, same count as Task 7 Step 4.

- [ ] **Step 3: Check the spec's four success criteria**

Run each and confirm:

```bash
# Criterion 1 -- the prohibition is stated in all three steering documents
grep -l "no \`tools/backtest.py\` replay engine\|There is no \`tools/backtest.py\`\|shared replay engine" \
    CLAUDE.md tools/README.md .claude/skills/backtest-theory/SKILL.md

# Criterion 2 -- no skill still routes findings to THEORY.md Learnings
grep -rn "THEORY.md\` Learnings" .claude/skills/ ; echo "exit=$?"

# Criterion 3 -- orientation sources unchanged and intact
ls RESEARCH_LOG.md theories/*/*/THEORY.md
python -m tools.cli theories list > /dev/null && echo "cli ok"

# Criterion 4 -- mechanical if Task 7 ran, by inspection if it was skipped
python -m pytest tests/test_conventions.py -q
grep -rn "insider_judgment import backtest" theories/ ; echo "exit=$?"
```

Expected: the first lists all three files; the second prints no matches and `exit=1`; the third lists both `THEORY.md` files and prints `cli ok`; the fourth passes. The fifth prints no matches (`exit=1`) if Task 7 ran; if Task 7 was skipped it still prints the `mention_family/backtest.py` hit, which is the known, user-deferred exception — report it in the handoff rather than fixing it here.

- [ ] **Step 4: Confirm no stray files**

```bash
git status --short
```

Expected: `RESEARCH_LOG.md` modified, and nothing else from this plan left uncommitted. No `_violation_probe.py` — if the probe from Task 7 is present, delete it. `theories/insider_bias/mention_family/backtest.py` may still show as untracked; that is another session's in-flight work and **is not yours to commit or delete**.

- [ ] **Step 5: Commit**

```bash
git add RESEARCH_LOG.md
git commit -m "docs: log the theory-locality decision

First entry written under the new pointer rule.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Notes for the executor

- **Do not migrate existing content.** Several tasks will tempt you to move a paragraph out of `THEORY.md` Learnings or `RESEARCH_LOG.md` into a `NOTES.md`. The spec forbids it: the convention is forward-only, and the seeds deliberately point at the old locations instead.
- **Do not soften the prohibitions.** "Prefer not to build a shared engine" is not what the spec says. The wording is absolute on purpose — it exists so a future session doing an obvious-looking refactor does not build the thing this spec argues against.
- **If a `grep` verification fails**, the edit landed in the wrong place. Re-read the surrounding lines before retrying rather than adding a second copy of the text.
- **Task 7 is gated and self-contained.** Never start it without the user's explicit approval, and never let waiting on that approval delay Tasks 1–6 or Task 8. If it is skipped, delete the marked paragraph from the `RESEARCH_LOG.md` entry in Task 8 Step 1 and report the deferred violation in the handoff.
- **`theories/insider_bias/mention_family/backtest.py` is another session's uncommitted work.** Task 7 Step 2 edits exactly one import line and three docstring phrases in it. Nothing else in this plan touches it, and no task commits it as a whole file.
