# Nov 5 2026: how many MW does a 1 C change move Ontario load, by season and time of day? Tested on same-hour pairs (day D vs D-2, same day type).
# Temps = Ontario load-weighted actual (Open-Meteo, data/wx/wx_hourly.csv), load = IESO Ontario demand actual (data/load_at_bid.csv).
#  A  current card rule: slope picked by D's temp (<12: -150/C, >18: +300/C, else 0)
#  B  degree-hours: heating = max(15-T,0), cooling = max(T-20,0) on both days, slopes by block
#  C  same, slopes by season x block          D  C with feels-like for cooling (humidity)
# Scored by leave-one-month-out: slopes fitted without the month being predicted.
import pandas as pd, numpy as np, json, sys
w = pd.read_csv('data/wx/wx_hourly.csv')
for c in ['t_act', 'feel_act', 't_fc', 'feel_fc']: w[c] = (w[c] - 32) * 5 / 9
L = pd.read_csv('data/load_at_bid.csv')[['date', 'he', 'ont_dem']].merge(w[['date', 'he', 't_act', 'feel_act']], on=['date', 'he'])
d2 = L.copy(); d2['date'] = (pd.to_datetime(d2.date) + pd.Timedelta(days=2)).dt.strftime('%Y-%m-%d')
x = L.merge(d2, on=['date', 'he'], suffixes=('', '_2')).dropna()
dt = pd.to_datetime(x.date); dow = dt.dt.dayofweek; dow2 = (dow - 2) % 7
x = x[(dow < 5) == (dow2 < 5)].copy(); dt = pd.to_datetime(x.date)                     # same day type only (weekday vs weekday, weekend vs weekend)
x['m'] = dt.dt.strftime('%Y-%m'); mo = dt.dt.month
x['season'] = np.select([mo.isin([12, 1, 2]), mo.isin([3, 4, 5]), mo.isin([6, 7, 8])], ['Winter', 'Spring', 'Summer'], 'Fall')
x['blk'] = pd.cut(x.he, [0, 6, 10, 15, 21, 24], labels=['HE1-6', 'HE7-10', 'HE11-15', 'HE16-21', 'HE22-24']).astype(str)
x['dL'] = x.ont_dem - x.ont_dem_2; x['dT'] = x.t_act - x.t_act_2
H = lambda t: np.clip(15 - t, 0, None); K = lambda t: np.clip(t - 20, 0, None)
x['dH'] = H(x.t_act) - H(x.t_act_2); x['dK'] = K(x.t_act) - K(x.t_act_2); x['dKf'] = K(x.feel_act) - K(x.feel_act_2)
print('pairs', len(x), x.date.min(), x.date.max())
def fit(g, kc):
    A = np.c_[g.dH, g[kc]]; lam = 5.0 * len(g) / 1000                                          # light ridge so thin cells don't go wild
    return np.linalg.solve(A.T @ A + lam * np.eye(2), A.T @ g.dL)
def cv(keys, kc='dK'):
    p = pd.Series(np.nan, index=x.index)
    for m in x.m.unique():
        tr, te = x[x.m != m], x[x.m == m]
        for k, g in te.groupby(keys):
            t = tr.set_index(keys).loc[[k] if not isinstance(k, tuple) else [k]] if False else tr[(tr[keys] == pd.Series(k if isinstance(k, tuple) else (k,), index=keys)).all(axis=1)]
            if len(t) < 200: t = tr[tr.blk == g.blk.iloc[0]]
            h, c = fit(t, kc); p[g.index] = h * g.dH + c * g[kc]
    return p
slopeA = np.where(x.t_act < 12, -150, np.where(x.t_act > 18, 300, 0)); pA = slopeA * x.dT
P = {'no temperature (0)': pd.Series(0.0, index=x.index), 'A current card rule': pd.Series(pA, index=x.index),
     'B by time of day': cv(['blk']), 'C by season x time of day': cv(['season', 'blk']), 'D = C + humidity (feels-like)': cv(['season', 'blk'], 'dKf')}
print('\n== How well each rule predicts the 2-day load change (MW), leave-one-month-out ==')
for k, p in P.items():
    e = x.dL - p; big = x.dT.abs() >= 3
    print(f'  {k:32s} MAE {e.abs().mean():5.0f} | on days temp moved 3C+: {e[big].abs().mean():5.0f} | explains {100*(1 - (e**2).sum()/((x.dL - x.dL.mean())**2).sum()):4.0f}% of the change')
for k in ['Winter', 'Spring', 'Summer', 'Fall']:
    s = x.season == k; print(f'  {k:7s}', ' | '.join(f'{n[:1]} {(x.dL - p)[s].abs().mean():4.0f}' for n, p in P.items()))
# full-sample slopes for the display table (MW per 1 C: heating = per C colder below 15, cooling = per C hotter above 20)
T = {}
for (s, b), g in x.groupby(['season', 'blk']):
    h, c = fit(g, 'dK'); T.setdefault(s, {})[b] = dict(heat=int(round(-h / 10) * 10), cool=int(round(c / 10) * 10), n=int(len(g)))
print('\n== MW per 1 C (heat = per C colder below 15 C, cool = per C hotter above 20 C) ==')
for s in ['Winter', 'Spring', 'Summer', 'Fall']: print(f'  {s:7s}', '  '.join(f"{b}: heat {v['heat']:4d} cool {v['cool']:4d}" for b, v in T[s].items()))
x.assign(pA=P['A current card rule'], pB=P['B by time of day'], pC=P['C by season x time of day'], pD=P['D = C + humidity (feels-like)'])[['date', 'he', 'dL', 'dT', 'pA', 'pB', 'pC', 'pD']].to_csv('data/research/temp_slope_cv.csv', index=False)
json.dump(T, open('data/research/temp_slopes.json', 'w'))
