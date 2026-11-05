"""onpeak_price2.py -- is the on-peak card too high, when, and can a calibrated range be built from out-of-sample errors only?"""
import numpy as np, pandas as pd
pd.set_option('display.width', 220)
X = pd.read_csv('data/research/onpeak_price.csv'); X['err'] = X.card - X.y; X['dow'] = pd.to_datetime(X.date).dt.dayofweek
print('== card (East P50 average, as on the Next day tab) minus XDE settle, by period ==')
for lab, x in [('2025', X[X.date < '2026-01-01']), ('Jan-Jun 26', X[(X.date >= '2026-01-01') & (X.date < '2026-07-01')]), ('Jul-Oct 26', X[(X.date >= '2026-07-01')]),
               ('last 60 d', X.tail(60)), ('last 30 d', X.tail(30))]:
    print(f'{lab:11s} days {len(x):3d}  bias {x.err.mean():+5.2f}  median {x.err.median():+5.2f}  MAE {x.err.abs().mean():5.2f}  card above settle {(x.err > 0).mean() * 100:3.0f}%')
x = X[X.date >= '2026-01-01']
print('\n-- 2026 by card level --'); print(x.groupby(pd.cut(x.card, [0, 45, 55, 65, 75, 90, 999]), observed=True).err.agg(['size', 'mean', 'median', lambda s: (s > 0).mean() * 100]).round(1).to_string())
print('\n-- 2026 by day of week (0=Mon) --'); print(x.groupby('dow').err.agg(['size', 'mean', 'median']).round(1).to_string())
print('\n-- 2026 by yesterday-settle vs card (card above the last known settle = calling a move up) --')
x = x.assign(mv=x.card - x.persist); print(x.groupby(pd.cut(x.mv, [-999, -10, -4, 4, 10, 999]), observed=True).err.agg(['size', 'mean', 'median', lambda s: (s > 0).mean() * 100]).round(1).to_string())
# out-of-sample range: for each day, quantiles of the card's own errors over the trailing 60 settled days (through D-2)
for base in ('card', 'card_bc', 'blend'):
    rows = []
    for i, r in X.iterrows():
        cut = (pd.Timestamp(r.date) - pd.Timedelta(days=2)).date().isoformat(); t = X[X.date <= cut].tail(60)
        if len(t) < 40 or pd.isna(r[base]): continue
        e = (t[base] - t.y).dropna(); qs = np.quantile(-e, [.1, .25, .5, .75, .9])     # settle = base + (-err)
        rows.append(dict(date=r.date, y=r.y, **{f'q{k}': r[base] + v for k, v in zip((10, 25, 50, 75, 90), qs)}))
    Q = pd.DataFrame(rows); Q26 = Q[Q.date >= '2026-01-01']
    print(f'\n== {base} + trailing-60-day error range, 2026 ({len(Q26)} days): share of settles below each line (want 10/25/50/75/90) ==')
    print({k: round((Q26.y < Q26[k]).mean() * 100) for k in ('q10', 'q25', 'q50', 'q75', 'q90')}, '| median-line MAE', round((Q26.q50 - Q26.y).abs().mean(), 2), 'bias', round((Q26.q50 - Q26.y).mean(), 2))
    Q.to_csv(f'data/research/onpeak_range_{base}.csv', index=False)
