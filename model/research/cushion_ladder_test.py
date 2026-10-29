"""research/cushion_ladder_test.py -- Oct 28 2026 (TEST ONLY). Does correcting gas need (gas_hat) by its trailing miss vs the gas
that actually ran improve the ladders? Re-runs our v2 sell rule (thresholds re-learned daily on the corrected history) and the
ladder 'v2 SELL=5, buy band=1, else 3', cleared on the actual DA. Correction known at the bid: mean miss by HE through D-2."""
import sys, warnings; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, da_virtual_bt as B
pd.set_option('display.width', 220)

def corrected(e, w, how='mean'):
    G = C.fuel_actual()[['date', 'he', 'g_gas']]
    x = e[['date', 'he', 'gas_hat']].merge(G, on=['date', 'he'], how='left'); x['miss'] = x.g_gas - x.gas_hat
    W = x.pivot_table(index='date', columns='he', values='miss').sort_index()
    W.index = pd.to_datetime(W.index); W = W.asfreq('D')
    r = W.shift(2).rolling(w, min_periods=max(5, w // 2))
    b = (r.mean() if how == 'mean' else r.median()).stack().rename('b').reset_index(); b['date'] = b.date.dt.strftime('%Y-%m-%d')
    out = e.merge(b, on=['date', 'he'], how='left'); return (out.gas_hat + out.b.fillna(0)).values

def run(zone):
    e = pd.read_csv(C.DATA / f'dv_frame_{zone}.csv'); rows = []
    for name, gh in [('current (no correction)', e.gas_hat.values)] + [(f'{w}-day {h} correction', corrected(e, w, h)) for w in (7, 14, 30) for h in ('mean', 'median')]:
        x = e.copy(); x['gas_hat'] = gh; x['v2'] = B.walk_v2(x)
        x['ours'] = np.where(x.v2 == 1, 5, np.where(x.buyband == -1, 1, 3))
        for per, lo in (('Sep 2025 ->', '2025-09-01'), ('2026 H2 (Jul ->)', '2026-07-01'), ('Sep 15 ->', '2026-09-15')):
            t = x[x.date >= lo]; r = B.run_ladder(t, 'ours', name); r['period'] = per; r['v2_hours'] = int((t.v2 == 1).sum()); rows.append(r)
    R = pd.DataFrame(rows)[['period', 'ladder', 'days', 'v2_hours', 'mwh_cleared', 'usd_per_mwh', 'usd_per_day', 'total', 'days_up', 'worst_day']]
    R.to_csv(C.DATA / 'research' / f'cushion_ladder_{zone}.csv', index=False); print(zone); print(R.sort_values(['period', 'ladder']).to_string(index=False))

if __name__ == '__main__':
    for z in sys.argv[1:] or ['EAST']: run(z)
