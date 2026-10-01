# Bid-morning checklist (East / Ottawa, DAM closes 08:00 MT)

| When (MT) | Step |
|---|---|
| 07:00 | `python morning.py` |
| 07:35 | NYISO is out. Run `python ieso_backfill.py` and `python pull_history.py --only adq2 --since 2025-04-01`, then have the desk rebuilt. |

## 1. Is it the right day and the right file?
- **Header:** it must say "DA for <tomorrow>".
- **IESO file:** it must be the ~07:50 EST Adequacy issue of today. If the header still shows yesterday's date, stop: the data is not in yet.

## 2. Outages tab: what is already priced, and what is new
- **Last 30 days vs tomorrow:** is tomorrow's total above the 30-day P75? Which fuel is driving it?
  - Known outages are priced into DA. Tested: DA tends to over-price them, which helps sells.
- **Trips in the last 24 h:** 500 MW or more means tight sells get ×1.5 automatically.
- **Watch-list tags:**
  - *In the model* and *Later days:* nothing to do for tomorrow's bid.
  - *You:* anything heard after IESO's file (a unit trip, an IESO notice). Enter it with the Gas / Nuclear what-if slider before copying ladders.

## 3. Next day tab: the shape of the day
- **Headroom by hour:** under 7,000 MW is the sell zone; the buy bands are East 7,500–9,500 and Ottawa 9,500–11,500.
- **DA forecast and range:** where the peak sits, and how wide P10–P90 is.

## 4. DA Virtual tab: each score and why
- **Scores:** 5 = v2 sell (tight or surplus), 1 = buy band, 3 = small straddle.
- **Tesla Δ:** Tesla minus the IESO load forecast. Negative means Tesla expects less load, a softer RT, and helps sells; positive (hundreds of MW) means load risk for sells.
- **DA−RT 7d / 14d badges:** a large negative number means RT has been beating DA at that hour lately. This is information only (not a tested rule), but it marks the riskiest sell hours.
- **Other flags:** a SCARCITY chip (headroom under 2,000 MW) or a ×1.5 chip.

## 5. East–Ottawa & Quebec tab
- **PQ.AT export limit tomorrow:** well below the last 7 days of exports means a smaller East/Ottawa premium.
- **Pair:** it is off unless you turn it on.

## 6. Size, then copy BOTH zones' buy and sell rows
- The known tail risk is RT spikes from trips after the bid and load misses; they cannot be predicted.
- If a bad day of roughly −$150–200k per zone is too much, lower Size × evenly rather than dropping the tight hours (tested).

## 0. Before the model: site/Checklist_Deviations.xlsx
- **Built by:** `morning.py` each morning. Open it in Excel; it recalculates on open.
- **Summary:** tomorrow vs the last-14 and last-30 day means for load, outages, wind/solar, headroom, Quebec limit, NY price, prices, and weather (Toronto/Ottawa temperature, cloud, solar, pressure, 100 m wind on the Lake Huron and Lake Erie shores). HIGH/LOW = at least one 30-day SD away.
- **Next_14_Days / Last_30_Days:** raw daily values and the differences.
- **Weather:** from Open-Meteo, fetched live each run and cached in data/wx/openmeteo_view.json.
- **Scenario sheet:** the yellow inputs change tomorrow's demand, wind %, solar %, gas / nuclear / hydro availability and net exports, optionally for an HE range. Headroom, gas need, the East/Ottawa DA and RT forecasts, and the model's score per hour recalculate, using the same arithmetic as the desk sliders; a changed score turns yellow. Set everything to 0 and HE 1–24 for the base case.
