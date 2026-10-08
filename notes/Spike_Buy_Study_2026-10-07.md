# Catching RT spikes with buys (Oct 7 2026)

## Setup
- Scripts: `model/spike_study.py`, `model/spike_rules.py`.
- Hours: non-sell hours only, Sep 2025 – Oct 6 2026, East and Ottawa.
- Spike: RT − DA ≥ $50.
- Halves: H1 is before Feb 15 2026; H2 is from Feb 15 on.

## What comes before spikes (evening HE17–22, non-sell hours)

| Factor | Spike rate | Note |
|---|---|---|
| All evening hours | ~11% | Morning HE1–6: ~4% |
| Headroom 7–9k (just above our tight line) | 12–16% | 9k+: 6–8% |
| CAHR ≥ 10 | 13–18% | |
| Wind falling >400 MW over 3h | 18% | Only 3–4% in H1; not stable |
| Tesla vs IESO, gas outages, bias7 | — | No stable lift |

Even in the best bucket, about 85% of hours do not spike. The **median** RT−DA is negative (−$8 to −$14). Spikes are driven by supply surprises after the bid (trips, wind misses), which bid-time data cannot see.

## Candidate rule S1: buy HE17–22 when headroom < 9,000 and the hour is not a sell
Bid at DA forecast + $30.

| | East | Ottawa |
|---|---|---|
| Mean RT−DA per MWh | +$12.1 | +$12.8 |
| By half (H1 / H2) | +$20.3 / +$9.3 | +$18.9 / +$10.4 |
| Last 90 days | +$3.6 | +$3.2 |
| Median per MWh | −$8 | −$9 |
| Hit rate | 34% | 34% |
| Positive months | 9 of 14 | 9 of 14 |
| Per day, mean (90% CI), per MW | +$36 (+$10 to +$66) | +$39 (+$12 to +$69) |
| Total **excluding the 10 best days** | about 0 | about 0 |
| Already in the buy band | 84% | 66% |

## Late-Sep / Oct spikes
- **Caught by S1:**
  - Sep 17 HE21.
  - Sep 28 HE22.
  - Oct 4 HE18–20 (headroom 7.1–7.5k, CAHR 10.8–11.6).
- **Missed by S1:**
  - Sep 27 HE19 (headroom 9.8k).
  - Oct 1 HE23.
  - Sep 30 HE8 (East congestion).
- **Oct 1 HE18–19:** these were tight sell hours. That is the sell loss tail, not a missed buy.

## Read
- A positive-expectation lottery: it loses a little most evenings, and about 10 days a year pay for everything.
- This fits "sell small, buy the spikes" only if it is sized small and kept steady, because you cannot know which day it pays.
- **Not wired.** Waiting on the desk's decision on size.

## Follow-up: caught vs missed (`model/spike_misses.py`, `model/spike_tvu.py`)

### Where the spikes fell
East had 721 spike hours (RT−DA ≥ $50), Sep 2025 – Oct 6 2026:

| What we did | Share |
|---|---|
| SHORT (tight or surplus sell) | 50% |
| Buy band, but bid too low to clear | 21% |
| No signal | 19% |
| Caught | 10% |

Ottawa looks the same.

### Common thread in the big ones
Tesla was far above its usual gap to IESO (**tvu** = Tesla − IESO, minus its 30-day median, same HE):

| Day | tvu |
|---|---|
| Sep 27 | +1,014 |
| Oct 1 | +303 / +376 |
| Oct 4 | +626 to +843 |

Medians:
- Spike hours: +100 to +150.
- Non-spike hours: +17.

### Tight sells when tvu ≥ +200 (675 h per zone)

| Tight sells | East | Ottawa |
|---|---|---|
| tvu ≥ +200: edge per MWh | +$2.3 | +$2.6 |
| tvu ≥ +200: H2 | +$0.5 | +$0.9 |
| All other tight sells: edge per MWh | +$17.7 | +$17.3 |
| Share of the >$100 losing hours carried by tvu ≥ +200 hours | 42% | 42% |

### Best long set: HE16–21, not a sell, tvu ≥ +300, headroom < 9k

| | East | Ottawa |
|---|---|---|
| Per MWh, H1 / H2 / last 90 | +$16 (2 / 20 / 19) | +$20 (23 / 20 / 18) |
| Hit rate | 37% | 37% |
| Days | 58, 21 up | 60, 23 up |
| Median day per MW | −$10.5 | −$10.8 |
| Mean day per MW | +$35 | +$45 |

Best days: Jul 27 (+$800/MW), Oct 4 (+$264/MW), Jan 16 (+$1,102/MW Ottawa). It fires about once a week, all year (not only winter).

## Hard backtest of both Tesla ideas (`model/tesla_rules_bt.py`): NEITHER ADOPTED
Period: Sep 12 2025 – Oct 6 2026, ladder-level P&L. All numbers below are for East; Ottawa is similar.

### A. Skip tight sells when tvu ≥ 200
| Measure | Result |
|---|---|
| Total P&L | 2.62M → 2.47M (−$157k) |
| H2 / last 90 days | +$3k / −$49k |
| Days worse than −$5k | 45 → 26 |
| Sharpe | 4.4 → 5.2 |
| Worst day | −181k → −168k |

- The skipped hours still made +$157k on the ladder, because they are offers that cleared high.
- The threshold grid is not a plateau: 300 is worse than both 200 and 400, and skipping only above 700 makes more than the baseline.
- A walk-forward threshold loses $332k vs not skipping.
- Read: tvu does pick worse-than-average tight hours (the placebo is at the 100th percentile), but skipping them gives up money.

### B. Spike buy: HE16–21, not a sell, tvu ≥ 300, headroom < 9k (bid at DA forecast + $30)
| Check | East | Ottawa |
|---|---|---|
| Placebo percentile (random evening non-sell hours) | 76 | 93 |
| Placebo percentile, inside headroom < 9k | 60 | 88 |
| Day-bootstrap 90% CI | −$26 .. +$3.3k | — |
| Without the best 5 days | Negative | Negative |

- None of the placebo results reaches significance (95).
- Grid: with headroom < 8k, tvu ≥ 300 loses money; across the grid, the result does not improve on dropping the tvu filter.
- East H1 for the rule: +$66 per MW (about zero).
- Walk-forward mostly picks tvu ≥ 0, not 300.
- Read: tvu adds nothing reliable beyond headroom. The rule's profit is a handful of days.
