"""Tier record, bands and soft-flag record from physics_history (daily refit, starred gaps) -> data/research/physics_tiers_test.json"""
import pandas as pd, numpy as np, json
res, bands = {}, {}
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv').dropna(subset=['rd']); h['m'] = h.date.str[:7]
    h['p'] = np.where(h.tier == 'C', np.sign(h.score), np.where(h.tier == 'N', np.sign(h.read), h.side)) * h.rd; ab = h.tier.isin(['A', 'B']); h['pnl'] = np.where(ab, h.p, 0); d = h.groupby('date').pnl.sum()
    g = h.groupby('tier').agg(h=('p', 'size'), avg=('p', 'mean'), hit=('p', lambda x: (x > 0).mean())); g['share'] = g.h / len(h)
    soft = h[h.soft]; nonsoft_long = h[ab & (h.side > 0) & ~h.soft]
    per = {}
    for lab, k in [('Sep 2025 - Feb 2026', h[h.date < '2026-03-01']), ('Mar - Oct 2026', h[h.date >= '2026-03-01'])]:
        t = k.tier.isin(['A', 'B']); per[lab] = dict(total=round(float(k.pnl.sum())), per=round(float(k.pnl[t].mean()), 2), months=f"{(k.groupby('m').pnl.sum()>0).sum()}/{k.m.nunique()}")
    res[z] = dict(period=f'{h.date.min()} to {h.date.max()}', tiers={t: dict(h=int(v.h), avg=round(float(v.avg), 2), hit=round(float(v.hit), 3), share=round(float(v.share), 3)) for t, v in g.iterrows()},
                  plan=dict(share=round(float(ab.mean()), 3), avg=round(float(h.pnl[ab].mean()), 2), hit=round(float((h.pnl[ab] > 0).mean()), 3), total=round(float(h.pnl.sum())),
                            months=f"{(h.groupby('m').pnl.sum()>0).sum()}/{h.m.nunique()}", worst=round(float(d.min())), july=round(float(h.pnl[h.m == '2026-07'].sum()))),
                  periods=per, soft=dict(h=int(len(soft)), up=round(float((soft.rd > 0).mean()) * 100) if len(soft) else None, avg=round(float(soft.rd.mean()), 1) if len(soft) else None,
                                         med=round(float(soft.rd.median()), 1) if len(soft) else None, other_long_up=round(float((nonsoft_long.rd > 0).mean()) * 100), other_long_avg=round(float(nonsoft_long.rd.mean()), 1)))
    v = h.read; bands[z] = h.groupby(pd.cut(v, [-1e9, -5, -1.5, 1.5, 5, 1e9], labels=['strong short', 'lean short', 'neutral', 'lean long', 'strong long']), observed=True).rd.agg(
        h='size', avg='mean', up=lambda x: (x > 0).mean(), spike=lambda x: (x >= 25).mean(), drop=lambda x: (x <= -25).mean()).round(3).reset_index().rename(columns={'read': 'band'}).to_dict('records')
    print(z, json.dumps(res[z], indent=0)[:1500])
json.dump(res, open('data/research/physics_tiers_test.json', 'w')); json.dump(bands, open('data/research/physics_bands.json', 'w'), default=str)
