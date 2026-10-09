"""fund_read.py -- 'Fundamentals read' (Oct 9 2026): one number per hour = what a model of ALL bid-time fundamentals expects for
RT - DA ($/MWh; + = RT above DA = longs pay, - = sells pay). Lean version of all_hours.py that can run every morning from the
model's own frames (dv_frame + Dawn/FX for CAHR). No side preferred. Information only -- it places no orders.
  python model/fund_read.py --track     # walk-forward track record by segment -> data/fund_read_track.csv
  predict(target, bundle) is called by fund_panel.py for the live page (trained on all days through D-2)."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C
from sklearn.ensemble import HistGradientBoostingRegressor
FE = ['he', 'month', 'wkend', 'head', 'gas_hat', 'gas_av', 'spare', 'g1', 'g3', 'res_r3', 'dem_r1', 'wind_fc', 'wr3', 'wind_r1', 'solar_fc', 'solar_r1',
      'gas_out', 'nuc_out', 'hyd_exp', 'exp_exp', 'gapT', 'gapDyn', 'cahr', 'p_da', 'prem', 'nyx', 'bias7', 'bias14']
SEG = [(1, 6, 'overnight 1-6'), (7, 10, 'morning 7-10'), (11, 15, 'midday 11-15'), (16, 21, 'evening 16-21'), (22, 24, 'late 22-24')]
seg = lambda he: next(n for a, b, n in SEG if a <= he <= b)
_GAS = {}

def _cahr(e):
    import cahr as K
    miss = [d for d in e.date.unique() if d not in _GAS]
    if miss: _GAS.update(K.gas_table(miss))
    g = e.date.map(lambda d: _GAS[d][2]); cp = e.date.map(K.cprice)
    return K.hr(e.p_da, g, cp)

def feats(d):
    d = d.sort_values(['date', 'he']).copy(); g = d.groupby('date')
    d['spare'] = d.gas_av - d.gas_hat; d['g1'] = g.gas_hat.diff(); d['g3'] = g.gas_hat.diff(3)
    d['resid'] = d.dem_fc - d.nuc_av - d.wind_fc.fillna(0) - d.solar_fc.fillna(0); d['res_r3'] = d.groupby('date').resid.diff(3)
    d['dem_r1'] = g.dem_fc.diff(); d['wind_r1'] = g.wind_fc.diff(); d['wr3'] = g.wind_fc.diff(3); d['solar_r1'] = g.solar_fc.diff()
    d['gapT'] = d.lf_tesla - d.dem_fc; d['gapDyn'] = d.lf_dynasty - d.dem_fc; d['nyx'] = d.nyA_da - d.p_da; d['prem'] = d.p_da - d.p_rt
    d['month'] = pd.to_datetime(d.date).dt.month; d['cahr'] = _cahr(d); d['sp'] = d.da - d.rt
    return d

def _fit(tr):
    r = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.04, max_iter=300, min_samples_leaf=50, l2_regularization=2.0, random_state=0)
    return r.fit(tr[FE], tr.sp.clip(-60, 60))

def predict(D, bundle):
    """{zone: {he: predicted DA-RT}} for target D; the target rows use the live bundle's gas need (signals_v2) and forecasts."""
    out = {}
    for z in ('EAST', 'OTTAWA'):
        d = pd.read_csv(C.DATA / f'dv_frame_{z}.csv'); H = {h['he']: h for h in bundle['hubs'][z]['hours']}
        t = d.date == D
        for c, k in (('gas_hat', 'gas_hat'), ('p_da', 'p_da'), ('p_rt', 'p_rt'), ('head', 'head')):
            d.loc[t, c] = d.loc[t, 'he'].map(lambda h: H.get(int(h), {}).get(k)).astype(float)
        f = feats(d); cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
        tr = f[(f.date <= cut) & f.sp.notna() & (f.date >= '2025-06-01')]; te = f[f.date == D]
        if te.empty: continue
        out[z] = dict(zip(te.he.astype(int), np.round(-_fit(tr).predict(te[FE]), 1)))     # stored as RT - DA (+ = longs)
    return out

def track():
    rows = []
    for z in ('EAST', 'OTTAWA'):
        f = feats(pd.read_csv(C.DATA / f'dv_frame_{z}.csv')); f['pred'] = np.nan
        for M in pd.period_range('2025-10', '2026-10', freq='M'):
            cut = (M.start_time - pd.Timedelta(days=2)).date().isoformat(); te = (f.date >= M.start_time.date().isoformat()) & (f.date <= M.end_time.date().isoformat()) & f.sp.notna()
            tr = f[(f.date <= cut) & f.sp.notna() & (f.date >= '2025-06-01')]
            if te.any(): f.loc[te, 'pred'] = _fit(tr).predict(f.loc[te, FE])
        o = f[f.pred.notna()].copy(); o['seg'] = o.he.map(seg)
        for s in [n for _, _, n in SEG] + ['ALL']:
            x = o if s == 'ALL' else o[o.seg == s]
            for k in (0, 5, 10):
                y = x[x.pred.abs() >= k]; pl = np.sign(y.pred) * y.sp
                rows.append(dict(zone=z, seg=s, min_read=k, hours=len(y), right_side_pct=round((pl > 0).mean() * 100), usd_mwh=round(pl.mean(), 1),
                                 H1=round(pl[y.date < '2026-02-15'].mean(), 1), H2=round(pl[y.date >= '2026-02-15'].mean(), 1), last90=round(pl[y.date >= '2026-07-08'].mean(), 1)))
    R = pd.DataFrame(rows); R.to_csv(C.DATA / 'fund_read_track.csv', index=False); return R

if __name__ == '__main__' and '--track' in sys.argv:
    pd.set_option('display.width', 220); print(track().to_string(index=False))
