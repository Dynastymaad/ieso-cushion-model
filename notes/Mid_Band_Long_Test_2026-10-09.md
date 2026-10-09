# Long 7,000-9,000 MW headroom vs the adaptive buy band (Oct 9 2026)
Scripts: model/mid_band_test.py, model/band_fix_test.py. Long bid = DA fc + $30, P&L = RT - DA per MW, non-sell hours.

## Fixed 7-9k long (East, Sep 2025 - Oct 8 2026)
- 2,000 h, +$10.1/MWh, total +20.2k; H1 +12.7k, H2 +7.4k; last 120 days +1.6k (+$2.6/MWh); last 60 +0.4k; w/o best 3 days +14.6k; placebo 100%.
- Positive 12 of 14 months; strongest Dec-Feb (+$18-24/MWh); Aug -$1.5/MWh.
- Ottawa the same.

## The adaptive band already trades it
- Live rule (trailing 120 days, 2,000 MW wide, mean DA-RT <= -3) sat at 7,000-9,000 / 7,500-9,500 almost all year.
- It moved to 9,500-11,500 at the end of Sep because 7,500-9,500 only averaged RT-DA +$1.9 over the last 120 days (threshold $3).
| East | Total | Last 120 | Last 60 | w/o best 3 |
|---|---|---|---|---|
| Live adaptive band | +19.6k | +1.8k | +0.8k | +14.0k |
| Fixed 7-9k | +20.2k | +1.6k | +0.4k | +14.6k |
| Live OR 7-9k | +20.7k | +2.0k | +0.8k | +15.1k |
| 7-9k add-on only | +1.1k | +0.1k | 0 | -0.2k |
Ottawa: live +24.2k, fixed +21.7k, add-on +1.5k (w/o best 3 +0.5k).
- Learning the band on non-sell hours only: worse (East +14.8k, Ottawa +18.7k).

## Decision
No change. The adaptive band is the 7-9k long most of the year; switching to a fixed band is no better and worse recently.
The add-on is small and not robust in East. Sells under 7,000 still pay (evening +$12.8/MWh, last 60 days +2.6k East).
