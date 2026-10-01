# VA Hub "DA Virtual" tab — what it does, what held up, what we changed

Re-test on Toronto and Southwest hub prices May 2025 – Sep 2026 (NRGStream history + IESO archive), bid-time inputs only.
Tests start Jul 2025 (signals) or Sep 2025 (rules that learn on 120 days). Code: `model/da_virtual_bt.py`, `model/dv_grid.py`.
Numbers are Toronto unless marked; Southwest is within ~$1 unless noted.

## 1. What the VA Hub tab does (server.py `/api/virtual_strategy`, virtual.html)
- **Prices:** DA and RT per hour from a heat-rate lookup (gas plug rounded to 500 MW → HR table by HE → × gas price), one RT price per load source (IESO/DAA, Tesla, Dynasty, LD1, LD2, Perplexity), and a consensus.
- **Auto-score 1–5:** from the gap between the mean RT across sources and DA. 1 if RT ≥ DA + $10 with 5+ sources agreeing and a range ≤ $30; 2 if ≥ +$5; 4 and 5 are the mirror image. Forced to 3 if the sources disagree by $40+.
- **Lean −13..+13:** ten ±1 signals plus an RT-vs-DA level term (±1/2/3). The signals are:
  - load vs DAA
  - DAA vs its 7-day average
  - wind 3h ramp
  - solar 1h ramp
  - gas ramp %
  - gas "ledge" (below 2,500 MW / above 7,200 MW)
  - gas outages
  - nuclear outages
  - rain
- **Flags:** SPIKE / COLLAPSE from total headroom (<5k / 5–7k spike; 7–9k / ≥9k collapse), plus a stack-steepness score. A flag boosts MW 1.5×.
- **Ladder:** 3 tiers per side, priced as % of RT (or DA for the clearing tier). The tier formulas are in the page's rules table; we kept them unchanged.
- **Paste format:** `HE\tMW\tP\tMW\tP\tMW\tP` followed by six empty fields, prices as `40.00`.
- **Also on the tab:** a fundamentals snapshot, load consensus deltas, hourly bias badges (trailing RT − DA, 7 and 14 days), RT skew, and a ±500 MW sensitivity table.

## 2. What the re-test found
| piece | result ($/MWh, 90% range) | verdict |
|---|---|---|
| Load vs DAA (Tesla/Dynasty vs IESO, ±200) | +4.51 (+2.30..+6.79) | keep |
| Wind ramp 3h (±400) | +7.32 (+3.06..+12.10) | keep |
| Gas-need ramp (±15%) | +3.00 (+0.94..+5.20) | keep |
| Load vs 7-day | −0.19 | drop |
| Gas ledge <2,500 sell / >7,200 buy | **−6.96 (−12.03..−1.58)** | wrong way. Both extremes are where DA overshoots RT; buying above 7,200 loses |
| Gas outages / nuclear outages | −1.76 / +0.70 | drop |
| Solar ramp | 4 hours in 15 months | never fires |
| RT-vs-DA level term | +2.14 (−0.33..+4.50) | no edge |
| Lean total ≥ ±2 | +2.98 (+0.76..+5.24) | weak; mostly the sell side |
| Auto-score (gap), directional | +2.50 (−0.29..+5.08) | no edge; score 1 buys lost $9.92 at Toronto |
| Hourly bias badges 7d / 14d | +0.88 / +1.51 | 7d none, 14d marginal |
| **Our v2 SELL** (tight or surplus, walk-forward) | **+5.53 (+3.25..+8.00)** | keep |
| **Our buy band** (headroom in a learned 2,000 MW middle band) | **+10.97 (+6.08..+16.11)** Toronto, +10.23 (+5.57..+15.20) Southwest | **new: the first long-side rule to pass** |

**Headroom zones, measured** (the VA Hub labels 7–9k "collapse-medium"):

| headroom | mean DA−RT | RT > DA | RT > $100 | RT < $25 |
|---|---|---|---|---|
| < 5k | +14.3 | 29% | 46% | 1% |
| 5–6k | +11.9 | 30% | 36% | 0% |
| 6–7k | +6.2 | 32% | 27% | 1% |
| 7–8k | −5.9 | 39% | 21% | 3% |
| 8–9k | −9.6 | 40% | 14% | 5% |
| 9–10k | 0.0 | 32% | 7% | 10% |
| 10–12k | −0.1 | 36% | 3% | 22% |
| 12k+ | +2.1 | 36% | 1% | 45% |

- The spike side of the VA flag is about right: 46% odds of RT > $100 below 5k, against the VA Hub's 47–60% at peak.
- Collapse odds (RT < $25) are 22% at 10–12k and 45% at 12k+, against the VA Hub's ~30% for everything at 9k or more.
- The 7–9k "collapse-medium" band is backwards. It is where RT beats DA most often, by $6–10 on average. This held in both halves of the sample (Jul–Jan and Feb–Sep) and at both hubs.

**Ladders** (VA Hub formulas and MW, cleared on the actual DA, settled at RT, Sep 2025 – Sep 2026):

| score picked by | $/MWh | $/day | 90% range $/day | Feb–Sep 26 $/MWh |
|---|---|---|---|---|
| VA Hub auto-score | 3.29 | $2,609 | −829..+5,894 | 1.02 |
| Ours (v2 SELL = 5, buy band = 1, else 3) | 6.90 | $6,776 | +3,922..+9,678 | 7.05 |

- The ladder structure itself works. Even score 3 on every hour (a wide straddle) made +$5.63/MWh, because a tier only fills when DA prints far from the RT forecast.
- Deep bids fill in both halves:

| bid price | $/MWh |
|---|---|
| 0.8 × RT forecast | +6.89 |
| DA P10 | +5.83 |

- Offers above the DA forecast also fill profitably:

| offer price | $/MWh |
|---|---|
| 1.2 × DA forecast | +8.13 |
| DA P90 | +9.92 |

- The largest losing day is still large (≈ −$200k at the VA base MW). It comes from score-5 offers on spike days, so size score 5 with that in mind.

## 3. What our DA Virtual tab uses
- **Prices:** our walk-forward DA model and range (MAE ≈ $5 in summer, $12 over 17 months including winter spikes), and RT = DA × the trailing 28-day RT/DA ratio. There is no heat-rate lookup; the earlier review measured it at $8.99 against our model's $5.10.
- **Suggested score:**

| score | when |
|---|---|
| 5 | v2 SELL |
| 4 | v2 SELL-L |
| 1 | headroom inside the buy band (re-learned daily) |
| 3 | everything else |

- **Lean column:** shows only the three VA signals that held up. It is information; the score does not use it.
- **Ladders:** the VA Hub tier formulas, unchanged, priced off our DA and RT forecasts. The size multiplier is capped at the hub limit (580 / 315 MW per side).
- **The 1.5× flag boost is off**, because it is not tested.
