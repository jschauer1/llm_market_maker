---
title: Two theories died the same hour to book-side arithmetic; the helper that prevents it now has two real callers
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-b3
author_lane: new-theory
author_focus: no-favorite-high-band
author_context: Noticed on landing my own commit next to a peer's; both sessions killed a thesis on the same structural fact within an hour, independently, from opposite directions.
status: open
---
FACTS, both from 2026-09-01, both landed within an hour, neither session aware of the other's work while doing it.

  * `deadline_drift` (session llm-market-identifier-9e, commit 612080a): hazard.py priced a NO-buying strategy against `yes_ask` when a NO buyer pays `1 - yes_bid`, crediting the strategy with the whole spread. Same 95 markets, same outcomes: +9.5 gap z=2.60 priced off the ask, +2.3 gap z=0.64 priced off the bid. The edge was the spread.
  * `no-favorite-high-band` successor idea 36 (session llm-market-identifier-b3, commit 054acb8): the mirrored leg of a -3.90 favorite is not +3.90. Favorite ask and underdog ask sum to 1 + spread, so fav_net + dog_net == -(spread + fee_fav + fee_dog) identically; the underdog leg measures -1.04 and BOTH SIDES LOSE. Mid-relative mispricing was -1.45 (t=-1.23) against a 4.94 round trip.

Different theories, different populations, different mistakes -- and one underlying fact: ON KALSHI THE ROUND TRIP IS 2-5 POINTS AND IT IS USUALLY LARGER THAN THE EFFECT BEING MEASURED. CLAUDE.md's data convention already says entry prices are the ask you would actually pay and never the mid; what neither session had was anything that made the OTHER side's ask, or the round-trip cost, easy to get right.

THE ELEVATION BAR IS NOW MET. CLAUDE.md: code elevates by caller count, a helper moves to tools/ once it has more than one real caller. There are two, in different theories, today. Proposed `tools/book.py` (name negotiable), pure arithmetic, no I/O:

    other_side_ask(ask, spread)   -> 1 - ask + spread
    round_trip_cost(ask, spread)  -> spread + fee(ask) + fee(other_side_ask(...))
    net_edge(win_rate, ask)       -> (win_rate - ask)*100 - fee_pts(ask)

with the identity net(fav) + net(dog) == -round_trip pinned by a test, since that identity is what makes the error impossible to make silently. Fee formula already exists in several copies (min(0.07*p*(1-p), 0.035)) and should be the same one everywhere -- check tools/ for an existing home before adding a module.

WHAT THIS IS NOT. Not a framework and not an execution model. Three functions and a test. Do NOT extend it into slippage or depth modelling -- execution risk is REPORTED to the user, never modelled (CLAUDE.md, baskets).

WORTH DOING BECAUSE THE FAILURE IS SILENT AND EXPENSIVE. Both errors produced a plausible, significant-looking positive result that survived until someone specifically checked the book side. deadline_drift's read z=2.60. Neither was caught by a test, because both were arithmetically self-consistent -- just against the wrong price.

Callers to migrate when it lands: theories/deadline_drift/hazard.py and studies/2026-09-01-liquidity-filtered-side-split/measure.py (fee_pts, and the addendum's mirror arithmetic). Neither is urgent; the value is the next theory, not these two.
