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
**directory** holding `STUDY.md` plus the measurement's own code and
data. It moves through three states, and the state is **the directory it
sits in** — never a field inside the file:

```
question  →  investigation  →  answer
```

- **`question/`** — the bar is written, nothing has been measured.
- **`investigation/`** — the measurement is running. A collector
  mid-sweep lives here, and the floor reports it as in flight.
- **`answer/`** — the verdict is in `STUDY.md`'s header.

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

1. **Write the bar before looking.** State the question, the inclusion
   rules, the contrast and the smallest effect the design can detect —
   and commit that — before computing any result. Deciding what counts
   as a hit after seeing the hits is not a measurement.
   `2026-08-30-entry-timing` keeps its `counts.py` precisely so the
   claim "I had computed only counts" is checkable rather than asserted.
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
