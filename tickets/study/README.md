# Studies — measurements that answer a question

**A study is a measurement that answers a question. It never bets.**

That is the whole definition, and it is the line between a study and a
theory:

| | theory | study |
|---|---|---|
| produces | **bets** | **an answer** |
| touches the ledger | yes — every candidate | **never** |
| is scored on | whether it made money | nothing; it is not scored |
| marked by | `THEORY.md` + a registry row | `STUDY.md` in its folder |
| lives in | `theories/<slug>/` | a study ticket — see below |

`Theory` is for things that produce bets. A study produces knowledge —
usually knowledge about whether a theory is worth building, or worth
keeping.

## A study is a ticket, and its state is its directory

A study is a ticket in the `study` lane, and a study ticket is a
**directory**: `STUDY.md` is the ticket, and while the measurement is
running the folder holds its code and data too. It moves through three
states, and the state is **the directory it sits in** — never a field
inside the file. Each state says what may be in the folder, so the three
are not just labels:

```
question  →  investigation  →  answer
```

- **`question/`** — **what should be investigated, and nothing else.**
  A study here is a *request*: one `STUDY.md` saying what the question
  is and why it is worth a session, filed by whoever noticed it. No
  design, no bar, no code, no data.
- **`investigation/`** — **where the work lives.** Claiming a question
  means advancing it here first; the pre-registration is written here,
  before looking, as the investigation's first act. The measurement's
  code, its data and a collector mid-sweep all live here, and the floor
  reports it as in flight.
- **`answer/`** — **the answer, and only the answer.** `STUDY.md` says
  what was asked, how it was measured, what came back and what it
  decided; the investigation that produced it is **deleted**.

**`question/` holds no work at all** (user ruling 2026-09-03), and the
line is worth stating because it is not where a careful session would
draw it on its own. Designing the measurement *feels* like part of
asking the question: `2026-09-03-maker-mode-fill-simulation` was filed
into `question/` with a full pre-registration, a simulator, planted-path
fixtures and a collected `data/markets.jsonl` — a study most of the way
to an answer, sitting in the directory that means *nobody has started
this*. Two things break there at once. The backlog stops distinguishing
questions somebody could pick up from work already half-done, which is
the whole reason state is a directory; and the floor's in-flight report
covers `investigation/`, so a stalled collector in `question/` is
invisible exactly the way `series-bias-mining`'s stalls were.

So the test is not "has a result been computed" — it is **"has anyone
done anything yet"**. The first act of working on a study is
`tickets advance <path> --to investigation`, and everything after that
is written in the state it belongs to.

There is deliberately **no `completed/`**. A study is a permanent
record, and `completed/` is what the ticket purge matches; a finished
study is simply not a thing that query can match.

**A study lives inside the theory that owns it**, and in the root lane
when no single theory does:

```
<theory registry path>/studies/<state>/<date>-<slug>/   # theory-owned
tickets/study/<state>/<date>-<slug>/                    # no single owner
```

A theory's registry path is not always `theories/<slug>` —
`insider_judgment` lives under a shared family parent — so file through
the CLI, which looks the path up, rather than writing the directory by
hand:

```bash
python -m tools.cli tickets new --lane study --slug <date>-<slug> \
    --title "<the question>" --theory <slug> --session <you>
python -m tools.cli tickets advance <path>     # question → investigation → answer
python -m tools.cli studies                    # every study and its verdict, live
```

State was a `**Status:**` line in `STUDY.md` until 2026-09-01. It
drifted exactly as a duplicated status field always does:
`series-bias-mining` read `complete` while two open tickets said its
sweep was unfinished, and nothing could tell you which claim was right.
One fact, one home — the directory.

## When a study has an answer, the investigation is deleted

**User ruling 2026-09-03.** A study that has reached an answer is
*documented as an answer*. Its scripts, its intermediates and its working
data were the means of getting there, not the finding, and they stay only
as long as the question is open. When the study advances to `answer/`,
they go with the advance.

This is the rule retirement already applies to a theory, for the same
reason: what a future session needs is the claim, the method and the
numbers, not the megabytes behind them. And it has the same safeguard —
**the deletion is recoverable, not merely reversible in principle.** The
answer document carries the git rev its code lived at:

```markdown
**Code:** deleted at `<rev>` — `git show <rev>:<path>` returns any file,
`git ls-tree -r --name-only <rev> <study dir>` lists what the folder held.
```

Without that line "it's in git somewhere" is an archaeology problem, which
is exactly what `RETIRED.md`'s rev line exists to prevent.

### What the answer document has to carry

The code is gone, so the document is the record. It states:

1. **The header** — `**Date:** … · **Tier:** … · **Verdict:** …`, which
   is what `python -m tools.cli studies` reads.
2. **The question**, in one sentence.
3. **The method** — the population and its inclusion rules, the contrast,
   and the bar as it was pre-registered. Enough that somebody could run
   the measurement again without the script.
4. **The numbers**, including the ones that did not support the verdict.
5. **The limits** — what the result does not cover.
6. **`**Code:**`** — the rev above.

A document that fails this is not ready for `answer/`, and the answer is
to finish the document rather than to keep the folder.

### The one thing that is not deleted

**Source data that cannot be bought back stays.** CLAUDE.md's data
conventions split on one test — can a future session regenerate this from
what is already on disk? A corpus of raw Kalshi payloads cannot: Kalshi
ages settled markets out of its public API after ~60 days, and a
gitignored file has no copy in any rev, so deleting it is permanent in a
way deleting a script never is.

So a retained corpus is named in the answer document, with why it cannot
be re-collected:

```markdown
**Retained:** `data/legs.db` — 150k raw Kalshi payloads, gitignored, not
in any rev; re-collection needs an API that ages this window out.
```

Everything a `git show` can return goes. And a dataset that *other work
reads* is not a retention case at all — it has become infrastructure and
needs an owner; see below.

## When to run one

You run a study when you need to know something **before** you act.

- **"Is this idea worth building?"** `2026-08-27-calendar-arb-firing-rate`
  checked whether date-ladder violations ever actually occur at
  executable quotes. Zero, across ten board snapshots. That killed a
  spec in an afternoon instead of after a month of building.
- **"Is this theory's number real?"** `2026-08-27-settlement-day-clustering`
  found that two theories' strong opening results were both a single
  settlement day.
- **"How should this work everywhere?"** `2026-08-30-entry-timing`
  measured whether entering early or late is better, across every
  theory at once.

The payoff is asymmetric, which is why studies are worth the calendar
time: a study that finds nothing has still stopped you building the
wrong thing, and it costs a day rather than a month.

## The rules

1. **Write the bar before looking** — in `investigation/`, as the first
   thing the investigation does. State the question, the inclusion
   rules, the contrast and the smallest effect the design can detect —
   and commit that — before computing any result. Deciding what counts
   as a hit after seeing the hits is not a measurement.
   `2026-08-30-entry-timing` keeps its `counts.py` precisely so the
   claim "I had computed only counts" is checkable rather than asserted.
   **The ordering is proved by the commit, not by the directory** — the
   bar is committed on its own, before the run that produces a number.
2. **Never touch the ledger.** No `record_opportunity`, no basket, no
   ticker. If it produces a bet it is a theory, and it needs a spec.
   (Currently 18 of 18 studies hold this line.)
3. **Report the verdict in the header**, so nobody has to read the study
   to learn what it concluded:
   `**Date:** … · **Tier:** … · **Verdict:** …`
   `python -m tools.cli studies` reads exactly that, live.
4. **A failed prediction is a result.** Report it as failed. A
   better-looking cut found afterwards is a hypothesis for the next
   population, never the headline.

The shared contracts in [`../new-theory/README.md`](../new-theory/README.md)
apply here too — rules 0 through 0f were mostly *learned* from studies,
and rule 0f (measure at executable prices) is the one that kills fastest.

## When a study stops being a study

**A study that grows a dataset other work depends on has become
infrastructure, and needs an owner.** `2026-08-29-series-bias-mining` is
the worked example and the reason this section exists: 353 MB, four
passes, a multi-hour resumable collector against data Kalshi ages out of
its API after ~60 days, and a 72,010-row corpus that *other studies now
read*. That is a dependency, not an experiment — and because nothing
treated it as one, its collector stalled twice and both times somebody
noticed by accident.

A one-shot experiment needs no supervision. Infrastructure does. If a
study reaches that point, say so in its `STUDY.md`, leave it in
`investigation/` until the sweep is actually finished, and expect the
floor to report it as in flight until then.

## What the floor does and does not do with studies

The floor **reports** study state every run — that is how a stalled
collector gets noticed on a one-day lag instead of by luck.

The floor **never re-runs a study's analysis.** Re-running the same test
daily is multiple comparisons by calendar: run a test sixty times and
one of them comes up significant. A study is run once, against a bar
written first. Extending it is deliberate work in the `study` lane, with
its own statement of what changed and why — see
`2026-08-29-series-bias-mining`'s own one-run rule, which says two runs
over two collection states are two different tests and the second must
not present whichever looks better.
