# The structural-gate rule constrains payload *fields*, not payload *versions*

**Date:** 2026-08-29 · **Status:** complete, **revised after peer review**
· **Tier:** A (no model in the measurement path) · Adversarial review of
`0f06265`, at session 78's request

> **Revision note (2026-08-29).** The first version of this study
> (`0b5b25e`) quoted four examples, **three of them backwards**, and
> leaned on a "39 number-moves" statistic that dissolves on inspection.
> Session 09's review caught all of it. The thesis survives; the exhibits
> did not. The extraction bug and the corrected numbers are documented
> below rather than quietly fixed, because the failure is more
> instructive than the finding.

## The claim

CLAUDE.md's structural-gate rule keeps tier A when, among other
conditions:

1. the classification is **"answerable from the market's own text as
   written at open"** — identical on day one and on settlement day; and
2. **"the payload carries no outcome-bearing data. Rules and title
   only"** — described as *"a property of the prompt file, reviewable in
   `git diff`."*

Condition 2 is enforceable: a reviewer can read the prompt. **Condition 1
is not**, and nothing in the rule makes it checkable. A replay that
fetches a settled market's text *today* is not reading the text as
written at open — it is reading whatever Kalshi last wrote. The prompt
can be fully compliant while the data is not.

**So the proposed fifth condition is not a new requirement. It is the
operationalization of a phrase condition 1 already contains.** (Framing
owed to session 09; it is better than the "new hole" framing the first
version used, and it makes the prevalence question below mostly moot.)

## The extraction bug, recorded because it is the lesson

The first version's before/after quotes came from `sorted(set_of_values)`
— **alphabetical order, presented as chronological**. `"above 12000"`
sorts before `"above 12500"`, so a *correction downward* was reported as
a *strike moving upward*. The counting code was sound and reproduced
exactly under independent re-run; only the example extraction was wrong,
and it was wrong in the direction that flattered the thesis.

This is the same error this repo spent the day cataloguing — an ordering
the data never encoded, asserted anyway — and it produced a false headline
exhibit that would have gone into CLAUDE.md verbatim. **Any script that
reports "before → after" must sort by `captured_at`, not by value.**

## Measurement (corrected)

Every market appearing in **more than one** `market_snapshots` capture —
12 captures spanning 2026-08-24 → 2026-08-29, a **5-day** window.
Whitespace-collapsed and lowercased to separate cosmetic from
substantive; versions ordered by `captured_at`.

| | count | of 156,231 multi-capture markets |
|---|---|---|
| substantive `rules_primary` change | 331 | 0.21% |
| substantive `title` change | 541 | 0.35% |

*(The first version divided by 202,690 — all distinct markets, including
those seen once, which cannot show a change. The honest denominator is
the multi-capture set.)*

### What those 331 changes actually are

Grouped by edit pattern (a pattern shared across many markets is a
template migration, not a per-market decision):

| class | n |
|---|---|
| team-name / punctuation / typo template migrations | 329 |
| template corruption **fixed** (`\|\| Original Date \|\|` → a real date) | 1 |
| **genuine change of resolution criteria** | **1** |

The recurring patterns are `"PHI Eagles"` → `"Philadelphia"` (and 30-odd
siblings), `"Festival ,"` → `"Festival,"`, `"Hirozaku"` → `"Hirokazu"`.
The single "number moved" the first version leaned on is
`"SF 49ers"` → `"San Francisco"` — the moving number is the **49**.

**There are zero strike moves in the window.**

### The one genuine case

**`KXDATACENTERMORATORIUM-27JAN012`**, on an open market:

- 2026-08-24 — *"...has **become law** in any U.S. state..."*
- 2026-08-29 — *"...is **enacted** in any U.S. state..."*

A different legal bar and a different YES set, edited under a live market
whose decision point a replay would sit before. This is the whole
empirical basis for the condition: **one case in five days**, not 331.

## What the measurement does and does not bound

- It bounds **live-market drift**, and finds it overwhelmingly benign:
  330 of 331 substantive edits are cosmetic in meaning.
- It is **silent on post-settlement editing**, which is the truly
  outcome-driven channel. Zero changes were observed at a non-open
  capture — but only **21,248 of 1,390,328** snapshot rows (1.5%) are
  non-open, so that channel is close to unobservable here. Absence of
  evidence, not evidence of absence.
- Five days and 12 captures is a **lower bound on prevalence**, not a
  rate. Edits plausibly cluster near listing and near settlement, and
  settlement is exactly where a replay's decision point sits furthest
  from today's text.

**The condition should therefore not cite a prevalence number at all.**
One genuine case invites "too rare to matter"; the lower-bound argument
invites "unmeasured, so speculative". Neither settles it, and neither
needs to — the argument rests on condition 1 being unenforceable as
written, and on the fix being free when no edit occurred.

## Why neither existing safeguard catches it

- The **contamination probe** cannot: there is no recall to catch. The
  model honestly reads text that already encodes the change, and passes
  any "can you state the outcome?" test.
- **`git diff` of the prompt** cannot: the prompt is fully compliant. The
  leak is in the data.

(Both confirmed by session 09 against attempts to break them.)

## Fifth condition — ADOPTED 2026-08-29

> **STATUS: ADOPTED.** The user delegated adjudication of this class of
> decision to the supervisor session (09) on 2026-08-29; the amendment's
> author (78) had recused. Ruling: the two-part form below is adopted,
> and part (b) **keeps tier A** — with the disclosure and drift bound
> mandatory, since the measured drift composition (one genuine
> resolution-criteria change in the 5-day window) does not justify
> voiding all pre-snapshot history, and a downgrade would re-teach
> theories to avoid the honest tool. CLAUDE.md and
> `.claude/skills/backtest-theory/SKILL.md` now carry the rule; this
> section stays as the rationale record.

### Why two parts, and not the one part first drafted

The first version proposed: build the payload from the snapshot at or
before the decision point, and **exclude** markets with no such capture.

**That exclusion clause would have nullified the rule it amends**, and
neither this study nor session 78 spotted it — session 09 did.
First-party snapshots begin **2026-08-24**. Kalshi's settled API serves
current text only, and candlesticks carry prices, not rules. So for every
decision point before 2026-08-24 there is no point-in-time text anywhere,
and "exclude when absent" excludes **essentially all history** from
structural gating — while the amendment's entire pitch was tier-A
evidence over *all* history instead of tier B's thin post-cutoff window.
As drafted it did not patch the amendment; it repealed it for the past.

**Proposed** instead — again, *proposed*, with the second half
explicitly a **user judgment call**:

> **(a) Point-in-time where available — would be mandatory.** Where a capture at
> or before the decision point exists, the gate's payload is built from
> it, never from a current fetch. Cheap, closes the live-drift channel
> for the whole snapshot era going forward.
>
> **(b) Disclosed where not.** Where no capture predates the decision
> point, today's text may be used, but the `backtest_runs` notes must say
> so and the run should carry a drift-risk bound measured from the
> snapshot era for its population.

Whether (b) is acceptable **at tier A** is not a question this study
should answer. Both options belong in front of the user, and until they
rule, **the four conditions as written remain the whole rule.**

## Two observations that are not this hole

1. **Condition 1's counterfactual is unverifiable in general.** The
   rule's worked example is safe by accident — the NBA has 30 teams
   because of a fact that does not move. *"Is this one of the plausible
   nominees?"* has the same grammatical shape and is not stable at all.
   If a reviewer must **ask** that question rather than read it off the
   prompt, the rule should say so out loud.
2. **The probe tests explicit recall, not implicit influence.** "Can the
   model state the outcome?" and "are its gate decisions shifted by
   knowing it?" are different failures. A sharper probe compares the
   gate's **pass rate** on pre- versus post-cutoff markets matched on
   structure. Worth proposing to the `backtest-theory` skill as its own
   item, independent of everything above.

## What this does not challenge

The amendment's core reasoning is right, and this study does not argue
otherwise. Penalising a structural gate identically to outcome judgment
did teach theories to avoid the honest tool. The four conditions are
well-chosen, and "derived, never self-reported" plus "an unrun probe
counts as outcome judgment" close the obvious self-dealing routes. This
is one condition made checkable — on thin evidence, honestly labelled.
