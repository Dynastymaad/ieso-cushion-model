"""research/crowd_study.py -- Oct 31 2026 (TEST ONLY). How do the other virtual traders behave in East/Ottawa, and does it tell us
when DA clears rich or cheap and when RT beats DA? Source: IESO public virtual transactions (all participants, cleared and bid MW),
cache/market_virtuals.csv. Sign: net = cleared virtual supply - cleared virtual demand (+ = crowd net SHORT, pushes DA down)."""
import sys, warnings; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 220)

def frame(zone):
    m = pd.read_csv(C.CACHE / 'market_virtuals.csv'); m = m[m.zone == f'{zone}:HUB'].rename(columns={'deliverydate': 'date', 'hour': 'he'})
    m['dem_cl'] = -m.loadschedule; m['sup_cl'] = m.supplyschedule; m['net'] = m.sup_cl - m.dem_cl
    m['dem_bid'] = m.loadbid; m['sup_bid'] = m.supplybid
    d = pd.read_csv(C.DATA / f'dv_frame_{zone}.csv')[['date', 'he', 'da', 'rt', 'p_da', 'q10', 'q90', 'head', 'v2', 'buyband']]
    x = d.merge(m[['date', 'he', 'dem_cl', 'sup_cl', 'net', 'dem_bid', 'sup_bid']], on=['date', 'he'], how='inner')
    try:
        o = pd.read_csv(C.CACHE / 'dynasty_virtuals.csv'); o = o[o.zone.str.upper().str.startswith(zone[:4])]
        o['s'] = np.where(o.buysell.str.lower().str.startswith('s'), o.volume, -o.volume)
        x = x.merge(o.groupby(['date', 'hour']).s.sum().rename('ours').reset_index().rename(columns={'hour': 'he'}), on=['date', 'he'], how='left')
    except Exception: x['ours'] = np.nan
    x = x.sort_values(['date', 'he']); x['x'] = x.rt - x.da; x['res'] = x.da - x.p_da; x['m'] = x.date.str[:7]
    x['net_y'] = x.groupby('he').net.shift(1)                     # yesterday's cleared net, same hour (known at the bid)
    x['crowd_pl'] = x.sup_cl * (x.da - x.rt) + x.dem_cl * (x.rt - x.da)
    return x

if __name__ == '__main__':
    for z in ('EAST', 'OTTAWA'):
        x = frame(z); x = x[x.rt.notna()]
        print(f'\n================ {z}: {x.date.min()} .. {x.date.max()}, {x.date.nunique()} days ================')
        print('-- crowd book by month: cleared MW/h, net (+ short), crowd P&L $ (all participants) --')
        g = x.groupby('m'); print(pd.DataFrame({'sup_cl': g.sup_cl.mean(), 'dem_cl': g.dem_cl.mean(), 'net': g.net.mean(), 'crowd_pl_k': g.crowd_pl.sum() / 1000,
              'pl_per_mwh': g.crowd_pl.sum() / (g.sup_cl.sum() + g.dem_cl.sum()), 'rt_minus_da': g.x.mean()}).round(1).tail(12).to_string())
        print('-- by hour block, last 90 days: who is short / long --')
        t = x[x.date >= (pd.Timestamp(x.date.max()) - pd.Timedelta(days=90)).date().isoformat()]
        t['blk'] = pd.cut(t.he, [0, 4, 8, 15, 19, 24], labels=['HE1-4', 'HE5-8', 'HE9-15', 'HE16-19', 'HE20-24'])
        print(t.groupby('blk').agg(sup=('sup_cl', 'mean'), dem=('dem_cl', 'mean'), net=('net', 'mean'), rt_da=('x', 'mean'), crowd_pl=('crowd_pl', 'sum')).round(1).to_string())
        print('-- persistence: corr(today net, yesterday net same hour) --', round(x[['net', 'net_y']].corr().iloc[0, 1], 2))
        print('-- same-day crowd net vs DA residual (DA - our fc) and RT-DA (NOT known at the bid; shows the mechanism) --')
        b = pd.qcut(x.net, 5, duplicates='drop'); print(x.groupby(b).agg(hours=('x', 'size'), net=('net', 'mean'), da_minus_fc=('res', 'mean'), rt_minus_da=('x', 'mean'), rt_gt_da=('x', lambda s: (s > 0).mean() * 100)).round(1).to_string())
        print('-- KNOWN AT THE BID: yesterday\'s crowd net (same hour) -> today --')
        y = x.dropna(subset=['net_y']); b = pd.qcut(y.net_y, 5, duplicates='drop')
        print(y.groupby(b).agg(hours=('x', 'size'), net_y=('net_y', 'mean'), da_minus_fc=('res', 'mean'), rt_minus_da=('x', 'mean'), rt_gt_da=('x', lambda s: (s > 0).mean() * 100),
                               spike25=('x', lambda s: (s > 25).mean() * 100)).round(1).to_string())
        for per, lo, hi in (('2026 Jul-Sep', '2026-07-01', '2026-09-30'), ('Oct 2026', '2026-10-01', '2026-10-31')):
            q = y[(y.date >= lo) & (y.date <= hi)]; b = pd.qcut(q.net_y, 3, labels=['crowd long yday', 'mid', 'crowd short yday'], duplicates='drop')
            print(f'   {per}:', q.groupby(b).x.agg(['size', 'mean', lambda s: (s > 0).mean() * 100]).round(1).to_dict('index'))
        if x.ours.notna().any():
            o = x[x.ours.notna() & (x.ours != 0)]; print(f'-- our trades vs crowd (through {x[x.ours.notna()].date.max()}): our side same as crowd net in', round((np.sign(o.ours) == np.sign(o.net)).mean() * 100), '% of traded hours; our share of crowd cleared MW', round(o.ours.abs().sum() / (o.sup_cl + o.dem_cl).sum() * 100), '%')
