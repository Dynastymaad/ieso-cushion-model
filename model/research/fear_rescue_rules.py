"""research/fear_rescue_rules.py -- turn the fear / rescue read into trades and test them honestly.
SHORT 'fear but rescue': public spare < 1,500, private spare 300+ looser, wind models agree (spread <= 1,200).
LONG  'calm but danger': public spare >= 1,500 and private spare 300+ tighter.
Price-taker, 1 MW, P&L = DA-RT for shorts, RT-DA for longs. Robustness: threshold grid, periods, and an ADAPTIVE version that each
week trades a rule only if its trailing 90 days (through D-2) made money -- the market changes, so the read must earn its place."""
import sys; sys.path.insert(0, 'model'); sys.path.insert(0, 'model/research')
import numpy as np, pandas as pd
pd.set_option('display.width', 230)
def rules(e, t_sp=1500, r=300, ws=1200):
    short = (e.pub_sp < t_sp) & (e.rescue >= r) & (e.w_spread <= ws)
    long_ = (e.pub_sp >= t_sp) & (e.rescue <= -r)
    return short, long_
def pl(e, m, side): return (e.da - e.rt)[m] if side == 'S' else (e.rt - e.da)[m]
for z in ('EAST', 'OTTAWA'):
    e = pd.read_csv(f'data/research/fear_rescue_{z}.csv'); e['m'] = e.date.str[:7]
    s, l = rules(e)
    print(f'\n===== {z} =====')
    for nm, m, sd in (('SHORT fear-but-rescue', s, 'S'), ('LONG calm-but-danger', l, 'L'), ('v2 sells (current)', e.v2 == 1, 'S')):
        p = pl(e, m, sd); g = p.groupby(e.per[m])
        print(f'{nm:24s} {int(m.sum()):5d} h  ${p.mean():+6.2f}/MWh  win {(p>0).mean()*100:3.0f}%  total ${p.sum():>9,.0f} | ' + ' | '.join(f'{k} {v.mean():+.1f} ({len(v)}h)' for k, v in g))
    print('-- threshold grid (avg $/MWh, hours): short | long --')
    for t_sp in (1000, 1500, 2000):
        for r in (200, 300, 500):
            s2, l2 = rules(e, t_sp, r); a = pl(e, s2, 'S'); b = pl(e, l2, 'L')
            print(f'   spare<{t_sp} rescue>={r}: short {a.mean():+6.2f} ({len(a)}h, win {(a>0).mean()*100:.0f}%) | long {b.mean():+6.2f} ({len(b)}h, win {(b>0).mean()*100:.0f}%)')
    print('-- adaptive (trade a rule only if its trailing 90 days were profitable) vs always on, by month --')
    e = e.sort_values(['date', 'he']); out = []
    for D in sorted(e.date.unique()):
        if D < '2025-10-01': continue
        tr = e[(e.date <= (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()) & (e.date > (pd.Timestamp(D) - pd.Timedelta(days=92)).date().isoformat())]
        ts, tl = rules(tr); g = e[e.date == D]; gs, gl = rules(g)
        on_s = pl(tr, ts, 'S').sum() > 0 if ts.sum() >= 10 else False; on_l = pl(tr, tl, 'L').sum() > 0 if tl.sum() >= 10 else False
        out.append(dict(date=D, m=D[:7], s_all=pl(g, gs, 'S').sum(), l_all=pl(g, gl, 'L').sum(), s_ad=pl(g, gs, 'S').sum() if on_s else 0, l_ad=pl(g, gl, 'L').sum() if on_l else 0,
                        on_s=on_s, on_l=on_l))
    o = pd.DataFrame(out); M = o.groupby('m')[['s_all', 's_ad', 'l_all', 'l_ad']].sum().round(0); M['short_on_days'] = o.groupby('m').on_s.mean().round(2); M['long_on_days'] = o.groupby('m').on_l.mean().round(2)
    print(M.to_string()); print('TOTAL', o[['s_all', 's_ad', 'l_all', 'l_ad']].sum().round(0).to_dict())
