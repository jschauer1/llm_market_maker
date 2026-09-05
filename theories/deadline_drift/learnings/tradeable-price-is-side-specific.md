# Price the side the strategy can actually buy

**Summary:** Reconstruct and score the quoted side the procedure trades before interpreting any historical edge.
**Applies to:** Kalshi binary replays that buy NO, especially candle-based history outside the live `Market` type.
**Finding:** Measured (2026-09-01): using `yes_ask` instead of `1 - yes_bid` credited this screen with the bid-ask spread and roughly doubled the apparent gap; the corrected wide-population estimate remained post-hoc and unbettable.
**Do next time:** Name the entry side in the replay, assert its book identity, and report gross and net results at that executable quote.
**Evidence:** [THEORY.md — Decision procedure](../THEORY.md#decision-procedure); [NOTES.md — CORRECTION 2](../notes/archive/NOTES.md#2026-09-01--correction-2-the-edge-was-the-bid-ask-spread-measured-against-the-price-a-no-buyer-actually-pays-it-is-gone)
**Revisit when:** Kalshi changes binary-book identities or historical data exposes direct side-specific asks.
**Updated:** 2026-09-04
