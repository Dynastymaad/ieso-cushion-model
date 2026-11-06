# Nov 5 2026: tests of how DA is built, from IESO's own reports (Aug 14 - Nov 5 2026).
import pandas as pd, numpy as np, glob
pd.set_option('display.width', 250)
a = pd.concat([pd.read_csv(f) for f in sorted(glob.glob('data/research/dabuild/adq_dat_*.csv'))])
v = pd.concat([pd.read_csv(f) for f in sorted(glob.glob('data/research/dabuild/vt_*.csv'))])
vt = v.groupby(['date', 'he'])[['total_load_scheduled', 'total_supply_scheduled', 'net_scheduled', 'total_load_bid', 'total_supply_offered']].sum().reset_index()
ve = v[v.zone.str.startswith('EAST')].groupby(['date', 'he']).net_scheduled.sum().rename('vt_east').reset_index()
vo = v[v.zone.str.startswith('OTTAWA')].groupby(['date', 'he']).net_scheduled.sum().rename('vt_ott').reset_index()
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)[['date', 'he', 'dem_fc', 'ont_dem', 'rd', 'pub_sp', 'gas_hat']]
o = pd.read_csv('data/research/physics_history_OTTAWA.csv', low_memory=False)[['date', 'he', 'rd']].rename(columns={'rd': 'rd_o'})
x = a.merge(vt, on=['date', 'he'], how='left').merge(ve, on=['date', 'he'], how='left').merge(vo, on=['date', 'he'], how='left').merge(h, on=['date', 'he'], how='left').merge(o, on=['date', 'he'], how='left')
x = x[x.pre_avg.notna() & x.da_total_load.notna() & x.ont_dem.notna()].copy()
print('hours', len(x), x.date.min(), x.date.max(), '| pre-bid version times (EST):', x.pre_at.str[11:16].value_counts().head(3).to_dict())
print('\n### which IESO forecast is the warehouse number we use (dem_fc)?')
for c in ['pre_ont_fc', 'pre_avg', 'pre_peak']: print(f'   dem_fc - {c:11s}: mean {(x.dem_fc - x[c]).mean():+6.0f}, avg abs {(x.dem_fc - x[c]).abs().mean():5.0f}')
print('\n### IESO forecasts vs actual Ontario demand (actual minus forecast)')
for c in ['pre_avg', 'pre_peak', 'pre_ont_fc']: print(f'   {c:11s}: mean {(x.ont_dem - x[c]).mean():+6.0f}, avg abs {(x.ont_dem - x[c]).abs().mean():5.0f}')
print(f'   peak minus average: mean {(x.pre_peak - x.pre_avg).mean():+.0f} MW, median {(x.pre_peak - x.pre_avg).median():+.0f}, 90th pct {(x.pre_peak - x.pre_avg).quantile(.9):+.0f}')
print('\n### CLAIM: DA clears load at IESO\'s average forecast')
x['exp'] = x.post_exp_sch.abs(); x['vl'] = x.total_load_scheduled.abs().fillna(0)
cands = {'Total Load': x.da_total_load, 'Total Load - dispatch load': x.da_total_load - x.da_total_dispatch_load, 'Total Load - exports': x.da_total_load - x.exp,
         'Total Load - exports - dispatch load': x.da_total_load - x.exp - x.da_total_dispatch_load, 'Total Load - exports - virtual load': x.da_total_load - x.exp - x.vl,
         'Total Load - exports - virtual load - dispatch load': x.da_total_load - x.exp - x.vl - x.da_total_dispatch_load}
for n, d in cands.items():
    k = d.notna()
    print(f'   {n:52s} vs IESO avg fc: mean {(d - x.pre_avg)[k].mean():+6.0f} avg abs {(d - x.pre_avg)[k].abs().mean():5.0f} | vs actual: mean {(d - x.ont_dem)[k].mean():+6.0f} avg abs {(d - x.ont_dem)[k].abs().mean():5.0f}')
best = x.da_total_load - x.exp - x.vl - x.da_total_dispatch_load; k = best.notna()
b = np.linalg.lstsq(np.c_[np.ones(k.sum()), x.pre_avg[k], (x.ont_dem - x.pre_avg)[k]], best[k], rcond=None)[0]
print(f'   regression: DA ND load = {b[0]:.0f} + {b[1]:.3f} x IESO avg fc + {b[2]:.3f} x (actual - IESO avg fc)   [~0 on the last = DA used IESO\'s forecast, not what happened]')
print('\n### CLAIM: a large peak-over-average gap (Pass 2 may commit extra units) softens RT')
x['pg'] = x.pre_peak - x.pre_avg; q = pd.qcut(x.pg, 4, duplicates='drop')
print(x.groupby(q, observed=True).agg(hours=('rd', 'size'), east_rt_da=('rd', 'mean'), ott_rt_da=('rd_o', 'mean'), rt_below_da=('rd', lambda s: 100 * (s < 0).mean())).round(2).to_string())
k = x.dropna(subset=['rd']); b = np.linalg.lstsq(np.c_[np.ones(len(k)), k.pg / 100, (k.ont_dem - k.pre_avg) / 100], k.rd.clip(-300, 300), rcond=None)[0]
print(f'   East RT-DA = {b[0]:+.2f} {b[1]:+.2f} per 100 MW of peak gap {b[2]:+.2f} per 100 MW of load miss')
print('\n### Virtual traders: how big and which way (MW per hour, all zones)')
print(f'   virtual load scheduled avg {x.total_load_scheduled.abs().mean():.0f}, virtual supply scheduled avg {x.total_supply_scheduled.mean():.0f}, net (supply - load) {x.net_scheduled.mean():+.0f}')
print(f'   bids offered: load {x.total_load_bid.mean():.0f}, supply {x.total_supply_offered.mean():.0f}')
print(f'   East hub net scheduled avg {x.vt_east.mean():+.0f} (abs {x.vt_east.abs().mean():.0f}); Ottawa {x.vt_ott.mean():+.0f} (abs {x.vt_ott.abs().mean():.0f})')
print(v.groupby('zone').net_scheduled.agg(['mean', lambda s: s.abs().mean()]).round(0).sort_values('mean').to_string())
x['nb'] = pd.qcut(x.net_scheduled, 4, labels=['most virtual LOAD (buying DA)', '2nd', '3rd', 'most virtual SUPPLY (selling DA)'])
print(x.groupby('nb', observed=True).agg(net_MW=('net_scheduled', 'mean'), east_rt_da=('rd', 'mean'), ott_rt_da=('rd_o', 'mean'), east_rt_below=('rd', lambda s: 100 * (s < 0).mean()), load_miss=('ont_dem', lambda s: 0)).drop(columns='load_miss').round(2).to_string())
x.to_csv('data/research/dabuild/da_build_frame.csv', index=False)
