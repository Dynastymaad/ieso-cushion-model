# Bid-time weather and outage timing — sources and first tests (28 Sep 2026)

## Temperature forecast as it stood at the bid
| source | what it holds | bid-safe how | status |
|---|---|---|---|
| **Open-Meteo Previous Runs API** (public, no key) | hourly forecasts as issued 1 and 2 days before, since 2024 | use the 2-day-old run (`_previous_day2`): always issued before D-1 08:00 MT | **pulled**: 6 load centres, Apr 2025 – Sep 2026 → `data/wx/openmeteo_prevruns_ontario.csv.gz`, `model/wx_bid.py` → `data/wx/wx_hourly.csv` |
| Warehouse `WeatherHourlyForecast` (NOAA, StormVista ECMWF-EPS / GFS-ENS, WSI) | Ontario stations, each vintage stamped | keep vintages issued before the bid | **pulled, but the table only keeps ~2 weeks** (14 Sep → 1 Oct 2026, 70k rows). No history there; Open-Meteo stays the history source. Could be archived daily from now on if we want a second vendor |

Open-Meteo's Toronto 2-day-old forecast vs observed CYYZ: MAE 2.9°F, corr 0.983. Load-weighted:

| centre | weight |
|---|---|
| Toronto | .40 |
| Ottawa | .16 |
| Hamilton | .12 |
| London | .12 |
| Barrie | .12 |
| Windsor | .08 |

The load-weighted MAE vs the later analysis is 2.3°F.

**First test** (`model/load_miss.py`, walk-forward, 10,849 h). Target: IESO's load miss (actual − pre-DA forecast; mean −243 MW, MAE 432).

| predictor of the miss | corr | MAE after correcting |
|---|---|---|
| weather only (degrees, feels-like, change vs 2 days ago, weekend, peak) | 0.15 | 402 |
| Tesla − IESO + IESO's own miss two days ago | **0.56** | **338** |
| both | 0.55 | 345 |

- IESO's forecast already uses the weather. On its own, a temperature forecast does not tell us when IESO will miss.
- Tesla vs IESO does, and it flagged two of the hot days: 5 Oct 25 (predicted +490 vs actual +607) and 25 Jul 25 (+415 vs +505).
- It did not flag 2 May 26 or 11 Mar 26.

**Veto test on v2 SELL hours** (skip the sell when…):

| condition | hours | days | DA−RT of skipped hours | 90% range | halves | verdict |
|---|---|---|---|---|---|---|
| predicted load miss ≥ +400 MW (Tesla + IESO d-2) | 222 | 50 | −11.90 | −26.54..+2.17 | −13.0 / −2.6 | near miss (both halves lose, range touches 0) |
| predicted load miss ≥ +300 MW | 380 | 85 | −7.70 | −17.68..+1.75 | −10.2 / **+4.8** | fails |
| forecast ≥ 75°F, weekend, shoulder month | 33 | 6 | −49.98 | −85.01..−4.26 | all in 2025 | the pattern you saw, but only 6 days |
| forecast ≥ 80°F | 518 | 78 | +13.84 | | | wrong way (hot sells win overall) |
| forecast ≤ 20°F | 480 | 51 | +17.99 | +0.31..+33.96 | | wrong way (cold sells win) |

## Outage timing
| source | what it holds | status |
|---|---|---|
| **Adequacy2 all-vintage archive** (canpower sandbox) | every IESO re-issue of gas / nuclear / hydro outage totals, with its publish time, May 2025 → | **pulled**: 613k changes → `model/outage_timeline.py` → `data/outage_features.csv` |
| IESO `GenOutputCapability`, every hourly version | per-unit capability; the version shows when a unit dropped | IESO keeps ~90 days. `ieso_backfill.py` now archives **all versions** from here on, not just the final file |
| IESO `TxOutagesTodayAll`, `TxLimitsOutage0to2Days` | transmission outages and resulting limits, time-stamped | now archived (all versions) |
| Warehouse `GenerationOutages` / `IIRPlantOutage` | PJM / MISO categories; old IIR plant list | not Ontario, not used |
| NRGStream | to check for Ontario outage streams | needs a fresh login |

IESO does not publish per-unit forced-outage notices publicly beyond `GenOutputCapability`. The Adequacy timeline is the only 17-month record of *when* outage MW appeared.

## Outage timing — results (Toronto; Southwest the same within ~$1)
Features per delivery hour, built from the timeline (`model/outage_timeline.py`):

| feature | meaning |
|---|---|
| `add_after` | outage MW added after our bid (mean +303 MW) |
| `ret_assumed` | MW IESO assumes will be back by D vs where the fleet is right now (mean +243 MW) |
| `trips_d1` | MW added to yesterday's own hours after yesterday's bid, i.e. units that tripped in the last 24 h |

**When did the damaging outages appear?** On losing sell hours with a 200 MW+ post-bid addition, the timing spread out like this:

| when it appeared | share |
|---|---|
| D-1 afternoon | 16% |
| 18–24 h before the hour | 16% |
| 12–18 h before | 20% |
| 6–12 h before | 21% |
| 0–6 h before | 19% |
| after the hour started | 9% |

- **87%** of big-loss hours saw the addition arrive **after the DA results** (~13:30 EST on D-1), against 78% of winning hours.
- The worst outage days were overnight or same-day trips. The first 200 MW arrived only this far ahead:

| day | first 200 MW arrived |
|---|---|
| 24 Jan 26 | 7 h before |
| 1 Jul 25 | 5 h before |
| 10 Jun 26 | 8 h before |
| 6 Jan 26 | during the hour |

**Can we predict the additions at bid time?** Partly.
- IESO's return-to-service assumptions slip: when IESO assumes 1,000+ MW will be back, 711 MW gets added after the bid, against 147 MW when it assumes none (corr 0.33).
- But those predictable additions do **not** hurt the sell. DA already prices them, and more:

| on v2 SELL hours | hours | DA−RT | 90% range | halves |
|---|---|---|---|---|
| IESO assumes ≥ 500 MW returns | 1,778 | +6.61 | +2.55..+11.01 | +6.3 / +7.0 |
| predicted post-bid additions ≥ 500 MW | 706 | +11.75 | +1.71..+22.31 | +6.3 / +15.5 |
| **units tripped in the last 24 h ≥ 500 MW** | 1,447 | **+12.33** | **+6.96..+18.00** | **+13.0 / +11.2** |
| units tripped in the last 24 h < 500 MW | 5,269 | +3.66 | +0.89..+6.19 | |

- The trips effect is monotonic:

| trips in last 24 h | DA−RT |
|---|---|
| ≥ 250 MW | +10.29 |
| ≥ 500 MW | +12.33 |
| ≥ 750 MW | +14.65 |
| ≥ 1,000 MW | +18.11 |

- Picking the threshold walk-forward each month gives +11.32 (+6.25..+16.24).
- Southwest: +11.41 (+5.84..+17.21).
- After a run of trips the DA market over-prices tomorrow's risk. That makes these the *best* sells, not the ones to skip.

**Adopted: SELL size ×1.5 when trips in the last 24 h ≥ 500 MW** (score 5 only). Toronto, same VA ladders, Jul 2025 – Sep 2026:

| | net | made | lost | worst day |
|---|---|---|---|---|
| base | +3.67M | +6.74M | −3.07M | −203,664 |
| with the ×1.5 | **+4.43M** | +7.71M | −3.28M | −203,664 (unchanged) |

**Not adopted:** using trips to skip buy-band hours. Buy-band hours made +12.58 with fewer than 500 MW of trips and +5.65 with 500 or more, but the 90% range of the latter crosses zero.

## Bottom line
- **Outages:** the losses come from the outages IESO learns about after the DA clears. We cannot see those at 08:00 MT, and the ones we *can* predict are already in the DA price.
- **Weather:** it adds nothing over IESO's own forecast.
- **What changed:** the model now uses the outage timeline in the one direction that tested well, more size on sells after a day of trips.
- **Live data:** it comes from `pull_history.py --only outages`. `ieso_backfill.py` now archives every Adequacy3 version, so the GitHub job can compute it from IESO's public files.
