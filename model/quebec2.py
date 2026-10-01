"""quebec2.py -- Quebec demand (Hydro-Quebec open data 2019-2024 + a temperature model for 2025-26), HQ's other
interchanges (EIA ISNE/NYIS -> HQT via NRGStream), NY HQ LBMP, and whether any of it helps East/Ottawa at the bid.
HQ publishes hourly demand only up to 2025-01-01 (and a rolling 2 days), so for the test window HQ demand is MODELLED
from Montreal (.65) / Quebec City (.35) temperature: fit 2019-2023, checked on 2024, then run on
  actual temperature (explanatory)  and  the Open-Meteo forecast issued 2 days ahead (pd2 = bid-safe).
Outputs data/quebec/hq_hourly.csv, data/quebec2.json."""
import sys, json, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, nrg_import as N, fail_fix as FF, quebec as Q
QD = C.DATA / 'quebec'

def key_utc(ts):
    t = pd.to_datetime(ts, utc=True).dt.tz_localize(None) - pd.Timedelta(hours=5) + pd.Timedelta(hours=1)
    return C._ts_to_key(t)

def temps():
    w = pd.read_csv(QD / 'openmeteo_quebec.csv'); w['wt'] = w['loc'].map({'YUL': .65, 'YQB': .35})
    w = w.dropna(subset=['t_act']).groupby('time_utc').apply(lambda d: pd.Series({'t': np.average(d.t_act, weights=d.wt), 't_fc': np.average(d.t_pd2, weights=d.wt) if d.t_pd2.notna().all() else np.nan})).reset_index()
    w['date'], w['he'] = key_utc(w.time_utc); w['he'] = w.he.astype(int)
    return w

def X(d, col):
    t = d[col].values; hdd = np.clip(18 - t, 0, None); cdd = np.clip(t - 20, 0, None)
    H = pd.get_dummies(d.he.astype(int)).values.astype(float); wk = (pd.to_datetime(d.date).dt.dayofweek >= 5).values.astype(float)
    return np.column_stack([H, hdd, hdd ** 2 / 10, cdd, wk, H * hdd[:, None] / 10])

def demand_model():
    h = pd.read_csv(QD / 'hq_demand_hist_2019_2024.csv'); h['date'], h['he'] = key_utc(h['date']); h['he'] = h.he.astype(int)
    w = temps(); d = h.merge(w, on=['date', 'he']).dropna(subset=['moyenne_mw', 't'])
    tr, te = d[d.date < '2024-01-01'], d[d.date >= '2024-01-01']
    b = np.linalg.lstsq(X(tr, 't'), tr.moyenne_mw.values, rcond=None)[0]
    e = X(te, 't') @ b - te.moyenne_mw.values
    fit = dict(train=f'{tr.date.min()}..{tr.date.max()}', test_2024_mae=round(np.abs(e).mean()), test_2024_mape=round(np.abs(e / te.moyenne_mw.values).mean() * 100, 1),
               r2=round(1 - (e @ e) / ((te.moyenne_mw - te.moyenne_mw.mean()) ** 2).sum(), 3), mean_mw=round(te.moyenne_mw.mean()))
    b = np.linalg.lstsq(X(d, 't'), d.moyenne_mw.values, rcond=None)[0]           # refit on all 6 years for 2025-26
    z = w[w.date >= '2025-04-01'].copy(); z['hq'] = X(z, 't') @ b
    zf = z.dropna(subset=['t_fc']); z.loc[zf.index, 'hq_fc'] = X(zf, 't_fc') @ b
    z[['date', 'he', 't', 't_fc', 'hq', 'hq_fc']].to_csv(QD / 'hq_hourly.csv', index=False)
    return fit, z

def interchange():
    r = pd.read_csv(QD / 'nrg3_hq_interchange.csv'); r['date'], r['he'] = N.to_key(r.ts); r = r[r.date.ne('NaT') & r.he.notna()]; r['he'] = r.he.astype(int)
    w = r.pivot_table(index=['date', 'he'], columns='key', values='value').reset_index().rename(columns={4157: 'ny_hq_lbmp', 192620: 'isne_to_hq', 192625: 'nyis_to_hq'})
    return w

def run():
    fit, z = demand_model(); print('HQ demand model:', fit)
    w = Q.frame(history=True).merge(z[['date', 'he', 't', 't_fc', 'hq', 'hq_fc']], on=['date', 'he'], how='left').merge(interchange(), on=['date', 'he'], how='left')
    w = w[w.date >= '2025-07-01'].copy(); w['mon'] = w.date.str[:7]
    out = dict(fit=fit)
    m = w.groupby('mon').agg(t=('t', 'mean'), hq=('hq', 'mean'), pq_exp=('pq_exp', 'mean'), hq_to_ne=('isne_to_hq', 'mean'), hq_to_ny=('nyis_to_hq', 'mean'), ny_hq=('ny_hq_lbmp', 'mean'),
                                e_basis=('east_da_basis', 'mean'), o_basis=('ottawa_da_basis', 'mean')).round(1)
    print(m.to_string()); out['monthly'] = m.reset_index().to_dict('records')
    c = w[['hq', 'pq_exp', 'pq_imp', 'isne_to_hq', 'nyis_to_hq', 'ny_hq_lbmp', 'east_da_basis', 'ottawa_da_basis', 'eo_da', 'da_ontario']].corr().round(2)
    print('\ncorrelations (hourly):'); print(c.loc[['hq', 'pq_exp', 'isne_to_hq', 'nyis_to_hq', 'ny_hq_lbmp']].to_string()); out['corr'] = c.to_dict()
    # daily: does Quebec demand pull more Ontario exports? (PQ.AT at its limit most hours -> expect little)
    dd = w.groupby('date').agg(hq=('hq', 'mean'), pq=('pq_exp', 'mean'), lim=('at_exp_lim', 'mean'), x_ne=('isne_to_hq', 'mean'), x_ny=('nyis_to_hq', 'mean')).dropna()
    b = np.polyfit(dd.hq / 1000, dd.pq, 1); out['pq_per_gw_hq'] = round(b[0]); print('\ndaily PQ exports vs HQ demand: +', round(b[0]), 'MW exported per GW of HQ demand, corr', round(dd.hq.corr(dd.pq), 2))
    b2 = np.polyfit(dd.hq / 1000, dd.x_ne + dd.x_ny, 1); out['hq_exports_ne_ny_per_gw'] = round(b2[0]); print('  HQ imports(+)/exports(-) with NE+NY per GW HQ demand:', round(b2[0]))
    # bid-time test: HQ demand forecast (pd2 temps) surprise vs trailing 7-day same-HE -> East/Ottawa DA forecast residual and DA-RT
    ww = w.sort_values(['date', 'he']).copy()
    base = ww.pivot_table(index='date', columns='he', values='hq').shift(2).rolling(7, min_periods=5).mean().stack().rename('hq7').reset_index()   # actual-temp demand, known by D-2
    ww = ww.merge(base, on=['date', 'he'], how='left'); ww['surp'] = (ww.hq_fc - ww.hq7) / 1000
    res = {}
    for zname in ('EAST', 'OTTAWA'):
        q = pd.read_csv(C.DATA / f'bt_quantiles_{zname}.csv')[['date', 'he', 'p_da', 'da']]
        f = pd.read_csv(C.DATA / f'dv_frame_{zname}.csv')[['date', 'he', 'sp', 'v2']]
        x = q.merge(f, on=['date', 'he']).merge(ww[['date', 'he', 'surp', 'hq_fc']], on=['date', 'he']).dropna(subset=['surp', 'da', 'p_da', 'sp'])
        x['res'] = x.da - x.p_da
        days = sorted(x.date.unique()); A, Bm = [], []
        for i, D in enumerate(days):
            if i < 60: continue
            tr = x[(x.date > days[i - 60]) & (x.date <= days[i - 2])]; te = x[x.date == D]
            F = lambda d: np.column_stack([np.ones(len(d)), d.surp]); M = F(tr)
            co = np.linalg.solve(M.T @ M + np.diag([0, 5.0]), M.T @ tr.res.values)
            A.append(te.res.abs().values); Bm.append((te.res - F(te) @ co).abs().values)
        A, Bm = np.concatenate(A), np.concatenate(Bm)
        x['sb'] = pd.cut(x.surp, [-99, -1, -.3, .3, 1, 99], labels=['< -1 GW', '-1..-0.3', '±0.3', '+0.3..+1', '> +1 GW'])
        by = x.groupby('sb').agg(sp=('sp', 'mean'), res=('res', 'mean'), h=('sp', 'size')).round(2)
        hi = x[x.surp > 1]; lo_, hi_ = FF.boot(hi.sp.values, hi.date.values) if len(hi) > 50 else (np.nan, np.nan)
        res[zname] = dict(mae=[round(A.mean(), 3), round(Bm.mean(), 3)], by=by.reset_index().astype({'sb': str}).to_dict('records'), cold_sp=[round(hi.sp.mean(), 2), round(lo_, 2), round(hi_, 2), len(hi)])
        print(f'\n{zname}: DA forecast MAE walk-forward {len(days)-60} d: model {A.mean():.3f} | + HQ demand surprise (bid-time) {Bm.mean():.3f}')
        print('  by HQ demand surprise (forecast vs last week, GW):'); print(by.to_string())
    out['bid'] = res
    e = ww.dropna(subset=['t_fc', 't']); out['temp_fc_mae_C'] = round((e.t_fc - e.t).abs().mean(), 2)
    (C.DATA / 'quebec2.json').write_text(json.dumps(out, default=float, indent=1)); print('-> quebec2.json; temp fc MAE', out['temp_fc_mae_C'], 'C')

if __name__ == '__main__': run()
