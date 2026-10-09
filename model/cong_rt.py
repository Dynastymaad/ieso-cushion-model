"""cong_rt.py -- Oct 8 2026: RT zonal price split into energy / congestion / loss for EAST and OTTAWA (IESO RealtimeZonalEnergyPrices,
archive Jun -> Oct 2026, 5-min). Hourly averages -> data/rt_components.csv. Then: in RT spike hours, how much was congestion?"""
import sys, re, zipfile; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
A = C.ROOT / 'archive' / 'RealtimeZonalEnergyPrices'; rows = []
Z = re.compile(r'<ZoneName>([^<]+)</ZoneName>(.*?)</TransactionZone>', re.S)
I = re.compile(r'<Interval>(\d+)</Interval>\s*<ZonalPrice>([-\d.]+)</ZonalPrice>\s*<EnergyLossPrice>([-\d.]+)</EnergyLossPrice>\s*<EnergyCongPrice>([-\d.]+)</EnergyCongPrice>')
for zf in sorted(A.glob('*.zip')):
    z = zipfile.ZipFile(zf); best = {}
    for n in z.namelist():
        m = re.search(r'_(\d{10})(?:_v(\d+))?\.xml$', n)
        if m and (m.group(1) not in best or int(m.group(2) or 1e6) > best[m.group(1)][0]): best[m.group(1)] = (int(m.group(2) or 1e6), n)
    for k, (_, n) in best.items():
        s = z.read(n).decode('utf-8', 'ignore'); d = f'{k[:4]}-{k[4:6]}-{k[6:8]}'; he = int(k[8:])
        for name, body in Z.findall(s):
            v = np.array([[float(a), float(b), float(c)] for _, a, b, c in I.findall(body)])
            if len(v): rows.append((d, he, name.split(':')[0], v[:, 0].mean(), v[:, 2].mean(), v[:, 1].mean(), v[:, 0].max()))
r = pd.DataFrame(rows, columns=['date', 'he', 'zone', 'rt', 'cong', 'loss', 'rt_max5']); r['energy'] = r.rt - r.cong - r.loss
r.to_csv(C.DATA / 'rt_components.csv', index=False)
print('zones', r.zone.unique(), r.date.min(), r.date.max(), len(r))
p = r.pivot_table(index=['date', 'he'], columns='zone', values=['rt', 'cong', 'energy'])
for z in ('EAST', 'OTTAWA'):
    if z not in r.zone.unique(): continue
    x = p.xs(z, axis=1, level=1); x = x[x.rt >= 150]
    print(f'\n{z}: hours with RT >= $150: {len(x)} | median congestion ${x.cong.median():.1f}, energy ${x.energy.median():.1f} | hours where congestion > $30: {(x.cong > 30).sum()}')
sel = p.loc[[i for i in p.index if i[0] in ('2026-09-27', '2026-09-30', '2026-10-01', '2026-10-04', '2026-10-07') and 16 <= i[1] <= 20 or (i[0] == '2026-09-30' and i[1] == 8)]]
print(sel.round(0).to_string())
