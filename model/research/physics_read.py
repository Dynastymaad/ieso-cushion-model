"""STEP 2 - read every hour from the physics, walk-forward (weights refit weekly on 2026 data through D-2), trade every hour 1 MW.
V1 expected shock only (load + wind surprise we can see coming)       V2 V1 scaled by how much spare there is to absorb it + what DA priced
V3 V2 + ramps, recent IESO bias, wind downside, NY pull              V4 V3 with interactions learned by trees (same inputs)"""
import pandas as pd, numpy as np, sys
from sklearn.linear_model import Ridge; from sklearn.ensemble import HistGradientBoostingRegressor as HGB
z = sys.argv[1] if len(sys.argv) > 1 else 'EAST'
e = pd.read_csv('data/research/physics_EAST.csv')[['date', 'he', 'bias_L', 'bias_W']]
p = pd.read_csv(f'data/research/stress_{z}_extra.csv'); p['rd'] = p.rt - p.da
e = p.merge(e, on=['date', 'he'], how='left').sort_values(['date', 'he']).reset_index(drop=True)
e = e[(e.date >= '2026-01-01') & e.rd.notna() & e.gas_hat.notna() & e.vs.notna()].copy()
nw = [c for c in e if c.startswith('wf_') and c != 'wf_meteologica']
e['gap_meteo_L'] = e.lf_meteologica - e.dem_fc; e['gap_tesla_L'] = e.lf_tesla - e.dem_fc
e['gap_meteo_W'] = e.wind_fc - e.wf_meteologica; e['gap_models_W'] = e.wind_fc - e.w_models; e['gap_low_W'] = e.wind_fc - e[nw].min(axis=1)
e['gL'] = e.gap_meteo_L.fillna(e.gap_tesla_L).fillna(0); e['gW'] = e.gap_meteo_W.fillna(e.gap_models_W).fillna(0)
e['inv_sp'] = 1000 / e.pub_sp.clip(lower=500); e['rich'] = (e.vs - 18).clip(lower=0); e['cheap'] = (-5 - e.vs).clip(lower=0)
e['ny_pull'] = e.nyA_da - e.p_da; e['wk'] = e.wkend.astype(float); e['blk'] = pd.cut(e.he, [0, 6, 8, 15, 19, 22, 24], labels=False)
for c in ['bias_L', 'bias_W', 'w3', 'g3', 'res3', 'gap_low_W', 'w_spread', 'inv_sp', 'pub_sp', 'ny_pull']: e[c] = e[c].fillna(e[c].median() if c in ('pub_sp','inv_sp','ny_pull') else 0)
V = {'V1': ['gL', 'gW'],
     'V2': ['gL', 'gW', 'inv_sp', 'xL', 'xW', 'vs', 'rich', 'cheap'],
     'V3': ['gL', 'gW', 'inv_sp', 'xL', 'xW', 'vs', 'rich', 'cheap', 'bias_L', 'bias_W', 'w3', 'g3', 'res3', 'gap_low_W', 'w_spread', 'ny_pull', 'pub_sp', 'wk', 'blk'],
}
V['V4'] = V['V3']; V['V5'] = V['V3']; V['V6'] = V['V3']
V['V7'] = V['V3'] + ['iWR', 'wup', 'iLR']   # V7 = V5 (90 days) + wind gap x wind ramp, wind arriving, load gap x evening   # V5 = V3 on trailing 90 days only; V6 = V3 fit separately per block of the day
e['xL'] = e.gL * e.inv_sp; e['xW'] = e.gW * e.inv_sp
e['wup'] = e.w3.clip(lower=0); e['iWR'] = (e.gW / 200) * (e.w3 / 200); e['iLR'] = e.gL * e.he.between(17, 22)
ONLY = sys.argv[2].split(',') if len(sys.argv) > 2 else None
if ONLY: V = {k: v for k, v in V.items() if k in ONLY}
weeks = pd.date_range('2026-03-02', e.date.max(), freq='7D')
for v, F in V.items():
    e[v] = np.nan
    for s in weeks:
        s0 = s.strftime('%Y-%m-%d'); s1 = (s + pd.Timedelta(days=6)).strftime('%Y-%m-%d'); cut = (s - pd.Timedelta(days=2)).strftime('%Y-%m-%d')
        tr = e[e.date <= cut]; te = (e.date >= s0) & (e.date <= s1)
        if te.sum() == 0: continue
        if v in ('V5', 'V7'): tr = tr[tr.date > (s - pd.Timedelta(days=92)).strftime('%Y-%m-%d')]
        if v == 'V6':
            for b in range(6):
                tb = tr[tr.blk == b]; kb = te & (e.blk == b); X, y = tb[F].values, tb.rd.clip(-80, 150).values; mu, sd = X.mean(0), X.std(0) + 1e-9
                if kb.sum(): e.loc[kb, v] = Ridge(alpha=50).fit((X - mu) / sd, y).predict((e.loc[kb, F].values - mu) / sd)
            continue
        X, y = tr[F].values, tr.rd.clip(-80, 150).values
        if v == 'V4': m = HGB(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=60).fit(X, y); e.loc[te, v] = m.predict(e.loc[te, F].values)
        else:
            mu, sd = X.mean(0), X.std(0) + 1e-9; m = Ridge(alpha=50).fit((X - mu) / sd, y); e.loc[te, v] = m.predict((e.loc[te, F].values - mu) / sd)
t = e[e.date >= '2026-03-02'].copy(); t['m'] = t.date.str[:7]
print(f'===== {z}: every hour read, {t.date.min()}..{t.date.max()} ({len(t)} h). short-all ${-t.rd.mean():+.2f}/MWh, long-all ${t.rd.mean():+.2f}')
for v in V:
    c = t[v] - t[v].groupby(t.date).transform(lambda s: 0)  # raw read
    side = np.sign(t[v]); pnl = side * t.rd; mo = pnl.groupby(t.m).mean()
    q = pd.qcut(t[v].rank(method='first'), 5, labels=False); qq = t.rd.groupby(q).mean().round(1).tolist()
    big = t[v].abs() >= t[v].abs().quantile(.5); pb = (side * t.rd)[big]
    print(f'{v}: all hours ${pnl.mean():+.2f}/MWh hit {(pnl>0).mean():.0%} months+ {(mo>0).sum()}/{len(mo)} | stronger half of reads ${pb.mean():+.2f} hit {(pb>0).mean():.0%} | RT-DA by read quintile {qq} | long share {(side>0).mean():.0%}')
    print('     by month $/MWh', mo.round(1).to_dict())
    xj = pnl[t.m != '2026-07']; sz = (t[v].abs() / t[v].abs().rolling(500, min_periods=50).median().shift(24)).clip(0, 2).fillna(1); ps = side * sz * t.rd
    print(f'     ex-July ${xj.mean():+.2f} hit {(xj>0).mean():.0%} | Mar-Jun ${pnl[t.date<"2026-07"].mean():+.2f} Jul-Oct ${pnl[t.date>="2026-07"].mean():+.2f} | sized by conviction ${ps.sum()/sz.sum():+.2f}/MWh | valley HE9-15 ${pnl[t.he.between(9,15)].mean():+.2f} peak HE16-19 ${pnl[t.he.between(16,19)].mean():+.2f}')
t.to_csv(f'data/research/physics_read_{z}.csv', index=False)
o = t[t.date == '2026-10-31'][['he', 'gL', 'gW', 'pub_sp', 'vs'] + list(V) + ['rd']]
V['V3'] = ['gL', 'gW', 'inv_sp', 'xL', 'xW', 'vs', 'rich', 'cheap', 'bias_L', 'bias_W', 'w3', 'g3', 'res3', 'gap_low_W', 'w_spread', 'ny_pull', 'pub_sp', 'wk', 'blk']
print('Oct 31:'); print(o.round(1).to_string(index=False))
print('\nV5 weights ($/MWh RT-DA per one typical move of each input; intercept = recent average RT-DA), fit as of:')
F = V['V3']; W = {}
for s in ['2026-04-01', '2026-06-01', '2026-08-01', '2026-10-31']:
    S_ = pd.Timestamp(s); tr = e[(e.date <= (S_ - pd.Timedelta(days=2)).strftime('%Y-%m-%d')) & (e.date > (S_ - pd.Timedelta(days=92)).strftime('%Y-%m-%d'))]
    X = tr[F].values; mu, sd = X.mean(0), X.std(0) + 1e-9; m = Ridge(alpha=50).fit((X - mu) / sd, tr.rd.clip(-80, 150)); W[s] = list(m.coef_) + [m.intercept_]
print(pd.DataFrame(W, index=F + ['intercept']).round(1).to_string())
