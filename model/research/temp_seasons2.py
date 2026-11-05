# Nov 5 2026: Nov + Mar counted as Winter vs current seasons. (a) load-change accuracy, walk-forward AND leave-one-month-out (only way to score November with winter data),
# (b) card P&L walk-forward by hub, by month, and on the hours where the point changed.
import sys; sys.path.insert(0, '.'); import numpy as np, pandas as pd, temp_conv as TC
def tier(score, read):
    s, r = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s == r), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s == r), s, np.where(a, 0, np.where(abs(read) >= 5, r, 0)))
def plan(h, sc):
    t, s = tier(sc, h.read); return pd.Series(np.where(np.isin(t, ['A', 'B']), s * h.rd, 0), index=h.index)
def lomo(x):
    fit = x[x.same & x.dL.notna() & x.dH.notna() & x.dK.notna()]; p = pd.Series(np.nan, index=x.index)
    for m in fit.m.unique():
        S = TC.slopes(fit[fit.m != m]); te = fit[fit.m == m]
        p[te.index] = [S[(s, b)][0] * h + S[(s, b)][1] * k for s, b, h, k in zip(te.season, te.blk, te.dH, te.dK)]
    return p
base = dict(TC.SEAS); V = {'cur': base, 'new': {**base, 11: 'Winter', 3: 'Winter'}}; T, A = {}, {}
for k, S in V.items():
    TC.SEAS = S; x = TC.frame(); T[k] = TC.mw_table(x)[['date', 'he', 'tmw', 'dL', 'same']]; x['lp'] = lomo(x); A[k] = x[['date', 'he', 'dL', 'lp', 'same']]
    if k == 'new': nov = TC.slopes(x[x.same & x.dL.notna() & x.dH.notna() & x.dK.notna() & (x.m < '2026-11')])
print('(a) Average miss on the 2-day load change (MW)')
for lab, sel in [('all months', lambda d: d.date.notna()), ('November', lambda d: d.date.str[5:7] == '11'), ('March', lambda d: d.date.str[5:7] == '03')]:
    r = []
    for k in V:
        w = T[k][T[k].same & T[k].dL.notna()]; w = w[sel(w)]; l = A[k][A[k].same & A[k].dL.notna() & A[k].lp.notna()]; l = l[sel(l)]
        r.append(f'{k}: walk-fwd {(w.dL - w.tmw).abs().mean():.0f}, leave-1-month-out {(l.dL - l.lp).abs().mean():.0f}')
    print(f'  {lab:11s} ' + ' | '.join(r))
print('\n(b) Card P&L (A/B plan, 1 MW), Sep 2025 - Sep 2026, walk-forward')
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'../data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']); h = h[h.date <= '2026-09-30']; s0 = h.score - h['c_Temp swing']
    R = {}
    for k in V:
        t = h[['date', 'he']].merge(T[k][['date', 'he', 'tmw']], on=['date', 'he'], how='left').tmw.values
        p = np.where(t >= 250, 1, np.where(t <= -250, -1, 0)); R[k] = (p, plan(h, s0 + p))
    d = R['new'][1] - R['cur'][1]; mo = h.date.str[:7]; dm = d.groupby(mo).sum()
    ch = R['new'][0] != R['cur'][0]
    print(f'  {z}: current ${R["cur"][1].sum():,.0f} -> Nov+Mar winter ${R["new"][1].sum():,.0f} ({d.sum():+,.0f}) | months better {(dm > 1).sum()}, worse {(dm < -1).sum()}, same {(dm.abs() <= 1).sum()}')
    print(f'     by month: ' + ', '.join(f'{m} {v:+,.0f}' for m, v in dm.items() if abs(v) > 1))
    print(f'     hours where the temp point changed: {ch.sum()} (Nov {(ch & (h.date.str[5:7]=="11")).sum()}, Mar {(ch & (h.date.str[5:7]=="03")).sum()})')
print('\n(c) Numbers November 2026 would use (fitted through Oct 31), heat per C colder below 15:')
for s in ['Winter', 'Fall']: print(f'  {s:6s}', '  '.join(f'{b} {round(nov[(s, b)][0], -1):.0f}' for _, _, b in TC.BLK))
