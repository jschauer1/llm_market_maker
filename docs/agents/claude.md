# Claude Code runtime adapter

Read this file when the repository is running in Claude Code. `AGENTS.md`,
`docs/RESEARCH_GUIDE.md`, and the selected canonical skill remain the policy;
this file only maps their runtime operations to the Claude Code host.

## Native agent operations

Claude Code tool inventories vary by version, configuration, and enabled
features. Inspect the tools and their schemas in the active session before
dispatching. Use the exposed operations that implement these outcomes:

| Shared operation | Claude Code mapping when exposed |
|---|---|
| start an independent child | `Agent` with background execution |
| wait for a background child | `TaskOutput` with blocking enabled and a bounded timeout |
| stop a background child | `TaskStop` |
| continue or message a child | the inventory's resume/message operation |
| inspect all live children | the inventory's roster operation, if one exists |

`ListAgents`, `SendMessage`, and scheduler tools are not universal Claude Code
primitives. Never call one because an older procedure named it. When no roster
operation exists, maintain every returned child/task id in `FLEET_LOG.md` and
verify each with the available status/wait operation. That records managed
workers but does not prove global availability; the capacity preflight below
still governs whether a fleet can launch. When no continue or message operation
exists, report the limitation instead of inventing a resume parameter or
starting an unattributed replacement.

Prefer an appropriate mid-tier model for routine autonomous `go` work and a
stronger available model for difficult judgment, following the user's
efficiency preference. Pass a model or effort override only when the active
schema advertises the exact value. Otherwise inherit the session settings and
record that fact. A label such as "strong" or "fast" is a selection criterion,
not a model id.

For an existing judging role, aim for intelligence comparable to the theory's
benchmark judge and choose appropriate reasoning effort; use the shared role
tier when no benchmark exists. Insider judgment's reference is Sonnet-class.
Follow the shared guide's idealized-judge policy: the same procedure shares
calibration across models; retain actual model provenance.

Prefer native completion events or bounded blocking task waits within the
host's communication limits while the supervisor session is active. Arm a
scheduler only when the current inventory exposes create, inspect, and cancel
operations and reports their actual lifetime. Record its id and cancel it
during shutdown. Do not assume scheduled jobs die with the session or expire
after a fixed number of days.

## Capacity

Confirm the host's advertised global concurrency limit, the scope of its roster
operation, and whether worker-created judgment agents share that limit.
`supervise` reserves one global slot for a research worker's required judge and
uses the remaining capacity for at most three research workers. Count every
active agent the native roster exposes, including peer agents outside the
supervisor's own subtree and all nested agents. Do not claim visibility the
roster does not provide.

Before every research-worker or judge start, inspect the native roster. When
two workers need judgment and only the reserved capacity remains, start one
judge; the other worker stays active and uses bounded native task waits and
fresh roster checks until capacity opens. Never turn the supervisor into the
judge, perform required judgment inline, stop a productive research worker for
an ordinary collision, or invent a queue, roster, or capacity the host does not
expose. If the limit or accounting surface is unavailable, report the
capability limitation.

## Shell

Use the shell actually exposed by the host. Run repository Python and Git
commands as single commands. Do not paste Bash continuations or utilities into
PowerShell, or PowerShell pipelines into Bash. Prefer CLI filters and structured
output over shell-only `head`, `tail`, or `wc` pipelines.

## Runtime attribution

Use lowercase `claude` when a command explicitly records the provider, or the
neutral `agent` default when provider identity is not material. Record the
exact model identity reported by the active runtime for judgment provenance.
If the runtime reports only a requested alias and does not resolve it, record
that alias explicitly as unresolved. Do not infer a resolved model from a
configured alias or from this adapter.
