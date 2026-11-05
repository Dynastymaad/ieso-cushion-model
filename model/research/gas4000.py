# Nov 5 2026: is it harder to get big RT prints when bid-time gas need is under 4,000 MW? gas_hat = gas need at the bid (load - nuclear - hydro - wind - solar - other + exports).
import pandas as pd, numpy as np
pd.set_option('display.width', 250)
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']); h['yr'] = h.date.str[:4]
    gb = pd.cut(h.gas_hat, [-9e9, 2000, 3000, 4000, 5000, 6000, 7000, 9e9], labels=['<2k', '2-3k', '3-4k', '4-5k', '5-6k', '6-7k', '7k+'])
    f = lambda g: pd.Series(dict(hours=len(g), da=g.da.mean(), rt=g.rt.mean(), rt_da=g.rd.mean(), median=g.rd.median(), up25=100 * (g.rd >= 25).mean(), up50=100 * (g.rd >= 50).mean(),
                                 up100=100 * (g.rd >= 100).mean(), dn25=100 * (g.rd <= -25).mean(), p95=g.rd.quantile(.95), p99=g.rd.quantile(.99), rt100=100 * (g.rt >= 100).mean()))
    print(f'\n=== {z}: RT - DA by bid-time gas need, Sep 2025 - Nov 2026 (up25 = % of hours RT ended $25+ above DA) ===')
    print(h.groupby(gb, observed=True).apply(f).round(1).to_string())
    if z == 'EAST':
        lo = h.gas_hat < 4000
        print('\n-- under 4,000 vs 4,000+, by year and block (% hours RT $50+ above DA | avg RT-DA)')
        for lab, k in [('Sep-Dec 2025', h.yr == '2025'), ('2026', h.yr == '2026')]:
            for b, (a, c) in {'HE1-6': (1, 6), 'HE7-15': (7, 15), 'HE16-21': (16, 21), 'HE22-24': (22, 24)}.items():
                s = k & h.he.between(a, c); x, y = h[s & lo], h[s & ~lo]
                print(f'   {lab:12s} {b:7s} <4k: {len(x):5d} h  up50 {100*(x.rd>=50).mean():4.1f}%  avg {x.rd.mean():6.2f} | 4k+: {len(y):5d} h  up50 {100*(y.rd>=50).mean():4.1f}%  avg {y.rd.mean():6.2f}')
        print('\n-- what the plan did on LONGS and SHORTS (A/B tiers, $/MWh, 1 MW) by gas need')
        ab = h[h.tier.isin(['A', 'B'])].copy(); ab['pl'] = ab.side * ab.rd; ab['g'] = np.where(ab.gas_hat < 4000, '<4k', '4k+')
        print(ab.groupby(['side', 'g']).agg(hours=('pl', 'size'), avg=('pl', 'mean'), total=('pl', 'sum'), right=('pl', lambda s: (s > 0).mean())).round(2).to_string())
        print('\n-- spare check: of hours with gas need <4k, share with public spare 2,500+:', f'{100*(h.pub_sp[lo] >= 2500).mean():.0f}%', '| thin-spare (<2,500) hours with gas <4k:', int(((h.pub_sp < 2500) & lo).sum()))
