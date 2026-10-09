# Oct 9 2026: tight-evening guard, long-side test, lookbacks by segment, fleet changes, Oct 8 HE19 timing

## 1. Is a "coin flip" peak better taken long? (`model/tight_eval.py`, tight HE16–21, Tesla > IESO)
Losses on the long side are not capped at about $20:

| | Result |
|---|---|
| Average loss | −$57 to −$62 |
| Losses worse than −$20 | 46–49% of losing hours |
| Worst hour | −$286 to −$395 |

| Tight HE16–21 hours | Long $/MWh | Win rate | Long 85 MW (bid DA fc + $30) | Sell ladder |
|---|---|---|---|---|
| Tesla > IESO, last 120 days (59 h, 22 days) | +$2.0 (E) / +$1.5 (O) | 36% | −$13k (E) / +$27k (O) | −$10k / −$16k |
| Tesla > IESO, since Sep 2025 (314 h) | ≈ $0 | 37% | +$77k / +$2k | +$8k / +$11k |
| Tesla > IESO and wind fc ≥ 1,500, since Sep 2025 (107 h, 45 days) | +$8.1 / +$8.4 | 38–40% | **+$167k / +$96k** | **−$50k / −$59k** |
| Same, last 120 days | +$55 | | Only 6 h on 3 days | |

**Wired** (`run_model.py`, field `guard`):
- Tight HE16–21 with Tesla > IESO → **NO EDGE**: no orders.
- Same with wind fc ≥ 1,500 → **FLIP BUY**: 20/30/35 MW, bid DA fc + $30.

## 2. Unbiased segment rule vs the live model (`model/segment_lookback.py`)
- Segments: overnight 1–6, morning 7–10, midday 11–15, evening 16–21, late 22–24.
- Rule: each day, split the last N days of each segment into 5 headroom buckets. Sell or buy each bucket's direction if |mean| ≥ $3.
- P&L is price-taker $ per MW, Oct 2025 – Oct 6 2026.

| East, total | All | Evening | Midday | Morning | Overnight | Late | Last 90 days |
|---|---|---|---|---|---|---|---|
| **Live model** | **43,355** | **22,448** | 7,001 | 5,431 | 7,359 | 1,116 | 12,467 |
| Segment rule, 30 days | 6,368 | −1,257 | 5,250 | 3,166 | −791 | — | 6,312 |
| Segment rule, 60 days | 24,479 | 9,229 | 4,845 | 4,600 | 2,978 | 2,828 | 10,817 |
| Segment rule, 90 days | 14,467 | 10,555 | 3,010 | −2,553 | 1,800 | 1,654 | 8,613 |
| Segment rule, 120 days | 22,151 | 10,888 | 6,377 | −64 | 3,223 | 1,726 | 9,106 |

Ottawa is the same picture: live 37,883 against a best of 33,608 (60 days).

- Shorter windows are noisier, not better. 30 days is the worst.
- The live model wins every segment except the late hours.

## 3. Fleet changes and headroom (IESO Adequacy capacities, monthly)
| Item | Change |
|---|---|
| Gas capacity | 9.2–9.8k (summer 2025) → 11.3k (2026) |
| Nuclear capacity | 13.2k → 12.2k (Apr 2026) |
| Storage | 0 → 1,200 MW (Mar 2026 on) |
| Hydro capacity | 8.4k → 7.85k |

- Headroom already uses each day's IESO capacities and outages. The thresholds re-learn on the last 90 days.
- Adding storage to headroom made the sell rule worse: May–Oct 2026, +$9.25/MWh vs +$22.12 with the current headroom.
- Headroom ÷ demand was also worse (+$11.15). **No change.**

## 4. Oct 8 HE19 timing (IESO RealtimeTotals, 5-min, EST hour-ending)
| | Value |
|---|---|
| Ontario demand, HE18 last interval | 17,190 |
| Ontario demand, HE19 intervals 1–4 | 17,233 → 17,430 → 17,598 → **17,667** |
| Ontario demand, HE19 later intervals | ~17,100 |
| Price | $145 → $517 → $532 → $536 → $468 → $256 … $68 |
| 10-minute non-spin reserve | 709 → 511 |

- Demand rose about 480 MW in 20 minutes, right after sunset (about 17:48 EST). It peaked at interval 4 (18:15–18:20 EST, 19:15–19:20 EDT). The price spiked over exactly those intervals and eased as demand fell back.
- Exports were flat at about 2,420–2,450 MW.

## UPDATE (Oct 9): guard REMOVED after validation (`model/guard_validate.py`)
### NO-EDGE part (Tesla > IESO, wind < 1,500): skipping these sells costs money
| | East | Ottawa |
|---|---|---|
| Sells in those 207 hours made | +$58k | +$70k |
| By half (H1 / H2) | +67k / −9k | +75k / −5k |

### FLIP part (Tesla > IESO and wind ≥ 1,500): fails two robustness checks
**What supports it**

| Check | East | Ottawa |
|---|---|---|
| Gain over the whole period | +$218k | +$155k |
| By half (H1 / H2) | +184k / +34k | +113k / +43k |
| Placebo (random flips) | Beats 98.6% | Beats 98.8% |
| Threshold grid | Plateau, wind 1,250–1,750 | Plateau, wind 1,250–1,750 |

**What fails**

| Check | East | Ottawa |
|---|---|---|
| Without the best 3 days | −$114k | −$63k |
| Thresholds picked walk-forward | −$219k | −$84k |

Not reliable enough to trade automatically. Live signals are back to the pre-guard model.

## Oct 9 HE18-type setup as a long (tight evening, Tesla > IESO, CAHR ≥ 12, spare < 1,500, 1h gas ramp top 20%)
| Measure | East | Ottawa |
|---|---|---|
| Hours (days) | 25 (18) | 26 (18) |
| Long $/MWh | +$25.8 | +$24.5 |
| RT beat DA | 52% | 50% |
| By half (H1 / H2) | +30 / +4 | +28 / +4 |
| Without the best 3 days | Slightly negative | Slightly negative |

Each factor on its own makes a long **worse**:

| Factor alone | Long $/MWh |
|---|---|
| CAHR ≥ 12 | −$18 |
| Spare < 1,500 | −$29 |
| Ramp top 20% | −$16 |

Only the full combination turns positive. That supports a small discretionary long; it is too thin to be a model rule.
