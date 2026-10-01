# Ontario data — where every input lives, when it arrives, how long it survives

Dynasty Power / Ontario (IESO) desk, **Toronto and Southwest hubs**. Verified 2026-09-26.
Companion to the Alberta `Data_Access_Brief.md`; same access rules apply (section 0 there).

**Tags:** **[M]** measured on real files this session · **[S]** structural (rules / file
format) · **[?]** not yet confirmed — `ont_probe.py` (folder root) answers it.

---

## 0. The three things that decide the design

1. **The bid deadline is 10:00 Eastern prevailing (08:00 MT) on D-1.** Anything that is
   not published before then cannot be a DA input, and must not be in a DA backtest. [S]
2. **IESO report timestamps are EST all year** (no daylight saving), hours are **HE1–24
   ending**. In summer 10:00 EDT = **09:00 in IESO file time**. NYISO/PJM use Eastern
   *prevailing*, **hour-beginning**. So IESO HE *h* = NYISO hour-beginning *h* in summer,
   and HE24 = NYISO 00:00 of the next day. [S/M]
3. **IESO's public site is a rolling window, not an archive.** Daily price files ~90 days,
   forecast *vintages* ~30–46 days. Whatever the pipeline does not save each morning is
   gone. Build the archive first. [M]

---

## 1. IESO public reports — `https://reports-public.ieso.ca/public/<Report>/`

No key. XML (some CSV). The unversioned file (`PUB_X_YYYYMMDD.xml`) is the latest
version; `_vN` files are earlier vintages. Directory listings show a timestamp per file —
that timestamp (and `<CreatedAt>` inside the file) is what you filter on to rebuild
"what was known at 09:00 EST".

### 1a. Prices (targets)

| report | what | published | kept | notes |
|---|---|---|---|---|
| `DAHourlyZonal` | **DA price per virtual hub** (TORONTO:HUB, SOUTHWEST:HUB, …), hourly | D-1 ~12:33 EST | ~90 d | **this is what your virtuals clear at** |
| `RealtimeZonalEnergyPrices` | **RT 5-min price per virtual hub**, one file per hour | each hour | ~90 d | your RT settlement = 5-min prices; hourly mean for flat MW |
| `DAHourlyOntarioZonalPrice` | DA OZP (load-weighted Ontario price) + loss + congestion | D-1 ~12:31 EST | ~90 d | Toronto ≈ OZP +$0.43 DA, SW ≈ OZP −$0.17 [M] |
| `RealtimeOntarioZonalPrice` | RT OZP 5-min, hourly file | each hour | ~90 d | |
| `PredispHourlyZonal` / `PredispHourlyOntarioZonalPrice` | pre-dispatch price vintages | from ~20:14 EST D-1, hourly | ~30 d | **after** the DA deadline; see review doc |
| `DAVirtualTransactions` | total virtual bids/offers offered & cleared per hub | D-1 ~12:31 | ~30 d | competition read: Toronto net ~117 MW virtual supply cleared/h [M] |
| `DAConstrShadowPrices`, `RealtimeConstrShadowPrices` | binding constraints | daily / hourly | ~30 d | only matters for hubs with basis; Toronto/SW rarely |
| `RealtimeMktPriceYear` | **HOEP era**, yearly CSV to Apr-2025 | — | 2010+ | pre-MRP market — **do not mix price levels with post-May-2025** |

### 1b. Fundamentals *forecasts* (the DA inputs)

| report | what | vintages | kept | notes |
|---|---|---|---|---|
| **`Adequacy3`** | per delivery date: Ontario demand forecast, embedded wind/solar, capacity & outages **by fuel** (nuclear, gas, hydro, wind, solar, biofuel, storage), wind/solar forecast, import/export capability, OR requirement, **excess capacity** | ~2/day out to 34 days; hourly-ish on D-1 and D | versions only ~46 d back; older dates keep final only | **the core DA input.** Pre-deadline vintage for D is the one issued **D-1 ~07:50 EST** (~04:20 also). After DA it also fills DA schedules/offers by fuel [M] |
| `VGForecastSummary` | IESO wind & solar forecast, grid + embedded, vintages | ~every 20–60 min | ~30 d | wind forecast updates after DA → RT signal |
| `TxLimitsOutage0to2Days`, `…3to34Days`, `TxOutages*` | transmission limits / planned outages | daily | rolling | congestion hubs only |
| `PreDAIntertieSchedLimits`, `DAIntertieSchedLimits` | intertie limits | daily | ~90 d | |

### 1c. Fundamentals *actuals* (training labels, RT diagnosis)

| report | what | kept | notes |
|---|---|---|---|
| `Demand` → `PUB_Demand_YYYY.csv` | hourly **Ontario Demand** and **Market Demand** | **yearly files since 2002** | Market Demand = Ontario Demand + exports |
| `GenOutputbyFuelHourly` → `_YYYY.xml` | hourly output by fuel | **yearly since 2015** | nuclear, gas, hydro, wind, solar, biofuel, other |
| **`GenOutputCapability`** | **per-unit hourly output + capability** (every gas, nuclear, hydro unit) | ~90 d | builds the physical gas ladder (CC → peakers → Lennox) — see review doc |
| `IntertieScheduleFlowYear` → `_YYYY.csv` | hourly imports, exports, **actual flow** per interface (MI, NY, PQ×9, MB, MN) | **yearly since 2018** | flow **+ = export** [M] |
| `IntertieScheduleFlow` | same, daily files | ~90 d | |
| `RealtimeTotals`, `DATotals` | market totals (energy, loss, dispatchable load, reserves) | ~90 d | |

**Only ~90 days of post-MRP prices are public.** The pipeline must save every day's
price, Adequacy3 and VG files from its first run. [M]

---

## 2. Neighbouring markets (free, no key)

| source | what | available | status |
|---|---|---|---|
| **NYISO DAM zonal LBMP** `http://mis.nyiso.com/public/csv/damlbmp/YYYYMMDDdamlbmp_zone.csv` (monthly zips for history) | Zone A "WEST" DA price, hour-beginning EPT, USD | **posted ~09:33 EDT on D-1** (Last-Modified 13:32–13:33 GMT on 4 days checked) [M] | **usable — 27 min before IESO closes.** Tight; the job must fetch it at 09:35–09:45 ET |
| NYISO RT, loads, flows | `mis.nyiso.com/public/` P-24A, P-58 etc. | ongoing | not tested yet |
| PJM DA LMP | PJM Data Miner (needs free API key) | results ~13:30 ET D-1 | **too late** for the DA bid |

Correction to the first review: I said NYISO DAM was not available before the IESO
deadline. The file headers show it is (≈09:33 ET). It does add to the DA forecast — see
the review doc.

---

## 3. Your two databases — what is already confirmed for Ontario

From `aeso-cushion model/cache/fwd_inventory.csv` (pulled from `Warehouse.dbo.ForwardPrices`):

| ExchangeCode | node | daily/monthly | history | use |
|---|---|---|---|---|
| **CVX**, XCL | Dawn Ontario / Union-Dawn gas | D | 2024-07 → | **Dawn gas price** (USD/MMBtu). Range this summer only $2.44–2.85 |
| XCN, DWN | Dawn gas | M | long curve | seasonal level |
| **XDE / XEA** | Ontario Hub power (on-peak) | D | 2025-05 → | market's own day-ahead price view; ONZN before 2025-05 |
| **XDG / XDZ** | Ontario Hub power (off-peak) | D | 2025-05 → | |
| XDY | Ontario Hub power (7×24 / flat) | D | 2025-05 → | |
| XDB/XDC/XDD/XDF/XDH | Ontario Hub power | M | → 2032 | term curve |
| **PDA** | PJM Western Hub | D | 2024-07 → | neighbour price level |
| ADP | NYISO "WEST" (Zone A) | D | 2024-07 → | neighbour price level |
| HHD | Henry Hub | D | | |

**Timing trap in the forwards [M]:** the row with `EffectiveDate = D-1` for strip D is the
end-of-day settle on D-1, i.e. **after** the DA results. Only `EffectiveDate ≤ D-2` (last
business day before D-1) is legal at bid time. Use that.

**Not yet known [?]** — run `python ont_probe.py` from the folder root (light queries,
25-second cap each); it answers:

- whether `LoadForecast` / `WindForecast` / `SolarForecast` carry an IESO / Ontario market,
  and from which vendors. **This is the single most valuable unknown.** The spread edge
  comes from having a better load forecast than IESO. If vendors like those in the AESO
  tables exist for Ontario, with vintages, we can finally test that edge properly.
- whether canpower holds any Ontario snapshot table (equivalent of
  `aeso_fundamentals_snapshots`) or Toronto weather.
- the product definitions behind XDE/XDG/XDY (on-peak hours, weekend treatment).

---

## 4. Other inputs

| input | where | status |
|---|---|---|
| Weather, Toronto / Ottawa / London | Open-Meteo (same pattern as `wx.py`) | not pulled yet; needed for like-day load checks and an own load forecast |
| Tesla / Dynasty load forecasts | pasted today (VA Hub `inputs` page) | **no history available to me** — they have to be archived with their issue time from now on |
| Virtual uplift (CT 1852 DRSU on virtual *offers*) | your settlement statements | size unknown to me; it comes off every DA-sell P&L |
| Virtual hub MW limits | IESO training deck | **Toronto 580 MW, Southwest 315 MW**; one bid + one offer per hub per hour; ≥1 MW; 2,160 price/quantity pairs a day |

---

## 5. The morning timeline (MT, summer)

| MT | event |
|---|---|
| 03:20 | Adequacy3 early vintage for D (04:20 EST) |
| 04:00–08:00 | IESO DAM bid window (06:00–10:00 EPT) |
| **06:50** | **Adequacy3 main pre-DA vintage for D** (07:50 EST) |
| **07:33** | **NYISO DAM results posted** |
| **07:45** | last sensible moment to run the model and paste the ladder |
| 08:00 | **IESO DAM closes** |
| 11:30 | IESO DA results (hubs, OZP, totals, virtuals) |
| 19:15 | first pre-dispatch for D (RT monitoring only) |

Winter (EST): Eastern times stay the same in IESO file time; MT shifts. Recompute from
UTC in code, never hard-code MT.

---

## 6. Gotchas found so far

1. **Adequacy3 counts unforecast wind/solar as "outage".** Wind `out` = capacity − forecast. Use the forecast field, not cap − out, for renewables. [M]
2. **Storage (1,200 MW) appears as its own fuel in Adequacy3** but as OTHER in the fuel-hourly actuals. [M]
3. **Intertie flow sign: + = export** in `IntertieScheduleFlow*`. The VA Hub mixes both conventions on some tabs. [M]
4. **Gas outages grow after the bid deadline:** final − pre-DA gas outage averages **+125 MW** (median +70, 90th pct +458). Nuclear adds +27, hydro +67. That is real, but it is a *spread / RT* effect, not a DA input (DA is fitted on the pre-DA vintage). [M, 46 days]
5. **HOEP (pre-May-2025) is a different market.** Summer-2024 HOEP averaged ~$35 against ~$60 DA now. Use it for shapes only. [M]
6. **Only summer is in the sample.** No shoulder-season or low-price (surplus baseload) regime has been observed post-MRP in the public window. [M]
7. **Directory listings silently drop old versions.** For dates older than ~46 days, only the final Adequacy3 survives. A "backtest" on those dates would be using *after-the-fact* inputs. [M]
