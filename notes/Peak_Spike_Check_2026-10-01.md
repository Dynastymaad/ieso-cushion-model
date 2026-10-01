# Peak-spike and cushion check for Oct 1 (run Sep 30)

## Units
- Lennox G1/G2: capability 525 MW each, all week, with 0 output. They are available but not dispatched (too costly to run), so this is not an outage. They are in headroom as available gas.
- Lennox G3: capability dropped to 0 on Sep 30. G4 has been at 0 since Sep 24. Both are real outages, and both are in the outage total the DA priced.
- Cardinal: capability 150-184 MW with 0 output. Economic, same as G1/G2.
- Brighton Beach: capability 642 MW flat. Output swings 243-470 MW, which is dispatch, not a derate.
- Takeaway: the fleet is available but out of the merit order. The risk is that G1/G2/Cardinal are slow to start if called in real time, which is what makes an RT pop possible.

## Cushion at the bid (HE8-21 minimum; hours below 7,000)

| Day | Min headroom | Hours below 7,000 |
|---|---|---|
| Sep 25 | 8,470 | 0 |
| Sep 26 | 10,080 | 0 |
| Sep 27 | 9,820 | 0 |
| Sep 28 | 6,460 | 4 |
| Sep 29 | 4,790 | 9 |
| Sep 30 | 5,240 | 9 |
| Oct 1 | 5,220 | 14 |

- Oct 1's peak is about the same as Sep 30 and looser than Sep 29. The morning (HE8-13, 6,400-6,900) is the tightest in the window.
- Drivers: demand is up about 2 GW vs Sep 25-27, nuclear outages are up about 1.4 GW and gas outages about 0.6 GW. Wind of about 1.9 GW partly offsets this.

## Recent peak RT (East HE16-21)
- RT above $100: Sep 17 (118), Sep 27 (260 at HE19), Sep 28 (109), Sep 29 (105). Other days peaked at $37-80.
- Sep 27 and 28 had DA around $50-69, so those spikes were large relative to DA. On Sep 29 DA was already $81-95.
- Sep 30 DA is $88-103 and Oct 1's forecast is $87-94, so a $100 print now costs about $10, not $50.

## Walk-forward tests (Jul 2025 - Sep 2026, tight peak sells HE16-21)
- By the number of RT>$100 peak hours in the prior 3 days:
  - 0 hours: +$38/MWh.
  - 1-3 hours: +$6 to +$17/MWh.
  - More than 3: +$10.7/MWh, with a 11% chance of RT beating DA by more than $100.
- The effect is not monotonic, and the halves disagree:
  - H1: a hot streak was better.
  - H2: a hot streak was worse, but still positive.
- Hot streak plus a day minimum below 5,500 MW (127 days): +$7.8 East and +$8.8 Ottawa, with P(RT>DA+100) about 11%.
- By DA level: DA $85-100 averages +$8.8; DA above $100 averages +$15-20. Higher DA leaves more room.
- Conclusion: the short stays positive in every state tested, so no skip or size-down rule is warranted. This is consistent with the earlier rejected RT>$100 rule, which cost about $1.4M per zone. The loss tail is real (about 1 hour in 10), and it is the cost of the edge.
