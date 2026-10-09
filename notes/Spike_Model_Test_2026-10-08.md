# Can a model rank spike hours well enough to buy them? (Oct 8 2026)

## Setup
- Scripts: `model/spike_feats.py` (features) and `model/spike_model.py` (test).
- Target: RT−DA ≥ $50 in the hour.
- Walk-forward: one model per month, trained only on days up to 2 days before the month. Out of sample Oct 2025 – Oct 6 2026, about 8,900 hours per zone.
- Models: gradient-boosted trees and logistic regression.
- 23 bid-time inputs:
  - Headroom, day-minimum headroom, gas need, gas spare, CAHR, DA forecast.
  - Tesla vs IESO, Tesla vs usual.
  - Wind forecast and its 3-hour change; spread and minimum across the 5 weather-model wind forecasts.
  - Residual-load ramp, gas outages percentile.
  - Spikes in the last days known, bias7, NY spread, hour, month, weekend, sell flag.
- Buy rule: bid at DA forecast + $30.

## Results
Base spike rate: 7.8% (East), 8.6% (Ottawa).

**Ranking power (AUC; 0.5 = coin flip, 1.0 = perfect)**

| Ranker | East | Ottawa |
|---|---|---|
| Boosted model | 0.71 | 0.70 |
| Headroom alone | 0.69 | 0.68 |
| CAHR alone | 0.71 | 0.69 |

The model barely beats single variables.

**Top-ranked hours**
- The top 2–5% spike 16–26% of the time, 2–3× the base rate.
- But the DA in those hours is already high:

  | Measure | Value |
  |---|---|
  | Median RT−DA | −$10 to −$30 |
  | Buy P&L, all hours | −$18 to +$14/MWh |
  | Last 90 days | Negative |
  | Without the best 5 days | Negative |

- Non-sell hours only:

  | Measure | Value |
  |---|---|
  | Buy P&L | +$4 to +$16/MWh |
  | Last 90 days | Zero to negative |
  | Without the best 5 days | About zero |

**What the model keys on:** DA forecast, headroom, wind forecast, Tesla vs IESO, gas need. All of these are things DA already prices.

## Read
- The predictable part of spike risk is already in the DA price, so buying it does not pay.
- The spikes that pay (RT spikes while DA is cheap) come from events after the bid: trips, wind misses, load misses. Bid-time data does not see these.
- More inputs of the same kind will not fix this.

## What could help
New information about the probability of after-the-bid events:
- Unit forced-outage history (which units trip, and when).
- Weather-model disagreement on load.
- Intertie curtailment patterns.

Not tested yet.
