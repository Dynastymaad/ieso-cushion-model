# Nov 5 2026: does bidding at a price pick the wrong hours? A buy fills only if DA clears at or below the bid; a sell only if DA clears at or above the offer.
import pandas as pd, numpy as np
pd.set_option('display.width', 250)
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd', 'da_fc'])
    t = h[h.tier.isin(['A', 'B'])].copy(); t['pl'] = t.side * t.rd; t['dmiss'] = t.da - t.da_fc     # + = DA cleared above our forecast
    print(f'\n===== {z}: {len(t)} traded hours (A/B), {t.date.min()}..{t.date.max()} | price-taker total ${t.pl.sum():,.0f}')
    print('-- RT-DA result by where DA cleared vs our bid-time DA forecast')
    b = pd.cut(t.dmiss, [-999, -20, -10, -5, 0, 5, 10, 20, 999])
    print(t.groupby(['side', b], observed=True).agg(hours=('pl', 'size'), pl_per_h=('pl', 'mean'), right=('pl', lambda s: (s > 0).mean())).round(2).unstack(0).to_string())
    print('-- What price-sensitive bids would have made (buy fills if DA <= bid, sell fills if DA >= offer)')
    for off in [-10, -5, 0, 5, 10, 20, 999]:
        lim = t.da_fc + np.where(t.side > 0, off, -off)
        fill = np.where(t.side > 0, t.da <= lim, t.da >= lim) if off < 999 else np.ones(len(t), bool)
        lab = 'price taker (always fills)' if off == 999 else f'buy at fc{off:+d} / sell at fc{-off:+d}'
        k = t[fill]; n = t[~fill]
        print(f'   {lab:30s} fills {100*fill.mean():4.0f}% | filled ${k.pl.sum():8,.0f} (${k.pl.mean():+.2f}/h) | NOT filled would have made ${n.pl.sum():8,.0f} (${n.pl.mean() if len(n) else 0:+.2f}/h)')
