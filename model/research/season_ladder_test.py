"""research/season_ladder_test.py -- Oct 28 2026 (TEST ONLY). Since mid-Sep the ladder lost money. Two candidate fixes:
(a) re-learn the v2 sell thresholds on a shorter trailing window (default 120 days), (b) drop the score-3 straddle."""
import sys, warnings; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, da_virtual_bt as B, signals_v2 as S

def walk(e, look):
    out = pd.Series(0, index=e.index)
    for D in sorted(e.date.unique()):
        if D < '2025-07-01': continue
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=look)).date().isoformat()
        tr = e[(e.date <= c2) & (e.date > lo) & e.sp.notna()]
        th, tg = S.best_thr(tr, 'head', S.HEAD_THR), S.best_thr(tr.dropna(subset=['gas_hat']), 'gas_hat', S.GAS_THR)
        m = e.date == D; out[m] = ((e.loc[m, 'head'] < (th or -1)) | (e.loc[m, 'gas_hat'] < (tg or -1))).astype(int)
    return out

rows = []
for z in ('EAST', 'OTTAWA'):
    e = pd.read_csv(C.DATA / f'dv_frame_{z}.csv')
    for look in (120, 90, 60, 45, 30):
        x = e.copy(); x['v2'] = e.v2 if look == 120 else walk(e, look)
        for strad in (3, 0):
            x['sc'] = np.where(x.v2 == 1, 5, np.where(x.buyband == -1, 1, strad))
            for per, lo in (('Sep 2025 ->', '2025-09-01'), ('Jul 2026 ->', '2026-07-01'), ('Sep 15 ->', '2026-09-15')):
                r = B.run_ladder(x[x.date >= lo], 'sc', ''); rows.append(dict(zone=z, lookback=look, straddle='yes' if strad else 'no', period=per,
                                   usd_mwh=r['usd_per_mwh'], usd_day=r['usd_per_day'], total=r['total'], days_up=r['days_up']))
R = pd.DataFrame(rows); R.to_csv(C.DATA / 'research' / 'season_ladder.csv', index=False)
print(R.pivot_table(index=['zone', 'lookback', 'straddle'], columns='period', values='total').round(0).to_string())
