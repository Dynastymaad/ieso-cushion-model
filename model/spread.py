"""spread.py -- RT forecast = DA forecast + expected (RT - DA), walk-forward.
Spread features, all known at the bid deadline: headroom, Tesla-minus-IESO load gap (full,
and only when |gap| >= 600 MW), NY-OH scheduled flow, block, weekend."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C

def feats(d):
    d = d.copy()
    d['sp'] = d.rt - d.da
    d['tight'] = np.clip((9000 - d['head']) / 1000, 0, None)
    d['gbig_dn'] = np.where(d.gapT <= -0.6, d.gapT + 0.6, 0.0)     # Tesla well below IESO
    d['gbig_up'] = np.where(d.gapT >= 0.6, d.gapT - 0.6, 0.0)
    for b in range(5): d[f'b{b}'] = (d.blk == b).astype(float)
    return d

SPREAD_SETS = {
  'zero': None,
  'trailing median by block': 'median',
  'ridge: block + tightness': ['b1', 'b2', 'b3', 'b4', 'tight', 'wkend'],
  'ridge: + Tesla gap (big only)': ['b1', 'b2', 'b3', 'b4', 'tight', 'wkend', 'gbig_dn', 'gbig_up'],
  'ridge: + Tesla gap + NY flow': ['b1', 'b2', 'b3', 'b4', 'tight', 'wkend', 'gbig_dn', 'gbig_up', 'dni'],
}

def walk_spread(d, cols, win=28, lam=2.0):
    dates = sorted(d.dropna(subset=['rt', 'da']).date.unique()); out = []
    for i in range(win, len(dates) + 1):
        D = (pd.Timestamp(dates[-1]) + pd.Timedelta(days=1)).date().isoformat() if i == len(dates) else dates[i]
        # outcomes known at the D-1 deadline: RT through D-2 fully
        cut = (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat()
        tr = d[(d.date >= dates[max(0, i - win)]) & (d.date < cut)].dropna(subset=['sp'])
        te = d[d.date == D].copy()
        if not len(te) or len(tr) < 200: continue
        if cols is None: te['s_hat'] = 0.0
        elif cols == 'median':
            m = tr.groupby('blk').sp.median(); te['s_hat'] = te.blk.map(m).fillna(0)
        else:
            t = tr.dropna(subset=cols); X = np.c_[np.ones(len(t)), t[cols].values]
            # winsorise the target: spikes should not set the typical spread
            y = t.sp.clip(t.sp.quantile(0.02), t.sp.quantile(0.98))
            R = np.eye(X.shape[1]) * lam; R[0, 0] = 0
            beta = np.linalg.solve(X.T @ X + R, X.T @ y)
            te['s_hat'] = np.c_[np.ones(len(te)), te[cols].fillna(0).values] @ beta
        out.append(te)
    return pd.concat(out)


def binned(tr, te, min_n=15):
    """conditional median spread: block x tightness band x Tesla-gap band, shrunk to block median."""
    def keys(x):
        tb = np.where(x['head'] < 8000, 'tight', np.where(x['head'] < 10500, 'mid', 'loose'))
        gb = np.where(x.gapT <= -0.6, 'Tlow', np.where(x.gapT >= 0.6, 'Thigh', 'n'))
        return pd.Series(x.blk.astype(str) + '|' + tb + '|' + gb, index=x.index)
    tr = tr.copy(); te = te.copy(); tr['k'] = keys(tr); te['k'] = keys(te)
    bm = tr.groupby('blk').sp.median(); g = tr.groupby('k').sp.agg(['median', 'size'])
    w = (g['size'] / (g['size'] + min_n)); shr = w * g['median'] + (1 - w) * g.index.str.split('|').str[0].astype(int).map(bm).values
    te['s_hat'] = te.k.map(shr).fillna(te.blk.map(bm)).fillna(0)
    return te['s_hat']


def walk_binned(d, win=42):
    dates = sorted(d.dropna(subset=['rt', 'da']).date.unique()); out = []
    for i in range(21, len(dates) + 1):
        D = (pd.Timestamp(dates[-1]) + pd.Timedelta(days=1)).date().isoformat() if i == len(dates) else dates[i]
        cut = (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat()
        tr = d[(d.date >= dates[max(0, i - win)]) & (d.date < cut)].dropna(subset=['sp', 'gapT'])
        te = d[d.date == D].copy()
        if not len(te): continue
        te['s_hat'] = binned(tr, te).values; out.append(te)
    return pd.concat(out)
