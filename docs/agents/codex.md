# Codex runtime adapter

Read this file when the repository is running in Codex. `AGENTS.md`,
`docs/RESEARCH_GUIDE.md`, and the selected canonical skill remain the policy;
this file only maps their runtime operations to Codex.

## Native agent operations

The tool inventory shown in the current session is authoritative. For the
current collaboration API, use these mappings:

| Shared operation | Codex operation |
|---|---|
| inspect live agents | `collaboration.list_agents` |
| start an independent child | `collaboration.spawn_agent` |
| continue an idle child | `collaboration.followup_task` |
| deliver context without starting a turn | `collaboration.send_message` |
| wait for child events | `collaboration.wait_agent` |
| stop a child | `collaboration.interrupt_agent` |

Use `spawn_agent` only for a concrete independent task. Give every child a
unique lowercase `task_name`. Use `fork_turns="none"` for a fleet worker: its
on-disk brief, `AGENTS.md`, the shared guide, and this adapter provide its
context. Prefer an appropriate mid-tier model for routine work and a stronger
available model for difficult judgment, following the user's efficiency
preference. Select a model or reasoning effort only from values advertised by
the current tool schema; otherwise omit the override and record that it
inherited the session settings. Never translate a capability label such as
"strong" into an invented model id.

For an existing judging role, aim for intelligence comparable to the theory's
benchmark judge and choose appropriate reasoning effort; use the shared role
tier when no benchmark exists. Insider judgment's reference is Sonnet-class.
Follow the shared guide's idealized-judge policy: the same procedure shares
calibration across models; retain actual model provenance.

Prefer `wait_agent` for active supervision. Use bounded, multi-minute waits
within the host's communication limits; after a timeout, inspect the live
roster and repository footprint, then wait again. A user message may end a
wait early. A scheduler is not part of the collaboration API. Create no
scheduled automation unless the current Codex inventory explicitly exposes
one and the user asked for it; its documented lifetime, notification behavior,
and cancellation operation then override any example elsewhere.

## Capacity

This host presently exposes four global concurrent slots, including the
supervisor; that is runtime state, not a permanent Codex guarantee. Inspect the
current inventory and configuration each session. `list_agents` reports the
active agents in the current root task tree; count every active agent it shows,
including agents outside the supervisor's own subtree and nested agents under
research workers. Do not claim visibility into unrelated Codex tasks that the
operation does not report.

`supervise` reserves one global slot for a research worker's required judgment
agent, then uses the remaining advertised capacity for at most three research
workers. With the current four-slot limit and no other active consumers, the
valid roster is one supervisor, two research workers, and one slot that is
either free or occupied by one judge. A judge is an additional active agent;
the worker that created it remains active.

Before every research-worker or judge spawn, call `list_agents` and recount.
When two workers need judgment together, only one starts a judge. The other
worker remains active and uses bounded `wait_agent` waits plus fresh inventory
checks until the judge exits; a rejected spawn is not evidence that no agent
started, so inspect before retrying. The supervisor does not become the judge,
and workers do not perform required judgment inline. If the global limit or
inventory needed for this accounting is unavailable, report the capacity
limitation instead of inventing it.

## Windows shell

Codex on this repository runs PowerShell. Invoke Python and Git commands as
single commands; a trailing backslash is not a PowerShell continuation. Use
PowerShell operations for shell-only examples:

| Intent | PowerShell |
|---|---|
| count dirty paths | `(git status --porcelain | Measure-Object -Line).Lines` |
| keep the last three lines | `$result | Select-Object -Last 3` |
| keep the first ten lines | `$result | Select-Object -First 10` |
| copy a template | `Copy-Item -LiteralPath <source> -Destination <destination>` |

The repository CLI is the stable interface. Prefer its filters and structured
output over shell pipelines when both are available.

## Runtime attribution

Use lowercase `codex` when a command explicitly records the provider, or the
neutral `agent` default when provider identity is not material. Record the
exact model identity reported by the active runtime for judgment provenance.
If the runtime reports only a requested alias and does not resolve it, record
that alias explicitly as unresolved. Do not infer a resolved model from a
display name or from this adapter.
