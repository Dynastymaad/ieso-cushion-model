"""gas_ledge2.py -- Nov 2 2026 research. (1) is the ledge one-sided (misses up vs down)? (2) gas ramp (bid-time 3 h change in gas need) vs RT - DA, on and off the ledge."""
import sys, numpy as np, pandas as pd
pd.set_option('display.width', 220)
for z in ('EAST', 'OTTAWA'):
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['da', 'rt', 'ont_dem', 'g_wind'])
    h['net_miss'] = (h.ont_dem - h.dem_fc) - (h.g_wind - h.wind_fc); h = h[h.date >= '2026-01-01']
    h['ledge'] = np.where(h.da_fc >= 75, 'DA fc 75+', 'DA fc <75')
    print(f'\n######## {z} 2026 ########')
    print('-- (1) RT-DA by realised net-load miss (after the fact), on vs off the ledge: mean / median / % RT>DA+50')
    b = pd.cut(h.net_miss, [-9e9, -600, -300, -100, 100, 300, 600, 9e9])
    t = h.groupby(['ledge', b], observed=True).rd.agg(h='size', mean='mean', med='median', spike=lambda x: (x > 50).mean() * 100).round(1)
    print(t.unstack(0).to_string())
    print('-- (2) RT-DA by bid-time gas ramp g3 (gas need now minus 3 h earlier, MW): + = gas ramping up into the hour')
    gb = pd.cut(h.g3, [-9e9, -1500, -800, -300, 300, 800, 1500, 9e9])
    t = h.groupby(['ledge', gb], observed=True).rd.agg(h='size', mean='mean', med='median', up=lambda x: (x > 0).mean() * 100, spike=lambda x: (x > 50).mean() * 100).round(1)
    print(t.unstack(0).to_string())
    print('-- (2b) same, by time of day (ramp up vs ramp down), all 2026')
    h['blk'] = pd.cut(h.he, [0, 6, 10, 15, 21, 24], labels=['HE1-6', 'HE7-10', 'HE11-15', 'HE16-21', 'HE22-24'])
    h['rb'] = pd.cut(h.g3, [-9e9, -800, 800, 9e9], labels=['down 800+', 'flat', 'up 800+'])
    t = h.groupby(['blk', 'rb'], observed=True).rd.agg(h='size', mean='mean', med='median', spike=lambda x: (x > 50).mean() * 100).round(1)
    print(t.unstack(1).to_string())
    print('-- (2c) does the ramp change how much a miss matters? RT-DA per 100 MW of realised miss')
    def sl(g): return pd.Series(dict(h=len(g), per100=round(np.polyfit(g.net_miss.clip(-2000, 2000), g.rd.clip(-150, 300), 1)[0] * 100, 2) if len(g) > 60 else np.nan))
    print(h.groupby(['ledge', 'rb'], observed=True).apply(sl, include_groups=False).unstack(0).to_string())
