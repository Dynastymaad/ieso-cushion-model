# Short risk-reward gauge (Oct 9 2026) -- model/short_gauge.py, data/short_gauge.csv
Short P&L = DA - RT, every hour, East Sep 12 2025 - Oct 8 2026. Rich DA = CAHR >= 10 or headroom < 7,000 or DA fc >= 30d median + $10.
Unpriced risk signs = Tesla >= IESO+150 | IESO wind falling 200+ (3h) | gas need +500 (3h).
| Setup | Hours | Avg | Win | Win$/Loss$ | Worst 5% |
|---|---|---|---|---|---|
| Rich, 0 signs | 1,770 | +5.9 | 65% | 1.29 | 129 |
| Rich, 1 sign | 1,484 | +5.1 | 65% | 1.24 | 118 |
| Rich, 2-3 signs | 633 | -10.5 | 60% | 0.72 | 222 |
| Normal/cheap, 0 | 2,989 | +0.9 | 65% | 1.14 | 31 |
| Normal/cheap, 1 | 1,832 | -0.9 | 62% | 0.89 | 41 |
| Normal/cheap, 2-3 | 659 | -11.4 | 58% | 0.43 | 123 |
Rich 0-1 rows positive both halves and last 120 days (+7.4/+9.8). Ottawa same. Display/judgement only; scoring unchanged.
Note: earlier advice "tight hours with 4+ signs keep the sell" counted PRICED signs (spare, CAHR); with the 3 UNPRICED signs, 2+ means don't short.
