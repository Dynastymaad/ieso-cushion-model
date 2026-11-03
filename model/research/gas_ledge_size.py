"""gas_ledge_size.py -- Nov 2 2026. Does the ledge (DA fc 75+ or spare < 2,500) change the edge per MWh of the existing tiers, by side and gas ramp?
If the edge is bigger there with a similar hit rate, the ledge is a sizing input, not a scoring one."""
import numpy as np, pandas as pd
pd.set_option('display.width', 220)
for z in ('EAST', 'OTTAWA'):
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']); h = h[h.date <= '2026-11-01']
    h = h[h.tier.isin(['A', 'B'])].copy(); h['pnl'] = h.side * h.rd
    h['ledge'] = np.where((h.da_fc >= 75) | (h.pub_sp < 2500), 'on ledge', 'off')
    h['ramp'] = pd.cut(h.g3, [-9e9, -800, 800, 9e9], labels=['gas down 800+', 'flat', 'gas up 800+'])
    h['sd'] = np.where(h.side > 0, 'long', 'short'); h['yr'] = np.where(h.date < '2026-01-01', '2025', '2026')
    f = lambda g: pd.Series(dict(h=len(g), per=round(g.pnl.mean(), 2), med=round(g.pnl.median(), 1), hit=round((g.pnl > 0).mean() * 100), tot=round(g.pnl.sum()),
                                 p5=round(g.pnl.quantile(.05), 0)))
    print(f'\n######## {z}: tiers A+B, 1 MW per hour ########')
    for yr in ('2026', '2025'):
        print(f'-- {yr}: by ledge x side'); print(h[h.yr == yr].groupby(['ledge', 'sd']).apply(f, include_groups=False).to_string())
    print('-- 2026: by ledge x side x gas ramp'); print(h[h.yr == '2026'].groupby(['ledge', 'sd', 'ramp'], observed=True).apply(f, include_groups=False).to_string())
    print('-- 2025: by ledge x side x gas ramp'); print(h[h.yr == '2025'].groupby(['ledge', 'sd', 'ramp'], observed=True).apply(f, include_groups=False).to_string())
