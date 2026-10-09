# Spike Watch (wired) and the Tesla > IESO tight-sell flag (Oct 8 2026)

## Spike Watch: wired in `run_model.py` (field `sw`) and the DA Virtual matrix (column "Spike", chip "SPIKE BUY 20 @ $X")
**Hours:** evening HE16–21 that the model is not selling. One point each for:

| Point | Condition |
|---|---|
| 1 | Headroom 7,000–8,500 |
| 2 | CAHR ≥ 10 |
| 3 | Tesla or Dynasty ≥ IESO demand |
| 4 | IESO wind down 150+ MW over the last 3 hours |

**Trade:** score 2 or more = a separate small long, 20 MW, bid at DA forecast + $30. It is not part of the score ladder.

**Backtests:**
- Since Sep 2025:

  | | East | Ottawa |
  |---|---|---|
  | Per MWh | +$14 | +$17.5 |
  | Win rate | 33–34% | 33–34% |
  | Average win / loss | +$91 / −$25 | +$99 / −$25 |

- 2026 at 20 MW (`model/spike_watch_2026.py`): East +$153k, Ottawa +$205k. Without the best 5 days: +$32k / +$59k. Worst day about −$5k.
- Sep–Oct spikes inside its window: 9 of 11 flagged. Missed: Sep 17 HE21 and Sep 27 HE19, both score 1.

**Flagged hours that lost:** 67% of flagged hours settled RT below DA, with a median loser of −$21. Of all flagged hours:

| RT vs DA | Share |
|---|---|
| Within $10 below DA | 15% |
| $10–30 below DA | 32% |
| More than $30 below DA | 19% |

**Data check:** every input is known before the 08:00 MT bid:
- Adequacy 07:49 vintage.
- Our walk-forward DA forecast.
- Dawn settle and FX as of D-2.
- Tesla and Dynasty forecasts, loaded or issued before the deadline. The Tesla backfill keeps the original 04:28 load times.
- No DA intertie schedules are used. That earlier look-ahead was removed from all of this.

## Tesla > IESO on tight evening sells: shown as a chip, not acted on (`model/tight_guard.py`)
- Oct 1 HE17–20 and Oct 7 HE17–20 both had Tesla above IESO at the bid (+8 to +215 MW), and wind forecasts near 1,900–2,000 MW that came in short.

Ladder P&L, Sep 12 2025 – Oct 6 2026:

| Rule | East total | Ottawa total | Days < −$5k | Worst day | Sharpe | Last 90 days |
|---|---|---|---|---|---|---|
| All tight sells (live) | $2.62M | $2.49M | 45 / 46 | −$181k | 4.4 / 3.9 | — |
| Skip tight HE16–21 when Tesla > IESO | −$8k | −$11k | 32 / 33 | −$160k | 5.0 / 4.4 | −$41k |
| Skip only when Tesla > IESO by 300+ | +$40k | +$63k | 38 / 39 | −$169k | — | −$37k |

- The 300+ rule makes more money and passes the "more money" rule, but it would not have caught Oct 1 or Oct 7.
- Decision left to the desk. The flag is shown on the page; ladders are unchanged.
