# Calibration Harvest — lab notebook

Raw, dated, append-only. Distilled findings graduate to `THEORY.md`.

## 2026-08-27 — built; the repo's existing settled data cannot serve this theory

Built from the backlog spec
(`docs/superpowers/specs/theories/2026-08-24-theory-calibration-harvest-design.md`,
priority 1 of 22). Registered `proposed`, deliberately not `testing`: no
cell is measured, so the theory records nothing on the board yet.

**The first thing I checked, and the reason this took longer than "S".**
The repo holds 6,636 settled full-coverage backtest rows
(`backtest-2026-08-25-mention-fullcov` 3,441 +
`backtest-2026-08-25-insider-fullcov` 3,195), all with point-in-time asks
and settlements. Reusing them would have made this a one-hour build. They
are unusable here, for two independent reasons:

1. That population was **fetch-scoped by `replay.NO_CATEGORIES`**, which
   excludes Sports, Crypto, **Climate and Weather**, Commodities,
   Economics, **Elections** and Financials. This theory's central claim is
   that politics and weather have *opposite* signs. The one dataset on
   disk excludes both.
2. It inherits `insider_bias.screen`'s **14-day cap** on days-to-close, so
   every horizon bin beyond two weeks is empty — and Le 2026's horizon
   component is strongest at 1mo+.

Confirmed by inspection rather than assumed: the 461 distinct series in
those runs are mention/entertainment-heavy (KXWCMENTION 855, KXTRUMPMENTION
350, KXRT 242, KXALBUMEQUIV 234...), and the horizon split is
2,219 / 2,331 / 2,086 across `<=2d` / `2d-1w` / `1w-2w` with nothing beyond.

So this theory needs its own collection. Hence `collect.py` rather than a
one-shot `backtest.py`.

**Sizing the campaign** (measured 2026-08-27 against `/series`, 13,578
series total): Politics 2,240 (1,060 touched in 60d), Elections 1,606
(1,444), Climate and Weather 360 (154). The two pre-registered domains are
~2,650 series of per-series settled walks plus a candlestick call per
settled market. That is a multi-session campaign, which is why the
collector checkpoints per series and writes every observation to the DB as
the series completes.

**Design decisions worth recording:**

- *One observation per (market, horizon bin).* The rows share an outcome
  and are not independent — but every row of one market settles on the
  same day, so the day-clustered SE this theory already mandates absorbs
  that dependence for free. The residual bias (markets contributing
  unequal row counts tilt the point estimate) is in THEORY.md's known
  biases and is the reason `n_days`, not `n`, gates `measured`.
- *Entry offsets 1 / 4 / 14 / 45 days* sit comfortably inside their bins
  so a one-candle timing slip cannot move an observation across a cell
  boundary.
- *No import from `theories/insider_bias/`.* Forbidden as a sibling
  import, and wrong on the merits — the 14-day cap is exactly the
  parameter this theory must not have. The overlapping spread/volume
  numbers are coincidence of both wanting tradeable markets.
- *Wilson lower bounds everywhere.* `mention_family` computed edges
  against a raw 41/41 = 1.000 and died at full coverage; its own NOTES had
  flagged the unshrunk rate as a defect. A grid of cells guarantees some
  cell looks golden, so the pessimistic end of the interval is the only
  honest reading.

**Smoke test (NOT a result).** Ran the collector over the first 4 weather
series by API order — 218 observations, 58 settlement days:

```
weather|<=2d|0.65-0.75   30/41   days=37
weather|<=2d|0.75-0.85   39/50   days=33
weather|<=2d|0.85-0.92   40/42   days=32
weather|<=2d|0.92-0.97   76/81   days=49
```

Overall +0.58 pts net with a day-clustered SE of 1.7 — indistinguishable
from zero, which is the correct thing for a smoke test to show.

**These numbers must not be read as evidence** and are recorded only to
show the pipeline works: 4 of 154 series, taken in API order, is exactly
the thin non-random slice that killed `mention_family`. The theory's own
rule is full coverage of a population before any cell publishes a rate.

One genuinely encouraging structural fact did come out of it, and it is
about the *method* rather than the result: weather cells reach 32–49
distinct settlement days at n≈41–81, because weather markets settle every
single day. That is the opposite of the day-clustering problem found in
`studies/2026-08-27-settlement-day-clustering/`, and it means the weather
domain can clear the `n_days >= 8` floor easily. The politics domain,
whose markets cluster on event dates, will be much harder — worth watching
when that collection runs.

**Next:** full weather collection (154 series) started in the background
tonight against `--run-id backtest-2026-08-27-calharvest-weather`,
checkpoint at `backtests/weather.json`. Politics+Elections
(~2,504 series) is the larger job and has not been started. The theory
moves to `testing` only once a population is complete and a cell clears
both floors under full coverage.

## 2026-08-27 (later) — collector was measuring a population the screen would never trade

Caught while watching the first full weather run: **`collect.py` applied no
volume floor at all**, while `screen.py` requires `volume >= 500`. The
replay was therefore reconstructing decisions on markets the live theory
could never have surfaced, and every cell rate it produced would have
described an untradeable population. That is the exact failure the
backtest rule in CLAUDE.md is written to prevent — "call the same
functions the live path calls" — and I had reimplemented the screen's
conditions in the collector while dropping one of them.

The 417 observations already collected were discarded (rows deleted;
settlements kept, since those are facts about the world rather than
decisions) and the checkpoint reset. Nothing was published from them.

Fixed in two places, both mirroring `insider_bias.replay`:

- `_candle_at` now returns `(candle, running_volume)`, accumulating volume
  over exactly the candles at or before the entry moment. Kalshi's candle
  volume is per-period, not cumulative, so the running sum is what the
  live screen's `volume` field would have shown — and summing only to the
  entry candle is what keeps it lookahead-free. An entry below the floor
  yields no observation for that bin.
- `worth_fetching(volume)` skips a settled market before any candlestick
  call when its *final* volume is under the floor. Cumulative volume only
  grows, so a market that ends below the floor was below it at every
  earlier moment — a safe, conservative pre-filter, and the same argument
  `replay.is_candidate` makes.

The second one is also the fix for a practical problem: the first run was
managing ~80s per series (11 of 154 in ~15 minutes, a ~3.5h projection)
because it fetched 60 days of daily candles for *every* settled market
including low-volume husks. `below_floor` is now reported per series so
the skip rate is visible rather than assumed.

**No version bump.** The theory is `proposed`, has never run live, and has
published no measurement — this is fixing the procedure before it has a
track record, not changing one that has. Had a single cell been published
from the old rule, this would have been a v2.

Lesson worth carrying: a collector that *reimplements* the screen's
predicates instead of calling `screen.screen()` will drift from it, and
the drift is invisible until someone diffs the two by eye. The sibling
`insider_bias.replay.replay_market` avoids this by running the real
`screen.screen()` against a reconstructed `Market`. This collector cannot
do quite the same thing — it needs an observation *per horizon bin*
rather than the first day that clears — but the next revision should
reconstruct a `Market` and call the real screen per bin rather than
re-checking spread/volume/price by hand.

## 2026-08-29 — the collector cannot be made faster, and it does not need to be

The 2026-08-27 stop note flagged the collector as slow ("~1 series/several
minutes on large series; worth profiling the per-market candle call before
committing to the ~2,504-series politics run"). Profiled it. Three
findings, and the last one is the useful one.

### 1. It is all in the candlestick call, as suspected

Instrumented `tools.http.get_json` by URL shape over three real weather
series: **99.5% of wall clock in per-market candlestick GETs**, 350 calls
at 244ms each = 85s of an 86s walk. `list_settled` was 0.4s of it.

### 2. The obvious two fixes do not work

**Connection pooling: no.** The hypothesis was a TLS handshake per call,
since `requests.get` opens a fresh connection every time. Added a pooled
per-thread `requests.Session` (`tools/http.py`) and re-measured against
the live API: mean candlestick latency **244ms → 239ms**. The cost is
server-side, not handshake. The change was kept — it is correct, it does
help the paged `list_settled` calls (127ms → 82ms), and it is the
prerequisite for any threaded caller — but it is not a speedup.

**Concurrency: also no, and this is the real constraint.** Same 80-fetch
probe set at several worker counts:

| workers | wall clock | ms/call | errors |
|---|---|---|---|
| 1 | 17.5s | 218 | 0 |
| 4 | 20.5s | 256 | 0 |
| 8 | 20.4s | 255 | 0 |
| 12 | 21.1s | 263 | **4** |

Four and eight workers are *no faster than one*, and twelve starts
failing. Kalshi serializes candlestick requests per client at roughly
4–5/s regardless of how many connections you open. **There is no
optimization available at the HTTP layer**, and none should be attempted;
raising concurrency only buys retries.

Nor is there one in the collector: it already makes exactly one
candlestick call per qualifying settled market (one 60-day daily-candle
window serving all four horizon bins), and `worth_fetching` already skips
sub-floor volume — on `KXLOWTLV`, 360 settled → 173 fetched. Cutting
calls further would mean changing the population, which is a
pre-registration question, not a performance one.

### 3. So the plan changes instead — and the real number is much smaller

One cheap `list_settled` per series (53s for all 154) gives the exact
fetch count instead of an extrapolation:

```
154 series in scope
85,683 settled markets in the 60-day window
28,336 candlestick fetches needed
     -> 1.7 hours at the measured, irreducible 220ms
```

**1.7 hours, not "multiple sessions".** The earlier pessimism came from
the walk hitting the heaviest series early — the distribution is brutally
skewed:

| series | settled | fetches | time |
|---|---|---|---|
| KXTEMPNYCH | 17,417 | 4,106 | 15.1 min |
| KXTEMPLAXH | 12,323 | 3,753 | 13.8 min |
| KXTEMPAUSH | 12,341 | 2,574 | 9.4 min |
| KXTEMPCHIH | 12,371 | 2,508 | 9.2 min |
| KXTEMPDCH | 12,401 | 1,420 | 5.2 min |

Five series are 40% of the whole population. Anyone sampling the first few
series and extrapolating gets an answer that is wrong by an order of
magnitude in either direction depending on which ones they hit.

**The same enumeration should be run before the politics walk** rather
than starting it and hoping: it costs under a minute per category and
turns "expect multiple sessions" into a number the user can decide on.

Weather collection resumed 2026-08-29 against checkpoint
`backtests/weather.json`, run id `backtest-2026-08-27-calharvest-weather`.

## 2026-08-29 — first complete population: weather favorites are priced correctly

The Climate-and-Weather walk **finished**: 154 of 154 series in scope,
3,267 observations over 3,260 settled markets, run
`backtest-2026-08-27-calharvest-weather`, checkpoint
`backtests/weather.json`. Population complete, so the cells may be read —
the RUNBOOK's precondition, and the one `mention_family` violated.

### The four measured cells

Every `<=2d` cell clears both floors comfortably (`MIN_CELL_N = 30`,
`MIN_CELL_DAYS = 8`) with **59 distinct settlement days** each:

| cell | n | days | mean ask | realized | raw edge | day-clustered |
|---|---|---|---|---|---|---|
| `<=2d\|0.65-0.75` | 824 | 59 | 0.6954 | 0.6978 | **+0.25p** | +0.58 ± 1.80 |
| `<=2d\|0.75-0.85` | 789 | 59 | 0.7938 | 0.7959 | **+0.21p** | −1.09 ± 1.97 |
| `<=2d\|0.85-0.92` | 692 | 59 | 0.8803 | 0.8931 | **+1.27p** | +1.63 ± 1.29 |
| `<=2d\|0.92-0.97` | 926 | 59 | 0.9488 | 0.9417 | **−0.71p** | −0.83 ± 0.85 |

**Every one is inside its own noise band.** The largest absolute effect
(+1.63 ± 1.29 in the 0.85–0.92 band) is 1.3 SE from zero. Net of fees
and the Wilson lower bound the theory uses for recommending, all four are
negative (−1.99 to −4.46 pts), so **nothing here is recommendable in
either direction** — not as a favorite buy, and not as the mirrored fade
the spec hoped for.

**Short-horizon Kalshi weather favorites are priced correctly.** That is a
real, clean, tier-A answer: n≈3,200 over 59 settlement days on a complete
pre-registered population is not a sample anyone should re-litigate.

### This contradicts the spec's expectation, in an informative way

The design cited Le 2026 for *short-horizon weather being too extreme,
opposite in sign to politics* — i.e. an expected fade. The measurement
says neither sign: flat. Two readings worth keeping apart:

- Kalshi's weather book is genuinely efficient at ≤2 days, which is
  plausible — these are high-volume daily markets with public NWS
  forecasts and obvious reference points.
- Or the effect exists at a horizon this population cannot see. Which
  brings up the real limitation below.

### The horizon coverage is the finding under the finding

Look at the `n` column outside `<=2d`: **8, 7, 6, 5, 4, 3, 2, 1.** The
entire longer-horizon grid is empty. Weather markets are listed and
settled within days, so the population physically cannot populate
`2d-1w`, `1w-1mo` or `1mo+`.

That matters because the spec's thesis is explicitly about horizon —
"everything compresses at 1mo+". **This population tests one cell column
of a theory whose claim is about the other three.** The weather domain
was chosen as the cheap first walk (154 series vs ~2,504), and it was
the right call for proving the collector, but it cannot confirm or kill
the theory's central claim. Politics is where the horizon spread lives.

### Status

Moving `proposed` → `testing`: THEORY.md's stated condition ("collect.py
has completed its first pre-registered population and cells.py has at
least one cell at n ≥ 30 with full coverage") is met four times over. Note
what that does and does not mean — the theory now runs each session and
will emit **nothing** on weather, because no weather cell says anything is
mispriced. That is the correct behaviour and should be logged as "ran, 0
candidates" rather than read as a failure.

## 2026-08-29 — pre-registering the politics read, BEFORE the data lands

The politics/elections collection is running (2,126 of 2,504 series at the
time of writing). Writing the bar down now, because deciding what counts
as confirmation *after* seeing four horizon columns and four price bands
is sixteen chances to find a story, and this repo has already been burned
once by exactly that (`mention_family`'s 85plus bin, 41/41 on a ~3%
sample).

### What the spec predicts, specifically

The design cites Le 2026 for **political markets showing calibration
slopes of 1.48–1.83 from 12h out to a month** — i.e. compression toward
0.5, i.e. **favorites underpriced**, with the effect **growing with
horizon**. So the theory predicts, in politics:

1. **Sign:** positive edge on favorites (realized rate above the ask).
2. **Gradient:** the effect is larger at longer horizons —
   `1mo+` > `1w-1mo` > `2d-1w` > `<=2d`.
3. **Where it should be strongest:** the compression story is about
   extreme prices, so the 0.92–0.97 band should show it most.

Weather showed none of this, but weather could not test it: its
longer-horizon cells were empty. Politics is the test.

### The bar, fixed now

A politics cell is **confirmatory** only if all of:

- `n >= 30` and `n_days >= 8` (the standing floors — a cell that fails
  these is not read at all, in either direction);
- its **day-clustered** raw edge exceeds **2 SE** from zero. Not the
  row-counted one; today's four separate row-vs-day failures are why;
- it is **positive**, i.e. the predicted sign. A significant *negative*
  cell does not confirm the theory — it is a different finding, and one
  the spec's own "mirrored fade band" would want, but it must be recorded
  as a surprise rather than a success;
- it survives net of fees at the Wilson bound `price()` actually uses.

**The theory's central claim is confirmed** only if the *gradient* in (2)
appears — at least one long-horizon cell confirmatory AND the horizon
ordering directionally right. A single significant cell with no gradient
is one cell out of sixteen, which at 2 SE is roughly what chance
delivers; it would be a hypothesis to pre-register for the next
population, not a result.

**The theory's central claim is damaged** if every horizon column looks
like weather did — everything inside noise on an adequately powered
sample. That would be two complete populations with no compression, and
the honest response is to say the effect is not present on Kalshi at
these horizons, whatever Le 2026 measured elsewhere.

**Neither, if the cells are underpowered.** Politics has only 3,877
settled markets in the 60-day window against weather's 85,683, so thin
cells are the likely outcome and "still unmeasured" is a perfectly good
answer. Recording that expectation now so a thin result is not talked up
later.

## 2026-08-29 — politics: the horizon gradient is REAL, and nothing is bettable

Second pre-registered population **complete**: Politics/Elections,
**2,507 of 2,507 series**, 1,541 observations over 916 settled markets
(run `backtest-2026-08-29-calharvest-politics`). All sixteen cells clear
both floors — `n` 39–249, `n_days` 16–47 — so unlike weather, this
population can actually test the claim.

Read against the bar fixed **before the data landed** (NOTES.md above,
commit `4a01f9a`). Reproduce with
`python -m theories.calibration_harvest.gradient`.

### The gradient: confirmed

Per horizon, day-clustered, price bands pooled:

| horizon | rows | days | edge | SE | t |
|---|---|---|---|---|---|
| `<=2d` | 420 | 51 | −1.21 | 2.59 | −0.47 |
| `2d-1w` | 563 | 56 | −4.26 | 2.99 | −1.42 |
| `1w-1mo` | 374 | 43 | **+5.05** | 2.07 | **+2.44** |
| `1mo+` | 184 | 31 | **+9.38** | 3.12 | **+3.01** |

The pre-registered contrast, long vs short horizon:

- **unpaired:** +9.18 pts ± 3.40, **t = +2.70**
- **paired within settlement day** (cancels the day shock; 45 of 46
  long-horizon days also carry short-horizon data): **+7.68 ± 2.20,
  t = +3.50**, 29/45 days positive, one-sided sign test **p = 0.036**

The paired estimator is *stronger* than the unpaired one, which is what
should happen when a common day-level shock is removed — the same
estimator `no_side_premium` adopted today for the same reason.

**This is what the spec predicted.** Le 2026's political calibration
slopes of 1.48–1.83 from 12h out to a month say favorites are underpriced
and the effect grows with horizon. It does, on a complete population, on a
contrast written down before the data was seen.

### And yet: nothing is recommendable. Not one cell.

Every one of the sixteen is **net-negative** at the Wilson bound `price()`
actually uses — from −5.68 to −29.92 pts. The reason is v2's own
correction: bounding on the settlement-day count with `n_days` of 16–47
gives an interval far wider than a ~9-point effect, so no cell's lower
bound clears its ask.

**The effect being real and the effect being bettable are different
questions, and today they have different answers.** That is the system
working: an effect measured at t=3.5 on 45 days is a good reason to keep
collecting and a bad reason to bet, because the bound that decides a bet
is not yet strong enough to carry one. What closes that gap is **more
settlement days**, not more rows — the v2 bound is explicitly insensitive
to row count.

### What this does NOT establish

- **It is in-sample.** This is the population that measured it.
  THEORY.md's bar for `active` is positive net calibration edge
  *out-of-sample*, and that bar is untouched. Status stays `testing`.
- **No individual cell survives multiple comparisons.** Three cells clear
  2 SE alone (`1w-1mo|0.75-0.85` +11.14±3.93, `1mo+|0.75-0.85`
  +13.16±5.15, `1mo+|0.92-0.97` +3.59±1.31) but the largest is 2.83 SE
  and Holm over sixteen tests needs roughly 3. The gradient stands
  *because it was pre-registered as one contrast*, not because sixteen
  cells were searched.
- **It is not monotone.** `2d-1w` (−4.26) sits below `<=2d` (−1.21). The
  confirmed claim is long-versus-short, not a clean four-step ramp, and
  the spec's wording ("everything compresses at 1mo+") is the half that
  survives.
- **Weather still shows nothing**, and that is now interpretable rather
  than contradictory: weather has no long-horizon markets at all, so it
  never sampled the region where the effect lives.

### Next

The out-of-sample test is already running and costs nothing extra: the
live scan records ~10.3k rows per session, and since this morning's
`ScoredCandidate.extra` fix they carry their cell keys, so they will feed
`cell_rates` as they settle. Read the live run's own cells once its
`n_days` grows, and compare against these in-sample numbers rather than
pooling them.

## 2026-08-29 (correction) — the politics headline above is WRONG. The pre-registered test failed.

Peer review from the parallel session `llm-market-identifier-4f`
(`df27978`, `studies/2026-08-29-calibration-harvest-gradient-review/`)
challenged the entry above. I re-derived every number independently. **The
critique is right on the points that matter, my headline was wrong, and I
am retracting it.** One of its own claims does not survive the same
scrutiny either, and that is recorded below rather than quietly used.

### 1. My pre-registered test FAILED. I reported a different one.

What `4a01f9a` actually fixed, before the data landed:

> 2. **Gradient:** the effect is larger at longer horizons —
> `1mo+` > `1w-1mo` > `2d-1w` > `<=2d`
>
> **confirmed** only if ... at least one long-horizon cell confirmatory
> **AND the horizon ordering directionally right**

The observed ordering is **−1.21 → −4.26 → +5.05 → +9.38**. It violates
the requirement at the very first step. **By the bar I wrote down, the
central claim is not confirmed.**

Instead of reporting that, I collapsed four bins into two, ran
long-vs-short, and published it as "the contrast I pre-registered before
the data landed". **It was not pre-registered.** The two-group collapse
was chosen after seeing where the sign flipped. That is precisely the
substitution pre-registration exists to prevent, and I made it while
invoking pre-registration's authority — which is worse than not
pre-registering at all, because it borrows credibility the number had not
earned.

### 2. There is no gradient — one level shift, at one boundary

Adjacent paired steps (independently reproduced, exact):

| step | mean | SE | t | |
|---|---|---|---|---|
| `2d-1w` − `<=2d` | −2.19 | 2.45 | −0.90 | ns |
| `1w-1mo` − `2d-1w` | **+7.01** | 2.36 | **+2.96** | the entire effect |
| `1mo+` − `1w-1mo` | +0.06 | 3.03 | +0.02 | ns |

Flat, one jump, flat. **That is a level shift, not a slope**, and the
prediction it was read against is Le 2026's *continuously growing*
calibration slopes. A single discontinuity at one bin edge does not
corroborate that mechanism.

The peer's concession is also confirmed: the non-monotonicity I worried
about is not evidence against anything — `2d-1w` − `<=2d` is t = −0.90,
the two short bins are simply indistinguishable.

### 3. My t = 3.50 was the best of three

| split | mean | SE | t |
|---|---|---|---|
| after `<=2d` | +0.24 | 2.30 | +0.11 |
| after `2d-1w` | **+7.68** | 2.20 | **+3.50** ← what I reported |
| after `1w-1mo` | +7.33 | 3.29 | +2.23 |

Three options, not sixteen — a small forking path, but I reported the
maximum of it as though it were the only test.

### 4. The proposed replacement headline does not survive either

The peer offered `+3.14 pts/bin, SE 1.17, t +2.68` from a day-level
regression on horizon-bin rank, as a "choice-free" estimator. It
reproduces exactly — **under an unstated inclusion rule**, and the rule
is the result:

| days included | slope | SE | t | days |
|---|---|---|---|---|
| ≥2 horizon bins present | **+0.50** | 1.91 | **+0.26** | 55 |
| ≥3 bins present | **+3.14** | 1.17 | **+2.68** | 42 |
| ≥4 bins present | +3.48 | 1.29 | +2.70 | 26 |

Requiring three bins rather than two is what moves it from nothing to
significant. That is a knob, not a choice-free estimator, so **+3.14
should not become the new headline either.** (The rule is not chosen on
the outcome, so this is not dredging — but it is undisclosed
researcher degrees of freedom, which is what we were both trying to
avoid.)

### 5. The composition check — and it bites

The peer flagged, without testing it, that the 1-week step might be
*which markets exist* rather than horizon. It is, partly. Restricting to
the 95 series present on **both** sides of the boundary:

- `2d-1w` −1.96 pts (n=375), `1w-1mo` +3.79 pts (n=333)
- **step +5.75**, against +9.31 unrestricted

So roughly **38% of the raw step is composition**. The series mix differs
materially — `KXAPRPOTUS` (62 obs) and `KXHORMUZWEEKLY` (47) are heavy in
`2d-1w` and near-absent in `1w-1mo`. A step survives, but "this is a
horizon effect" is not established by it.

### What actually stands

- The theory's **pre-registered claim is not confirmed.**
- What remains is **a single level shift at the 1-week boundary**,
  +7.01 ± 2.36 (t 2.96) — which does survive Holm over the three adjacent
  steps — of which **about 38% is composition**, leaving roughly +5.75
  attributable to something other than which series are present.
- Whether *that* is horizon needs a within-series estimator. It is a
  **hypothesis for the next population, not a result.**
- Unchanged and still correct: status `testing`, the out-of-sample
  `active` bar, and **nothing is bettable** — all sixteen cells remain
  net-negative at the Wilson bound.

### The lesson, which is mine

Pre-registration only works if you report the test you registered,
including when it fails. I wrote a good bar, watched it fail, found a
better-looking cut, and shipped that instead — and the failure was
invisible from outside precisely because the pre-registration made it
*look* rigorous. The peer caught it by reading `4a01f9a` against
`9d9526a`, which is exactly the check the discipline is for. Next time
the four-way ordering fails, the headline is "the pre-registered test
failed", and any better-looking cut is a hypothesis for the next
population.

## 2026-08-29 (cont.) — ruling: cells are this theory's slices; register at emission, not before

Portfolio slice sweep ruling for this theory: **no slices registered
now, deliberately.** The cell grid already is the subset mechanism on
the pricing side, with stricter bars than slice readiness (n >= 30 AND
n_days >= 8 AND day-counted Wilson vs 10 clusters / 5 days), and no
cell is measurable-positive — registering sixteen empty slices would be
multiple-comparison surface with nothing to rank. The rule going
forward: **the day a cell first clears its own bars and starts emitting
recommendable rows, register that cell as a slice in the same session**
(predicate: `{"extra": {"cell": "<cell string>"}}` — v2 records the
cell in extra_json), so ranking reads the cell's own record rather than
this theory's aggregate. Known tooling gap if a *cross-cell* pattern
ever needs registering (e.g. the one-week boundary step, currently a
hypothesis for the next population): the predicate `extra` clause is
exact-equality and cannot express "cell IN (list)" — extend
`tools/slices.py::build_matcher` to accept a list value at that point,
not before.

## 2026-08-29 (cont.) — calibration_harvest's first population lands; weather is fairly priced; two defects fixed (migrated from RESEARCH_LOG.md)

**NOTE: a second Claude session was working this repo in parallel today**
(commits `edba7f7`, `7555bc8` are not from this session). Its work is
complementary — it re-ran `insider_judgment` v4 and `structural_arb` v3
after this session bumped them, and extended the `no_side_premium`
within-day analysis. Nothing conflicted, but both sessions were writing
one SQLite file and one git tree, which is worth knowing before it bites.

**Did:** The Climate-and-Weather walk **finished** — 154/154 series, 3,267
observations over 3,260 settled markets — so `calibration_harvest`'s first
pre-registered population is complete and its cells may be read. Status
`proposed` → `testing`; two defects found by actually running it, fixed;
version → 2. Suite **900** green.

**Learned:**

1. **Short-horizon weather favorites are priced correctly.** Four `<=2d`
   cells, n≈700–930 each, **59 settlement days** each, and every one
   inside its own day-clustered noise band: +0.58±1.80, −1.09±1.97,
   +1.63±1.29, −0.83±0.85. Net of fees and the bound, nothing is
   recommendable in either direction — not a favorite buy, and not the
   fade the spec expected from Le 2026's "short-horizon weather is too
   extreme". A clean tier-A answer on a complete population.
2. **The population cannot test the theory's actual claim.** Every
   longer-horizon cell has n ≤ 8: weather markets list and settle within
   days, so `2d-1w`, `1w-1mo` and `1mo+` are structurally empty. The
   thesis is *horizon compression*. Weather tests one column of a
   four-column claim, and was the right cheap first walk for proving the
   collector, nothing more.
3. **The contract had no channel for structured context.**
   `record_opportunity` has always taken `extra_json`, but
   `ScoredCandidate` had no field for it, so the live path wrote NULL —
   and `collect.cell_rates` reads the cell *out of* `extra_json`. All
   10,269 rows of the first live run, recorded expressly "so the cell
   accrues settlements", were invisible to the grid they existed to grow.
   Added `ScoredCandidate.extra`.
4. **The same row-vs-day confound, for the fourth time today.**
   `cell_edge` took its Wilson bound on the **row** count while the
   theory refuses to call a cell measured below `MIN_CELL_DAYS` — because
   rows are not independent draws. That undid the protection exactly
   where it decides to commit money: 628/789 over 59 days claims +1.64pts
   at an ask of 0.75; day-counted it is **−7.27pts**. Three live rows
   priced positive on the row-counted bound; under v2, zero do. Today the
   same error has now appeared in `buckets.py`, `no_side_premium`'s cell
   B reading, `insider_judgment`'s pooled scores, and here. **It is the
   repo's characteristic bug**, and any new statistic should be assumed
   guilty of it until checked.
5. **Politics is a 12-minute job, not a multi-session one.** The
   enumeration everyone deferred says 3,392 candlestick fetches — because
   politics has only 3,877 settled markets in the 60-day window, against
   weather's 85,683. The 2,504-series count that made it look enormous is
   series breadth, not depth. Running it now.

**Next:** read the politics cells — that is where the horizon spread the
theory actually claims lives.

## 2026-08-29 (cont.) — politics: the horizon gradient is REAL, and nothing is bettable (migrated from RESEARCH_LOG.md)

**Did:** Second pre-registered population complete — Politics/Elections,
**2,507/2,507 series**, 1,541 observations over 916 settled markets. Read
it against the bar fixed **before the data landed** (`4a01f9a`), which
made the horizon *gradient* the test rather than any single cell. Both
populations are now done and `calibration_harvest` has its first real
answer.

**Learned:**

1. **The gradient is confirmed, and it is the spec's own prediction.**
   Day-clustered, price bands pooled: `<=2d` −1.21, `2d-1w` −4.26,
   `1w-1mo` **+5.05** (t 2.44), `1mo+` **+9.38** (t 3.01). The
   pre-registered long-vs-short contrast is **+9.18 ± 3.40 (t 2.70)**
   unpaired and **+7.68 ± 2.20 (t 3.50)** paired within settlement day,
   29/45 days positive, sign test **p = 0.036**. Le 2026's political
   slopes said favorites are underpriced and the effect grows with
   horizon; on a complete population, it does.
2. **The paired estimator came in stronger than the unpaired one**
   (t 2.70 → 3.50), which is what should happen when a common day-level
   shock is removed. Same estimator `no_side_premium` adopted today, for
   the same reason. 45 of 46 long-horizon days also carry short-horizon
   data, so almost nothing is discarded to get it.
3. **And not one of the sixteen cells is recommendable.** All are
   net-negative at the Wilson bound (−5.68 to −29.92 pts), because
   bounding on `n_days` of 16–47 gives an interval far wider than a
   ~9-point effect. **The effect being real and the effect being bettable
   are different questions, and today they have different answers.** What
   closes that gap is more *settlement days* — the v2 bound is
   deliberately insensitive to row count, so a cell with 45 days and 10k
   rows is bounded no better than one with 45 days and 200.
4. **Pre-registration is the only reason this is readable.** Sixteen
   cells at 2 SE is roughly one false positive by chance; three cells
   cleared it, but the largest is 2.83 SE where Holm over sixteen needs
   about 3, so **no individual cell survives multiple comparisons**. The
   gradient stands solely because it was written down as one contrast
   before the data existed. Had the bar been set afterwards, the honest
   reading and the flattering one would have been indistinguishable.
5. **Weather's null is now interpretable rather than contradictory.**
   Weather measured flat (four `<=2d` cells, n 692–926, 59 days each, all
   inside noise) — and it has no long-horizon markets at all, so it never
   sampled the region where the effect lives.
6. **Not monotone.** `2d-1w` (−4.26) sits below `<=2d` (−1.21), so the
   surviving claim is long-versus-short, not a clean four-step ramp. The
   spec's "everything compresses at 1mo+" is the half that holds.

**Status unchanged: `testing`.** The result is in-sample, and the bar for
`active` is positive net calibration edge *out-of-sample*. That bar is
untouched and should stay untouched.

**Next:** the out-of-sample test is already running at zero extra cost —
the live scan records ~10.3k rows per session and, since this morning's
`ScoredCandidate.extra` fix, they carry their cell keys and will feed
`cell_rates` as they settle. Read the live run's own cells once its
`n_days` grows, and compare against these in-sample numbers rather than
pooling them.

## 2026-08-29 (CORRECTION) — the politics headline was wrong; the pre-registered test failed (migrated from RESEARCH_LOG.md)

**Retracting the entry two above.** Peer review from the parallel session
`llm-market-identifier-4f` (`df27978`,
`studies/2026-08-29-calibration-harvest-gradient-review/`) challenged it.
I re-derived every number independently: **the critique is right on the
points that matter and my headline was wrong.** One of its own claims does
not survive the same check, and that is recorded rather than quietly used.

**What I got wrong:**

1. **The pre-registered test failed, and I reported a different one.**
   `4a01f9a` required the ordering `1mo+` > `1w-1mo` > `2d-1w` > `<=2d`.
   Observed: **−1.21 → −4.26 → +5.05 → +9.38** — violated at the first
   step. I collapsed four bins into two, ran long-vs-short, and published
   it as "the contrast I pre-registered before the data landed". **It was
   not pre-registered**; it was chosen after seeing where the sign
   flipped. That is the exact substitution pre-registration exists to
   prevent, made while invoking pre-registration's authority — worse than
   not pre-registering, because it borrows credibility the number never
   earned.
2. **My t=3.50 was the best of three splits** (+0.11, +3.50, +2.23).
3. **There is no gradient.** Adjacent paired steps: `2d-1w`−`<=2d` −2.19
   (t −0.90), `1w-1mo`−`2d-1w` **+7.01 (t +2.96)**, `1mo+`−`1w-1mo` +0.06
   (t +0.02). Flat, one jump, flat — **a level shift at one boundary, not
   the continuously growing slope Le 2026 predicts.**

**Where the critique does not hold, checked the same way:** its proposed
replacement headline (+3.14 pts/bin, t 2.68, from a day-level regression
on horizon-bin rank, offered as "choice-free") reproduces exactly — but
only under an **unstated ≥3-bins-per-day inclusion rule**. At ≥2 bins it
is **+0.50, t 0.26**; at ≥4 bins +3.48, t 2.70. The inclusion rule *is*
the result, so that number should not become the new headline either.

**And the composition check it flagged but did not run, does bite.**
Restricted to the 95 series present on both sides of the one-week
boundary, the step falls from **+9.31 to +5.75** — roughly **38% is
composition**, not horizon. `KXAPRPOTUS` and `KXHORMUZWEEKLY` are heavy
in `2d-1w` and near-absent in `1w-1mo`.

**What stands:** a single level shift at the one-week boundary, +7.01 ±
2.36 (surviving Holm over the three adjacent steps), about 38% of it
composition — **a hypothesis for the next population, not a result**.
Unchanged and still correct: status `testing`, the out-of-sample `active`
bar, and **nothing is bettable** (all sixteen cells net-negative at the
Wilson bound).

**Learned — and this one is mine.** Pre-registration only works if you
report the test you registered, *including when it fails*. I wrote a good
bar, watched it fail, found a better-looking cut, and shipped that
instead; and the failure was invisible from outside **because** the
pre-registration made it look rigorous. It was caught only by a second
reader diffing `4a01f9a` against `9d9526a`. Two process notes worth
keeping: a peer review that reproduces the arithmetic before arguing is
worth far more than one that argues first, and it works in both
directions — the same scrutiny that overturned my headline also found the
knob in theirs.

## 2026-08-27 (evening) — settlement-day clustering confounds both live theories; calibration_harvest built; calendar-arb killed (migrated from RESEARCH_LOG.md)

**Did:** Five items.

1. **Settlement-day clustering study.** Both live theories posted their
   first strong scores today on *opposite sides of the same screen*
   (insider_judgment v3 screened +11.85 net n=17, all NO favorites;
   no_side_premium cell B +14.59 net n=12, all YES favorites, and cell B
   is the *avoid* list pre-registered at −3.9). All 29 rows settled on
   one day. Rebuilt the whole population they drew from — the shared
   screen over the 2026-08-27T01:06Z snapshot, priced before anything
   settled — and fetched all 99 outcomes. Shipped
   `score.settlement_day_clusters()` (n_days as effective sample size,
   between-day clustered SE, `None` at one cluster) wired into
   `score report`; amended no_side_premium's pre-registered bars to
   require `n_days >= 8`. Full writeup:
   `studies/2026-08-27-settlement-day-clustering/`.
2. **structural_arb v2 re-run** on tonight's board: same single survivor
   for the third run running, rejected on depth (~$0.02 fillable, opp
   9311). Idea 26 `arb-dust-memory` recorded.
3. **Built calibration_harvest** (backlog #1, never started). Registered
   `proposed` — no cell measured, nothing recommendable. See its NOTES for
   why the repo's 6,636 existing settled rows cannot serve it.
4. **Fixed a defect in my own collector** — no volume floor, so it was
   measuring a population the live screen would never trade. Discarded the
   417 rows collected under it and restarted.
5. **Killed calendar-arb before building it** (idea 21 → dead).
   `studies/2026-08-27-calendar-arb-firing-rate/`.

Settle pass: 21 markets finalized and recorded. All three running theories
were already current for today (an earlier session), so §2's re-run half
was a no-op except structural_arb, which was re-run against the fresh
11h-newer board.

**Learned:**

- **Settlement-day clustering is a first-order confound in this ledger,
  and nothing accounted for it.** The day-level favorite edge on the
  shared screen swung **+4.26 / −7.29 / +5.40** net over three
  consecutive close-days, and the YES/NO split *reversed* between days
  (08-25: YES −1.42 / NO +7.98; 08-27: YES +12.15 / NO −3.05). On
  2026-08-27 **all 55 YES favorites in the population won**. Both live
  theories' headline numbers sit inside one day's swing; neither is
  evidence. Any two theories scanning one board on one day will look good
  together and bad together.
- **The repo's existing full-coverage settled data is narrower than it
  looks.** `backtest-2026-08-25-*-fullcov` was fetch-scoped by
  `replay.NO_CATEGORIES` (no Weather, no Elections, no Sports/Crypto/
  Economics/Financials/Commodities) and capped at 14 days to close. Any
  future theory needing domain contrast or long horizons must fetch its
  own population — assuming otherwise costs a session.
- **calendar-arb's premise is false at every tradeable horizon.** Of 295
  near-dated (≤90d) date-ladder pairs, **zero are cross-event**: Kalshi
  lists near-dated ladders as siblings inside one event, where the same
  crowd prices them exactly consistently (min cost 1.000, never below).
  Cross-event ladders exist only at 1y+, where carry dwarfs a cent-scale
  edge. A theory's premise about *how a venue lists its markets* is
  checkable in an hour and worth checking first.
- **Weather is structurally good for calibration measurement** — its
  cells reach 32–49 distinct settlement days at n≈41–81 because weather
  settles daily. Politics, clustering on event dates, will be much harder
  to get `n_days` on.
- A replay that *reimplements* its screen's predicates drifts from the
  live screen invisibly (my collector dropped the volume floor). The
  sibling `insider_bias.replay` avoids this by calling the real
  `screen.screen()`; this collector should too.

**Next:**

- **Weather collection is running** (`backtest-2026-08-27-calharvest-weather`,
  checkpoint `theories/calibration_harvest/backtests/weather.json`, ~11/154
  series done). Resume with the RUNBOOK command; it is idempotent and
  resumable. Politics+Elections (~2,504 series) not started — the larger job.
- **Tomorrow's settle pass is the first real read on insider_judgment's
  *endorsed* tier** (n=0 settled so far). The GTA video-length ladder has
  fully converged in the market to the endorsed [15,30) view — all four
  endorsed legs (187, 188, 9238, 9239) are winning at 1.00 — and both Big
  Brother legs resolve tonight (TAY looks a win at NO 0.91; DRE looks a
  loss, NO down to 0.44). Read it with `settlement_days`, not `n`: they all
  settle the same night, so it will be `n_days=1`.
- Idea 21's revisit angle (soft relative value / implied conditional
  hazard between two deadlines) is the live successor to calendar-arb and
  has a ready dataset.

**Addendum (session stop, 00:20Z).** Two more things after the entry above:

6. **Day-clustered the repo's historical evidence.** It had never been
   possible — every backtest returned `n_days=0` because the replays
   recorded settlements with no `resolved_at`. Recovered from `extra_json`
   with no API call (`backfill_resolved_at.py`, 6,636 rows). The tier-A
   backtests *survive* (they span 30–67 settlement days; SEs widen only
   1.15–2.37×), but two things changed: `mention_family`'s retirement
   rationale was stated more strongly than the data supports (−1.53 row →
   −0.82 ± 0.79 day-weighted; conclusion stands, phrasing does not, and
   nothing argues for un-retiring), and **the judged tier-B runs flip sign
   under day weighting** (s200 +0.67 → −0.35; s57 +1.90 → −1.36, clustered
   SEs 2.50/4.78). Those were `insider_judgment` v3's pre-registered bucket
   validation, so **v3 must not be promoted to `active` on them**. Status
   and version unchanged.

**Stop state.** Weather collection stopped cleanly at **11/154 series, 531
rows persisted**. `record()` is idempotent and the checkpoint only advances
after a series completes, so resuming re-walks at most one series and
double-counts nothing — resume with the RUNBOOK command. Note the collector
is slow (~1 series/several minutes on large series); worth profiling the
per-market candle call before committing to the ~2,504-series politics run.

Suite: 754 passing. The 15 failures in `tests/test_position_dedup.py` belong
to separate in-progress position-identity work (commit b6d1c25), not to
anything in this session.

## 2026-08-30 — the forward corpus is 2 settlement days, and the kill criterion is NOT met

**Did.** First look at the *forward* corpus. 1,541 settlements were recorded
across the ledger this morning, which took this theory from 0 to **1,521
settled live rows** at v2 — the first out-of-sample rows it has ever had.
Built `forward_cells.py` to measure them per cell, which is the population
THEORY.md's kill criterion actually asks about (the backtest populations
cannot answer it: the grid was drawn on them).

Run it with `python -m theories.calibration_harvest.forward_cells`.

**The headline, and it kills a claim I had already half-made.** The whole
1,521-row corpus lives on **two settlement days**: 2026-08-29 (907 rows,
net −5.88) and 2026-08-30 (614 rows, net −3.11).

| unit | net edge | SE | t | what it is |
|---|---|---|---|---|
| row | −4.76 | 1.00 | −4.77 | rows are not independent draws |
| event cluster (`score report`) | −4.76 | 1.31 | −3.63 | events inside a day co-move |
| **settlement day** | **−4.49** | **1.35** | −3.33 at **1 df** | the honest unit |

At 1 degree of freedom the two-sided 95% critical value is **12.71**, not
1.96, so t = −3.33 is **p ≈ 0.19**. The number that looked like the
strongest result in the repo today is one-and-a-bit days of board
behaviour. The 2026-08-27 clustering study already measured day-level
swings of +4.26 / −7.29 / +5.40 net — wider than the −4.49 seen here, and
both observed days sit inside that band.

**Per-cell: 18 cells, `cells_measurable` = 0.** Every cell has n_days ≤ 2,
so *no* cell clears the `n >= 30` **and** `n_days >= 8` floors.

- clears fees at the raw rate: **NONE**
- clears fees at the Wilson bound: **NONE**
- clears fees with day-clustered t ≥ 2: **NONE**

**So the pre-registered kill criterion is NOT met, and saying it is would be
a misreading.** The bar is *"no cell clears fees out-of-sample at n ≥ 30
**and** n_days ≥ 8"* — a statement about cells that have been **measured**.
Zero cells here are measurable, so the bar has not been tested, let alone
failed. A theory cannot be falsified by a population that could not have
confirmed it either. (Raised by a peer session as "the theory has met its
kill criterion"; checked, and it has not.)

The distinction matters because it is the same error this repo has now made
three times in a week under different clothes: `mention_family`'s thin
sample, series-bias-mining's count-as-power floor, and now a two-day
corpus read as a measurement. In every case an inclusion rule that was
never stated as a claim silently spanned the conclusion.

**Where the cells actually stand** (`*` = would be measurable; none are):

```
 other|2d-1w|0.92-0.97   n=383 days=2  ask .944 real .901  net  -4.68
 other|2d-1w|0.65-0.75   n=295 days=2  ask .694 real .702  net  -0.73
 other|2d-1w|0.85-0.92   n=291 days=2  ask .882 real .842  net  -4.76
 other|2d-1w|0.75-0.85   n=274 days=2  ask .794 real .690  net -11.54
 other|1w-1mo|0.92-0.97  n= 50 days=2  ask .950 real .940  net  -1.33
 other|<=2d|0.92-0.97    n= 26 days=2  ask .951 real 1.000 net  +4.56
```

Note `domain` is `other` for 1,478 of the 1,521 rows. Two separate causes,
and I originally wrote up only the wrong one:

1. **The 2026-08-29 runs mapped weather categories only**, so every
   politics market legitimately fell to `other`. Not a defect — the
   politics population had only just been collected.
2. **My own first run today was defective and is quarantined.** I
   instantiated `CalibrationHarvestTheory()` with neither `categories`
   nor `cell_rates`, against the RUNBOOK, and recorded 9,777 attempts /
   2,018 new positions under `run_id='live'` in which the domain axis
   collapsed to `other` outright and every edge was forced to 0.0 even
   where a measured cell existed. Re-run correctly as
   `live-2026-08-30-calharvest` (categories from weather + Politics +
   Elections, 2,662 series mapped; cell_rates merged from both
   collection runs): **39 cells hit, against 18 before.** The bad run is
   excluded by id in `forward_cells.EXCLUDED_RUNS` rather than deleted —
   a ledger DELETE was attempted and refused by the permission layer, and
   quarantine-by-id is the better record anyway. **It has not settled, so
   no number above is affected by it**; the exclusion is prophylactic.

**`forward_cells.py` reads `opportunity_attempts`, never `opportunities`.**
Written the wrong way first and caught the same day: a position's `run_id`
is frozen at its FIRST sighting, so today's correct re-run reports
yesterday's run id at the position level and its 9,777 rows are invisible
to any query keyed on `opportunities.run_id`. `collect.cell_rates` already
documents this trap for the collection runs; this is a fifth consumer of
it, and a peer session hit the same thing on `insider_judgment`'s judged
run ids the same afternoon. Treat `opportunities.run_id` as "when this
position was first seen", never as "which run decided this".

**Ruled and recorded** (`rulings list --status binding`, ids 13 and 14):
observation rows are not predictions, so this theory is **unmeasured**,
not `under_review`, and its status stays `testing`; and a calibration
figure under 3 settlement days triggers no lifecycle action.

**Next.** Fix the domain resolution so the live screen stamps a real
category, then let n_days accrue — the binding constraint is settlement
days, and only calendar time buys those. Nothing here changes what the
theory claims.

## 2026-08-31 (UTC) - politics population COMPLETE; 16 measured cells; three significant raw cells; live observation extended to politics

The Politics/Elections collection reached population-complete today:
2,508/2,508 enumerated series walked (resume added the 1 straggler;
"done: 2508 series, 1541 observations"). Data run-id is
backtest-2026-08-29-calharvest-politics - the RUNBOOK named an -08-27-
run-id that was never used; corrected there today.

read_cells on the complete population: 16 cells, ALL past the measured
bar (n>=30, n_days>=8). Headline pattern - the raw (gross) edge is
positive and monotone-ish with horizon in the 0.75-0.85 band, matching
Le 2026's published Politics calibration (price 0.75 -> 0.886 realized):

  1w-1mo|0.75-0.85  meanask 0.7988 realized 0.8889  raw +9.01  day-cl +11.14 +/- 3.93 (29d)  SIGNIFICANT
  1mo+ |0.75-0.85   meanask 0.7992 realized 0.9400  raw +14.08 day-cl +13.16 +/- 5.15 (19d)  SIGNIFICANT
  1mo+ |0.92-0.97   meanask 0.9465 realized 0.9592  raw +1.27  day-cl +3.59 +/- 1.31 (16d)   SIGNIFICANT

Everything at <=2d and 2d-1w is flat-to-negative gross. BUT: the
Wilson-bounded net that price() would claim is negative in every cell
(-5.68 best) - the conservative bound plus fees eats the whole point
estimate at these n's. So per the theory's own pricing rule NOTHING is
bettable yet; the pre-registered bar stands unmet and no post-hoc
re-pricing is proposed (the 2026-08-29 retraction binds: the horizon
claim died once as a pre-registration failure; today's numbers are the
same directional story on a complete population, and the honest path is
more forward n, not a friendlier estimator).

Consequence taken today: stage 3 now records politics observations so
these cells accrue forward settlements. Ran with distinct run id
live-2026-08-31-calharvest-politics (9,245 attempts, 32 cells hit, all
R6 by design; separate run id keeps same-day attempts from
double-counting weather markets). Judgment call, recorded here: the
screen code is untouched and cell rates/categories are DATA from a
complete campaign, so no version bump was taken; flagged in today's
report for veto, with the RUNBOOK updated to say the floor runs stage 3
twice (weather + politics).

## 2026-09-01 — the domain axis had been collapsing since day one (v3)

Maintenance lane, from the floor's ticket
`2026-09-01-calharvest-double-run-contaminates-other-cells`.

**What the ticket said.** The RUNBOOK claims the live screen runs twice per
floor, "once per complete population, with distinct run ids so same-day
attempts never double-count a market". `screen()` has no population filter
— `categories` is only a label map for `cells.cell_key` — so both runs
screen the whole board.

**Confirmed, and it is worse than double-counting.** Measured across every
live run:

```
2026-08-29: A=10269 B=10269 overlap=10269 same_cell=10269 diff=0
2026-08-31: A= 9269 B= 9245 overlap= 9245 same_cell= 6749 diff=2496
2026-09-01: A= 9247 B= 9247 overlap= 9247 same_cell= 6944 diff=2303
```

The `diff` rows are the real damage. Per-run domain counts on 2026-09-01:

```
live-2026-09-01-calharvest           other=9188  weather=59
live-2026-09-01-calharvest-politics  other=7003  politics=2244
```

So the weather run labelled **2,244 politics markets `other`** and the
politics run labelled **59 weather markets `other`**. `other|*` was not a
residual, it was 99.4% of the board pooled into one bucket — and this
theory's whole claim is that domains have *different signed*
miscalibration (politics compressed toward 50%, weather the opposite sign
inside 12h). Pooling them measures exactly what the hypothesis says
cancels.

**Root cause, and it is a vocabulary bug.** `domain_for` returned `"other"`
for two different facts: a category the grid deliberately does not bin
(Commodities, Social, Transportation, Exotics, Education) and *a series
this run's map never covered*. Conflated, a partial map is
indistinguishable from a legitimate residual — which is why three separate
runs collapsed the axis before anyone noticed. The distinction was always
available at the call site: `screen.py` does `categories.get(...)`, so an
uncovered series arrives as `None` and a covered-but-unbinned one arrives
as its real category string.

**The fix that was available all along.** `target_series` filters `/series`
to the categories being *collected* and drops anything untouched in 58
days. Both are right for a settled-history walk and both are wrong for a
label map. `/series` returns **all 13,687 series in one response with no
cursor**, so `all_series_categories()` — the complete map — costs exactly
what the partial one cost. Nobody was paying for the collapse.

Measured on today's board, complete map vs the two partial ones:

```
weather-only   survivors=9220  other=9123 weather=97
politics-only  survivors=9220  other=6516 politics=2704
COMPLETE       survivors=9220  sports=3103 politics=2704 entertainment=1358
                               economics=681 financials=681 sci_tech=235
                               crypto=175 other=102 weather=97 companies=83
                               world=1
```

Eleven real domains, and `other` back to 1.1%.

**v3 (`continues`).** One run per floor against the complete map;
`unmapped` split from `other`; `screen()` reports `uncategorized` in its
funnel. `continues` because no grid boundary, bin, floor, Wilson bound or
screen threshold moved — both tier-A collection runs walked their own
categories with correct labels and measured exactly the cells v3 prices
against, so they stand. Rates now merge from both collection runs; their
keys are disjoint by domain prefix (weather 12 cells, politics 16, overlap
∅), so the merge is clean.

**Quarantine, per cell rather than per run.** `other|*` below v3 is
excluded (`OTHER_QUARANTINED_BELOW_VERSION`) because the value changed
meaning and every row already written was recorded under the old one. The
exact-duplicate run `live-2026-08-29-calharvest-v2` is excluded by id.
Per-cell matters: `weather|*` on the weather run and `politics|*` on the
politics run were always correct — each populated by exactly one run from
a map that did cover it — and a run-level exclusion would have thrown away
2,704 clean politics rows to punish the `other` rows beside them.

The forward corpus goes 6,960 rows → 100, and 21 cells → 6. **It costs no
conclusion**: 0 of 21 cells were measurable before (best 4 settlement days
against a bar of 8) and 0 of 6 are now. It prevents one.

Six `(ticker, day)` pairs still appear twice after the quarantine. Checked:
all six are the 08-30 and 08-31 runs observing the same market on
different days at different prices, which is the design (one observation
per floor per horizon bin) and is what `n_days` absorbs. No same-day
duplicates remain.

**Not done, and ticketed** (`theory` lane): the 6,860 quarantined rows are
**recoverable**, not lost. Every attempt carries `series_ticker` in
`extra_json` (verified: 9,269 of 9,269 on `live-2026-08-31-calharvest`),
and the complete category map re-derives the true domain for each. That is
a corpus migration and a judgment call about what this theory's evidence
is, so it belongs to the theory's own lane, not to maintenance.

**Checked it does not turn the theory into a bet-producer.** Under v3 with
merged rates, 2,754 rows price against a `measured` cell — but 0 have
`edge_pts_net > 0` (max −0.95). Observation rows under ruling 13, as
before.

## 2026-09-01 (later) - the pricing rule could not fire, and the reason is the estimator, not the data

Written BEFORE the change lands, because this theory has already been
burned once by choosing a contrast after seeing the numbers (2026-08-29
retraction). The argument below has to stand on its own, and the test of
that is stated here in advance: **if the fix were motivated by making
history look good, it would make history look good.** It does not. Under
the corrected estimator exactly one of twenty measured cells crosses
zero, in-sample, at +1.25 pts, and it belongs to the horizon claim that
was already retracted. That is recorded up front as *not a result*.

### The finding: v3's bound is infeasible at v3's own gate

`cell_edge` bounds on the settlement-day count
(`wilson_lower(round(p*n_days), n_days)`). Ask what true gross edge a
cell would need before `price()` emits anything positive:

    minimum n_days at which ANY positive edge is possible,
    even at a realized rate of 100%:

        ask 0.65  ->   8 days      ask 0.88  ->  31 days
        ask 0.70  ->  10 days      ask 0.92  ->  48 days
        ask 0.75  ->  13 days      ask 0.95  ->  79 days
        ask 0.80  ->  17 days      ask 0.97  -> 134 days

`MIN_CELL_DAYS` is **8**. So the gate calls a cell `measured` - the label
that authorizes a bet - at a day count where the pricing rule provably
cannot emit a positive edge at any realized rate, for every ask above
0.65. The gate and the estimator disagree about what the theory is doing,
and the gate is the one that says "measured".

**And Kalshi's reachable history is 58 days.** So the 0.92-0.97 band -
the favorite-longshot band, where this theory's whole thesis says the
effect is *strongest* - is unreachable by any tier-A backtest this theory
can ever run. Not "hard": arithmetically impossible. Required true gross
edge at the 58-day ceiling:

        ask 0.70 -> +14.5    ask 0.88 -> +10.3
        ask 0.80 -> +11.4    ask 0.95 -> IMPOSSIBLE at any realized rate

Le 2026's headline politics effect is +13.6 pts gross. The best cell this
repo has ever measured is +14.08. **v3 can only fire on effects at or
above the largest number in the literature**, and only outside the band
the literature says is richest. That is not conservatism; it is a dead
branch, and it explains every "0 cells measurable / nothing recommendable"
result this theory has produced without any of them being about the data.

### Why the bound is wrong: rho is not 1, it is ~0.03

Day-Wilson is not a neutral choice. It is the design-effect correction
`n_eff = n / (1 + (mbar - 1) * rho)` evaluated at **rho = 1** - total
within-day dependence, every market on a settlement day carrying one
draw's worth of information. v2 adopted it citing the 2026-08-27
clustering study, and hedged correctly at the time: "a proper
cluster-robust interval would sit somewhere between n_days and n."

Measured it. ANOVA intracluster correlation, per cell, on both complete
populations (20 cells clearing n>=30 and n_days>=8):

    pooled rho:  mean 0.0667   median 0.0266   90th pct 0.2326   max 0.3151

    weather cells (mbar 12-16):  rho -0.007 to +0.016  ->  DEFF 1.00-1.20
    politics cells (mbar 2-5):   rho -0.34  to +0.32   ->  DEFF 1.00-1.97

Weather is the sharp case: `<=2d|0.92-0.97` has n=926 over 59 days and
rho=0.008, so n_eff is **824**, not 59. Day-Wilson discards a factor of
**14** in effective sample size there.

The mechanism is obvious once stated, and it is why the 2026-08-27 study
does not transfer. That study measured day clustering on the
`insider_bias` population - a near-term board of *correlated events*
settling together. A calibration_harvest cell is (domain x horizon x
price bin), and the ~14 rows it holds on one settlement day are ~14
different cities' temperature markets. Those are close to independent
draws. Politics has the smaller mbar (2.6-5.3) and the higher rho, which
is the right direction: same-day politics markets far more often share an
underlying event. **The clustering is real; assuming it is total is what
was wrong.**

### The change (v4, `continues`)

`cell_edge` bounds on a design-effect-corrected effective n:

    mbar  = n / n_days
    DEFF  = max(1, 1 + (mbar - 1) * CLUSTER_RHO)
    n_eff = clamp(round(n / DEFF), 1, n)

with **one pooled `CLUSTER_RHO = 0.2326`** - the 90th percentile of the
20 measured cells, ~3.5x the mean and ~9x the median. Deliberately
pessimistic, and deliberately **one number**: a per-cell rho would be a
free parameter per cell, which is the thing this grid must never have.
The floors `MIN_CELL_N` and `MIN_CELL_DAYS` are untouched.

Note the endpoints, because they are what makes this a correction rather
than a loosening: rho=1 returns exactly `n_days` (v3), rho=0 returns
exactly `n` (v1). v3 and v1 are the two extreme special cases of the
formula, and the measurement says the truth is near the v1 end for
weather and about a quarter of the way for politics. The fix does not
invent an estimator; it stops pinning a measurable parameter at a value
the data rejects.

### What it changes today: nothing bettable

    cells firing:  day-Wilson (v3) 0  |  DEFF-Wilson (v4) 1  |  row-Wilson (v1) 2

The single cell is `politics|1mo+|0.75-0.85`, n=50, n_days=19, ask 0.799,
realized 0.940, +1.25 net. It is **not a result and must not be bet**:

  - **in-sample** - it is the population the grid was drawn on;
  - the *thinnest* long-horizon cell in the grid (n=50);
  - 1 of 20 cells, no multiple-comparison correction survives that;
  - it is the same cell whose horizon claim was **retracted on
    2026-08-29** as a pre-registration failure. It does not get to come
    back through a new estimator.

The pre-registered kill criterion is still **not met and still not
tested**: it asks whether a cell clears fees *out-of-sample* at n>=30 and
n_days>=8, and the forward corpus still has no measurable cell.

### What this buys, and the bar for it

The point of the change is the frontier, not today's cells. Required true
gross edge at the 58-day ceiling, v3 versus v4:

    ask    v3 (day)    v4 (DEFF, mbar 14)
    0.70     +14.5          +7.9
    0.80     +11.4          +6.9
    0.88     +10.3          +5.5
    0.95   IMPOSSIBLE       +3.5

That is the difference between a theory that can never fire and one that
can fire on an effect the size the literature actually reports - and it
re-opens the 0.92-0.97 band, which v3 had closed by arithmetic.

**Pre-registered, now:** v4 is confirmed only by a cell clearing fees
**out-of-sample** at n>=30 and n_days>=8 under the DEFF bound - a forward
cell, or a walk of a domain that did not exist when this was written.
A cell that fires only in weather or politics is in-sample and confirms
nothing. If a full further domain walk plus forward accrual produces no
out-of-sample firing cell, the honest reading is that Kalshi carries no
harvestable calibration edge at these price bands after fees, and the
theory should be put to the user for retirement - the estimator excuse
will have been spent.

### Also learned, and it changes the walk plan

The DEFF correction **saturates in rows**. Holding the 58-day ceiling and
varying rows-per-day from 3 to 170, the requirement at ask 0.70 moves
only 9.6 -> 7.4 pts, because DEFF grows with mbar and cancels the extra
rows almost exactly. **Only settlement days buy real power, and they are
capped at 58 upstream.** So walking a *huge* domain is worth little more
than walking a moderate one: the sizing probe (`collect size`, added
today) exists to avoid paying for rows that buy nothing. Crypto is the
trap - `KXBTC15M` alone is 5,497 settled markets / 5,491 candlestick
fetches (~20 min) on 15-minute BTC markets, all landing on the same ~58
days.
