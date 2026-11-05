# Nov 5 2026: thin spare (<2500) doubles load AND wind points today. Wind points lose money in thin hours. Test: double load only. Tier proxy P&L = sign(read) x (RT-DA), spike-clipped and raw.
import pandas as pd, numpy as np
P = ['c_Load gap', 'c_Wind gap', 'c_Wind ramp', 'c_Wind upside', 'c_DA priced', 'c_NY pull', 'c_Exports']
for z in ['EAST', 'OTTAWA']:
    e = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False); e = e[e.rt.notna() & e.da.notna() & e.read.notna()].copy()
    m = np.where(e.pub_sp < 2500, 2, 1)
    def tiers(card):
        s = np.sign(card) == np.sign(e.read)
        return np.where((card.abs() >= 3) & s, 'A', np.where(card.abs() >= 3, 'C', np.where(e.read.abs() >= 5, 'B', 'N')))
    now = e[P].sum(axis=1)
    alt = now - e['c_Wind gap'] + e['c_Wind gap'] / m
    for lab, c in (('now (load+wind x2)', now), ('load only x2', alt)):
        t = tiers(c); pl = np.sign(e.read) * (e.rt - e.da); plc = np.sign(e.read) * (e.rt - e.da).clip(-150, 150)
        r = pd.DataFrame(dict(t=t, pl=pl, plc=plc)).groupby('t').agg(h=('pl', 'size'), raw=('pl', 'mean'), clip=('plc', 'mean'), hit=('pl', lambda x: (x > 0).mean())).round(2)
        print(z, lab); print(r.T.to_string()); print()
    ch = (tiers(now) != tiers(alt)); print(z, 'hours that change tier:', ch.sum(), 'of', len(e), '| thin hours:', (m == 2).sum()); print('-' * 60)
