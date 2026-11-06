# Nov 5 2026: numbers for the playbook doc, from the current physics_history (Sep 2025 - Nov 5 2026), East + Ottawa.
import pandas as pd, numpy as np
pd.set_option('display.width', 250)
H = []
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']); h['z'] = z; H.append(h)
e = pd.concat(H); E = e[e.z == 'EAST'].copy()
E['lm'] = E.ont_dem - E.dem_fc; E['wm'] = E.g_wind - E.wind_fc; E['shock'] = E.lm - E.wm
print('== 1. after-bid net shock (load miss - wind miss, MW) vs RT-DA, East')
sb = pd.cut(E.shock, [-9e9, -1000, -500, 0, 500, 1000, 1500, 9e9])
print(E.groupby(sb, observed=True).rd.agg(hours='size', avg='mean', spike50=lambda s: 100 * (s >= 50).mean(), drop25=lambda s: 100 * (s <= -25).mean()).round(1).to_string())
print('\n== 2. $ RT-DA per +100 MW of net shock, by bid-time public spare (East, OLS slope)')
for lab, k in [('spare < 1,500', E.pub_sp < 1500), ('1,500-2,500', E.pub_sp.between(1500, 2500)), ('2,500-4,000', E.pub_sp.between(2500, 4000)), ('4,000-5,500', E.pub_sp.between(4000, 5500)), ('5,500+', E.pub_sp > 5500)]:
    g = E[k & E.shock.notna()]; b = np.polyfit(g.shock / 100, g.rd.clip(-300, 300), 1)[0]; print(f'   {lab:14s} {len(g):5d} h  ${b:5.2f} per 100 MW   spike50 {100*(g.rd>=50).mean():4.1f}%')
print('   misses: load avg abs', round(E.lm.abs().mean()), 'MW (IESO bias', round(E.lm.mean()), '), wind avg abs', round(E.wm.abs().mean()))
print('\n== 3. card points standalone, both hubs (edge $/MWh spike-clipped at 150, hit %), + Temp swing')
P = ['c_Load gap', 'c_Wind gap', 'c_Wind ramp', 'c_Wind upside', 'c_DA priced', 'c_NY pull', 'c_Exports', 'c_Temp swing']
e['d'] = e.rd.clip(-150, 150); rows = []
for p in P:
    g = e[e[p] != 0]; s = np.sign(g[p]); pl = s * g.d; agr = np.sign(g.read) == s; th = g.pub_sp < 2500
    rows.append(dict(point=p[2:], hours=len(g) // 2, edge=pl.mean(), hit=100 * (pl > 0).mean(), with_read=pl[agr].mean(), against=pl[~agr].mean(), thin=pl[th].mean(), loose=pl[~th].mean()))
print(pd.DataFrame(rows).round(2).to_string(index=False))
print('\n== 4. tiers (A/B traded, side x RT-DA, 1 MW) and card size')
e['pl'] = np.where(e.tier == 'C', np.sign(e.score), np.where(e.tier == 'N', np.sign(e.read), e.side)) * e.rd
print(e.groupby(['z', 'tier']).pl.agg(hours='size', avg='mean', hit=lambda s: (s > 0).mean()).round(2).unstack(0).to_string())
for z in ['EAST', 'OTTAWA']:
    k = e[(e.z == z) & e.tier.isin(['A', 'B'])]; print(z, 'plan total', round((k.side * k.rd).sum()), 'months', k.date.str[:7].nunique(), 'months positive', int(((k.side * k.rd).groupby(k.date.str[:7]).sum() > 0).sum()))
g = e[e.score != 0].copy(); g['a'] = g.score.abs().clip(upper=6); g['p'] = np.sign(g.score) * g.rd
print(g.groupby('a').p.agg(hours='size', avg='mean', hit=lambda s: (s > 0).mean()).round(2).to_string())
print('\n== 5. tier record by period, both hubs')
k = e[e.tier.isin(['A', 'B'])].copy(); k['p'] = k.side * k.rd; k['per'] = np.where(k.date < '2026-03-01', 'Sep25-Feb26', np.where(k.date < '2026-07-01', 'Mar-Jun26', 'Jul-Nov26'))
print(k.groupby(['per', 'tier']).p.agg(['size', 'mean']).round(2).unstack().to_string())
