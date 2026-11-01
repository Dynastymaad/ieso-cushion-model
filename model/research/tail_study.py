"""research/tail_study.py -- Oct 31 2026 (TEST ONLY). Can we tell, at the bid, which hours carry the RT-above-DA tail (when to BUY)?
Walk-forward weekly (train through D-2, test the next week), Jul 6 -> Oct 30 2026. Features = everything the RT read uses
(bid-time fundamentals, Meteologica gaps, gas-need miss) + the crowd: cleared virtual net of all traders for the same hour on D-1 and D-2,
and the crowd's day-level net. Targets: RT > DA (buy wins) and RT >= DA + $25 (tail). Scored: how much better the top-ranked hours are
than the base rate, and P&L of buying them (price-taker at the DA clear, 1 MW)."""
import sys, json, warnings; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, rt_read as RR
from sklearn.ensemble import HistGradientBoostingClassifier as HGC
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 220)
Z = sys.argv[1] if len(sys.argv) > 1 else 'EAST'
START = sys.argv[2] if len(sys.argv) > 2 else '2026-07-06'; FAST = '--fast' in sys.argv
b = json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text())
f = RR.frame(Z, b['target'], b); f = f[f.rt.notna() & f.da.notna()].copy()
m = pd.read_csv(C.CACHE / 'market_virtuals.csv'); m = m[m.zone == f'{Z}:HUB'].rename(columns={'deliverydate': 'date', 'hour': 'he'})
m['net'] = m.supplyschedule + m.loadschedule; m['dbid'] = m.loadbid; m['sbid'] = m.supplybid
W = m.pivot_table(index='date', columns='he', values='net').sort_index(); W.index = pd.to_datetime(W.index); W = W.asfreq('D')
for k, lag in (('crowd1', 1), ('crowd2', 2)):
    s = W.shift(lag).stack().rename(k).reset_index(); s['date'] = s.date.dt.strftime('%Y-%m-%d'); f = f.merge(s, on=['date', 'he'], how='left')
dl = W.mean(axis=1).shift(1).rename('crowd_day1').reset_index(); dl['date'] = dl.date.dt.strftime('%Y-%m-%d'); f = f.merge(dl, on='date', how='left')
f['x'] = f.rt - f.da; f['win'] = (f.x > 0).astype(int); f['tl'] = (f.x >= 25).astype(int)
base = RR.FE; plus = base + ['crowd1', 'crowd2', 'crowd_day1']
for c in ('p_base', 'p_plus', 't_base', 't_plus'): f[c] = np.nan
for s in pd.date_range(START, f.date.max(), freq='7D'):
    s0 = s.date().isoformat(); e = (s + pd.Timedelta(days=6)).date().isoformat(); cut = (s - pd.Timedelta(days=2)).date().isoformat()
    te = (f.date >= s0) & (f.date <= e); tr = f[(f.date <= cut) & (f.date >= '2025-06-01')]
    for y, nm in (('win', 'p'), ('tl', 't')):
        for fe, tag in (((base, 'base'),) if FAST else ((base, 'base'), (plus, 'plus'))):
            mdl = HGC(max_depth=3, learning_rate=0.05, max_iter=250, min_samples_leaf=60, l2_regularization=2.0, random_state=0).fit(tr[fe], tr[y])
            f.loc[te, f'{nm}_{tag}'] = mdl.predict_proba(f.loc[te, fe])[:, 1]
t = f[f.date >= START].dropna(subset=['p_base']).copy()
print(f'{Z}: test {t.date.min()}..{t.date.max()}, {len(t)} hours; base rates: RT>DA {t.win.mean()*100:.0f}%, tail(+$25) {t.tl.mean()*100:.1f}%')
for col, y in ((('p_base', 'win'), ('t_base', 'tl')) if FAST else (('p_base', 'win'), ('p_plus', 'win'), ('t_base', 'tl'), ('t_plus', 'tl'))):
    auc = roc_auc_score(t[y], t[col]); rows = []
    for top in (0.05, 0.10, 0.20):
        th = t[col].quantile(1 - top); k = t[t[col] >= th]
        rows.append(f'top {int(top*100)}%: {len(k)} h, RT>DA {k.win.mean()*100:.0f}%, tail {k.tl.mean()*100:.0f}%, avg RT-DA {k.x.mean():+.1f}, Oct {k[k.date>="2026-10-01"].x.mean():+.1f}')
    print(f'  {col:7s} ({y}) AUC {auc:.2f} | ' + ' | '.join(rows))
bb = t[t.buyband == -1] if 'buyband' in t else None
if bb is not None: print(f'  current buy band: {len(bb)} h, RT>DA {bb.win.mean()*100:.0f}%, tail {bb.tl.mean()*100:.0f}%, avg RT-DA {bb.x.mean():+.1f}')
print('-- what the top-10% tail hours look like (plus model) vs all --')
k = t[t.t_base >= t.t_base.quantile(.9)]
for c in ['he', 'spare', 'gas_hat', 'shift', 'met_wgap', 'crowd1', 'p_da', 'wkend']:
    if c in t: print(f'   {c:10s} top10 {k[c].mean():8.1f}   all {t[c].mean():8.1f}')
t[[c for c in ['date', 'he', 'da', 'rt', 'x', 'p_base', 'p_plus', 't_base', 't_plus', 'crowd1'] if c in t]].to_csv(C.DATA / 'research' / (f'tail_preds_{Z}.csv' if START == '2026-07-06' else f'tail_preds_{Z}_{START}.csv'), index=False)
