---
name: propose-theory
description: Formalize a new trading hypothesis into a theory folder, after checking it has not already been tried. Use when you have an idea worth testing, or the user asks for a new strategy.
---

# Propose a Theory

## 1. Check the research memory FIRST

Before any other work:

<!-- rule: search-the-registry (moved from CLAUDE.md § Research memory, 2026-08-29) -->
Search the idea registry **before** proposing anything:

```bash
python -m tools.cli ideas search "<keyword>"
```
<!-- /rule -->

Search several phrasings — the same idea wears different words:

```bash
python -m tools.cli ideas search "<another keyword>"
```

- **Matches a `dead` idea?** Read its `outcome` and `revisit_angle`. Without a
  genuinely different angle, stop and tell the user it was tried and why it
  failed. Repeating a known dead end is the failure this registry exists to
  prevent.
- **Matches a `parked` idea?** Check `revisit_after`. If the condition is now
  met, this is high-value work — proceed and say why it is newly viable.
- **Matches a `promoted` idea?** The theory already exists. Improve it instead.

## 2. Record the idea

```bash
python -m tools.cli ideas record <slug> "<title>" \
    --description "<the hypothesis in a sentence or two>" \
    --source claude
```

Record it even if you end up dropping it — an idea investigated and abandoned
is exactly what a future session needs to know about.

## 3. Write the spec — and the spec is a ticket

**A theory is not made without a spec, and the spec is a `new-theory`
ticket.** Write it before any procedure code. There is no separate spec
tree: there was one, and every document in it still read "Status: backlog
— not yet proposed as a theory" weeks after four had become running
theories, one had been retired and two were dead. One document, one home,
one status.

```bash
python -m tools.cli tickets new --lane new-theory --slug <slug> \
    --title "<the claim in one line>" --body "<the spec>" \
    --session <you> --author-lane <your lane> \
    --author-context "<what you were doing when you hit this>"
```

Read `tickets/new-theory/README.md` first. Its rules 0 through 0f are the
shared contracts every spec in that lane inherits, and they have killed
more ideas in this repo than any single spec's own kill criteria have —
rule 0 (an edge between siblings of one Kalshi event finds nothing) and
rule 0f (measure at *executable* prices, never the mid) between them
account for most of the backlog's dead entries.

What the body must carry, because a session with no other context has to
be able to pick it up and work it:

- **Mechanism** — what mistake is the market making, who is on the other
  side, and **why it persists** rather than being arbitraged away.
- **Kalshi population** — which series and how many markets, counted on a
  real board, not estimated.
- **What would kill it**, stated before any measurement, with the
  cheapest decisive test named first.
- **Mechanical or interpretive**, and the backtest tier that follows.
- **Relation to existing work** — the registry slugs it overlaps, checked
  in step 1, and why this is a sibling rather than a duplicate.

**An idea to try on an *existing* theory is not a new-theory ticket.** It
goes in that theory's own folder (`--lane theory --theory <slug>`),
because a theory folder is supposed to hold everything its expert needs.

**A spec earns its way to a build order.** The lane's states are
`open → evidence → build`, and the last two are not bookkeeping:
`evidence/` is where the cheapest decisive test you named above actually
runs against the bar the spec wrote *before looking*, and `build/` means
that bar was cleared — **ready to implement**. `open → build` is refused
in code, because a build order issued on an unmeasured thesis is the
failure this whole lane exists to prevent.

`build/` is the last state a spec has. Closing one **deletes** it: a
built spec's record is the theory it became, a dead one's is its
ideas-registry row, and `close` checks that row is there first.

```bash
python -m tools.cli tickets advance <path> --to evidence --note "<the test>"
```

Closing takes one of **four resolutions**, as the first word: `built`
(name the theory), `disproven` (the bar was met and the thesis failed —
not re-proposable), `underpowered` (the measurement *could not reach* the
bar, which is a different claim and stays re-proposable), or
`superseded`. The prose still fits after a colon. `disproven` and
`underpowered` are refused unless the finding is already in the ideas
registry with `what_was_tried` and `outcome` — and `underpowered` also
needs a `revisit_angle`, saying what would have to change before anyone
tries again, because `tickets purge` may delete the file once nothing
cites it and the registry row is what survives. Full vocabulary and the
lane's shared contracts: `tickets/new-theory/README.md`.

## 4. Interrogate the hypothesis

- What mistake is the market making, and **why does it persist** rather than
  being arbitraged away? A thesis with no answer here is usually wrong.
- **What would falsify it?** Not what would confirm it. If you cannot state a
  result that would kill this theory, it is not testable.
- Which data sources? Does anything exist to support it?
- If the signal is not from Kalshi, how does it reach a Kalshi ticker?

## 5. Split stage 1 from stage 2

**Ask first whether this theory needs a stage 2 at all.** If the thesis can be
decided by code — a monotonicity violation, a NO-basket summing below its
payout, a base-rate regression, a cross-platform divergence on a matched pair,
a measurable structural bias in a market family — then write the script,
record `edge_basis="model"`, leave stage 2 empty, and stop. That theory is
cheaper, reproducible, scales to the whole board, and backtests at tier A —
it replays over all reachable history and re-runs for free. Prefer it
whenever the thesis allows.

When the thesis does not allow it, that is not a downgrade. A tier B backtest
is capped to the post-cutoff window, so it accrues evidence more slowly and
costs tokens to replay — but that window is recent by construction, and the
smaller sample is already priced into the t-statistic and credibility. Do not
discount it a second time for being tier B.

Reach for LLM judgment when the thesis is *interpretive* — a claim about the
world that genuinely needs reading comprehension or context no threshold
captures: that somebody already knows something the price doesn't reflect,
that an outcome is effectively decided before it is official. Theses in that
mold are encouraged, not a concession: they surface bets no mechanical screen
can see, and proposing more of them is good research. What judgment is never
for is a *structural* question — how many winners the market pays, whether
its strikes are mutually exclusive, which family a ticker is in. Determine
those programmatically unless it is absolutely impossible; CLAUDE.md's
"Theories are instruments" draws the line.

If you do need stage 2: push as much as possible into stage 1 — code is
repeatable and free to run at scale. Be concrete about what's left: "check
whether the resolution source publishes on a schedule that can miss the close"
is useful; "use good judgment" is not.

If stage 1 is likely to leave more candidates than deep reasoning can afford,
decide the **tiering split** now, as part of designing the theory: does stage
2 need a cheap gate ahead of deep analysis, how many candidates does each
tier see, and what single question does the gate answer? Write the split down
in `THEORY.md` — `_TEMPLATE/THEORY.md`'s stage 2 section says what to state.
A theory whose decision path is fully deterministic can skip this and say so.

## 6. Scaffold

```bash
mkdir -p theories/<slug>
cp theories/_TEMPLATE/THEORY.md theories/<slug>/THEORY.md
cp theories/_TEMPLATE/NOTES.md theories/<slug>/NOTES.md
python -m tools.cli theories register <slug> "<Name>" theories/<slug>
python -m tools.cli ideas status <idea-slug> promoted --theory-id <slug>
```

Fill in `THEORY.md` completely. `NOTES.md` is the theory's lab
notebook — dated, raw, append-only — for dead ends, data quirks, and
hunches not yet worth a version bump; a note only moves into `THEORY.md`
once it changes what the theory claims or does. Then scaffold the
`Theory` subclass every theory package must expose — this is the object
`registry.discover()` finds and `find-edge` dispatches:

```python
# theories/<slug>/theory.py
from tools.domain import Candidate, Edge, ScoredCandidate
from tools.theory import Theory, TheoryContext


class <Name>Theory(Theory):
    id = "<slug>"
    name = "<Name>"
    version = 1
    # uses_llm_judgment = True and prompts={...} only if a model judges

    def screen(self, ctx: TheoryContext) -> list[Candidate]:
        ...

    def price(self, ctx, cands, verdicts=None) -> list[ScoredCandidate]:
        ...

# theories/<slug>/__init__.py
THEORY = <Name>Theory()
```

Only `screen()` and `price()` are required — everything else on `Theory` has
a default. Register the DB row with a `version` matching the class's
`version` ClassVar. `tests/test_conventions.py::test_the_real_registry_has_no_drift`
runs `registry.check_drift` against the real database on every suite run and
fails if the two disagree — on version, or on `uses_llm_judgment` — so a
class bumped without its DB row (or vice versa) is caught immediately rather
than silently merging two different procedures under one theory id. Write
any stage-1 code in the theory folder, with tests. Theory-local code stays
local until it earns promotion — see `tools/README.md`.

<!-- rule: facts-are-data (moved from CLAUDE.md § The theory contract, 2026-08-29) -->
**Facts are data, not procedure** — adding a confirmed pair to
`theory_facts` does not bump a version; changing how facts are derived
does.
<!-- /rule -->

**When the idea is a tweak of an existing theory rather than a new thesis**,
skip this whole scaffold and start it as an `exp/` variant instead: subclass
the existing `Theory`, override the one thing you're testing, and run it
with `run_id="exp/<slug>"`. No version bump, no registration — it produces
real, settling evidence at zero ceremony, and that evidence travels with the
eventual promotion (a version bump, or a proposed sibling theory citing the
experiment).

**If the theory uses LLM judgment**, write each judging prompt as a file in
`theories/<slug>/prompts/`, point the class's `prompts` ClassVar at them
(`{"analysis": "theories/<slug>/prompts/analysis.md", ...}`), and declare it:

```python
theories.set_uses_llm_judgment(conn, "<slug>", True)
```

From then on `finish()` refuses to write rows for a run whose model and
prompt were never recorded — that check runs automatically as part of
`run.apply(verdicts).finish()`, so there is nothing extra to call. Prompts
on disk are diffable, reviewable, and reproducible; a prompt living inside a
tool call is a decision procedure nobody wrote down.

## 7. Start at `proposed`, move to `testing` when it runs

A theory is `proposed` while its procedure is still being written. Once the
screen actually runs end to end and starts recording opportunities, move it
to `testing`:

```bash
python -m tools.cli theories status <slug> testing
```

`testing` means the theory is on the board and accruing evidence, while its
claimed edge is not yet demonstrated. It does not become `active` until a
tier A or B backtest shows positive *net* calibration edge
(`calibration_edge_net` — gross `calibration_edge` is not the promotion bar),
or the user explicitly overrides.

Say what evidence you would need to promote it — and what result would send
it to `under_review`. A theory whose falsifying result you cannot name is not
testable.

## If you drop the idea instead

<!-- rule: revisit-angle (moved from CLAUDE.md § Research memory, 2026-08-29) -->
Record every idea you consider, including ones you drop, with what you
actually tried and why it did not work. Write a `revisit_angle` — the
difference between "don't try this again" and "don't try this again *the same
way*" — rather than closing a door permanently. Never retire a theory without
recording why it failed.
<!-- /rule -->

```bash
python -m tools.cli ideas status <slug> dead \
    --what-was-tried "<what you actually did>" \
    --outcome "<why it does not work>" \
    --revisit-angle "<what a different approach would look like, or omit>"
```

Omit `--revisit-angle` only if the idea is genuinely exhausted.
