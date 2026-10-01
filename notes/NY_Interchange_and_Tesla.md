# New York interchange and Tesla panels (added Sep 30)

## Tesla vs IESO
- IESO over-forecasts load. Since Jul 2026, Adequacy demand has run +351 MW above actual (+469 at HE16-20). Tesla has run -29 MW (+102 at the peak) and has the lower MAE (539 vs 636 MW).
- So Tesla sitting below IESO is the usual state. On Sep 30 it was -224 to -663 MW below.
- The useful number is the gap against its 30-day median by HE. For Oct 1 at HE16-21, Tesla is +14 MW vs Adequacy against a usual -212. That makes Tesla about +227 MW higher than normal.
- Against IESO's own earlier day-ahead forecast, Tesla is -245 MW.
- Tesla vintage: the warehouse loads once, around 04:28 MT, so the page uses the 03:27 run. A later Tesla run seen in the portal is not in the model.

## New York
- The NYISO DAM schedule at the Ontario proxy (ny_dni_oh, + means Ontario exports to NY) posts around 09:40-09:55 ET. On Sep 30 it missed the 10:00 IESO close, so the page falls back to the previous day's schedule.
- NY Zone A DA posts around 09:33 ET.
- Levels are percentiles: hourly against the prior 30 days, daily peak against the prior 60 days.
- Test on model sell hours, Jul 2025-now, DA-RT by quartile:
  - ON->NY MW: +13.0 / +0.6 / +2.0 / +6.0 (East). High exports did not hurt sells.
  - NY A minus East DA forecast: +15.3 when NY is more than $25 below Ontario; otherwise +0.5 to +4.4.
- This is context only. It is not a model input, and no rule is adopted.
