# What the full history says (2026-09-26)

Data: IESO archive (90 days of hourly prices), Warehouse load/wind/solar vintages since
2024-06, Adequacy2 pre-deadline vintages since 2025-05-02, settled daily Ontario Hub DA
blocks since 2025-05-13. Scripts: `model/parse_archive.py`, `model/load_edge.py`,
`model/block_test.py`. Tags as before: [M] measured, [S] structural, [J] judgement.

## 1. Clocks — every source pinned down [M]
| source | EffectiveDateTime means | usable at bid time if |
|---|---|---|
| IESO, Tesla (Warehouse) | EST, hour-**beginning** (HE = +1h) | loaded (DateCreated ~04:28) on or before D-1 |
| DYNASTY (Warehouse) | EST, hour-beginning; **no UTC column** | issued (Timestamp) before D-1 08:00 |
| Meteologica (Warehouse) | Eastern **prevailing** (EDT in summer), hour-beginning | loaded on or before D-1 |
| Adequacy2 archive | IESO HE, EST; `ieso_createtime` in EST | issued before D-1 09:00 EST (the 07:49 run) |
| Ontario Hub daily settles | on-peak = IESO HE7–22 (= HE8–23 EPT) | only rows struck **after** the strip day |
Alignment chosen by minimum error against IESO actual Ontario Demand (wrong-hour MAE is 2× worse).

## 2. Load forecasts at the deadline — 505 days [M]
| source | hours | MAE MW | bias (fc − actual) |
|---|---|---|---|
| IESO Adequacy2 (what DA clears on) | 12,265 | 428 | **+236** |
| IESO (Warehouse vintage) | 12,035 | 472 | +205 |
| **Tesla** | 12,264 | **359** | −18 |
| DYNASTY | 9,122 | 369 | −16 |
| Tesla + DYNASTY average | 9,122 | **345** | −16 |
| Meteologica | 481 | 241 | 0 (only 3 weeks — not yet conclusive) |

- **When Tesla disagrees with IESO by more than 300 MW, it is right about the direction of IESO's miss 81% of the time** (6,741 hours). DYNASTY 80% (4,115 hours). About two-thirds of the gap shows up in the outturn (slope 0.66).
- Tesla beats IESO in 13 of 17 months; IESO is better in Nov-2025, Feb-2026, Mar-2026 and Sep-2026, and Apr-2026 is a tie.
- Bias-correcting IESO helps it (472 → 443) but it still trails Tesla.

## 3. Does that turn into RT − DA money? (90 days, Toronto) [M]
- IESO's *actual* miss drives the spread strongly: rank corr **0.52**; a miss of +600 MW or more gives RT > DA 84% of the time (median +$13); −600 or worse gives RT < DA 87% (median −$15).
- **But Tesla's gap to IESO at bid time only weakly predicts the spread (rank corr 0.15)**, even though it predicts the miss well. The useful part is at the extremes:
  - Tesla ≥ 600 MW **below** IESO (640 h): mean −$13, RT < DA 68%.
  - Tesla ≥ 600 MW **above** IESO (50 h): RT > DA 64%.
  - In between: nothing tradeable.
- [J] The common part of the miss is already priced — virtual sellers (net ~117 MW/h at Toronto) are trading the same IESO over-forecast. The edge is the *size* of the gap on the day, not its existence. DYNASTY adds little over Tesla on the spread.

## 4. DA level over 355 weekdays (settled on-peak blocks) [M]
- **The summer "level curve" does not generalize.** Fitting DA against headroom on a rolling window loses to simply repeating the last settled DA: $21–25 vs $17.5–18.4 MAE. It breaks worst in winter (Jan-2026 averaged $145 on-peak with Dawn at $7).
- **An anchored "delta" model wins:** start from the last settled DA and move it by the change in headroom and in Dawn gas. MAE **$14.26 vs $17.56** for persistence (−19%), better on 65–70% of days, and better in 12 of 14 months including Jan/Feb.
- Months where it did not beat persistence: Dec-2025 and Mar-2026 (regime turns).
- Monthly averages show the regimes the model must carry: spring collapse (mid-May-25 off-peak $4–15, on-peak as low as $16), summer peaks ($97–100 July), and a gas-driven winter ($107–145, Dawn $4–7).

## 5. What this changes in the build
1. DA model v1 = **anchor on the last settled DA + delta from fundamentals** (headroom change, Dawn change, NYISO DAM), with the hourly shape from recent days. Not a free-standing level curve.
2. Spread signal = **Tesla − IESO gap, used only when it is large** (≥ 600 MW), sized by the miss grid and headroom.
3. Winter needs its own attention: gas price and heating load dominate; test NYISO/PJM and weather there first.
4. Keep archiving daily — the hourly RT/spread history is the binding constraint.

## 6. Tests run on 2026-09-26 (second pass)
**NYISO early intertie read [M].** NYISO's DAM Daily Energy Report (P-30) posts the NY-side
scheduled net imports at the Ontario proxy (`Net Imports DNI OH`) at 09:37–09:56 ET on D-1
(10:06 on one day in the last month) — before the IESO 10:00 ET close on most days.
- vs IESO's own NY schedule for the same hour: correlation **0.83**, MAE 226 MW (90 days).
- vs Ontario's **total** net exports: correlation **0.71**. IESO's pre-deadline Adequacy has no
  export schedules at all, so this is information IESO's forecast does not contain.
- Adding it to the hourly DA price model did **not** lower the error beyond what the NYISO
  Zone A DAM price already gives (6.46 → 6.52). The price already carries the flow. Keep it as
  the intertie forecast (and for the RT view), not as a separate price input.

**Hourly DA, Toronto, 71 test days (Jul 19 – Sep 27), same hours for every model [M]:**
| model | MAE | evening HE17–21 |
|---|---|---|
| yesterday same hour | 10.42 | 17.99 |
| headroom curve | 7.15 | 10.93 |
| + NYISO Zone A DAM | 6.46 | 9.89 |
| + NYISO + NY intertie | 6.52 | 10.22 |
| + Tesla gap | 6.78 | 10.61 (Tesla helps RT, not DA — DA clears on IESO's number) |
| hybrid: + yesterday's DA | **6.36** | 10.26 |

**Next-day on-peak, 294 weekdays across all seasons [M]:**
| model | MAE |
|---|---|
| last settled DA | 17.56 |
| anchored delta (headroom, gas) | 14.26 |
| Ontario Hub forward, struck D-2 | 13.81 |
| **50/50 of the two** | **12.52** |
The market's forward and the fundamentals are complementary; neither alone is best.

**2-week horizon benchmark [M]:** the Ontario Hub daily forward curve beats "last settled DA"
at every lead (lead 2 d: $14 vs $26; lead 7: $21 vs $36; lead 14: $30 vs $40, on-peak weekdays).
That forward curve is the bar the 2-week view has to clear. Testing the fundamentals model at
those leads needs `pull_history.py --only horizon` (Adequacy2 vintages at 2–15 days lead,
Tesla/IESO load and wind out to 16 days).
