# Why the last two weeks went flat or negative: evening sells (Oct 9 2026, TESTS ONLY, nothing wired)

## The model's calls at a flat 10 MW, Sep 24 – Oct 8 (price-taker, Oct 8 RT from IESO)
| | East | Ottawa |
|---|---|---|
| Total | **−$1,524** | **−$3,579** |
| Evening HE16–21 | −$4,054 | −$4,776 |
| All other hours | +$2,530 | +$1,197 |
| Without Oct 1, 7 and 8 | +$6,068 | +$5,103 |

Buys (buy band) made +$3.1k at East and +$0.7k at Ottawa. The damage was **short** evening hours that spiked.

## Evening sells by month: the typical hour wins every month, but 10–18% of hours blow up by $50+
**East, $/MWh**

| | 25-07 | 25-08 | 25-09 | 25-10 | 25-11 | 25-12 | 26-01 | 26-02 | 26-03 | 26-04 | 26-05 | 26-06 | 26-07 | 26-08 | 26-09 | 26-10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Mean | −6 | +13 | +19 | −1 | +1 | +1 | +55 | +40 | +3 | +2 | −18 | −13 | +59 | +7 | +25 | −24 |
| Blow-ups | 15% | 11% | 7% | 15% | 17% | 18% | 12% | 11% | 5% | 7% | 13% | 13% | 3% | 14% | 0% | 15% |

- The edge comes from a few months: Jan–Feb, Jul, Sep.
- In Oct–Dec 2025 and Mar–Jun 2026 it was about break-even or negative, and Oct 2026 looks the same.
- Only about 16 months of data exist (IESO's new DA market started May 2025), so this seasonal pattern has been seen only once.

## Things tested that did NOT fix it
1. **Stop or flip evening sells when they lost over the last 7–60 days.** Every version made less than the live model, and flipping made much less.

   | | East | Ottawa |
   |---|---|---|
   | Live | 17,882 | 14,334 |
   | Best skip version | 15,190 (7 days) | 11,852 (14 days) |

   Recent results do not predict the next days.
2. **Only sell evenings when DA clears $10–20 above our forecast.** $/MWh goes up, but the total goes down (East 17.9k → 9.7–10.1k), and the blow-up rate rises from 12% to 16–18%.
3. **Earlier today:**
   - The tight-evening guard: the no-edge part lost money; the flip part fails without its best 3 days and when thresholds are picked walk-forward.
   - Shorter lookbacks, an unbiased segment model, and an all-fundamentals model.

## Read
The evening sell is a "small win most days, big loss on a few" trade. Its yearly profit depends on which months you are in.
