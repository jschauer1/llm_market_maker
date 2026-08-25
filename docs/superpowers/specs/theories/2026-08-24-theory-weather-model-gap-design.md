# Weather Model Gap — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `weather-model-gap` · Priority: 9 of 22 · Effort: M ·
LLM in decision path: no · Backtest tier: A

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "weather-model-gap"` for status
changes, then formalize via the `propose-theory` skill.

## Assessment

**Applicability 4/5 · Implementability 3/5 · Likelihood of success 3/5 ·
Composite 10/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
calibrated probabilities)

- *Applicability 4:* daily-settling markets across many stations —
  direct bets and the fastest evidence accrual in the backlog.
- *Implementability 3:* forecast-archive plumbing, station↔market
  mapping, and walk-forward bias correction are real work, all keyless.
- *Likelihood 3:* the mechanics are documented in unusual detail and Le
  2026 independently measures structured weather mispricing — but a
  whole retail tool ecosystem now competes on exactly this trade, so
  the surviving edge is probably the station-bias and 3–5-day slices,
  and the backtest must prove edge persists in the crowded recent era.

## 1. Hypothesis

Kalshi temperature markets settle on a specific NWS station reading, and
professional-grade forecast ensembles for that exact station are public
and keyless. Converting an ensemble forecast into a probability per
strike and betting where it disagrees with the market by a wide margin
captures two documented gaps: retail pricing off "the city forecast"
instead of the settlement station, and systematic NWS/city bias patterns
the ensemble sees and casual traders don't.

## 2. Evidence

- Practitioner documentation is unusually specific for this family:
  settlement is per-station (e.g., Boston settles on KBOS at a printed
  close time), a ~2°F forecast cushion clears Kalshi's ~1.75¢ per-contract
  fee, systematic traders use an ~8-point model-vs-market gap as an entry
  floor, and the edge is widest 3–5 days out when uncertainty is priced
  wide. Per-city, per-season NWS bias is described as "one of the most
  measurable and persistent edges" in the family.
- Le 2026 measures short-horizon weather as the *overconfident* domain
  (slopes 0.69–0.87 within 12h — prices too extreme), independent
  evidence that this family misprices in a structured way.
- The honest counterweight: a whole retail tool ecosystem now exists for
  exactly this trade (weather edge finders, bots, playbooks), so the
  cheap version is crowded. The residual claims are the station-vs-city
  gap, the bias patterns, and the 3–5-day window where tools that chase
  same-day accuracy aren't focused.

## 3. Non-goals and exclusions

- Temperature ladders only in v1 (highs/lows). Precipitation and events
  with messier settlement definitions come later, each as a versioned
  addition.
- No proprietary or keyed data: NWS (api.weather.gov) and Open-Meteo are
  keyless; ensemble members come from public model output. If a needed
  archive turns out to require a key, that component is out.
- This is not `settled-but-trading` (post-observation certainty) and not
  `calibration-harvest`'s weather fade (price-bin statistics): this
  theory prices each market from a *forecast*, pre-observation. Overlap
  with the fade cell is handled by `find-edge` same-ticker dedup, and the
  two edges are recorded under different theories with different
  `edge_basis` models.

## 4. Decision procedure

Fully mechanical.

- For each supported station/market: pull the current ensemble forecast
  for the settlement station and valid time; map members to the strike
  ladder → per-strike probability; apply a per-station bias correction
  fitted from that station's historical forecast-vs-settlement errors.
- Candidate: |model − market| ≥ 8 points (the practitioner floor, kept
  deliberately as the pre-registered start) at 1–5 days to close, with a
  liquidity floor. `edge_basis="model"`, capped claim (start: 6 points)
  so ensemble misspecification can't assert a huge edge.
- One candidate per ladder (largest gap), same correlation rule as
  smile-smoothing.

## 5. Data requirements

- Open-Meteo (keyless) for current + **historical archived forecasts** —
  the archive is what makes a tier-A backtest honest; verify archive
  depth at implementation.
- NWS station observations for settlement truth (keyless).
- In-repo: board, candlesticks, fee math. Station↔market mapping is part
  of the versioned procedure.

## 6. Backtest design

Tier A: for each settled temperature market in the candlestick window,
reconstruct the forecast **as it stood** at decision time from the
archived model runs (never the final observation), compute the rule's
trades at historical asks, settle. Lookahead traps: archived-run
timestamps must precede the decision moment; the bias correction must be
walk-forward (fitted only on settlements before each decision date).

## 7. Kill criteria

- Model-vs-market gaps ≥ 8 points exist but resolve in the *market's*
  favor as often as the model's → the crowd already prices the ensemble;
  kill, and record per-station results (one biased station could still
  survive as a narrow theory).
- Archived forecast data unavailable at needed depth → `paused` on the
  prerequisite; the live-forward version can still accrue evidence
  slowly, which is a user decision to make at proposal time.

## 8. Implementation plan

`theories/weather_model_gap/{THEORY.md,ensemble.py,stations.py,screen.py}`
+ tests. Effort M — the forecast-archive plumbing and station mapping are
most of it. Fast evidence accrual is the payoff: these markets settle
daily.

## 9. Testing approach

Unit tests: member→strike probability mapping, bias-correction
walk-forward boundary, station mapping, the 8-point/1–5-day screen.
Fixture backtest with synthetic ensemble runs and known settlements.

## 10. Open risks

- Competition is the central risk (section 2); the spec survives it only
  if the backtest shows residual edge *after* the crowded era began —
  split the backtest window around the tooling ecosystem's emergence and
  weight the recent half.
- Ensemble→probability conversion under-disperses if members are treated
  as exchangeable when they aren't; keep the conversion simple and
  documented, and let the cap absorb the error.

## 11. Sources

- Practitioner playbooks: [botforkalshi strategy guide](https://www.botforkalshi.com/blog/kalshi-weather-trading-strategy), [PillarLab temperature playbook](https://pillarlabai.com/blog/how-to-trade-temperature-markets-kalshi/), [a 32-losing-trades postmortem](https://www.northlakelabs.com/max/blog/what-i-learned-from-32-losing-kalshi-trades/) — settlement mechanics, fee cushion, entry thresholds, bias patterns.
- [Le 2026](https://arxiv.org/pdf/2602.19520) — short-horizon weather overconfidence.
- Keyless data: [api.weather.gov](https://api.weather.gov), [Open-Meteo](https://open-meteo.com).
