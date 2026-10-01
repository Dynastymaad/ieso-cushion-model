# Ontario model v1 — backtest (2026-09-27)

Walk-forward throughout: every forecast uses only data that existed at the bid morning
(08:00 MT on D-1 for next day; the same morning at lead L for the outlook). Prices in CAD/MWh.
Scripts: `model/blocks.py`, `model/hourly.py`, `model/spread.py`, `model/trading.py`,
`model/horizon.py`, `model/run_model.py`.

## 1. Next-day DA, hourly — Toronto and Southwest (Jul 19 – Sep 27, 71 days, 1,704 h per hub)
| model | Toronto MAE | SW MAE | evening HE17–21 (Tor) | overnight HE1–6 (Tor) | MAPE (Tor) |
|---|---|---|---|---|---|
| yesterday's DA same hour | 10.42 | 10.53 | 17.99 | 3.73 | 16.9% |
| **v1 (hybrid + block-reconciled, averaged)** | **6.44** | **6.48** | 10.24 | 3.04 | 11.0% |
| hybrid alone | 6.36 | 6.44 | 10.35 | 2.98 | 10.8% |
Hybrid = per-block ridge on IESO pre-deadline headroom, NYISO Zone A DAM (posted 09:33 ET),
NYISO's scheduled NY–Ontario flow (P-30, 09:40–09:55 ET), weekend, yesterday's DA.
v1 averages it with the same shape rescaled to the all-season block model, because the
hourly history is summer-only and the block model is the one tested through winter.

**DA ranges are calibrated:** realised DA fell below the P10/P25/P50/P75/P90 forecasts in
10.7 / 24.7 / 50.1 / 74.5 / 89.8% of hours (Toronto; SW 10.1 / 25.6 / 50.5 / 73.5 / 89.5%).
Average P10–P90 width $21.

Live check, Sun 2026-09-27 (forecast as of 09-26 morning, DA published later): Toronto MAE
$4.02, SW $4.14, 71–79% of hours inside P10–P90.

## 2. DA by block, all seasons, lead 1–14 days (Dec 15 2025 – Sep 24 2026)
MAE in $/MWh. Model = 50/50 of (last DA moved by the change in IESO headroom, Dawn gas and
PJM West forward) and the Ontario Hub daily forward struck before the origin.
| lead (days) | on-peak persist | on-peak forward | **on-peak model** | off-peak forward | **off-peak model** |
|---|---|---|---|---|---|
| 1 | 17.45 | 14.48 | **12.86** | 9.32 | **7.66** |
| 2 | 22.50 | 17.03 | **14.84** | 12.48 | **11.08** |
| 3 | 26.62 | 19.75 | **17.03** | 14.66 | **11.94** |
| 5 | 32.60 | 21.72 | **19.87** | 16.85 | **13.51** |
| 7 | 40.36 | 28.41 | **26.37** | 18.47 | **14.98** |
| 10 | 40.28 | 35.67 | **32.49** | 21.57 | **18.16** |
| 14 | 48.41 | 37.67 | **36.89** | 24.09 | **21.54** |
Average prices in the window: on-peak $79, off-peak $48. The model beats the traded forward at
every lead: on-peak by 7–14% out to ten days and 2% at fourteen; off-peak by 11–20%. January is the worst month
for every method (≈$38 on-peak MAE next day, Dawn at $7).
- Tested and rejected: letting fundamentals overrule the forward when they disagree by
  more than 30% (the forward was closer in those cases, but reweighting did not improve the total).

## 3. Hourly DA out to two weeks — Toronto (Jul 1 – Sep 24)
| lead | model | forward × shape | last known same hour |
|---|---|---|---|
| 2 d | **12.94** | 15.35 | 21.96 |
| 3 d | **13.68** | 15.76 | 23.78 |
| 5 d | **14.04** | 15.54 | 23.00 |
| 7 d | **15.42** | 17.74 | 24.45 |
| 10 d | **17.50** | 19.44 | 28.23 |
| 14 d | **19.36** | 20.28 | 26.19 |
Southwest is within $0.3–0.8 of these.

## 4. Real-time (Jul 26 – Sep 27, 63 days)
- RT point forecast (P50): Toronto MAE **$18.02** (SW $17.66), vs $18.81 for "RT = forecast DA".
  RT hour-to-hour noise dominates; the value is in the range and the skew, not the point.
- RT ranges are calibrated: below P10/P25/P50/P75/P90 in 10.9 / 25.2 / 50.2 / 76.0 / 90.6% of hours.
  Average P10–P90 width $64 (vs $21 for DA).
- Predicting the size of RT − DA hour by hour did not beat a per-block median (corr ≈ 0.0–0.02).
  Spread money comes from *which hours to trade*, below.

## 5. Virtual trading — 1 MW per hour, Jun 28 – Sep 26 (91 days), no uplift/fees
| rule (bid-time inputs only) | Toronto $/MWh | win % | Toronto total | worst day | SW $/MWh |
|---|---|---|---|---|---|
| sell every hour | 4.80 | 62% | $10,447 | −$1,360 | 4.32 |
| sell HE14–21 | 11.29 | 68% | $8,159 | −$1,272 | 10.53 |
| **sell when headroom < 8,500 MW** | **14.73** | 68% | $11,431 | −$1,015 | 13.25 |
| sell when tight AND HE14–21 | 15.94 | 71% | $8,047 | −$1,272 | 14.87 |
| **sell when Tesla ≥ 600 MW below IESO** | 13.24 | 68% | $8,472 | **−$574** | 12.42 |
| buy when Tesla ≥ 600 MW above IESO | 5.52 | 64% | $276 (50 h) | −$81 | 5.73 |
| v1 combined (sell tight-eve or Tesla-low; buy Tesla-high & loose) | 11.70 | 67% | **$11,829** | −$1,344 | 10.88 |

By month (Toronto, $/MWh): the combined rule made +21.7 in July, +5.1 in August and +6.3 in
September. The three June days lost. **The thresholds (8,500 MW, 600 MW) were chosen by
looking at this same summer**, so treat the levels as in-sample until the live log confirms them.

**Offer price matters.** Selling tight evening hours with the offer at the model's DA P25
instead of at market cleared 75% of the hours, lifted $/MWh from $7.99 to $10.39 and kept
the total ($2,690 vs $2,755). Offering at P50 gives $15.38/MWh on 45% of the hours.

**Your own book, same period (public prices):** Toronto sells +$15.60/MWh on 27,667 MWh
(+$431k), Toronto buys −$3.08/MWh (−$44k), Essa sells +$8.75, Essa buys +$3.13, SW −$4.08
net on 1,080 MWh. The model agrees with the desk on selling and says buy far less often.

## 6. What is still weak
- Winter: hourly prices exist only since Jun 28, so the hourly model has not seen winter;
  the block model has, and its January error is ~3× the summer error.
- RT spikes: no method predicts individual spike hours; they are handled as range, not point.
- Uplift on virtual offers (CT 1852) is not in the P&L.
