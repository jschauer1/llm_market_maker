# Enforcing Surfaces — Plan: Rule Delivery (phases A + B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land §7.5's skill-invocation rule + skill map in CLAUDE.md, then move the ten owned task-time rules out of CLAUDE.md into the skills that own them — atomically, content-neutrally, each rule's single home held by a manifest conventions test.

**Architecture:** Pure text moves plus one new conventions test. Every move is one commit that deletes text from CLAUDE.md and adds the identical text to a skill inside a marked block; the manifest test fails at any commit where a moved rule is missing from its owning skill or CLAUDE.md's map stops naming that skill. No behavior code changes.

**Tech Stack:** Markdown, pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-enforcing-surfaces-design.md` §7 (especially §7.2 single-home ruling, §7.3 scope table, §7.5 map text, §7.6 marked blocks + test, §7.7 approval scope). The user approved removing exactly these ten rules, per-commit enumerated. The §7.9 architecture rewrite is already performed — do not redo it.

## Global Constraints

- Suite green throughout: 1,038 passing at plan start (`python -m pytest -q`).
- **Content-neutral moves**: the text added to a skill is byte-identical to the text removed from CLAUDE.md (minus surrounding-context reflow); the commit diff must show delete-here/add-there of the same prose. Rewording a rule during a move is forbidden.
- **Atomicity**: a rule leaves CLAUDE.md only in the commit that lands it in its skill.
- Each commit message enumerates the rules it moves by number and slug (§7.7 auditability).
- Skill files live at `.claude/skills/<name>/SKILL.md`. Marked-block format (from spec §7.6):
  `<!-- rule: <slug> (moved from CLAUDE.md § <section>, 2026-08-29) -->` … `<!-- /rule -->`
- **Coordination (shared tree with a peer session running the log migration):** before editing `tests/test_conventions.py` (Task 1) message the peer session llm-market-identifier-50; Task 6 (rule 32 → go) is HARD-GATED on the peer confirming their §6.7 CLAUDE.md rewrite has landed; RESEARCH_LOG.md appends also go through the peer. The peer owns RESEARCH_LOG.md, theories/*/NOTES.md, the log-classification companion file.
- Commit messages end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## The manifest (single source of truth for Tasks 1–6)

| # | slug | owning skill | CLAUDE.md location (anchors verified 2026-08-29, post-4ecdd2d) |
|---|---|---|---|
| 13 | backtest-web-search-off | backtest-theory | line ~534, the single sentence `Web search stays off in every backtest judgment subagent.` |
| 19 | structural-gate-conditions | backtest-theory | line ~547: the paragraph starting `A judging stage is **structural** — and does not cost tier A — only when all` PLUS its five `- **…**` bullets (through the bullet ending `…refresh the bound as snapshot history grows).`) |
| 20 | record-the-tier-claim | backtest-theory | line ~576: the paragraph starting `Record the claim where it can be checked:` through `…the tier, not the paper trail.` |
| 10 | judge-blind | find-edge | line ~300: the paragraph `**Judge blind to price wherever the theory allows it.** …` ending `…removes the largest contaminant.` |
| 11 | buckets-from-deep-stage | find-edge | line ~635: within the `**Batch within a tier**` paragraph, the sentence `Confidence buckets always come from the deep stage; a gate answers "worth a closer look," never "good bet."` — moved together with rule 12 as one block (they share the paragraph) |
| 12 | batch-and-dedupe | find-edge | line ~635 `**Batch within a tier** — tens of candidates per call, never one subagent per candidate.` plus the dedup sentence at line ~616 `Deduplicate before gating — sibling strikes on one event almost always share a verdict.` |
| 17 | facts-are-data | propose-theory | line ~176: the theory-contract bullet `- **Facts are data, not procedure** — …changing how facts are derived — does.` |
| 35 | search-the-registry | propose-theory | lines ~340-346: the `## Research memory` body: `Search the idea registry **before** proposing anything:` + its bash block |
| 36 | revisit-angle | propose-theory | lines ~347-352: the paragraph `Record every idea you consider… Never retire a theory without recording why it failed.` |
| 32 | notes-theory-log-split | go | **GATED on peer's §6.7**: the (rewritten-by-peer) `RESEARCH_LOG.md stays cross-theory…` bullet in "What lives in a theory" |

Rules that stay (no action): 24/29/30 (no owning skill), 18's tier definitions (constitutional; Task 5 adds only an explainer to score-theories), 25, and everything constitutional/enforced.

---

### Task 1: §7.5 map into CLAUDE.md + the manifest test

**Files:**
- Modify: `CLAUDE.md` (inside "How the user drives this", after the "Both are normal." line)
- Modify: `tests/test_conventions.py` (append; message the peer session first per Global Constraints)

**Interfaces:**
- Produces: `_MOVED_RULES: dict[str, str]` (slug → skill name) module-level in test_conventions.py, EMPTY at this commit — Tasks 2–6 each add their entries; `test_every_moved_rule_lives_in_its_owning_skill`.

- [ ] **Step 1: Add §7.5's rule to CLAUDE.md** — insert this text (spec §7.5, verbatim) as a new paragraph after "Both are normal.":

```markdown
**When a task has a skill, invoke it before starting.** Backtesting →
`backtest-theory`. Choosing bets → `find-edge`. New hypothesis →
`propose-theory`. Settling and scoring → `score-theories`. Comparing →
`compare-theories`. A session → `go`. The skills carry rules this file does
not repeat, loaded at the moment they bind. **Prefer loading a skill to not
loading one**: the cost of reading one you did not strictly need is a few
hundred tokens, and the cost of skipping one is a rule you never saw.
```

- [ ] **Step 2: Write the failing-by-construction test** (append to `tests/test_conventions.py`; it passes green with the empty manifest and bites as Tasks 2–6 populate it):

```python
#: Task-time rules relocated out of CLAUDE.md into the skill that owns the
#: activity (enforcing-surfaces spec 7.2, user-ruled 2026-08-29). One home
#: per rule: the marked block must exist in the owning skill, and
#: CLAUDE.md's skill map must still name that skill. Populated one entry
#: per move commit; an entry here without its block is a dropped rule.
_MOVED_RULES: dict[str, str] = {}


def test_every_moved_rule_lives_in_its_owning_skill():
    """Each relocated rule has exactly one home: its marked block exists
    in the owning skill, and CLAUDE.md's skill map still names that
    skill. A rule dropped in a move fails at the dropping commit."""
    claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    problems = []
    for slug, skill in sorted(_MOVED_RULES.items()):
        skill_file = ROOT / ".claude" / "skills" / skill / "SKILL.md"
        if f"<!-- rule: {slug} " not in skill_file.read_text(encoding="utf-8"):
            problems.append(f"{slug}: no marked block in {skill}/SKILL.md")
        if f"`{skill}`" not in claude_md:
            problems.append(f"{slug}: CLAUDE.md's map no longer names {skill}")
    assert problems == [], (
        "a relocated rule lost its single home:\n" + "\n".join(problems)
    )
```

- [ ] **Step 3: Run** `python -m pytest tests/test_conventions.py -q` (all green) then the full suite.
- [ ] **Step 4: Commit** — `feat: skill-invocation rule + single-home manifest test (spec 7.5, 7.6; phase A)`

---

### Task 2: move rules 13, 19, 20 into backtest-theory

**Files:** Modify `CLAUDE.md`, `.claude/skills/backtest-theory/SKILL.md`, `tests/test_conventions.py` (manifest entries only)

- [ ] **Step 1**: Read backtest-theory/SKILL.md; add a `## Rules this skill owns` section (or append to an existing rules section if one exists) holding three marked blocks, each containing the CLAUDE.md text **verbatim** per the manifest table:

```markdown
<!-- rule: backtest-web-search-off (moved from CLAUDE.md § Backtest tiers, 2026-08-29) -->
Web search stays off in every backtest judgment subagent.
<!-- /rule -->

<!-- rule: structural-gate-conditions (moved from CLAUDE.md § Backtest tiers, 2026-08-29) -->
[the full five-conditions block, cut verbatim]
<!-- /rule -->

<!-- rule: record-the-tier-claim (moved from CLAUDE.md § Backtest tiers, 2026-08-29) -->
[the record-the-claim paragraph, cut verbatim]
<!-- /rule -->
```

- [ ] **Step 2**: Delete exactly those spans from CLAUDE.md. Where the five-conditions block sat inside the "Structural gates keep tier A" narrative, leave ONE pointer sentence so the section stays coherent (spec §7.3): `The five conditions a stage must meet to count as structural live in backtest-theory — load it before claiming the tier.` The pointer is a pointer, never a paraphrase.
- [ ] **Step 3**: Add to `_MOVED_RULES`: `"backtest-web-search-off": "backtest-theory", "structural-gate-conditions": "backtest-theory", "record-the-tier-claim": "backtest-theory"`.
- [ ] **Step 4**: Verify content-neutrality: `git diff` shows the deleted CLAUDE.md prose reappearing verbatim in the skill. Run the full conventions file + full suite.
- [ ] **Step 5: Commit** — `feat: move rules 13 (web-search-off), 19 (structural-gate-conditions), 20 (record-tier-claim) to backtest-theory (phase B)`

---

### Task 3: move rules 10, 11, 12 into find-edge

Same shape as Task 2. Blocks: `judge-blind` (the whole paragraph from line ~300, including the `judged_blind=True` sentence), and one combined block `batch-and-dedupe` + `buckets-from-deep-stage` holding the "Batch within a tier" paragraph plus the "Deduplicate before gating" sentence (two marked blocks may wrap adjacent text; keep the two slugs as separate `<!-- rule: -->` markers even if adjacent). CLAUDE.md keeps the Subagents section's tiering table and narrative; where the removed sentences sat, reflow the paragraph without paraphrasing the removed rules. The judge-blind paragraph's removal from "Never state a probability you introspected" leaves that section's flow intact (the paragraphs before and after don't reference it).

- [ ] Steps mirror Task 2 (verbatim blocks → delete spans → manifest entries → neutrality check → suite → commit `feat: move rules 10 (judge-blind), 11 (buckets-from-deep-stage), 12 (batch-and-dedupe) to find-edge (phase B)`).

---

### Task 4: move rules 17, 35, 36 into propose-theory

Same shape. `facts-are-data` (the theory-contract bullet — the list loses one bullet cleanly; the parenthetical echoes of "facts are data" elsewhere in CLAUDE.md are references, not the rule, and stay). `search-the-registry` (the Research memory body + bash block) and `revisit-angle` (the following paragraph): after both moves the `## Research memory` section body is replaced by one pointer line: `Idea-registry discipline — search before proposing, record what you tried, write a revisit_angle — lives in propose-theory; invoke it before proposing anything.` (that names the topics, quotes no rule text).

- [ ] Steps mirror Task 2; commit `feat: move rules 17 (facts-are-data), 35 (search-the-registry), 36 (revisit-angle) to propose-theory (phase B)`.

---

### Task 5: rule-18 reading explainer in score-theories (additive only)

**Files:** Modify `.claude/skills/score-theories/SKILL.md` only. NOTHING is removed from CLAUDE.md — tier definitions are constitutional (spec §7.4).

- [ ] **Step 1**: Add a short section to the skill: what a tier means when *trusting* a number — quoting nothing, pointing at CLAUDE.md § Backtest tiers as the authority, and stating the two §7.4-ruled reading rules in the skill's own words: tier B numbers already price their sample size (never discount twice); tier C is excluded from credibility, use the contamination probe. Mark it `<!-- explainer: tier-reading (authority: CLAUDE.md § Backtest tiers) -->` so the manifest test never claims it (no `_MOVED_RULES` entry — it is not a move).
- [ ] **Step 2**: Suite; commit `feat: tier-reading explainer in score-theories (rule 18 stays constitutional; phase B)`.

---

### Task 6: move rule 32 into go — **GATED on the peer's §6.7 landing**

- [ ] **Step 0 (gate)**: Confirm via the peer session (llm-market-identifier-50) that their §6.7 rewrite of the `RESEARCH_LOG.md stays cross-theory…` bullet has been committed. Do not start before then; the move must carry their NEW text, not the old.
- [ ] **Steps 1–5**: mirror Task 2 for the (rewritten) bullet → `.claude/skills/go/SKILL.md` as `<!-- rule: notes-theory-log-split (moved from CLAUDE.md § What lives in a theory, 2026-08-29) -->`; CLAUDE.md keeps one pointer line in the bullet's place (`Where notes, theory docs and the log divide lives in go — the split is the promotion bar the user ruled 2026-08-29.`); manifest entry `"notes-theory-log-split": "go"`; commit `feat: move rule 32 (notes-theory-log-split) to go (phase B complete)`.

---

### Task 7: closeout

- [ ] Full suite green; `python -m tools.cli rulings status 7 implemented` (the single-home relocation ruling) — only after Task 6.
- [ ] Word count: `wc -w CLAUDE.md` — record the net change in the log entry (expected: net negative vs pre-§7.5 baseline once all ten rules are out).
- [ ] Message the peer, then append the phase-A/B completion entry to RESEARCH_LOG.md; commit.
