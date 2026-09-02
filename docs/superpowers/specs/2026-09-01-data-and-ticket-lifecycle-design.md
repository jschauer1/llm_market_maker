# Data locality and the ticket lifecycle

**Date:** 2026-09-01 · **Status:** design, awaiting review · **Supersedes:** nothing

Two standards, written together because they answer the same question from
opposite ends: **where does the output of a session go, and what is it
allowed to cost?**

- **Data locality** — what gets saved at all, and whose folder it lands in.
- **The ticket lifecycle** — how queued work moves, and when a finished
  ticket stops occupying the tree.

They meet at the study, which turns out to be a ticket.

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

**And "study" turned out to be four jobs wearing one word.** Reading all
15 `STUDY.md` files and counting which theories each names: **7 serve
exactly one theory** (`side-split-60day-obs`, `structural-arb-violation-liquidity`,
`deadline-drift-classifier-audit` and four more), **5 serve none**
(`entry-timing`, `settlement-day-clustering` and the early-close pair),
**2 exist to decide whether to build a spec**, and **1 names no theory at
all** — `structural-gate-payload-version` rules on what a repo rule
constrains, which is governance, not measurement. Half the tree is a
theory's own data filed somewhere else. That is the locality rule this
repo already has, unenforced on the one kind of work that most looks like
it belongs elsewhere.

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
| a study | its own state directory — inside its theory, or in the root `study` lane (Part 3) |

An evidence-stage ticket is not a third owner: it spawns a study and the
study owns the data. That is the point of Part 3 — it is what keeps this
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
new-theory:   open → evidence → implement → completed
study:        question → investigation → answer
maintenance:  open → completed
theory:       open → completed
```

The study lane is the odd one and Part 3 is why: its tickets are
**directories**, its terminal state is `answer/` rather than `completed/`,
and it is therefore the one lane the purge never touches.

| state | means |
|---|---|
| `open` | filed; nobody has started |
| `evidence` | a measurement is running against the spec's bar (new-theory only) |
| `implement` | the evidence cleared the bar — this is a build order (new-theory only) |
| `question` | the bar, written before looking (study only) |
| `investigation` | the measurement running, with its code and data (study only) |
| `answer` | the verdict — terminal and **permanent** (study only) |
| `completed` | terminal, for every other lane and every outcome |

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

## Part 3 — A study is a ticket pipeline

**A study is a measurement you run to answer a question before you act on
it. It never places a bet.** That definition does not change. What changes
is that a study stops being a folder in a separate tree and becomes **a
ticket with its own lifecycle**, living inside the thing it is about.

```
study:  question → investigation → answer
```

| state | holds |
|---|---|
| `question/` | the question and the bar, **written before looking** |
| `investigation/` | the measurement running — its code and its data |
| `answer/` | the verdict. **Terminal and permanent** |

### Why this shape, and not a folder in `studies/`

**Pre-registration becomes structural rather than disciplinary.** Rule 1
of `studies/README.md` is *"write the bar before looking"* — today a rule
somebody follows. Under the pipeline, `investigation/` is unreachable
except through `question/`. The rule is the pipeline.

**Persistence needs no special case.** The purge (Part 5) only ever
touches `completed/`. The study lane has no `completed/` — its terminal
state is `answer/`. Study answers survive because there is nothing for the
purge to match, not because someone remembered to exempt them.

**It deletes a duplicated status field that is failing right now.**
`studies/2026-08-29-series-bias-mining/STUDY.md` carries
`**Status:** complete — result: not measured`, and the study has two open
tickets saying the phase-2 sweep is unfinished and pass 4's filter
conditions are reversed. The header and the work disagree, in the live
repo, today. Under the pipeline the state is the directory and there is
nothing left to contradict: `STUDY.md` keeps `Date`, `Tier` and `Verdict`
and **loses `Status` entirely**.

**And it removes a concept.** "A ticket about a study" stops existing.
Work items against a running measurement — *finish the sweep*, *pass 4 is
reversed* — are ordinary tickets against the owning theory. A study is the
question, not the queue of chores under it.

### Where a study lives

Locality, unchanged from every other kind of work in this repo:

| owner | path |
|---|---|
| one theory | `<theory registry path>/studies/<state>/<date>-<slug>/` |
| nobody | `tickets/study/<state>/<date>-<slug>/` — a root lane beside `maintenance/` and `new-theory/` |

**Top-level `studies/` disappears.**

`tools/registry.py` already anticipated the first row. `_theory_packages`
skips any folder carrying `STUDY.md`:

```python
if folder.name == "_TEMPLATE" or (folder / "STUDY.md").exists():
    continue
```

That exclusion only does anything if a `STUDY.md` can appear under
`theories/`. The guard was built and never used; this is what it was for.

### Study tickets are directories

The one lane where a ticket is a directory rather than a file, and it is
forced: a measurement has code and data, and they belong with it.

```
<owner>/studies/investigation/2026-08-30-parlay-markup/
    TICKET.md      the question, the bar, the inclusion rules
    STUDY.md       Date / Tier / Verdict — no Status
    collect.py
    data/          gitignored past 10MB, per Part 1
<owner>/studies/answer/2026-08-30-entry-timing/
    TICKET.md
    STUDY.md
    RESULT.md      what it concluded
```

### The evidence stage spawns a study; it is not one

This corrects the seam in this design's earlier draft. A new-theory spec
in `evidence/` **spawns a study ticket** and names it in its frontmatter;
it does not become one. The spec advances to `implement/` or closes
`disproven`/`underpowered` when the answer lands.

That split is the right one because the two have different lifetimes:
**the spec is work and eventually purges; the study's answer is knowledge
and never does.** A theory that does not exist yet owns nothing, so its
study starts in the root `tickets/study/` lane and stays there — studies
are not moved once cited.

### Migration — all 15

Measured 2026-09-01 by reading each `STUDY.md` and counting which theories
it names. Seven have exactly one owner, five have none, one is a
governance ruling with zero theory mentions, and every one but
`parlay-markup` is finished.

| study | goes to | state |
|---|---|---|
| `side-asymmetry-extension` | `theories/no_side_premium/studies/` | answer |
| `side-split-60day-obs` | `theories/no_side_premium/studies/` | answer |
| `liquidity-filtered-side-split` | `theories/no_side_premium/studies/` | answer |
| `structural-arb-violation-liquidity` | `theories/structural_arb/studies/` | answer |
| `deadline-drift-classifier-audit` | `theories/deadline_drift/studies/` | answer |
| `series-bias-mining` | `theories/insider_bias/mention_family/studies/` | **investigation** |
| `calibration-harvest-gradient-review` | `theories/retired/calibration_harvest/studies/` | answer |
| `calendar-arb-firing-rate` | `tickets/study/` | answer |
| `smile-smoothing-ladder-flatness` | `tickets/study/` | answer |
| `settlement-day-clustering` | `tickets/study/` | answer |
| `early-close-exposure-existing-backtests` | `tickets/study/` | answer |
| `early-close-exposure-in-the-bettable-slice` | `tickets/study/` | answer |
| `entry-timing` | `tickets/study/` | answer |
| `parlay-markup` | `tickets/study/` | **investigation** |
| `structural-gate-payload-version` | `docs/` | — |

Three notes on the awkward rows:

- **`series-bias-mining` lands in `investigation/`, not `answer/`** — its
  header claims complete and its tickets say otherwise. The pipeline
  forces the honest answer. Its two open tickets become ordinary
  `mention_family` theory tickets.
- **`structural-gate-payload-version` is not a study.** It names no
  theory and measures no market; it rules on what a repo rule constrains.
  That is a governance document and it goes to `docs/`.
- **`calibration-harvest-gradient-review` follows its theory into
  `retired/`** (Part 4). A retired theory's studies retire with it.

Plus the three probe directories, which are studies that were never
called one:

| from | to | state |
|---|---|---|
| `tickets/new-theory/evidence/2026-09-01-aggregation-gap-probe/` | `tickets/study/` | answer |
| `tickets/new-theory/evidence/2026-09-01-accumulation-decay-probe/` | `tickets/study/` | answer |
| `tickets/new-theory/evidence/2026-09-01-block-trade-probe/` | `tickets/study/` | answer |

Each gains a `STUDY.md` written from the `RESULT.md` already in the
folder — the finding is re-filed, never re-derived. Afterwards
`tickets/new-theory/evidence/` holds ticket files plus the lane's shared
reference material (`2026-08-24-evidence-ledger.md` and the two reading
-note files), and nothing else.

**Citations move with them.** `tickets/new-theory/README.md` names
`evidence/2026-09-01-aggregation-gap-probe/` twice, and `studies/...`
paths are cited across `CLAUDE.md`, the skills, several `THEORY.md` and
`NOTES.md` files. `test_every_dated_cross_citation_still_resolves` and
`test_every_repo_path_named_in_docs_resolves` are the backstop, not the
plan.

### `cli studies` after the change

`studies.survey()` stops reading `studies/*/STUDY.md` and instead walks
the study states across theory folders and the root lane. Status comes
from the directory; `Verdict` and `Tier` still come from the header. The
rendered output gains an owner column, which is the thing that was
missing all along — a reader could not previously tell whether a study
served one theory or all of them without opening it.

## Part 4 — Retiring a theory

**A retired theory leaves `theories/`.** Its folder is replaced by
`theories/retired/<slug>/`, holding what proves it was tried and nothing
that could still be run.

### What survives

| kept | why |
|---|---|
| `RETIRED.md` | the death certificate — date, distilled rationale, what survives and why, **and the git rev the deleted code lived at** |
| `THEORY.md` | what the theory claimed and how it decided |
| `NOTES.md` | the lab notebook — literally the record that it was tried |
| `RESULTS.md` | **distilled** backtest performance: the populations walked, the cells, the numbers each one produced, and the kill criterion it met |

Everything else goes: the `.py` modules, `RUNBOOK.md`, `prompts/`, the raw
backtest payloads, the theory's completed tickets, `__pycache__`.
`git show <rev>:<path>` retrieves any of it, and `RETIRED.md` names the rev
so retrieval is a command rather than archaeology.

**The raw backtest payloads do not survive; their findings do.** This is
the user ruling of 2026-09-01 — *"theory + notes + backtest performance
with details, not the entire backtest"* — and it is the elevation rule
already in CLAUDE.md applied to a dying theory: **knowledge elevates by
distillation.** `calibration_harvest`'s 508K of `backtests/*.json` becomes
a `RESULTS.md` carrying the three populations, the 47 cells past both
floors, the zero positive net edges, and the horizon sign reversal — the
things a future session would actually read. Nobody re-reads 508K of JSON;
they read the table.

### Two mechanical consequences, both of which bite

1. **`registry.discover()` imports every `THEORY.md` folder it finds.**
   `_theory_packages` does `rglob("THEORY.md")` under `theories/` and
   raises if the package exposes no `THEORY` singleton. A retired folder
   keeping its `THEORY.md` therefore breaks the drift check. Excluded the
   way the existing markers already are — by the `retired/` path segment
   **and** the presence of `RETIRED.md`, mirroring how `STUDY.md` marks a
   study folder.
2. **The registry `path` column must be repointed** to
   `theories/retired/<slug>`. `tickets.ticket_dir` reads that column, and
   a stale path files tickets into a phantom directory beside a theory
   that no longer exists — the exact bug this repo already fixed once, in
   the other direction.

`retired` is not in `SCANNABLE_STATUSES`, so the DB side of the drift
check already skips it; removing the code removes it from the class side.
No change to `check_drift` itself.

### The live case

`calibration_harvest` was retired on 2026-09-01 and its 866K folder is
still in `theories/`. It is the migration's first subject and its worked
example.

## Part 5 — The purge

```bash
cli tickets purge [--dry-run | --apply] [--older-than 7]
```

**Candidates:** tickets in any `completed/` — every lane that has one —
whose `closed:` date is at least 7 days ago.

**Studies are never candidates, and not by exemption.** The study lane's
terminal state is `answer/`, so a finished study is simply not a thing
this query matches. Permanence is a consequence of the state names rather
than a rule the purge has to remember.

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

## Part 6 — Backlog pressure

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

## Part 7 — Enforcement

Three tests in `tests/test_conventions.py`, in the house style — fail at
the commit that breaks the rule, not months later:

1. **`test_no_new_top_level_directory`** — the top level is an allowlist:
   `.claude`, `attic`, `db`, `docs`, `tests`, `theories`, `tickets`,
   `tools`, `user_reports`. A new one is an architecture decision, not a
   side effect. **`studies` is deliberately absent** — Part 3 dissolves
   it, and this test is what stops it growing back.
2. **`test_data_files_live_with_their_owner`** — a tracked file matching
   `.jsonl`, `.csv`, `.parquet` or `.db` must sit under a theory folder, a
   study state directory, `db/`, or `tests/`. Anywhere else is an escape.

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
3. **`test_ticket_states_match_their_lane`** — each lane's state
   directories come from its own declared set and nothing else: no
   `evidence/` or `implement/` under `maintenance/`, no `completed/`
   under a study, no `answer/` under `new-theory/`.

Plus coverage in `tests/test_tickets.py` for `advance` (each legal
transition, each refused one) and `purge` (a cited ticket survives, an
uncited one goes, `--dry-run` deletes nothing).

## Files touched

| file | change |
|---|---|
| `CLAUDE.md` | Data conventions reframed around the regenerable test; the three owners; the closed sink list; the lifecycle table |
| `tickets/README.md` | the per-lane state diagram; the four resolutions |
| `tickets/new-theory/README.md` | the evidence stage spawning a study; updated probe citations |
| `tickets/study/README.md` | **new** — the study pipeline, replacing `studies/README.md` |
| `tools/tickets.py` | per-lane `STATES`, directory-tickets for the study lane, `advance()`, `purge()`, resolution validation |
| `tools/studies.py` | `survey()` walks study states across theories and the root lane; owner column; `Status` no longer parsed |
| `tools/registry.py` | exclude the `theories/retired/` subtree from `discover()` |
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

Five phases, each leaving the repo green and usable. The order is forced
by the enforcement test in Part 6: the migration has to precede the rule
that would fail on it.

1. **The study pipeline** — SHIPPED 2026-09-02, merged at 4267816. — the lane, its states, directory-tickets,
   `survey()` rewritten, then the 15 studies and the 3 probe dirs moved
   and their citations updated. Top-level `studies/` goes. This is the
   biggest phase and the one everything else assumes.
2. **Retirement** — `theories/retired/`, `RETIRED.md`, the registry
   exclusion and path repoint, and `calibration_harvest` migrated as the
   worked example.
3. **Lifecycle** — per-lane `STATES` for `new-theory`, `advance()`, the
   four resolutions, the ideas-registry coupling on close, the CLI verbs.
   Tests for each transition.
4. **Purge** — `purge()` with its citation check, `--dry-run` default,
   the go-floor step.
5. **Standard and enforcement** — the CLAUDE.md rewrite, the READMEs, the
   skill edits, the three conventions tests, the backlog-pressure rule.

Phases 1 and 2 each stand alone and are worth doing even if the rest is
cut.

## What this deliberately does not do

- **No status field.** State stays the directory. A field would mean two
  sources of truth and the second one is always the stale one.
- **No lightweight study class.** A probe is a study; splitting studies
  into weight classes would recreate the duplicated home this design
  closes.
- **No "ticket about a study".** That concept is deleted. Chores against
  a running measurement are ordinary tickets against the owning theory; a
  study is the question, not the queue of work under it.
- **No moving a study once it is cited.** A study that starts in the root
  lane because its subject theory did not exist yet stays there when the
  theory is built. Studies are cited by path across the repo, and churning
  those paths costs more than the tidier filing is worth.
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
