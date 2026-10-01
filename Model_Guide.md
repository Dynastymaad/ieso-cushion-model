# Ontario Virtuals Desk — model guide

How the next-day model works, what each number on the page means, how to read the Ontario supply mix, and where it is weak.
Last updated 2026-09-27. Backtest details: `notes/Edge_Study.md`. Code map at the end.

---

## 1. What the page answers
For tomorrow (delivery day D, bid on D-1 before 08:00 MT / 10:00 EPT), per hour, for the **Toronto** (580 MW limit) and **Southwest** (315 MW) virtual hubs:
1. Where DA will clear (P10–P90).
2. Where RT will settle (P10–P90).
3. Whether to sell (virtual offer, earns DA − RT), at what size and at what prices.
4. The supply stack behind it: what gas has to cover after nuclear, wind, solar, hydro and exports.

Everything uses only data public before the deadline. IESO file times are EST all year, hour-ending HE1–24.

## 2. Timeline on the bid morning (summer, MT)
| MT | what arrives |
|---|---|
| ~02:30 | Warehouse load/wind vendor forecasts loaded (IESO, Tesla, Meteologica, Frontier, StormVista, NAM/GFS/GEM) |
| 06:50 | IESO Adequacy2/3 main pre-DA vintage for D (07:50 EST) |
| 07:33 | NYISO DAM prices (Zone A) |
| 07:37–07:56 | NYISO DAM energy report: scheduled NY↔Ontario flow |
| 07:45 | run the model, paste the ladder |
| 08:00 | IESO DAM closes |

## 3. The pieces

### 3.1 DA price (hourly)
Per time block, a ridge regression of ln(DA) on:
- spare MW (headroom)
- ln NYISO Zone A DA
- NY–Ontario scheduled flow
- weekend flag
- ln yesterday's DA (same hour)

It is fit on the trailing 21 days, then rescaled to a daily block level. That level is 50/50 of an "anchored delta" (last DA × change in headroom, Dawn gas and PJM West) and the traded Ontario Hub forward. Quantiles come from walk-forward residuals.
Accuracy (Jul 19 – Sep 27): Toronto MAE $6.44 (vs $10.42 for "yesterday same hour"). No overall skew. It runs slightly high in calm hours and low in spikes (−$19.7 when DA > $120). Saturdays run about $4 low.

### 3.2 RT price
DA forecast × the distribution of RT/DA for that time block and tightness. Use the range, not the point: the P50 error is $18 against $18.81 for "RT = DA forecast".

### 3.3 Sell signal (v2)
- **Tight:** spare MW below a threshold learned each morning from settled spreads (7,000 MW so far). DA commits peakers and Lennox that RT often does not need.
- **Surplus:** bid-time gas need below a learned threshold (2,500–4,000 MW). Ontario is long on nuclear, hydro and wind, and RT falls toward low offers.
- **SELL** = tight or surplus. **SELL-L** = the looser surplus threshold, at half size.
- **No buy rule:** none has passed the walk-forward test (see section 7).
- Offer tiers: SELL 50% at DA P10, 30% at P25, 20% at P50. SELL-L 60% at P25, 40% at P50.
- Walk-forward, Jul 20 – Sep 27, 1 MW, no uplift:

| | Toronto | Southwest |
|---|---|---|
| SELL | +$10.82/MWh, 90% range +3.3 to +17.5 | +$8.74 |
| every other hour, if sold | −$3.58 | −$3.71 |

### 3.4 Supply stack (bid-time, MW)
| row | source | accuracy |
|---|---|---|
| Demand IESO | Adequacy2 pre-DA forecast | runs high: actual below it in 73% of hours, by 377 MW on average |
| Demand Tesla | Warehouse LoadForecast (Tesla) | bias +26 MW, MAE 414 vs IESO 549 |
| Nuclear avail | Adequacy capacity − outages | — |
| Wind IESO / Meteologica | Adequacy2 / Warehouse WindForecast | MAE vs actual: Meteologica 244, IESO 264, Frontier 387, NAM 428, GFS 509, StormVista 436–487 |
| Solar | Adequacy2 | small (478 MW grid) |
| **Hydro (model)** | curve + carry (below) | MAE 229 MW vs DA hydro schedule (470 days); 14-day median 280; IESO hydro forecast 464 |
| Hydro IESO | Adequacy2 "Hydro Forecast Energy" | shown for reference; runs +251 MW high |
| **Net exports (model)** | NYISO-scheduled NY flow + curve + carry for the other interties | MAE ~450–500 MW vs DA schedule (77 days so far); 14-day median 732 |
| Gas need | demand − nuclear − wind − solar − hydro + net exports | vs DA gas schedule: MAE 582 MW (the old 14-day-median version: 936) |
| Gas need (Tesla load) | same with Tesla demand | removes most of IESO's load bias |
| Spare MW | gas + hydro available − (IESO demand − nuclear − wind − solar) | the Ontario "cushion" |
| Export / import limit, all ties | IESO Pre-DA intertie scheduling limits (= NRGStream DA limits, 100% match) | known at bid; exact |
| NY, MI, PQ export / import | same, by tie (PQ = sum of the nine lines) | exact |
| Export / import limit cut vs 28d | trailing 28-day median of the same HE minus D's limit (+ = derated) | tested below; no edge on its own |

**Hydro and exports, the Alberta method.** In Alberta the intertie assumption is a curve ("what does an hour this tight normally import?") plus a carry of the most recent observed miss, decayed with lead time, and capped at ATC. Ontario uses the same idea:
- **Curve:** for each HE, a linear fit of the DA schedule on residual demand (IESO demand − nuclear − wind − solar) plus a weekend shift, over the trailing 28 days.
- **Carry:** yesterday's same-hour miss of the curve (D-1's DA schedule is public at the deadline) × k. For hydro, k = 0.8, chosen on Jun–Dec 2025 and tested on 2026 (test MAE 236 vs 340 with no carry). For exports, k = 0.4, provisional until the full intertie history is pulled.
- **Caps:** hydro is capped at hydro available. Exports are capped by the intertie scheduling limits for D (IESO Pre-DA limits, published D-1 ~08:08 EST, before the bid): the NY part is clipped to the NY import/export limits, and the total to the sum of all ties (NY, MI, MN, MB and the nine PQ lines). Over 77 days the cap bound in 7 hours and the NY schedule was clipped in 196, so the MAE is unchanged (453 MW). The cap guards against impossible numbers; it does not add accuracy.
- **Exports:** the NY part comes straight from NYISO's DAM schedule, which is known before the IESO deadline. The curve and carry model only the rest (MI, PQ, MN, MB).

### 3.5 The other columns
- **Lennox %**: how often Lennox (the oil/gas steam plant, the most expensive unit) actually ran in RT at that spare MW this summer: 82% below 6,000 MW, 62% at 6–7k, 35% at 7–8k, 13% at 8–9k, 2% above 9k. Lennox hours averaged DA − RT of +$22; other hours +$0.3.
- **Lean**: a ridge estimate of DA − RT from bid-time inputs. The ranking is real (top fifth of hours +$5.70, bottom fifth −$2.99; permutation p = 0.003), but it is too weak to trade alone.
- **Tesla − IESO**: Tesla load minus IESO demand forecast, in MW. Hours with Tesla 600+ MW below IESO averaged DA − RT +$13, but walk-forward only +$1.86 (not significant). Information only.
- **ON→NY sched**: NYISO's DAM scheduled Ontario→NY flow. It matches IESO's actual NY flow (corr 0.81, same direction 91%). Used inside the exports forecast.
- **RT−DA if load 200–600 low / high**: a sensitivity. It is the median RT − DA in hours with similar spare MW when load missed IESO's forecast by 200–600 MW low or high. Overall: 600+ low −$15, 200–600 low −$5, 200–600 high +$5, 600+ high +$13.

### 3.6a What-if sliders (DA Virtual tab)
Demand (MW), wind (%), solar (%), gas / nuclear / hydro availability (MW), net exports (MW), with presets (gas unit trip, nuclear unit out, heat, calm, export pull). Each hour's headroom and gas need are shifted, DA moves through the DA model's own per-block coefficients (−11% per +1 GW headroom at HE18 today; NY-flow coefficient for exports), RT keeps its ratio to DA, and the signal, suggested score and ladders are re-run with the learned thresholds. Scores you set by hand stay; untouched hours follow the new suggestion.

### 3.6b Outages tab
See `notes/Outages.md`.

### 3.6 DA Virtual tab (modelled on the VA Hub "DA Virtual" tab)
- **Final matrix, per HE:**
  - DA forecast and P10–P90, RT forecast, RT − DA
  - headroom and its zone, with the measured odds of RT > DA and RT > $100 in that zone (17 months)
  - the v2 signal, and the lean (only the three VA signals that passed: load vs IESO, wind 3h ramp, gas-need ramp)
  - Tesla and Dynasty load minus IESO
  - trailing DA − RT at this HE over 7 and 14 days
  - what the VA Hub auto-score would say, and our suggested score with 1–5 buttons to override it
- **Suggested score:**

| score | when |
|---|---|
| 5 | v2 SELL |
| 4 | v2 SELL-L |
| 1 | headroom inside the **buy band** (re-learned daily) |
| 3 | everything else |

  Score-5 hours on the **tight** branch get **×1.5 MW when 500+ MW of units tripped in the last 24 h** (surplus sells: no boost, no edge there) (outage timeline; +$12.33/MWh vs +$3.66, both hubs and halves).
  The buy band is the 2,000 MW headroom window with the most negative DA − RT over the last 120 days (≥ 150 h, mean ≤ −$3). It has been 7,000–9,500 MW all year. Walk-forward result: +$10.97/MWh Toronto, +$10.23 Southwest; it is the first long rule that passed.
- **Ladders:** the VA Hub 3-tier formulas, priced off our DA and RT. The paste format matches the IESO grid (HE, 3 × MW/price, 3 empty tiers). A size multiplier is capped at the hub limit.
- **Re-test on the tab:** VA auto-score vs ours on the same ladders ($2,609/day vs $6,776/day at Toronto), every VA signal on its own, and the headroom zones. Full write-up: `notes/VA_Hub_DA_Virtual_Retest.md`. The other VA Hub tools are listed in `notes/VA_Hub_ToDo.md`.

### 3.7 East and Ottawa (traded zones) — see notes/East_Ottawa_Quebec.md
Hubs are East (85 MW/side/h) and Ottawa (100). Same model and rules as Toronto; 17-month capped ladder net +$3.48M East, +$3.33M Ottawa.
Quebec exports raise the East/Ottawa DA premium (+2.4 / +6.3 $/MWh per GW) but add nothing at the bid; shown on the East–Ottawa & Quebec tab.
Optional standing pair (sell East / buy Ottawa, HE12–16): holdout +3.42 $/MWh, positive-skew, off by default.

## 4. How to read Ontario's mix (vs Alberta)
- **Nuclear (~9 GW)** runs flat and never sets price on the way up. Outages matter 1:1: every MW out is a MW gas must cover.
- **Gas sets the price.** The DA gas schedule tracks DA price (corr 0.64). DA − RT is U-shaped in gas:

| DA gas schedule | DA − RT | sell wins |
|---|---|---|
| < 2 GW | +10.5 | 100% (6 h) |
| 2–3 GW | +9.5 | 79% |
| 3–4 GW | +7.7 | 79% |
| 4–5 GW | +2.5 | 66% |
| 5–6 GW | −3.3 | 53% |
| 6–8 GW | +8.7 | 61% |
| > 8 GW | +41.6 | 69% |

  In surplus and tight hours DA overshoots RT; in the balanced middle there is no edge. Alberta's cushion is one-sided; Ontario's is not.
- **Hydro (~3–4 GW scheduled)** is the flexible buffer. It moves with gas, so treat it as a response, not a cause.
- **Wind (≤ ~4.9 GW)** is the main supply surprise. +1,000 MW more wind in RT than DA scheduled moved DA − RT by +$22.
- **Demand miss** is the biggest single driver of DA − RT (corr −0.45). 1,000 MW less load than IESO forecast moved DA − RT by +$18.
- **Exports:** +1,000 MW more export in RT than DA scheduled moved DA − RT by −$19.
- **Nuclear surprise:** +$13 per GW. **Solar:** ≈ 0.
(OLS on Jun 28 – Sep 25, R² 0.31.)

## 5. Why the long side is hard (current finding)
- RT beat DA in only 38% of test hours. The top 2% of hours hold 34% of all buy-side dollars. The best buy days (Aug 7, Jul 27, Jul 26, Aug 1, Sep 17) were tight days where RT spiked **after** the deadline, on the same days the sell signal usually wins.
- No bid-time input separates "tight and DA overshoots" from "tight and RT spikes" with the data we have. Headroom, Tesla gap and yesterday's morning spread all have ~0 correlation with RT − DA.
- The one lead: NY Zone A DA above our Ontario forecast. When it was > $10 above, RT beat DA in 70% of hours (+$10.7), but only 20 hours on 4 days.
- What would separate them needs history we do not have yet:
  - hourly hub prices before 28 Jun 2026, to see more spike days
  - vendor wind and load vintages matched to prices
  - ~~intertie limits and derates~~ (now pulled; see 5.1: no edge on their own)
  - post-deadline outage patterns
- Weekend middays in the 5–7 GW gas band leaned long (+$15 mean, 61% win, 57 h). Not yet proven.

### 5.1 Intertie limits: tested, no trade on their own (May 2025 – Sep 2026, 516 days)
The limits for D are public at 08:08 EST on D-1, so they could be a bid-time input. Toronto shown; Southwest is within $1–3.
- **Import limit cut** vs its 28-day norm: DA − RT does not move in a consistent direction (−$3.9 at 100–250 MW cut, +$2.9 at 250–500, +$2.1 at 500–1,000). RT spikes (RT > DA + $50) are no more frequent. DA already prices the derate.
- **Export limit cut:** also flat overall. The one pocket is **tight days (spare < 8,000 MW) with the export limit cut ≥ 1,000 MW**: mean DA − RT −$16 (Toronto) / −$20 (Southwest), RT spikes 20% of hours, 22 days. The median is only −$1, so a few spike hours carry it.
- **Walk-forward** (each month picks its threshold and side from the trailing data, then trades the next month):

| rule | hours | $/MWh | 90% range | result |
|---|---|---|---|---|
| import cut (side learned) | 1,456 | +2.25 | −2.46..+6.50 | not significant |
| export cut (side learned) | 1,246 | −2.96 | −8.05..+1.54 | loses |
| NY / MI / PQ import cut | 589–1,564 | −1.74..+0.22 | all straddle 0 | nothing |
| BUY tight + export cut (the pocket above) | 132 | −13.62 | −21.17..−5.76 | **loses**: the pocket is not stable month to month |

- **After the deadline** (pre-dispatch and RT limits vs the DA limit; not tradeable at bid, useful intraday): when the export limit is **raised** after DA by 100+ MW, DA − RT averaged −$9.3 and RT spiked in 12% of hours (vs 7% normally). More room to export in RT pulls RT up. Import derates after DA showed nothing.
- **Use today:** the limits cap the exports forecast and are shown in the stack so a derate is visible. They are not in the signal.

## 6. Data: what we have and what is missing
| need | source | status |
|---|---|---|
| DA/RT hub prices, hourly | **NRGStream** (Toronto 421361/416911, Southwest 421363/416913), pulled 2026-09-27 → `data/nrg/hub_prices_nrg.csv`, May 2025 → Sep 2026; IESO public archive for the latest 90 days | have. Checked against the IESO files: DA identical to the cent in 98.9% of hours, RT hourly average in 97.4% |
| Pre-dispatch hub price | NRGStream 417075 / 417074 → same file (`pd`) | have, May 2025 → |
| DA intertie limits, all ties (NY, MI, MN, MB, Manitoba SK1 and the PQ lines) | NRGStream folder 2186 → `data/nrg/da_intertie_limits.csv` + `da_intertie_limits_pq.csv`; IESO PreDAIntertieSchedLimits for the latest days | have, May 2025 →. NRG = IESO in 100% of 720 overlap hours (SK1 = IESO zone PQSK) |
| Adequacy2, every vintage (pre-DA forecasts, DA schedules by fuel, zonal import/export schedules and offers) | canpower.ieso_adequacy2_all_archive | have, 2025-05-02 → |
| Load forecast vintages | Warehouse LoadForecast (IESO, Tesla, DYNASTY since 2024-06; Meteologica recent) | have |
| Wind forecast vintages | Warehouse WindForecast (IESO, Frontier, NAM, GFS, GEM since 2024-06; StormVista; Meteologica since 2026-03) | have |
| Solar forecast | Warehouse (Meteologica since 2026-03), Adequacy2 | have |
| Weather, Ontario stations | Warehouse WeatherHourly / WeatherHourlyForecast; StormVista (sandbox.weather, no permission yet) | partial |
| Generation by fuel, actual | IESO yearly files 2015+ | have |
| Per-unit output (gas ladder, Lennox) | IESO GenOutputCapability (≈90 days) → archive | archive since Jun 2026; **older → NRGStream** |
| Intertie flows, actual | IESO yearly 2018+ | have |
| Intertie limits, pre-dispatch / RT | NRGStream folders 4226 / 4227 → `data/nrg/pd_intertie_limits.csv`, `rt_intertie_limits.csv` (RT = hourly average of the 5-min limit) | have, May 2025 →. After the deadline, so diagnostics only |
| Wind/solar forecast vintages | NRGStream VG streams (publish-date vintages since 2021); StormVista API region `ieso` (key-based, archive since 2018) | not pulled: not needed. Adequacy2 pre-DA holds IESO's wind and solar at bid time for all 17 months, and the Warehouse holds the vendor forecasts (Meteologica best) since Jun 2024 |
| NYISO DAM prices + energy report | NYISO public archive 2025-04+ | have |
| Virtual transactions (market + Dynasty) | canpower | have |

**Getting the data ourselves (GitHub Pages step):** the browser pull was a one-off. The daily job must use the NRGStream API (`api.nrgstream.com/api/security/token` with the Trader username and password, then `/api/StreamData/{id}?fromDate=MM/DD/YYYY&toDate=…`, one token per login, released after use) and the StormVista API (`api.stormvistawxmodels.com/v1/model-data/...?apikey=…`). Credentials go in local `nrg.json` / `sv.json`, which are gitignored. NRG timestamps are hour-beginning Eastern prevailing time; `model/nrg_import.py` shifts them to the IESO keys. Streams the daily job needs: hubs DA 421361/421363, RT 416911/416913, pre-dispatch 417075/417074; DA intertie limits 105654–105681 (folder 2186); pre-dispatch limits 299232–299259 (folder 4226); RT limits 299479–299506 (folder 4227). The DA limits can also come free from IESO (`PUB_PreDAIntertieSchedLimits`, already in `ieso_backfill.py`), and the hub prices come from the IESO archive too, so going forward NRGStream is mainly the pre-dispatch and RT limits plus history.

## 7. Limits
- Most signal tests now cover 15–17 months (NRGStream history); the DA accuracy panels still show the summer window.
- The signal test covers 70 days; its 90% range is wide.
- Virtual-offer uplift is not deducted. If uplift is above ~$3/MWh, SELL-L is break-even.
- Wind and load surprises after the deadline can't be forecast at bid time.
- The export carry weight is provisional (77 days).

## 8. Code map
- `model/zone_bt17.py` — East/Ottawa 17-month ladders (capped), E–O pair, Quebec regressions → data/zone_bt17.json
- `model/nrg_import.py` — now also EAST / OTT / OZP (ONTARIO)
- `model/run_model.py eo_bundle()` — East–Ottawa & Quebec tab data

| file | role |
|---|---|
| ieso_backfill.py | daily archive of the IESO / NYISO rolling window |
| pull_history.py | Warehouse + sandbox pulls (`--only adq2x` for intertie schedules and offers) |
| ont_probe3.py | catalog probe for other databases (the datamart) |
| model/parse_archive.py | archive → data/*.csv |
| model/hourly.py, blocks.py | DA model |
| model/signals_v2.py | the sell signal (same code live and in the backtest) |
| model/supply_fc.py | hydro, exports and wind-vendor forecasts, intertie limits and caps (`--limits`), and the live stack |
| model/nrg_limits.py | NRGStream limit pulls (DA / pre-dispatch / RT) → wide `data/nrg/*_intertie_limits*.csv` |
| model/da_virtual.py | live pieces of the DA Virtual tab (buy band, lean, scores, ladders) |
| model/da_virtual_bt.py, dv_grid.py | 17-month re-test of the VA Hub rules and ladders → `data/dv_*` |
| model/wx_bid.py, load_miss.py | bid-time temperature (Open-Meteo 2-day-old forecasts) and the IESO load-miss test |
| model/outage_history.py | 7-year unit-level outage history, monthly norms, trip events → `data/genoutcap/` |
| model/outlook18.py | IESO 18-month Reliability Outlook editions → `data/outlook/ro_weekly.csv` |
| model/outages_tab.py | the Outages tab bundle (now, 35-day, outlook, units out, seasonal, watch list) |
| ieso_fwd35.py | IESO 35-day Adequacy schedule from the public site → `data/fwd35.csv` |
| model/outage_timeline.py | when outage MW appeared (Adequacy2 vintages) → `data/outage_features.csv`; live 'trips in last 24 h' |
| model/fail_study.py, fail_fix.py | losing-sell-day diagnosis and the fixes tested |
| model/limits_study.py | limits vs DA − RT, walk-forward tests → `data/ls_*` |
| model/edge_study*.py, long_study.py | backtests and diagnostics |
| model/run_model.py → build_page.py | bundle → page |
