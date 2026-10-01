# Ontario Cushion Model

Working folder for the Ontario (IESO) next-day DA / RT model — Toronto and Southwest hubs.
Separate from the Alberta `aeso-cushion model`; nothing here writes to that folder.

## Step 1 — database probe (done 2026-09-26)

In PowerShell:

```
cd "$HOME\OneDrive - Dynasty Power\Desktop\Ontario-Cushion Model"
python ont_probe.py
```

- Light queries only: table lists, column lists, indexes, 5-row samples, small page samples.
  Every query stops after 25 seconds and is skipped if slow.
- Credentials: a `db.json` in this folder if present, otherwise it reads
  `Documents\aeso-cushion model\db.json` (read only). Nothing is written to either database.
- Results: `out\*.csv` and `out\_summary.txt`. Tell Claude when it is done.
- Should take 2–5 minutes.

## Step 2 — second probe (done 2026-09-26)

```
python ont_probe2.py
```

Results in `out2\`. It checks: which vendors forecast Ontario load/wind/solar and how far
back, the issue cadence of those vintages, Toronto (CYYZ) weather, the Adequacy2 vintage
archive in canpower, and dumps the small virtual-transaction tables.

## Step 3 — save IESO's 90-day window NOW (it rolls off daily)

```
python ieso_backfill.py
```

IESO keeps only ~90 days of prices online and neither database has hourly DA/RT prices
before that, so this copies the window into `archive\` (raw files, one zip per report per
month). Re-run daily; it only downloads what is new. ~250 MB and 10–20 minutes the first time.

## Step 4 — pull the modelling history from the databases

```
python pull_history.py
```

Writes `cache\*.csv`: IESO / Tesla / Meteologica / Dynasty load-forecast vintages, wind and
solar vintages, actual Ontario load, Toronto weather, daily forwards (Ontario Hub on/off-peak
settles = daily DA history since May 2025, Dawn, PJM West, NYISO West), USD/CAD, the
Adequacy2 pre-deadline and final vintages since May 2025, and your virtual trades.
5–20 minutes; the Adequacy2 archive is the slow part.

## notes\

- `Ontario_Data_Brief.md` — every data feed, when it is published, how long it is kept.
- `Ontario_Tool_Review_and_Supply_Curve.md` — re-test of the VA Hub tools and the hourly supply curve.
