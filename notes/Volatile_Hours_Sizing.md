# Size down or skip the volatile sell hours? (model/vol_test.py, Sep 28 2026)

Setup: the live rules exactly, zone caps East 85 / Ottawa 100 MW, fills on the actual DA, settled at RT, Jul 2025 – Sep 2026.
Only score-5 sell hours that meet a bid-time flag are changed. The flags were fixed in advance, with no tuning:
- headroom < 5,000 or < 5,500 MW
- our DA forecast ≥ $75 or ≥ $100

| East | Net | Change | Worst day | Max drawdown | Net / max DD |
|---|---|---|---|---|---|
| Live | 3.48M | | −195k | −411k | 8.5 |
| Headroom < 5,500, half size | 2.90M | −0.57M | −153k | −311k | 9.3 |
| Headroom < 5,500, skip | 1.84M | −1.64M | −125k | −251k | 7.3 |
| DA forecast ≥ $75, half size | 2.58M | −0.90M | −107k | −297k | 8.7 |
| DA forecast ≥ $75, skip | 0.81M | −2.66M | −104k | −185k | 4.4 |

| Ottawa | Net | Change | Worst day | Max drawdown | Net / max DD |
|---|---|---|---|---|---|
| Live | 3.33M | | −188k | −492k | 6.8 |
| Headroom < 5,500, half size | 2.56M | −0.77M | −160k | −423k | 6.1 |
| Headroom < 5,500, skip | 1.51M | −1.82M | −140k | −438k | 3.4 |
| DA forecast ≥ $75, half size | 2.13M | −1.19M | −140k | −383k | 5.6 |

**Findings**
1. **The flagged hours are the best hours, not the worst.** In the live run they made $19–24/MWh against the $7–8 average. Headroom < 5,500 alone brought in $1.64M at East and $1.82M at Ottawa.
2. **Half of the worst days do not come from these hours.** Big RT spikes also hit ordinary hours with headroom of 6,000–11,000 MW: East Oct 5, Oct 7, Mar 11 and Jun 10; Ottawa Nov 3, Apr 27, Dec 10 and Aug 24. Cutting the tight hours therefore removes a lot of profit and only part of the tail.
3. **Risk-adjusted, nothing wins at both zones.** At East, headroom < 5,500 at half size is slightly better on net / max drawdown (9.3 vs 8.5). At Ottawa it is worse (6.1 vs 6.8). Skipping is worse everywhere.
4. **Recommendation: no special rule.** If a drawdown of about −$400–500k is too large for the book, lower the overall Size × on the DA Virtual tab. Net and drawdown then scale together, which is about as efficient as any of the targeted cuts.

## September 2026, following the page exactly (simulated, walk-forward)
- **East:** +$172k over Sep 1–28; 19 up and 9 down days; best +$64k (Sep 1), worst −$5.7k; $9.35 per MWh cleared.
- **Ottawa:** +$168k; 21 up and 7 down days; best +$75k (Sep 1), worst −$5.6k.
- **Where it came from:** almost all from score-5 sells (East +$166k, Ottawa +$170k), and mostly Sep 1–3. Buy-band buys: East +$6k, Ottawa −$5k.
- **Caveats:**
  - Sep 28 has only 13 RT hours so far; Sep 29 has none.
  - This is the backtest engine, not real fills. The page was not live for East/Ottawa in September.
  - Uplift and fees are not included.

## The RT > $100 ≥ 40% rule (model/rt100_rule.py, walk-forward odds, Sep 28 2026)

```

================ EAST (cap 85 MW) ================
  2025 (2025-07-01..2025-12-31):
     follow page        net   +1,542,516   worst day   -195,174   max drawdown   -410,930   days < -$50k 8
     rule: half size    net   +1,277,350   worst day   -195,174   max drawdown   -410,930   days < -$50k 7
     rule: skip         net     +886,656   worst day   -195,174   max drawdown   -410,930   days < -$50k 6
  2026 (2026-01-01..2026-09-28):
     follow page        net   +1,933,968   worst day   -178,146   max drawdown   -232,682   days < -$50k 5
     rule: half size    net   +1,689,003   worst day   -157,637   max drawdown   -237,223   days < -$50k 5
     rule: skip         net   +1,163,593   worst day   -134,565   max drawdown   -254,736   days < -$50k 4
  all (2025-07-01..2026-09-28):
     follow page        net   +3,476,484   worst day   -195,174   max drawdown   -410,930   days < -$50k 13
     rule: half size    net   +2,966,353   worst day   -195,174   max drawdown   -410,930   days < -$50k 12
     rule: skip         net   +2,050,249   worst day   -195,174   max drawdown   -410,930   days < -$50k 10
  flagged sell hours (odds >= 40%): 797 hours on 104 days, 671 filled. At full size they netted +1,426,235 (won +2,765,741, lost -1,339,506); hours losing $10k+: 43 totalling -923,645. By year: {'2025': 655860, '2026': 770376}
  all hours that lost $10k+ following the page: 163 (-3,241,327); the rule flagged 43 of them (-923,645)
  10 worst days following the page, and what the rule would have done:
      date  follow    half    skip  flagged_hours
2025-11-10 -195174 -195174 -195174              0
2026-01-24 -178146 -157637 -134565              1
2025-12-04 -158422  -81975    4027             10
2025-10-05  -86034  -86034  -86034              0
2025-10-07  -84082  -84082  -84082              0
2026-08-07  -70307  -50507  -28233              4
2026-03-11  -68751  -68751  -68751              0
2026-06-10  -64707  -64707  -64707              0
2026-05-29  -61288  -61288  -61288              0
2025-07-01  -58909  -58909  -58909              0
  10 best days following the page, and what the rule would have done:
      date  follow   half   skip  flagged_hours
2026-01-26  177438 177438 177438              0
2026-07-14  163198  92691  13372             12
2026-02-05  124195 124195 124195              0
2026-01-30  118127 100350  31783             11
2026-07-02  108960  87765   6016             13
2026-01-27  106066 106066 106066              0
2026-02-08  102443  86729  26118             16
2025-12-11  102396  92271  80880              1
2026-07-15   94541  53963   3199             13
2025-12-12   94042  77150  11994             15

================ OTTAWA (cap 100 MW) ================
  2025 (2025-07-01..2025-12-31):
     follow page        net   +1,238,218   worst day   -169,034   max drawdown   -491,877   days < -$50k 14
     rule: half size    net   +1,002,603   worst day   -149,696   max drawdown   -491,877   days < -$50k 12
     rule: skip         net     +732,752   worst day   -149,696   max drawdown   -491,877   days < -$50k 12
  2026 (2026-01-01..2026-09-28):
     follow page        net   +2,088,212   worst day   -187,982   max drawdown   -417,991   days < -$50k 8
     rule: half size    net   +1,695,196   worst day   -164,652   max drawdown   -426,572   days < -$50k 7
     rule: skip         net   +1,119,541   worst day   -141,322   max drawdown   -454,697   days < -$50k 8
  all (2025-07-01..2026-09-28):
     follow page        net   +3,326,430   worst day   -187,982   max drawdown   -491,877   days < -$50k 22
     rule: half size    net   +2,697,799   worst day   -164,652   max drawdown   -491,877   days < -$50k 19
     rule: skip         net   +1,852,293   worst day   -149,696   max drawdown   -491,877   days < -$50k 20
  flagged sell hours (odds >= 40%): 835 hours on 108 days, 697 filled. At full size they netted +1,474,137 (won +3,087,706, lost -1,613,569); hours losing $10k+: 50 totalling -1,147,214. By year: {'2025': 505466, '2026': 968671}
  all hours that lost $10k+ following the page: 200 (-4,517,515); the rule flagged 50 of them (-1,147,214)
  10 worst days following the page, and what the rule would have done:
      date  follow    half    skip  flagged_hours
2026-01-24 -187982 -164652 -141322              1
2025-12-04 -169034  -78804   11426             10
2025-11-10 -149696 -149696 -149696              0
2025-11-03 -140234 -140234 -140234              0
2026-04-27 -113106 -113106 -113106              0
2025-12-08 -110077  -47854   14369             18
2025-12-10 -105814 -105814 -105814              0
2025-08-24  -98533  -98533  -98533              0
2025-10-07  -95468  -95468  -95468              0
2025-07-01  -94284  -94284  -94284              0
  10 best days following the page, and what the rule would have done:
      date  follow   half   skip  flagged_hours
2026-01-26  205494 205494 205494              0
2025-12-11  180953 165137 149321              1
2026-07-14  175651  95483  15315             12
2026-02-05  139192 139192 139192              0
2026-01-30  138535 105188  35929             11
2026-07-02  129821  91086  10636             13
2026-01-28  122366 122366 122366              0
2026-01-27  115372 115372 115372              0
2026-07-03  115341  60710   6080             12
2026-02-08  110154  80717  19577             16
```
