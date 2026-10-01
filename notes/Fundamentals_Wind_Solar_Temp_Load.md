# Ontario fundamentals: wind, solar, temperature and load: how to form your own view

Numbers are measured on our own data, May 2025 - Sep 2026: IESO actual load, Toronto Pearson (CYYZ) weather, IESO pre-DA Adequacy forecasts, IESO hourly output by fuel, and East DA/RT. Hours are IESO hour-ending EST.

---

## 0. The one idea that ties it together

Everything below matters through one number: **headroom**, meaning how much flexible supply is left once the system has met load.

> headroom = gas available + hydro available − (demand − nuclear − wind − solar)

- More load lowers headroom. So do less wind, less solar and more outages.
- DA is set on the bid-time picture. RT is set on what actually happens.
- You make money when you judge, better than DA does, how the real hour will differ from the bid-time forecast. You do not make money just by knowing what the forecast says.
- So for every driver, ask two questions:
  1. **Level:** is it high or low vs normal? DA mostly prices this already.
  2. **Surprise:** which way is the forecast likely to be wrong? This is what moves RT against DA.

How RT−DA moves per 1 GW of surprise (East, all hours):

| Surprise of 1 GW... | RT−DA, all hours | Tight (< 7,000 MW headroom) | Middle (7,000-9,500) | Loose (> 9,500) |
|---|---|---|---|---|
| Load comes in **higher** than IESO forecast | **+$28** | +$38 | +$30 | +$19 |
| Wind comes in **higher** than IESO forecast | **−$32** | −$57 | −$45 | −$21 |

- A 1 GW wind miss moves price about as much as a 1 GW load miss, and slightly more.
- Both effects roughly double when the system is tight.
- The DA level itself barely reacts to the wind forecast: about −$2 per GW, after allowing for demand. DA treats wind as known. **The money is in the wind surprise, not the wind level.**

---

## 1. Load: how to read it

### What IESO's "Ontario Demand" is
- It is load served by the **transmission grid**.
- **Embedded (behind-the-meter / distribution) solar and wind are netted out.** They look like lower demand, not like supply.
- Exports are **not** included. "Market Demand" = Ontario Demand + exports.
- Use Ontario Demand for fundamentals. Treat exports separately (see the NY panel).

### The usual daily shape (Sep-Oct, MW)

| | Overnight low (HE3-5) | Morning (HE8-10) | Midday (HE12-14) | Evening peak (HE18-19) | Late (HE23) |
|---|---|---|---|---|---|
| Weekday | ~13,400 | ~16,100 | ~16,400-16,700 | **~18,050** | ~15,400 |
| Weekend | ~12,900 | ~14,000-14,700 | ~15,300-15,600 | **~17,050** | ~14,600 |

- Weekends run about **1,000 MW lower** at the peak and up to **2,000 MW lower** in the morning ramp, because there is no commute or commercial load.
- The evening peak is driven by lighting and cooking as it gets dark. In October it **moves earlier and gets sharper** as sunset comes forward. Oct 2 peaks at HE19.
- Holidays behave like a Sunday. Thanksgiving is Mon Oct 12, 2026.

### IESO's forecast runs high

Since May 2025, actual load minus the pre-DA forecast:

| Month | Avg miss (MW) | Month | Avg miss (MW) |
|---|---|---|---|
| Jan | −319 | Jul | **−412** |
| Feb | −176 | Aug | **−417** |
| Mar | −130 | Sep | −226 |
| Apr | −193 | Oct | −64 |
| May | −114 | Nov | −78 |
| Jun | −211 | Dec | −186 |

- The miss is largest in summer heat. October has historically been almost unbiased.
- Since July the peak (HE16-20) has run about −470 MW.
- **What to do with it:** don't take IESO's number as the centre. Compare it to Tesla. Tesla has been close to unbiased: −29 MW overall, +102 at the peak, MAE 539 vs IESO's 636.
- **Tesla − IESO, vs its usual gap, is the best single predictor of IESO's miss we have found** (corr 0.56; see Weather_and_Outage_Data.md). A temperature forecast alone hardly helps (corr 0.15), because IESO already uses the weather.

### Load checklist
1. **Day type:** weekday, weekend or holiday? Is this hour on the morning ramp, at midday or at the evening peak?
2. **Peak size:** IESO's peak vs the same weekday last week. A change of more than ±1,000 MW needs a reason: weather, a holiday or a data glitch.
3. **Tesla − IESO by hour vs the usual gap.** The page shows this. More than +150 MW above the usual gap means "load risk up"; more than −150 below means "load risk down".
4. **Size it:** with headroom around 7,500, a +300 MW load miss is roughly a +$9 RT move (+$30/GW). The same miss in a tight hour is about +$11.

---

## 2. Temperature

HE18 weekday load vs Toronto temperature:

| Temperature (°C) | Load (MW) | Temperature (°C) | Load (MW) |
|---|---|---|---|
| −15 to −10 | 21,490 | 15 to 18 | 16,540 |
| −10 to −5 | 20,520 | 18 to 21 | 17,290 |
| −5 to 0 | 20,000 | 21 to 24 | 18,900 |
| 0 to 5 | 18,820 | 24 to 27 | 20,830 |
| 5 to 10 | 17,310 | 27 to 30 | 21,770 |
| 10 to 15 | **16,220 (the low point)** | > 30 | 23,630 |

- **The low point is 10-18°C.** In that range a few degrees of forecast error barely moves load. **October sits right here**, so temperature is a weak driver this month and darkness / day type matters more.
- **Cooling side (above ~20°C): about +490 MW per °C.** This is the strongest weather effect in the province. A 3°C heat miss is about 1,500 MW, enough to turn a loose day tight.
- **Heating side (below ~12°C): about −220 MW per °C,** so roughly +220 MW per degree colder. That is weaker than cooling because most Ontario heating is natural gas, not electric. It strengthens below about −10°C.
- **Humidity** (dew point) adds to the cooling effect. A 30°C day with a 22°C dew point loads more than a dry 30°C day.
- **Where:** Toronto carries about 40% of the load weight. Ottawa is 16%, and Hamilton, London and Barrie are 12% each. A heat or cold miss in Toronto matters most.
- **Your view:** compare tomorrow's forecast high and low with the last few days. Ask whether it sits on the flat part of the curve (10-18°C) or on a steep part. On a steep part, a 2-3°C forecast bust is your load risk. Cold snaps and heat waves also lift gas prices, which raises the cost of the marginal gas unit.

---

## 3. Solar (and cloud cover)

Ontario has two kinds of solar:

| | Size | Where it shows up |
|---|---|---|
| **Grid (transmission) solar** | ~478 MW capacity | In supply ("Solar Forecast"). Midday output ~300 MW in summer, ~280 in Oct, under 100 in Dec-Jan. |
| **Embedded (distribution) solar** | Midday output ~700-750 MW in summer, peaks ~1,000 | Hidden inside demand: it lowers Ontario Demand. ~640 midday in Oct, ~220 in Dec. |

Midday weekday load at the same temperature (18-27°C, Apr-Sep), by cloud cover:

| Cloud cover | Load | Embedded solar | Grid solar | IESO miss |
|---|---|---|---|---|
| 0-25% (clear) | 16,780 | 850 | 371 | −325 |
| 25-75% | 17,600 | 705 | 303 | −308 |
| 75-100% (overcast) | **17,990** | 527 | 224 | −642 |

- **Overcast midday load runs about +1,200 MW above clear-sky load at the same temperature.** About 450 MW of that is lost solar: roughly 320 MW embedded and 150 MW grid. The rest is cloudier days being muggier or darker, so more lighting.
- IESO already expects this. On cloudy days it over-forecasts *more* (−642 MW). **Clouds are not a free edge.** What matters is clouds that were not in the forecast.
- **When it matters:** HE10-16, Apr-Sep. Solar is nearly irrelevant to the evening peak in October, because the sun is down by about HE19.
- **Your view:** check the cloud-cover forecast for southern Ontario midday. A sunnier-than-forecast day lowers midday load and RT, which is bearish. A sudden overcast day is bullish midday.

---

## 4. Wind

- **Capacity:** about 4,940 MW of grid wind, plus a little embedded wind.
- **Seasonal pattern (actual monthly mean):**

| Jul | Aug | Sep | Oct | Nov | Dec | Jan |
|---|---|---|---|---|---|---|
| 805 | 790 | 861 | 1,514 | 2,158 | 2,312 | 2,316 |

  - Summer is calm. **October is the turn into the windy season.**
  - The largest hour on record here is 4,509 MW.
- **IESO's pre-DA wind forecast:**
  - Bias: −56 MW. It is slightly too high.
  - MAE: 267 MW.
  - Misses by more than 500 MW in 14% of hours, and by more than 1 GW in 2%.
  - Misses are largest in spring and winter (MAE 300-365) and smallest in Jul-Sep (~200).
- **Why it matters:** wind sits at the bottom of the supply stack, so every MW of wind displaces gas at the margin. A 1 GW over-delivery lowers RT−DA by about $32, and by $57 in tight hours.
- **Pressure and wind:**
  - High pressure overhead means light winds and calm, often clear nights. Wind is low and the evening is tighter.
  - A frontal passage or low pressure means strong, gusty wind, so wind runs high.
  - The surprise risk is **front timing**. If the front arrives 6 hours early or late, the forecast can bust by 1-2 GW.
- **Ramps:** watch the 3-hour change into the evening peak. Wind falling 300+ MW per 3 hours into HE17-20 tightens the peak just as load rises. On Oct 2, wind falls about 300 MW per 3 hours through the evening.
- **Your view:**
  1. Compare IESO's wind forecast with Meteologica (both are on the page) and with a weather model such as ECMWF or GFS on Windy / Open-Meteo, at Lake Huron and Lake Erie (where most of the turbines are).
  2. If the vendors disagree by more than 300-500 MW, a forecast miss is likely, and the side to lean is the vendor with the better recent record.
  3. Check whether a front is due around the peak.

---

## 5. Putting it into a view (10-minute routine before opening the model)

1. **Calendar:** weekday, weekend or holiday? Month and season, which tells you where you are on the temperature curve?
2. **Load:**
   - IESO's peak vs last week.
   - Tesla − IESO vs the usual gap.
   - Write down your own peak estimate: the **average of Tesla and (IESO + IESO's last-30-day bias)**. See Step 2 below; the earlier "IESO + (gap − usual gap)" formula tested worse and is withdrawn.
3. **Temperature:** flat part of the curve (10-18°C) or a steep part? How big is a plausible bust, in MW?
4. **Clouds** (Apr-Sep midday only): clearer or cloudier than normal, and does the forecast agree?
5. **Wind:**
   - Level vs the season (Oct ~1,500).
   - IESO vs Meteologica gap.
   - Front timing.
   - The evening ramp.
6. **Supply** (the Outages tab): nuclear and gas outages vs 30 days. Is anything due to start or end in the peak?
7. **Net it:** your expected headroom at the peak, plus the direction and size of the most likely surprise, converted at about $30/GW (load) and $32-45/GW (wind).
   - "Surprise points to tighter, and DA looks relaxed" → leans long.
   - "Surprise points to looser, and DA looks scared" → leans short.
8. **Then** open the model and see where you agree and disagree. A disagreement is only worth acting on if you can name the fundamental behind it.

### Oct 2 worked through quickly
- Friday, the first week of October.
- Peak at 16,885 MW, about 1,900 MW below Oct 1. Normal for a cooler Friday.
- Temperature sits on the flat part of the curve, so it is a low-weight driver.
- Solar does not matter for the evening.
- Wind is at 1.2-1.8 GW, about seasonal. Meteologica is 100-300 MW above IESO, which points slightly looser. Wind falls into the evening, which points slightly tighter.
- Nuclear outages are thin, at a 30-day high. No new outages start in the peak.
- Tesla could not be read today: the data is stale.
- **My read:** fairly priced. The only real upside surprise is a trip. That is consistent with the model's low-conviction buy.

---

## Where to look

| What | Where |
|---|---|
| IESO demand, wind, solar, outages | IESO Adequacy report (the page's stack table); ieso.ca → Power Data |
| Tesla / Meteologica | The desk page (Tesla panel; supply-stack table) |
| Temperature, dew point, cloud, wind fields | Open-Meteo or Windy (ECMWF / GFS) at Toronto, Ottawa, Lake Huron and Lake Erie. The checklist workbook pulls these. |
| Pressure and fronts | Environment Canada surface analysis; Windy's "pressure" layer |
| Real-time check | gridstatus.io / IESO real-time output by fuel |

---

## Step 1 in detail: the calendar and the temperature curve (added Oct 1)

Use the daily **average** at CYYZ, (max + min) / 2 in °F, which is what the StormVista max/min plot gives you.

**Daily peak load (MW) by daily average temperature and day type, May 2025 - Sep 2026:**

| Avg °F | Mon | Tue-Thu | Fri | Sat | Sun | Holiday |
|---|---|---|---|---|---|---|
| 10-20 | 21,190 | 21,010 | 20,370 | – | 20,840 | 19,910 |
| 20-30 | 20,250 | 20,190 | 19,610 | 19,390 | 19,780 | 18,750 |
| 30-40 | 18,630 | 19,200 | 19,550 | 18,400 | 17,920 | – |
| 40-50 | 17,600 | 17,160 | 17,390 | 16,820 | 16,500 | – |
| 50-55 | 16,750 | 16,880 | 16,110 | 15,210 | 15,420 | 15,270 |
| 55-60 | 16,950 | 16,900 | 16,350 | 15,600 | 15,350 | 15,440 |
| 60-65 | 17,830 | 17,490 | 17,820 | 16,020 | 16,930 | 17,920 |
| 65-70 | 19,610 | 19,100 | 18,920 | 18,490 | 18,390 | 19,320 |
| 70-75 | 21,510 | 21,370 | 21,750 | 19,580 | 20,440 | 19,920 |
| 75-80 | 22,970 | 22,690 | 22,400 | 21,890 | 24,060 | 21,020 |
| 80-90 | 24,570 | 24,150 | 23,860 | 23,040 | 23,010 | 23,830 |

### Season and month: how steep the curve is where you sit
- **Flat zone, about 50-62°F average.** Load barely reacts. October and May live here.
- **Hot side (above ~65°F average):** about **+350 MW per °F** on weekdays and +320 on weekends.
- **Cold side (below ~50°F):** about **+120 MW per °F colder**, the same on weekdays and weekends.

### Day type: shifts the whole curve up or down
The slope stays about the same; the level moves. Peak vs Tue-Thu at the same temperature:

| Mon | Fri | Sat | Sun | Holiday |
|---|---|---|---|---|
| +30 | −90 | **−1,020** | −840 | **−1,370** |

### Day type: how IESO's forecast and the price behave

| Day type | IESO miss, all hours | IESO miss, HE16-20 | RT−DA, all hours | RT−DA, HE16-20 |
|---|---|---|---|---|
| Mon | **−398** | −463 | −3.4 | −1.7 |
| Tue-Thu | −287 | −336 | −2.3 | −1.1 |
| Fri | −195 | −113 | −2.0 | −1.9 |
| Sat | −97 | −103 | **+5.6** | +3.2 |
| Sun | −91 | −148 | +1.0 | −6.0 |
| Holiday | −190 | −235 | **+10.8** | **+26.9** (only 14 days) |

### Plausible temperature bust
- At D+1 the forecast is good. Open-Meteo's 2-day-old Toronto forecast had an MAE of 2.9°F, and about 2.3°F load-weighted.
- So budget **±3°F**:
  - In the flat zone, that is about ±0-300 MW.
  - On the hot side, about ±1,000 MW.
  - On the cold side, about ±350 MW.
- When the models (ECMWF vs GFS) disagree by more than 5°F for tomorrow, budget the full spread.


---

## Step 2 in detail: reading load (added Oct 1)

Tested on daily peaks, Jun 2025 - Sep 2026. Daily peaks avoid any hour-alignment problems.

### Which peak forecast to trust

| Daily peak estimate | Bias | MAE | MAE H1 / H2 | Misses > 500 MW |
|---|---|---|---|---|
| IESO (Adequacy, at the bid) | +165 | 441 | 436 / 445 | 29% |
| IESO + its last-30-day bias | 0 | 433 | 424 / 443 | 30% |
| Tesla | −6 | 384 | 362 / 410 | 28% |
| **Average of Tesla and (IESO + bias)** | −4 | **364** | **352 / 377** | **24%** |

- **Use the blend.** It beats every single forecast in both halves.
- The checklist's first formula, IESO + (Tesla gap − usual gap), is **worse**: bias +237, MAE 507. It adds IESO's bias back in. It is withdrawn.

### Tesla − IESO vs its usual gap
Peak HE16-20, "usual" = the last-30-day median gap for that hour:

| Tesla gap vs usual | Hours | IESO's actual miss | RT−DA mean | RT−DA median |
|---|---|---|---|---|
| ≤ −300 MW | 594 | −701 | −4.3 | −19.5 |
| −300 to −150 | 275 | −240 | −8.5 | −18.1 |
| ±150 | 614 | −207 | −0.8 | −14.5 |
| +150 to +300 | 281 | −103 | +3.8 | −13.8 |
| ≥ +300 MW | 608 | +26 | +3.1 | −11.8 |

- Correlation with IESO's miss: 0.53.
- When Tesla sits well below its usual gap, IESO over-forecasts by about 700 MW. When Tesla sits well above it, IESO is about right.
- That is worth roughly $7-12/MWh of RT−DA at the peak.
- Use it as a tilt, not a trade on its own.

### IESO peak vs last week (same weekday)
- This is a sanity check, not a predictor. The typical gap is ±980 MW, and only part of it comes from the temperature change (correlation 0.22).
- Use it to ask "why is tomorrow different?":
  - The temperature moved onto or off a slope.
  - It is a holiday.
  - A data problem.
- A gap of more than about 1,500 MW with no reason is worth a second look.

### Oct 2
- IESO peak: 16,885.
- IESO + 30-day bias (−203): about 16,680.
- Tesla, from the stale Sep 30 run: 16,865.
- **Blend: about 16,770.**
- Last Friday (Sep 25, also a 58°F average) actually peaked at 16,956 at HE18.
- **View: 16,700-16,950.** That is in line with IESO, with no load surprise expected.


---

## Step 3 in detail: temperature busts (added Oct 1)

Tested with the load-weighted forecast as it stood two days before (Open-Meteo previous runs), against the actual, May 2025 - Sep 2026. Your StormVista D+1 run is newer, so expect its errors to be a little smaller.

**How often the daily-average forecast misses**

| Zone (by forecast) | Days | Bias (actual − forecast) | MAE | Miss > 3°F | Miss > 5°F |
|---|---|---|---|---|---|
| Cold side (< 50°F) | 206 | +0.4°F | 1.5°F | 11% | 1% |
| Flat (50-62°F) | 97 | +1.35°F | 2.0°F | 26% | 5% |
| Hot side (> 62°F) | 210 | +0.7°F | 1.6°F | 13% | 2% |

- Forecasts run slightly **cool**: the day comes in warmer.
- Busts are most common in the shoulder (flat zone), which is exactly where they matter least.

**What a 1°F miss does at the peak (HE16-20)**

| Zone | IESO miss per °F warmer than forecast | RT−DA per °F |
|---|---|---|
| Cold side | −28 MW | −$4.0 |
| Flat | +42 MW | +$0.5 |
| Hot side | +118 MW | **+$5.5** |

These effects are smaller than the curve slope suggests, because IESO's 07:50 forecast already uses a newer weather run.

**Hot side, by size of the miss**

| Actual vs forecast | Days | IESO miss | RT−DA mean | RT−DA median |
|---|---|---|---|---|
| 1-3°F cooler | 39 | −655 | −11.6 | −18.4 |
| ±1°F | 83 | −451 | −2.3 | −18.3 |
| 1-3°F warmer | 60 | −399 | −3.7 | −18.1 |
| **> 3°F warmer** | 26 | **+113** | **+35.8** | −0.4 |

- **Cold side:** more than 3°F colder than forecast gave +$71 RT−DA, but on only 4 days. Warmer than forecast gave −$8 to −$16.

**The read**
- Ask which zone you are in.
- In the flat zone, move on.
- On the hot side, the risk that matters is a **warm** bust: more than 3°F hotter happens on about 1 hot day in 8, and has been worth about +$36 RT−DA.
- On the cold side, the risk is a **cold** bust.
- Confidence comes from the model spread. If ECMWF and GFS (StormVista) disagree by more than 3-5°F for tomorrow, treat a bust as live.
- Forecasting the direction of the bust yourself is not tested. Don't trade it on its own.


---

## Step 4 in detail: clouds (added Oct 1)

Tested on midday HE11-15, May 2025 - Sep 2026. Toronto cloud cover: the 2-day-old forecast vs the actual.

- The cloud forecast is often wrong: MAE 24 points in Apr-Sep, and a miss of more than 30 points on 34% of days.
- **The misses did not move price.**

| Apr-Sep, actual vs forecast | Days | IESO load miss | Embedded solar | RT−DA |
|---|---|---|---|---|
| Much clearer (> 30 pts) | 97 | −265 | 741 | −3.2 |
| Clearer | 76 | −434 | 692 | −8.3 |
| As forecast | 108 | −242 | 608 | −2.8 |
| Cloudier | 33 | −189 | 661 | +3.3 |
| Much cloudier | 15 | −385 | 684 | −6.0 |

- Per +10 points cloudier than forecast: 0 MW of load and −$0.12 RT−DA.
- Oct-Mar: +38 MW and +$2, on small samples.
- **Why:** IESO re-forecasts with newer weather by 07:50, and Ontario's solar is small (~1 GW midday all-in). A 30-point cloud miss is worth about 100-150 MW, which is lost in the noise.
- **The read:** glance at it and move on. It only matters in a tight midday hour (headroom < 7,000 at HE11-15), where 150 MW can tip things. Even there, it has not been tested as an edge.


---

## Step 5 in detail: wind (added Oct 1)

### Which wind forecast to trust
Bid-time vintages against actual grid wind, Mar 20 - Sep 30 2026. That is the only period with Meteologica: 4,536 hours, one season.

| Forecast | Bias (MW) | MAE (MW) |
|---|---|---|
| **Meteologica** | +31 | **244** |
| IESO | +55 | 262 |
| Frontier | +56 | 378 |
| NAM | −15 | 423 |
| GEM | +122 | 443 |
| StormVista ECMWF | +331 | 446 |
| GFS | +322 | 517 |

- **Use IESO and Meteologica for the MW.**
- The raw weather-model conversions (GFS, ECMWF, GEM) run 300+ MW high, with roughly double the error.
- Use those weather models (Windy, StormVista) for **front timing and direction only**, never for the MW.

### Meteologica vs IESO gap → what happened

| Meteologica − IESO at the bid | Hours | Actual − IESO | RT−DA mean | RT−DA median |
|---|---|---|---|---|
| ≤ −500 | 92 | −416 | +0.6 | −3.9 |
| −500 to −200 | 691 | −260 | +2.1 | −3.1 |
| ±200 | 3,164 | −37 | −0.4 | −3.7 |
| +200 to +500 | 502 | +128 | **−4.6** | −10.4 |
| ≥ +500 | 87 | +271 | −2.8 | −10.6 |

- About **60% of the gap shows up**. When Meteologica is higher, expect more wind than IESO says, and vice versa.
- The price effect is in the right direction but small: about ±$3-5. It is a tilt, not a trade.
- Only 6 months of data. At the peak (HE16-21) the pattern is noisier.

### Evening ramp (IESO forecast, HE15 → HE20) → RT−DA at HE17-20

| Ramp | East H1 / H2 | Ottawa H1 / H2 |
|---|---|---|
| Wind falls > 300 MW | +3.8 / **+13.2** | −8.8 / +14.2 |
| Flat (±300) | −11.3 / −7.7 | −5.3 / −5.0 |
| Wind rises > 300 MW | +1.0 / −7.8 | +0.4 / +2.7 |

Days: 45/77 falls, 129/120 flat, 55/30 rises.

- **East:** a falling-wind evening has beaten a flat one by +$15 (H1) and +$21 (H2).
- **Ottawa:** only in H2.
- Most likely reason: wind falling while load ramps up forces gas units to start in real time.
- This is already in the model as the "Wind 3h ramp" lean. Use it as a lean toward longs or away from sells at HE17-20, not as a rule.

### Level vs the season
- Wind well above normal (> +500 MW vs the month's average) has the **largest** errors (MAE 343 vs 202 when low).
- Windy days are the uncertain days, but the level on its own does not move RT−DA (−$1.9).

### Pressure and fronts
- A big pressure change through the day (the page flags more than 8 hPa) means a front is passing.
- That is when the 1-2 GW wind busts happen.
- Check the front's timing on Windy or StormVista. A front arriving early or late around HE17-20 is the risk.

### The read
1. Take IESO and Meteologica.
2. If they are 200+ MW apart, lean about 60% toward Meteologica.
3. Note whether wind falls into the peak (bullish evening).
4. If a front is passing, widen your uncertainty.

**Oct 2:**
- Meteologica +209 vs IESO, so slightly soft.
- Wind falls about 460 MW HE15→20, so firmer evening.
- Pressure +13.7 hPa, so a front is moving through.
- Net: the two wind signals roughly cancel, and the front makes the evening uncertain.
