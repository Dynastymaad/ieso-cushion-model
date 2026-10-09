"""book_days.py -- Oct 8 2026: daily P&L shape of the live book (tight + surplus sells, buy band, all on the live ladders incl. CAHR
repricing) and of Spike Watch. Base ladder MW (sells 20/30/40, buys 40/30/20). Sep 12 2025 -> Oct 6 2026."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV, tesla_rules_bt as TB
pd.set_option('display.width', 250)
def leg(r, cahr_on=True):
    if r.why == 'tight': return TB.sell_pl(r) if cahr_on else sum(q for q, p in DV.ladder(5, r.p_da, r.p_rt)[1] if p is not None and r.da >= p) * (r.da - r.rt)
    if r.why == 'surplus': return sum(q for q, p in DV.ladder(5, r.p_da, r.p_rt)[1] if p is not None and r.da >= p) * (r.da - r.rt)
    if r.buyband == -1: return sum(q for q, p in DV.ladder(1, r.p_da, r.p_rt)[0] if p is not None and r.da <= p) * (r.rt - r.da)
    return 0.0
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv'); m = m[(m.date >= '2025-09-12') & (m.date <= '2026-10-06') & m.rt.notna() & m.p_rt.notna()].copy()
    m['cahr'] = m.cahr.fillna(0); m['pl'] = [leg(r) for r in m.itertuples()]; m['pl0'] = [leg(r, False) for r in m.itertuples()]
    m['kind'] = np.where(m.why == 'tight', 'tight', np.where(m.why == 'surplus', 'surplus', np.where(m.buyband == -1, 'band', '-')))
    d = m.groupby('date').pl.sum(); d = d[m.groupby('date').pl.apply(lambda s: (s != 0).any())]
    q = d.quantile([.05, .1, .25, .5, .75, .9, .95]).round(0).to_dict()
    print(f'\n=========== {z}: live book, {len(d)} trading days ===========')
    print(f'total ${d.sum():,.0f} | mean day ${d.mean():,.0f} | median day ${d.median():,.0f} | days up {(d>0).mean()*100:.0f}% | avg up day ${d[d>0].mean():,.0f} | avg down day ${d[d<0].mean():,.0f}')
    print('day percentiles:', q)
    print(f'best 10 days ${d.nlargest(10).sum():,.0f} | worst 10 days ${d.nsmallest(10).sum():,.0f} | total without worst 10 ${d.sum()-d.nsmallest(10).sum():,.0f}')
    print('by leg: total', m.groupby('kind').pl.sum().round(0).to_dict(), '| worst-10-day losses by leg', m[m.date.isin(d.nsmallest(10).index)].groupby('kind').pl.sum().round(0).to_dict())
    w = m[m.date.isin(d.nsmallest(8).index)]
    for D, g in w.groupby('date'):
        bad = g.nsmallest(3, 'pl')
        print(f'  {D} day ${g.pl.sum():,.0f}: ' + '; '.join(f"HE{int(r.he)} {r.kind} DA {r.da:.0f} RT {r.rt:.0f} head {r['head']:.0f} ${r.pl:,.0f}" for _, r in bad.iterrows()))
    d0 = m.groupby('date').pl0.sum(); print(f'without CAHR repricing: total ${d0.sum():,.0f}, worst day ${d0.min():,.0f}, worst 10 ${d0.nsmallest(10).sum():,.0f}')
    # tail by hour type: tight evening hours by DA forecast level
    te = m[(m.kind == 'tight') & m.he.between(16, 21)]; te['b'] = pd.cut(te.p_da, [0, 70, 85, 100, 999])
    print('tight evening sells by DA fc:', te.groupby('b', observed=True).agg(h=('pl', 'size'), total=('pl', 'sum'), worst_hr=('pl', 'min'), lose20k=('pl', lambda s: (s < -20000).sum())).round(0).to_dict('index'))
