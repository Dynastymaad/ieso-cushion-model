"""temp_load.py -- Nov 5 2026 research only. How Ontario load responds to temperature, by season and time of day.
Temperature = Toronto Pearson (CYYZ) hourly actual (deg F in the Warehouse, converted to C), stamped in Eastern local time,
mapped to IESO hour-ending EST. Load = IESO Ontario Demand (actual). IESO's own D-1 forecast = pre-DA Adequacy demand."""
import sys, numpy as np, pandas as pd; sys.path.insert(0, 'model'); import common as C
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
w = pd.read_csv(C.CACHE / 'cyyz_weather_actual.csv'); w['t'] = pd.to_datetime(w.EffectiveDateTime)
w['t'] = w.t.dt.tz_localize('America/Toronto', ambiguous='NaT', nonexistent='NaT').dt.tz_convert('Etc/GMT+5').dt.tz_localize(None) + pd.Timedelta(hours=1)  # hour-ending EST
w = w.dropna(subset=['t']); w['date'] = w.t.dt.strftime('%Y-%m-%d'); w['he'] = w.t.dt.hour.replace(0, 24)
w.loc[w.he == 24, 'date'] = (w.loc[w.he == 24, 't'] - pd.Timedelta(days=1)).dt.strftime('%Y-%m-%d')
w['tc'] = (w.Temperature - 32) / 1.8; w['dp'] = (w.DewPoint - 32) / 1.8
L = C.actual_demand()[['date', 'he', 'ont_dem']]; L['date'] = L.date.astype(str)
a = C.adq2('preDA')[['date', 'he', 'dem_fc']]; a['date'] = a.date.astype(str)
x = L.merge(w[['date', 'he', 'tc', 'dp']], on=['date', 'he']).merge(a, on=['date', 'he'], how='left')
x['dt'] = pd.to_datetime(x.date); x['m'] = x.dt.dt.month; x['wk'] = x.dt.dt.dayofweek >= 5
x['season'] = x.m.map({12: 'Winter', 1: 'Winter', 2: 'Winter', 3: 'Spring', 4: 'Spring', 5: 'Spring', 6: 'Summer', 7: 'Summer', 8: 'Summer', 9: 'Fall', 10: 'Fall', 11: 'Fall'})
x['yr'] = x.dt.dt.year; x['blk'] = pd.cut(x.he, [0, 6, 10, 15, 21, 24], labels=['HE1-6', 'HE7-10', 'HE11-15', 'HE16-21', 'HE22-24'])
print('hours', len(x), x.date.min(), x.date.max())
wd = x[~x.wk]
print('\n== 1. Weekday load (MW) by temperature (C) and season, all hours ==')
tb = pd.cut(wd.tc, [-40, -20, -15, -10, -5, 0, 5, 10, 15, 18, 21, 24, 27, 30, 45])
print(wd.groupby([tb, 'season'], observed=True).ont_dem.mean().unstack().round(0).to_string())
print('\n== 2. Weekday evening HE17-20 load by temperature and season ==')
pk = wd[wd.he.between(17, 20)]
print(pk.groupby([pd.cut(pk.tc, [-40, -20, -15, -10, -5, 0, 5, 10, 15, 18, 21, 24, 27, 30, 45]), 'season'], observed=True).ont_dem.mean().unstack().round(0).to_string())
# 3. sensitivity: piecewise slope (MW per C) by season x block, fit on daily-shape-removed data: load ~ hour-of-day x month means + heating/cooling terms
print('\n== 3. MW per 1 C, weekday (piecewise: heating below 15 C, cooling above 20 C), by season and block ==')
rows = []
for (s, b), g in wd.groupby(['season', 'blk'], observed=True):
    H = np.clip(15 - g.tc, 0, None); K = np.clip(g.tc - 20, 0, None)
    A = np.c_[np.ones(len(g)), H, K, pd.get_dummies(g.he, drop_first=True).values.astype(float), (g.yr == 2026).astype(float)]
    beta = np.linalg.lstsq(A, g.ont_dem.values, rcond=None)[0]
    rows.append(dict(season=s, block=b, hours=len(g), heat_MW_per_C_colder=round(beta[1]), cool_MW_per_C_hotter=round(beta[2]), temp_range=f'{g.tc.min():.0f}..{g.tc.max():.0f}'))
print(pd.DataFrame(rows).pivot(index='season', columns='block', values=['heat_MW_per_C_colder', 'cool_MW_per_C_hotter']).to_string())
print('\n== 4. Same temperature, different year: weekday load 2025 vs 2026 by month (same temp band 5-15 C or 20-27 C) ==')
for lo, hi in ((5, 15), (20, 27), (-10, 0)):
    g = wd[wd.tc.between(lo, hi)]
    t = g.groupby(['m', 'yr']).ont_dem.mean().unstack().round(0)
    if 2025 in t and 2026 in t: t['2026 - 2025'] = t[2026] - t[2025]
    print(f'-- temperature {lo}..{hi} C'); print(t.dropna().to_string())
print('\n== 5. Does IESO miss load more at some temperatures? (actual - IESO D-1 forecast), weekday ==')
y = wd.dropna(subset=['dem_fc']); y = y.assign(miss=y.ont_dem - y.dem_fc)
print(y.groupby([pd.cut(y.tc, [-40, -15, -5, 5, 15, 20, 25, 30, 45]), 'season'], observed=True).miss.agg(['mean', lambda s: s.abs().mean()]).round(0).unstack().to_string())
# 6. temperature change day over day vs IESO miss (cold snaps / warm-ups)
d = y.groupby('date').agg(tc=('tc', 'mean'), miss=('miss', 'mean'), season=('season', 'first')).reset_index()
d['dT'] = d.tc - d.tc.shift(1)
print('\n== 6. IESO daily load miss by day-over-day temperature change (weekdays) ==')
print(d.groupby([pd.cut(d.dT, [-30, -8, -4, -1.5, 1.5, 4, 8, 30]), 'season'], observed=True).miss.agg(['size', 'mean']).round(0).unstack().to_string())
x.to_csv(C.DATA / 'research' / 'temp_load.csv', index=False)
