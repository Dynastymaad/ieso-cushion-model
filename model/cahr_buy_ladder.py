"""cahr_buy_ladder.py -- buy band (score 1) ladder by CAHR: does bidding higher/lower or skipping by CAHR make more money?
Bids clear if actual DA <= bid. P&L = MW x (RT - DA). Same split as the sells: CAHR >= 10 vs < 10 (peaker line)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV

def run(t, d):
    rows = []
    for r in t.itertuples():
        buy, _ = DV.ladder(1, r.p_da, r.p_rt)
        q = 0 if d is None else sum(a for a, p in buy if p is not None and r.da <= p + d); rows.append((r.date, q * (r.rt - r.da), q))
    x = pd.DataFrame(rows, columns=['date', 'pl', 'mw']); f = lambda y: round(y.pl.sum())
    return dict(total=f(x), mwh=int(x.mw.sum()), H1=f(x[x.date < '2026-02-15']), H2=f(x[x.date >= '2026-02-15']), last90=f(x[x.date >= '2026-07-08']))
R = []
for z in ('EAST', 'OTTAWA'):
    f = pd.read_csv(C.DATA / f'cahr_frame_{z}.csv').merge(pd.read_csv(C.DATA / f'dv_frame_{z}.csv')[['date', 'he', 'p_rt']], on=['date', 'he'])
    f = f[f.why.isna() & (f.buyband == -1)].dropna(subset=['p_da', 'p_rt', 'da', 'rt'])
    for name, t in (('buy band, CAHR >= 10', f[f.cahr >= 10]), ('buy band, CAHR < 10', f[f.cahr < 10]), ('buy band, CAHR < 7.5', f[f.cahr < 7.5])):
        for lab, d in (('current', 0), ('bids -$10', -10), ('bids -$5', -5), ('bids +$5', 5), ('bids +$10', 10), ('skip', None)):
            R.append(dict(zone=z, group=name, hours=len(t), bids=lab, **run(t, d)))
R = pd.DataFrame(R); R.to_csv(C.DATA / 'cahr_buy_ladder_2026-10-07.csv', index=False); pd.set_option('display.width', 200); print(R.to_string(index=False))
