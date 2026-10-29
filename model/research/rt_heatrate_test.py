"""research/rt_heatrate_test.py -- Oct 28 2026 (TEST ONLY). Can heat rates + history give a more accurate RT read?
A) current RT P50 (DA fc + predicted RT-DA, median loss)
B) heat-rate model: predict the RT implied heat rate (carbon-adjusted, gas known at D-2) from the same bid-time features, then
   RT = HR x (gas + EF x CO2) - Bench x CO2
C) historical analog: RT heat rate = median of the 40 most similar past hours (same HE +-1, by need / spare / wind / load / month),
   converted with tomorrow's gas
D) average of A and B. Walk-forward weekly, Jul 6 -> Oct 27 2026, trained on days through D-2."""
import sys, warnings; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, rt_read as RR, cahr as K, json
Z = sys.argv[1] if len(sys.argv) > 1 else 'EAST'
b = json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text())
f = RR.frame(Z, b['target'], b); f = f[f.rt.notna() & f.da.notna()].copy()
f = K.add(f.drop(columns=['cahr'], errors='ignore'), 'p_da'); f['den'] = f.gas_cad + K.EF * f.cp; f['off'] = K.BENCH * f.cp
f['hr_rt'] = (f.rt + f.off) / f.den; f = f[f.den.notna()]
FE = RR.FE + ['gas_cad']
for c in ('A', 'B', 'C'): f[c] = np.nan
for s in pd.date_range('2026-07-06', f.date.max(), freq='7D'):
    s0 = s.date().isoformat(); e = (s + pd.Timedelta(days=6)).date().isoformat(); cut = (s - pd.Timedelta(days=2)).date().isoformat()
    te = (f.date >= s0) & (f.date <= e); tr = f[(f.date <= cut) & (f.date >= '2025-06-01')]
    f.loc[te, 'A'] = f.loc[te, 'p_da'] + RR._m('absolute_error').fit(tr[RR.FE], (tr.rt - tr.da).clip(-60, 60)).predict(f.loc[te, RR.FE])
    hrp = RR._m('absolute_error').fit(tr[FE], tr.hr_rt.clip(-5, 40)).predict(f.loc[te, FE])
    f.loc[te, 'B'] = hrp * f.loc[te, 'den'] - f.loc[te, 'off']
    K_ = ['gas_hat', 'spare', 'wind_fc', 'dem_fc', 'month']; sd = tr[K_].astype(float).std()
    for i in f.index[te]:
        r = f.loc[i]; pool = tr[(tr.he - r.he).abs() <= 1].dropna(subset=K_)
        d = (((pool[K_].astype(float) - r[K_].astype(float)) / sd) ** 2).sum(axis=1).astype(float); nn = pool.loc[d.nsmallest(40).index]
        f.loc[i, 'C'] = nn.hr_rt.median() * r.den - r.off
t = f[f.date >= '2026-07-06'].dropna(subset=['A', 'B', 'C']).copy(); t['D'] = (t.A + t.B) / 2
rows = []
for k, n in (('p_da', 'DA forecast only'), ('A', 'A: current RT P50'), ('B', 'B: heat-rate model'), ('C', 'C: historical analog heat rate'), ('D', 'D: average of A and B')):
    er = t[k] - t.rt
    for per, m in (('Jul 6 - Oct 27', t.date >= '0'), ('Oct', t.date >= '2026-10-01')):
        rows.append(dict(method=n, period=per, mae=round(er[m].abs().mean(), 2), median_ae=round(er[m].abs().median(), 1), within_10=round((er[m].abs() <= 10).mean() * 100),
                         direction=None if k == 'p_da' else round((np.sign(t[k] - t.p_da) == np.sign(t.rt - t.da))[m].mean() * 100)))
print(pd.DataFrame(rows).to_string(index=False))
