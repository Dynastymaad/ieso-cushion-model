"""buyband_deep.py -- Oct 7 2026 deep check of raising buy-band bids (buyband_bid_test.py). Questions:
 1 is the gain a handful of spike days?  2 how sure (day bootstrap)?  3 which hours / months?  4 does it survive capping RT spikes?
 5 what do the extra clears look like?  6 is it the buy band, or would bidding up win anywhere (control)?"""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV
pd.set_option('display.width', 250)

def run(t, d, rtcap=None):
    out = []
    for r in t.itertuples():
        buy, _ = DV.ladder(1, r.p_da, r.p_rt); rt = min(r.rt, rtcap) if rtcap else r.rt
        q = sum(a for a, p in buy if (d is None) or r.da <= p + d); out.append((q, q * (rt - r.da)))
    return pd.DataFrame(out, columns=['mw', 'pl'], index=t.index)

V = {'current': 0, '+$20': 20, '+$30': 30, 'always': None}
for z in ('EAST', 'OTTAWA'):
    f = pd.read_csv(C.DATA / f'cahr_frame_{z}.csv').merge(pd.read_csv(C.DATA / f'dv_frame_{z}.csv')[['date', 'he', 'p_rt']], on=['date', 'he'])
    f = f.dropna(subset=['p_da', 'p_rt', 'da', 'rt'])
    t = f[f.why.isna() & (f.buyband == -1)].reset_index(drop=True)
    X = {k: run(t, d) for k, d in V.items()}
    print(f'\n================ {z}: {len(t)} buy-band hours, {t.date.nunique()} days ================')
    # 1+2 concentration & bootstrap, incremental vs current
    rng = np.random.default_rng(7); rows = []
    for k in ('+$20', '+$30', 'always'):
        inc = (X[k].pl - X['current'].pl).groupby(t.date).sum().sort_values(ascending=False)
        bs = [inc.values[rng.integers(0, len(inc), len(inc))].sum() for _ in range(3000)]
        rows.append(dict(vs_current=k, gain=round(inc.sum()), days=len(inc), days_up=int((inc > 0).sum()), days_down=int((inc < 0).sum()),
                         top5_share=f'{inc.head(5).sum()/inc.sum()*100:.0f}%', gain_ex_top10=round(inc.iloc[10:].sum()), worst5_days=round(inc.tail(5).sum()),
                         ci90=f'{np.percentile(bs,5):+,.0f} .. {np.percentile(bs,95):+,.0f}', p_loss=f'{(np.array(bs)<0).mean()*100:.1f}%'))
    print('1-2) incremental gain vs current bids (by day):'); print(pd.DataFrame(rows).to_string(index=False))
    # 3 hour blocks and months
    blk = pd.cut(t.he, [0, 6, 16, 22, 24], labels=['HE1-6', 'HE7-16', 'HE17-22', 'HE23-24'])
    g = pd.DataFrame({k: X[k].pl.groupby(blk, observed=True).sum().round() for k in V}); g['hours'] = blk.value_counts()
    g['+$30 vs cur'] = g['+$30'] - g['current']; print('3a) by hour block, total $:'); print(g.to_string())
    mo = t.date.str[:7]
    g = pd.DataFrame({k: X[k].pl.groupby(mo).sum().round() for k in V}); g['hours'] = mo.value_counts(); g['+$30 vs cur'] = g['+$30'] - g['current']
    print('3b) by month:'); print(g.to_string())
    # 4 spike robustness
    rows = []
    for cap in (None, 200, 150, 100):
        Y = {k: run(t, d, cap) for k, d in V.items()}
        rows.append(dict(RT_capped_at=cap or 'none', **{k: round(Y[k].pl.sum()) for k in V}, gain_30=round(Y['+$30'].pl.sum() - Y['current'].pl.sum())))
    print('4) RT spikes capped (total $):'); print(pd.DataFrame(rows).to_string(index=False))
    # 5 the extra clears (+$30 not current), per hour: what are they?
    ex = (X['+$30'].mw > X['current'].mw); e2 = t[ex].assign(sp=lambda q: q.rt - q.da, sur=lambda q: q.da - q.p_da)
    base = t[X['current'].mw > 0].assign(sp=lambda q: q.rt - q.da, sur=lambda q: q.da - q.p_da)
    for n, q in (('already clear at current bids', base), ('extra hours cleared by +$30', e2)):
        print(f'5) {n}: {len(q)} h | DA - our DA fc median {q.sur.median():+.1f} | RT-DA mean {q.sp.mean():+.2f}, median {q.sp.median():+.2f}, RT>DA {(q.sp>0).mean()*100:.0f}%, '
              f'5th pct {q.sp.quantile(.05):+.1f}, 95th {q.sp.quantile(.95):+.1f} | H2 mean {q[q.date>="2026-02-15"].sp.mean():+.2f} | last90 mean {q[q.date>="2026-07-08"].sp.mean():+.2f} ({(q.date>="2026-07-08").sum()} h)')
    # 6 control: same +$30 on hours with NO signal (not band, not sell): if it also wins, the effect is generic
    nt = f[f.why.isna() & (f.buyband == 0) & (f.date >= t.date.min())].reset_index(drop=True)
    Xc = {k: run(nt, d) for k, d in V.items()}
    print(f'6) CONTROL no-signal hours ({len(nt)} h), buy ladder total $: ' + ', '.join(f'{k} {Xc[k].pl.sum():+,.0f}' for k in V)
          + f' | H2 +$30 {Xc["+$30"].pl[nt.date>="2026-02-15"].sum():+,.0f} vs current {Xc["current"].pl[nt.date>="2026-02-15"].sum():+,.0f}')
