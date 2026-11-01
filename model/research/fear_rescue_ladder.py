"""research/fear_rescue_ladder.py -- ladder P&L (VA tier formulas, cleared on the actual DA) with the fear / rescue read added."""
import sys; sys.path.insert(0, 'model')
import numpy as np, pandas as pd, da_virtual_bt as B
pd.set_option('display.width', 250)
for z in ('EAST', 'OTTAWA'):
    e = pd.read_csv(f'data/research/fear_rescue_{z}.csv'); e = e[e.date >= '2025-09-01']
    v2 = e.v2 == 1; bb = e.buyband == -1
    tight = e.pub_sp < 1500; resc = e.rescue >= 300; dang = e.rescue <= -300; unc = e.w_spread > 1200
    fr_short = tight & resc & ~unc; cd_long = (e.pub_sp >= 1500) & dang
    bad_sell = v2 & (dang | (tight & unc))
    x = e.da - e.rt
    print(f'\n===== {z} {e.date.min()}..{e.date.max()} =====')
    for nm, m in (('v2 sells, all', v2), ('v2 sells where private view says DANGER or tight+uncertain', bad_sell), ('v2 sells, the rest', v2 & ~bad_sell),
                  ('fear-but-rescue hours v2 did NOT sell', fr_short & ~v2), ('buy band hours', bb & ~v2), ('calm-but-danger hours', cd_long & ~v2)):
        p = x[m] if 'buy' not in nm and 'calm' not in nm else -x[m]
        print(f'   {nm:60s} {int(m.sum()):5d} h  ${p.mean():+6.2f}/MWh  win {(p>0).mean()*100:3.0f}%')
    V = {'1 ladder now (v2 sell=5, buy band=1)': np.where(v2, 5, np.where(bb, 1, 0)),
         '2 + no sells where private says danger/uncertain': np.where(v2 & ~bad_sell, 5, np.where(bb, 1, 0)),
         '3 + short fear-but-rescue hours': np.where((v2 & ~bad_sell) | fr_short, 5, np.where(bb, 1, 0)),
         '4 + long calm-but-danger hours': np.where((v2 & ~bad_sell) | fr_short, 5, np.where(bb | cd_long, 1, 0))}
    rows = []
    for nm, sc in V.items():
        mm = e.assign(sc=sc); r = B.run_ladder(mm, 'sc', nm); row = dict(variant=nm, total_k=round(r['total'] / 1000), usd_mwh=r['usd_per_mwh'], days_up=r['days_up'], worst_k=round(r['worst_day'] / 1000))
        for per, g in mm.groupby(np.select([mm.date < '2026-01-01', mm.date < '2026-07-01'], ['25H2', '26H1'], '26JulOct')): row[per] = round(B.run_ladder(g, 'sc', '')['total'] / 1000)
        row['Oct26'] = round(B.run_ladder(mm[mm.date >= '2026-10-01'], 'sc', '')['total'] / 1000)
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))
