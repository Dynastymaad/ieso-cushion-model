# Risk gauge wired into the model (Oct 9 2026) -- run_model.py, tests: gauge_wire_test.py, short_gauge.py
Unpriced signs (known at the bid): Tesla >= IESO + 150 | IESO wind falling >= 200 MW over 3 h | gas need rising >= 500 MW over 3 h.
An hour counts max(its own signs, previous hour's signs).
- 2+ signs on a model SELL -> sell removed ("NO SHORT").
- 2+ signs on a non-sell hour -> separate long, 10 MW, bid DA fc + $30 ("RISK BUY"), unless Spike Watch already holds it.
- 0-1 signs: unchanged. Label per hour: SHORT OK (DA rich, no sign) / SHORT, 1 SIGN / NO EDGE / WATCH / NO SHORT / LONG.
Backtest per MW, Sep 2025 - Oct 6 2026 (vs current sells only):
| | Total | H1 | H2 | Last 120 | Last 60 | w/o best 3 | Worst day |
|---|---|---|---|---|---|---|---|
| East current sells | 28.8k | 14.8k | 14.0k | 12.7k | 4.8k | 22.9k | -2.3k |
| East with gauge | 43.3k | 21.0k | 22.4k | 13.6k | 4.9k | 37.8k | -1.0k |
| Ottawa current | 18.2k | 12.7k | 5.5k | 11.3k | 4.1k | 11.9k | -2.8k |
| Ottawa with gauge | 33.3k | 16.8k | 16.4k | 12.8k | 4.1k | 27.6k | -2.8k |
Threshold grid (27 combos): better total 100%, last 120 days 93-100%, last 60 days only 26-30% (recent period ~flat).
Rejected: half-size 1-sign sells (worse); steep ramp counted double (worse); dropping surplus sells HE10-19 (helps but segment picked after looking; not wired).
Oct 9: gauge would have bought HE5-6 (+15.7, +15.2) but still sold HE7-8 (1 sign each: rich DA, gas ramp). HE7 lost $38/MWh; 1-sign rich shorts average +$5.1/MWh with 12% of hours losing $50+.
