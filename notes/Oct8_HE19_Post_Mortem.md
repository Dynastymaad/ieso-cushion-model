# Oct 8 2026 HE19 post-mortem (IESO public reports, read Oct 8 evening)

## Prices
| Hour | DA | RT | Congestion | RT 5-min |
|---|---|---|---|---|
| East HE18 | $84.6 | $76 | $0 | |
| East HE19 | $95.3 | **$272** | $0 | 145, **517, 532, 536, 468**, 256, 235, 145, 139, 139, 87, 68 |
| HE20 | $71.7 | $72 | | |
| HE21 | $48.5 | $18 | | 0 for 8 intervals |

- Every zone paid the same price at HE19: Ottawa $277, Toronto $268, West $265.
- HE19 was a system-wide spike, not East/Ottawa congestion.

## Bid-time view vs what happened (HE18 / HE19)
| Item | At the bid (Oct 7 07:49) | Actual / latest (Oct 8 19:52) | Change |
|---|---|---|---|
| IESO demand | 16,858 / 17,168 | 17,058 / 17,268 | +200 / +100 |
| Wind | 1,800 / 1,673 fc | 1,443 / 1,365 actual output | −357 / −308 |
| Gas outages | 3,075 | 3,076 | 0; no unit trips in GenOutputCapability |
| Hydro outages | | | +50–90 |
| Net exports (DA cleared → RT) | 2,897 / 2,668 | 2,472 / 2,523 | −425 / −145 (helped) |
| Storage | | 824 / 1,057 MW discharging at HE18–19 (maxed) | |

- Net tightening at HE19: about +300 MW.
- Gas output at HE19 was 4,861 MW against about 8,260 available. Supply was not short. The spike was ramp scarcity: wind falling, solar gone and load peaking at once.

## Was it visible at the bid?
**Yes: the evening ramp was extreme.** Residual load rose about +2,470 MW from HE15 to HE19, the 98th percentile of the last 60 days. Wind was forecast to fall about 450 MW into HE19.

**Test (tight sells HE17–20 by ramp percentile, since Sep 2025)**

| Evening ramp | Per MWh | Hours losing more than $100 |
|---|---|---|
| Top 10% | **+$5.8** | 11 of 102 |
| Otherwise | +$15 to +$22 | |

The top 10% is still positive on the ladder (+$47k per zone). Oct 1 was a normal ramp (46th percentile), so ramp does not explain every blow-up.
