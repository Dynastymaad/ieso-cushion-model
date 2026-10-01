# Ontario — second pass: the "drop / demote" list re-tested, and the hourly supply curve

Toronto and Southwest hubs. Data: IESO public reports 2026-06-28 → 09-27 (2,175 hours),
pre-deadline Adequacy3 vintages for 46 days (from 08-13), NYISO DAM Zone A, and warehouse
daily forwards (Dawn, PJM West, NYISO West, Ontario Hub). Every test is **walk-forward**:
fitted only on days before the target, inputs only as they stood before 09:00 EST on D-1.

**Tags:** [M] measured here, with n · [S] structural · [J] judgement.
**Sample warning:** every number is summer only. Re-measure in October.

---

## Part 1 — the drop / demote list, re-tested

### Summary of verdicts

| tool | first-pass call | re-test result | final call |
|---|---|---|---|
| NYISO DAM for tomorrow | drop (timing) | **Posted ~09:33 ET, before the 10:00 close. DA error 5.08 → 4.44 (−13%)** | **KEEP — I was wrong** |
| PJM / NYISO / Ontario Hub daily forwards (D-2 settle) | drop | PJM West: 4.82 → 4.68 (−3%). NY-West and Ontario Hub forwards: worse | **Minor keep: PJM only**, as a small daily nudge |
| Gas-plug heat-rate lookup | drop | $8.99 vs $5.10 on same hours; even with *perfect* flow/hydro knowledge $10.58 | **Drop confirmed** |
| "Flex headroom" spike/collapse thresholds | demote | Concept right (it's the cushion), stated odds too high | **Keep the concept, recalibrate the odds** |
| Hourly bias badges / diagnostics score | drop | Buy-side: no value. Sell-side evening: real, but mostly the tightness effect | **Demote to a secondary input** inside the spread model |
| Pre-dispatch price | drop as RT forecast | Worse than DA at every lead; biased +$17 to +$30 | **Drop for DA decisions**; keep as intraday monitor only |
| Fixed outage adders (+400 gas / +150 nuc) | drop | Real creep exists but smaller: **+125 gas / +27 nuc / +67 hydro** | **Replace** with measured creep, RT scenarios only |
| Lean / auto-score composite | drop | Can't test without Tesla/Dynasty history | **Park** until the load history exists |
| Spike / collapse / forecast-error pages | demote | Hindsight descriptions (use actual misses) | **Keep as review pages**, not signals |
| Congestion tool | peripheral | Toronto/SW basis to OZP ~$1; only 11 (Tor) / 18 (SW) hours over $20 in 90 d | **Not needed for your hubs** |

### 1. NYISO DAM — correction [M]

- **Timing:** NYISO's `damlbmp_zone.csv` for D carries `Last-Modified` 13:32–13:33 GMT on
  D-1 (four days checked) = **09:33 EDT, 27 minutes before the IESO close**. The VA Hub's
  "~07:35 MDT" note was right. It is not leakage if the job runs 07:35–07:45 MT.
- **Value:** adding ln(NY Zone A DAM, same hour) to the headroom model:

| fit window | headroom only | + NYISO DAM | test hours |
|---|---|---|---|
| 14 days | $5.84 | **$5.46** | 735 |
| 21 days | $5.08 | **$4.44** | 567 |

- It helps the **DA level only**. As a spread signal (NY DAM vs our DA forecast) it has no
  value: rank corr 0.04 with RT−DA.
- **Fallback:** if NYISO is late, run without it. Don't wait past 07:50 MT.
- PJM DA still posts ~13:30 ET, which is too late.

### 2. Daily forwards (warehouse) [M]

- **Timing:** only settles with EffectiveDate ≤ D-2 are legal. The D-1 settle is struck
  after the DA results.
- **As a standalone forecast,** the Ontario Hub on-peak forward (XDE) vs actual DA HE8–23
  weekdays gives MAE $12.39. The model gives $5.98.
- **As a daily nudge on the model** (fitted on prior 14 days, 480 test hours):

| nudge | model error |
|---|---|
| none | $4.82 |
| PJM West D-2 | **$4.68** |
| NYISO West D-2 | $4.94 |
| Ontario Hub on-peak D-2 | $4.96 |

- **Call:** PJM carries a little information about neighbour demand. Worth a slot, not a
  headline. Blending the Ontario Hub forward in hourly made things worse.

### 3. Gas-plug heat-rate lookup (the VA Hub's core engine) [M, 595 hours]

**How I rebuilt it:**
- Plug = IESO demand fcst + trailing net exports − nuclear avail − wind − solar − trailing
  hydro − bio − 125.
- Price lookup = HE±1 × 500 MW bins of actual gas output, trailing 60 days, minimum 3 obs.

**Results on the same hours:**

| method | DA error |
|---|---|
| **headroom model** | **$5.10** |
| headroom + NYISO | **$4.54** |
| heat-rate lookup, forecast plug | $8.99 (and no answer in 140 of 735 hours: the tails) |
| heat-rate lookup, **actual** flows and hydro (perfect hindsight) | $10.58 |

**Why it fails:**
- Exports and hydro *react* to price. Building them into the plug and then reading price
  back off gas output is circular.
- Even perfect foresight of those flows makes it worse, not better.
- The heat-rate *idea* (scale by Dawn gas) is fine for seasonality. It just can't be
  tested yet: Dawn only ranged $2.44–2.85 this summer.

### 4. Flex headroom and its spike / collapse odds [M, Aug–Sep]

- The VA Hub's "total head" is the same idea as the headroom used here. Ours ranks a
  little better (rank corr with DA −0.90 vs −0.84; with RT −0.74 vs −0.70) because it
  leaves out the circular flows.
- **The stated odds were too high.** The page says head < 5,000 MW on peak gives
  "47–60% odds > $100, 30%+ > $150". Measured:

| VA-Hub head (peak HE15–22) | n | P(RT > $100) | P(RT > $150) | P(RT < $25) |
|---|---|---|---|---|
| < 5,000 | 45 | 16% | 2% | 0% |
| 5,000–7,000 | 145 | 9% | 2% | 0% |
| 7,000–9,000 | 142 | 4% | 1% | 1% |

- **Collapse side, all hours:** 9–11k MW head gives 19% RT < $25; above 11k gives 52%.
  The page's "~30%" is in range.
- **Call:** keep headroom as *the* state variable and publish calibrated odds from the
  archive.

### 5. Momentum: bias badges and the diagnostics score [M, Toronto, 1,975 hours]

**Pooled across all hours:**

| rule (days D-2…D-8, same HE) | n | P(RT > DA next day) | mean spread |
|---|---|---|---|
| base rate | 1,975 | 37.9% | −$3.92 |
| "6 of 7 up" badge (buy) | 37 | 48.6% | +$0.99 |
| strong buy (7-day mean ≥ +15, ≥ 5 up) | 39 | 30.8% | −$4.70 (**loses**) |
| "≤ 1 of 7 up" badge (sell) | 407 | 31.4% | −$12.92 |
| strong sell (7-day mean ≤ −15, ≤ 2 up) | 316 | 31.3% | −$16.07 |

**Split by time block:**
- The whole sell effect is in the evening (HE17–21):
  - flagged: −$27.1, RT < DA 80% (n 162)
  - not flagged: +$0.4 (n 248)
- It holds in each month: Jul −38.6 vs +10.8, Aug −12.6 vs −3.8, Sep −23.7 vs −1.4.

**Controlled for headroom (Aug–Sep evenings):**

| | n | mean spread | RT < DA |
|---|---|---|---|
| tight + flagged | 85 | −$18.4 | 76% |
| tight + not flagged | 77 | −$12.9 | 75% |
| loose, either | 58 | about −$4 | 70% |

**Call:**
- Buy-side badges are noise.
- The sell-side persistence is mostly *tightness in disguise*: same hit rate once you know
  headroom, about $5 extra magnitude.
- Keep "last-7-days spread, this HE" as one input to the spread model. Don't use it as a
  standalone badge.
- My first-pass "momentum is useless" was too strong: pooling across hours hid the
  evening effect.

### 6. Pre-dispatch price [M, ~30 days]

| issued before the hour by | n | pre-dispatch vs RT error | DA vs RT error | pre-dispatch bias | rank corr (PD−DA) vs spread |
|---|---|---|---|---|---|
| 18 h (D-1 evening) | 267 | $36.40 | $17.87 | +$30.4 | −0.04 |
| 8 h | 587 | $34.07 | $14.72 | +$27.0 | −0.01 |
| 2 h | 750 | $25.20 | $12.96 | +$18.2 | 0.18 |
| 1 h | 753 | $19.54 | $12.94 | +$16.8 | **0.32** |

- It's never available before the DA close.
- It's always worse than DA as a level and always biased high.
- An hour out, its *direction* versus DA carries information.
- **Call:** useless for virtual bids. Useful on an intraday monitor, used as a direction
  signal, not a price.

### 7. Outage adders [M, 46 days, 1,104 hours]

Final Adequacy3 minus the pre-deadline vintage, same hour:

| fuel | mean | median | 90th pct | share of hours > +100 MW |
|---|---|---|---|---|
| gas outage | **+125** | +70 | +458 | 42% |
| nuclear outage | +27 | 0 | +74 | 9% |
| hydro outage | +67 | +22 | +241 | 30% |

- Actual nuclear output averaged 71 MW below the pre-DA "available".
- Outage creep vs RT−DA: rank corr 0.18. It is real, but you can't see it at bid time.
- **Call:** don't add anything to the DA inputs. The DA model is fitted on pre-DA vintages,
  so the creep is already in the calibration, and a flat adder would just move the
  intercept.
- Use the measured creep distribution for RT scenarios, like the Alberta outage slider.
  The fixed +400 / +150 is about 3× and 5× too big.

### 8. Not testable yet

- **Lean score and auto-score:** these need Tesla / Dynasty / like-day history with issue
  times.
- **Weather banner:** cheap to test once Toronto weather is pulled.

They stay out until they pass a walk-forward test.

---

## Part 2 — where each hour sits on the supply curve, and what a miss is worth

Three views, from physical to empirical. For trading, the third is the one that pays.

### 2a. The physical gas ladder (GenOutputCapability, per unit, 2,175 hours) [M]

Ontario's dispatchable stack above nuclear and hydro, as rungs:

| rung | units | capability (avg) |
|---|---|---|
| 1 CC and cogen | Portlands, Goreway, Halton Hills, Napanee, Greenfield, Greenfield South, Brighton Beach, TA Sarnia, Thorold, St Clair, cogens | ~7,870 MW |
| 2 peakers | York Energy Centre ×2, Hydrogen Ready (HRPP) | ~670 MW |
| 3 Lennox (gas/oil steam, long start, committed ahead) | Lennox G1–G4 | ~1,930 MW |

**Where the hour sat vs price:**

| deepest rung actually running | hours | median DA | median RT | P(RT > $100) | median RT−DA |
|---|---|---|---|---|---|
| CC/cogen only | 1,787 | $43.7 | $42.2 | 4% | −$2.9 |
| peakers | 71 | $83.8 | $68.9 | 23% | −$1.7 |
| **Lennox** | **317** | **$110.7** | **$84.5** | 36% | **−$26.5** |

**CC spare (capability − output) vs RT:** rank corr −0.84.

| spare CC | hours | median RT | P(RT > $100) | peakers/Lennox on |
|---|---|---|---|---|
| > 3,000 MW | 679 | $32 | 0% | 0% |
| 2,000–3,000 | 618 | $44 | 1% | 4% |
| 1,500–2,000 | 490 | $64 | 12% | 21% |
| 1,000–1,500 | 332 | $81 | 31% | 62% |
| 500–1,000 | 56 | $135 | 64% | 95% |

**The biggest single finding in this pass [M]:**
- **About 81% of all the DA premium at Toronto and SW came from the 317 hours when Lennox
  was running.**

| hub | Lennox on (317 h): mean RT−DA | RT < DA | Lennox off (1,857 h): mean RT−DA |
|---|---|---|---|
| Toronto | −$26.8 | 71% | −$1.1 |
| Southwest | −$23.9 | 69% | −$1.0 |

- Outside those hours the spread is close to zero.
- [J] The mechanism: Lennox has to be committed day-ahead. When the DA schedules it, the
  DA price is set by a very expensive unit, and RT then rarely needs all of it.
- **Caveat:** "Lennox on" is measured after the fact. At bid time you forecast the chance
  of it from headroom:

| pre-DA headroom | hours | P(Lennox runs) |
|---|---|---|
| < 6,000 MW | 104 | 45% |
| 6,000–7,000 | 65 | 29% |
| 7,000–8,000 | 118 | 8% |
| 8,000–9,000 | 137 | 2% |
| > 9,000 | 647 | ≤1% |

- **Build implication:** the model should carry **P(Lennox committed DA)** per hour as a
  headline output, the Ontario equivalent of Alberta's "reaches simple cycle".

### 2b. The empirical curves: DA vs RT, per block [M, 46 days]

- The DA curve is fitted as ln(DA) on the *pre-DA* headroom.
- The RT curve is fitted as ln(RT) on *actual* headroom (final availability minus actual
  net demand).
- Values are the price at a given headroom, then the $ cost of losing 100 MW there.

| block | headroom → | 12,000 | 10,000 | 8,000 | 6,500 |
|---|---|---|---|---|---|
| HE1–6 | DA level / $ per 100 MW | $36 / 0.31 | $42 / 0.37 | $50 / 0.44 | $57 / 0.50 |
| | RT level / $ per 100 MW | $32 / 0.74 | $51 / 1.16 | $80 / 1.83 | $113 / 2.57 |
| HE7–10 | DA | $36 / 0.38 | $45 / 0.47 | $55 / 0.59 | $65 / 0.69 |
| | RT | $30 / 0.52 | $43 / 0.74 | $60 / 1.04 | $78 / 1.35 |
| HE11–16 | DA | $30 / 0.48 | $41 / 0.67 | $57 / 0.92 | $73 / 1.17 |
| | RT | $25 / 0.46 | $36 / 0.66 | $52 / 0.96 | $68 / 1.26 |
| **HE17–21** | **DA** | $34 / 0.57 | $48 / 0.79 | **$66 / 1.10** | **$85 / 1.42** |
| | **RT** | $37 / 0.41 | $46 / 0.52 | **$58 / 0.65** | **$68 / 0.77** |
| HE22–24 | DA | $37 / 0.50 | $49 / 0.65 | $64 / 0.86 | $78 / 1.05 |
| | RT | $30 / 0.56 | $44 / 0.82 | $64 / 1.18 | $84 / 1.57 |

**How to read it:**
- **In the evening the DA curve is about twice as steep as the RT curve.** Losing headroom
  raises DA faster than it raises RT. That's the evening premium, seen as curve shape, and
  it's consistent with the Lennox finding.
- **Overnight it's the other way round.** RT is steeper, so thin overnight headroom is
  where RT can beat DA.
- These are smooth fits (exponential per block). They understate the very tight tail,
  where Lennox and imports take over. The grid version in the build will use binned
  quantiles like the Alberta grid.

### 2c. What a load miss is worth — the one to trade off [M, 1,056 hours]

- **Miss** = actual (demand − nuclear − wind − solar) minus IESO's pre-deadline forecast
  of the same.
- Positive miss means more net demand than IESO assumed.
- Cells show the **median RT − DA** (mean in brackets, n).

| pre-DA headroom | miss < −600 | −600…−200 | −200…+200 | +200…+600 | > +600 |
|---|---|---|---|---|---|
| < 7,000 (very tight) | **−46** (−43, 36) | −25 (−31, 47) | −10 (−19, 35) | −5 (0, 36) | +6 (16, 15) |
| 7,000–8,500 | −19 (−16, 34) | −5 (−4, 51) | +3 (4, 46) | +7 (13, 32) | **+20** (27, 26) |
| 8,500–10,000 | −8 (−8, 57) | −5 (−5, 67) | +4 (4, 54) | +9 (12, 29) | **+29** (29, 24) |
| 10,000–11,500 | −7 (−8, 64) | −4 (−2, 68) | +3 (5, 63) | +5 (8, 32) | +6 (10, 10) |
| > 11,500 (loose) | −13 (−13, 70) | −5 (−5, 60) | −1 (−2, 69) | +1 (3, 19) | +3 (6, 12) |

**What this says for a given hour:**
1. **Very tight (< 7,000 MW):**
   - The DA has already priced scarcity, and then some.
   - A miss *down* is very costly for a DA buyer: −$25 to −$46.
   - Even a +200–600 MW miss up leaves RT *below* DA.
   - These are sell-DA hours unless you are confident demand comes in 600+ MW over IESO.
2. **Middle (7,000–10,000 MW):**
   - The payoff is asymmetric *upward*. A 600+ MW miss up pays +$20 to +$29.
   - A miss down costs only −$5 to −$19.
   - This is where a better load forecast makes money on DA buys.
3. **Loose (> 10,000 MW):**
   - About $1–2 per 100 MW either way.
   - Not worth risk unless the miss is large and down: < −600 gives −$13 when loose.

- IESO's forecast ran high in 55–91% of hours by HE, so misses skew down.
- That's why the premium side of the table is so well populated.

### 2d. Example — tomorrow, Sunday 2026-09-27 (DA already published: an out-of-sample check)

- Inputs: Adequacy3 vintage issued 09-26 07:5x EST.
- Fit: headroom model on the last 21 days.
- Every hour sits in the loose or middle band. From the grid, a ±500 MW miss is worth
  roughly −$4 to +$5 in most hours and more in HE18–20.

| HE | headroom MW | model DA | + NYISO | actual OZP | Toronto | SW | DA $ per −100 MW headroom |
|---|---|---|---|---|---|---|---|
| 1 | 12,100 | 35.8 | 33.5 | 31.46 | 31.07 | 31.00 | 0.33 |
| 4 | 12,700 | 33.8 | 30.5 | 28.47 | 28.03 | 28.01 | 0.32 |
| 8 | 11,700 | 40.1 | 38.6 | 43.81 | 43.31 | 43.43 | 0.30 |
| 12 | 10,900 | 37.6 | 37.1 | 38.66 | 38.45 | 38.35 | 0.46 |
| 16 | 10,900 | 37.3 | 40.1 | 41.74 | 41.49 | 41.52 | 0.46 |
| 17 | 10,400 | 44.6 | 42.6 | 49.30 | 49.10 | 49.07 | 0.68 |
| 18 | 10,100 | 46.7 | 46.0 | 52.32 | 52.06 | 52.01 | 0.71 |
| **19** | **9,800** | 48.5 | 47.8 | 57.05 | 56.81 | 56.75 | **0.74** |
| 20 | 10,000 | 47.1 | 45.6 | 52.81 | 52.49 | 52.41 | 0.72 |
| 21 | 10,500 | 43.4 | 41.9 | 46.62 | 46.26 | 46.29 | 0.66 |
| 24 | 11,700 | 39.6 | — | 39.88 | 39.47 | 39.43 | 0.25 |

- **Accuracy:** 24-hour error $3.54 (model), $3.31 (with NYISO). Toronto and SW sat
  $0.2–0.6 under OZP all day.
- **Weak spot:** the evening was under-called by $5–9. Sunday has no weekday term yet;
  that's on the build list.

---

## Part 3 — what changes in the build because of this

1. **Inputs at bid time:**
   - IESO Adequacy3 (pre-DA vintage)
   - NYISO DAM Zone A (09:33 ET)
   - Dawn and PJM West D-2 settles (warehouse)
   - Your load forecasts, archived with issue time
2. **Headline outputs per hour, Toronto and SW:**
   - DA P50 / EV
   - RT P50
   - P(Lennox committed)
   - the miss-value row (what ±500 MW is worth at this hour's headroom)
   - bid and offer
3. **Bid/offer logic uses the miss grid, not a flat ladder:**
   - sell DA where headroom is very tight
   - buy DA only in the middle band, and only when your load view is above IESO's
   - stand aside when loose
4. **Archive every morning:** Adequacy3, VG, prices, NYISO, and your load files.
5. **Not in the build** until they pass a walk-forward test:
   - heat-rate lookup
   - pre-dispatch as an RT forecast
   - fixed outage adders
   - buy-side bias badges
   - lean / auto-score
