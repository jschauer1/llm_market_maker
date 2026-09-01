---
title: tickets.ticket_dir hardcodes theories/<slug>/, so family-nested theories get a phantom ticket folder
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-cc
status: open
---
Found by the 2026-09-01 floor while filing a theory ticket.

tools/tickets.py::ticket_dir (line ~53) builds a theory ticket path as:

    return Path(root) / 'theories' / theory / 'tickets'

It never consults the theory registry's `path` column. insider_judgment's registry path is `theories/insider_bias/insider_judgment` (it moved under a shared family parent when mention_family split off), so every ticket filed for it lands in:

    theories/insider_judgment/tickets/          <- phantom, contains ONLY a tickets/ dir
                                                   and no THEORY.md, code, or notes

instead of:

    theories/insider_bias/insider_judgment/tickets/

Both insider_judgment tickets are currently in the phantom folder:
  - 2026-09-01-adopt-strong-moderate-no.md
  - 2026-09-01-runbook-stale-on-orphaned-slice.md (filed today)

Why this matters beyond tidiness: CLAUDE.md's expert contract says 'a theory folder contains everything its expert needs to run'. An agent booted inside theories/insider_bias/insider_judgment/ -- which is what the registry, the RUNBOOK and every import path point at -- will never see its own backlog. `cli tickets list` still finds them by globbing, so the breakage is invisible from the supervisor side and only bites the expert.

Fix: resolve the directory from theories.get(conn, slug)['path'] with the hardcoded layout as fallback for a theory with no registry row, then move the two existing files and confirm `tickets list` still reads them. Worth also checking whether anything else in the repo assumes the theories/<slug>/ layout -- registry.discover() and the RUNBOOK's package path already use the real nested one, so this looks like the only place that guesses.
