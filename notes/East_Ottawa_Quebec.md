# East and Ottawa zones, the Quebec interties and the East–Ottawa pair

Test window: Jul 2025 – Sep 2026 (455 days) for the signal and ladders. Prices run from May 2025, and the first month is used only as training. East and Ottawa DA, RT and pre-dispatch come from NRGStream: streams 421358/416908/417068 (East) and 421360/416910/417073 (Ottawa); OZP is 415916/413124. They match the IESO archive on the overlap: DA to the cent in 100% of hours, RT hourly in 98%.
Scripts: `model/zone_backtest.py`, `model/da_virtual_bt.py EAST OTTAWA`, `model/zone_bt17.py ladders|spread|quebec`. Results are in `data/zone_bt17.json`.

## No look-ahead, and fills
- **Inputs:** every input is what was published before the D-1 10:00 EPT deadline. Adequacy preDA vintages are all stamped before the deadline. Load, wind and solar forecasts use their bid-time vintages. The zone/OZP basis ratio stops at D-1's DA, which is published on D-2.
- **Learned values:** the v2 thresholds, the buy band, the RT/DA ratio and the pair side all learn on days ≤ D-2, because RT for D-1 is not final at the bid.
- **Fills:** the ladder tests clear each tier against the actual DA. A bid fills if DA ≤ its price; an offer fills if DA ≥ its price. Filled MW settle at RT. The price-taker rows ("DA−RT $/MWh") assume a fill and are only for measuring the signal.
- **Not modelled:** uplift and fees; our own price impact (85–100 MW is small against the zone); and the fact that we chose which rules to test, which the untouched second-half checks guard against.

## Zone assumptions changed
- **Limits:** East 85 MW and Ottawa 100 MW per side per hour (IESO Table 2). Ladders scale down when they would exceed the limit.
- **Boost:** the ×1.5 tight-sell boost does nothing at East because score-5 offers (90 MW) already hit the 85 MW cap. At Ottawa it adds about $144k over 17 months.
- **Zone DA forecast:** OZP block forecast × the trailing-14-day zone/OZP ratio, blended 50/50 with the hourly model (same as Toronto). DA MAE is 12.6 at East and 13.9 at Ottawa, against 12.4 at Toronto.

## Results (ladders capped, live rules: v2 SELL = 5, buy band = 1, else 3, tight boost)

| | East | Ottawa |
|---|---|---|
| Net, 454 days | +$3.48M | +$3.33M |
| $/MWh cleared | 7.84 | 7.09 |
| $/day | 7,670 | 7,341 |
| Jul–Jan / Feb–Sep net | +2.15M / +1.34M | +1.96M / +1.37M |
| Worst day / max drawdown | −195k / −411k | −188k / −492k |
| v2 tight sells, DA−RT | +11.00 (90%: +5.85..+16.12) | +10.66 (+5.12..+15.89) |
| v2 surplus sells | +0.83 (−0.64..+2.32) | −1.87 (−4.56..+0.72) |
| Tight + 500 MW trips | +24.79 | +25.55 |
| Buy band, RT−DA | +10.30 | +10.49 |

**Watch item: the surplus branch.** It has no edge on its own at either zone, and Ottawa Feb–Sep is negative. Dropping surplus sells to score 3 was tested. It raises $/MWh (10.7 East, 10.3 Ottawa), but net moves the wrong way at East (−$208k) and the right way at Ottawa (+$100k). That is mixed, so nothing was changed.

## Quebec
- **Flows:** Ontario exports to Quebec almost every hour, about 1,000 MW, nearly all on PQ.AT (Outaouais). Exports sit at ≥95% of the DA limit in 65% of hours. Imports are small (about 100 MW).
- **Explanatory regression**, DA basis on Quebec exports and imports, a near-limit flag, OZP, headroom and demand, over 12,168 hours:
  - East − OZP: **+2.36 $/MWh per GW exported** (day-bootstrap 90%: +1.77..+3.05).
  - Ottawa − OZP: **+6.32 per GW**.
  - East − Ottawa: **−3.93 per GW**. More exports pull Ottawa above East, which fits PQ.AT connecting on the Ottawa side.
  - OZP itself: no significant effect from exports (+1.1, t 0.8) once headroom and demand are in. Imports lower it (−5.1 per GW).
- **After the bid:** a cut in the RT PQ.AT export limit below the DA limit goes with DA > RT: about +$30 per GW cut at East and +$26 at Ottawa. Supply stays home in RT, which is the same pattern as the earlier limits study.
- **At the bid:** adding the bid-time PQ.AT DA limit and D-2 exports to the zone DA forecast made it worse (East MAE 12.82 → 13.15, Ottawa 14.31 → 14.83, walk-forward over 417 days). They are shown on the page as context only.

## East–Ottawa pair (sell East DA, buy Ottawa DA)
- **All hours:** P&L per MW = (DA_E − DA_O) − (RT_E − RT_O). Over 512 days it averages +1.30 $/MWh (+0.58..+2.07).
- **HE12–16:** these hours were first seen on Jul–Sep 2026. On the untouched May 2025 – Jun 2026 holdout they make +3.42 (+1.32..+5.68).
  - The win rate is only 33% and the median is −0.21.
  - At 85 MW a day averages +$1,452, worst −$18k, best +$116k.
  - Clipping hours to ±$50 leaves −0.21. All of the edge comes from Ottawa RT spikes: 102 hours on 36 days, mostly Nov–Jan and Apr–May, with PQ.AT exports at the limit.
- **Daily side choice:** choosing the side each day from the trailing 28 days did worse (+0.75; the 14-day version −0.23). The page therefore offers one fixed standing pair, off by default. The legs go into both hubs' ladders as a first tier (East offer at −$100, Ottawa bid at $2,000) and share the zone limits with the ladder.
- **Next step, not done:** a bid-time flag for Ottawa-area transmission outages (TxOutages archive, from Sep 2026) could pick out the spike days. It is not testable yet because the history is too short.

## Data pulled this round
- `data/nrg/_raw/nrg3_east_ott_qc.csv.gz` holds East/Ottawa/OZP DA, 5-min RT and PD, plus NRG "Quebec Export/Import Scheduled – DAA/Adq". It became `nrg2_EAST_*`, `nrg2_OTT_*` and `nrg2_OZP_*`, then `hub_prices_nrg.csv`, and the Quebec part became `data/qc_nrg_sched.csv`.
- The pull used a temporary NRGStream chart named "New Sep 28 2026 12:03" (id 299038) in your chart list, and it can be deleted. For GitHub, the daily job should use the NRGStream API stream IDs above.

## Quebec pulls, round 2 (`model/quebec2.py`, data/quebec/)
- **Sources:**
  - Warehouse HQ demand only covers Jan–Mar 2024, so it is not usable.
  - Hydro-Québec open data has hourly demand for 2019 to 2025-01-01, plus a rolling 2 days.
  - For 2025–26, demand is modelled from Open-Meteo temperature (Montreal .65 / Quebec City .35). Fit 2019–23, checked on 2024: MAPE 5.3%, R² 0.91. Tomorrow's value uses the forecast issued 2 days earlier, which is bid-safe (temperature forecast MAE 1.4 °C).
- **Findings:**
  - Quebec demand runs from about 17 GW in summer to 29 GW in January.
  - Ontario exports barely follow it (+19 MW per GW, daily corr 0.34) because PQ.AT is at its limit.
  - Hourly correlation of Quebec demand with the NY–HQ LBMP is 0.53, with the East basis 0.34 and with OZP 0.51: a winter price level.
- **At the bid:** when the Quebec demand forecast was more than 1 GW above last week, East DA settled $7.1 above our forecast (Ottawa $8.0), but DA−RT did not move (+1.6 / +0.2). Adding it to the DA forecast made it worse (East 13.05 → 13.51, Ottawa 14.64 → 15.23). Not used; re-test after this winter.
- **PQ.AT DA intertie LMP** (IESO, May–Sep 2026, 146 days), from IESO's DA intertie LMP file: the external congestion price is non-zero (export limit binding) in 38% of hours.
  - v2 sells in binding hours: East +0.15, Ottawa −5.64. In other hours: +10.52 / +9.79.
  - Same-day binding is only known after the bid. The D-2 flag, which is known at the bid, still splits East sells +1.93 vs +9.51 (difference 90%: −14.2..−0.9) and Ottawa +1.52 vs +5.54 (difference not significant).
  - Watch item only: one summer, 146 days.
- **HQ interchanges:** EIA ISNE/NYIS → HQT interchange and the NY HQ LBMP (NRGStream 192620 / 192625 / 4157) are in data/quebec/nrg3_hq_interchange.csv.
- **Still missing:** `pull_history.py --only adq2x` (bid-time scheduled exports by interface) was not in the cache. Run it, and the bid-time Quebec schedule gets tested the same way.

## Round 3 (Sep 28): adq2x tested, Quebec demand dropped
- **Modelled demand removed.** The temperature-modelled Quebec demand (round 2) is no longer on the page or in the model; only real data is used. `quebec2.py` is kept only for the PQ.AT intertie-LMP numbers.
- **adq2x** (`model/qc_adq2x.py`, `data/qc_adq2x.json`):
  - The pre-DA Adequacy vintage has no intertie bids, offers or schedules at all; they are 0% filled. IESO publishes them only after the DA run, so there is no bid-time Quebec schedule. The latest one known at the bid is D-2's.
  - The final DA Quebec export schedule matches actual PQ exports: corr 0.99, 1,040 vs 1,033 MW.
  - Quebec export bids average 1,732 MW, and bids exceed the schedule by more than 200 MW in 98.5% of hours. Quebec almost always wants more than the interties carry, so the DA export limit, known at the bid, is what matters.
  - **Bid-time test**, D-2 unscheduled Quebec bids above vs below their 30-day median, v2 sells, 17 months:
    - East: +5.06 vs +5.72.
    - Ottawa: +2.55 vs +5.33.
    - Same direction in both halves, but the ranges overlap, so not adopted.
- **Quebec demand history: what is needed.**
  - Hydro-Québec open data (`historique-demande-electricite-quebec`) has hourly demand for 2019–2024 only. The dataset was modified in June 2026 but still ends 2025-01-01.
  - HQ generation history (`historique-production-electricite-quebec`) covers 2019–2025. 2026 is not published.
  - The live feed (`demande-electricite-quebec`) keeps only about 2 days.
  - The Warehouse table `HydroQuebecDemand` stops at 2024-03-11.
  - The options:
    1. Ask the warehouse owner why the `HydroQuebecDemand` loader stopped in March 2024, and whether they archived HQ's live feed after that. If they did, a backfill gives real history immediately.
    2. Start archiving HQ's live 15-min demand feed daily now (the same idea as `ieso_backfill.py`). This builds real history from today only.
    3. Ask Hydro-Québec (open-data contact on the dataset page) for 2025–2026 hourly demand, or wait for their annual update.
    4. Buy history from a vendor that archives the HQ feed (for example Yes Energy, Enverus, or Wood Mackenzie/Genscape). NRGStream does not carry it: only NPCC weekly and the HQ interchanges.
  - Real Quebec demand would only matter if it explains East/Ottawa DA−RT beyond the DA export limit. Given the limit-bound result above, that is unlikely to be large.
