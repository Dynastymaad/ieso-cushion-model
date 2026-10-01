"""da_hourly_test.py -- walk-forward DA tests, Toronto hub, every input as it stood
at the bid deadline. Variants are added one idea at a time so each can be judged."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import common as C, pandas as pd, numpy as np
ZONE = sys.argv[1] if len(sys.argv) > 1 else 'TORONTO'
p = C.prices(ZONE)[['date', 'he', 'da', 'rt']]
a = C.adq2('preDA')[['date', 'he', 'head', 'dem_fc', 'resid_fc', 'gas_av', 'hyd_av', 'nuc_av', 'wind_fc']]
ny = pd.read_csv(C.DATA / 'nyiso_zoneA_da.csv'); dni = pd.read_csv(C.DATA / 'nyiso_p30_dni_oh_sample.csv')
L = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'lf_tesla', 'lf_adq2']]
d = p.merge(a, on=['date', 'he']).merge(ny, on=['date', 'he'], how='left').merge(dni, on=['date', 'he'], how='left').merge(L, on=['date', 'he'], how='left')
d = d.dropna(subset=['da', 'head']).sort_values(['date', 'he']).reset_index(drop=True)
d['blk'] = pd.cut(d.he, [0, 6, 10, 16, 21, 24], labels=False)
d['dow'] = pd.to_datetime(d.date).dt.dayofweek; d['wkend'] = (d.dow >= 5).astype(int)
# yesterday (D-1) same hour: known at bid time (published on D-2)
prev = d[['date', 'he', 'da', 'head', 'ny_dni_oh', 'nyA_da']].copy(); prev['date'] = (pd.to_datetime(prev.date) + pd.Timedelta(days=1)).dt.date.astype(str)
d = d.merge(prev, on=['date', 'he'], how='left', suffixes=('', '_y'))
d['lda'] = np.log(d.da.clip(lower=5)); d['lda_y'] = np.log(d.da_y.clip(lower=5))
d['lny'] = np.log(d.nyA_da.clip(lower=5)); d['lny_y'] = np.log(d.nyA_da_y.clip(lower=5))
d['h'] = d['head'] / 1000; d['dh'] = (d['head'] - d.head_y) / 1000
d['dni'] = d.ny_dni_oh / 1000; d['ddni'] = (d.ny_dni_oh - d.ny_dni_oh_y) / 1000
d['gapT'] = (d.lf_tesla - d.lf_adq2) / 1000
dates = sorted(d.date.unique())

def wf(feats, target='lda', win=21, anchor=None, per_blk=True):
    out = []
    for i in range(win, len(dates)):
        te = d[d.date == dates[i]]; tr = d[(d.date >= dates[i - win]) & (d.date < dates[i])]
        for b in (range(5) if per_blk else [None]):
            t = tr if b is None else tr[tr.blk == b]; e = te if b is None else te[te.blk == b]
            t = t.dropna(subset=feats + [target] + ([anchor] if anchor else [])); e = e.dropna(subset=feats + ([anchor] if anchor else []))
            if len(t) < 30 or not len(e): continue
            y = t[target] - (t[anchor] if anchor else 0)
            X = np.c_[np.ones(len(t)), t[feats].values]; lam = np.eye(X.shape[1]) * 0.5; lam[0, 0] = 0
            beta = np.linalg.solve(X.T @ X + lam, X.T @ y)
            pr = np.c_[np.ones(len(e)), e[feats].values] @ beta + (e[anchor].values if anchor else 0)
            out.append(pd.DataFrame({'date': e.date, 'he': e.he, 'y': e.da, 'p': np.exp(pr)}))
    return pd.concat(out)

V = {
  'persist (yesterday same HE)': None,
  'level: headroom': dict(feats=['h']),
  'level: headroom + wkend': dict(feats=['h', 'wkend']),
  'level: headroom + NY price': dict(feats=['h', 'lny', 'wkend']),
  'level: headroom + NY price + NY DNI OH': dict(feats=['h', 'lny', 'dni', 'wkend']),
  'level: + Tesla gap': dict(feats=['h', 'lny', 'dni', 'wkend', 'gapT']),
  'anchor: yesterday + dHead': dict(feats=['dh'], anchor='lda_y'),
  'anchor: + dNYprice + dDNI': dict(feats=['dh'], anchor='lda_y') ,
  'hybrid: level feats + yesterday': dict(feats=['h', 'lny', 'dni', 'wkend', 'lda_y']),
}
d['dlny'] = d.lny - d.lny_y
V['anchor: + dNYprice + dDNI'] = dict(feats=['dh', 'dlny', 'ddni'], anchor='lda_y')
res = {}
base = d[d.date.isin(dates[21:])].dropna(subset=['da_y'])
for k, v in V.items():
    if v is None: r = base.assign(p=base.da_y, y=base.da)[['date', 'he', 'y', 'p']]
    else: r = wf(**v)
    r = r.merge(base[['date', 'he']], on=['date', 'he'])            # same hours for every model
    e = r.p - r.y
    res[k] = dict(hours=len(r), MAE=round(e.abs().mean(), 2), bias=round(e.mean(), 2),
                  MAE_HE17_21=round(e[r.he.between(17, 21)].abs().mean(), 2), medAE=round(e.abs().median(), 2))
print(ZONE, 'test days', len(dates) - 21, dates[21], '->', dates[-1])
print(pd.DataFrame(res).T.to_string())
