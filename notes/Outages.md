# Outages — what the model uses, what the Outages tab shows, and what was tested (28 Sep 2026)

## 1. Inside the model (what changes a trade)
| piece | where | what it does | tested result |
|---|---|---|---|
| Outages in headroom and gas need | IESO pre-DA Adequacy (last version before D-1 09:00 EST) | gas / nuclear / hydro outages reduce available supply. Headroom = gas + hydro available − (IESO demand − nuclear available − wind − solar) | the base of the v2 signal |
| **Trips in the last 24 h** | `model/outage_timeline.py`, `da_virtual.trips_d1()` | outage MW that appeared on yesterday's own hours *after* yesterday's bid, as known at today's bid | score-5 sells ×1.5 when ≥ 500 MW **and the sell is on the tight branch** (changed 28 Sep: surplus sells showed no edge from trips, `model/boost_test.py`). Those sell hours made +12.33 $/MWh (90% +6.96..+18.00) vs +3.66 otherwise; both halves and both hubs agree; walk-forward +11.32. Toronto net +3.67M → +4.43M; worst day unchanged |
| SCARCITY flag | headroom < 2,000 MW | chip only | 12 days, too few for a rule |

**How "trips in the last 24 h" is computed**
1. The source is every re-issue of IESO's Adequacy report since May 2025, from `pull_history.py --only outages`. We keep only the moments a value changed.
2. For each hour of yesterday we read the gas + nuclear + hydro outage MW twice:
   - in the version IESO published before *yesterday's* 09:00 EST bid
   - in the latest version before *today's* 09:00 EST bid
3. Trips = the second number minus the first, per HE: the units that went down in the last day and weren't in the plan.
4. On the DA Virtual tab, a score-5 hour on the tight branch (spare below the signal's learned threshold) with trips ≥ 500 MW gets its ladder MW × 1.5 and shows a ×1.5 chip. Surplus-branch sells are not boosted.

**Why it works.** After a run of trips, the day-ahead market over-prices the next day's risk. The DA bids are built by people who have just watched units fail; RT usually settles lower than that fear.

**What does NOT hurt us, even though it looks like it should**
- IESO's return-to-service assumptions slip. When IESO assumes 1,000+ MW will be back, about 711 MW is added back after the bid, against 147 MW when it assumes none.
- But sells on those hours made +$6.61/MWh: DA already prices the slip.
- The outages that do hurt us arrive after the DA results. 87% of big-loss hours saw the addition arrive after ~13:30 EST on D-1, often overnight or on the day. They cannot be seen at 08:00 MT.

## 2. Outage levels and seasonal ratios (history back to 2019)
- **Source:** IESO `GenOutputCapabilityMonth`, per unit and per hour, May 2019 – Sep 2026 (`model/outage_history.py`).
- **Method:** each unit's rating is the 98th percentile of its capability over the trailing year; outage = rating − capability.
- **Check:** it matches IESO's own Adequacy gas outage (corr 0.989 over 12,336 overlap hours).
- **Gas outage as a share of capacity** (median, peak hours), with the busiest trip months:

| months | median share out | note |
|---|---|---|
| Jul–Aug | 6–7% | |
| Jan–Feb | 8% | |
| Jun | 13% | ~59 short gas trips a month |
| Sep | 11% | |
| Dec | 11% | ~58 short gas trips a month |
| Apr–May | 21–26% | spring maintenance |
| Oct–Nov | 20–26% | fall maintenance; Nov ~61 short gas trips a month |

  The maintenance seasons are the same shoulder months where our losing sell days cluster.
- **Test: is an above-normal outage level a signal?** No. Bid-time gas outage above its monthly P75 gave DA−RT +2.23 (90% range −1.60..+5.82); inside the normal range +2.95; below P25 −3.01 (−8.04..+2.32). It's on the tab as context, not in the signal.
- **Nuclear:** 2025–26 has sat above its historical range almost all the time (refurbishment programmes), so the nuclear share isn't a useful "normal". The tab tells you to read nuclear in MW.

## 3. The 35-day schedule
- **Source:** IESO `Adequacy3`, one public file per day for the next 34 days. `ieso_fwd35.py` downloads today's set, keeps a dated snapshot and writes `data/fwd35.csv`. No login, so the GitHub job can run it.
- **How far off IESO's schedule runs,** measured on 17 months of vintages (`cache/ieso_adq2_leads.csv`). IESO's schedule understates gas outages by:

| lead | understated by |
|---|---|
| at the bid | 179 MW |
| 2 days out | 313 MW |
| 7 days out | 534 MW |
| 15 days out | 763 MW |

  Nuclear is understated by 26 → 198 MW over the same leads.
- **What the tab plots:** the schedule, an "expected" line (schedule + that measured shortfall at each lead) and the normal range for the month.
- **Leads 16–34:** their history needs `pull_history.py --only fwd35`. Until then the tab holds the 15-day value and marks those rows with *.

## 4. The 18-month Reliability Outlook
- **Editions:** all eight editions of the tables from Dec 2024 to Sep 2026, from ieso.ca → `data/outlook/`, parsed by `model/outlook18.py`.
- **What we read:** the weekly "Reductions by Fuel Type" (firm scenario), and the external-intertie transmission outage list.
- **How good it has been.** Each week was scored against the last edition published at least a week before (73 weeks):

| | corr | bias | MAE | naive "same as 4 weeks ago" MAE |
|---|---|---|---|---|
| gas | 0.62 | −241 MW | 628 MW | 1,009 |
| nuclear | 0.54 | −964 MW | 1,087 MW | |

  Nuclear misses unplanned outages: for example, +1,700 MW from Aug 2026 wasn't in the June edition.
- **How to use it:** as the gas maintenance calendar, with nuclear treated as a floor.

## 5. Do I bake outage MW into the load?
**No.**
- **Already counted:** outages are supply. They're already inside tomorrow's headroom and gas need, and the signal thresholds were learned on those same numbers. Adding them to load would double-count.
- **Late news:** if you hear of an outage after IESO's report, move the **Gas / Nuclear available** slider on the DA Virtual tab instead.
- **Beyond tomorrow:** the 35-day "expected" line already adds the typical unscheduled outages.

## 6. What to run
| command | how often | what it feeds |
|---|---|---|
| `python ieso_fwd35.py` | daily | the 35-day schedule |
| `python pull_history.py --only outages --since 2025-05-01` | daily, until the GitHub job computes trips from the archived Adequacy3 versions | trips in the last 24 h |
| `python pull_history.py --only fwd35 --since 2025-05-01` | once | the 16–34 day lead history |
| `python ieso_backfill.py` | daily | the per-unit and Adequacy3 archives |

## 30-day lookback and "is it priced in?" (Sep 28 2026, `model/outage_priced.py`, `outages_tab.look30`)
- **30-day table (Outages tab):** each of the last 30 days shows the gas, nuclear and hydro MW that were out at the bid (peak HE8–21 averages). It also shows the MW IESO added after the bid, the final total, trips in the 24 h before the bid, the tightest bid-time headroom, and the realised East DA−RT.
- **Tomorrow's row:** it is compared with the 30 days by mean, P75, max, rank and z-score. Cells above the P75 are red.
- **Priced in? Tested over 453 days on peak hours, East and Ottawa, with day-bootstrap 90% intervals:**
  - Outages known at the bid are priced. Their deviation from the 30-day mean does not predict DA−RT: East +1.42 $/MWh per GW (−1.20..+4.26), Ottawa +0.75 (−2.12..+3.81). If anything DA over-prices them: on days more than 1 GW above the 30-day mean, East DA−RT was +7.9.
  - MW added after the bid are not priced. RT beats DA by 10.7 $/MWh per GW at East (1.7..19.5) and 9.1 at Ottawa. On days with 500–1,000 MW added, East DA−RT was −6.9.
- **Watch-list tags:**
  - *In the model:* already in headroom, gas need or sizing.
  - *Later days:* the 35-day schedule and the Outlook. They reach the model when the day becomes tomorrow.
  - *Ignore:* intertie cuts under 100 MW that are not on the Quebec or New York interfaces.
  - *You:* news that arrives after IESO's last Adequacy file; use the what-if sliders for it.
