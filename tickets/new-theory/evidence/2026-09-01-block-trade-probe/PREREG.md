# Pass B pre-registration — written BEFORE any per-ticker block count

Ticket: `tickets/new-theory/open/2026-09-01-block-trade-whale-follow.md`
Session `fleet-w2-g2`, new-theory lane. 2026-09-01.

## Question
Does `is_block_trade=true` occur often enough on the liquid Kalshi board
to define a population a theory could screen?

## What is already known when this is written
- taker_flow sampled 93,399 trades over the 40 highest-volume markets;
  the one market inspected in detail had zero blocks (ticket text).
- Pass A here: 15,000 consecutive board-wide trades (2026-09-01
  23:43:45Z - 23:45:48Z), **0 flagged**. The field is present on
  10/10 keys of every row, so this is a measured false, not a missing
  field.
- Prints up to 272,727 contracts appear in that window unflagged, and
  1,342 of the 15,000 were >= 500 contracts. **The flag is therefore not
  a size proxy.**

## Population (fixed here)
Session board, open markets, taker_flow's own liquidity bar:
`open_interest >= 500`, `volume >= 1000`, `spread <= 0.05`.
Sample = the **300 highest-open-interest** markets clearing it.

That sample is deliberately biased *toward* finding blocks: a negotiated
block is size, so the largest open positions are the most favourable
place to look. A null on a favourable sample is decisive; a null on a
random one would not be.

Walk depth: `trades(ticker, max_pages=3)` — up to 3,000 newest trades per
market, newest-first (the feed's only ordering).

## Decision rule (fixed before the numbers)
- **0 flagged trades** across the sample -> no population on the liquid
  board. **DO NOT BUILD.** Record the negative against the idea registry,
  close the ticket with the sample size, and stop.
- **>= 30 markets carrying >= 1 flagged trade** -> a population exists;
  design the screen and run the tier A replay.
- **Flagged trades exist in < 30 markets** -> "exists, but not a
  population". Record the count so no later session re-measures it, and
  do not build.

## What this cannot settle
Whether Kalshi *has* a block facility that simply is not surfaced on the
public trade feed. The theory needs the flag to be readable, so an
unreadable facility kills it either way — but the distinction belongs in
the record.

---

# Pass C — added after Pass B, and it is NOT the decision

Pass B's sample was the 300 highest-open-interest liquid markets, argued
in the pre-registration as the place most favourable to finding blocks.
**That argument has a hole, and it is worth stating rather than hiding:**
the mechanism the ticket proposes is "size that could not be worked into
the book", which points at *thin* books, not thick ones. Pass B's filter
(`spread <= 0.05, volume >= 1000, OI >= 500`) excludes exactly those.

Pass C therefore samples **300 markets at random across the whole board,
no liquidity filter**, `max_pages=2`. Fixed before it runs:

- It is **descriptive**, not the decision. The decision rule fixed above
  is about the liquid board — the only population a theory could trade at
  executable prices (rule 0f) — and Pass B already answered it.
- What Pass C can change: if blocks turn out to be common in illiquid
  markets, the *finding* becomes "the facility exists but lives where you
  cannot trade" rather than "the facility is unused". Different sentence
  in the record, same DO NOT BUILD.
- Seed fixed at 20260901 so the sample is reproducible.
