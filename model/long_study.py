"""long_study.py -- why the model cannot find the long (buy) hours. Walk-forward, bid-time inputs only.
buy P&L = RT - DA."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, edge_study as E
pd.set_option('display.width', 230); pd.set_option('display.max_rows', 200)
z = sys.argv[1] if len(sys.argv) > 1 else 'TORONTO'
w = pd.read_csv(C.DATA / f'bt_signals_v2_{z}.csv')
b = E.base(z)
w = w.merge(b[['date', 'he', 'rt']].rename(columns={'rt': 'rt_'}), on=['date', 'he'], how='left')
w['bu'] = -w.sp
# D-1 morning RT-DA (HE1-8 of D-1 settle before the 10:00 EPT deadline)
m = b[b.he <= 8].groupby('date').sp.mean().rename('m1').reset_index(); m['date'] = (pd.to_datetime(m.date) + pd.Timedelta(days=1)).dt.date.astype(str)
w = w.merge(m, on='date', how='left'); w['m1'] = -w.m1
w['gband'] = pd.cut(w.gas_hat, [-9e9, 3000, 4000, 5000, 6000, 7000, 9e9], labels=['<3k', '3-4k', '4-5k', '5-6k', '6-7k', '>7k'])
w['blk'] = w.he.map(E.BLKMAP)
s = w.dropna(subset=['sp'])
print(f'=== {z}: {s.date.nunique()} days {s.date.min()}..{s.date.max()}, {len(s)} h')
print(f'buy wins (RT>DA) {100*(s.bu>0).mean():.1f}% of hours; RT>DA by >$10 in {100*(s.bu>10).mean():.1f}%; >$50 in {100*(s.bu>50).mean():.1f}%')
tot = s.bu[s.bu > 0].sum(); top = s.nlargest(int(len(s) * .02), 'bu').bu.sum()
print(f'top 2% of hours ({int(len(s)*.02)}) hold {100*top/tot:.0f}% of all positive RT-DA dollars')
print('\nbig buy hours (RT-DA > $10): where they sit'); big = s[s.bu > 10]
for col in ['blk', 'gband', 'wkend']:
    t = pd.concat([big[col].value_counts(normalize=True).rename('share_big'), s[col].value_counts(normalize=True).rename('share_all')], axis=1)
    t['lift'] = t.share_big / t.share_all; print(t.round(2).to_string())
print('\nRT-DA mean / median / buy-win% by gas band x weekend:')
print(s.groupby(['gband', 'wkend']).bu.agg(n='count', mean='mean', median='median', win=lambda x: (x > 0).mean() * 100).round(1).to_string())
print('\nRT-DA by block x weekend:'); print(s.groupby(['blk', 'wkend']).bu.agg(n='count', mean='mean', median='median', win=lambda x: (x > 0).mean() * 100).round(1).to_string())
print('\ncorrelation with RT-DA (bid-time):')
for c in ['m1', 'gapT', 'lean', 'gas_hat', 'head', 'wind_fc', 'nyx', 'lag2', 'prof']:
    x = s[[c, 'bu']].dropna(); print(f'  {c:8s} {x.corr().iloc[0,1]:+.3f}  spearman {x.corr("spearman").iloc[0,1]:+.3f}  n={len(x)}')
print('\nD-1 morning RT-DA (known at bid) quintile -> today RT-DA:')
s['m1q'] = pd.qcut(s.m1.rank(method='first'), 5, labels=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])
print(s.groupby('m1q').agg(m1=('m1', 'mean'), bu=('bu', 'mean'), med=('bu', 'median'), win=('bu', lambda x: (x > 0).mean() * 100)).round(2).to_string())
# execution: bid at a model quantile -> only buys when DA clears BELOW our forecast
print('\nbid-price execution (buy only if published DA <= bid):')
q = s.dropna(subset=['q10'])
for scope, mask in [('all hours', np.ones(len(q), bool)), ('non-signal hours', (q.signal == 'NONE').values), ('gas 4-7k', q.gband.isin(['4-5k', '5-6k', '6-7k']).values)]:
    for k in ['q10', 'q25', 'q50']:
        c = mask & (q.da <= q[k]).values; t = q[c]
        print(f'  {scope:17s} bid {k}: {c.sum():4d} h cleared, RT-DA {t.bu.mean():+6.2f} (median {t.bu.median():+.2f}, win {100*(t.bu>0).mean():.0f}%), top-5-day share {100*t.groupby("date").bu.sum().nlargest(5).sum()/max(t.bu.sum(),1e-9):.0f}%')
# walk-forward cell rule: buy (wkend, blk, gband) cells whose trailing mean AND median RT-DA > 0
out = []
for D in sorted(w.date.unique()):
    cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); tr = s[s.date <= cut]
    x = w[w.date == D].copy()
    if tr.date.nunique() < 21: continue
    g = tr.groupby(['wkend', 'blk', 'gband']).bu.agg(['mean', 'median', 'count']).reset_index()
    good = g[(g['count'] >= 30) & (g['mean'] > 2) & (g['median'] > 0)]
    x = x.merge(good[['wkend', 'blk', 'gband']].assign(cell=1), on=['wkend', 'blk', 'gband'], how='left'); out.append(x)
wf = pd.concat(out); wf['cell'] = wf.cell.fillna(0)
R = [E.score(wf, 'buy cells with trailing mean>2 & median>0', np.where(wf.cell == 1, -1, 0)),
     E.score(wf, 'same, non-signal hours only', np.where((wf.cell == 1) & (wf.signal == 'NONE'), -1, 0)),
     E.score(wf, 'buy if D-1 morning RT-DA > +3', np.where(wf.m1 > 3, -1, 0)),
     E.score(wf, 'buy if D-1 morning RT-DA > +3 & non-signal', np.where((wf.m1 > 3) & (wf.signal == 'NONE'), -1, 0)),
     E.score(wf, 'buy if lean < -2', np.where(wf.lean < -2, -1, 0)),
     E.score(wf, 'buy if Tesla >= +300 & non-signal', np.where((wf.gapT >= 300) & (wf.signal == 'NONE'), -1, 0)),
     E.score(wf, 'buy non-signal, bid at q25', np.where((wf.signal == 'NONE') & (wf.da <= wf.q25), -1, 0))]
print('\n=== walk-forward buy candidates ==='); print(pd.DataFrame(R).to_string(index=False))
# what the biggest buy days looked like at bid time
d = s.groupby('date').agg(bu=('bu', 'sum'), head_min=('head', 'min'), gas_max=('gas_hat', 'max'), lean=('lean', 'mean'), m1=('m1', 'first'), sells=('signal', lambda x: (x != 'NONE').sum()))
print('\n10 best buy days (1 MW every hour):'); print(d.nlargest(10, 'bu').round(1).to_string())
