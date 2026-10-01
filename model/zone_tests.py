"""zone_tests.py -- everything re-tested for EAST and OTTAWA (bid-time inputs only, walk-forward).
  1 DA / RT forecast accuracy (zone_backtest.py files)
  2 v2 SELL signal, tight vs surplus branch, trips x1.5 on tight sells
  3 VA ladders with the zone MW limits (East 85, Ottawa 100 per side per hour), fills on the actual DA
  4 East-Ottawa spread pair (sell East DA + buy Ottawa DA, or the reverse): walk-forward by HE on trailing spreads
  5 Quebec / New York intertie inputs known at the bid: do they improve the zone DA forecast?"""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV, fail_fix as FF, quebec as Q
pd.set_option('display.width', 250)
LIM = {'EAST': 85, 'OTTAWA': 100}

def sig_frame(zone):
    w = pd.read_csv(C.DATA / f'bt_signals_v2_{zone}.csv')
    q = pd.read_csv(C.DATA / f'bt_quantiles_{zone}.csv')[['date', 'he', 'p_da']]
    r = pd.read_csv(C.DATA / f'bt_rt_quantiles_{zone}.csv')[['date', 'he', 'r50']].rename(columns={'r50': 'p_rt'})
    o = pd.read_csv(C.DATA / 'outage_features.csv')[['date', 'he', 'trips_d1']]
    x = w.drop(columns=[c for c in ('p_da',) if c in w]).merge(q, on=['date', 'he'], how='left').merge(r, on=['date', 'he'], how='left').merge(o, on=['date', 'he'], how='left')
    return x

def ladder_net(x, zone, boost):
    rows = []
    for r in x.dropna(subset=['da', 'rt', 'p_da', 'p_rt']).itertuples():
        s = 5 if r.signal == 'SELL' else 4 if r.signal == 'SELL-L' else 3
        b, o = DV.ladder(s, r.p_da, r.p_rt)
        k = 1.5 if (boost and s == 5 and r.why == 'tight' and (r.trips_d1 or 0) >= 500) else 1.0
        tb = [(q * k, p) for q, p in b if p is not None]; to = [(q * k, p) for q, p in o if p is not None]
        for side in (tb, to):                                   # zone cap per side
            tot = sum(q for q, _ in side)
            if tot > LIM[zone]: side[:] = [(q * LIM[zone] / tot, p) for q, p in side]
        mb = sum(q for q, p in tb if r.da <= p); ms = sum(q for q, p in to if r.da >= p)
        rows.append((r.date, mb + ms, mb * (r.rt - r.da) + ms * (r.da - r.rt)))
    d = pd.DataFrame(rows, columns=['date', 'mw', 'pl']); g = d.groupby('date').pl.sum()
    return dict(days=len(g), mwh=round(d.mw.sum()), usd_mwh=round(d.pl.sum() / d.mw.sum(), 2), net=round(g.sum()), made=round(g[g > 0].sum()), lost=round(g[g < 0].sum()),
                usd_day=round(g.mean()), worst_day=round(g.min()), days_up=round((g > 0).mean() * 100))

def spread_walk(start=None, look=28, min_edge=1.0):
    """pair P&L per MW = (DA_E - DA_O) - (RT_E - RT_O) if we SELL East / BUY Ottawa; the reverse flips the sign.
    Each day, for each HE, the side and trade/no-trade come from the trailing `look` days through D-2 (mean pair P&L >= $min_edge)."""
    w = Q.frame(history=True).dropna(subset=['da_east', 'rt_east', 'da_ottawa', 'rt_ottawa']).sort_values(['date', 'he'])
    w['pair'] = w.eo_da - w.eo_rt                                # + = sell East / buy Ottawa made money
    days = sorted(w.date.unique()); start = start or days[min(look + 2, len(days) - 1)]; out = []
    for D in days:
        if D < start: continue
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=look + 2)).date().isoformat()
        tr = w[(w.date <= c2) & (w.date > lo)].groupby('he').pair.agg(['mean', 'count'])
        te = w[w.date == D].copy(); m = te.he.map(tr['mean'])
        te['side'] = np.where(m >= min_edge, 1, np.where(m <= -min_edge, -1, 0)); out.append(te)
    t = pd.concat(out); t['pl'] = t.side * t.pair
    return w, t

def intertie_da_test(zone):
    """hourly DA model with and without bid-time intertie inputs (PQ.AT export / import limit, NY limits, all known at 08:08 EST)."""
    import hourly as HR
    d = HR.frame(zone)
    L = pd.read_csv(C.DATA / 'nrg' / 'da_intertie_limits_pq.csv')[['date', 'he', 'LIM_PQAT_EXP', 'LIM_PQAT_IMP']]
    N = pd.read_csv(C.DATA / 'nrg' / 'da_intertie_limits.csv')[['date', 'he', 'LIM_NY_EXP']]
    d = d.merge(L, on=['date', 'he'], how='left').merge(N, on=['date', 'he'], how='left')
    d['atx'] = -d.LIM_PQAT_EXP / 1000; d['ati'] = d.LIM_PQAT_IMP / 1000; d['nyx'] = -d.LIM_NY_EXP / 1000
    dates = sorted(d.dropna(subset=['da']).date.unique()); res = {}
    for name, feats in (('base', HR.FEATS), ('+ Quebec/NY limits', HR.FEATS + ['atx', 'ati', 'nyx'])):
        rows = []
        for i in range(21, len(dates)):
            D = dates[i]; tr = d[(d.date >= dates[i - 21]) & (d.date < D) & d.da.notna()]; te = d[d.date == D]
            e = HR.fit_predict(tr, te, feats=feats); rows.append(e[['date', 'he', 'da', 'p_h']])
        r = pd.concat(rows); res[name] = (r.p_h - r.da).abs().mean()
    return res, len(dates)

if __name__ == '__main__':
    for z in ('EAST', 'OTTAWA'):
        print(f'\n================ {z} (limit {LIM[z]} MW) ================')
        x = sig_frame(z); s = x[x.signal == 'SELL'].dropna(subset=['sp'])
        print(f'test window {x.date.min()}..{x.date.max()}, {x.date.nunique()} days')
        for n, m in (('v2 SELL all', s.index == s.index), ('  tight', s.why == 'tight'), ('  surplus', s.why == 'surplus'),
                     ('  tight & trips >= 500', (s.why == 'tight') & (s.trips_d1 >= 500)), ('  tight & trips < 500', (s.why == 'tight') & (s.trips_d1 < 500))):
            v = s[m]
            if len(v) < 10: print(f'  {n:24s} h {len(v)}'); continue
            lo, hi = FF.boot(v.sp.values, v.date.values); print(f'  {n:24s} h {len(v):4d} d {v.date.nunique():3d} DA-RT {v.sp.mean():+7.2f} ({lo:+.2f}..{hi:+.2f}) win {(v.sp>0).mean()*100:.0f}%')
        print('  ladders (score 5 SELL / 4 SELL-L / 3 else), capped at the zone limit:')
        for b in (False, True): print('   ', 'trips x1.5 on tight' if b else 'no boost          ', ladder_net(x, z, b))
        res, n = intertie_da_test(z); print(f'  DA model MAE over {n} days:', {k: round(v, 3) for k, v in res.items()})
    w, t = spread_walk()
    print('\n================ East-Ottawa spread ================')
    print(f'{w.date.min()}..{w.date.max()}, {w.date.nunique()} days; DA spread E-O mean {w.eo_da.mean():+.2f} sd {w.eo_da.std():.2f}; RT spread mean {w.eo_rt.mean():+.2f} sd {w.eo_rt.std():.2f}')
    print('always sell East / buy Ottawa (pair P&L per MW-h):', round(w.pair.mean(), 2), ' by HE block:', w.groupby(pd.cut(w.he, [0, 6, 11, 16, 21, 24])).pair.mean().round(2).to_dict())
    tt = t[t.side != 0]; lo, hi = FF.boot(tt.pl.values, tt.date.values)
    print(f'walk-forward pair (trailing 28 d by HE, trade if |edge| >= $1): {len(tt)} h on {tt.date.nunique()} days, {tt.pl.mean():+.2f} $/MWh ({lo:+.2f}..{hi:+.2f}), win {(tt.pl>0).mean()*100:.0f}%, sides {tt.side.value_counts().to_dict()}')
    print('  worst hours:', tt.nsmallest(5, 'pl')[['date', 'he', 'side', 'eo_da', 'eo_rt', 'pl']].round(1).to_dict('records'))
    t.to_csv(C.DATA / 'eo_spread_walk.csv', index=False)
