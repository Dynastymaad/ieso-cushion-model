# Hours where RT came in $50+ above DA (East / Ottawa), Sep 25 - Oct 2

| Day | HE | DA | RT | RT−DA | Main cause |
|---|---|---|---|---|---|
| Sun Sep 27 | 19 | 58 | 260 | +202 (both zones) | Load beat IESO (+257, then +813/+1,111 at HE20-21); 921 MW of outages added after the bid at HE18; evening ramp. Headroom 9.5k, so not tight |
| Wed Sep 30 | 8 | 55 | 110 | +55 East only | East congestion +$286 for 3 intervals (05-07); Ottawa and Ontario ~$38. Local transmission event |
| Thu Oct 1 | 18 | 101 | 379 | +279 | Wind −370 vs forecast; outages +234; ramp from HE17 interval 9; final headroom 5,880 |
| Thu Oct 1 | 19 | 115 | 348 | +233 | Wind −361; outages +349; final headroom 5,197 (−529 vs bid) |
| Thu Oct 1 | 23 | 48 | 108 | +60 | Load +833 vs IESO; wind −451; outages +687 at HE22 |

## 5-minute shape (East)
- **Sep 27 HE19:** 72, 210, 360, 229, 236, 360, 91, 229, 416, 418, 416, 84. Repeated spikes inside the hour: scarcity at the margin.
- **Sep 30 HE08:** $38 flat, apart from 324 for intervals 5-7, with congestion of $286.
- **Oct 1:**
  - HE17 climbs from interval 8 (78 → 317).
  - HE18 sits at 320-432 all hour.
  - HE19 runs 376-426, then falls to 128 by interval 12.
  - HE20 is back to $55.
- **Oct 1 HE23:** $108 flat all hour. A sustained tightness, not a single spike.

## What the bid-time data said
- **Sep 27:** Tesla was +805 to +916 MW above IESO at HE17-20. That signal was right: load came in well above IESO by HE20-21. The model had no position here; headroom of 9.8k put it just above the buy band.
- **Oct 1 HE18-19:** Tesla showed nothing (+78 to +215). Meteologica was missing. Headroom was already tight and DA was already at $100+. The model was short, so this is the tight-sell loss tail: about 1 hour in 10 loses more than $100.
- **Oct 1 HE23:** the East buy (HE23-24) won.

## Pattern
- **Supply surprises after the bid drove these moves, not load.**
  - Wind came in 350-450 MW short on Oct 1 evening.
  - IESO added 200-900 MW of outages after the bid.
- The spikes start on the evening ramp (HE17-19) and fade once load turns over (HE20).
- **Load:** IESO over-forecast the peak but under-forecast the late evening on both Sep 27 and Oct 1.
- Caveat: actual load uses the warehouse hourly series, which may be an hour off in places.
