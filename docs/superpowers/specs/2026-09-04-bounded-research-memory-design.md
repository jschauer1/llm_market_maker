# Bounded research memory

User approved the context-only refactor on 2026-09-04, adding exploration
through summaries. Trading behavior, evidence math, floor scheduling, and
other proposed refactors are outside this change.

This includes existing research Markdown entrypoints: `RESEARCH_LOG.md`
(there is no standalone `research.md` in the current inventory), theory
Learnings sections, notebooks, study answers, and results write-ups. Each is
classified as current decision context, scoped reusable knowledge, or targeted
source history. Navigation is updated mechanically; semantic distillation
follows the bounded selection below. A short summary is admitted only when it
names a useful future decision or saves specific investigation. Content that
fails this bar is removed from active memory, not given a placeholder summary.

The interface is a Markdown knowledge map: root questions lead to bounded
topic/theory menus, then individual lesson cards, then original evidence.
Theory lessons live with their theory; shared lessons cite ownerless studies
or shared operational evidence. Existing databases, specifications, studies,
and raw captures retain their responsibilities.

The card's required fields are Summary, Applies to, Finding, Do next time,
Evidence, Revisit when, Updated. Scope and uncertainty survive compression.
Maps are limited to 500 words and 12 child entries; cards to 180 words;
global entries to 80 words; the active log to 800 words and 8 dated entries.
New raw narrative uses one question per file, capped at 1,200 words.

Current policy and task procedures replace mandatory whole-notebook reading
and per-session global diaries with progressive retrieval and conditional
consolidation. Historical material is preserved. The old global log is copied
byte-for-byte into an explicitly historical archive before its entrypoint is
rewritten. Notebook bodies and old theory Learnings sections move intact to
owner-local `notes/archive/`; compact original entrypoints lead to useful
selected lessons and preserve explicit archive redirects for old citations.
Initial curated maps disclose
that unindexed history can still contain relevant findings.

Validation: compare agent startup/close-out behavior before and after; inspect
lesson fidelity against original sources; check budgets, navigation, and local
link targets; verify log preservation by hash; run existing policy/discovery
and documentation convention checks. No production Python or database changes.

## Migration from the current repository

The user's priority is lower token cost, even when that means losing some
information from active memory. Completion means usable navigation and useful
selected lessons, not an exhaustive summary of the repository. Historical
sources can stay on disk without earning space in the maps.

1. **Move mechanically first.** Preserve the existing global log verbatim in
   the archive, replace its entrypoint with a short map/current narrative, and
   replace instructions that demand full notebooks or per-session diaries.
   Move notebook bodies and historical Learnings sections mechanically into
   owner archives too; their old entrypoints contain only useful retrieval
   routes. This removes bulk prose from active context without model-based
   rewriting of old entries.
2. **Select from cheap signals.** Use filenames, headings, study verdicts,
   current specifications, and existing structured state to choose lessons.
   Prioritize an expensive repeated mistake, a result's applicability limit,
   or a constraint that changes the next action. Skip task diaries, test totals,
   repeated explanations, and obsolete next-step lists.
3. **Bound the initial distillation.** At most two cards per current theory,
   one per retired theory, and four shared cards: at most sixteen cards.
   Already completed useful cards may remain; no expansion just to fill quotas.
   For unfinished owners, read at most roughly 2,000 additional source words
   per theory and 4,000 for shared findings, using targeted sections. Stop on
   the first limit reached. If a claim cannot be substantiated within that
   allowance, omit it or mark the uncertainty rather than launch a broad audit.
4. **Use existing short answers directly.** A study with a clear verdict and
   limits can be a map entry pointing to its answer; it needs no extra card.
   A long source with no selected lesson remains searchable and unindexed.
5. **Check cheaply, then stop.** Check all links and word limits mechanically.
   Review selected high-impact claims against their cited passages; exercise
   a few fresh-agent retrieval/close-out scenarios and existing documentation
   checks. Do not run a model over every historic entry or repeatedly polish
   the same summary. Source ambiguity is disclosed, not concealed by prose.
6. **Improve on demand.** Future agents add a missing lesson when actual work
   encounters it and its reuse justifies the cost. There is no automatic
   exhaustive backfill job or open-ended migration backlog.

Accepted loss: low-value history, duplicate explanations, and undiscovered
older findings may be absent from active memory. We preserve the original
archive cheaply, but do not require agents to recover everything in it.
Source captures, paid judgments, run provenance, and measured records remain
intact. A summary must retain scope, uncertainty, and its original evidence
pointer; if it cannot, leaving it out is preferable to a misleading lesson.

The current files are edited in place for the approved context scope; prior
uncommitted implementation work is preserved. Smaller-model curators receive
non-overlapping owners and the above stop conditions. The parent integrates
and validates the navigation instead of repeating their full research reads.

Delivery is checked in `tests/test_research_memory.py` and the existing
convention suite. Fourteen useful cards survived the initial sixteen-card
selection after two failed the duplication/value review. Studies and results
remain original evidence reached by question; no attempt was made to rewrite
every source or turn each old paragraph into a new memory item.
