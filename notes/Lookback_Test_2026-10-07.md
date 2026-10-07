# How much history should the model learn from? (walk-forward test, Oct 7 2026)

## Setup
- Each day, the sell thresholds (headroom and gas need) are re-learned on the days up to D-2, using only the last N days of history.
- Test period: Jul 2025 - Oct 6 2026.
- Measure: price-taker DA-RT per MW.
- Halves: H1 is before Feb 15 2026; H2 is from Feb 15 on.

## Core sells (tight or surplus), total $ per MW

| Lookback | East total | East $/MWh | East H1 / H2 | Ottawa total | Ottawa $/MWh | Ottawa H1 / H2 |
|---|---|---|---|---|---|---|
| All history (old live) | 33,679 | 4.47 | 5.76 / 3.01 | 21,374 | 2.94 | 5.12 / 0.47 |
| 365 days | 32,827 | 4.49 | 5.76 / 2.95 | 21,359 | 3.07 | 5.12 / 0.52 |
| 180 days | 36,653 | 5.52 | 5.76 / 5.17 | 22,837 | 3.61 | 4.92 / 1.70 |
| 120 days | 35,749 | 5.36 | 5.68 / 4.89 | 24,550 | 3.89 | 5.44 / 1.82 |
| **90 days (adopted)** | **37,330** | **5.91** | **6.22 / 5.46** | **26,738** | **4.34** | **5.94 / 2.24** |
| 60 days | 35,434 | 5.81 | 5.94 / 5.61 | 26,358 | 4.33 | 6.04 / 2.07 |

- Every window of 180 days or shorter beats all-history, so the result is robust.
- 90 days is the best at both zones and in both halves.

## Extended SELL-L tier (gas need under the largest qualifying threshold)
At 90 days the tier lost money: East −$2.70/MWh over 250 hours, Ottawa −$5.30/MWh over 203 hours. It is switched off (`USE_EXT = False`).

## Buy band lookback
The buy band already re-learns on the last 120 days. Combined East + Ottawa total by window:

| 60d | 90d | 120d | 180d | 365d |
|---|---|---|---|---|
| 35,627 | 44,040 | **46,675** | 43,585 | 45,000 |

120 days stays.

## Change made
In `model/signals_v2.py`:
- `LOOKBACK = 90`
- `USE_EXT = False`

The backup is `signals_v2.bak_pre_lookback.py`.
