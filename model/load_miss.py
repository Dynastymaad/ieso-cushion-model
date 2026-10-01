"""load_miss.py -- can bid-time weather tell us when IESO's load forecast will run LOW (the #2 cause of losing sells)?
Target: miss = actual Ontario demand - IESO pre-DA forecast (+ = load came in above IESO). All features bid-safe:
  Open-Meteo pd2 temperature / feels-like / dew point (issued ~48 h before), cooling / heating degrees,
  change vs the actual two days earlier, weekend, HE, Tesla - IESO, and IESO's own miss two days earlier (same HE).
Walk-forward ridge, trailing 60 days, refit every day. Then: veto v2 SELL hours when the predicted miss >= +X MW."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 250)

def frame(zone='TORONTO'):
    e = pd.read_csv(C.DATA / f'fs_frame_{zone}.csv')
    w = pd.read_csv(C.DATA / 'wx' / 'wx_hourly.csv')
    e = e.drop(columns=[c for c in w.columns if c not in ('date', 'he') and c in e], errors='ignore').merge(w, on=['date', 'he'], how='left')
    L = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'ont_dem']]
    e = e.drop(columns=['ont_dem'], errors='ignore').merge(L, on=['date', 'he'], how='left')
    e['miss'] = e.ont_dem - e.dem_fc
    e['cdd'] = (e.t_fc - 65).clip(lower=0); e['hdd'] = (55 - e.t_fc).clip(lower=0); e['feel_x'] = e.feel_fc - e.t_fc
    d2 = e[['date', 'he', 't_act', 'miss']].copy(); d2['date'] = (pd.to_datetime(d2.date) + pd.Timedelta(days=2)).dt.date.astype(str)
    e = e.merge(d2.rename(columns={'t_act': 't_act_d2', 'miss': 'miss_d2'}), on=['date', 'he'], how='left')
    e['dt_vs_d2'] = e.t_fc - e.t_act_d2
    e['wk'] = (e.dow >= 5).astype(int); e['pk'] = e.he.between(12, 21).astype(int)
    e['cdd_pk'] = e.cdd * e.pk; e['cdd_wk'] = e.cdd * e.wk; e['dt_pk'] = e.dt_vs_d2 * e.pk
    return e

F_WX = ['cdd', 'hdd', 'feel_x', 'dt_vs_d2', 'cdd_pk', 'cdd_wk', 'dt_pk', 'wk']
F_ALL = F_WX + ['gapT', 'miss_d2']

def walk(e, feats, win=60, start='2025-07-01', lam=5.0):
    e = e.sort_values(['date', 'he']).reset_index(drop=True); e['pm_' + '_'.join(feats[:1])] = np.nan; out = pd.Series(np.nan, index=e.index)
    days = sorted(e.date.unique())
    for D in days:
        if D < start: continue
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=win)).date().isoformat()
        tr = e[(e.date <= c2) & (e.date > lo)].dropna(subset=feats + ['miss'])
        te = e.date == D
        if len(tr) < 400: continue
        mu, sd = tr[feats].mean(), tr[feats].std().replace(0, 1)
        X = np.c_[np.ones(len(tr)), ((tr[feats] - mu) / sd).values]; R = np.eye(X.shape[1]) * lam; R[0, 0] = 0
        b = np.linalg.solve(X.T @ X + R, X.T @ tr.miss.clip(-2500, 2500).values)
        Z = e.loc[te, feats].fillna(mu); out[te] = np.c_[np.ones(te.sum()), ((Z - mu) / sd).values] @ b
    return out

if __name__ == '__main__':
    e = frame(); t0 = e[e.date >= '2025-07-01']
    e['pm_wx'] = walk(e, F_WX); e['pm_all'] = walk(e, F_ALL); e['pm_tesla'] = walk(e, ['gapT', 'miss_d2'])
    e.to_csv(C.DATA / 'lm_frame.csv', index=False)
    t = e[(e.date >= '2025-07-01')].dropna(subset=['miss', 'pm_all', 'pm_wx', 'pm_tesla'])
    print(f'hours {len(t)}; IESO load miss: mean {t.miss.mean():+.0f} MW, MAE {t.miss.abs().mean():.0f}')
    for c, n in (('pm_tesla', 'Tesla gap + IESO miss 2 days ago'), ('pm_wx', 'weather only (Open-Meteo, bid-safe)'), ('pm_all', 'weather + Tesla + IESO miss 2d ago')):
        r = t.miss - t[c]; hi = t[c] >= 300
        print(f'  {n:40s} corr {t[c].corr(t.miss):.3f}  MAE after correction {r.abs().mean():.0f}  | predicted >= +300 MW: {hi.sum()} h, actual miss there {t.miss[hi].mean():+.0f}, share actually >= +300 {(t.miss[hi] >= 300).mean()*100:.0f}%')
    # which loss days would have been flagged
    for d in ['2025-10-05', '2025-07-25', '2026-05-02', '2025-07-01', '2026-03-11', '2025-09-06', '2026-05-29']:
        x = e[e.date == d]; print(f'  {d}: actual miss {x.miss.mean():+5.0f}  pred(all) {x.pm_all.mean():+5.0f}  pred(wx) {x.pm_wx.mean():+5.0f}  pred(tesla) {x.pm_tesla.mean():+5.0f}  temp fc max {x.t_fc.max():.0f}F  dT vs D-2 {x.dt_vs_d2.mean():+.1f}')
