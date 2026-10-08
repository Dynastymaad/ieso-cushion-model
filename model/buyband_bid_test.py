"""buyband_bid_test.py -- Oct 7 2026: are the buy-band (score 1) bids too low? Bids clear if actual DA <= bid; P&L = MW x (RT - DA).
Buy band rebuilt as live (120-day walk-forward, sell hours excluded). Sep 2025 -> Oct 6 2026. Base ladder = VA score-1:
bids [min(DA fc x1.20, RT fc x1.10), RT fc x0.95, RT fc x0.85] for 40/30/20 MW. Variants shift all bids by +$X,
or reshape the tiers. 'Marginal' = MWh that clear at this step but not the previous one (is the extra MW still profitable?)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV

def bids(r, how):
    b, _ = DV.ladder(1, r.p_da, r.p_rt)
    if how[0] == 'shift': return [(q, p + how[1]) for q, p in b]
    if how[0] == 'taker': return [(q, 1e9) for q, p in b]
    if how[0] == 'shape':   # tiers at RT fc x k1/k2/k3 (top tier still capped by DA fc x1.2)
        k = how[1]; return [(q, max(p, round(r.p_rt * kk))) for (q, p), kk in zip(b, k)]

def run(t, how):
    rows = []
    for r in t.itertuples():
        q = sum(a for a, p in bids(r, how) if r.da <= p); rows.append((r.date, r.he, q, q * (r.rt - r.da)))
    return pd.DataFrame(rows, columns=['date', 'he', 'mw', 'pl'])

def summ(x, name, prev=None):
    dd = x.groupby('date').pl.sum(); per = lambda y: round(y.pl.sum() / max(y.mw.sum(), 1), 2)
    o = dict(variant=name, mwh=int(x.mw.sum()), total=round(x.pl.sum()), usd_mwh=per(x),
             H1=round(x[x.date < '2026-02-15'].pl.sum()), H2=round(x[x.date >= '2026-02-15'].pl.sum()), last90=round(x[x.date >= '2026-07-08'].pl.sum()),
             worst_day=round(dd.min()), days_up=round((dd > 0).mean() * 100))
    if prev is not None:   # marginal MWh vs previous step
        d = x.assign(dmw=x.mw - prev.mw.values, dpl=x.pl - prev.pl.values)
        o.update(marg_mwh=int(d.dmw.sum()), marg_usd_mwh=round(d.dpl.sum() / max(d.dmw.sum(), 1), 2),
                 marg_H1=round(d[d.date < '2026-02-15'].dpl.sum()), marg_H2=round(d[d.date >= '2026-02-15'].dpl.sum()), marg_l90=round(d[d.date >= '2026-07-08'].dpl.sum()))
    return o

R = []
for z in ('EAST', 'OTTAWA'):
    f = pd.read_csv(C.DATA / f'cahr_frame_{z}.csv').merge(pd.read_csv(C.DATA / f'dv_frame_{z}.csv')[['date', 'he', 'p_rt']], on=['date', 'he'])
    t = f[f.why.isna() & (f.buyband == -1)].dropna(subset=['p_da', 'p_rt', 'da', 'rt']).reset_index(drop=True)
    prev = None
    for name, how in [('current', ('shift', 0))] + [(f'all bids +${k}', ('shift', k)) for k in (5, 10, 15, 20, 30)] + [('price-taker (always clear)', ('taker',))]:
        x = run(t, how); R.append(dict(zone=z, hours=len(t), **summ(x, name, prev))); prev = x
    for name, k in (('tiers RT x 1.10/1.00/0.95', (1.10, 1.00, 0.95)), ('tiers RT x 1.15/1.05/1.00', (1.15, 1.05, 1.00))):
        R.append(dict(zone=z, hours=len(t), **summ(run(t, ('shape', k)), name)))
R = pd.DataFrame(R); R.to_csv(C.DATA / 'buyband_bid_test_2026-10-07.csv', index=False)
pd.set_option('display.width', 250); print(R.to_string(index=False))
