"""shock_predict.py -- Oct 8 2026: can bid-time data predict the after-bid surprises (after_bid.py)?
For each surprise: rank correlation with candidate bid-time predictors, and a walk-forward ridge forecast (monthly refit,
trained through first-of-month - 2 days) -> out-of-sample R^2 and how well the predicted top 10% catch real big shocks."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 250)
m = pd.read_csv(C.DATA / 'after_bid_EAST.csv').sort_values(['date', 'he']).reset_index(drop=True)
w = C.load_forecasts_at_bid()[['date', 'he', 'lf_ieso']]; m = m.drop(columns=['lf_ieso'], errors='ignore').merge(w, on=['date', 'he'], how='left')
m['nyx'] = m.nyA_da - m.p_da; m['gapT'] = m.lf_tesla - m.dem_fc; m['gapDyn'] = m.lf_dynasty - m.dem_fc
m['lf_sd'] = m[['dem_fc', 'lf_tesla', 'lf_dynasty', 'lf_ieso']].std(axis=1); m['lf_rng'] = m[['dem_fc', 'lf_tesla', 'lf_dynasty', 'lf_ieso']].max(1) - m[['dem_fc', 'lf_tesla', 'lf_dynasty', 'lf_ieso']].min(1)
m['blk'] = pd.cut(m.he, [0, 6, 14, 18, 22, 24], labels=False)
# trailing (D-8..D-2) means of realised surprises, same HE block -- known at the bid
dd = m.groupby(['date', 'blk'])[['load_miss', 'wind_miss', 'surp', 'tie_miss']].mean().reset_index(); dd['dt'] = pd.to_datetime(dd.date)
for c in ('load_miss', 'wind_miss', 'surp', 'tie_miss'):
    s = dd.pivot(index='dt', columns='blk', values=c).sort_index()
    tr = s.shift(2, freq='D').reindex(s.index).rolling(7, min_periods=3).mean() if False else s.rolling('7D').mean().shift(2, freq='D').reindex(s.index)
    tr = tr.stack().rename(f'{c}_tr7').reset_index(); tr['date'] = tr.dt.dt.date.astype(str); m = m.merge(tr[['date', 'blk', f'{c}_tr7']], on=['date', 'blk'], how='left')
m['net_exp_da'] = m.exp_da.abs() - m.imp_da.abs()
P = {'load_miss': ['gapT', 'tvu', 'gapDyn', 'lf_sd', 'lf_rng', 'load_miss_tr7', 'dem_fc', 'he', 'wkend', 'month'],
     'wind_miss': ['w_nwp_sd', 'w_gap_nwp', 'w_gap_min', 'wind_fc', 'wr3', 'wind_miss_tr7', 'he', 'month'],
     'surp': ['surp_tr7', 'gas_hat', 'gas_av', 'gas_out', 'gas_out_p', 'head', 'he', 'month', 'wkend'],
     'tie_miss': ['tie_miss_tr7', 'nyx', 'head', 'he', 'month']   # Oct 8: DA intertie schedules removed -- they are set by the DA run itself (not known at the bid)}
t = m[(m.date >= '2025-09-01') & (m.date <= '2026-10-06')].copy()
for y, F in P.items():
    print(f'\n---- {y}: rank correlation with bid-time predictors (|0.1| = weak, |0.3| = useful)')
    print(t[F + [y]].corr(method='spearman')[y].drop(y).round(3).sort_values(key=abs, ascending=False).to_dict())
    t[f'{y}_hat'] = np.nan
    for M in pd.period_range('2025-11', '2026-10', freq='M'):
        cut = (M.start_time - pd.Timedelta(days=2)).date().isoformat(); te = (t.date >= M.start_time.date().isoformat()) & (t.date <= M.end_time.date().isoformat())
        tr = t[(t.date <= cut)].dropna(subset=[y])
        if len(tr) < 1000 or not te.any(): continue
        mu, sd = tr[F].mean(), tr[F].std().replace(0, 1); X = ((tr[F] - mu) / sd).fillna(0).values; X = np.c_[np.ones(len(X)), X]
        R = np.eye(X.shape[1]) * 50; R[0, 0] = 0; b = np.linalg.solve(X.T @ X + R, X.T @ tr[y].values)
        Xt = np.c_[np.ones(te.sum()), ((t.loc[te, F] - mu) / sd).fillna(0).values]; t.loc[te, f'{y}_hat'] = Xt @ b
    q = t.dropna(subset=[y, f'{y}_hat']); r2 = 1 - ((q[y] - q[f'{y}_hat']) ** 2).sum() / ((q[y] - q[y].mean()) ** 2).sum()
    big = q[y] >= q[y].quantile(.9) if y != 'wind_miss' else q[y] <= q[y].quantile(.1)
    pk = q[f'{y}_hat'] >= q[f'{y}_hat'].quantile(.9) if y != 'wind_miss' else q[f'{y}_hat'] <= q[f'{y}_hat'].quantile(.1)
    print(f'   walk-forward out-of-sample R^2 {r2:+.3f} | of hours predicted in the worst 10%, {big[pk].mean()*100:.0f}% really were (random = 10%) | spike rate in them {q[pk].spk.mean()*100:.1f}% vs {q.spk.mean()*100:.1f}% base')
t.to_csv(C.DATA / 'shock_predict_EAST.csv', index=False)
