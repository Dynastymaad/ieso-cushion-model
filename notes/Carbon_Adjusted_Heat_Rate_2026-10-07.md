# Carbon-adjusted heat rate (CAHR), Oct 7 2026

## Formula (`model/cahr.py`)

```
Price = HR × Gas + (HR × 0.0554 − Benchmark) × CarbonPrice
HR    = (Price + Benchmark × CarbonPrice) / (Gas + 0.0554 × CarbonPrice)
```

| Input | Value | Source |
|---|---|---|
| Price | Our DA forecast for the hour, CAD/MWh | Known at the bid |
| Gas | Dawn (ICE CVX) × USD/CAD, CAD/MMBtu | Last settle for day D, struck on or before D-2 |
| 0.0554 | tCO2e per MMBtu | Desk number |
| Benchmark | 0.310 tCO2e/MWh | Ontario EPS natural-gas generation standard (IESO APO Carbon Pricing Module, Mar 2024) |
| CarbonPrice | CAD/t: $80 (2024), $95 (2025), $110 (2026), +$15/yr to $170 in 2030 | Ontario EPS, which follows the federal benchmark |

How to read it, in MMBtu/MWh:

| CAHR | What it means |
|---|---|
| 6.5–7.5 | Efficient combined cycle |
| 8–9 | Older CCGT or cogen |
| 10–12 | Peaker |
| Above 12 | DA is priced above any gas unit's cost, so it carries a scarcity premium |

## Price-taker test (Sep 2025 – Oct 6 2026)

Figures are $/MWh. Columns read H1 / H2 / last 90 days. H1 is before Feb 15 2026; H2 is from Feb 15 on.

| Group | East | Ottawa |
|---|---|---|
| Tight sells, CAHR ≥ 12 | **+19.6** (15.1 / 27.3 / 25.3), 1,309 h | **+18.6** (14.3 / 26.2 / 25.0), 1,376 h |
| Tight sells, CAHR < 12 | +2.7 (3.4 / −0.5 / 8.7), 896 h | +2.1 (2.9 / −0.9 / 9.1), 792 h |
| Surplus sells | About 0 at every CAHR | Negative at most CAHR levels |
| Buy band, CAHR < 7.5 | −5.9, 84 h | −2.1, 104 h |
| Buy band, CAHR 10+ | +14 to +25 | +18 to +22 |

- A fixed 12 cut beats a 60-day percentile cut: more hours and more dollars.
- A buy-band filter that skips buys when CAHR < 7.5 adds only +$500 East / +$200 Ottawa total, and is flat in H2. **Not adopted.**

## Ladder test (`model/cahr_ladder.py`)

Sells are cleared on the actual DA. Figures are total $ over the period. Columns read H1 / H2.

| Change | East | Ottawa |
|---|---|---|
| A-grade (tight & CAHR ≥ 12): cap offers at 0.9 × RT forecast | 1.84M → **2.22M** (H1 +105k, H2 +277k) | 1.78M → **2.19M** (H1 +115k, H2 +294k) |
| B-grade (tight & CAHR < 12): offers +$10 | 305k → **442k** (H1 +126k, H2 +11k) | 231k → **345k** (H1 +100k, H2 +14k) |

Both changes make more money at both zones and in both halves. **Adopted.**

## Wired (Oct 7)

- `run_model.py`:
  - Each hour carries `cahr` and `grade` (A/B on tight score-5 hours).
  - Each hub carries `gas` (Dawn, FX, gas CAD, carbon price, benchmark).
- Page:
  - New CAHR column in the DA Virtual matrix; red when ≥ 12.
  - An A/B chip on tight sells.
  - `baseLadder()` reprices tight score-5 sells:
    - A: every offer becomes min(offer, 0.9 × RT forecast).
    - B: every offer +$10.
  - The what-if recomputes CAHR from the what-if DA.
- Unchanged: surplus sells, the buy band, MW sizes and the trips ×1.5 boost.

Backups: `run_model.bak_pre_cahr.py`, `page_template.bak_pre_cahr.html`.

## Also seen (not acted on)

Ottawa surplus sells lose money at the ladder level: −$146k over the period, both halves. This is worth its own test.
