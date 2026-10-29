"""research/rt_read_test.py -- Oct 28 2026 (TEST ONLY). Can the RT P50 read get more accurate?
RT read = model DA forecast (p_da) + predicted RT-DA. Walk-forward weekly from Jul 6 2026, trained on days through D-2.
Variants: base fundamentals read; + Meteologica load/wind gaps and gas-need miss bias; median (absolute) loss; recency weights."""
import sys, json, warnings, time; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, fund_read as FR, supply_fc as S
from sklearn.ensemble import HistGradientBoostingRegressor
pd.set_option('display.width', 220)
ZONE = sys.argv[1] if len(sys.argv) > 1 else 'EAST'
VARS = sys.argv[2].split(',') if len(sys.argv) > 2 else ['base', 'plus', 'plus_med', 'plus_med_w']

def frame():
    f = FR.feats(pd.read_csv(C.DATA / f'dv_frame_{ZONE}.csv'))
    L = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'lf_meteologica']]
    W = S.wind_at_bid()[['date', 'he', 'wf_meteologica']]
    G = C.fuel_actual()[['date', 'he', 'g_gas']]
    f = f.merge(L, on=['date', 'he'], how='left').merge(W, on=['date', 'he'], how='left').merge(G, on=['date', 'he'], how='left')
    f['met_lgap'] = f.lf_meteologica - f.dem_fc; f['met_wgap'] = f.wf_meteologica - f.wind_fc
    f['shift'] = f.met_lgap - f.met_wgap
    x = f.pivot_table(index='date', columns='he', values='g_gas') - f.pivot_table(index='date', columns='he', values='gas_hat')
    x.index = pd.to_datetime(x.index); x = x.asfreq('D').shift(2).rolling(30, min_periods=10).mean()
    b = x.stack().rename('gmiss30').reset_index(); b['date'] = b.date.dt.strftime('%Y-%m-%d')
    f = f.merge(b, on=['date', 'he'], how='left'); f['spare_c'] = f.spare - f.gmiss30.fillna(0)
    return f[f.rt.notna() & f.da.notna()].copy()

PLUS = FR.FE + ['met_lgap', 'met_wgap', 'shift', 'gmiss30', 'spare_c']
def fit(tr, fe, loss, w, direct=False):
    r = HistGradientBoostingRegressor(loss=loss, max_depth=3, learning_rate=0.04, max_iter=300, min_samples_leaf=50, l2_regularization=2.0, random_state=0)
    sw = None
    if w:
        age = (pd.Timestamp(tr.date.max()) - pd.to_datetime(tr.date)).dt.days.values; sw = 0.5 ** (age / 90)
    y = (tr.rt - tr.p_da).clip(-80, 150) if direct else (tr.rt - tr.da).clip(-60, 60)
    return r.fit(tr[fe], y, sample_weight=sw)

f = frame(); cfg = {'base': (FR.FE, 'squared_error', False), 'plus': (PLUS, 'squared_error', False), 'plus_med': (PLUS, 'absolute_error', False),
                    'plus_med_w': (PLUS, 'absolute_error', True), 'base_med': (FR.FE, 'absolute_error', False), 'base_w': (FR.FE, 'squared_error', True),
                    'direct_med': (PLUS, 'absolute_error', False, True), 'direct_sq': (PLUS, 'squared_error', False, True)}
for v in VARS: f[v] = np.nan
t0 = time.time()
for s in pd.date_range('2026-07-06', f.date.max(), freq='7D'):
    s0 = s.date().isoformat(); e = (s + pd.Timedelta(days=6)).date().isoformat(); cut = (s - pd.Timedelta(days=2)).date().isoformat()
    te = (f.date >= s0) & (f.date <= e); tr = f[(f.date <= cut) & (f.date >= '2025-06-01')]
    for v in VARS:
        c = cfg[v]; f.loc[te, v] = fit(tr, c[0], c[1], c[2], len(c) > 3).predict(f.loc[te, c[0]])
t = f[f.date >= '2026-07-06'].dropna(subset=VARS).copy(); days = sorted(t.date.unique())
rows = []
for v in ['DA fc only'] + VARS:
    read = t.p_da if v == 'DA fc only' else t.p_da + t[v]; e_ = read - t.rt
    for per, m in (('Jul 6 - Oct 27', t.date >= '0'), ('Oct', t.date >= '2026-10-01'), ('last 14 d', t.date >= days[-14])):
        r = dict(variant=v, period=per, hours=int(m.sum()), mae=round(e_[m].abs().mean(), 2), median_ae=round(e_[m].abs().median(), 1), bias=round(e_[m].mean(), 1),
                 within_10=round((e_[m].abs() <= 10).mean() * 100))
        if v != 'DA fc only':
            g = t[v][m]; k = g.abs() >= 5; pl = np.sign(g[k]) * (t.rt - t.da)[m][k]
            r.update(sign_hit=round((np.sign(g) == np.sign((t.rt - t.da)[m])).mean() * 100), trade_hours=int(k.sum()), trade_usd=round(pl.mean(), 2))
        rows.append(r)
R = pd.DataFrame(rows); R.to_csv(C.DATA / 'research' / f'rt_read_{ZONE}.csv', index=False); print(R.to_string(index=False)); print(f'{time.time()-t0:.0f}s')
t[['date', 'he', 'rt', 'da', 'p_da'] + VARS].to_csv(C.DATA / 'research' / f'rt_read_preds_{ZONE}.csv', index=False)
