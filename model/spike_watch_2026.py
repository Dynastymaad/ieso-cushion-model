"""spike_watch_2026.py -- Oct 8 2026: Spike Watch (spike_watch.py, score >= 2, evening HE16-21 non-sell, bid DA fc + $30) in 2026 only:
P&L at 20 MW by month, drawdown, worst/best days; and every RT spike (RT-DA >= $40) in Sep-Oct with what Spike Watch said."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 260); MW = 20
S = pd.read_csv(C.DATA / 'shock_predict_EAST.csv')[['date', 'he', 'gapDyn', 'gapT']]
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv').merge(S, on=['date', 'he'], how='left')
    m = m[(m.date >= '2026-01-01') & (m.date <= '2026-10-07') & m.rt.notna()].copy()
    m['f_head'] = m['head'].between(7000, 8500); m['f_cahr'] = m.cahr >= 10; m['f_load'] = (m.gapT >= 0) | (m.gapDyn >= 0); m['f_wind'] = m.wr3 <= -150
    m['score'] = m[['f_head', 'f_cahr', 'f_load', 'f_wind']].sum(axis=1)
    m['flag'] = m.he.between(16, 21) & m.why.isna() & (m.score >= 2)
    m['clear'] = m.da <= m.p_da + 30; m['pl'] = np.where(m.flag & m.clear, MW * (m.rt - m.da), 0.0)
    t = m[m.flag & m.clear]; dd = m.groupby('date').pl.sum(); dd = dd[dd != 0]; cum = dd.cumsum()
    print(f'\n================ {z} 2026 (Jan 1 - Oct 7), {MW} MW per flagged hour ================')
    print(f'total ${t.pl.sum():,.0f} | flagged hours {len(t)} on {t.date.nunique()} days | win {(t.pl>0).mean()*100:.0f}% | avg win ${t.pl[t.pl>0].mean():,.0f} / avg loss ${t.pl[t.pl<=0].mean():,.0f} per hour')
    print(f'days up {(dd>0).sum()} / down {(dd<0).sum()} | best day {dd.idxmax()} ${dd.max():,.0f} | worst day {dd.idxmin()} ${dd.min():,.0f} | max drawdown ${(cum - cum.cummax()).min():,.0f}')
    print(f'without best 3 days ${dd.sum() - dd.nlargest(3).sum():,.0f} | without best 5 ${dd.sum() - dd.nlargest(5).sum():,.0f}')
    print('by month $:', t.groupby(t.date.str[:7]).pl.sum().round(0).astype(int).to_dict())
    sp = m[(m.date >= '2026-09-01') & (m.rt - m.da >= 40)].copy()
    sp['what'] = np.where(sp.why.notna(), 'SHORT (model sell)', np.where(~sp.he.between(16, 21), 'outside HE16-21', np.where(sp.flag & sp.clear, 'FLAGGED, would clear', np.where(sp.flag, 'flagged, bid too low', 'not flagged'))))
    print('Sep-Oct spikes (RT-DA >= $40):'); print(sp[['date', 'he', 'da', 'rt', 'head', 'cahr', 'gapT', 'gapDyn', 'wr3', 'score', 'what']].round(0).to_string(index=False))
    print('summary:', sp.what.value_counts().to_dict())
