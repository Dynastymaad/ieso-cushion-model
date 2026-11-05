"""levels_by_block.py -- Nov 5 2026, research only. RT - DA by bid-time gas need, wind forecast and NY - Ontario, per time block.
2026 is the read; Sep-Dec 2025 is the cross-check."""
import numpy as np, pandas as pd
pd.set_option('display.width', 250)
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False); h['rd'] = h.rt - h.da; h = h.dropna(subset=['rt', 'da'])
B = {'HE1-6 overnight': (1, 6), 'HE7-8 morning ramp': (7, 8), 'HE9-15 valley': (9, 15), 'HE16-21 evening': (16, 21), 'HE22-24 late': (22, 24)}
f = lambda s: pd.Series(dict(h=len(s), mean=s.mean(), med=s.median(), up=(s > 0).mean() * 100, spike=(s > 50).mean() * 100))
for yr, x0 in [('2026', h[h.date >= '2026-01-01']), ('Sep-Dec 2025', h[h.date < '2026-01-01'])]:
    print(f'\n################ {yr} (weekdays) ################')
    x0 = x0[x0.wkend == 0]
    for bn, (a, b) in B.items():
        x = x0[x0.he.between(a, b)]
        print(f'\n=== {bn} ===   (mean / median RT-DA, % RT>DA, % RT>DA+50)')
        for col, bins in [('gas_hat', [-9e9, 3000, 4000, 5000, 6000, 7500, 9e9]), ('wind_fc', [0, 1000, 2000, 3000, 9e9]), ('ny', [-999, -20, -10, 0, 10, 999])]:
            t = x.groupby(pd.cut(x[col], bins), observed=True).rd.apply(f).unstack().round(1)
            t.index = [f'{col} {i}' for i in t.index.astype(str)]
            print(t[t.h >= 25].to_string(header=(col == 'gas_hat')))
