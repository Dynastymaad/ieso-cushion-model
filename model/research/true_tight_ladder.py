"""research/true_tight_ladder.py -- trading the gap with thresholds known in advance (trailing 6-week percentiles of the gap, through D-2),
and whether it improves the current ladder (v2 sells / buy band). 2026 Mar 2 -> Oct 29, both hubs, linear fair-RT version."""
import sys; sys.path.insert(0, 'model')
import numpy as np, pandas as pd, da_virtual_bt as B
pd.set_option('display.width', 240)
for z in ('EAST', 'OTTAWA'):
    t = pd.read_csv(f'data/research/true_tight_{z}.csv').sort_values(['date', 'he']); e = pd.read_csv(f'data/dv_frame_{z}.csv')[['date', 'he', 'v2', 'buyband', 'p_rt']]
    t = t.drop(columns=[c for c in ('v2', 'buyband', 'p_rt') if c in t]).merge(e, on=['date', 'he'], how='left')
    for q in (0.10, 0.25, 0.75, 0.90): t[f'thr{int(q*100)}'] = np.nan
    for D in sorted(t.date.unique()):
        past = t[(t.date <= (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()) & (t.date > (pd.Timestamp(D) - pd.Timedelta(days=44)).date().isoformat())].gap_lin
        if len(past) > 300:
            for q in (0.10, 0.25, 0.75, 0.90): t.loc[t.date == D, f'thr{int(q*100)}'] = past.quantile(q)
    t = t.dropna(subset=['thr90']); x = t.rt - t.da; t['m'] = t.date.str[:7]
    print(f'\n===== {z} {t.date.min()}..{t.date.max()} ({len(t)} h) =====')
    for nm, msk, sd in (('SHORT gap >= trailing p90', t.gap_lin >= t.thr90, -1), ('SHORT gap >= p75', t.gap_lin >= t.thr75, -1), ('LONG gap <= p10', t.gap_lin <= t.thr10, 1), ('LONG gap <= p25', t.gap_lin <= t.thr25, 1)):
        p = sd * x[msk]; mo = p.groupby(t.m[msk]).mean().round(1)
        print(f'   {nm:26s} {int(msk.sum()):5d} h ${p.mean():+6.2f} win {(p>0).mean()*100:3.0f}%  by month {mo.to_dict()}')
    v2 = t.v2 == 1; hi = t.hr_fc >= t.groupby('m').hr_fc.transform(lambda s: s.quantile(2 / 3))
    tt = v2 & (t.gap_lin <= t.thr25)          # v2 sells the physics says are TRULY tight
    print(f'   v2 sells: {int(v2.sum())} h ${(-x[v2]).mean():+.2f} | of which truly tight (gap <= p25): {int(tt.sum())} h ${(-x[tt]).mean():+.2f} win {((-x[tt])>0).mean()*100:.0f}% | rest ${(-x[v2 & ~tt]).mean():+.2f}')
    V = {'ladder now': np.where(v2, 5, np.where(t.buyband == -1, 1, 0)),
         'no sells when truly tight': np.where(v2 & ~tt, 5, np.where(t.buyband == -1, 1, 0)),
         '+ short gap >= p90': np.where((v2 & ~tt) | (t.gap_lin >= t.thr90), 5, np.where(t.buyband == -1, 1, 0)),
         '+ long gap <= p10': np.where((v2 & ~tt) | (t.gap_lin >= t.thr90), 5, np.where((t.buyband == -1) | (t.gap_lin <= t.thr10), 1, 0)),
         'gap only (p90 short / p10 long)': np.where(t.gap_lin >= t.thr90, 5, np.where(t.gap_lin <= t.thr10, 1, 0))}
    rows = []
    for nm, sc in V.items():
        mm = t.assign(sc=sc); r = B.run_ladder(mm, 'sc', nm); row = dict(variant=nm, total_k=round(r['total'] / 1000), usd_mwh=r['usd_per_mwh'], days_up=r['days_up'], worst_k=round(r['worst_day'] / 1000))
        for mo, g in mm.groupby('m'): row[mo] = round(B.run_ladder(g, 'sc', '')['total'] / 1000)
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))
