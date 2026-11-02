"""Nov 1 2026: models' high-end wind above IESO (w_up = max of 9 weather models - IESO wind forecast), known at the bid."""
import pandas as pd, numpy as np
def load(z):
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False); h = h[h.read.notna()].copy()
    h['w_up'] = h.w_hi - h.wind_fc; h['w_upr'] = h.w_up / h.wind_fc.clip(lower=200)
    h['per'] = np.where(h.date < '2026-03-01', 'Sep-Feb', 'Mar-Oct'); h['m'] = h.date.str[:7]; return h
B = [-1e9, 0, 300, 600, 900, 1200, 1e9]; LB = ['<0', '0-300', '300-600', '600-900', '900-1200', '1200+']
for z in ['EAST', 'OTTAWA']:
    h = load(z); s = h.dropna(subset=['rd'])
    print(f'\n===== {z}: all hours, RT-DA by models-high minus IESO wind (MW) =====')
    print(s.groupby([pd.cut(s.w_up, B, labels=LB), 'per'], observed=True).rd.agg(h='size', avg='mean', up=lambda x: (x > 0).mean()).round(2).unstack('per').to_string())
    L = s[s.tier.isin(['A', 'B']) & (s.side > 0)].assign(p=lambda x: x.rd); S = s[s.tier.isin(['A', 'B']) & (s.side < 0)].assign(p=lambda x: -x.rd)
    print('-- our A/B LONGS, $/MWh by w_up --'); print(L.groupby([pd.cut(L.w_up, B, labels=LB), 'per'], observed=True).p.agg(h='size', avg='mean', hit=lambda x: (x > 0).mean()).round(2).unstack('per').to_string())
    print('-- our A/B SHORTS, $/MWh by w_up --'); print(S.groupby([pd.cut(S.w_up, B, labels=LB), 'per'], observed=True).p.agg(h='size', avg='mean').round(2).unstack('per').to_string())

print('\n===== rule variants: change in tiers A+B $/MW vs today (Sep-Feb | Mar-Oct | months better) =====')
def pnl(h, sc):
    s, v = np.sign(sc), np.sign(h.read); t = np.select([(abs(sc) >= 3) & (s == v), abs(sc) >= 3, abs(h.read) >= 5], ['A', 'C', 'B'], 'N')
    side = np.where(abs(sc) >= 3, s, v); return pd.Series(np.where(np.isin(t, ['A', 'B']), side * h.rd.fillna(0), 0), index=h.index), t, side
for z in ['EAST', 'OTTAWA']:
    h = load(z); h = h[h.rd.notna()]; base, t0, s0 = pnl(h, h.score.values)
    print(z, f'today: Sep-Feb {base[h.per=="Sep-Feb"].sum():,.0f} | Mar-Oct {base[h.per=="Mar-Oct"].sum():,.0f}')
    for X in [600, 800, 1000, 1200]:
        p, _, _ = pnl(h, (h.score - (h.w_up >= X)).values); d = p - base; md = d.groupby(h.m).sum()
        print(f'  card -1 when w_up >= {X:4d}: {d[h.per=="Sep-Feb"].sum():+7,.0f} | {d[h.per=="Mar-Oct"].sum():+7,.0f} | months better {(md>0).sum()}/{(md!=0).sum()}')
    for X in [600, 900, 1200]:
        p = base.where(~((s0 > 0) & (h.w_up >= X)), 0); d = p - base; md = d.groupby(h.m).sum()
        print(f'  skip longs when w_up >= {X:4d}: {d[h.per=="Sep-Feb"].sum():+7,.0f} | {d[h.per=="Mar-Oct"].sum():+7,.0f} | months better {(md>0).sum()}/{(md!=0).sum()}')
    for R in [0.5, 1.0]:
        p, _, _ = pnl(h, (h.score - (h.w_upr >= R)).values); d = p - base; md = d.groupby(h.m).sum()
        print(f'  card -1 when models high {R:.0%}+ above IESO: {d[h.per=="Sep-Feb"].sum():+7,.0f} | {d[h.per=="Mar-Oct"].sum():+7,.0f} | months better {(md>0).sum()}/{(md!=0).sum()}')
