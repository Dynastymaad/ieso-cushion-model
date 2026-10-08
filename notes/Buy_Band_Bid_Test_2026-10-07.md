# Raising buy-band bids: deep check (Oct 7 2026). NOT ADOPTED

## Setup
- Scripts: `model/buyband_bid_test.py` (bid levels) and `model/buyband_deep.py` (the checks below).
- Period: Sep 2025 – Oct 6 2026, buy-band hours only (walk-forward band).
- Ladder: VA score-1 bids, cleared on the actual DA.
- P&L: MW × (RT − DA).

## Headline (looked great)
Raising every bid by $30 made about 3× the total P&L:

| Zone | Current | +$30 |
|---|---|---|
| East | $421k | $1.21M |
| Ottawa | $496k | $1.45M |

Every step up was positive in both halves.

## Why it is not adopted

### 1. It is a spike trade, not an edge on typical hours
- Even at the current bids:

  | Measure | Value |
  |---|---|
  | Median RT−DA | about −$2.5 |
  | Hours where RT beat DA | 43% |
  | Mean RT−DA | +$8 |

  The positive mean comes from a few large RT spikes (95th percentile +$74 to +$82).
- The extra hours that +$30 clears look the same:

  | Measure | Value |
  |---|---|
  | Median RT−DA | about −$4 |
  | Hours where RT beat DA | 40–41% |
  | 5th percentile | −$41 |
  | 95th percentile | +$90 to +$99 |

### 2. The gain disappears when RT spikes are capped
Gain from +$30 vs current, by RT cap:

| RT capped at | East | Ottawa |
|---|---|---|
| No cap | +$794k | +$952k |
| $200 | +$306k | +$295k |
| $150 | +$68k | +$29k |
| $100 | −$386k | −$460k |

### 3. Day by day, it loses more often than it wins
- East: 124 days better, 130 days worse. Ottawa: 145 better, 160 worse.
- The top 5 days provide 41–49% of the gain.

### 4. The gain sits in winter (Dec–Feb) and is small lately
Gain from +$30 vs current, recent months:

| Month | East | Ottawa |
|---|---|---|
| Jul | −$5k | +$72k |
| Aug | +$4k | +$51k |
| Sep | +$62k | +$13k |

In the last 90 days the extra hours averaged +$1.7 (East) and +$3.8 (Ottawa), with a negative median.

### 5. Control test: much of it is not the buy band
- Bidding +$30 on hours with **no signal** also "made" +$350k–$470k.
- So the effect is largely "own RT, catch spikes", not something specific to the band.
- The band still does better per hour: about $440/h vs $130/h at East.

## Conclusion
This is a lottery-ticket long: it loses a little on most hours and wins big on rare spikes, mostly in winter. It would lower the hit rate and make P&L lumpy. That does not suit a sell-led book that is currently 6W–1L.

## Revisit
Revisit before winter (late November). Test a winter-only, evening-only variant (HE17–22), where the gain was largest.
