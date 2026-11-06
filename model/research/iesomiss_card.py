# Nov 5 2026: does a modelled IESO miss make a better load-gap point? Same thresholds (+-100 = 1, +-250 = 2), x2 in thin spare.
import pandas as pd, numpy as np
p = pd.read_csv('data/research/iesomiss_pred.csv')[['date', 'he', 'p1', 'p2', 'p3', 'g_met', 'g_tes']]
def tier(score, read):
    s_, r_ = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s_ == r_), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s_ == r_), s_, np.where(a, 0, np.where(abs(read) >= 5, r_, 0)))
pts = lambda g: np.where(g >= 250, 2, np.where(g >= 100, 1, np.where(g <= -250, -2, np.where(g <= -100, -1, 0))))
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']).merge(p, on=['date', 'he'], how='left')
    h = h[h.p2.notna()].reset_index(drop=True); m = np.where(h.pub_sp < 2500, 2, 1); s0 = h.score - h['c_Load gap']; mo = h.date.str[:7]
    def run(g): t, sd = tier(s0 + pts(g.fillna(0)) * m, h.read); return pd.Series(np.where(np.isin(t, ['A', 'B']), sd * h.rd, 0), index=h.index)
    t, sd = tier(h.score, h.read); cur = pd.Series(np.where(np.isin(t, ['A', 'B']), sd * h.rd, 0), index=h.index)
    V = {'M1 linear': h.p1, 'M2 boosted': h.p2, 'Meteologica where it exists, else M2': h.g_met.fillna(h.p2), 'M3 where Meteologica exists, else M2': h.p3.fillna(h.p2)}
    print(f'{z} {h.date.min()}..{h.date.max()}: current (Meteologica, else Tesla) ${cur.sum():,.0f}')
    for n, g in V.items():
        v = run(g); d = v - cur; dm = d.groupby(mo).sum()
        print(f'   {n:38s} ${v.sum():,.0f} ({d.sum():+,.0f}) | months better {(dm > 1).sum()}, worse {(dm < -1).sum()} | first half {d[h.date < "2026-04-15"].sum():+,.0f}, second half {d[h.date >= "2026-04-15"].sum():+,.0f}')
