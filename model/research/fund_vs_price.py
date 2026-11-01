"""Do spare-gap and stress percentile add information beyond what DA already priced? 2026, bid-time inputs only.
'Goes south' = RT-DA >= +25 (a short gets hurt) or <= -25 (a long gets hurt)."""
import pandas as pd, numpy as np, sys
z = sys.argv[1] if len(sys.argv) > 1 else 'EAST'
e = pd.read_csv(f'data/research/stress_{z}_extra.csv'); e['rd'] = e.rt - e.da; e = e.dropna(subset=['rd', 'gbm', 'vs'])
e['half'] = np.where(e.date < '2026-07-01', 'Mar-Jun', 'Jul-Oct')
# stress percentile: rank of today's walk-forward score inside the trailing 60 days of scores (no look-ahead)
e = e.sort_values(['date', 'he']); days = sorted(e.date.unique()); pct = []
for D in days:
    past = e[(e.date < D) & (e.date >= str((pd.Timestamp(D) - pd.Timedelta(days=60)).date()))].gbm.values
    cur = e[e.date == D].gbm.values
    pct += list((np.searchsorted(np.sort(past), cur) / max(len(past), 1) * 100) if len(past) > 200 else [np.nan] * len(cur))
e['spct'] = pct; e = e.dropna(subset=['spct'])
e['priced'] = pd.cut(e.vs, [-1e9, -5, 18, 1e9], labels=['DA cheap (vs<=-5)', 'DA normal', 'DA rich (vs>=18)'])
e['gap'] = pd.cut(-e.rescue, [-1e9, -300, 300, 1e9], labels=['ours looser 300+', 'agree', 'ours tighter 300+'])
e['stress'] = pd.cut(e.spct, [-1, 20, 80, 101], labels=['stress low (<20)', 'mid', 'stress high (>80)'])
def tab(by):
    g = e.groupby(['priced', by, 'half'], observed=True).rd
    t = pd.DataFrame({'h': g.size(), 'RT-DA': g.mean().round(1), 'up%': g.apply(lambda x: (x > 0).mean() * 100).round(0),
                      'spike+25%': g.apply(lambda x: (x >= 25).mean() * 100).round(0), 'drop-25%': g.apply(lambda x: (x <= -25).mean() * 100).round(0)})
    return t.unstack('half')
print(f'===== {z}  hours {len(e)}  base RT-DA {e.rd.mean():+.1f}  spike+25 {(e.rd>=25).mean():.0%}  drop-25 {(e.rd<=-25).mean():.0%}')
for by in ['gap', 'stress']:
    print(f'\n--- DA priced x {by} ---'); print(tab(by).to_string())
# information test: does adding gap/stress to 'priced' improve hourly ranking of RT-DA, on the half it never saw?
from scipy.stats import spearmanr
for h in ['Mar-Jun', 'Jul-Oct']:
    s = e[e.half == h]; base = s.groupby('priced', observed=True).rd.transform('mean')
    out = {}
    for by in ['gap', 'stress']:
        other = e[e.half != h]; m = other.groupby(['priced', by], observed=True).rd.mean()   # cell means learned on the OTHER half
        pred = pd.Series([m.get((a, b), np.nan) for a, b in zip(s.priced, s[by])], index=s.index)
        out[by] = spearmanr(pred, s.rd, nan_policy='omit')[0]
    pm = e[e.half != h].groupby('priced', observed=True).rd.mean(); pp = s.priced.map(pm).astype(float)
    print(f'{h}: rank corr with RT-DA using cell means from the other half -> DA priced only {spearmanr(pp, s.rd)[0]:.2f} | +spare gap {out["gap"]:.2f} | +stress {out["stress"]:.2f}')
