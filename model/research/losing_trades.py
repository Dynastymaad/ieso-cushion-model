# Nov 5 2026: what did the trades that went against the model look like at the bid? East/Ottawa, Dynasty virtuals Sep 2025 - Sep 2026.
import pandas as pd, numpy as np
pd.set_option('display.width', 250)
d = pd.read_csv('cache/dynasty_virtuals.csv'); d['he'] = d.hour; d['side'] = np.where(d.buysell.str.lower().str.startswith('b'), 1, -1); d['zone'] = d.zone.str.upper(); d['mw'] = d.volume.abs()
P = []
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).rename(columns={'side': 'm_side'})
    k = d[d.zone.str.contains(z)].merge(h, on=['date', 'he'], how='inner').dropna(subset=['rt', 'da']); k['zz'] = z; P.append(k)
k = pd.concat(P); k['pl'] = k.side * k.rd * k.mw; k['pl1'] = k.side * k.rd
k['grp'] = np.where(k.tier.isin(['A', 'B']), np.where(k.m_side == k.side, 'with model', 'AGAINST model'), 'model no trade')
k['grp'] = (np.where(k.side > 0, 'BUY ', 'SELL ') + k.grp)
cols = dict(MWh=('mw', 'sum'), pnl=('pl', 'sum'), per_MWh=('pl1', 'mean'), rt_above_da=('rd', lambda s: 100 * (s > 0).mean()), read=('read', 'mean'), card=('score', 'mean'),
            DA_vs_usual=('vs', 'mean'), da_fc=('da_fc', 'mean'), da=('da', 'mean'), spare=('pub_sp', 'mean'), gas_need=('gas_hat', 'mean'), load_gap=('load_gap', 'mean'), wind_gap=('wind_gap', 'mean'), ny=('ny', 'mean'))
print(k.groupby('grp').agg(**cols).round(1).T.to_string())
b = k[(k.side > 0)]
print('\n### Buys: result by how DA was priced vs usual at the bid (DA priced point input, $ above the 14-day usual for that hour)')
print(b.groupby(pd.cut(b.vs, [-99, -8, 0, 8, 18, 999]), observed=True).agg(MWh=('mw', 'sum'), per_MWh=('pl1', 'mean'), rt_above=('rd', lambda s: 100 * (s > 0).mean())).round(1).to_string())
print('\n### Buys: by public spare at the bid')
print(b.groupby(pd.cut(b.pub_sp, [-9e9, 1500, 2500, 4000, 9e9]), observed=True).agg(MWh=('mw', 'sum'), per_MWh=('pl1', 'mean'), rt_above=('rd', lambda s: 100 * (s > 0).mean()), da=('da', 'mean')).round(1).to_string())
print('\n### Buys: by hour block and month')
print(b.groupby(pd.cut(b.he, [0, 6, 15, 21, 24]), observed=True).agg(MWh=('mw', 'sum'), per_MWh=('pl1', 'mean')).round(1).to_string())
print(b.groupby(b.date.str[:7]).agg(MWh=('mw', 'sum'), pnl=('pl', 'sum'), per_MWh=('pl1', 'mean')).round(0).T.to_string())
print('\n### Worst 10 buy days')
print(b.groupby('date').agg(MWh=('mw', 'sum'), pnl=('pl', 'sum'), read=('read', 'mean'), card=('score', 'mean'), vs=('vs', 'mean'), spare=('pub_sp', 'mean'), gas=('gas_hat', 'mean'), da=('da', 'mean'), rt=('rt', 'mean')).sort_values('pnl').head(10).round(0).to_string())
