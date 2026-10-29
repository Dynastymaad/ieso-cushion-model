"""rt_read.py -- Oct 28 2026. RT P50 read per hour for the Fundamentals tab (display only, no effect on the ladders).
RT P50 = DA forecast + predicted RT - DA from all bid-time fundamentals (fund_read features + Meteologica load / wind gaps
vs IESO + trailing 30-day gas-need miss), median (absolute-error) loss so it targets the typical hour, not the spikes.
P10 / P90 from quantile models on the same features. Trained each morning on every settled day through D-2.
Walk-forward test Jul 6 - Oct 27 2026 (model/research/rt_read_test.py, East): MAE $18.2 vs $20.5 for 'RT = DA forecast',
RT-vs-DA direction right 63%; P10-P90 held the actual RT 78% of hours. Ottawa the same within $1.
Also: 'spare adj' = gas spare corrected by the trailing 30-day miss of gas need vs gas that actually ran (through D-2);
recal_test.py: need error 808 -> 528 MW over the last 14 days. Each morning's read is logged to data/rt_read_log.csv."""
import sys, json, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, fund_read as FR, supply_fc as S
from sklearn.ensemble import HistGradientBoostingRegressor as HGB
FE = FR.FE + ['met_lgap', 'met_wgap', 'shift', 'gmiss30', 'spare_c']
LOG = C.DATA / 'rt_read_log.csv'
J = lambda v, k=1: None if v is None or pd.isna(v) else round(float(v), k)

def _gmiss(f):
    x = f.pivot_table(index='date', columns='he', values='g_gas') - f.pivot_table(index='date', columns='he', values='gas_hat')
    x.index = pd.to_datetime(x.index); x = x.asfreq('D').shift(2).rolling(30, min_periods=10).mean()
    b = x.stack().rename('gmiss30').reset_index(); b['date'] = b.date.dt.strftime('%Y-%m-%d'); return b

def frame(zone, D, bundle):
    d = pd.read_csv(C.DATA / f'dv_frame_{zone}.csv'); H = {h['he']: h for h in bundle['hubs'][zone]['hours']}; t = d.date == D
    for c in ('gas_hat', 'p_da', 'p_rt', 'head'):
        d.loc[t, c] = d.loc[t, 'he'].map(lambda h: H.get(int(h), {}).get(c)).astype(float)
    f = FR.feats(d)
    L = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'lf_meteologica']]; W = S.wind_at_bid()[['date', 'he', 'wf_meteologica']]
    G = C.fuel_actual()[['date', 'he', 'g_gas']]
    f = f.merge(L, on=['date', 'he'], how='left').merge(W, on=['date', 'he'], how='left').merge(G, on=['date', 'he'], how='left')
    f['met_lgap'] = f.lf_meteologica - f.dem_fc; f['met_wgap'] = f.wf_meteologica - f.wind_fc; f['shift'] = f.met_lgap - f.met_wgap
    gm = _gmiss(f[f.date < D]); f = f.merge(gm, on=['date', 'he'], how='left')
    if f.loc[f.date == D, 'gmiss30'].isna().all():                      # target day: same trailing value (D-2 window end)
        last = gm[gm.date == gm.date.max()].set_index('he').gmiss30; f.loc[f.date == D, 'gmiss30'] = f.loc[f.date == D, 'he'].map(last)
    f['spare_c'] = f.spare - f.gmiss30.fillna(0)
    return f

def _m(loss, q=None):
    kw = dict(loss=loss, max_depth=3, learning_rate=0.04, max_iter=300, min_samples_leaf=50, l2_regularization=2.0, random_state=0)
    if q is not None: kw['quantile'] = q
    return HGB(**kw)

def spare_adj(D):
    """trailing 30-day mean of (gas that ran - displayed gas need) by HE, through D-2, from the saved bid-time reads."""
    h = json.loads((C.DATA / 'fund_history.json').read_text())
    f = pd.DataFrame([dict(date=k, **x) for k, v in h.items() for x in v])[['date', 'he', 'need']]
    f = f.merge(C.fuel_actual()[['date', 'he', 'g_gas']], on=['date', 'he'])
    c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=32)).date().isoformat()
    w = f[(f.date <= c2) & (f.date > lo)]; return (w.g_gas - w.need).groupby(w.he).mean(), int(w.date.nunique())

def build(D, bundle):
    out = {'date': D, 'hubs': {}}
    for z in ('EAST', 'OTTAWA'):
        f = frame(z, D, bundle); c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
        tr = f[(f.date <= c2) & (f.date >= '2025-06-01') & f.rt.notna() & f.da.notna()]; te = f[f.date == D].sort_values('he')
        if te.empty: continue
        y = (tr.rt - tr.da).clip(-60, 150)
        p50 = _m('absolute_error').fit(tr[FE], y.clip(-60, 60)).predict(te[FE])
        p10 = _m('quantile', .1).fit(tr[FE], y).predict(te[FE]); p90 = _m('quantile', .9).fit(tr[FE], y).predict(te[FE])
        base = te.p_da.values; rows = []
        for i, he in enumerate(te.he.astype(int)):
            lo_, hi_ = sorted([base[i] + p10[i], base[i] + p90[i]]); mid = min(max(base[i] + p50[i], lo_), hi_)
            rows.append(dict(he=he, da_fc=J(base[i]), rt_p50=J(mid), rt_p10=J(lo_), rt_p90=J(hi_), rt_minus_da=J(mid - base[i])))
        out['hubs'][z] = rows
    try:
        adj, n = spare_adj(D); prac = {r['he']: r for r in bundle.get('fund', {}).get('prac', {}).get('rows', [])}
        out['spare_adj'] = {int(he): dict(miss=J(adj.get(he), 0), sp=prac.get(he, {}).get('sp'),
                                          sp_adj=None if prac.get(he, {}).get('sp') is None or pd.isna(adj.get(he)) else int(round(prac[he]['sp'] - adj.get(he))))
                            for he in range(1, 25)}
        out['spare_days'] = n
    except Exception as ex: out['spare_err'] = str(ex)
    _log(D, out); out['track'] = track(D)
    return out

def _log(D, out):
    rows = [dict(date=D, zone=z, **r) for z, rs in out['hubs'].items() for r in rs]
    if not rows: return
    new = pd.DataFrame(rows)
    old = pd.read_csv(LOG) if LOG.exists() else pd.DataFrame()
    if len(old): old = old[~((old.date == D))]
    pd.concat([old, new]).to_csv(LOG, index=False)

def track(D):
    """live record of the logged reads vs settled prices (East), plus the walk-forward test numbers."""
    res = {'test': dict(period='Jul 6 - Oct 27 2026 (walk-forward)', mae=18.2, mae_da_only=20.5, within10=48, direction=63, cover=78)}
    if not LOG.exists(): return res
    l = pd.read_csv(LOG); l = l[(l.zone == 'EAST') & (l.date < D)]
    p = C.prices('EAST')[['date', 'he', 'da', 'rt']]; m = l.merge(p, on=['date', 'he']).dropna(subset=['rt', 'da'])
    if len(m):
        e = m.rt_p50 - m.rt
        res['live'] = dict(days=int(m.date.nunique()), hours=len(m), mae=J(e.abs().mean()), within10=int(round((e.abs() <= 10).mean() * 100)),
                           direction=int(round((np.sign(m.rt_minus_da) == np.sign(m.rt - m.da)).mean() * 100)),
                           cover=int(round(((m.rt >= m.rt_p10) & (m.rt <= m.rt_p90)).mean() * 100)))
    return res

if __name__ == '__main__':
    b = json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text()); r = build(b['target'], b)
    for x in r['hubs']['EAST']: print(x)
    print(r.get('spare_adj', {}).get(17), r.get('spare_days'), r['track'])
