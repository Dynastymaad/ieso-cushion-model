# Nov 5 2026: Temp swing card point with tested MW-per-C conversions (walk-forward: slopes fitted only on months before the one traded).
import pandas as pd, numpy as np, json
w = pd.read_csv('data/wx/wx_hourly.csv')
for c in ['t_act', 'feel_act', 't_fc', 'feel_fc']: w[c] = (w[c] - 32) * 5 / 9
L = pd.read_csv('data/load_at_bid.csv')[['date', 'he', 'ont_dem']].merge(w[['date', 'he', 't_act', 'feel_act', 't_fc', 'feel_fc']], on=['date', 'he'], how='outer')
d2 = L[['date', 'he', 'ont_dem', 't_act', 'feel_act']].copy(); d2['date'] = (pd.to_datetime(d2.date) + pd.Timedelta(days=2)).dt.strftime('%Y-%m-%d')
x = L.merge(d2, on=['date', 'he'], suffixes=('', '_2'))
dt = pd.to_datetime(x.date); mo = dt.dt.month; x['m'] = dt.dt.strftime('%Y-%m')
x['same'] = (dt.dt.dayofweek < 5) == (((dt.dt.dayofweek - 2) % 7) < 5)
x['season'] = np.select([mo.isin([12, 1, 2]), mo.isin([3, 4, 5]), mo.isin([6, 7, 8])], ['Winter', 'Spring', 'Summer'], 'Fall')
x['blk'] = pd.cut(x.he, [0, 6, 10, 15, 21, 24], labels=['HE1-6', 'HE7-10', 'HE11-15', 'HE16-21', 'HE22-24']).astype(str)
H = lambda t: np.clip(15 - t, 0, None); K = lambda t: np.clip(t - 20, 0, None)
x['dL'] = x.ont_dem - x.ont_dem_2
x['dH'] = H(x.t_act) - H(x.t_act_2); x['dK'] = K(x.t_act) - K(x.t_act_2); x['dKf'] = K(x.feel_act) - K(x.feel_act_2)          # for fitting (actuals)
x['fH'] = H(x.t_fc) - H(x.t_act_2); x['fK'] = K(x.t_fc) - K(x.t_act_2); x['fKf'] = K(x.feel_fc) - K(x.feel_act_2)             # at the bid (forecast vs actual 2 days earlier)
def coef(g, kc):
    nh, nk = (g.dH != 0).sum(), (g[kc] != 0).sum(); A = np.c_[g.dH, g[kc]]; b = np.linalg.lstsq(A, g.dL, rcond=None)[0] if len(g) > 50 else np.zeros(2)
    return (b[0] if nh >= 150 else np.nan), (b[1] if nk >= 150 else np.nan)
def slopes(tr, keys, kc):
    out = {}
    blk = {b: coef(g, kc) for b, g in tr.groupby('blk')}; al = coef(tr, kc)
    for k, g in tr.groupby(keys):
        h, c = coef(g, kc); b = k[-1] if isinstance(k, tuple) else k
        h = h if not np.isnan(h) else blk[b][0] if not np.isnan(blk[b][0]) else al[0]; c = c if not np.isnan(c) else blk[b][1] if not np.isnan(blk[b][1]) else al[1]
        out[k] = (h, c)
    return out, blk, al
def bidMW(keys, kc, fk):
    mw = pd.Series(np.nan, index=x.index); fit = x[x.same & x.dL.notna() & x.dH.notna()]
    for m in sorted(x.m.dropna().unique()):
        tr = fit[fit.m < m]
        if tr.m.nunique() < 4: continue
        S, blk, al = slopes(tr, keys, kc); te = x[(x.m == m) & x.fH.notna()]
        for i, r in te.iterrows():
            k = tuple(r[c] for c in keys) if len(keys) > 1 else r[keys[0]]; h, c = S.get(k, blk.get(r.blk, al))
            mw[i] = np.nan_to_num(h) * r.fH + np.nan_to_num(c) * r[fk]
    return mw
V = {'B by time of day': bidMW(['blk'], 'dK', 'fK'), 'C by season x time of day': bidMW(['season', 'blk'], 'dK', 'fK'), 'D season x time of day + humidity': bidMW(['season', 'blk'], 'dKf', 'fKf')}
X = x[['date', 'he']].copy()
for k, v in V.items(): X[k] = v.values
X.to_csv('data/research/temp_card2_mw.csv', index=False)
def tier(score, read):
    s, r = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s == r), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s == r), s, np.where(a, 0, np.where(abs(read) >= 5, r, 0)))
def plan(h, sc):
    t, s = tier(sc, h.read); return pd.Series(np.where(np.isin(t, ['A', 'B']), s * h.rd, 0), index=h.index)
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).merge(X, on=['date', 'he'], how='left').dropna(subset=['rd'])
    h = h[h['C by season x time of day'].notna()].copy(); h['mo'] = h.date.str[:7]
    s0 = h.score - h['c_Temp swing']; b0 = plan(h, s0); cur = plan(h, h.score)
    print(f'\n{z} {h.date.min()} to {h.date.max()} | no temp point ${b0.sum():,.0f} | current rule ${cur.sum():,.0f} ({cur.sum()-b0.sum():+,.0f}), fires {(h["c_Temp swing"]!=0).sum()} h')
    for k in V:
        for th in (250, 400):
            p = np.where(h[k] >= th, 1, np.where(h[k] <= -th, -1, 0)); n = plan(h, s0 + p)
            nm, cm = n.groupby(h.mo).sum(), cur.groupby(h.mo).sum()
            print(f'  {k:36s} +-{th}: fires {(p!=0).sum():5d} h | ${n.sum():,.0f} ({n.sum()-b0.sum():+,.0f} vs none, {n.sum()-cur.sum():+,.0f} vs current) | months vs current better {(nm>cm+1).sum()}/worse {(nm<cm-1).sum()}')
