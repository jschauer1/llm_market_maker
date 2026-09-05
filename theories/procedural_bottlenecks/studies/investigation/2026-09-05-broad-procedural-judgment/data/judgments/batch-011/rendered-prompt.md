# Broad procedural judgment — prospective discovery, revision 1

You are an independent price-blind judge. Read only this prompt and the
specified bare input. The operator already loaded repository research policy.
Do not inspect receipts, other studies, the database, old verdicts or prices.
Do not spawn agents. Use the requested model/effort, and report actual search
usage honestly. This is an experiment, not a betting recommendation.

Question: Does a real, identifiable decision or process have necessary steps
whose current status changes whether the exact contract predicate can happen
by its actual payout deadline? The mechanism applies across all domains.
Do not reject a domain merely because it is unfamiliar or not FDA/legislation.
Do not forecast a probability or name a price, position, edge or fair value.

Work in supplied event order; classify EVERY listed market exactly once.
Read rules_primary and rules_secondary together. The scheduled close can be
after an economic deadline: extract the actual rule deadline and exact event
that pays YES. Different subjects/rungs in an event can have different labels.
Identify shared subjects so repeated deadline rungs cannot masquerade as
independent evidence. Family describes mechanism, not whether it looks good.

Use these categories:

- `substantive_barrier`: A necessary substantive step is unfinished and a
  documented current obstacle or timing conflict obstructs the path by THIS
  deadline. Cite the required step AND the obstacle; examine credible bypasses.
  A later target date is not proof of impossibility. A past rejection needs
  current status. Merely pending work, a difficult election, or no announcement
  is not a barrier.
- `plausible_path`: Material steps remain, but dated affirmative evidence
  supports a viable path by the deadline. A generic possibility, hopes, rumors,
  or “there is still time” is insufficient. This label does not predict YES.
- `formalities_only`: The substantive decision is already made or completed;
  only a routine ministerial act remains to satisfy the contract. A vote,
  signature with discretion, genuine review or substantive launch is not a
  formality. Check whether the rules already resolve on the earlier decision.
- `insufficient_evidence`: The mechanism could apply, but available status is
  missing, stale, contradictory or too weak for the labels above. Preserve the
  gap, never fill it with intuition. Search failure remains this category.
- `not_applicable`: No identifiable institutional/organizational process or
  necessary-step mechanism bears on this predicate. State the exact reason;
  pure live sporting performance, measurement totals and spontaneous mentions
  are usual examples. Natural/aggregate outcomes can have institutional
  components, so classify the actual contract rather than its category.

Research efficiently across shared sources and deadlines. Use current primary
sources (official records, agency/company statements, filings, court dockets,
organizer schedules); reliable reporting may identify a primary source. Search
by subject/predicate, not Kalshi ticker. Avoid market and prediction websites
because their prices/outcomes defeat blindness. Keep source publication dates
and distinguish scheduled targets from completed acts. Check current status
before compressing a packet. Do not browse historical sources as though they
were today's status. Only sources public by the decision timestamp may support
the verdict. If a publication day overlaps that timestamp and its hour is
unknown, disclose ambiguity and abstain when it matters.

For not_applicable, exact rule text is sufficient; no pointless search. For
other categories, search source status, reuse within one event when applicable,
and preserve what was actually found. Do not impose a per-family success quota
or force a label to make the sample interesting. A focused unresolved search
can end with insufficient_evidence; do not spend indefinitely on one subject.

Write one JSON object per line to the specified NEW output file. Append and
flush after each event so paid work survives interruption. Never overwrite
existing verdicts. Schema for every line (no extra numeric probability fields):

```json
{
  "key": "exact input market key",
  "bucket": "one category above",
  "subject_key": "stable entity+underlying action, shared across rungs",
  "family": "short mechanism family, e.g. corporate_transaction",
  "predicate": "what exactly makes this contract YES",
  "deadline": "rule deadline, or unknown with explanation",
  "mandatory_steps": [{"step":"necessary step","status":"complete|pending|unknown","source_url":"url or rules"}],
  "obstacle": "documented obstacle or none established",
  "bypass": "supported route around the obstacle or unresolved",
  "rationale": "compact explanation grounded in actual cited evidence",
  "sources": [{"url":"primary URL","title":"title","published_at":"date or unknown","accessed_at":"UTC timestamp","quote":"short supporting excerpt","supports":"precise fact"}],
  "source_gaps": ["material missing status or none"],
  "web_search_used": true
}
```

Retain source search receipts in a separate sources.jsonl beside the output,
including unsuccessful searches and URLs consulted. Save raw primary source
bytes with retrieval timestamp and SHA-256 where directly accessible; report
access failures instead of inventing captures. Keep rationale short enough to
review, while retaining the necessary evidence. After each completed batch,
report counts and the output path to the operator. Do not inspect prices to
decide which judgments deserve reporting.


Bare input: C:\Users\jbs00\OneDrive\Documents\Current_Work\LLM_market_identifier\theories\procedural_bottlenecks\studies\investigation\2026-09-05-broad-procedural-judgment\data\judgments\batch-011\input.json
Output: C:\Users\jbs00\OneDrive\Documents\Current_Work\LLM_market_identifier\theories\procedural_bottlenecks\studies\investigation\2026-09-05-broad-procedural-judgment\data\judgments\batch-011\first-output.jsonl
