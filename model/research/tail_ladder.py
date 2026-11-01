"""research/tail_ladder.py -- ladder P&L with the tail flag (no sells in the top-10% tail-risk hours) and/or extra buys on the
top-10% RT>DA hours. Cutoffs = 90th percentile of the model's scores over the trailing 6 weeks (known ex ante)."""
import sys; sys.path.insert(0, 'model')
import pandas as pd, numpy as np, da_virtual_bt as B
START = sys.argv[1] if len(sys.argv) > 1 else '2025-12-01'
for z in ['EAST', 'OTTAWA']:
    t = pd.read_csv(f'data/research/tail_preds_{z}_{START}.csv'); e = pd.read_csv(f'data/dv_frame_{z}.csv')
    m = e.merge(t[['date', 'he', 'p_base', 't_base']], on=['date', 'he']); m = m[m.rt.notna()].sort_values(['date', 'he'])
    for col in ('p_base', 't_base'):
        m[col + '_thr'] = np.nan
        for D in sorted(m.date.unique()):
            past = m[(m.date < D) & (m.date >= (pd.Timestamp(D) - pd.Timedelta(days=42)).date().isoformat())][col]
            if len(past) > 200: m.loc[m.date == D, col + '_thr'] = past.quantile(.9)
    m = m.dropna(subset=['p_base_thr', 't_base_thr']); buy = m.p_base >= m.p_base_thr; tail = m.t_base >= m.t_base_thr; s = m.v2 == 1; x = m.rt - m.da
    print(f'\n{z} {m.date.min()}..{m.date.max()}: v2 sells {int(s.sum())} h  DA-RT {(-x[s]).mean():+.2f} | in tail hours {int((s & tail).sum())} h {(-x[s & tail]).mean():+.2f} | outside {(-x[s & ~tail]).mean():+.2f}')
    V = {'ladder now': np.where(s, 5, np.where(m.buyband == -1, 1, 0)), 'no sells in tail hours': np.where(s & ~tail, 5, np.where(m.buyband == -1, 1, 0)),
         '+ buys on top-10% RT>DA': np.where(s & ~tail, 5, np.where(buy | (m.buyband == -1), 1, 0))}
    rows = []
    for nm, sc in V.items():
        mm = m.assign(sc=sc); r = B.run_ladder(mm, 'sc', nm); row = dict(variant=nm, total=r['total'], usd_mwh=r['usd_per_mwh'], days_up=r['days_up'], worst=r['worst_day'])
        for mo, g in mm.groupby(mm.date.str[:7]): row[mo] = round(B.run_ladder(g, 'sc', '')['total'] / 1000)
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))
