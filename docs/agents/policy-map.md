# Load policy for the work being done

Read this map at startup after `AGENTS.md`. The complete authoritative text
stays in `docs/RESEARCH_GUIDE.md`; this map selects text, not which rules apply.
The runtime adapter and the selected canonical skill are also required.

The universal invariants in `AGENTS.md` apply to every task. Select guide text
by the action being performed, not by topics merely quoted, summarized, or
present in an input artifact. If one bounded profile below fully describes the
work, load exactly its sections. Otherwise use the action matrix and combine
rows for the actions actually being performed.

Read each selected `##` section separately and in full, including its `###`
subsections, through the next `##` heading. Locate headings in the current file
instead of relying on cached line numbers. If output truncates, resume after the
last displayed line; do not restart the section or reread the whole guide.
Load new sections before widening into a new action.

## Bounded action profiles

- **Report from completed receipts supplied or already saved:** `Mission`;
  `Pipelines propose, judgment disposes`; `Never state a probability you
  introspected`; `How ranking works`; `What counts as evidence`. This permits
  reading and reporting existing results. It does not start judgment, pricing,
  screening, the floor, or a replay.
- **Interpret saved research to choose the next worthwhile action:** `Mission`;
  `Research memory`; `How ranking works`; `An underperforming theory is a research object,
  not trash`; `What counts as evidence`; `Backtest tiers`. This permits a
  bounded decision or hand-off. It does not implement pricing or a backtest,
  run collection, or mutate live research state.
- **Record an answer whose research is already complete:** `Mission`; `The
  theory contract`; `What lives in a theory, and what gets elevated`; `Research
  memory`. This permits the requested answer document and
  earned navigation/context updates. It does not load lifecycle policy unless
  the task also moves, deletes, retires, or changes theory status/version. Load
  `Data conventions` before handling source datasets, collection, storage, or
  backups; a Markdown summary of a supplied answer does none of these.

These profiles are narrow overrides to over-broad topic matching, not shortcuts
around the named sections. If the task performs another action, return to the
matrix below and add every row for that action before proceeding.

Read the whole guide for a broad policy audit or when the task cannot be mapped
confidently after applying the profiles and action matrix.
An autonomous `go` worker first reads orientation sections, then loads the
sections for its selected lane before acting there. A supervisor loads the
supervision rows; experts retrieve relevant theory-local source sections via
`knowledge/README.md`. Maps select lessons; they do not require reading every leaf.

| Guide section | Read when |
|---|---|
| `Mission` | Every task. |
| `What ships here — and what doesn't` | Orienting an autonomous session, proposing theories, or reviewing project scope. |
| `Theories are instruments` | Research orientation, proposing or changing a thesis, choosing a research lane, or supervising researchers. |
| `Platform roles` | Researching markets, matching markets, recording opportunities, or changing those tools. |
| `How the user drives this` | Autonomous research orientation, supervision, or creating/changing tickets, studies, skills, and session workflows. |
| `Pipelines propose, judgment disposes` | Screening, judging, recording, ranking or reporting candidates, or changing those tools. |
| `The theory contract` | Running or building a theory/study, changing its harness, ledger boundary, or judging integration. |
| `What lives in a theory, and what gets elevated` | Creating, moving, or sharing code/data/docs; changing architecture; working on a theory, study, or backtest; supervising experts. |
| `Never state a probability you introspected` | Any probability, edge, model, judgment, gate, theory design, evidence analysis, or changes to those tools. |
| `Research memory` | Reading/writing research context, proposing, revisiting, researching or deduplicating an idea; changing memory or idea-registry tools. |
| `How ranking works` | Scoring, pricing, comparing, promoting or reporting opportunities; working on theories, slices, or evidence; running the floor or supervising research. |
| `Toolkit` | Every coding task or task that invokes repository tools; includes vocabulary and compatibility rules. |
| `Theory lifecycle and versioning` | Changing a theory/procedure/status/version, interpreting evidence across versions, retiring or supervising theories, or changing lifecycle tooling. |
| `An underperforming theory is a research object, not trash` | Diagnosing results, changing procedure/evidence/version relationships, retirement, scoring, comparison, or supervising research. Includes version carry rules. |
| `What counts as evidence` | Any backtest, measurement, pricing, score, probability, ranking, promotion or evidence claim; running the floor or supervising research. |
| `Backtest tiers` | Running, judging, scoring, consuming, or changing backtests; claiming contamination tier or historical credibility. |
| `Subagents — cheap gates, expensive analysis` | Dispatching judgment, delegating research, choosing model tiers, or changing worker workflows. |
| `Record what judged, and what you asked it` | Dispatching or ingesting judgments, using a new model, recording provenance, moving prompts, or changing those interfaces. |
| `Data conventions` | Reading/writing/collecting/deleting data, changing storage or backups, recording or reporting results, creating studies, or running the floor. |
| `Getting started` | First use or autonomous research orientation. |

For a bounded code fix, start with Mission and Toolkit plus the rows describing
the behavior and files affected. For evidence work outside a bounded profile,
read the complete evidence, ranking, lifecycle, judgment, and data policies
before deciding what may pool.
Tests check that every top-level guide section has exactly one row here; new
policy cannot silently become unreachable from startup.
