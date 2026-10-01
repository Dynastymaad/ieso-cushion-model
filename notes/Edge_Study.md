# Edge study — does the Ontario model give a tradeable signal? (2026-09-27)

Everything walk-forward: each day's signal uses only data public before that morning's 08:00 MT deadline.
RT is fully known only through D-2 at bid time, so thresholds and regressions learn from spreads settled by D-2.
Test window: Jul 20 – Sep 27 2026 (70 days, Toronto and Southwest). Prices from Jun 28. 1 MW per hour, no uplift.
Code: model/edge_study.py, model/edge_study2.py, model/signals_v2.py. Raw outputs: notes/edge_study_*.txt, notes/signals_v2_backtest.txt.
Hour-level files: data/es_da_errors_hourly_*.csv (every DA error), data/bt_signals_v2_*.csv (every signal hour and its DA−RT).

## 1. Sep 27: why v1 missed the short
Toronto DA−RT HE1–15: +8.0 −3.8 −1.8 +5.4 +5.2 +1.0 +5.2 +19.4 +17.8 +6.3 +1.1 +3.9 +10.1 +14.7 +17.0 (sum +108).
v1 only sold when headroom was < 8,500 MW in HE14–21, or when Tesla was ≥ 600 MW below IESO. On Sep 27 headroom was 9,800–12,700 MW and Tesla was above IESO, so v1 had no sell trigger. It was a **surplus** day: bid-time gas need was 2,540–2,820 MW in HE7–13, and the DA gas schedule came in at 1,780–2,615 MW. RT kept falling to $14.6 5-minute prices. HE13–15 also had wind 700–900 MW above the DA schedule, which no bid-time input could see.
v1's BUY in HE17–20 came from the Tesla ≥ +600 rule. Walk-forward, that rule made +$4.66 on 35 hours with a 90% range of −4.67 to +9.36, so it is not an edge. It was removed.
**v2 on Sep 27:** SELL-L HE1–17 (surplus, extended threshold 4,500 MW), no trade HE18–24. Settled so far: +$108.

## 2. DA forecast error — direction, individual numbers (Toronto, 1,704 h, Jul 19 – Sep 27)
Error = model − published DA (+ means the model was too high).
- Mean −0.48, median +0.23. Too high in 51.2% of hours, too low in 48.8%. There is no overall skew.
- Percentiles: 1% −33.3, 5% −15.2, 10% −9.6, 25% −3.9, 50% +0.2, 75% +4.5, 90% +9.5, 95% +13.4, 99% +20.4. The tail is on the low side: the model misses spikes.
- Histogram: ≤ −30: 26 h; −30 to −15: 62; −15 to −10: 70; −10 to −5: 199; −5 to −2: 263; ±2: 445; 2 to 5: 250; 5 to 10: 233; 10 to 15: 98; 15 to 30: 58; > 30: 0.
- By price level (conditional skew): DA < $30 → +3.5; $30–40 → +0.9; $40–50 → +1.6; $50–60 → +1.8; $60–80 → −2.2; $80–120 → −3.6; > $120 → −19.7 (54 h). The model compresses: slightly high in calm hours, low in spikes.
- By weekday: Mon −0.3, Tue −0.3, Wed +1.7, Thu −1.1, Fri +2.2, Sat −4.0, Sun −1.4. Saturday runs low in every block. A walk-forward day × block correction fixed the Saturday bias (−4.0 → −0.5) but raised the MAE (6.44 → 6.92), so it is not applied.
- By HE: HE12–13 mean −3.2/−3.4 (low); HE16–18 median +3.9 to +4.7 (high in normal evenings, low when they spike).
- Errors come in runs: daily error autocorrelation is 0.32 (Toronto). Subtracting 25% of yesterday's block error moves MAE only 6.44 → 6.38, so this was not adopted.
- Worst misses, model too low: Aug 7 HE12 (DA 201.6 vs 104.6), Sep 1 HE17–20 (−50 to −92), Jul 27 HE17–18, Aug 6 HE17–18. All are tight (headroom < 8,000) spike days.
- Worst misses, model too high: Aug 11 HE17–18 (+26 to +30), Aug 25 HE15–22 (+22 to +25), Jul 20 HE17–20.
The full daily table is on the page and in data/es_da_errors_daily_*.csv.

## 3. DA − RT: where the money is (Toronto, 92 days)
- All hours: mean +4.81, median +3.75, DA > RT in 62% of hours. But in the test window it was only **+1.06** (90% range −1.99 to +3.96), because the Jun 28 – Jul 19 spike days carried the full-sample number.
- Weekday afternoons and evenings favour selling (HE14–21 mean +11 to +29). Weekend middays favour buying (HE12–13 mean −5.6/−6.9, sells won only 30–44%).
- Largest losses on the sell side: Jul 4 HE18 (−594), Jun 30 HE20 (−441), Aug 7 HE17–19 (−242 to −432), Jul 27 HE18–20.

## 4. Signals, walk-forward (Toronto | Southwest), $/MWh [90% day-resampled range], hours
| rule | Toronto | Southwest |
|---|---|---|
| **v2 SELL core (tight or surplus)** | **+10.82 [+3.28, +17.53], 411 h, 74% win, 75% days up** | **+8.74 [+0.82, +15.57]** |
| v2 SELL-L extended hours | +3.31 [+0.92, +5.85], 268 h | +3.25 [+0.89, +5.71] |
| v2 core + extended | +7.85 [+3.39, +11.98], 679 h, total $5,332 | +6.57 [+2.08, +11.07] |
| tight only (headroom < learned threshold, 7,000) | +12.46 [+2.14, +22.17] | +9.34 [−1.90, +19.62] |
| surplus only (gas need < learned threshold) | +7.56 [+5.21, +9.75], 80% win | +7.54 [+4.83, +9.81] |
| every other hour, if sold | **−3.58 [−6.71, −0.62]** | −3.71 [−6.59, −1.00] |
| sell every hour | +1.06 [−1.99, +3.96] | +0.47 [−2.54, +3.28] |
| v1 rules (in-sample thresholds) | +3.45 [−1.77, +8.86] | +2.27 [−2.91, +7.65] |
| Tesla ≤ −600: sell | +1.86 [−0.45, +4.27] | — |
| Tesla ≥ +600: buy | +4.66 [−4.67, +9.36], 35 h | — |
| buy all non-signal hours | +3.58, but the median hour lost $1.78, it won 44%, and 5 days made 86% of the total → a spike lottery, not an edge | similar |
- By month (core SELL hours, Toronto): Jul +6.04 (median +6.27), Aug +8.38 (+15.61), Sep +24.41 (+23.96). Positive every month.
- Robustness: dropping each rule's 3 best and 3 worst days, core goes +10.86 → +11.68 and surplus +7.54 → +8.47.
- Regression "lean": the ranking is real (quintiles −2.99 / +0.13 / +0.77 / +1.73 / +5.70; permutation p = 0.003) but too weak to trade alone (sign hit rate 58.8% vs 61.6% for always guessing the majority side).
- Offer price, in core sell hours: price-taker +11.94/MWh, $3,880. Offer at P10: cleared 92%, +12.12, $3,611. At P25: 79%, +13.61, $3,485. At P50: 50%, +18.03, $2,921.
- Caveat: choosing between the two surplus-threshold methods (max-mean vs largest ≥ $3) was made after seeing both, which is mild selection. Both are shown.

## 5. The desk's own trades split by v2 (Toronto, Jul 20 – Sep 8, 48 days)
| | hours | MWh | $/MWh | P&L |
|---|---|---|---|---|
| Sells in v2 hours | 420 | 7,680 | **+15.97** | +$122,648 |
| Sells outside v2 hours | 708 | 10,734 | −0.68 | −$7,348 |
| Buys in v2 sell hours | 393 | 4,120 | **−9.20** | −$37,903 |
| Buys outside v2 hours | 519 | 6,206 | +4.47 | +$27,770 |
Almost all of the desk's sell profit came in v2 hours. Buying into a v2 sell hour cost $38k. The desk's own buy picks outside signal hours made money, and the model does not replicate that.

## 6. Generation: what moves DA − RT (ex post, Jun 28 – Sep 25, 2,160 h)
OLS: DA − RT per +1,000 MW of (actual minus what DA assumed). R² 0.31.
- Demand (actual − IESO pre-DA forecast): −18.3 $/MWh, corr −0.45. IESO over-forecasts in 73% of hours, median −313 MW, mean −377, largest HE6 and HE15–16 (−550).
- Wind (RT − DA schedule): +22.1, corr +0.15.
- Nuclear (RT − DA): +13.2.
- Net exports (RT − DA): −18.8, corr −0.15.
- Solar: ~0.
- Gas and hydro deviations are the system's response, not causes.
- DA price level follows the DA gas schedule (corr 0.64) and the hydro schedule (0.62).
- DA − RT by DA gas schedule: < 2 GW +10.5 (100% sell wins, 6 h); 2–3 GW +9.5 (79%); 3–4 GW +7.7 (79%); 4–5 GW +2.5 (66%); 5–6 GW −3.3 (53%); 6–8 GW +8.7 (61%); > 8 GW +41.6 (69%). U-shaped.
- Lennox running in RT: DA − RT +22.0 (456 h) vs +0.3 otherwise.
- Bid-time gas need (the gas_hat column) vs the DA gas schedule: corr 0.82, MAE 993 MW, bias +331.

## 7. Column checks
- Lennox %: recalibrated. Lennox actually ran in RT: 82% of hours with headroom < 6,000, 62% at 6–7k, 35% at 7–8k, 13% at 8–9k, 2% above 9k. The old page values (45/29/8/2/1) were too low.
- Tesla − IESO: Tesla MAE 414 MW vs IESO 549, bias +26 vs −377. DA − RT by gap band: ≤ −600 +13.2 (68% sell wins); −600 to −200 +3.1; ±200 −0.5; +200 to +600 +1.0; ≥ +600 −5.5 (36%, 50 h). It sorts hours in-sample but did not hold walk-forward, so it is information only.
- ON→NY (NYISO DAM net import from Ontario): corr 0.81 with IESO's actual NY flow, same sign 91%, 13,031 h. It adds no price skill beyond the NY price. Information only.
- RT − DA if the load miss is ±200–600 MW: overall medians are −4.8 (load low) and +5.4 (load high); 600+ low −15.0, 600+ high +13.0. Consistent with the OLS.

## 8. Limits
- One summer only: shoulder and winter regimes have not been seen post-MRP.
- Uplift is not deducted. If virtual-offer uplift is above ~$3/MWh, SELL-L is break-even.
- 70 test days. The core rule's 90% range is wide (+3 to +18).
- Wind surprises (Sep 27 HE13–15) cannot be forecast at bid time.
