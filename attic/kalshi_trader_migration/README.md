# kalshi_trader migration (one-time, completed 2026-08-23)

`migrate_kalshi_trader.py` imported the predecessor project's track record
from `opportunities.json`. It ran once; it is kept because the v1 data it
can regenerate was deleted on the user's instruction (RESEARCH_LOG.md,
2026-08-23 v2-bump addendum) and this script is the only way back. If it
must run again, note it wrote to the pre-position-identity schema and
will need `migrate-positions` run afterwards.
