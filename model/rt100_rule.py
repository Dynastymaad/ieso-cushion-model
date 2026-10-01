"""rt100_rule.py -- the user's rule: on hours the model says SELL (score 5), skip or halve the size when the page's
'RT > $100' odds for that headroom band are 40% or more. Walk-forward: the odds for day D use only hours up to D-2
(expanding window from May 2025, same bands as the page, needs >= 50 past hours in the band). Nets by calendar year."""
import sys, json, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, zone_bt17 as Z, vol_test as V
EDGES = [-1e9, 5000, 6000, 7000, 8000, 9000, 10000, 12000, 1e9]

def odds(zone):
    """P(RT > $100 | headroom band), known at the bid for each delivery day (hours <= D-2)."""
    e = pd.read_csv(C.DATA / f'dv_frame_{zone}.csv').dropna(subset=['rt', 'head'])[['date', 'he', 'rt', 'head']]
    e['band'] = pd.cut(e['head'], EDGES, labels=False); e['hit'] = (e.rt > 100).astype(float)
    days = sorted(pd.read_csv(C.DATA / f'dv_frame_{zone}.csv').date.unique()); out = {}
    for D in days:
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); tr = e[e.date <= c2]
        g = tr.groupby('band').hit.agg(['mean', 'count']); out[D] = {int(b): (r['mean'] if r['count'] >= 50 else np.nan) for b, r in g.iterrows()}
    return out

def run():
    res = {}
    for z in Z.LIM:
        e = Z.frame(z); O = odds(z)
        e['band'] = pd.cut(e['head'], EDGES, labels=False)
        e['p100'] = [O.get(d, {}).get(int(b), np.nan) if not pd.isna(b) else np.nan for d, b in zip(e.date, e.band)]
        flag = lambda r: (not pd.isna(r.p100)) and r.p100 >= 0.40
        base = V.rows(e, z); half = V.rows(e, z, flag, .5); skip = V.rows(e, z, flag, 0.0)
        base['p100'] = e.dropna(subset=['da', 'rt', 'p_da', 'p_rt']).p100.values
        fl = V.rows(e, z, flag, 1.0).risky.values; base['flag'] = fl
        R = {}
        print(f'\n================ {z} (cap {Z.LIM[z]} MW) ================')
        for yr in ('2025', '2026', 'all'):
            m = (lambda x: x.date.str[:4] == yr) if yr != 'all' else (lambda x: x.date == x.date)
            r = {}
            for n, x in (('follow page', base), ('rule: half size', half), ('rule: skip', skip)):
                xx = x[m(x)]; d = xx.groupby('date').pl.sum(); cum = d.cumsum()
                r[n] = dict(net=round(d.sum()), days=len(d), worst_day=round(d.min()), max_dd=round((cum - cum.cummax()).min()), days_lt_50k=int((d < -50000).sum()))
            R[yr] = r
            span = f"{base[m(base)].date.min()}..{base[m(base)].date.max()}"
            print(f'  {yr} ({span}):'); [print(f'     {n:18s} net {v["net"]:>+12,}   worst day {v["worst_day"]:>+10,}   max drawdown {v["max_dd"]:>+10,}   days < -$50k {v["days_lt_50k"]}') for n, v in r.items()]
        # what did the flagged hours do at full size?
        f = base[base.flag]; hrs = f[f.mw_s > 0]
        big = hrs[hrs.pl <= -10000]; gains = hrs[hrs.pl > 0]
        R['flagged'] = dict(hours=int(len(f)), filled=int(len(hrs)), days=int(f.date.nunique()), net=round(f.pl.sum()), won=round(gains.pl.sum()), lost=round(hrs[hrs.pl < 0].pl.sum()),
                            big_loss_hours=int(len(big)), big_loss_sum=round(big.pl.sum()), by_year={y: round(f[f.date.str[:4] == y].pl.sum()) for y in ('2025', '2026')})
        print(f"  flagged sell hours (odds >= 40%): {len(f)} hours on {f.date.nunique()} days, {len(hrs)} filled. At full size they netted {f.pl.sum():+,.0f} "
              f"(won {gains.pl.sum():+,.0f}, lost {hrs[hrs.pl<0].pl.sum():+,.0f}); hours losing $10k+: {len(big)} totalling {big.pl.sum():+,.0f}. By year: {R['flagged']['by_year']}")
        # large-loss hours overall: how many did the rule catch?
        allbig = base[base.pl <= -10000]; caught = allbig[allbig.flag]
        R['big_loss'] = dict(all_hours=int(len(allbig)), all_sum=round(allbig.pl.sum()), caught_hours=int(len(caught)), caught_sum=round(caught.pl.sum()))
        print(f"  all hours that lost $10k+ following the page: {len(allbig)} ({allbig.pl.sum():+,.0f}); the rule flagged {len(caught)} of them ({caught.pl.sum():+,.0f})")
        # worst 10 days
        dd = base.groupby('date').pl.sum().nsmallest(10); hd = half.groupby('date').pl.sum(); sk = skip.groupby('date').pl.sum(); rows = []
        for D, v in dd.items(): rows.append(dict(date=D, follow=round(v), half=round(hd.get(D, 0)), skip=round(sk.get(D, 0)), flagged_hours=int(base[(base.date == D) & base.flag].shape[0])))
        R['worst_days'] = rows; print('  10 worst days following the page, and what the rule would have done:'); print(pd.DataFrame(rows).to_string(index=False))
        # best 10 days given up
        bd = base.groupby('date').pl.sum().nlargest(10); rows = []
        for D, v in bd.items(): rows.append(dict(date=D, follow=round(v), half=round(hd.get(D, 0)), skip=round(sk.get(D, 0)), flagged_hours=int(base[(base.date == D) & base.flag].shape[0])))
        R['best_days'] = rows; print('  10 best days following the page, and what the rule would have done:'); print(pd.DataFrame(rows).to_string(index=False))
        res[z] = R
    (C.DATA / 'rt100_rule.json').write_text(json.dumps(res, default=float, indent=1))

if __name__ == '__main__': run()
