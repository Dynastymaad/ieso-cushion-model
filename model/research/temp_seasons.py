# Nov 5 2026: does November behave like winter (heating on)? Re-test the conversion with Nov counted as Winter. Walk-forward, same scoring as temp_card2.
import sys; sys.path.insert(0, '.'); import numpy as np, pandas as pd, temp_conv as TC
def tier(score, read):
    s, r = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s == r), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s == r), s, np.where(a, 0, np.where(abs(read) >= 5, r, 0)))
def plan(h, sc):
    t, s = tier(sc, h.read); return pd.Series(np.where(np.isin(t, ['A', 'B']), s * h.rd, 0), index=h.index)
base = dict(TC.SEAS)
V = {'current (Nov = Fall)': base, 'Nov = Winter': {**base, 11: 'Winter'}, 'Nov + Mar = Winter': {**base, 11: 'Winter', 3: 'Winter'}}
H = {z: pd.read_csv(f'../data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']) for z in ['EAST', 'OTTAWA']}
for lab, S in V.items():
    TC.SEAS = S; x = TC.frame(); t = TC.mw_table(x)
    f = t[t.same & t.dL.notna()]; e = (f.dL - f.tmw).abs()
    nov = f.date.str[5:7] == '11'
    msg = f'{lab:22s} 2-day load change miss: all {e.mean():.0f} MW | November {e[nov].mean():.0f} | March {e[f.date.str[5:7]=="03"].mean():.0f}'
    for z, h in H.items():
        k = h.merge(t[['date', 'he', 'tmw']], on=['date', 'he'], how='left'); k = k[k.date <= '2026-09-30']
        p = np.where(k.tmw >= 250, 1, np.where(k.tmw <= -250, -1, 0)); s0 = k.score - k['c_Temp swing']
        msg += f' | {z} ${plan(k, s0 + p).sum():,.0f}'
    print(msg)
