"""block_test.py -- walk-forward test of the DA level model on 500 days of
settled daily on-peak DA (weekdays), using the Adequacy2 pre-deadline vintage."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import common as C, pandas as pd, numpy as np
a = C.adq2('preDA'); b = C.daily_blocks()
f = pd.read_csv(C.CACHE / 'fwd_daily_ontario.csv', parse_dates=['EffectiveDate', 'Strip'])
g = f[(f.ExchangeCode == 'CVX') & ((f.Strip - f.EffectiveDate).dt.days >= 2)].sort_values('EffectiveDate').groupby('Strip').Price.last()
gas = g.rename('dawn').reset_index(); gas['date'] = gas.Strip.dt.date.astype(str)
on = a[a.he.between(7, 22)].groupby('date').agg(hd=('head', 'mean'), dem=('dem_fc', 'mean'), nuc=('nuc_av', 'mean'),
                                                 wind=('wind_fc', 'mean'), gasav=('gas_av', 'mean'), hydav=('hyd_av', 'mean')).reset_index()
d = b.merge(on, on='date').merge(gas[['date', 'dawn']], on='date', how='left')
d['dow'] = pd.to_datetime(d.date).dt.dayofweek
d = d[(d.dow < 5) & d.da_on.notna() & d.hd.notna()].sort_values('date').reset_index(drop=True)
d['dawn'] = d.dawn.ffill().bfill(); d['m'] = d.date.str.slice(0, 7)
print(len(d), d.date.min(), d.date.max())
print(d.groupby('m').agg(n=('da_on', 'size'), da_on=('da_on', 'mean'), da_min=('da_on', 'min'), headroom=('hd', 'mean'),
                         demand=('dem', 'mean'), nuclear=('nuc', 'mean'), wind=('wind', 'mean'), dawn=('dawn', 'mean')).round(1).to_string())
res = []
for W in (20, 40, 60):
    for i in range(W, len(d)):
        tr, te = d.iloc[i - W:i], d.iloc[i]
        X = np.c_[np.ones(W), tr.hd / 1000]; y = np.log(tr.da_on.clip(lower=3))
        bb = np.linalg.lstsq(X, y, rcond=None)[0]; p = np.exp(bb[0] + bb[1] * te.hd / 1000)
        y3 = np.log(tr.da_on.clip(lower=3) / tr.dawn); b3 = np.linalg.lstsq(X, y3, rcond=None)[0]
        p3 = te.dawn * np.exp(b3[0] + b3[1] * te.hd / 1000)
        res.append((W, te.date, te.da_on, p, p3, d.iloc[i - 1].da_on))
r = pd.DataFrame(res, columns=['W', 'date', 'y', 'headroom', 'heatrate', 'persist'])
for W, g in r.groupby('W'):
    print('window', W, 'days n', len(g), {k: round((g[k] - g.y).abs().mean(), 2) for k in ['headroom', 'heatrate', 'persist']})
g = r[r.W == 40].copy(); g['m'] = g.date.str.slice(0, 7)
print(g.groupby('m').apply(lambda x: pd.Series({'n': len(x), 'DA_on': x.y.mean(), 'model_MAE': (x.headroom - x.y).abs().mean(),
      'heatrate_MAE': (x.heatrate - x.y).abs().mean(), 'persist_MAE': (x.persist - x.y).abs().mean()}), include_groups=False).round(1).to_string())
r.to_csv(C.DATA / 'block_test.csv', index=False)

# ---- delta model: anchor on the last settled DA, move it by the change in fundamentals
d['lp'] = np.log(d.da_on.clip(lower=3)); d['dlp'] = d.lp.diff(); d['dhd'] = d.hd.diff() / 1000
d['dgas'] = np.log(d.dawn).diff(); d['ddem'] = d.dem.diff() / 1000
res2 = []
for W in (40, 60, 120):
    for i in range(W + 1, len(d)):
        tr, te = d.iloc[i - W:i].dropna(subset=['dlp', 'dhd', 'dgas']), d.iloc[i]
        for name, cols in (('d_head', ['dhd']), ('d_head_gas', ['dhd', 'dgas'])):
            X = np.c_[tr[cols].values]; bb = np.linalg.lstsq(X, tr.dlp, rcond=None)[0]
            p = np.exp(d.iloc[i - 1].lp + (te[cols].values * bb).sum())
            res2.append((W, name, te.date, te.da_on, p, d.iloc[i - 1].da_on))
r2 = pd.DataFrame(res2, columns=['W', 'model', 'date', 'y', 'p', 'persist'])
for (W, mname), g in r2.groupby(['W', 'model']):
    print('delta', mname, 'W', W, 'n', len(g), 'MAE', round((g.p - g.y).abs().mean(), 2), 'persist', round((g.persist - g.y).abs().mean(), 2),
          'share of days better', round(((g.p - g.y).abs() < (g.persist - g.y).abs()).mean(), 2))
g = r2[(r2.W == 60) & (r2.model == 'd_head_gas')].copy(); g['m'] = g.date.str.slice(0, 7)
print(g.groupby('m').apply(lambda x: pd.Series({'n': len(x), 'DA_on': x.y.mean(), 'delta_MAE': (x.p - x.y).abs().mean(),
      'persist_MAE': (x.persist - x.y).abs().mean()}), include_groups=False).round(1).to_string())
