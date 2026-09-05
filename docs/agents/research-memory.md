# Save knowledge that a future agent can use

Keep saved summaries compact and deeper context easy to retrieve. Agents may
read further whenever they judge that more context will help their work. The
size limits below govern saved prose, not how much an agent may learn. Start at
[the knowledge map](../../knowledge/README.md), choose a relevant branch, read
the matching lesson, then follow its evidence only to answer a specific
question. A map is a menu, not a reading list. These rules govern context and
documentation; evidence eligibility and source-data retention remain in the
research guide.

## What to read

1. Get current state from the existing CLI, tickets, and the relevant
   `THEORY.md` sections. Maps describe where to look; they do not cache scores,
   ticket queues, lifecycle status, or model settings.
2. Read the chosen theory's `learnings/README.md` or one shared topic map.
   Open lessons whose applicability matches the task. Before running a theory,
   read its complete runbook, including its sub-theories and required stages.
3. Before expensive work, search relevant lesson titles/summaries and the idea
   registry. If nothing matches, search headings and keywords in that owner's
   historical notes and studies. An unindexed finding may already exist.
   Absence from a map is not evidence that an idea is new.
4. Read the source section when scope, method, uncertainty, or a contradiction
   matters. A source link should identify a heading, run ID, or dated entry.
   A whole notebook, research log, or archive is never a startup requirement.

Read headings first when a document is long, then request the selected section
in bounded chunks. If tool output truncates, continue at the first unread line;
do not repeatedly request the whole file. Judge retrieval by whether it improves
understanding or decisions; a larger reading footprint is not itself a failure.
Compare manifests, hashes, and large tables programmatically; their full text
rarely helps a model decide anything.

For example, `rg -n 'spread|executable|liquidity' knowledge/topics
knowledge/lessons` locates execution lessons without opening study corpora.
For a theory, use its registry path's `learnings/` directory. Search output is
a locator: open the matching file before using its conclusion. Supervisors
use maps and shared state; experts retrieve owner-local evidence.

## Where writing belongs

| Material | Authoritative home | Shape |
|---|---|---|
| Hypothesis, procedure, lifecycle | `THEORY.md`, `RUNBOOK.md`, registry | Current specification; linked detail |
| Measured results, paid judgments, source captures | Existing ledger and owner data | Original evidence and provenance |
| Reusable lesson about a theory | `<registry path>/learnings/<lesson>.md` | One scoped conclusion and action |
| Reusable lesson from an ownerless study or shared operation | `knowledge/lessons/<lesson>.md` | Same card, citing its original owner |
| Study answer | Existing `STUDY.md` | Full result and limitations; link directly if already short |
| New exploratory narrative | `<owner>/notes/YYYY-MM-DD-<question>.md` | One investigation; outcome first |
| Work still to do | Existing owner ticket or in-flight study | Task and next action |
| Consequential change affecting other sessions | `RESEARCH_LOG.md` | Short dated change and source link |

Old notebook bodies live under each owner's `notes/archive/`, reached through
the compact `NOTES.md` entrypoint. Old log entries live in the linked global
archive. Preserve original evidence, retrieve relevant sections, and write new investigations in
separate `notes/` files. Results already recorded in a campaign or study need
no second narrative in notes. Keep raw data and paid outputs in their existing
stores; prose points to them instead of pasting rows or transcripts.

## The lesson formula

Use [the card template](../../knowledge/templates/lesson.md). A card contains
exactly these fields, in this order:

- **Summary:** One sentence saying what a future agent should retain.
- **Applies to:** Population/sub-theory, version, window, and conditions that
  limit the finding. Include discovery versus independent confirmation.
- **Finding:** Label it measured, observed, interpretation, or unconfirmed.
  State the conclusion and its important uncertainty. Date any numerical
  snapshot; include the denominator/unit when needed to interpret it.
- **Do next time:** A concrete decision, check, or avoided repetition.
- **Evidence:** Direct source links and a section, run ID, or retrieval key.
  Cite original evidence, not only another summary.
- **Revisit when:** An observable change that warrants testing again.
- **Updated:** Date this interpretation was checked against its sources.

The Summary and Do next time must carry the same conditions as Applies to.
For example, an offset-based resume over a changing sort order needs a frozen
population; a test of that case does not require every stable-key paginator to
save an ordered list. Keep synthetic demonstrations explicitly synthetic and
separate from empirical claims about real markets or production behavior.

A lesson earns a card only if it changes a future decision or saves meaningful
investigation. Name that decision or avoided work in **Do next time**. A map
entry earns space only if its summary helps select useful content; "notes about
X" and "we investigated Y" fail this test. Shortness alone is not value. Remove
low-value summaries from active memory instead of polishing or archiving more
summaries. Retain an old-path pointer only when existing citations need it.
A routine successful run, unchanged result, test count, command
transcript, and unfinished idea do not earn one. A subset finding stays scoped
to that subset. An underpowered result remains unconfirmed. Compressing a
finding never makes it a new source of probability or changes an evidence gate.

Before discarding a finding as already learned, compare the relevant card's
finding and action with the new source. A shared topic or map title does not
establish duplication: a new failure mechanism may change what to do next time.
If the reading allowance prevents that comparison, leave the source intact and
state that consolidation is unverified; do not call it redundant.

## Budgets and navigation

| Surface | Limit |
|---|---|
| Root map or topic/owner map | 500 words, at most 12 child entries |
| Each map entry | One link and a summary of at most 30 words |
| Lesson card | Target 100–140 words; maximum 180, including fields |
| Global log entry | Maximum 80 words, including its evidence link |
| Active global log | 800 words; at most 8 dated entries |
| New narrative note | 1,200 words; supporting evidence linked separately |

When a map exceeds its limit, split it into meaningful question groups and
replace their entries with summary links to the child maps. Do not create
`part-1`, `misc`, or an unlimited list of every leaf. Search remains available
across all cards; normal reading follows one branch. Filenames describe the
conclusion, without a date, so references survive revision.

When a card exceeds its limit, remove repetition first. If it contains two
independent decisions, split them. Keep the applicability and uncertainty;
move methods and supporting detail to the source. Map summaries help select a
card and must not become competing accounts of its evidence.

## Save and consolidate

At session close, preserve any new evidence, update the existing task record,
then decide whether a reusable lesson was learned. Search for an existing card
before adding one. Revise that card in place, update its map summary in the same
change, and keep the original evidence. If a conclusion is overturned, say so
in the finding with both sources; if merged, leave a short `Superseded by`
pointer at the old path and remove it from active menus. Do not silently erase
an earlier contradiction. Correct historical errors with a dated correction.

The writer owns link maintenance. Moving a study, retiring a theory, renaming
a source, or superseding a lesson includes updating incoming map/card links.
Use `rg` on the old path or filename to find them. When a source cannot be
recovered, mark the lesson unverified and retain that limitation until repaired.

When archiving prose with existing citations, retain a visible source link
and `<!-- research-memory-archive: relative/path.md -->` at the old entrypoint.
The convention check follows that explicit redirect to verify dated citations
and ruling headings without changing historical database rows. Newly written
evidence links name the original source directly, including its section.

Append to `RESEARCH_LOG.md` only when a result changes how a different session
should act: explain what changed, why it matters, and link its canonical home.
Routine completion needs no entry. Keep history chronological; when the active
log reaches its limit, move its oldest complete entries to a dated file under
`knowledge/archive/`, update that archive's summary map, and preserve citations.
Historical instructions are evidence of past practice, not current policy.

Finish by checking that a reader can choose a relevant branch, understand the
action and its limits, and locate the evidence without reading the archive.
Initial maps are curated coverage, not proof that all old findings have been
distilled. Improve coverage when a task encounters a useful missing lesson.
Do not launch an exhaustive archive backfill. Omitting low-value history from
active memory is acceptable; spending an unbounded token budget preserving
every past thought is not the goal. When a source is too costly to verify for
the task at hand, leave the lesson out or state its uncertainty.
