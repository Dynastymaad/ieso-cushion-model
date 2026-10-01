# The days our SELL lost: what happened, and what we could have caught

**Scope.** The v2 SELL signal (tight or surplus, walk-forward thresholds), run over Toronto and Southwest hub prices, Jun 2025 – Sep 2026.
- Toronto: 428 sell days; **143 lost**.
  - The losing days cost **−$45.6k per MW**.
  - The winning days made +$82.7k per MW.
- Southwest: 140 losing days, the same pattern.
- Everything below is Toronto; Southwest agrees within about $1 unless stated.
- Code: `model/fail_study.py` (diagnosis) and `model/fail_fix.py` (tests).
- Data: `data/fs_*.csv`, with the day-by-day table in `data/fs_diag_TORONTO.csv`.

## 1. What went wrong on each losing day
For each losing day I measured the surprises that arrived **after** the 08:00 MT deadline, in MW of lost headroom:
- load vs IESO's bid-time forecast
- wind vs the bid-time forecast
- outages added between the bid-time and the end-of-day Adequacy report
- exports vs the expected level
- the RT import limit vs the DA limit

The largest surprise, weighted by the losing hours, is the day's main cause.

| main cause (Toronto) | days | loss $/MW |
|---|---|---|
| Outages added after the bid (gas / nuclear forced out) | 39 | −12,231 |
| Load came in above IESO's forecast | 29 | −12,129 |
| Exports above expected | 40 | −7,473 |
| Wind below forecast | 14 | −7,155 |
| Scarcity at bid (headroom < 3,000 MW) | 3 | −2,936 |
| No single surprise ≥ 250 MW | 13 | −2,420 |
| RT import limit cut | 5 | −1,253 |

Across all the hours where a sell lost more than $50 (RT > DA + $50), the surprises show up far more often than in the winning hours:

| surprise | losing hours | winning hours |
|---|---|---|
| Load 300+ MW above forecast | 34% | 8% |
| Headroom fell 1,000+ MW after the bid | 35% | 14% |
| Wind 300+ MW below forecast | 27% | 15% |
| Gas outages added after the bid | 35% | 24% |

In 18% of the big losing hours, none of these surprises happened.

**The 20 worst days** (Toronto, loss per MW sold as a price-taker; "protective ladder" = score-5 offers at our P25/P50/P75, see §3):

| date | sell type | loss $/MW | RT max | what happened after the bid | visible at bid? | VA ladder $ | protective ladder $ |
|---|---|---|---|---|---|---|---|
| Tue 29 Jul 25 | tight | −2,780 | 1,226 | Headroom negative at bid (−787 MW) and RT kept spiking into the evening. Load actually came in 2,000 MW **below** forecast. | **Yes: extreme scarcity.** Tesla 1,300 MW below IESO (wrong way). | +10,745 | +44,783 |
| Mon 10 Nov 25 | tight | −2,259 | 984 | Wind 460 MW short, outages +270 MW, the RT import limit cut 440 MW. | No | −203,664 | −150,468 |
| Sat 24 Jan 26 | tight | −2,033 | 1,325 | **1,215 MW of gas/nuclear forced out after the bid**, on a cold day (12°F). | Partly: Tesla +411 MW over IESO; NY premium in 58% of hours | −183,157 | −150,936 |
| Thu 4 Dec 25 | tight | −1,984 | 821 | Wind short 260 MW; tight from HE1 (1,700 MW). | No | −163,452 | −108,103 |
| Tue 1 Jul 25 | tight | −1,842 | 710 | Load +770 MW and outages +800 MW after the bid. | No: Tesla was 150 MW *below* IESO | −95,614 | −20,369 |
| Tue 9 Dec 25 | tight | −1,500 | 706 | Exports ran 1,000 MW above normal, plus load +400. | Partly: NY premium in 56% of hours | −100,125 | −22,933 |
| Sat 2 May 26 | surplus | −1,245 | 380 | Load +1,060 MW over forecast on a $30 DA day. | Partly: Tesla +175 MW | −17,756 | +1,378 |
| Sun 5 Oct 25 | surplus | −1,126 | 331 | Load +1,070 MW (81°F October Sunday) plus wind short 530 MW. | **Yes: Tesla +631, Dynasty +340 over IESO** | −85,839 | −26,233 |
| Fri 7 Aug 26 | tight | −1,011 | 544 | Evening wind short 315 MW, outages +245. | No | −69,745 | −11,004 |
| Tue 7 Oct 25 | tight | −926 | 409 | Load +540 MW. | No: Tesla 430 MW *below* IESO | −83,380 | −95,140 |
| Sat 6 Sep 25 | surplus | −905 | 304 | Load +500 MW. | No | −60,574 | −49,874 |
| Wed 10 Jun 26 | surplus | −898 | 471 | **1,395 MW forced out after the bid.** | No | −74,904 | −74,540 |
| Fri 29 May 26 | surplus | −841 | 447 | Load +630 MW on a $25 DA day. | Partly: Tesla +154 | −68,798 | −68,742 |
| Wed 11 Mar 26 | surplus | −800 | 325 | Load +1,100 MW, and the RT import limit cut 600 MW. | No | −72,025 | −64,740 |
| Tue 6 Jan 26 | tight (1 h) | −668 | 803 | Outages +540 MW at HE18. | No | −60,151 | −33,417 |
| Wed 23 Jul 25 | surplus | −635 | 516 | Outages +550 MW (evening). | No | −63,420 | −21,979 |
| Sat 22 Nov 25 | tight | −616 | 320 | Nothing large; RT just ran hot. | No | −5,759 | +336 |
| Fri 25 Jul 25 | tight | −610 | 368 | Load +910 MW and outages +880 MW (85°F). | **Yes: Tesla +530 over IESO** | −52,472 | −34,557 |
| Sat 4 Oct 25 | tight | −567 | 322 | Load +455 MW. | No | −18,705 | +561 |
| Sat 4 Jul 26 | tight (3 h) | −565 | 777 | HE17–18 spike, no single cause. | Partly: Tesla +659 over IESO | −39,537 | 0 |

The losing days bunch in the shoulder months:

| months | losing days |
|---|---|
| Oct–Dec 2025 | 41 |
| Apr–Jun 2026 | 39 |
| Jul–Sep 2026 | 19 |

## 2. What we tested, and the result
Each candidate is something we **could see before 08:00 MT**. "Vetoed hours" are the sell hours the fix would have dropped. A fix passes only if all four hold:
- the vetoed hours lost money
- the whole 90% range is below zero
- both halves of the sample (Jul–Jan and Feb–Sep) agree
- both hubs agree

| candidate fix (skip the SELL when…) | vetoed hours | their DA−RT | 90% range | halves | verdict |
|---|---|---|---|---|---|
| Tesla load ≥ IESO + 300 MW | 868 | −2.54 | −8.83..+3.60 | −3.8 / −0.6 | **near miss** (SW −3.57, −10.09..+2.84) |
| …only on surplus sells | 427 | −4.05 | −9.12..+0.38 | −5.9 / −3.1 | **near miss** (SW −4.82, −9.93..**−0.27**) |
| …same, threshold re-learned daily (walk-forward) | 203 | −4.09 | −9.36..+0.88 | −6.9 / −2.1 | **fails**: gain +$830 per MW over 13 months |
| Tesla ≥ IESO (any amount) | 2,055 | −0.76 | −5.34..+3.73 | | no edge |
| Dynasty ≥ IESO | 1,475 | +2.11 | | | no (those sells won) |
| Bid headroom < 2,000 MW | 70 | −46.18 | −119.6..+23.0 | all in summer 2025 | **too few days (12)**. Watch-list flag only |
| Surplus sell with DA forecast < $25 | 607 | −1.96 | −5.04..+0.77 | −3.2 / −1.8 | near miss, small |
| Vendor wind 300+ MW below IESO | 1,110 | +4.02 | | | no (those sells won) |
| Meteologica wind 300+ below IESO | 274 | −0.16 | | | no edge |
| IESO raised its demand forecast 300+ since D-2 | 611 | **+14.28** | +2.72..+24.67 | | **wrong way**: these sells won |
| Outages added 300+ between D-2 and the bid | 581 | **+13.98** | +3.66..+24.20 | | **wrong way**: these sells won |
| NY Zone A ≥ our DA + $10 | 351 | **+17.07** | +2.21..+32.48 | | **wrong way** |
| RT beat DA two days ago (same HE or day mean) | 1,403 / 2,790 | +7.28 / +5.46 | both > 0 | | **wrong way** |
| Yesterday hot ≥ 85°F / cold ≤ 20°F | 195 / 334 | +22.35 / +31.67 | | | **wrong way** |
| Evening peak HE17–21 | 1,497 | +10.83 | | | **wrong way** |

**What this means.** Every bid-time warning that looks like "RT will spike" makes DA go up even more than RT: IESO raising load, outages already announced, a NY premium, heat, cold, the evening peak, recent RT spikes. On those hours the sell *wins*. The losses come from surprises that arrive **after** the deadline:
- forced outages
- load above IESO
- wind shortfalls
- exports pulled up in RT

We had nothing at 08:00 MT that separated those surprise days from the many days they did not happen. The one partial exception is Tesla running well above IESO: it correlates 0.57 with the actual load miss. It came close, but it does not pass.

## 3. What does pass: offer pricing, not a veto
Score-5 offers placed at our DA range (P25 / P50 / P75) instead of the VA tiers (max(0.98 DA, RT), RT, RT + $5), with the same MW (20/30/40). Cleared on the actual DA, all 428 Toronto / 411 Southwest sell days, Jul 2025 – Sep 2026:

| score-5 ladder | $/MWh | $/day | 90% range $/day | loss on losing days | worst day |
|  | made on winning days → net: VA Toronto +6.38M − 3.05M = **+3.33M**; protective +4.64M − 2.04M = **+2.60M**; VA Southwest +5.81M − 2.84M = **+2.97M**; protective +4.27M − 1.94M = **+2.33M** | | | | |
|---|---|---|---|---|---|
| VA tiers, Toronto | 8.06 | 7,787 | +4,921..+10,610 | −3.05M | −203,664 |
| **P25 / P50 / P75, Toronto** | **9.04** | 6,078 | +3,960..+8,384 | **−2.04M (−33%)** | **−150,936 (−26%)** |
| VA tiers, Southwest | 7.71 | 7,226 | +4,497..+10,106 | −2.84M | −184,895 |
| **P25 / P50 / P75, Southwest** | **8.53** | 5,672 | +3,505..+7,773 | **−1.94M (−31%)** | −183,194 |

- The offers only clear when DA prints at or above our range. So on the days RT runs away, less volume is sold, or it is sold at a better price.
- The cost is about 22% less P&L per day, because fewer hours clear on good days.
- It is a risk setting, not free money. **Decision (Sep 28): not adopted** — the VA tiers net more (+3.33M vs +2.60M Toronto). The toggle was removed.

## 4. What would let us catch more of these days (data, not yet testable)
1. **Temperature forecast at bid time** (Warehouse WeatherHourlyForecast vintages). We only have actual temperature. Load-miss days cluster on hot shoulder-season weekends (5 Oct, 25 Jul, 2 May) where IESO's forecast was low.
2. **IESO outage notices (forced-outage reports)** with timestamps. The largest loss bucket is outages that arrive after the bid; we need to see whether any show up early in the IESO or NRGStream outage feeds.
3. **Meteologica load forecast history** (we have it only since 2026-03). If Meteologica agrees with Tesla on "load above IESO", the near-miss veto may become a pass.
4. **More scarcity days.** Headroom below 2,000 MW happened on only 12 sell days, all in summer 2025. RT beat DA by $46 on average there. The tab now flags these hours as **SCARCITY** so you can decide; it becomes a rule once another summer confirms it.

## 5. Changes made
- DA Virtual tab:
  - the score-5 protective toggle was added, then removed by decision (VA tiers kept)
  - SCARCITY chip on hours with bid headroom < 2,000 MW
- No veto added to the signal: none passed.
- The near-miss (surplus sell with Tesla ≥ IESO + 300) is on the watch list in `notes/VA_Hub_ToDo.md`, to re-test with Meteologica load and a temperature forecast.

## Can late outages be predicted? (Sep 28 2026, quick check, East, live rules)
- **Worst 20 days:** median 457 MW added after the bid (peak hours) against 236 on all days. 45% of them had 500 MW or more added, against 24% of all days.
- **Load misses matter too:** 40% of the worst 20 days had IESO load come in at least 300 MW above the bid-time forecast, against 23% of all days.
- **Predicting the MW added after the bid** from bid-time inputs (trips in the last 24 h, IESO's assumed returns, outages at the bid) on a walk-forward, trailing-60-day fit:
  - Accuracy: corr 0.26 and MAE 357, no better than the trailing mean (MAE 355).
  - Assumed returns is the only input with any signal (corr 0.35): returns slip.
  - Days with high predicted additions actually made more money (+$8.5k vs +$5.8k per day). DA already prices the expected slip.
- **Conclusion:** the part DA misses is the unannounced trips, which are not predictable from the data we have. Nothing more to build. The remaining levers are:
  - news between IESO's last Adequacy file and the bid submission (what-if sliders);
  - overall size.
