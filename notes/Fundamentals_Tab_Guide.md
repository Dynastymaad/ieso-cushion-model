# Fundamentals tab: what every column means and how much it matters

## Overview
- All numbers are **bid-time forecasts**, the ones we bid on (IESO 07:49 report, vendor forecasts loaded before 08:00 MT).
- Hours are **hour-ending EST**: HE19 = 18:00–19:00 EST (19:00–20:00 EDT).
- The key distinction: **DA already sees these numbers.** A column "matters" only if it helps predict whether **RT ends above or below DA**, not whether prices are high.

## Importance (from the tests in notes/)
| Importance | Columns | Why |
|---|---|---|
| **High** | Tesla − IESO; Fundamentals read; Headroom; Last 7d RT − DA | These had measurable power to predict RT − DA after DA has priced the day. Tesla − IESO is the load-miss signal behind Oct 1, 7 and 8. |
| **Medium** | Wind (IESO / Meteo / models); CAHR; Gas spare + ramps; Evening ramp note; Net exp | They explain spikes physically, but DA mostly prices them. They matter when they combine: windy forecast + Tesla above IESO; steep ramp + spare under 1,000. |
| **Low** | Nuclear; Hydro av / exp; Solar; Gas available; IESO demand level; DA / RT forecasts | They are mostly priced or very stable. Useful context, rarely the reason a trade wins. |

## Column by column

### Gas
- **Available**: gas capacity minus gas outages (MW). The fleet ceiling. It changes when units go on or off outage. Gas capacity grew about 2,000 MW since 2025.
- **Need**: what gas must cover once nuclear, wind, solar, expected hydro and expected net exports are taken off demand. This is the model's own gas-need number.
- **Spare**: Available − Need.
  - Under about 1,500 MW: gas is close to its ceiling (shaded); under 1,000: dark.
  - Low spare alone did **not** make sells lose: DA prices it.
  - Low spare **plus** a top-10% evening ramp was bad, but that result rests mostly on one day (Dec 4).
- **Ramp 1h / Ramp 3h**: how much gas need rises from 1 or 3 hours earlier.
  - Green = top 20% for that hour over the last 60 days (gas must ramp hard: bullish RT); dark green = top 5%.
  - Red = bottom 20%: gas backing down (bearish RT).
  - Large ramps explain **when** in the hour spikes happen (Oct 8 HE19 first 20 minutes). By themselves they did not predict RT beating DA.
- **1h pct**: the percentile behind the ramp colour.

### Headroom
- Gas available + hydro available − (demand − nuclear − wind − solar).
- **The model's main driver.** Under the learned line (about 7,000 now), DA has historically over-priced the hour: sells earned about +$18/MWh on tight evenings, with RT beating DA only 27% of the time.
- Batteries (1,200 MW) are **not** included. Adding them made the rule worse.

### Load net of nuc/wind/solar
- Demand minus the "free" supply: what hydro, gas and imports must cover.
- Its HE15 → HE19 rise is the **evening ramp** in the note above the table.
- Its HE5 → HE8 rise is the morning ramp.

### Load (MW)
- **IESO**: IESO's demand forecast. The DA market leans on it.
- **Tesla / Dynasty / Meteo**: vendor forecasts.
- **Tesla − IESO**: the most useful single column.
  - Tesla normally sits below IESO, so a positive number is unusual.
  - When Tesla is above IESO on a tight evening, the sell edge was about $0. Windy evenings with it lost money for sells and paid longs.
  - Green at +200 or more; red at −400 or less.

### Wind (MW)
- **IESO / Meteo**: the two main forecasts.
- **Models low / high**: lowest and highest of 5 weather models.
- A windy evening forecast (≥ 1,500) with Tesla above IESO is the setup where wind came in short and RT spiked (Oct 1, 7, 8).
- A wide low/high gap means wind is uncertain.
- Blank when the vendor files had not loaded. Run `morning.py --wind` after 07:20 MT.

### Solar
- Matters at midday and around sunset. The evening ramp starts as solar drops to 0 (HE17–18 in October).

### Other supply / ties
- **Nuclear**: available nuclear. Flat day to day; changes only with outages. Low importance.
- **Hydro av**: hydro capacity minus outages.
- **Hydro exp**: hydro we expect to actually run, from the recent pattern.
- **Net exp**: expected net exports (+ = Ontario exporting). Changes after the bid (intertie cuts or adds) are one of the four after-bid surprises behind spikes. Oct 8 midday West congestion was a transmission event, not visible here.

### CAHR
- The DA forecast turned into a carbon-adjusted heat rate (MMBtu/MWh):
  - 7–8 = efficient gas setting the price.
  - 10–12 = peakers.
  - Over 12 = DA is pricing scarcity.
- Used to grade tight sells: A (≥ 12) is priced to clear, B is priced $10 higher.

### Price forecast
- **East DA / East RT / Ottawa DA**: our forecasts.
- The RT forecast is the DA forecast scaled by recent RT/DA ratios. It is context, not a signal.

### Fundamentals read (E / O)
- What a model of **all** the columns above expects for **RT − DA** ($/MWh). + = longs pay, − = sells pay. East first, Ottawa after.
- Trained on every day through D-2, with no side preferred. Hover for its record in that segment.
- How to read the record:
  - Right side 56–70% of the time, but the average $/MWh since Oct 2025 is small: the losses are bigger than the wins.
  - Over the last 90 days it has been strong: about +$18/MWh when the read is $10 or more.
- Treat it as a second opinion, not an order.

### Last 7d RT − DA
- Average RT − DA at this hour over the last 7 settled days, and on how many of those 7 days RT beat DA.
- **"3/7" = RT beat DA on 3 days, DA beat RT on 4.**
- A big average with a low count (e.g. +$81.8, 3/7) means a few spike days, not a steady pattern.

### Model
- The model's call for that hour:
  - **SELL**.
  - **BUY** (buy band).
  - **NO EDGE**: tight evening but Tesla above IESO; stand aside.
  - **FLIP BUY**: tight evening, Tesla above IESO and a windy forecast; tested long.
  - **—**: no position.
