"""unit_trips.py -- Oct 8 2026: unit-level trips from IESO GenOutputCapability (archive, Jun -> Oct 2026, last version per day).
A 'trip' = a unit that was producing >= 30 MW in hour h-1 and whose capability drops by >= 50% (and >= 50 MW) in hour h
while its output collapses. Writes data/unit_trips.csv (one row per trip) and data/unit_hourly_gas.csv (gas units)."""
import sys, re, zipfile; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
A = C.ROOT / 'archive' / 'GenOutputCapability'
G = re.compile(r'<Generator>\s*<GeneratorName>([^<]+)</GeneratorName>\s*<FuelType>([^<]+)</FuelType>(.*?)</Generator>', re.S)
def sec(b, tag):
    m = re.search(rf'<{tag}>(.*?)</{tag}>', b, re.S)
    return {} if not m else {int(h): float(v) for h, v in re.findall(r'<Hour>(\d+)</Hour>\s*<EnergyMW>([-\d.]+)</EnergyMW>', m.group(1))}
rows = []
for zf in sorted(A.glob('*.zip')):
    z = zipfile.ZipFile(zf); names = z.namelist(); days = {}
    for n in names:
        m = re.search(r'_(\d{8})(?:_v(\d+))?\.xml$', n)
        if not m: continue
        d, v = m.group(1), int(m.group(2) or 10**6)          # unversioned = latest
        if d not in days or v > days[d][0]: days[d] = (v, n)
    for d, (v, n) in sorted(days.items()):
        s = z.read(n).decode('utf-8', 'ignore'); date = f'{d[:4]}-{d[4:6]}-{d[6:]}'
        for name, fuel, b in G.findall(s):
            if fuel.strip().upper() not in ('GAS', 'NUCLEAR', 'HYDRO'): continue
            o, c = sec(b, 'Outputs'), sec(b, 'Capabilities')
            for h in range(1, 25): rows.append((date, h, name.strip(), fuel.strip().upper(), o.get(h, np.nan), c.get(h, np.nan)))
u = pd.DataFrame(rows, columns=['date', 'he', 'unit', 'fuel', 'out', 'cap']).sort_values(['unit', 'date', 'he'])
u['po'] = u.groupby('unit').out.shift(); u['pc'] = u.groupby('unit').cap.shift()
trip = (u.po >= 30) & (u.cap <= 0.5 * u.pc) & ((u.pc - u.cap) >= 50) & (u.out <= 0.5 * u.po)
t = u[trip][['date', 'he', 'unit', 'fuel', 'po', 'pc', 'cap']].rename(columns={'po': 'mw_lost'})
t.to_csv(C.DATA / 'unit_trips.csv', index=False); u[u.fuel == 'GAS'].to_csv(C.DATA / 'unit_hourly_gas.csv', index=False)
print('days', u.date.nunique(), u.date.min(), u.date.max(), '| units', u.unit.nunique(), '| trips', len(t), 'MW', int(t.mw_lost.sum()))
print(t.groupby(['fuel']).size().to_dict()); print(t.groupby('unit').agg(n=('mw_lost', 'size'), mw=('mw_lost', 'sum')).sort_values('n', ascending=False).head(15).to_string())
print('by HE:', t.groupby('he').size().to_dict())
