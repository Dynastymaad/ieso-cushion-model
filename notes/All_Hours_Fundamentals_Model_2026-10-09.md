# Trading every hour from all fundamentals (Oct 9 2026): `model/all_hours.py`

## Setup
- Walk-forward gradient-boosted regression of DA−RT, refit monthly on data through first-of-month − 2 days.
- Out of sample: Oct 2025 – Oct 6 2026, about 8,900 hours per zone.
- 36 bid-time inputs:
  - Headroom, gas need, gas available, spare gas.
  - Gas ramp 1h / 3h, residual-load ramp, load ramp, wind level and ramp, solar level and ramp.
  - Gas and nuclear outages (MW and percentile), expected hydro, expected net exports.
  - Tesla / Dynasty vs IESO, CAHR, DA forecast, DA vs RT forecast, NY spread.
  - Recent after-bid surprises: intertie changes, outages added, load misses.
  - Weather-model wind spread, recent spikes, recent RT−DA by hour, hour, month, weekend.

Results are price-taker $ per MW.

| | East total | H1 / H2 | Last 90 days | Ottawa total |
|---|---|---|---|---|
| **Live model** | **44,529** | 22,279 / 22,250 | 12,213 | **39,763** |
| Model on the hours live leaves FLAT, all predictions | 2,170 | −1,114 / 3,283 | 2,546 | −680 |
| Same, only when the prediction is ≥ $5 | 1,880 | −789 / 2,669 | 2,238 | −1,607 |
| Model on ALL hours instead of live (≥ $5) | 19,570 | 4,318 / 15,252 | 10,352 | 14,655 |
| Model on ALL hours instead of live (≥ $10) | 18,793 | | 8,422 | 14,271 |

- **Flat hours:** 2,740 of 8,879 (31%). The average |DA−RT| in them is about $19, but no combination of fundamentals predicted the side: about $0/MWh, negative in H1 and at Ottawa.
- **The money left on the table is small:** at most about $2k per MW per year at East, and negative at Ottawa.
- **The all-fundamentals model does not beat the live model** in any segment overall. Over the last 90 days it is close: East 10.4k vs 12.2k, Ottawa 12.0k vs 12.4k.
- **Small, positive in both zones:** morning flat hours HE7–10 at ≥ $5, +$4.6 to +$5.8/MWh, about 200 hours a year.
