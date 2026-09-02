# Data locality and the ticket lifecycle

**Date:** 2026-09-01 · **Status:** design, awaiting review · **Supersedes:** nothing

Two standards, written together because they answer the same question from
opposite ends: **where does the output of a session go, and what is it
allowed to cost?**

- **Data locality** — what gets saved at all, and whose folder it lands in.
- **The ticket lifecycle** — how queued work moves, and when a finished
  ticket stops occupying the tree.

They meet at the evidence stage, which turns out to be a study.

## Why

**Data costs bloat and context confusion.** Neither is priced today. The
repo carries ~700MB, and while most of it is correctly owned and
gitignored, nothing says so: the two big data dirs are conventions
somebody followed, not rules anybody stated. There is no bar a session has
to clear before writing a file, and no statement of whose folder it goes
in.

**Meanwhile the same work has been filed in two places.** Five new-theory
specs were killed by a cheap measurement. Two of them produced a study;
three produced a probe directory under `tickets/new-theory/evidence/`
that `cli studies` cannot see, the floor's stall-detection does not
cover, and no verdict header describes:

| spec | measurement lived in | in `cli studies`? |
|---|---|---|
| `calendar-arb` | `studies/2026-08-27-calendar-arb-firing-rate/` | yes |
| `smile-smoothing` | `studies/2026-08-29-smile-smoothing-ladder-flatness/` | yes |
| `aggregation-gap` | `tickets/new-theory/evidence/2026-09-01-aggregation-gap-probe/` | **no** |
| `accumulation-decay` | `tickets/new-theory/evidence/2026-09-01-accumulation-decay-probe/` | **no** |
| `block-trade-whale-follow` | `tickets/new-theory/evidence/2026-09-01-block-trade-probe/` | **no** |

`studies/README.md` already claims this work. Its first listed reason to
run a study is *"Is this idea worth building?"*, and its worked example is
`calendar-arb-firing-rate` — *"that killed a spec in an afternoon instead
of after a month of building."* That is the evidence stage, described in
the studies doc, with three probe dirs quietly doing the same job under a
different name. This is the duplicated-home failure CLAUDE.md already
records once, when 22 spec documents in `docs/` all read "Status: backlog"
weeks after four had become theories. **One document, one home, one
status.**

**And the backlog only grows.** `close` moves a ticket to `completed/` and
explicitly never deletes it. That was the right call when the repo was a
week old; at 28 completed tickets it is starting to be the cost the data
standard is about.

## Part 1 — The data standard

### Two kinds of data, two rules

The existing principle — *"save as much as you can, while you can"* — is
not wrong, it is **unscoped**. It was written about perishable source
data and has been read as being about everything. The scope is restored
by one test:

> **Can a future session regenerate this from what is already on disk?**

- **No → source data.** Kalshi payloads, candles, per-trade corpora, LLM
  judgments already paid for in tokens. Unbuyable: Kalshi ages settled
  markets out of its public API after ~60 days, and a model's verdicts
  cost tokens that are not spent twice. **Capture aggressively; the
  existing rule is unchanged and still governs.**
- **Yes → derived data.** Intermediates, re-runnable aggregates, scratch
  analysis, restated summaries, a second copy of a number the ledger
  already holds. **Earns its keep two ways only: it is expensive to
  regenerate, or something cites it.** Default is not to keep it.

The asymmetry is deliberate. Losing source data is unrecoverable; losing
derived data costs CPU. Where the test is genuinely unclear, keep it — but
the test is usually not unclear.

### Data lands in the thing that produced it

**Two owners, and only two:**

| owner | folder |
|---|---|
| a theory | its registry path (not always `theories/<slug>`) |
| a study | `studies/<date>-<slug>/` |

An evidence-stage ticket is not a third owner: it scaffolds a study and
writes there (Part 3). That is the point of Part 3 — it is what makes this
list two entries long instead of two-and-a-special-case.

A focused session writes files into its own owner's folder and nowhere
else. **Reading stays open everywhere** — that is already the rule
("Reading is open; only writing is segregated") and nothing here narrows
it. A session may read any theory's notes, any study's data, any ticket,
at any time; it just may not deposit new files there.

### The shared sinks — the complete list

Writing outside your owner's folder is legitimate at exactly these
targets, and this list is closed:

1. **The database**, through the `tools/` APIs — ledger, scores,
   `theory_facts`, ideas, snapshots, provenance. This is the designed
   shared sink and needs no justification.
2. **`RESEARCH_LOG.md`** — append only, cross-cutting session narrative.
3. **Tickets — any lane, without restriction.** The one broad exception,
   and it is broad on purpose: a ticket is how a focused session tells
   another owner something without spending their attention. Filing one
   never needs a reason.
4. **`user_reports/<date>/`** — the floor lane only.
5. **`tests/` and their fixtures** — an *elevation*, which is a migration
   under the existing caller-count rule, not a casual write.

### The escape hatch

One, and it is narrow: **"my task is impossible otherwise."** Not
inconvenient, not slower — impossible. A session that takes it must say so
plainly in its report and file a ticket naming what it wrote and where, so
the escape is visible rather than absorbed.

### Big data dirs declare themselves

A data directory over **10MB** adds its own `.gitignore` entry
**naming the directory, not a filename** — the reason the existing
`series-bias-mining` entry already gives: the `-journal`, the WAL and the
per-run logs were all still untracked, so `git add -A` would have staged
them. This promotes a habit that is already followed twice into a rule.

## Part 2 — The ticket lifecycle

State is a directory, never a field. That is unchanged and load-bearing:
the backlog is read by listing, so a finished ticket has to leave it
physically. What changes is that **the set of states depends on the
lane**:

```
new-theory:    open → evidence → implement → completed
maintenance:   open → completed
theory, study: open → completed
```

| state | means |
|---|---|
| `open` | filed; nobody has started |
| `evidence` | a measurement is running against the spec's bar (new-theory only) |
| `implement` | the evidence cleared the bar — this is a build order (new-theory only) |
| `completed` | terminal, for every lane and every outcome |

**`completed/` is reachable from any state.** A spec does not have to
survive to the end of the pipeline to close; it closes the moment it is
resolved, from wherever it is.

### Closing a new-theory ticket: four resolutions

`resolution` is free text today. For the new-theory lane it gains a
required first word, because two of these mean opposite things about
re-proposing and the distinction is currently invisible:

| resolution | means | re-proposable? |
|---|---|---|
| `built` | became a running theory — name it | n/a |
| `disproven` | the bar was met and the thesis failed | **no** |
| `underpowered` | **the measurement could not reach the bar** — population too thin, history too short, liquidity too low. Must name what was missing and what would change it | **yes**, when conditions change |
| `superseded` | folded into another spec or theory | n/a |

`disproven` is `calendar-arb` and `smile-smoothing`: measured, and the
answer was no. `underpowered` is a different claim — *we could not tell* —
and it is the one the user specifically asked to be made explicit. **A
spec that cannot gather enough evidence goes to `completed/` like any
other**; it does not sit in `evidence/` indefinitely looking like work in
flight, and it is not left in `open/` looking unstarted.

### Closing elevates the knowledge first

**A `disproven` or `underpowered` close requires an ideas-registry entry
before `close` will accept it** — `ideas.update_status` with
`what_was_tried`, `outcome`, and for `underpowered` a `revisit_angle`
naming what would have to change.

This is not bookkeeping. It is what makes Part 4's purge safe: the file
may leave the tree after a week precisely because the durable fact
elevated out of it first. Without the coupling, purging an uncited
`underpowered` spec just lets somebody re-propose it in three weeks —
the exact failure the ideas registry exists to prevent.

### Transitions get verbs

```bash
cli tickets advance <path> --to evidence  --note "<what the probe tests>"
cli tickets advance <path> --to implement --note "<what the evidence showed>"
cli tickets close   <path> --resolution "<built|disproven|underpowered|superseded>: ..."
```

`advance` refuses a state its lane does not have, refuses to move
backwards, and refuses `--to implement` from `open` — the evidence stage
is not optional for a spec that has not been measured.

`status:` in the frontmatter stays `open` through `evidence` and
`implement`, becoming `done` only at `completed`. This is deliberate: a
spec being measured is still open work, `--status open` should show it,
and `backlog()` needs no change to its filter.

## Part 3 — The evidence stage is a study

**`advance --to evidence` scaffolds a real study** at
`studies/<date>-<slug>/`, and the ticket moves to
`tickets/new-theory/evidence/<date>-<slug>.md` as a plain file carrying
`study: <folder>` in its frontmatter and the bar in its body.

The measurement — its pre-registration, its code, its data, its verdict —
lives in the study folder. This buys four things a probe dir does not:

1. **`cli studies` sees every probe.** The survey reads `STUDY.md` off
   disk, so a scaffolded study appears the moment it exists.
2. **The floor's stall-detection covers it.** CLAUDE.md records that a
   stalled collector was noticed by accident twice; probes were entirely
   outside that net.
3. **The verdict-in-header rule applies**, so nobody has to read the
   measurement to learn what it concluded.
4. **Measurement data has exactly one home**, which is what makes Part 1's
   three-owner rule complete rather than nearly complete.

### What `evidence/` holds afterwards

- **Ticket files** `<date>-<slug>.md` — specs in the evidence stage
- **The lane's shared reference material**, unchanged and still linked
  from that README: `2026-08-24-evidence-ledger.md`,
  `2026-08-24-le-2026-calibration-notes.md`,
  `2026-08-24-angelini-deangelis-2026-notes.md`

No directories. That removes the file-versus-directory distinction an
earlier draft of this design proposed, which was clever and would not have
survived contact with a session that had not read it.

### Migration

The three existing probe dirs become studies:

| from | to |
|---|---|
| `evidence/2026-09-01-aggregation-gap-probe/` | `studies/2026-09-01-aggregation-gap-probe/` |
| `evidence/2026-09-01-accumulation-decay-probe/` | `studies/2026-09-01-accumulation-decay-probe/` |
| `evidence/2026-09-01-block-trade-probe/` | `studies/2026-09-01-block-trade-probe/` |

Each gains a `STUDY.md` with the standard header, **written from the
`RESULT.md` already in the folder** — the finding is re-filed, never
re-derived. `PREREG.md` where it exists stays as the pre-registration.

**Citations must move with them.** `tickets/new-theory/README.md` names
`evidence/2026-09-01-aggregation-gap-probe/` twice, in rule 0 and again
further down. `test_every_dated_cross_citation_still_resolves` and
`test_every_repo_path_named_in_docs_resolves` are the backstop, but the
links get updated deliberately rather than left for a test to find.

Net effect: three real measured verdicts enter `cli studies`, where the
supervisor contract says they should have been all along.

### Study-lane tickets are unaffected

A ticket *about* a study stays `open → completed`. A study's own verdict
header is a separate lifecycle and this design does not touch it.

## Part 4 — The purge

```bash
cli tickets purge [--dry-run | --apply] [--older-than 7]
```

**Candidates:** tickets in any `completed/` — every lane, including theory
and study folders — whose `closed:` date is at least 7 days ago.

**A candidate is kept if anything cites it.** The check looks for the
ticket's slug or its repo path in:

- tracked files: `CLAUDE.md`, `README.md`, every `docs/` file, every
  skill under `.claude/skills/`, every `NOTES.md`, `THEORY.md`,
  `STUDY.md` and `README.md`, `RESEARCH_LOG.md`, `FLEET_LOG.md`, other
  tickets, and `tests/`
- the DB's citation-bearing text columns — slice `origin`, ruling
  entries, ticket resolutions

Anything else is `git rm`'d. History keeps it: `git log --diff-filter=D`
finds it and `git show` retrieves it. This matches how `user_reports/` and
the large data dirs are already treated — recoverable, therefore not
carried in the working tree.

**`--dry-run` is the default.** Deleting files is not something a skill
should do as a side effect of a flag it forgot to pass.

go-floor gains one step: run `purge --apply`, and report the count and the
names in the **Floor record** section — the receipt, where it belongs.

## Part 5 — Backlog pressure

Tickets are a priority, balanced against research rather than replacing
it. The balance is made mechanical so it is not re-litigated every
session:

- `cli tickets list` grows an **age** column and a pressure line.
- `go`'s lane-choice step gains one rule: **a lane holding a ticket open
  more than 14 days, or holding 5 or more open tickets, is either taken
  or explicitly declined with a reason in the session report.**
- **The floor is never displaced by ticket pressure.** It is a daily
  guarantee, not a discretionary lane.

The two numbers are a starting point, not a measurement. Against today's
backlog — 4 maintenance open, 16 new-theory open — the ≥5 rule fires on
`new-theory` immediately. That is arguably correct (16 unbuilt specs is
real pressure) and arguably noise. **Flagged for the user; easy to tune
once, hard to tune repeatedly.**

## Part 6 — Enforcement

Three tests in `tests/test_conventions.py`, in the house style — fail at
the commit that breaks the rule, not months later:

1. **`test_no_new_top_level_directory`** — the top level is an allowlist:
   `.claude`, `attic`, `db`, `docs`, `studies`, `tests`, `theories`,
   `tickets`, `tools`, `user_reports`. A new one is an architecture
   decision, not a side effect.
2. **`test_data_files_live_with_their_owner`** — a tracked file matching
   `.jsonl`, `.csv`, `.parquet` or `.db` must sit under a theory folder, a
   study folder, `db/`, or `tests/`. Anywhere else is an escape.

   **This test currently fails, on exactly three files** — and they are
   exactly the three the Part 3 migration moves:

   ```
   tickets/new-theory/evidence/2026-09-01-accumulation-decay-probe/candles.jsonl
   tickets/new-theory/evidence/2026-09-01-block-trade-probe/pass_b.jsonl
   tickets/new-theory/evidence/2026-09-01-block-trade-probe/pass_c.jsonl
   ```

   Every other tracked data file in the repo already sits with its owner.
   That is the strongest available evidence that the rule describes what
   this repo already does, and that the one place it drifted is the one
   Part 3 closes. The test goes red on the migration commit and green when
   it lands, in that order.
3. **`test_ticket_states_match_their_lane`** — no `implement/` or
   `evidence/` under `maintenance/`, and no state directory outside the
   set its lane declares.

Plus coverage in `tests/test_tickets.py` for `advance` (each legal
transition, each refused one) and `purge` (a cited ticket survives, an
uncited one goes, `--dry-run` deletes nothing).

## Files touched

| file | change |
|---|---|
| `CLAUDE.md` | Data conventions reframed around the regenerable test; the three owners; the closed sink list; the lifecycle table |
| `tickets/README.md` | the per-lane state diagram; the four resolutions |
| `tickets/new-theory/README.md` | the evidence stage as a study; updated probe citations |
| `studies/README.md` | studies as the evidence stage's home |
| `tools/tickets.py` | per-lane `STATES`, `advance()`, `purge()`, resolution validation |
| `tools/cli.py` | `tickets advance`, `tickets purge`, age column |
| `.claude/skills/go-floor/SKILL.md` | the purge step and its report line |
| `.claude/skills/go/SKILL.md` | the backlog-pressure rule |
| `.claude/skills/go-new-theory/SKILL.md` | read `implement/` first; advance through `evidence` |
| `.claude/skills/go-theory/SKILL.md`, `go-study`, `go-maintenance` | the data-locality line |
| `tests/test_conventions.py`, `tests/test_tickets.py` | the three tests plus transition coverage |

**Implementation-order constraint:** `test_every_repo_path_named_in_docs_resolves`
scans `CLAUDE.md`, so the new state directories must exist before CLAUDE.md
names them in backticks. Create them with a `.gitkeep` in the same change
as the doc edit.

## Phasing

Four phases, each leaving the repo green and usable. The order is forced
by the enforcement test in Part 6: the migration has to precede the rule
that would fail on it.

1. **Migration** — the three probe dirs become studies, `STUDY.md`
   written from each `RESULT.md`, citations in
   `tickets/new-theory/README.md` updated. Nothing else changes; the
   repo is already better off (three verdicts enter `cli studies`).
2. **Lifecycle** — per-lane `STATES`, `advance()`, the four resolutions,
   the ideas-registry coupling on close, the CLI verbs, the directories
   with `.gitkeep`. Tests for each transition.
3. **Purge** — `purge()` with its citation check, `--dry-run` default,
   the go-floor step.
4. **Standard and enforcement** — the CLAUDE.md rewrite, the READMEs, the
   skill edits, the three conventions tests, the backlog-pressure rule.

Phase 1 is worth doing even if the rest is cut.

## What this deliberately does not do

- **No status field.** State stays the directory. A field would mean two
  sources of truth and the second one is always the stale one.
- **No lightweight study class.** A probe is a study; splitting studies
  into weight classes would recreate the duplicated home this design
  closes.
- **No change to the study verdict lifecycle**, to scoring, to the ledger,
  or to any load-bearing vocabulary already in CLAUDE.md
  (`disposition`, `edge_basis`, `run_mode`, `segment`, version `kind`,
  tiers, rungs, theory `status`). The new resolution words are a *new*
  vocabulary, not a redefinition of an existing one — per CLAUDE.md's own
  "prefer a new name to a redefined one".
- **No retroactive purge.** The 7-day clock runs from `closed:`, so
  today's 28 completed tickets become eligible on their own dates. The
  first floor after this ships should expect a batch, which is why
  `--dry-run` is the default.

## Open questions for the user

1. **The pressure numbers** — 14 days and 5 tickets. ≥5 fires on
   `new-theory` on day one.
2. **Whether `implement/` earns its place**, or whether "evidence cleared,
   now build" is adequately carried by the `evidence` ticket's own body.
   It is one more directory and one more transition; the argument for it
   is that the backlog listing shows what is ready to build without
   opening files.
