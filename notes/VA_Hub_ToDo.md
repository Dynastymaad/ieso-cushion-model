# VA Hub tools — to-do list (after the DA Virtual tab)

Each entry says what the tool is for, and the plan: build it, improve it, fold it into another page, or leave it out. Items marked **re-tested** were covered in `Ontario_Tool_Review_and_Supply_Curve.md` or `VA_Hub_DA_Virtual_Retest.md`.

## Next up (they feed the DA Virtual tab)
1. **Load Consensus / Load Match / Load Analysis** — a live table of every load vendor against IESO for tomorrow, plus each vendor's trailing error by HE.
   - We already hold Tesla, Dynasty, Meteologica and IESO at bid time. The "load vs IESO" signal passed the re-test.
   - *Build* as a panel under the matrix, with each vendor's 30-day MAE.
2. **VG Forecast** — wind and solar by vendor for tomorrow, with each vendor's error.
   - Meteologica is the best (MAE 244 vs IESO 264). The wind 3h ramp signal passed.
   - *Build*, using the Warehouse vendors plus the StormVista API when we move to GitHub.
3. **Sensitivity / RT skew** — how much DA moves for ±500 MW of gas need.
   - The VA Hub derives it from the heat-rate table. *Rebuild* from our DA model's headroom coefficient instead, and test whether it predicts |RT − DA|.
4. **Weather risk (rain, temperature)** — VA Hub's rain signal.
   - *Needs* Toronto hourly weather history matched to prices before it can be tested. Pull from the Warehouse WeatherHourly table.
5. **Spike / collapse boost (1.5× MW)** — turned off on our tab.
   - *Test* whether the boost on SPIKE-zone offers pays. SPIKE zones made +$12 to +$23 per MWh on offers at 1.1× RT, but carry the worst days.

## Later
6. **Cross Market NX (next-day net exports)** — our exports model covers the same ground: NYISO schedule + curve + carry, capped by the limits.
   - *Fold in*: show the export forecast, the limits and NY Zone A on one panel.
7. **NYISO / PJM pages** — NY Zone A DAM is already an input (DA error −13%). PJM West D-2 is a small daily nudge.
   - *Build* a small reference panel; no new model.
8. **Congestion** — Toronto/SW basis to OZP is about $1.
   - *Low priority* for our hubs.
9. **Adq3 / Fundamentals / Inputs / Prices** — raw data views.
   - *Build* as one "Data" tab, showing freshness per feed, so it is clear what arrived before 08:00 MT.
10. **Outlook, 14 Days, 35 Days** — parked by your call (next day only). Our block forecast exists if needed.
11. **Like Days** — nearest past days by headroom, load and wind, with what DA and RT did.
    - *Build* after the tab settles. It is a good review tool, but not a signal until tested.
12. **$100+ Spikes / −$50 Collapse / Forecast Errors / Diagnostics** — hindsight pages (**re-tested**: useful for review, not signals).
    - *Build* one "Review" tab covering yesterday's misses and spikes.
13. **Heat-rate lookup audit** — *drop* (**re-tested**: $8.99 vs our $5.10).
14. **Hourly bias badges** — kept as information columns (7d / 14d). 14d is marginal (+$1.51); 7d has no edge.

## Also on the list
- Daily data pull for GitHub Pages: NRGStream API for limits and history, IESO public files, NYISO, Warehouse. This replaces the browser pulls.
- Uplift: deduct the virtual uplift from every P&L once we have the rate.

## Watch list from the losing-sell-days study (notes/Losing_Sell_Days.md)
- Re-test "skip surplus SELL when Tesla ≥ IESO + 300" once Meteologica load history and bid-time temperature forecasts are pulled (near miss today).
- Scarcity (bid headroom < 2,000 MW): turn the flag into a rule if next summer confirms RT > DA there.
- Pull IESO forced-outage notices with timestamps. Outages added after the bid are the largest loss bucket.

## Added Sep 28 2026 (East/Ottawa switch)
- Ottawa-area transmission outage flag at the bid (for the E–O pair spike days) once TxOutages history is long enough.
- Surplus-branch sells: re-check at East/Ottawa after 3 more months (mixed result, unchanged).
- Daily pull of NRG streams 421358/416908/417068/421360/416910/417073/415916/413124 through the API for GitHub.
- `pull_history.py --only quebec` (HQ demand, PQ intertie LMPs) still to run and test.
