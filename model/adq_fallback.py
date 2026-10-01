"""adq_fallback.py -- if the database does not have IESO's pre-DA Adequacy2 vintage for tomorrow yet, build it from
IESO's public Adequacy3 file (same fundamentals, archived by ieso_backfill.py): the latest version for delivery day D
issued on D-1 before 09:00 EST. Appends those rows to cache/ieso_adq2_preDA.csv in the database's format.
Does nothing when the database already has a D-1 vintage. The next pull_history run overwrites the cache anyway."""
import sys, zipfile, re; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from datetime import datetime, timedelta, timezone
import pandas as pd, common as C, parse_archive as P
MAP = {'dem_fc': ('Ontario Demand', 'Forecast'), 'nuclear_cap': ('Internal Resource', 'Nuclear Capacity'), 'nuclear_out': ('Internal Resource', 'Nuclear Outage'),
       'gas_cap': ('Internal Resource', 'Gas Capacity'), 'gas_out': ('Internal Resource', 'Gas Outage'), 'hydro_cap': ('Internal Resource', 'Hydro Capacity'),
       'hydro_out': ('Internal Resource', 'Hydro Outage'), 'wind_fc': ('Internal Resource', 'Wind Forecast'), 'solar_fc': ('Internal Resource', 'Solar Forecast'),
       'wind_cap': ('Internal Resource', 'Wind Capacity'), 'storage_cap': ('Internal Resource', 'Storage Capacity'), 'storage_out': ('Internal Resource', 'Storage Outage'),
       'biofuel_cap': ('Internal Resource', 'Biofuel Capacity'), 'biofuel_out': ('Internal Resource', 'Biofuel Outage'),
       'emb_wind': ('Embedded Generation', 'Wind'), 'emb_solar': ('Embedded Generation', 'Solar'), 'exc_cap': ('Excess', 'Capacity')}

def run(D=None):
    est = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)
    D = D or (est.date() + timedelta(days=1)).isoformat(); d1 = (pd.Timestamp(D) - pd.Timedelta(days=1))
    cut = d1 + pd.Timedelta(hours=9)
    f = C.CACHE / 'ieso_adq2_preDA.csv'; a = pd.read_csv(f)
    have = a[a.date == D].ieso_createtime.max() if (a.date == D).any() else None
    best = None
    for z in sorted((C.ARCH / 'Adequacy3').glob(f'Adequacy3_{D[:4]}{D[5:7]}.zip')):
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if D.replace('-', '') not in n or '_v' not in n: continue
                rows = P.adq_rows(zf.read(n)); t = pd.Timestamp(rows[0]['issued'])
                if d1 <= t < cut and (best is None or t > best[0]): best = (t, rows)
    if have is not None and pd.Timestamp(have).date() == d1.date() and (best is None or pd.Timestamp(have) >= best[0]):
        print(f'adq fallback: database already has the newest vintage for {D} ({have}); nothing to do'); return
    if best is None:
        print(f'adq fallback: no Adequacy3 version for {D} issued {d1.date()} before 09:00 EST in the archive -- run python ieso_backfill.py --quick first'); return
    t, rows = best; out = []
    for r in rows:
        for k, (rt, st) in MAP.items():
            if r.get(k) is not None: out.append(dict(date=D, hour=r['he'], resourcetype=rt, subtype=st, value=r[k], ieso_createtime=t.strftime('%Y-%m-%d %H:%M:%S')))
    a = a[a.date != D]; a = pd.concat([a, pd.DataFrame(out)], ignore_index=True); a.to_csv(f, index=False)
    print(f'adq fallback: database had {have or "nothing"} for {D}; used IESO Adequacy3 issued {t} ({len(out)} rows)')

if __name__ == '__main__': run(sys.argv[1] if len(sys.argv) > 1 else None)
