# Nov 5 2026: models that predict IESO's load miss (actual - IESO pre-DA forecast) at the bid. Walk-forward, data through D-2 only.
import pandas as pd, numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor as HGB
pd.set_option('display.width', 250)
L = pd.read_csv('data/load_at_bid.csv')[['date', 'he', 'ont_dem', 'lf_adq2', 'lf_tesla', 'lf_dynasty', 'lf_meteologica']]
H = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)[['date', 'he', 'dem_fc']]
x = L.merge(H, on=['date', 'he'], how='left'); x['ieso'] = x.dem_fc.fillna(x.lf_adq2)
print('IESO pre-DA: physics dem_fc vs load_at_bid lf_adq2 avg abs diff', round((x.dem_fc - x.lf_adq2).abs().mean(), 1))
w = pd.read_csv('data/wx/wx_hourly.csv')[['date', 'he', 't_fc', 't_act', 'feel_fc', 'cc_fc']]
for c in ['t_fc', 't_act', 'feel_fc']: w[c] = (w[c] - 32) / 1.8
a2 = w[['date', 'he', 't_act']].copy(); a2['date'] = (pd.to_datetime(a2.date) + pd.Timedelta(days=2)).dt.strftime('%Y-%m-%d')
x = x.merge(w[['date', 'he', 't_fc', 'feel_fc', 'cc_fc']], on=['date', 'he'], how='left').merge(a2.rename(columns={'t_act': 't_d2'}), on=['date', 'he'], how='left')
x = x.sort_values(['date', 'he']).reset_index(drop=True); x['miss'] = x.ont_dem - x.ieso
x['g_tes'] = x.lf_tesla - x.ieso; x['g_dyn'] = x.lf_dynasty - x.ieso; x['g_met'] = x.lf_meteologica - x.ieso
x['bias7'] = x.groupby('he').miss.transform(lambda s: s.shift(2).rolling(7, min_periods=3).mean())       # IESO's own miss, same HE, D-2..D-8
x['bias28'] = x.groupby('he').miss.transform(lambda s: s.shift(2).rolling(28, min_periods=10).mean())
x['tswing'] = x.t_fc - x.t_d2; x['dow'] = pd.to_datetime(x.date).dt.dayofweek; x['mo'] = pd.to_datetime(x.date).dt.month
x['hd'] = np.clip(15 - x.t_fc, 0, None); x['cd'] = np.clip(x.feel_fc - 20, 0, None)
F_lin = ['g_tes', 'g_dyn', 'bias7', 'bias28']
F_gb = ['g_tes', 'g_dyn', 'bias7', 'bias28', 'tswing', 't_fc', 'hd', 'cd', 'cc_fc', 'he', 'dow', 'mo', 'ieso']
days = sorted(x.date.unique()); dd = pd.to_datetime(x.date)
P = {k: pd.Series(np.nan, index=x.index) for k in ['M1 linear: vendor gaps + IESO recent bias', 'M2 boosted: + temperature, hour, day type', 'M3 boosted + Meteologica (where it exists)']}
for i, D in enumerate(days):
    Dt = pd.Timestamp(D); tr = x[(dd <= Dt - pd.Timedelta(days=2))]; te = x.index[x.date == D]
    if tr.date.nunique() < 90: continue
    t = tr.dropna(subset=F_lin + ['miss']); t = t[pd.to_datetime(t.date) > Dt - pd.Timedelta(days=150)]
    A = np.c_[np.ones(len(t)), t[F_lin].values]; b = np.linalg.solve(A.T @ A + 1e3 * np.eye(A.shape[1]), A.T @ t.miss.values)
    q = x.loc[te, F_lin]; ok = q.notna().all(axis=1); P['M1 linear: vendor gaps + IESO recent bias'][te[ok.values]] = np.c_[np.ones(ok.sum()), q[ok].values] @ b
    if i % 7 == 0 or 'gb' not in globals():
        t2 = tr.dropna(subset=['miss']); gb = HGB(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40).fit(t2[F_gb], t2.miss)
        t3 = t2[t2.g_met.notna()]; gm = HGB(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40).fit(t3[F_gb + ['g_met']], t3.miss) if len(t3) > 600 else None
    P['M2 boosted: + temperature, hour, day type'][te] = gb.predict(x.loc[te, F_gb])
    if gm is not None:
        k = te[x.loc[te, 'g_met'].notna().values]
        if len(k): P['M3 boosted + Meteologica (where it exists)'][k] = gm.predict(x.loc[k, F_gb + ['g_met']])
x = x.assign(**{f'p{i+1}': v for i, v in enumerate(P.values())})
x.to_csv('data/research/iesomiss_pred.csv', index=False)
def score(k, label):
    print(f'\n{label}: {len(k)} h, {k.date.min()}..{k.date.max()}')
    print(f'   {"IESO as is":44s} MAE {k.miss.abs().mean():4.0f}')
    for n, c in [('Tesla', 'g_tes'), ('Dynasty', 'g_dyn'), ('Meteologica', 'g_met')] + [(n, f'p{i+1}') for i, n in enumerate(P)]:
        if k[c].notna().mean() < 0.95: continue
        print(f'   {n:44s} MAE {(k.miss - k[c]).abs().mean():4.0f} | corr with IESO miss {k[c].corr(k.miss):.2f} | sign right when |miss|>200: {100*(np.sign(k[c]) == np.sign(k.miss))[k.miss.abs() > 200].mean():.0f}%')
score(x[x.p1.notna() & x.p2.notna() & x.g_tes.notna() & x.g_dyn.notna() & x.miss.notna() & (x.date >= '2025-09-08')], 'ALL HOURS (no Meteologica)')
score(x[x.p3.notna() & x.g_met.notna() & x.p1.notna() & x.g_dyn.notna() & x.miss.notna()], 'METEOLOGICA HOURS')
