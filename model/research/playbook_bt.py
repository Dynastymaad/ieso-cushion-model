"""Systematic Fundamentals-tab playbook, 2026, bid-time inputs only (Meteo/Tesla/IESO forecasts at bid, gas need from D-2 flows,
DA-fc 'vs usual' from prior 14 days, stress score trained through D-2, stress percentile vs prior 60 days). P&L = side x (RT - DA), 1 MW."""
import pandas as pd, numpy as np, sys
def load(z):
    e = pd.read_csv(f'data/research/stress_{z}_extra.csv'); e['rd'] = e.rt - e.da; e = e.sort_values(['date', 'he'])
    days = sorted(e.date.unique()); pct = []
    for D in days:
        past = e[(e.date < D) & (e.date >= str((pd.Timestamp(D) - pd.Timedelta(days=60)).date()))].gbm.dropna().values
        cur = e[e.date == D].gbm.values
        pct += list(np.searchsorted(np.sort(past), cur) / len(past) * 100) if len(past) > 200 else [np.nan] * len(cur)
    e['spct'] = pct; return e[e.spct.notna() & e.rd.notna() & e.vs.notna()].copy()
def read(r):
    rich, cheap = r.vs >= 18, r.vs <= -5; tight, loose = r.rescue <= -300, r.rescue >= 300
    scared = r.pub_sp < 1500; lo, hi = r.spct < 20, r.spct > 80
    if (scared or rich) and loose: return -1, 'S1 fear priced, our spare says rescue'
    if rich and lo:                return -1, 'S2 DA rich, stress low'
    if rich and not tight:         return -1, 'S3 DA rich, we see no extra tightness'
    if lo and loose:               return -1, 'S4 stress low and we see extra spare'
    if tight and not rich and not lo: return 1, 'L1 we see less spare, DA not pricing it'
    if r.w3 <= -300 and not rich and not loose and not lo: return 1, 'L2 wind falling into hour, not priced'
    return 0, '-- no read'
for z in sys.argv[1:] or ['EAST', 'OTTAWA']:
    e = load(z); rr = e.apply(read, axis=1); e['side'] = [a for a, b in rr]; e['rule'] = [b for a, b in rr]
    e['pnl'] = e.side * e.rd; e['m'] = e.date.str[:7]; e['half'] = np.where(e.date < '2026-07-01', 'Mar-Jun', 'Jul-Oct')
    # walk-forward gate: a rule trades on day D only if its own record over the prior 90 days (to D-2) is positive with >=30 h
    days = sorted(e.date.unique()); live = []
    for D in days:
        c2 = str((pd.Timestamp(D) - pd.Timedelta(days=2)).date()); c0 = str((pd.Timestamp(D) - pd.Timedelta(days=92)).date())
        past = e[(e.date <= c2) & (e.date > c0) & (e.side != 0)].groupby('rule').pnl.agg(['mean', 'size'])
        ok = set(past[(past['mean'] > 0) & (past['size'] >= 30)].index); live += list(e[e.date == D].rule.isin(ok))
    e['live'] = live; e['pnl_g'] = np.where(e.live, e.pnl, 0)
    print(f'\n================ {z}  {e.date.min()}..{e.date.max()}  {e.date.nunique()} days ================')
    t = e[e.side != 0]
    g = t.groupby(['rule', 'half']).pnl.agg(h='size', avg='mean', win=lambda x: (x > 0).mean()).round(2).unstack('half'); print(g.to_string())
    print('\nBy month, $ total (all rules, 1 MW each hour):'); mo = t.groupby('m').pnl.sum().round(0); print(mo.to_dict())
    for lab, col, msk in [('ALL RULES', 'pnl', e.side != 0), ('GATED (rule only if its last-90-day record > 0)', 'pnl_g', e.live & (e.side != 0))]:
        d = e.groupby('date')[col].sum(); s = e[msk]
        print(f'{lab}: {len(s)} h ({len(s)/len(e):.0%} of hours), ${s[col].mean():+.2f}/MWh, win {(s[col]>0).mean():.0%}, total ${d.sum():,.0f}/MW, '
              f'days up {(d[d!=0]>0).mean():.0%}, worst day ${d.min():,.0f}, months up {(e.groupby("m")[col].sum()>0).sum()}/{e.m.nunique()}')
    print(f'reference: short every hour ${-e.rd.mean():+.2f}/MWh | long every hour ${e.rd.mean():+.2f}/MWh')
    o = e[e.date == '2026-10-31'][['he', 'vs', 'pub_sp', 'rescue', 'spct', 'w3', 'rule', 'live', 'rd']]; o['spct'] = o.spct.round(0)
    print('\nOct 31 read:'); print(o.round(0).to_string(index=False))
    gm = e[e.live & (e.side != 0)]
    print('GATED by rule:'); print(gm.groupby('rule').pnl.agg(h='size', avg='mean', win=lambda x: (x > 0).mean(), total='sum').round(2).to_string())
    print('GATED by month $:', gm.groupby('m').pnl.sum().round(0).to_dict())
    xj = gm[gm.m != '2026-07']; print(f'GATED excluding July: {len(xj)} h ${xj.pnl.mean():+.2f}/MWh win {(xj.pnl>0).mean():.0%} total ${xj.pnl.sum():,.0f}')
    v = gm[gm.he.between(9, 15)]; print(f'GATED valley HE9-15 only: {len(v)} h ${v.pnl.mean():+.2f}/MWh win {(v.pnl>0).mean():.0%}')
    e[['date', 'he', 'side', 'rule', 'live', 'rd', 'pnl', 'pnl_g']].to_csv(f'data/research/playbook_{z}.csv', index=False)
