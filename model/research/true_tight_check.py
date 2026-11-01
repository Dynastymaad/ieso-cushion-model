"""research/true_tight_check.py -- is the priced-minus-fundamental gap more than 'short when DA is expensive'?
Same number of hours, picked by: the gap (gbm / linear), the DA forecast level, DA forecast vs usual, the DA forecast's heat rate (CAHR)."""
import sys; sys.path.insert(0, 'model')
import numpy as np, pandas as pd
pd.set_option('display.width', 240)
for z in ('EAST', 'OTTAWA'):
    t = pd.read_csv(f'data/research/true_tight_{z}.csv'); t['m'] = t.date.str[:7]
    print(f'\n===== {z} {t.date.min()}..{t.date.max()} =====')
    for n in (180, 400, 900):
        row = []
        for nm, col in (('gap (gbm)', 'gap'), ('gap (linear)', 'gap_lin'), ('DA fc level', 'p_da'), ('DA fc vs usual', 'vs'), ('DA fc heat rate', 'hr_fc')):
            k = t.nlargest(n, col); p = k.da - k.rt; mo = p.groupby(k.m).mean()
            row.append(f'{nm}: ${p.mean():+.1f} win {(p>0).mean()*100:.0f}% months+ {(mo>0).sum()}/{len(mo)}')
        print(f'SHORT top {n} h -> ' + ' | '.join(row))
    for n in (300, 900, 2000):
        row = []
        for nm, col in (('gap (gbm)', 'gap'), ('gap (linear)', 'gap_lin'), ('DA fc vs usual', 'vs'), ('DA fc heat rate', 'hr_fc')):
            k = t.nsmallest(n, col); p = k.rt - k.da; mo = p.groupby(k.m).mean()
            row.append(f'{nm}: ${p.mean():+.1f} win {(p>0).mean()*100:.0f}% months+ {(mo>0).sum()}/{len(mo)}')
        print(f'LONG bottom {n} h -> ' + ' | '.join(row))
    # does the gap add anything once you know DA is expensive? within the top third of DA fc heat rate, split by gap
    hi = t[t.hr_fc >= t.hr_fc.quantile(2 / 3)]
    for col in ('gap', 'gap_lin'):
        b = pd.qcut(hi[col], 3, labels=['gap low', 'gap mid', 'gap high'])
        print(f'   expensive-DA hours split by {col}:', hi.groupby(b).apply(lambda g: f'{len(g)}h shorts ${(g.da-g.rt).mean():+.1f} win {((g.da-g.rt)>0).mean()*100:.0f}%').to_dict())
    lo = t[t.hr_fc <= t.hr_fc.quantile(1 / 3)]
    for col in ('gap', 'gap_lin'):
        b = pd.qcut(lo[col], 3, labels=['gap low', 'gap mid', 'gap high'])
        print(f'   cheap-DA hours split by {col}:', lo.groupby(b).apply(lambda g: f'{len(g)}h longs ${(g.rt-g.da).mean():+.1f} win {((g.rt-g.da)>0).mean()*100:.0f}%').to_dict())
