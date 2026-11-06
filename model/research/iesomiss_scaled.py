# Nov 5 2026: same card, M2 rescaled so its spread matches the gap the card was built on (ratio of standard deviations, trailing 90 days through D-2).
import pandas as pd, numpy as np
p = pd.read_csv('data/research/iesomiss_pred.csv')[['date', 'he', 'p2', 'g_tes', 'g_met']]
def tier(score, read):
    s_, r_ = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s_ == r_), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s_ == r_), s_, np.where(a, 0, np.where(abs(read) >= 5, r_, 0)))
pts = lambda g: np.where(g >= 250, 2, np.where(g >= 100, 1, np.where(g <= -250, -2, np.where(g <= -100, -1, 0))))
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).merge(p, on=['date', 'he']).sort_values(['date', 'he']).reset_index(drop=True)
    gap = h.load_gap; k = pd.Series(np.nan, index=h.index)
    for D in sorted(h.date.unique()):
        tr = (h.date <= (pd.Timestamp(D) - pd.Timedelta(days=2)).strftime('%Y-%m-%d')) & (h.date > (pd.Timestamp(D) - pd.Timedelta(days=92)).strftime('%Y-%m-%d')) & h.p2.notna()
        if tr.sum() > 500: k[h.date == D] = gap[tr].std() / h.p2[tr].std()
    h['k'] = k; h = h[h.rd.notna() & h.p2.notna() & h.k.notna()].reset_index(drop=True); m = np.where(h.pub_sp < 2500, 2, 1); s0 = h.score - h['c_Load gap']; mo = h.date.str[:7]
    def pl(sc): t, sd = tier(sc, h.read); return pd.Series(np.where(np.isin(t, ['A', 'B']), sd * h.rd, 0), index=h.index)
    cur = pl(h.score); a = pl(s0 + pts(h.p2) * m); b = pl(s0 + pts(h.p2 * h.k) * m)
    for n, v in [('M2 as is', a), ('M2 rescaled to the card gap\'s spread', b)]:
        d = v - cur; dm = d.groupby(mo).sum()
        print(f'{z} {h.date.min()}..{h.date.max()} {n:38s} ${v.sum():,.0f} vs current ${cur.sum():,.0f} ({d.sum():+,.0f}) | months better {(dm>1).sum()}, worse {(dm<-1).sum()} | halves {d[h.date<"2026-04-15"].sum():+,.0f} / {d[h.date>="2026-04-15"].sum():+,.0f} | scale avg {h.k.mean():.2f}')
    pt0 = h['c_Load gap'] / m; pt1 = pts(h.p2 * h.k); print(f'   load points now: -2 {100*(pt0==-2).mean():.0f}% 0 {100*(pt0==0).mean():.0f}% +2 {100*(pt0==2).mean():.0f}% | rescaled M2: -2 {100*(pt1==-2).mean():.0f}% 0 {100*(pt1==0).mean():.0f}% +2 {100*(pt1==2).mean():.0f}%')
