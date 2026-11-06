# Nov 5 2026: do 30/60/90-day fitting windows beat the season buckets for the temperature read?
# Target: the 2-day load change (D vs D-2, same hour, same day type) predicted at the bid from forecast temps (fH, fK). Slopes refit DAILY on pairs dated <= D-2.
# Each window fits heat + cool per time-of-day block; a term with under 60 hours of that weather in the window falls back to the season number (current method).
import sys; sys.path.insert(0, '.'); import numpy as np, pandas as pd, temp_conv as TC
x = TC.frame(); x['d'] = pd.to_datetime(x.date); x['doy'] = x.d.dt.dayofyear
f = x[x.same & x.dL.notna() & x.dH.notna() & x.dK.notna()].copy()
ev = x[x.fH.notna() & x.fK.notna() & (x.date >= '2025-09-08') & (x.date <= '2026-11-05')].copy()
def coef(g, mn):
    if len(g) < 30: return np.nan, np.nan
    b = np.linalg.lstsq(np.c_[g.dH, g.dK], g.dL, rcond=None)[0]
    return (b[0] if (g.dH != 0).sum() >= mn else np.nan), (b[1] if (g.dK != 0).sum() >= mn else np.nan)
V = {'Seasons, monthly refit (live now)': None, 'Seasons, daily refit': None, 'Last 30 days': ('trail', 30), 'Last 60 days': ('trail', 60), 'Last 90 days': ('trail', 90),
     'Same time of year +-15 d (30-day bucket)': ('cal', 15), 'Same time of year +-30 d (60-day bucket)': ('cal', 30)}
P = {k: pd.Series(np.nan, index=ev.index) for k in V}; S_month = {}
for D, g in ev.groupby('date'):
    Dt = pd.Timestamp(D); past = f[f.d <= Dt - pd.Timedelta(days=2)]
    if past.date.str[:7].nunique() < 4: continue
    m = D[:7]
    if m not in S_month: S_month[m] = TC.slopes(f[f.date.str[:7] < m])
    Sd = TC.slopes(past)
    for b, gb in g.groupby('blk'):
        s = gb.season.iloc[0]; hm, cm = S_month[m][(s, b)][:2]; hd, cd = Sd[(s, b)][:2]
        P['Seasons, monthly refit (live now)'][gb.index] = hm * gb.fH + cm * gb.fK
        P['Seasons, daily refit'][gb.index] = hd * gb.fH + cd * gb.fK
        pb = past[past.blk == b]
        for k, v in V.items():
            if v is None: continue
            if v[0] == 'trail': tr = pb[pb.d > Dt - pd.Timedelta(days=2 + v[1])]
            else: dd = (pb.doy - Dt.dayofyear).abs(); tr = pb[np.minimum(dd, 365 - dd) <= v[1]]
            h, c = coef(tr, 60); h = hd if np.isnan(h) else h; c = cd if np.isnan(c) else c
            P[k][gb.index] = h * gb.fH + c * gb.fK

def tier(score, read):
    s_, r = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s_ == r), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s_ == r), s_, np.where(a, 0, np.where(abs(read) >= 5, r, 0)))
M = pd.DataFrame({k: P[k] for k in V}).assign(date=ev.date, he=ev.he)
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'../data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']).merge(M, on=['date', 'he'], how='inner')
    h = h[h[list(V)].notna().all(axis=1)]; s0 = h.score - h['c_Temp swing']; mo = h.date.str[:7]; R = {}
    for k in V:
        p = np.where(h[k] >= 250, 1, np.where(h[k] <= -250, -1, 0)); t, sd = tier(s0 + p, h.read); R[k] = pd.Series(np.where(np.isin(t, ['A', 'B']), sd * h.rd, 0), index=h.index)
    b = R['Seasons, monthly refit (live now)']; bm = b.groupby(mo).sum()
    print(f'{z} {h.date.min()}..{h.date.max()} live ${b.sum():,.0f}')
    for k in V:
        if k.startswith('Seasons, monthly'): continue
        v = R[k]; vm = v.groupby(mo).sum(); print(f'   {k:42s} ${v.sum():,.0f} ({v.sum()-b.sum():+,.0f}) | months better {(vm>bm+1).sum()}, worse {(vm<bm-1).sum()}')
