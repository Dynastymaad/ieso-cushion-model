"""Which bid-time numbers foresee the two surprises that drive RT-DA (load vs IESO, wind vs IESO)?"""
import pandas as pd, numpy as np
e = pd.read_csv('data/research/physics_EAST.csv').sort_values(['date', 'he'])
nw = [c for c in e if c.startswith('wf_') and c != 'wf_meteologica']
e['gap_meteo_L'] = e.lf_meteologica - e.dem_fc; e['gap_tesla_L'] = e.lf_tesla - e.dem_fc; e['gap_dyn_L'] = e.lf_dynasty - e.dem_fc
e['gap_meteo_W'] = e.dem_fc * 0 + (e.wind_fc - e.wf_meteologica); e['gap_models_W'] = e.wind_fc - e.w_models; e['gap_low_W'] = e.wind_fc - e[nw].min(axis=1)
# IESO's own recent miss for the same hour, only days <= D-2 (7-day mean)
for s, c in [('s_load', 'bias_L'), ('s_wind', 'bias_W')]:
    p = e.pivot_table(index='date', columns='he', values=s).sort_index()
    p.index = pd.to_datetime(p.index); r = p.rolling('7D', min_periods=3).mean(); r.index = r.index + pd.Timedelta(days=2)
    b = r.stack().rename(c).reset_index().rename(columns={'level_0': 'date', 'level_1': 'he'}); b['date'] = b.date.dt.strftime('%Y-%m-%d')
    e = e.merge(b, on=['date', 'he'], how='left')
print('load surprise (actual demand - IESO fc), MW: mean', round(e.s_load.mean()), ' MAE', round(e.s_load.abs().mean()))
for c in ['gap_meteo_L', 'gap_tesla_L', 'gap_dyn_L', 'bias_L']:
    k = e[[c, 's_load']].dropna(); print(f'  {c:13s} n{len(k):5d} corr {k[c].corr(k.s_load):+.2f}  slope {np.polyfit(k[c], k.s_load, 1)[0]:+.2f}')
print('wind surprise (IESO fc - actual wind), MW: mean', round(e.s_wind.mean()), ' MAE', round(e.s_wind.abs().mean()))
for c in ['gap_meteo_W', 'gap_models_W', 'gap_low_W', 'bias_W', 'w_spread']:
    k = e[[c, 's_wind']].dropna(); print(f'  {c:13s} n{len(k):5d} corr {k[c].corr(k.s_wind):+.2f}  slope {np.polyfit(k[c], k.s_wind, 1)[0]:+.2f}')
e.to_csv('data/research/physics_EAST.csv', index=False)
