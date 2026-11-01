"""research/scenario_2026.py -- Oct 31 2026 (TEST ONLY). 2026 data only (the market changed).
Learn on Jan-Sep 2026 which bid-time fundamentals decide the outcome inside each market-read scenario, then read October 2026 BLIND
(fundamentals only), and only afterwards score those October reads against settlements."""
import sys, warnings; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd, common as C, market_read as MR
pd.set_option('display.width', 240); pd.set_option('display.max_columns', 40)

def frame(z):
    e = MR.history(z); e = e[e.date >= '2026-01-01'].copy().sort_values(['date', 'he'])
    g = e.groupby('date')
    e['w3'] = e.wind_fc - g.wind_fc.shift(3)                              # IESO wind change into the hour (- = falling)
    e['res3'] = e.resid_fc - g.resid_fc.shift(3)                          # net-load ramp
    e['vs'] = e.p_da - e.groupby('he').p_da.transform(lambda s: s.shift(1).rolling(14, min_periods=5).median())   # DA fc vs usual
    e['blk'] = pd.cut(e.he, [0, 6, 9, 15, 19, 24], labels=['HE1-6', 'HE7-9', 'HE10-15', 'HE16-19', 'HE20-24'])
    e['scen'] = np.select([e.cell == 'FEAR -> RESCUE', e.cell == 'FEAR + DANGER', e.cell == 'CALM -> DANGER'], ['scared+rescue', 'scared+danger', 'calm+danger'], 'other')
    return e

FAC = {'rescue': 'rescue MW (+ looser)', 'd_load': 'best load - IESO', 'd_wind': 'best wind - IESO', 'w_spread': 'wind models spread', 'pub_sp': 'public spare',
       'valve': 'valves', 'w3': 'IESO wind 3h change', 'res3': 'net-load 3h ramp', 'vs': 'DA fc vs usual', 'crowd1': 'crowd yday (+ short)', 'head': 'headroom'}

def drivers(t, side):
    """for each factor: long P&L (RT-DA) in its bottom vs top third, Jan-Jun vs Jul-Sep (consistency)."""
    rows = []
    for f, nm in FAC.items():
        d = t.dropna(subset=[f])
        if len(d) < 90: continue
        q = d[f].quantile([1 / 3, 2 / 3]).values; lo, hi = d[d[f] <= q[0]], d[d[f] >= q[1]]
        a = lambda x: (x.rt - x.da).mean()
        h1 = lambda x: a(x[x.date < '2026-07-01']); h2 = lambda x: a(x[x.date >= '2026-07-01'])
        rows.append(dict(factor=nm, low_third=f'<= {q[0]:,.0f}', rtda_low=round(a(lo), 1), high_third=f'>= {q[1]:,.0f}', rtda_high=round(a(hi), 1), gap=round(a(hi) - a(lo), 1),
                         gap_H1=round(h1(hi) - h1(lo), 1), gap_Q3=round(h2(hi) - h2(lo), 1)))
    r = pd.DataFrame(rows); r['consistent'] = np.sign(r.gap_H1) == np.sign(r.gap_Q3); return r.reindex(r.gap.abs().sort_values(ascending=False).index)

if __name__ == '__main__':
    for z in ('EAST',):
        e = frame(z); tr = e[e.date < '2026-10-01']
        print(f'===== {z} 2026 Jan-Sep: scenario outcomes (RT - DA, + = longs win) =====')
        print(tr.groupby('scen').apply(lambda g: pd.Series(dict(hours=len(g), rt_da_mean=(g.rt - g.da).mean(), rt_da_median=(g.rt - g.da).median(), rt_gt_da=((g.rt > g.da).mean() * 100),
              spike25=((g.rt - g.da >= 25).mean() * 100), avg_when_spike=(g.rt - g.da)[g.rt - g.da >= 25].mean(), collapse=((g.rt - g.da <= -20).mean() * 100), avg_when_collapse=(g.rt - g.da)[g.rt - g.da <= -20].mean()))).round(1).to_string())
        for s in ('scared+rescue', 'scared+danger', 'calm+danger'):
            t = tr[tr.scen == s]; print(f'\n--- {s} ({len(t)} h): what decides it (long P&L RT-DA in the bottom vs top third of each factor) ---')
            print(drivers(t, s).to_string(index=False))
            print('   by block:', t.groupby('blk').apply(lambda g: f'{len(g)}h {(g.rt-g.da).mean():+.1f}').to_dict())
            print('   crowd:', t.groupby(np.where(t.crowd1 <= -40, 'crowd long', 'crowd not long')).apply(lambda g: f'{len(g)}h {(g.rt-g.da).mean():+.1f} RT>DA {(g.rt>g.da).mean()*100:.0f}%').to_dict())
        e.to_csv(C.DATA / 'research' / f'scenario_2026_{z}.csv', index=False)
