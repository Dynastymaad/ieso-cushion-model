"""cahr_ladder.py -- ladder-level test: does pricing the A-grade sells (tight & CAHR >= 12) more aggressively,
or the other sells less aggressively, make more money? Offers clear if actual DA >= offer. P&L = MW x (DA - RT)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV

def run(t, fn):
    pl, mw, rows = 0.0, 0, []
    for r in t.itertuples():
        _, sell = DV.ladder(5, r.p_da, r.p_rt); sell = fn(r, sell)
        q = sum(a for a, p in sell if p is not None and r.da >= p); rows.append((r.date, q * (r.da - r.rt), q))
    x = pd.DataFrame(rows, columns=['date', 'pl', 'mw'])
    h1 = x[x.date < '2026-02-15']; h2 = x[x.date >= '2026-02-15']; l9 = x[x.date >= '2026-07-08']
    f = lambda y: round(y.pl.sum() / max(y.mw.sum(), 1), 2)
    return dict(total=round(x.pl.sum()), mwh=int(x.mw.sum()), usd_mwh=f(x), H1_total=round(h1.pl.sum()), H2_total=round(h2.pl.sum()), last90_total=round(l9.pl.sum()), H1=f(h1), H2=f(h2))

same = lambda r, s: s
def shift(d): return lambda r, s: [(q, None if p is None else p + d) for q, p in s]
def floor_rt(k): return lambda r, s: [(q, None if p is None else int(round(min(p, r.p_rt * k)))) for q, p in s]
R = []
for z in ('EAST', 'OTTAWA'):
    f = pd.read_csv(C.DATA / f'cahr_frame_{z}.csv').merge(pd.read_csv(C.DATA / f'dv_frame_{z}.csv')[['date', 'he', 'p_rt']], on=['date', 'he'])
    f = f.dropna(subset=['p_da', 'p_rt', 'da', 'rt'])
    A = f[(f.why == 'tight') & (f.cahr >= 12)]; Bt = f[(f.why == 'tight') & (f.cahr < 12)]; S = f[f.why == 'surplus']
    for name, t in (('A-grade tight (CAHR>=12)', A), ('B tight (CAHR<12)', Bt), ('surplus', S)):
        for lab, fn in (('current ladder', same), ('all tiers -$5', shift(-5)), ('all tiers -$10', shift(-10)), ('cap tiers at 0.9 x RT fc', floor_rt(0.9)), ('all tiers +$5', shift(5)), ('all tiers +$10', shift(10))):
            R.append(dict(zone=z, group=name, hours=len(t), pricing=lab, **run(t, fn)))
R = pd.DataFrame(R); R.to_csv(C.DATA / 'cahr_ladder_2026-10-07.csv', index=False)
pd.set_option('display.width', 220); print(R.to_string(index=False))
