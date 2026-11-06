# Nov 5 2026: my explanation for "the more accurate load blend made less money" was: the card thresholds were set on Tesla's gap.
# Test: give the blend thresholds that fire exactly as often as the current load gap (quantile-matched, learned on days <= D-2 only).
import pandas as pd, numpy as np
ens = pd.read_csv('data/research/ensemble_fc.csv')[['date', 'he', 'lens']]
def tier(score, read):
    s_, r_ = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s_ == r_), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s_ == r_), s_, np.where(a, 0, np.where(abs(read) >= 5, r_, 0)))
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']).merge(ens, on=['date', 'he'], how='left')
    h = h[(h.date >= '2025-11-20') & h.lens.notna()].reset_index(drop=True); m = np.where(h.pub_sp < 2500, 2, 1)
    raw = h['c_Load gap'] / m; g = h.lens - h.dem_fc; s0 = h.score - h['c_Load gap']
    p = np.zeros(len(h)); dts = sorted(h.date.unique())
    for D in dts:
        tr = h.date < (pd.Timestamp(D) - pd.Timedelta(days=1)).strftime('%Y-%m-%d'); te = (h.date == D).values
        if tr.sum() < 2000: continue
        qs = {v: (raw[tr] >= v).mean() for v in (1, 2)}; qn = {v: (raw[tr] <= -v).mean() for v in (1, 2)}
        hi1, hi2 = g[tr].quantile(1 - qs[1]), g[tr].quantile(1 - qs[2]); lo1, lo2 = g[tr].quantile(qn[1]), g[tr].quantile(qn[2])
        gg = g[te]; p[te] = np.where(gg >= hi2, 2, np.where(gg >= hi1, 1, np.where(gg <= lo2, -2, np.where(gg <= lo1, -1, 0))))
    ok = h.date >= dts[0]; mo = h.date.str[:7]
    def pnl(sc): t, sd = tier(sc, h.read); return pd.Series(np.where(np.isin(t, ['A', 'B']), sd * h.rd, 0), index=h.index)
    cur = pnl(h.score); new = pnl(s0 + p * m); fixed = pnl(s0 + np.where(g >= 250, 2, np.where(g >= 100, 1, np.where(g <= -250, -2, np.where(g <= -100, -1, 0)))) * m)
    k = p != 0
    print(f'{z} {h.date.min()}..{h.date.max()}: current ${cur.sum():,.0f} | blend, same thresholds ${fixed.sum():,.0f} ({fixed.sum()-cur.sum():+,.0f}) | blend, thresholds matched to firing rate ${new.sum():,.0f} ({new.sum()-cur.sum():+,.0f}); '
          f'months better {(new.groupby(mo).sum() > cur.groupby(mo).sum() + 1).sum()}/{mo.nunique()} | fires {100*k.mean():.0f}% vs current {100*(raw != 0).mean():.0f}%')
