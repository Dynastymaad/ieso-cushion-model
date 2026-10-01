# Spec: pre-model checklist workbook, Alberta version
(Written from the Ontario build, Sep 2026, to hand to the Alberta model session. Items marked **(check)** are Alberta facts to confirm against AESO rules / your own model before relying on them.)

## 0. What to build (one sentence)
- **The workbook:** an Excel workbook, `Checklist_Deviations.xlsx`, rebuilt every morning by the model's daily script. It shows tomorrow's key drivers against the last 14 and 30 days, the next 14 days, charts of where things are heading, and a scenario sheet.
- **Controls:** a button that runs all the data pulls.
- **Rule:** raw data plus differences only, with no model opinions inside it.

## 1. Alberta mechanics to design around (differs from Ontario)
- **Price:**
  - One province-wide **real-time pool price**: the hourly average of the minute-by-minute system marginal price (SMP). It is energy-only, with no capacity market.
  - Offer cap **$999.99/MWh**, floor **$0** (check current values).
  - **There is no IESO-style day-ahead market or virtual trading** (the Restructured Energy Market plans a day-ahead market — check status and dates). Trading the "next day" means forwards and NGX / bilateral products against the expected pool price. The checklist therefore compares drivers to the **pool price** (and to forward marks if you have them), not DA vs RT.
- **Clock:** AESO uses hour-ending in Mountain time (check whether files are MST or MPT). Keep one clock in the Data sheet and say which in the README.
- **The key number is the supply cushion.**
  - Cushion = available offered capacity − demand (AIL), after wind, solar and interties. The AESO publishes a supply cushion / supply adequacy measure (check the exact definition in your model).
  - A low cushion means the price climbs the steep top of the merit order. This is the Alberta equivalent of Ontario's headroom.
- **Supply mix:**
  - **Gas** (cogen, combined cycle, simple cycle, coal-to-gas conversions) sets price almost always.
  - **Wind** (about 5–6 GW) and **solar** (about 1.5–2 GW) are large and volatile, so their forecast error is the biggest swing factor. Wind is concentrated in southern Alberta (Pincher Creek, Medicine Hat, Lethbridge); solar in the southeast (check capacities).
  - Hydro is small. Battery storage is growing.
- **Interties:**
  - BC (via WECC), Montana (MATL, about 300 MW) and Saskatchewan (about 150 MW) — check limits.
  - **ATC (available transfer capability) is often reduced**, and import volumes set how much of the peak must come from gas.
- **Behaviour:**
  - Economic withholding and strategic offers by large portfolios matter.
  - Real-time offers can be restated. The **merit order is published with a 60-day lag** (check).
  - Price spikes cluster in low-wind, high-load hours.
- **Gas:** AECO price is the fuel cost of the marginal unit and sets the price floor for gas-set hours.

## 2. Workbook structure (copy exactly)
Sheets, in this order:
1. **README**: how to read each sheet, what each row is, peak definition, clock, sources, build date.
2. **Summary**: one row per item. Columns:
   - Group, Item, Unit, Tomorrow
   - Last-14 mean, Tomorrow − last-14
   - Last-30 mean, Tomorrow − last-30
   - Last-30 SD, z vs last-30, Flag (HIGH/LOW at |z| ≥ 1)
   - Last-30 min, Last-30 max
   - Next-14 mean, Next-14 − last-30
   - Note
   Put the refresh buttons in the top-right (see §5).
3. **Scenario**: yellow input cells, an hourly table (HE1–24) and a results box (see §4).
4. **Charts**: native Excel charts (see §3).
5. **Next_14_Days**: tomorrow + 13 days. For every item: Value, vs last-14, vs last-30. Red/green conditional fill when the difference exceeds one last-30 SD.
6. **Last_30_Days**: the same, newest first.
7. **Data**: one row per day, D-30 … D+13.
   - Columns: Date, Period (History / Tomorrow / Forward), then one column per item.
   - Raw values in blue font; the tomorrow row is yellow.

**Every average, difference, SD and flag is an Excel formula on Data.**
- Averages: `AVERAGEIFS` by date window.
- Min/max: `_xlfn.MINIFS` / `_xlfn.MAXIFS`.
- SD: SUMPRODUCT form, so no array formula is needed.
- Lookups: `INDEX/MATCH`.
- Never XLOOKUP or FILTER.

### Items to track (Alberta)
Use peak **HE8–23** (or your model's on-peak) for the averages.

| Group | Item | Periods |
|---|---|---|
| Load | AIL forecast daily peak / on-peak avg (AESO forecast as of the bid time you trade at); AIL actual; load miss = actual − forecast | H,T,F (forecast) / H (actual, miss) |
| Supply | Supply cushion: tightest hour, on-peak avg; available capacity; outages / derates by fuel (gas, coal-to-gas, hydro, other) from AESO outage reports | H,T,F |
| Supply | Outage MW added after your trade time (latest outage report minus the one at your decision time) | H |
| Renewables | Wind forecast on-peak avg and min; solar forecast max; **wind forecast error** (actual − forecast) | H,T,F / H |
| Interties | Import ATC BC / MATL / SK, scheduled imports / exports, actual net interchange | H,T |
| Prices | Pool price on-peak avg, off-peak avg, daily max; hours ≥ $500; SMP volatility; forward on-peak mark (if available) and pool − forward | H (T/F for forwards) |
| Fuel | AECO gas price | H,T |
| Neighbours | Mid-C or BC reference price (if available) | H,T |
| Weather | Calgary and Edmonton max/min temperature (load); cloud cover (solar); **100 m wind at Pincher Creek, Medicine Hat, Lethbridge / Forty Mile** (wind); sea-level pressure (highs = calm) | H,T,F |
| Reference | Your model's cushion threshold(s), as a constant line for the charts | H,T,F |

Weather source: the Open-Meteo forecast API. One call with comma-separated lat/lon, `past_days=31&forecast_days=16`, hourly `temperature_2m, cloud_cover, shortwave_radiation, pressure_msl, wind_speed_100m`, timezone America/Edmonton. Cache the JSON so the build still works offline.

Blank what a period cannot know (tomorrow's pool price, forward outcomes). Blank placeholder forecasts too: if a forward series is flat across the day, it is a placeholder, so drop it (Ontario's 35-day wind was).

## 3. Charts (native Excel, one unit per chart, never two y-axes)
- **Line / column over the 44 days (D-30 … D+13):**
  - AIL forecast vs actual
  - outages stacked by fuel
  - cushion (tightest and avg) vs the model threshold (dashed)
  - outages added after the decision time
  - wind forecast (MW)
  - 100 m wind at the wind-farm points (km/h)
  - Calgary / Edmonton max temperature
  - cloud cover
  - pressure
  - pool price on-peak / off-peak
  - pool − forward (if forwards exist)
  - import ATC and net imports
- **Scatter, last 30 days:**
  - tightest cushion vs on-peak pool price
  - wind forecast error vs pool price
  - load miss vs pool price
  - outages added after the decision time vs pool price
- **Style:** fixed categorical colours in order (blue #2A78D6, orange #EB6834, aqua #1BAF7A, yellow #EDA100), grey dashed for reference lines, axis tick labels at "low" so they don't collide with the zero line, legend at the bottom.

## 4. Scenario sheet (inputs that move the Alberta price)
- **Yellow inputs:**
  - demand change (MW)
  - wind change (% of forecast)
  - solar change (%)
  - gas / thermal available change (MW, − = trip or derate)
  - import ATC change (MW, − = intertie cut)
  - net exports change (MW)
  - AECO gas change ($/GJ)
  - Apply from HE / to HE
- **Hourly table:**
  - base cushion, scenario cushion (= base + availability change + wind/solar change + import change − demand change)
  - base and scenario price forecast, using **your Alberta model's own sensitivity of price to cushion** (for example its cushion→price lookup, or a fitted log-price slope per GW by time block), and heat-rate × AECO for gas-set hours
  - base and scenario signal / score
  - changed cells highlighted yellow
- **Results box (base vs scenario):**
  - tightest cushion
  - on-peak price forecast
  - count of hours below the model threshold
  - hours whose signal changed
- **Two charts:** cushion by hour and price by hour, base vs scenario.
- **Test:** with every input at 0, the scenario must reproduce the model's base output exactly.
- **Quick setups printed on the sheet:**
  - gas unit trip −400 MW HE17–21
  - calm day wind −60%
  - cold snap demand +800
  - BC intertie cut import ATC −500

## 5. Refresh buttons and the daily run (what went wrong in Ontario, and the fixes)
- **Buttons:** two cells with hyperlinks to `.bat` launchers in the model folder: REFRESH (all pulls + rebuild) and Rebuild only. Each launcher:
  1. `cd /d "%~dp0"`
  2. runs the daily script with `python -X utf8`
  3. opens the newest workbook through a small `open_checklist.py` (`os.startfile`).
- **Use absolute `file:///C:/...` links.** On OneDrive, Excel opens the workbook from its web URL, and relative links 404.
- **Windows encoding:** run every sub-script with `-X utf8` / `PYTHONUTF8=1`. Otherwise `write_text` with "→" crashes on cp1252.
- **Optional add-ons:** don't make them depend on packages that may be missing (e.g. tabulate). Wrap them so a failure prints a warning and doesn't stop the run.
- **Workbook open in Excel:** catch `PermissionError` and save a timestamped copy instead.
- **Formula recalculation:**
  - Set `wb.calculation.fullCalcOnLoad = True`, so Excel computes on open.
  - If you verify formulas with LibreOffice, don't ship the LibreOffice-resaved file: it rewrites hyperlinks as relative paths. Always ship the file written directly by openpyxl.
- **Excel version:** MINIFS/MAXIFS need Excel 2019 / 365.
- **Data freshness:** the build must refuse or flag a stale day. Print the delivery day and the vintage of the key forecast file in the header / README.

## 6. Acceptance checks before calling it done
1. Zero formula errors after a recalculation.
2. The Summary tomorrow values equal the Data row for tomorrow.
3. The scenario with all inputs at 0 reproduces the base in all 24 hours.
4. A test scenario moves the cushion by the expected MW and the price in the expected direction.
5. Both buttons open the launcher from the OneDrive-opened workbook.
6. The run works when the workbook is open (a timestamped copy is written).
7. The charts render with no overlapping axis labels.
