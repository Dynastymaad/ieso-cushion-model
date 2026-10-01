"""signals_v2.py -- the trade signal that survived the walk-forward test (notes/Edge_Study.md).
One function, day(), used by BOTH the backtest and the live bundle, so the page shows exactly what was tested.

For target day D (bid morning D-1), using only spreads known at the deadline (RT complete through D-2):
  gas_hat : bid-time gas need = IESO demand fc - nuclear available - wind fc - solar fc
            - expected hydro + expected net exports (trailing 14-day median DA schedule per HE)
  TIGHT   : headroom < threshold learned on trailing spreads (best mean DA-RT, >= 40 h)
  SURPLUS : gas_hat < threshold learned the same way (candidates 2,500..4,500 MW)
  SELL    = TIGHT or SURPLUS (core tier).  EXTENDED tier: SURPLUS with the largest gas threshold whose
            trailing mean DA-RT >= $3 (more hours, lower $/MWh, higher total).  No buy rule passed the test.
  lean    : ridge regression of DA-RT on bid-time features (ranking only; shown, not traded)."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C

HEAD_THR = [7000, 7500, 8000, 8500, 9000, 9500, 10000]
GAS_THR = [2500, 3000, 3500, 4000, 4500]
FE = ['head_k', 'gapT_k', 'wind_k', 'dem_k', 'wkend', 'prof', 'lag2', 'nyx', 'pda']

def schedules():
    f = pd.read_csv(C.DATA / 'adq3_final.csv'); f['da_net_exp'] = -f.exp_sch.fillna(0) - f.imp_sch.fillna(0)
    return f[['date', 'he', 'hydro_sch', 'da_net_exp']]

def prep(d):
    """d needs: date he head dem_fc wind_fc solar_fc nuc_av gapT nyA_da p_da wkend sp (sp NaN for the target)."""
    d = d.copy().sort_values(['date', 'he'])
    d['head_k'] = d['head'] / 1000; d['gapT_k'] = d.gapT / 1000; d['wind_k'] = d.wind_fc / 1000; d['dem_k'] = d.dem_fc / 1000
    d['nyx'] = d.nyA_da - d.p_da; d['pda'] = d.p_da
    l2 = d[['date', 'he', 'sp']].copy(); l2['date'] = (pd.to_datetime(l2.date) + pd.Timedelta(days=2)).dt.date.astype(str)
    d = d.drop(columns='lag2', errors='ignore').merge(l2.rename(columns={'sp': 'lag2'}), on=['date', 'he'], how='left')
    s = schedules(); d = d.drop(columns=[c for c in ('hydro_sch', 'da_net_exp') if c in d]).merge(s, on=['date', 'he'], how='left')
    return d

def best_thr(tr, col, cands, below=True):
    best, thr = -1e9, None
    for t in cands:
        m = tr[tr[col] < t]
        if len(m) >= 40 and m.sp.mean() > best: best, thr = m.sp.mean(), t
    return thr

def largest_thr(tr, col, cands, floor=3.0):
    thr = None
    for t in cands:
        m = tr[tr[col] < t]
        if len(m) >= 40 and m.sp.mean() >= floor: thr = t
    return thr

def day(d, D, win=42):
    """d = prep()'d frame holding history and day D. Returns D's rows with gas_hat, thresholds, signal, lean."""
    cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
    te = d[d.date == D].copy()
    # gas need
    lo14 = (pd.Timestamp(cut) - pd.Timedelta(days=14)).date().isoformat()
    h = d[(d.date <= cut) & (d.date > lo14)].dropna(subset=['hydro_sch'])
    m = h.groupby('he')[['hydro_sch', 'da_net_exp']].median().rename(columns={'hydro_sch': 'hyd_exp', 'da_net_exp': 'exp_exp'}).reset_index()
    te = te.merge(m, on='he', how='left')
    te['gas_hat'] = te.dem_fc - te.nuc_av - te.wind_fc.fillna(0) - te.solar_fc.fillna(0) - te.hyd_exp + te.exp_exp
    # history with its own gas_hat (same construction, lagged) for threshold learning
    hist = d[(d.date <= cut) & d.sp.notna()].copy()
    if 'gas_hat' not in hist or hist.gas_hat.isna().all(): hist['gas_hat'] = np.nan
    te['thr_head'] = best_thr(hist, 'head', HEAD_THR)
    te['thr_gas'] = best_thr(hist.dropna(subset=['gas_hat']), 'gas_hat', GAS_THR)
    te['thr_gas_ext'] = largest_thr(hist.dropna(subset=['gas_hat']), 'gas_hat', GAS_THR)
    tight = te['head'] < te.thr_head.fillna(-1); surplus = te.gas_hat < te.thr_gas.fillna(-1)
    ext = (te.gas_hat < te.thr_gas_ext.fillna(-1)) & ~(tight | surplus)
    te['why'] = np.where(tight, 'tight', np.where(surplus, 'surplus', np.where(ext, 'surplus (ext)', '')))
    te['signal'] = np.where(tight | surplus, 'SELL', np.where(ext, 'SELL-L', 'NONE'))
    # lean: ridge on trailing 42 days
    lo = (pd.Timestamp(cut) - pd.Timedelta(days=win)).date().isoformat()
    tr = d[(d.date <= cut) & (d.date > lo) & d.sp.notna()].copy()
    prof = tr.groupby(['wkend', 'he']).sp.median().rename('prof').reset_index()
    te = te.drop(columns='prof', errors='ignore').merge(prof, on=['wkend', 'he'], how='left'); tr = tr.drop(columns='prof', errors='ignore').merge(prof, on=['wkend', 'he'], how='left')
    feats = [f for f in FE if tr[f].notna().mean() > .8]; t = tr.dropna(subset=feats)
    if len(t) > 200:
        mu, sd = t[feats].mean(), t[feats].std().replace(0, 1)
        X = np.c_[np.ones(len(t)), ((t[feats] - mu) / sd).values]; R = np.eye(X.shape[1]) * 25.0; R[0, 0] = 0
        beta = np.linalg.solve(X.T @ X + R, X.T @ t.sp.clip(-40, 40).values)
        te['lean'] = np.c_[np.ones(len(te)), ((te[feats].fillna(mu) - mu) / sd).values] @ beta
    else: te['lean'] = np.nan
    return te

def walk(d, start='2026-07-20'):
    """Backtest: run day() for every date, feeding each day's gas_hat back so later thresholds can learn from it."""
    d = prep(d); d['gas_hat'] = np.nan; out = []
    for D in sorted(d.date.unique()):
        x = day(d, D)
        d.loc[d.date == D, 'gas_hat'] = d.loc[d.date == D, 'he'].map(dict(zip(x.he, x.gas_hat))).values
        if D >= start: out.append(x)
    return pd.concat(out)

if __name__ == '__main__':
    import edge_study as E
    for z in (sys.argv[1:] or ['TORONTO', 'SOUTHWEST']):
        b = E.base(z); w = walk(b); w.to_csv(C.DATA / f'bt_signals_v2_{z}.csv', index=False)
        sig = np.where(w.signal == 'SELL', 1, 0); ext = np.where(w.signal == 'SELL-L', 1, 0)
        R = [E.score(w, 'v2 SELL core (tight or surplus)', sig), E.score(w, 'v2 SELL-L extended hours only', ext),
             E.score(w, 'v2 core + extended', np.where(w.signal != 'NONE', 1, 0)), E.score(w, '  tight only', np.where(w.why == 'tight', 1, 0)),
             E.score(w, '  surplus only', np.where(w.why == 'surplus', 1, 0)), E.score(w, 'all other hours (if sold)', np.where(w.signal == 'NONE', 1, 0)),
             E.score(w, 'sell every hour', np.ones(len(w))), E.score(w, 'lean > 3 (info only)', np.where(w.lean > 3, 1, 0))]
        R = pd.DataFrame(R); R.to_csv(C.DATA / f'es_rules_v2_{z}.csv', index=False); print(z); print(R.to_string(index=False))
        q = w.dropna(subset=['sp'])
        q = q[q.signal == 'SELL'].dropna(subset=['q10'])
        for k in ['q10', 'q25', 'q50']:
            c = q.da >= q[k]; print(f'   offer at {k}: cleared {c.sum()}/{len(q)} h, {q.sp[c].mean():+.2f} $/MWh, total {q.sp[c].sum():+,.0f}; price-taker {q.sp.mean():+.2f}, total {q.sp.sum():+,.0f}')
        print('   thresholds used (head / gas):', w.groupby('date')[['thr_head', 'thr_gas']].first().value_counts().head(8).to_dict())
