"""hourly.py -- next-day hourly DA for a hub, walk-forward (bid-time inputs only).
  hybrid   : per time-block ridge of ln(DA) on headroom, ln(NYISO Zone A DAM), NY-OH scheduled
             net flow, weekend flag and ln(yesterday's DA same hour); trailing 21 days.
  scaled   : hybrid shape rescaled so each block's mean equals the all-season block model
             (50/50 anchored-delta + Ontario Hub forward; see blocks.py).
Returns predictions plus the residual pool used for quantiles."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C

def frame(zone):
    p = C.prices(zone)[['date', 'he', 'da', 'rt']]
    a = C.adq2('preDA')[['date', 'he', 'head', 'dem_fc', 'resid_fc', 'gas_av', 'hyd_av']]
    ny = pd.read_csv(C.DATA / 'nyiso_zoneA_da.csv'); ne = pd.read_csv(C.DATA / 'nyiso_dam_energy.csv')[['date', 'he', 'ny_dni_oh']]
    L = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'lf_tesla', 'lf_adq2', 'lf_dynasty']]
    d = a.merge(p, on=['date', 'he'], how='left').merge(ny, on=['date', 'he'], how='left').merge(ne, on=['date', 'he'], how='left').merge(L, on=['date', 'he'], how='left')
    d = d.sort_values(['date', 'he']).reset_index(drop=True)
    d['blk'] = pd.cut(d.he, [0, 6, 10, 16, 21, 24], labels=False).astype(int)
    d['dow'] = pd.to_datetime(d.date).dt.dayofweek; d['wkend'] = (d.dow >= 5).astype(int)
    prev = d[['date', 'he', 'da']].copy(); prev['date'] = (pd.to_datetime(prev.date) + pd.Timedelta(days=1)).dt.date.astype(str)
    d = d.merge(prev.rename(columns={'da': 'da_y'}), on=['date', 'he'], how='left')
    d['lda'] = np.log(d.da.clip(lower=5)); d['lda_y'] = np.log(d.da_y.clip(lower=5))
    d['lny'] = np.log(d.nyA_da.clip(lower=5)); d['h'] = d['head'] / 1000; d['dni'] = d.ny_dni_oh / 1000
    d['gapT'] = (d.lf_tesla - d.lf_adq2) / 1000
    return d

FEATS = ['h', 'lny', 'dni', 'wkend', 'lda_y']

def fit_predict(tr, te, feats=FEATS, lam=0.5):
    out = []
    for b in range(5):
        t = tr[tr.blk == b].dropna(subset=feats + ['lda']); e = te[te.blk == b].copy()
        e[feats] = e[feats].fillna(t[feats].median())
        if len(t) < 30 or not len(e): continue
        X = np.c_[np.ones(len(t)), t[feats].values]; R = np.eye(X.shape[1]) * lam; R[0, 0] = 0
        beta = np.linalg.solve(X.T @ X + R, X.T @ t.lda.values)
        e['p_h'] = np.exp(np.c_[np.ones(len(e)), e[feats].values] @ beta)
        for f_, b_ in zip(feats, beta[1:]): e['b_' + f_] = b_      # per-block coefficients (what-if sliders use b_h, b_dni)
        e['fit_res'] = np.nan
        out.append(e)
    return pd.concat(out) if out else te.iloc[:0]

def walk(zone, win=21, block_fc=None):
    d = frame(zone); dates = sorted(d.dropna(subset=['da']).date.unique())
    res = []
    for i in range(win, len(dates) + 1):
        D = (pd.Timestamp(dates[i - 1]) + pd.Timedelta(days=1)).date().isoformat() if i == len(dates) else dates[i]
        tr = d[(d.date >= dates[i - win]) & (d.date < D) & d.da.notna()]
        te = d[d.date == D]
        if not len(te): continue
        e = fit_predict(tr, te)
        if block_fc is not None and len(e):
            e = e.merge(block_fc, on='date', how='left')
            e['on'] = e.he.between(7, 22)
            tgt = np.where(e.on & (e.dow < 5), e.fc_on, np.where(e.on, e.fc_flat, e.fc_off))
            grp = e.groupby(e.on).p_h.transform('mean')
            e['p_s'] = np.where(np.isnan(tgt), e.p_h, e.p_h * tgt / grp)
        res.append(e)
    return pd.concat(res)
