# Spikes and after-the-bid surprises: trips, load disagreement, interties (Oct 8 2026)

Scripts (all in `model/`): `unit_trips.py`, `outage_surprise.py`, `after_bid.py`, `shock_predict.py`, `spike_model2.py`, `spike_model2_robust.py`, `spike_placebo.py`, `leakfree_run.py`.

## Data found
| Item | Source | Coverage |
|---|---|---|
| Unit trips | IESO GenOutputCapability (archive) | Jun 27 – Oct 8 2026 only (104 days) |
| Outages added after the bid | Adequacy2 outage timeline | Jun 2025 → |
| Load forecasts | IESO, Tesla, Dynasty at the bid; actual load | Apr 2025 → |
| Weather-model temperatures (StormVista) | | Sep 14 – Oct 1 2026 only; too short to test |
| Interties | RT schedules (IntertieScheduleFlowYear) vs DA schedules (Adequacy2 final) | 2025 → |
| Actual wind | GenOutputbyFuelHourly | |

## 1. What drives spikes: confirmed
Total after-bid supply shock = load miss − wind miss + outages added + intertie change.

| Shock | Spike rate | Mean RT−DA |
|---|---|---|
| < 0 | about 2% | |
| ≥ 1,500 MW | 31% | +$55 |

Each piece matters about equally: the worst 10% of each gives a 16–20% spike rate, against about 8% base.

## 2. Can each surprise be predicted at the bid?
| Surprise | Best bid-time predictor | Out-of-sample R² | Verdict |
|---|---|---|---|
| Unit trips (gas/nuclear) | Gas need, headroom, recent trips | — | Trip days 11–19% whatever the conditions; 53 events. **No** |
| Outages added after bid | Trailing 7 days (r = 0.18) | −0.17 | **No** |
| Wind miss | Weather-model spread / gap (r ≤ 0.19) | −0.03 | **No** |
| **IESO load miss** | **Dynasty − IESO (r = 0.49), Tesla − IESO (0.44)** | **+0.35** | **Yes** |
| Intertie change | Trailing 7 days, headroom | ≈ 0 | Weak (top 10% picks: 15% spike rate) |

## 3. Spike model with the new predictors (walk-forward, Nov 2025 – Oct 6 2026)
**First run looked strong (+$20–25/MWh), but it used DA intertie schedules. Those are set by the DA run itself, so they are not known at the bid. Removed.**

Leak-free result, buying the top 10% of non-sell hours each month (bid at DA forecast + $30):

| | East | Ottawa |
|---|---|---|
| Baseline model | +$7.8 | +$7.9 |
| With new predictors | **+$18.3** (H1 17.0 / H2 18.8) | **+$15.4** (12.3 / 16.8) |
| Last 90 days | +$4.7 | +$2.6 |
| Without the 5 best days | +$3.4k/MW | +$2.8k/MW |
| Placebo (new inputs shuffled across days, 20 runs) | Beats 19 of 20 | Beats 18 of 20 |
| Months positive | 9 of 12 | 10 of 12 |

August was negative at both zones.

## Verdict
- Promising but not proven: the edge over random inputs is only about 90–95% confidence, and it was weak in the last 90 days.
- **Not wired.** Next step: shadow-track the top picks daily for 4–6 weeks before adding it.
