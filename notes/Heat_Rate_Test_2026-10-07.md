# Implied heat rate test (Oct 7 2026)

## Setup
- **IHR** = our DA forecast ÷ Dawn gas.
  - Dawn is the last CVX settle for day D, struck on or before D-2, so it is known at the bid.
- IHR level shifts with the season, so each hour is ranked as a **percentile vs the trailing 60 days, same HE, through D-2**. This is walk-forward, with no look-ahead.
  - Cheap: below the 20th percentile.
  - Rich: above the 80th percentile.
- Signals are rebuilt as live: sells on 90-day thresholds, buy band on 120 days.
- Measured as price-taker DA−RT per MW, Sep 2025 to Oct 6 2026.
- Halves: H1 is before Feb 15 2026; H2 is from Feb 15 on.
- Scripts:
  - `model/hr_test.py` → `data/hr_test_2026-10-07.csv`, `data/hr_test_quintiles_2026-10-07.csv`
  - `model/hr_test2.py` → `data/hr_test2_2026-10-07.csv`

## Results ($/MWh; H1 / H2 / last 90 days)

| Bucket | East | Ottawa |
|---|---|---|
| Tight sells, IHR rich | **+17.3** (10.2 / 30.4 / 32.0), 940 h | **+18.3** (12.5 / 29.8 / 32.6), 963 h |
| Tight sells, IHR mid | +9.9 (10.1 / 9.5 / 13.2) | +8.0 (7.4 / 9.5 / 13.3) |
| Tight sells, IHR cheap | +0.3, 83 h | +6.9, 73 h |
| Surplus sells, cheap / mid / rich | −0.3 / +0.5 / +3.3 | −3.3 / −3.0 / −0.1 |
| Buy band, cheap / mid / rich | −2.2 / +12.9 / +11.7 | −2.4 / +14.0 / +12.1 |
| NEW: buy cheap no-signal hours | +2.2 (−0.4 / 5.3 / −1.3) | +2.8 (−0.4 / 7.1 / 1.7) |
| NEW: sell rich no-signal hours | −1.8 (7.5 / −5.6 / −2.0) | −1.5 (3.9 / −3.3 / 1.9) |

Sizing tests (price-taker; total $ per MW vs live 48,648 East / 43,493 Ottawa):

| Sizing | East | Ottawa |
|---|---|---|
| Rich sells ×1.5 | 57,097 | 52,318 |
| Cheap sells ×0.5 | 48,838 | 44,915 |

Both halves improve in both sizing tests.

## Read
- **IHR grades the tight sells.** When DA is priced rich vs gas in a tight hour, RT comes in about $17–18 under DA, against about $8–10 for normal-IHR tight sells. This holds at both zones, in both halves and in the last 90 days.
- **It does not create new trades.** Buying "cheap" hours or selling "rich" hours outside our signals is flat or negative and flips sign between halves.
- **Cheap DA is not a buy signal.** Buy-band hours with cheap IHR lost money; mid and rich buy-band hours carry the edge.
- **Surplus sells are not helped by IHR.**

## Limit
- Sells already fill the zone cap (East 85, Ottawa 100), so the ×1.5 upsizing is not directly tradeable.
- Usable forms: a confidence flag (rich tight = A-grade, full cap, priced to clear), or freeing cap from weaker hours.
- Not wired in. Pending the user's decision.
