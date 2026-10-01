"""
ieso_fwd35.py -- IESO's 35-day outage / adequacy schedule, straight from the public site (no database, no login).

IESO publishes one Adequacy3 file per delivery day for the next ~34 days and re-issues it through the day.
This saves today's latest copy of every future day (a daily snapshot, so we can later measure how the
schedule drifts) and writes data/fwd35.csv for the Outages tab.

    python ieso_fwd35.py
"""
import re, sys, time, zipfile, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE / 'model'))
import pandas as pd
from parse_archive import adq_rows
BASE = 'https://reports-public.ieso.ca/public/Adequacy3/'
UA = {'User-Agent': 'Mozilla/5.0 (DynastyPower ontario-cushion-model fwd35)'}

def get(u, tries=5):
    # IESO's public site sometimes drops connections (WinError 10054 / timeouts): retry with back-off
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r: return r.read()
        except Exception as ex:
            if k == tries - 1: raise
            w = 3 * (k + 1); print(f'  retry {k+1}/{tries-1} in {w}s: {u.rsplit("/",1)[-1]} ({str(ex)[:50]})', flush=True); time.sleep(w)

def main():
    est = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5); today = est.date()
    html = get(BASE).decode('utf-8', 'replace')
    days = sorted({m for m in re.findall(r'PUB_Adequacy3_(\d{8})\.xml', html) if m > today.strftime('%Y%m%d')})
    snap = HERE / 'archive' / 'Adequacy3_fwd'; snap.mkdir(parents=True, exist_ok=True)
    rows = []
    with zipfile.ZipFile(snap / f'fwd35_{today:%Y%m%d}.zip', 'a', zipfile.ZIP_DEFLATED) as z:
        miss = []
        for d in days:
            time.sleep(0.5)                                          # be gentle: ~35 files in a row
            try: b = get(BASE + f'PUB_Adequacy3_{d}.xml')
            except Exception as ex: miss.append(d); print(f'  skipped {d}: {str(ex)[:60]}'); continue
            if f'PUB_Adequacy3_{d}.xml' not in z.namelist(): z.writestr(f'PUB_Adequacy3_{d}.xml', b)
            for r in adq_rows(b): r['snapshot'] = today.isoformat(); rows.append(r)
    if miss: print(f'  {len(miss)} day(s) could not be fetched: {", ".join(miss)}')
    if not rows: sys.exit('fwd35: nothing fetched -- keeping the previous data/fwd35.csv')
    df = pd.DataFrame(rows); df.to_csv(HERE / 'data' / 'fwd35.csv', index=False)
    print(f'fwd35: {len(days)} days {days[0]}..{days[-1]} -> data/fwd35.csv ({len(df)} rows); snapshot archive/Adequacy3_fwd/fwd35_{today:%Y%m%d}.zip')

if __name__ == '__main__':
    main()
