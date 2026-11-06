# Nov 5 2026: physics audit. After the bid, every MW that load or another fuel misses vs the DA schedule has to be covered by gas (or exports/imports).
# Which pieces drive that, how much of RT-DA it explains, and does the read have a bid-time tell for each piece?   Aug 14 - Nov 5 2026 (IESO post-DA schedules).
import pandas as pd, numpy as np, glob
pd.set_option('display.width', 250)
f = pd.concat([pd.read_csv(x) for x in glob.glob('data/research/dabuild/fuel_*.csv')])
a = pd.concat([pd.read_csv(x) for x in glob.glob('data/research/dabuild/adq_dat_*.csv')])[['date', 'he', 'pre_avg', 'post_exp_sch', 'post_imp_sch']]
H = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)
O = pd.read_csv('data/research/physics_history_OTTAWA.csv', low_memory=False)[['date', 'he', 'rd']].rename(columns={'rd': 'rd_o'})
it = pd.read_csv('data/intertie_actual.csv')[['date', 'he', 'tot_flow']]; it['date'] = it.date.astype(str)
x = f.merge(a, on=['date', 'he']).merge(H, on=['date', 'he']).merge(O, on=['date', 'he']).merge(it.rename(columns={'tot_flow': 'nx_act'}), on=['date', 'he'], how='left')
x = x.dropna(subset=['rd', 'g_gas', 'da_gas', 'pre_avg', 'g_hydro', 'g_nuclear', 'g_wind'])
x['nx_da'] = x.post_exp_sch.abs() - x.post_imp_sch.abs()
D = {'load (actual - IESO avg fc)': x.ont_dem - x.pre_avg, 'net exports (actual - DA)': x.nx_act - x.nx_da,
     'wind (DA - actual)': x.da_wind - x.g_wind, 'hydro (DA - actual)': x.da_hydro - x.g_hydro, 'nuclear (DA - actual)': x.da_nuclear - x.g_nuclear,
     'solar (DA - actual)': x.da_solar.fillna(0) - x.g_solar.fillna(0), 'biofuel+other (DA - actual)': (x.da_biofuel.fillna(0) + x.da_other.fillna(0)) - (x.g_biofuel.fillna(0) + x.g_other.fillna(0))}
D = pd.DataFrame(D); D['sum of pieces (gas had to cover)'] = D.sum(axis=1); x['gas_dev'] = x.g_gas - x.da_gas
print(f'{len(x)} hours, {x.date.nunique()} days, {x.date.min()}..{x.date.max()}  (+ = adds to what gas had to cover)')
print(f'check: actual gas - DA gas schedule averages {x.gas_dev.mean():+.0f}, sd {x.gas_dev.std():.0f}; corr with the sum of pieces {x.gas_dev.corr(D.iloc[:, -1]):.2f}')
print('\n### Each piece: typical size, how much it moves gas, how much RT-DA it explains (East)')
y = x.rd.clip(-300, 300); tot = D.iloc[:, -1]; rows = []
for c in D.columns:
    s = D[c]; rows.append(dict(piece=c, mean=s.mean(), typical_abs=s.abs().mean(), share_of_gas_swing=100 * np.cov(s, tot)[0, 1] / tot.var(), corr_rt_da=s.corr(y), corr_rt_da_thin=s[x.pub_sp < 2500].corr(y[x.pub_sp < 2500])))
print(pd.DataFrame(rows).round(2).to_string(index=False))
print('   (share_of_gas_swing = how much of the hour-to-hour swing in what gas had to cover comes from that piece; they add to 100)')
print('\n### RT-DA by what gas had to cover after the bid, and by spare (East $/MWh)')
b = pd.cut(tot, [-9e9, -1000, -500, 0, 500, 1000, 9e9]); sp = pd.cut(x.pub_sp, [-9e9, 2500, 5000, 9e9], labels=['spare<2.5k', '2.5-5k', '5k+'])
print(x.groupby([b, sp], observed=True).rd.mean().unstack().round(1).to_string()); print(x.groupby(b, observed=True).rd.agg(['size', 'mean', 'median']).round(1).to_string())
print('\n### Hydro and nuclear: are their deviations visible at the bid?')
x['hyd_dev'] = D['hydro (DA - actual)']; x['nuc_dev'] = D['nuclear (DA - actual)']
x = x.sort_values(['date', 'he'])
for c in ['hyd_dev', 'nuc_dev']:
    lag = x.groupby('he')[c].transform(lambda s: s.shift(2).rolling(7, min_periods=3).mean())
    print(f'   {c}: mean {x[c].mean():+.0f}, typical {x[c].abs().mean():.0f} MW | corr with its own trailing week (same HE) {x[c].corr(lag):+.2f} | by hour block:', x.groupby(pd.cut(x.he, [0, 6, 15, 21, 24]), observed=True)[c].mean().round(0).to_dict())
