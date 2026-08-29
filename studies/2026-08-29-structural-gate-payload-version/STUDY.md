# The structural-gate rule constrains payload *fields*, not payload *versions*

**Date:** 2026-08-29 · **Status:** complete · **Tier:** A (no model in the
measurement path) · Adversarial review of `0f06265`, at session 78's request

## The claim being tested

CLAUDE.md's new structural-gate rule keeps tier A when, among other
conditions, **"the payload carries no outcome-bearing data. Rules and
title only"** — and notes this is *"a property of the prompt file, which
is already on disk and reviewable in `git diff`."*

That is true of *which fields* reach the model. It is not true of *which
version of those fields*, and the version is not in the prompt file.

## Measurement

Every market appearing in more than one `market_snapshots` capture, over
the repo's whole snapshot history (12 captures, 2026-08-24 → 2026-08-29 —
a **5-day** window), comparing `rules_primary` and `title` across
captures. Whitespace-collapsed comparison separates cosmetic from
substantive.

| field | markets changed | of 199,881 | cosmetic | **substantive** |
|---|---|---|---|---|
| `rules_primary` | 532 | 0.26% | 201 | **331** |
| `title` | 541 | 0.27% | 0 | **541** |

**Title changes where a number moved: 39.**

## Why this breaks the guarantee, for a small but real subclass

Most of the 541 title changes are template migrations that preserve
meaning — `"Denver vs Kansas City Pro Football game: Denver wins?"` →
`"Will Denver win the Denver vs Kansas City Pro Football game?"`. Those
are harmless.

A subclass is not:

- **`KXALBUMEQUIV-THE26OCT08-12K`** — `"above 12000 Album Equivalent
  Units"` → `"above 12500"`. **The strike moved under a live market**,
  while the ticker still reads `-12K`.
- **`KXDATACENTERMORATORIUM-27JAN012`** — `"has become law"` →
  `"is enacted in"`. Different legal bar, different YES set.
- **`KXCS2GAME-26AUG280400FAZEUNEAC-EAC`** — `"EAC Extra wins"` →
  `"EAC Rising wins"`. The counterparty was renamed.
- **`KXMOVIEDELAY-28DEC15`** — `"...by December 15"` → `"...by ||
  Original"`. Template corruption, which is its own hazard.

A backtest that fetches a settled market's text **today** judges it on
text that may have been edited *after*, and sometimes *because of*, what
happened. That is outcome-bearing data entering through a field the rule
explicitly permits.

**Neither existing safeguard catches it.**

- The **contamination probe** cannot: the model is not recalling
  anything. It is honestly reading text that legitimately encodes the
  outcome, and would pass any recall test.
- **`git diff` of the prompt file** cannot: the leak is in the data, not
  the prompt. The prompt correctly says "rules and title only" and is
  fully compliant.

## The fix, which is cheap and already available

`market_snapshots` preserves point-in-time `raw_json`. A structural
gate's payload should be built from **the snapshot at or before the
decision point**, never from a current fetch. Where no snapshot predates
the decision point, that market cannot be structurally gated honestly and
should be excluded rather than judged on today's text.

### The prevalence number is a LOWER BOUND, and the condition should not lean on it

Raised by session 78 and it corrects this study's own framing, so it is
recorded here rather than in a reply.

**Five days and 12 captures measure a floor, not a rate.** Text edits are
almost certainly not uniform in time: a market's rules are most likely to
be corrected near **listing** and near **settlement** — and settlement is
exactly where a replay's decision point sits *furthest* from today's
text. The twelve-month figure that actually governs a backtest could be
materially worse than 331/541, and this window cannot see it.

So the fifth condition **should not cite a prevalence number at all**.
Quoting 0.17% invites the reply "that is small enough to ignore", which
is an argument this measurement cannot support in either direction. The
fix is cheap, already in the repo, and costs nothing when no edit
occurred — so require it unconditionally and let the prevalence question
stay open.

Suggested fifth condition:

> **The payload is point-in-time.** Rules and title come from a capture
> at or before the decision point, never from a fetch made now, and a
> market with no capture predating its decision point is excluded rather
> than judged on today's text.
>
> Kalshi edits both fields under live markets — a strike moved 12000 →
> 12500 while its ticker still read `-12K`; "has become law" became "is
> enacted in"; a counterparty was renamed. Neither the contamination
> probe nor `git diff` of the prompt can see it: there is no recall to
> catch, and the prompt is fully compliant. **How often it happens is
> deliberately not part of this condition** — the honest measurement is a
> lower bound (see above), and the fix costs nothing when no edit
> occurred.

## Two weaker observations, recorded but not claimed as holes

1. **"Answerable from the market's own text as written at open" is a
   counterfactual nobody verifies.** The worked example is safe because
   the NBA has a fixed 30 teams. Set-cardinality questions generally are
   not: "how many plausible nominees are there?" is world knowledge that
   moves over time, so a 2026 model's answer need not match day one's.
   The condition is right; it just cannot be checked from the prompt, and
   a reviewer should ask it explicitly rather than reading the prompt and
   assuming.
2. **The probe tests explicit recall, not implicit influence.** "Can the
   model state the outcome?" and "are the model's gate decisions shifted
   by knowing it?" are different questions. A sharper probe compares the
   gate's *pass rate* on pre-cutoff versus post-cutoff markets matched on
   structure; a gap there is leakage the stated probe would miss.

## What this does not challenge

The amendment's core reasoning is right, and this study does not argue
against it. Penalising a structural gate identically to outcome judgment
did teach theories to avoid the honest tool. The four conditions are
well-chosen and the "derived, never self-reported" guard plus
"an unrun probe counts as outcome judgment" close the obvious
self-dealing routes. This is one missing condition, not a rejection.
