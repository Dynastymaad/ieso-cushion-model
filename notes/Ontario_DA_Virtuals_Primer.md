# Ontario day-ahead virtuals — market mechanics and what to think about before reading the model

Written for the East / Ottawa virtual book (Dynasty Power), Sep 2026. Numbers quoted from our own data are from
Jul 2025 – Sep 2026 unless stated. Items marked **(check)** are rules I am not 100% sure of — confirm them in the
IESO Market Rules / Market Manuals or with IESO before relying on them.

---------------------------------------------------------------------------------------------------------------

## 1. The market in one page

- **Operator:** the IESO (Independent Electricity System Operator) runs Ontario's wholesale market.
- **Market Renewal:** on **May 1, 2025** the "renewed market" went live. It added a financially binding **Day-Ahead Market (DAM)**, locational marginal prices (LMPs) at every node, and **virtual trading**. There is no DAM history before that date, which is why our data starts in May 2025.
- **Two settlements:**
  - **DAM:** runs on D-1. Bids and offers close at **10:00 EPT on D-1** (08:00 MT). It clears every hour of D and publishes DA prices early in the afternoon of D-1.
  - **Real-time market (RTM):** dispatches every 5 minutes on the day. Virtuals settle against the **hourly average of the 5-minute real-time prices** in their zone.
- **Prices are LMPs:**
  - Each node's price = the system energy price + a **loss** component + a **congestion** component. NRGStream's DA zone file carries all three.
  - A **virtual zonal price** is the load-weighted average of the nodal prices in that zone.
  - The **Ontario Zonal Price (OZP)** is the province-wide average used for non-dispatchable load.
- **Price limits:** the maximum market clearing price is **$2,000/MWh** and the floor is **−$100/MWh** (check the current values). Our pair legs use those as "always clears" prices.
- **Clock:**
  - IESO files are stamped in **EST all year**, with hours labelled **hour-ending** (HE1 = 00:00–01:00 EST).
  - In summer that is one hour behind Eastern daylight time, and it trips people up.
  - The model keys everything in IESO HE (EST).

## 2. What a virtual actually is

| You submit in the DAM | If it clears, you are | Settlement per MW per hour |
|---|---|---|
| **Virtual bid** (a buy) at price P | long in DA, automatically sold back in RT | **RT − DA** |
| **Virtual offer** (a sell) at price P | short in DA, automatically bought back in RT | **DA − RT** |

- **No physical delivery.** A virtual is a pure bet on the gap between the DA and RT prices in one zone and hour.
- **Clearing:**
  - A bid clears if DA settles **at or below** its price.
  - An offer clears if DA settles **at or above** its price.
  - Every cleared MW gets the **same DA price**, whatever price you bid.
- **You bet on the gap, not the level.** A high DA price is not bullish for a buy: the buy only wins if RT comes in **even higher** than that DA. This is the single most important idea in the whole book.
- **Your virtuals are in the DA clearing.** A large virtual offer lowers DA a little and a large bid raises it. At 85–100 MW in a zone with thousands of MW of load the effect is small, but not zero.
- **Convergence:** virtual traders collectively push DA toward the expected RT. What is left over are systematic premiums (DA over-pricing scarcity) and genuine surprises (trips, load misses).

## 3. Rules that bind our book

- **Zones:** nine virtual trading zones — East, Essa, Niagara, Northeast, Northwest, Ottawa, Southwest, Toronto, West. We trade **East** and **Ottawa**.
- **MW limits per side per hour** (IESO *Introduction to Virtual Trading*, Table 2):
  - East 85, Ottawa 100, Toronto 580, Southwest 315, West 190, Essa 100, Niagara 55, Northeast 50, Northwest 0.
  - A bid ladder and an offer ladder each count separately against the limit.
- **Submissions:**
  - **One bid and one offer per zone per hour.** Each is a price/quantity curve with several laminations (steps).
  - There is a daily cap on price/quantity pairs, about 2,160 in total (check your participant limit).
  - Bid prices must fall as quantity grows, and offer prices must rise.
  - Whether your submission tool wants **incremental or cumulative MW** per point depends on the tool. The desk has a "MW as running total" switch for that.
- **Holding both sides:** you *can* hold a bid and an offer in the same zone and hour, and our straddles do. For a score-5 sell, the ladder deliberately places **no bids**, so we never buy and sell against ourselves.
- **Credit and prudentials:** the IESO requires collateral against your potential virtual exposure (check the current prudential rules and your available credit before sizing up). An 85 MW position at a $1,000 RT spike is an $85k hour.
- **Charges and uplift:** virtuals are allocated some IESO charges and uplift through settlement (check the charge types that apply to virtual transactions). **None of our backtests include them.** Treat every $/MWh edge as *before* those costs.

## 4. How the Ontario system works (what drives prices)

- **Supply stack, bottom to top:**
  1. **Nuclear**, about 12 GW of capacity (Bruce, Darlington, Pickering). Must-run and slow to move. Refurbishment and outage programs remove thousands of MW for months. Today 4,670 MW (39%) is out.
  2. **Hydro**, about 7.9 GW. Partly run-of-river (must-run) and partly storage that can be shifted into peak hours.
  3. **Wind**, about 5 GW, and **grid solar**, about 0.5 GW. Price-takers, and their output is uncertain.
  4. **Embedded (behind-the-meter) solar** does not show up as supply: it *reduces* measured Ontario demand at midday.
  5. **Storage**, about 1.2 GW and new. It charges in cheap hours and discharges into the peak.
  6. **Gas**, about 11.3 GW. **Gas is almost always the marginal unit in the peak**, so Dawn gas prices and gas availability set the peak price.
- **Demand:** about 13–15 GW overnight and 17–24 GW at peak. Summer peaks are the highest; winter has a morning and an evening peak. Weekends and holidays run 1–2 GW lower.
- **Why prices fall to zero or go negative:** at night, in shoulder seasons and on windy weekends, nuclear + hydro + wind exceed demand plus exports ("surplus baseload"). Prices collapse, sometimes to the floor.
- **Why prices spike:** when gas is the last few units and something goes wrong (a trip, load above forecast, wind below forecast, an intertie cut), RT climbs the steep top of the gas and import stack. Rarely, operating-reserve shortfalls add **scarcity pricing**.
- **Headroom (cushion)** is the model's single most important number:
  - headroom = (gas available + hydro available) − (demand − nuclear available − wind − solar)
  - It is the MW of flexible supply left after serving load.
  - Under ~7,000 MW, prices are high and volatile. Over ~10,000 MW, prices are low and flat.

## 5. Interties (why neighbours matter)

- **Ontario connects to** Quebec, New York, Michigan, Minnesota and Manitoba. Ontario is usually a **net exporter**: Quebec about 1,000 MW, plus New York and Michigan depending on relative prices.
- **Exports are demand.** A higher export schedule means less headroom. Scheduled exports are in IESO's Adequacy data at the bid.
- **Intertie limits:**
  - They change with transmission outages.
  - A **cut after the bid** frees supply and pushes RT down, which is good for sells.
  - A limit **raised** after the bid pulls exports up and pushes RT up. This is the post-bid limit finding.
- **NISL (net interchange scheduling limit):** limits how fast total intertie schedules can change from hour to hour. When it binds, a NISL price shows up in the intertie LMPs.
- **Quebec and East/Ottawa:**
  - Most Quebec exports leave on **PQ.AT (Outaouais)**, which connects on the Ottawa side and runs at its limit about 65% of the time.
  - More export to Quebec raises the zone's DA premium over OZP: about **+$2.40/MWh per GW at East** and **+$6.30 at Ottawa**.
  - A low PQ.AT DA limit tomorrow means a smaller premium.
- **New York:** NYISO's DAM results (published about 07:35 MT) show what NY expects to import from Ontario. They feed the DA model and help explain the Ontario DA price level.

## 6. The information you have at the bid (and what you don't)

| Known before 08:00 MT on D-1 | Not known (the source of losses) |
|---|---|
| IESO Adequacy (about 07:50 EST): demand forecast; outages by fuel; wind and solar forecast; capacity; scheduled imports/exports | Units that trip after the file |
| Vendor load forecasts (Tesla, Dynasty, Meteologica) | How far load misses the forecast (heat, cold, cloud) |
| Trips in the last 24 h (from Adequacy versions) | Wind forecast error |
| DA intertie limits (IESO pre-DA file) | Intertie limit changes and curtailments |
| Yesterday's DA and most of RT; today's DA isn't out yet | Units IESO assumed back that don't return |
| NYISO DAM (07:35 MT) | RT dispatch quirks, ramping, NISL |
| 35-day outage schedule; 18-month Outlook | |

- **Anything in the left column is already in DA** — every other participant sees it too.
- **The right column is where money is made and lost.** Our tests:
  - Outages known at the bid are priced into DA, if anything over-priced.
  - MW added **after** the bid cost about $10/MWh per GW (RT beats DA).
  - The worst days were mostly post-bid trips plus load coming in above forecast.
  - None of it was predictable from bid-time data.

## 7. Where the edge comes from (what the model exploits)

1. **Scarcity premium in tight hours (the sells):**
   - When headroom is under 7,000 MW, DA tends to settle above RT. Buyers pay for protection against spikes. East: DA averaged $128 vs RT $116, and RT beat DA only ~31% of the time.
   - Selling collects that premium: many $15–30 wins, and a few $300–1,000 losses.
   - Net about +$11/MWh on the tight sells.
2. **Under-priced middle band (the buys):**
   - At moderate headroom (East 7,500–9,500 MW, Ottawa 9,500–11,500, re-learned daily), RT has tended to beat DA.
   - Buy-band hours made about +$10/MWh.
3. **Post-trip sizing:** after 500+ MW of trips in the last 24 h, tight sells did much better (+$25/MWh). The ladder sizes them ×1.5.
4. **Things that did *not* work and were left out:**
   - the VA Hub gas-ledge signal;
   - intertie limits on their own;
   - Quebec demand or bids;
   - skipping or halving risky hours;
   - vetoes on losing days;
   - predicting post-bid outages;
   - carrying yesterday's morning spike into today.

## 8. How to think about risk

- **The distribution is skewed.**
  - Sells: 70% small wins and a fat left tail. The worst single hour lost $1,067/MWh.
  - Buys and the East–Ottawa pair: the opposite, with many small losses and a few big wins.
- **Size is the only reliable risk lever.**
  - Cutting the tight hours removed more profit than risk: half size under 5,500 MW headroom cost $0.57M of net at East for a $100k smaller drawdown.
  - Scaling the whole book with **Size ×** changes profit and drawdown together.
- **Worst-case frame at full size (per zone):**
  - about −$150–200k on a bad day;
  - about −$400–500k worst drawdown over 17 months;
  - about +$3.3–3.5M net over the same period (backtest, before charges).
- **Concentration:** East and Ottawa move together (DA–RT correlation is high). Holding both is **not** diversification — it is roughly one bet at 185 MW.
- **Model risk:**
  - Thresholds are learned on trailing data, and regimes change (nuclear refurbishments, new storage, new rules).
  - Re-check performance monthly, and after any IESO rule change.
- **Operational risk:**
  - Wrong day, stale data (the header must say tomorrow's date and today's IESO file).
  - Entry format (incremental vs cumulative).
  - Missing one zone of a pair.
  - Late submission.

## 9. Before you even open the model (context checklist)

1. **Calendar:** weekday or weekend? Holiday (Ontario and US)? Weekend and holiday load is lower; the model knows the weekend, not every holiday.
2. **Weather:**
   - Heat or cold versus normal. Big temperature misses drive load misses.
   - Wind regime: calm high-pressure days mean low wind and a tighter peak.
   - Cloud cover: embedded solar can swing midday load by about a GW.
3. **Season and outage season:**
   - Spring (Mar–May) and fall (Sep–Nov) are maintenance seasons: many units out, and returns that slip.
   - Check the Outages tab's 35-day view and the 18-month Outlook for step changes.
4. **Nuclear status:** refurbishment (MCR) units and forced outages. One unit is 800–900 MW.
5. **Gas:** Dawn price and pipeline issues. They raise the level of both DA and RT; they do not move DA versus RT on their own.
6. **Neighbours:**
   - NY and MISO conditions (heat waves pull exports).
   - Quebec winter peaks (exports sit at the PQ.AT limit).
   - Intertie outages.
7. **IESO notices:** Advisory / Emergency Energy Alerts, conservation appeals, reliability notices. Read these before bidding — they are information DA may not fully price.
8. **Yesterday:** what did DA vs RT do? This is useful for understanding, not for trading — a big RT morning did **not** predict a big morning the next day.
9. **Your book:** credit available, open positions, and how much drawdown you can take this week. That decides **Size ×**.

## 10. Reading the model (in this order)

1. **Header:** "DA for <tomorrow>", built on today's ~07:50 EST IESO file.
2. **Outages tab:**
   - Tomorrow versus the last 30 days.
   - Trips in 24 h (≥ 500 MW means ×1.5 on tight sells).
   - Watch items tagged **You** — enter those with the sliders.
3. **Next day tab:**
   - Headroom by hour against 7,000 (sell line) and the zone buy bands.
   - DA forecast and its P10–P90 range.
4. **DA Virtual tab:**
   - Each hour's score and reason.
   - **Tesla Δ:** negative = softer RT, which helps sells.
   - **DA−RT 7d/14d badges:** big negatives mark risky sell hours; information only.
   - Chips: SCARCITY (headroom under 2,000 MW) and ×1.5.
5. **East–Ottawa & Quebec tab:** PQ.AT export limit tomorrow versus the last 7 days; the pair (off unless you turn it on).
6. **Size ×**, then the **MW format** switch, then copy **both zones'** buy and sell rows. Submit before 08:00 MT.

## 11. Glossary

- **DA / DAM:** day-ahead price / market.
- **RT / RTM:** real-time (5-minute, averaged hourly for virtual settlement).
- **PD:** pre-dispatch, IESO's hour-ahead indicative prices.
- **LMP:** locational marginal price (energy + loss + congestion).
- **OZP:** Ontario Zonal Price.
- **Virtual zonal price:** a zone's trading-hub price.
- **Headroom / cushion:** flexible supply left after load (section 4).
- **Adequacy report:** IESO's supply/demand outlook for the next days, issued several times a day. The pre-DA version is our main input.
- **Buy band:** the headroom range where RT has recently beaten DA; re-learned daily.
- **v2 SELL:** the tested sell signal. Headroom below the learned tight threshold, or gas need below the surplus threshold.
- **Ladder / lamination:** the steps of a bid or offer curve.
- **Straddle (score 3):** small bid far below and small offer far above the forecast. It only trades on extreme DA prints.
- **NISL:** net interchange scheduling limit.
- **MCR:** nuclear major component refurbishment.
- **SBG:** surplus baseload generation.
