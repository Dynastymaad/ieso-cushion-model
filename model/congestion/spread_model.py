"""congestion/spread_model.py -- Oct 13 2026 (TEST ONLY). Can bid-time fundamentals predict (a) the RT zone split, (b) the DA split, (c) the UNPRICED part?
Walk-forward: train on all days before month M, test on month M. Nothing wired."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, nrg_import as N, warnings; warnings.filterwarnings('ignore')
from sklearn.ensemble import HistGradientBoostingRegressor as H
pd.set_option('display.width', 250)
d = pd.read_csv(C.DATA / 'nrg' / 'on_zones_nrg.csv.gz'); d['date'], d['he'] = N.to_key(d.ts_ept_begin)
d = d[d.date.ne('NaT') & d.he.notna()]; d['he'] = d.he.astype(int); d = d.drop_duplicates(['date', 'he'], keep='last')
d = d[(d.date >= '2025-05-03') & (d.date <= '2026-10-12')]
a = C.adq2('preDA')[['date', 'he', 'dem_fc', 'wind_fc', 'solar_fc', 'nuc_out', 'gas_out', 'nuc_av', 'gas_av', 'hyd_av', 'head']]
L = pd.read_csv(C.DATA / 'nrg' / 'nrg2_DA_INTERTIE_LIMITS.csv.gz')  # DA intertie limits (posted before DA; change-points -> ffill)
L['ts'] = pd.to_datetime(L.ts_ept_begin); L = L.set_index('ts').sort_index()
L = L[~L.index.duplicated(keep='last')].drop(columns='ts_ept_begin').resample('h').ffill().reset_index()
L['date'], L['he'] = N.to_key(L.ts.dt.strftime('%Y-%m-%d %H:%M')); L = L[L.he.notna()]; L['he'] = L.he.astype(int)
keep = ['LIM_MI_IMP', 'LIM_MI_EXP', 'LIM_NY_IMP', 'LIM_NY_EXP']; x2 = L[['date', 'he'] + keep].drop_duplicates(['date', 'he'])
d = d.merge(a, on=['date', 'he'], how='left').merge(x2, on=['date', 'he'], how='left')
dt = pd.to_datetime(d.date); d['mon'] = dt.dt.month; d['dow'] = dt.dt.dayofweek
FUND = ['he', 'mon', 'dow', 'dem_fc', 'wind_fc', 'solar_fc', 'nuc_out', 'gas_out', 'nuc_av', 'gas_av', 'hyd_av', 'head'] + keep
def prep(A, B='EAST'):
    x = d[['date', 'he'] + [c for c in FUND if c != 'he']].copy()
    x['da'] = d[A + '_DA'] - d[B + '_DA']; x['rt'] = d[A + '_RT'] - d[B + '_RT']; x['un'] = x.rt - x.da
    x['dt'] = pd.to_datetime(x.date)
    for col, lag, nm in (('da', 1, 'da_y'), ('rt', 2, 'rt_d2'), ('un', 2, 'un_d2')):
        y = x[['dt', 'he', col]].copy(); y['dt'] = y.dt + pd.Timedelta(days=lag); x = x.merge(y.rename(columns={col: nm}), on=['dt', 'he'], how='left')
    # 7-day mean unpriced through D-2, same hour
    p = x.pivot_table(index='dt', columns='he', values='un').shift(2).rolling(7, min_periods=3).mean().stack().rename('un_7d').reset_index()
    return x.merge(p, on=['dt', 'he'], how='left').dropna(subset=['da', 'rt'])
LAGS = ['da_y', 'rt_d2', 'un_d2', 'un_7d']
def walk(x, target, feats):
    x = x.copy(); x['ym'] = x.date.str[:7]; out = []
    for ym in sorted(x.ym.unique()):
        if ym < '2025-11': continue
        tr, te = x[x.ym < ym], x[x.ym == ym]
        m = H(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=1.0).fit(tr[feats], tr[target].clip(*tr[target].quantile([.01, .99])))
        out.append(te.assign(pred=m.predict(te[feats])))
    return pd.concat(out)
def r2(y, p): return 1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum()
for A in ('WEST', 'NIAG', 'SW'):
    x = prep(A); print(f'\n=================== {A} - EAST  (test Nov 2025 -> Oct 2026, walk-forward) ===================')
    res = {}
    for tgt in ('rt', 'da', 'un'):
        for nm, f in (('fundamentals only', FUND), ('fund + lags', FUND + LAGS)):
            t = walk(x, tgt, f); res[(tgt, nm)] = t
            big = t[tgt].abs() >= 5; hit = ((t.pred.abs() >= 5) & big).sum() / max(big.sum(), 1)
            print(f'predict {tgt:3s} [{nm:17s}] R2 {r2(t[tgt], t.pred):+.2f}  corr {t[[tgt, "pred"]].corr().iloc[0, 1]:+.2f}  | |{tgt}|>=5 hrs {big.mean()*100:4.1f}%, caught {hit*100:4.0f}%')
    t = res[('un', 'fund + lags')]
    print('  trade unpriced model (side = sign(pred) if |pred| >= thr):')
    for thr in (1, 2, 4):
        v = t[t.pred.abs() >= thr].assign(pl=lambda z: np.sign(z.pred) * z.un)
        if len(v) < 30: continue
        dd = v.groupby('date').pl.sum(); mm = v.groupby(v.date.str[:7]).pl.sum()
        print(f'    thr ${thr}: hrs {len(v):5d} $/MWh {v.pl.mean():+6.2f} med {v.pl.median():+5.2f} win {(v.pl>0).mean()*100:3.0f}% days+ {(dd>0).mean()*100:3.0f}% months+ {(mm>0).sum()}/{len(mm)} total/MW {v.pl.sum():+7.0f}')
    # what the RT-split model leans on (permutation importance on last test fold region)
    from sklearn.inspection import permutation_importance
    tr = x[x.date < '2026-06-01']; te = x[x.date >= '2026-06-01']
    m = H(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40).fit(tr[FUND], tr.rt.clip(*tr.rt.quantile([.01, .99])))
    pi = permutation_importance(m, te[FUND], te.rt, n_repeats=3, random_state=0)
    print('  RT-split drivers (importance, fundamentals model):', ', '.join(f'{c} {v:.2f}' for c, v in sorted(zip(FUND, pi.importances_mean), key=lambda z: -z[1])[:8]))
    x.to_csv(C.DATA / 'congestion' / f'model_{A}_EAST.csv', index=False)
