"""zone_bt17.py -- East and Ottawa on the full 17 months (NRGStream history May 2025 -> Sep 2026 + IESO archive).
Bid-time inputs only; every threshold learned on days <= D-2; fills simulated on the actual DA (bid clears if DA <= bid,
offer clears if DA >= offer), settled at RT. Zone limits: East 85 MW, Ottawa 100 MW per side per hour (IESO Table 2).
  python model/zone_bt17.py ladders | spread | quebec | all"""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV, fail_fix as FF, quebec as Q, boost_test as BT
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
LIM = {'EAST': 85, 'OTTAWA': 100}
RES = {}
HALVES = (('Jul-Jan', lambda d: d < '2026-02-01'), ('Feb-Sep', lambda d: d >= '2026-02-01'))

def frame(zone):
    e = pd.read_csv(C.DATA / f'dv_frame_{zone}.csv').sort_values(['date', 'he']).reset_index(drop=True)
    o = pd.read_csv(C.DATA / 'outage_features.csv')[['date', 'he', 'trips_d1']]
    e = e.merge(o, on=['date', 'he'], how='left'); e['branch'] = BT.branch(e)
    return e[e.date >= '2025-07-01']

def ladder_rows(e, zone, boost=True, scorer='live'):
    rows = []
    for r in e.dropna(subset=['da', 'rt', 'p_da', 'p_rt']).itertuples():
        s = 5 if r.v2 == 1 else (1 if (scorer == 'live' and r.buyband == -1) else 3)
        b, o = DV.ladder(s, r.p_da, r.p_rt)
        k = 1.5 if (boost and s == 5 and r.branch == 'tight' and (0 if pd.isna(r.trips_d1) else r.trips_d1) >= 500) else 1.0
        tb = [(q * k, p) for q, p in b if p is not None]; to = [(q * k, p) for q, p in o if p is not None]
        for side in (tb, to):
            tot = sum(q for q, _ in side)
            if tot > LIM[zone]: side[:] = [(q * LIM[zone] / tot, p) for q, p in side]
        mb = sum(q for q, p in tb if r.da <= p); ms = sum(q for q, p in to if r.da >= p)
        rows.append((r.date, r.he, s, r.branch, mb, ms, mb * (r.rt - r.da) + ms * (r.da - r.rt)))
    return pd.DataFrame(rows, columns=['date', 'he', 'score', 'branch', 'mw_b', 'mw_s', 'pl'])

def summ(x):
    d = x.groupby('date').pl.sum(); mw = x.mw_b.sum() + x.mw_s.sum(); cum = d.cumsum()
    lo, hi = FF.boot(x.pl.values / np.maximum(x.mw_b + x.mw_s, 1e-9) * 0 + x.pl.values, x.date.values) if len(x) > 50 else (np.nan, np.nan)
    return dict(days=len(d), mwh=int(mw), usd_mwh=round(x.pl.sum() / max(mw, 1), 2), net=round(d.sum()), made=round(d[d > 0].sum()), lost=round(d[d < 0].sum()),
                usd_day=round(d.mean()), worst_day=round(d.min()), p5_day=round(d.quantile(.05)), max_dd=round((cum - cum.cummax()).min()), days_up=round((d > 0).mean() * 100))

def ladders():
    for z in LIM:
        e = frame(z); print(f'\n================ {z} (cap {LIM[z]} MW/side/h), {e.date.min()}..{e.date.max()}, {e.date.nunique()} days ================')
        s = e[(e.v2 == 1) & e.sp.notna()]
        for n, m in (('v2 SELL all', s.index == s.index), ('  tight', s.branch == 'tight'), ('  surplus', s.branch == 'surplus'),
                     ('  tight & trips>=500', (s.branch == 'tight') & (s.trips_d1 >= 500))):
            for hn, hf in (('all', lambda d: d == d),) + HALVES:
                v = s[m & hf(s.date)]
                if len(v) < 20: continue
                lo, hi = FF.boot(v.sp.values, v.date.values)
                RES.setdefault(z, {}).setdefault('v2', {})[f'{n.strip()}|{hn}'] = dict(h=len(v), d=int(v.date.nunique()), mean=round(v.sp.mean(), 2), lo=round(lo, 2), hi=round(hi, 2))
                print(f'  {n:22s} {hn:8s} h {len(v):5d} d {v.date.nunique():3d}  DA-RT {v.sp.mean():+7.2f} ({lo:+.2f}..{hi:+.2f})  win {(v.sp>0).mean()*100:.0f}%')
        b = e[(e.buyband == -1) & e.sp.notna()]
        if len(b) > 20:
            lo, hi = FF.boot(-b.sp.values, b.date.values); print(f'  buy band (RT-DA)        all      h {len(b):5d} d {b.date.nunique():3d}  RT-DA {-b.sp.mean():+7.2f} ({lo:+.2f}..{hi:+.2f})')
        print('  ladders, capped:')
        R = {}
        for name, kw in (('live: v2=5, band=1, else 3, tight boost', dict(boost=True)), ('same, no boost', dict(boost=False)), ('v2=5 else 3 (no band)', dict(boost=True, scorer='nob'))):
            x = ladder_rows(e, z, **kw); R[name] = x
            print(f'    {name:40s}', summ(x))
            RES.setdefault(z, {})[name.split(':')[0].split(',')[0]] = summ(x)
            if name.startswith('live'):
                RES[z]['halves'] = {hn: summ(x[hf(x.date)]) for hn, hf in HALVES}
                for hn, hf in HALVES: print(f'      {hn:8s}', summ(x[hf(x.date)]))
                by = x.groupby('score').agg(mwh=('mw_s', 'sum'), mwb=('mw_b', 'sum'), pl=('pl', 'sum')); by['usd_mwh'] = (by.pl / (by.mwh + by.mwb)).round(2)
                print('      by score:', by.round(0).to_dict('index'))
                x.to_csv(C.DATA / f'zone_ladder_{z}.csv', index=False)

def spread(look=28, min_edge=1.0):
    w, t = Q_spread(look, min_edge)
    print(f'\n================ East-Ottawa spread, {w.date.min()}..{w.date.max()}, {w.date.nunique()} days ================')
    print(f'DA E-O mean {w.eo_da.mean():+.2f} sd {w.eo_da.std():.2f} | RT E-O mean {w.eo_rt.mean():+.2f} sd {w.eo_rt.std():.2f} | |RT E-O|>$20 in {(w.eo_rt.abs()>20).mean()*100:.1f}% of h')
    print('always sell East/buy Ottawa, $/MWh pair:', round(w.pair.mean(), 2), {k: round(v, 2) for k, v in w.groupby(pd.cut(w.he, [0, 6, 11, 16, 21, 24])).pair.mean().items()})
    for hn, hf in (('all', lambda d: d == d),) + HALVES:
        v = w[hf(w.date)]; lo, hi = FF.boot(v.pair.values, v.date.values); print(f'   always-pair {hn:8s} {v.pair.mean():+.2f} ({lo:+.2f}..{hi:+.2f}) median {v.pair.median():+.2f}')
    tt = t[t.side != 0]
    for hn, hf in (('all', lambda d: d == d),) + HALVES:
        v = tt[hf(tt.date)]; lo, hi = FF.boot(v.pl.values, v.date.values)
        print(f'walk-forward pair ({look} d by HE, |edge|>=${min_edge:g}) {hn:8s}: {len(v)} h on {v.date.nunique()} d, {v.pl.mean():+.2f} $/MWh ({lo:+.2f}..{hi:+.2f}), median {v.pl.median():+.2f}, win {(v.pl>0).mean()*100:.0f}%, sides {v.side.value_counts().to_dict()}')
    # DA-cleared version: the pair only happens when BOTH legs clear. Offer East at floor, bid Ottawa at cap -> always clears; P&L = 85 MW x pair
    d = tt.assign(pl85=tt.pl * 85).groupby('date').pl85.sum()
    print(f'   at 85 MW/leg: net {d.sum():+,.0f}, per trade-day {d.mean():+,.0f}, worst day {d.min():+,.0f}, best {d.max():+,.0f}')
    print('   worst hours:', tt.nsmallest(5, 'pl')[['date', 'he', 'side', 'eo_da', 'eo_rt', 'pl']].round(1).to_dict('records'))
    # conditional on DA basis being known at bid? no -- DA spread is unknown at the bid; check by headroom (bid-time) instead
    w['hb'] = pd.cut(w['head'], [-1e9, 4000, 6000, 8500, 1e9], labels=['<4k', '4-6k', '6-8.5k', '>8.5k'])
    print('   pair by bid-time headroom:', w.groupby('hb').pair.agg(['mean', 'median', 'count']).round(2).to_dict('index'))
    t.to_csv(C.DATA / 'eo_spread_walk.csv', index=False)
    h = w[(w.he >= 12) & (w.he <= 16)]; ho = h[h.date < '2026-06-27']; lo, hi = FF.boot(ho.pair.values, ho.date.values); d = ho.groupby('date').pair.sum() * 85
    a_lo, a_hi = FF.boot(w.pair.values, w.date.values)
    RES['spread'] = dict(start=w.date.min(), end=w.date.max(), days=int(w.date.nunique()), all_mean=round(w.pair.mean(), 2), all_lo=round(a_lo, 2), all_hi=round(a_hi, 2),
                         he1216_holdout=dict(h=len(ho), mean=round(ho.pair.mean(), 2), lo=round(lo, 2), hi=round(hi, 2), median=round(ho.pair.median(), 2), win=round((ho.pair > 0).mean() * 100),
                                             wins_mean=round(ho.pair.clip(-50, 50).mean(), 2), day85_mean=round(d.mean()), day85_worst=round(d.min()), day85_best=round(d.max())),
                         he1216_found=dict(mean=round(h[h.date >= '2026-06-27'].pair.mean(), 2)),
                         walk=dict(h=len(tt), mean=round(tt.pl.mean(), 2)))
    for lk, me in ((56, 1.0), (28, 2.0), (14, 1.0)):
        _, t2 = Q_spread(lk, me); v = t2[t2.side != 0]; lo, hi = FF.boot(v.pl.values, v.date.values)
        print(f'   sensitivity look {lk} edge ${me:g}: {len(v)} h, {v.pl.mean():+.2f} ({lo:+.2f}..{hi:+.2f})')

def Q_spread(look, min_edge):
    w = Q.frame(history=True).dropna(subset=['da_east', 'rt_east', 'da_ottawa', 'rt_ottawa']).sort_values(['date', 'he'])
    w['pair'] = w.eo_da - w.eo_rt
    days = sorted(w.date.unique()); out = []
    for D in days[look + 2:]:
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=look + 2)).date().isoformat()
        m = w[(w.date <= c2) & (w.date > lo)].groupby('he').pair.mean()
        te = w[w.date == D].copy(); mm = te.he.map(m); te['edge'] = mm
        te['side'] = np.where(mm >= min_edge, 1, np.where(mm <= -min_edge, -1, 0)); out.append(te)
    t = pd.concat(out); t['pl'] = t.side * t.pair
    return w, t

def ols(y, X, names):
    X = np.column_stack([np.ones(len(y))] + X); b, *_ = np.linalg.lstsq(X, y, rcond=None); r = y - X @ b
    n, k = X.shape; s2 = r @ r / (n - k); XtXi = np.linalg.inv(X.T @ X)
    # HAC-lite: cluster by day would be better; use day-block bootstrap for the headline coefficient instead
    se = np.sqrt(np.diag(XtXi) * s2); r2 = 1 - (r @ r) / ((y - y.mean()) @ (y - y.mean()))
    return pd.DataFrame({'coef': b, 'se': se, 't': b / se}, index=['const'] + names).round(3), round(r2, 3), n

def quebec():
    w = Q.frame(history=True)
    s = pd.read_csv(C.DATA / 'qc_nrg_sched.csv'); w = w.merge(s, on=['date', 'he'], how='left')
    w = w[w.date >= '2025-05-01'].copy(); w['mon'] = w.date.str[:7]
    print(f'\n================ Quebec interties, {w.date.min()}..{w.date.max()}, {w.date.nunique()} days ================')
    m = w.groupby('mon').agg(pq_exp=('pq_exp', 'mean'), pq_imp=('pq_imp', 'mean'), at_exp=('pq_at_exp', 'mean'), at_lim=('at_exp_lim', 'mean'), at_use=('at_exp_use', 'mean'),
                             e_basis=('east_da_basis', 'mean'), o_basis=('ottawa_da_basis', 'mean'), eo_da=('eo_da', 'mean'), ozp=('da_ontario', 'mean')).round(2)
    print(m.to_string())
    print('share of hours PQ.AT exports >= 95% of the DA limit:', round((w.at_exp_use >= .95).mean() * 100, 1), '%')
    print('NRG "Quebec Export Scheduled - DAA" vs actual PQ exports: corr', round(w[['qc_exp_daa', 'pq_exp']].corr().iloc[0, 1], 2), ' mean', round(-w.qc_exp_daa.mean()), 'vs', round(w.pq_exp.mean()))
    # 1. what moves the East / Ottawa DA basis (zone - OZP)? contemporaneous, explanatory
    v = w.dropna(subset=['east_da_basis', 'ottawa_da_basis', 'pq_exp', 'head', 'dem_fc', 'at_exp_lim']).copy()
    v['exp_k'] = v.pq_exp / 1000; v['imp_k'] = v.pq_imp / 1000; v['head_k'] = v['head'] / 1000; v['dem_k'] = v.dem_fc / 1000
    v['near_lim'] = (v.at_exp_use >= .95).astype(float); v['ozp'] = v.da_ontario
    names = ['exp_k', 'imp_k', 'near_lim', 'ozp', 'head_k', 'dem_k']
    for y in ('east_da_basis', 'ottawa_da_basis', 'eo_da'):
        tab, r2, n = ols(v[y].values, [v[c].values for c in names], names); print(f'\n  {y} ~ Quebec exports/imports + near-limit + OZP + headroom + demand   (R2 {r2}, n {n})'); print(tab.to_string())
    # day-block bootstrap for the export coefficient (hours inside a day are not independent)
    rng = np.random.default_rng(11); days = v.date.unique(); g = {d: i for d, i in v.groupby('date').groups.items()}; bs = []
    for _ in range(300):
        idx = np.concatenate([g[d] for d in rng.choice(days, len(days))]); u = v.loc[idx]
        X = np.column_stack([np.ones(len(u))] + [u[c].values for c in names]); bs.append(np.linalg.lstsq(X, u.east_da_basis.values, rcond=None)[0][1:4])
    bs = np.array(bs); RES.setdefault('quebec', {}).update(east_exp=[round(x, 2) for x in np.percentile(bs[:, 0], [5, 50, 95])], east_near=[round(x, 2) for x in np.percentile(bs[:, 2], [5, 50, 95])])
    for y in ('ottawa_da_basis', 'eo_da'):
        tb_, _, _ = ols(v[y].values, [v[c].values for c in names], names); RES['quebec'][y] = dict(exp=float(tb_.loc['exp_k', 'coef']), exp_se=float(tb_.loc['exp_k', 'se']), imp=float(tb_.loc['imp_k', 'coef']))
    RES['quebec']['share_at_limit'] = round((w.at_exp_use >= .95).mean() * 100, 1)
    RES['quebec']['monthly'] = m.reset_index().to_dict('records')
    print('  East basis, day-bootstrap 90% CI: exp_k', np.percentile(bs[:, 0], [5, 95]).round(2), ' imp_k', np.percentile(bs[:, 1], [5, 95]).round(2), ' near_lim', np.percentile(bs[:, 2], [5, 95]).round(2))
    # 2. Ontario-wide effect: exports to Quebec are load for Ontario -> OZP price
    tab, r2, n = ols(v.ozp.values, [v[c].values for c in ('exp_k', 'imp_k', 'head_k', 'dem_k')], ['exp_k', 'imp_k', 'head_k', 'dem_k'])
    print(f'\n  OZP DA ~ Quebec exports + imports + headroom + demand (R2 {r2}):'); print(tab.to_string())
    # 3. basis in $ by export bucket and hour block
    v['xb'] = pd.cut(v.pq_exp, [-1, 500, 1000, 1500, 1e9], labels=['<0.5GW', '0.5-1', '1-1.5', '>1.5GW'])
    print('\n  mean DA basis by Quebec export level:'); print(v.groupby('xb')[['east_da_basis', 'ottawa_da_basis', 'eo_da', 'ozp']].mean().round(2).assign(h=v.groupby('xb').size()).to_string())
    v['lb'] = pd.cut(v.at_exp_use, [-1, .5, .8, .95, 10], labels=['<50%', '50-80%', '80-95%', '>=95%'])
    print('  mean DA basis by PQ.AT use of export limit:'); print(v.groupby('lb')[['east_da_basis', 'ottawa_da_basis', 'eo_da']].mean().round(2).assign(h=v.groupby('lb').size()).to_string())
    # RT: do RT flows / limit changes explain East/Ottawa RT basis and the zone DA-RT spread?
    r = w.dropna(subset=['east_rt_basis', 'pq_at_flow', 'at_exp_lim_rt', 'at_exp_lim']).copy()
    r['lim_cut'] = ((r.at_exp_lim - r.at_exp_lim_rt) / 1000)                # + = RT export limit below the DA limit
    r['flow_k'] = r.pq_at_exp / 1000 - r.pq_at_imp / 1000; r['head_k'] = r['head'] / 1000   # scheduled net export on PQ.AT
    for y in ('east_sp', 'ottawa_sp', 'east_rt_basis'):
        u = r.dropna(subset=[y]); tab, r2, n = ols(u[y].values, [u[c].values for c in ('lim_cut', 'flow_k', 'head_k')], ['lim_cut', 'flow_k', 'head_k'])
        print(f'\n  {y} ~ RT PQ.AT limit cut vs DA + actual PQ.AT export flow + headroom (after-the-fact, R2 {r2}):'); print(tab.to_string())
    # 4. bid-time: does anything Quebec known at the bid improve the East/Ottawa DA forecast? walk-forward, trailing 60 d
    lagx = w.pivot_table(index='date', columns='he', values='pq_exp').shift(2).stack().rename('pq_exp_d2').reset_index()   # D-2 actual (published)
    for z in ('EAST', 'OTTAWA'):
        q = pd.read_csv(C.DATA / f'bt_quantiles_{z}.csv')[['date', 'he', 'p_da', 'da']]
        x = q.merge(w[['date', 'he', 'at_exp_lim', 'da_ontario', 'head']], on=['date', 'he'], how='left').merge(lagx, on=['date', 'he'], how='left')
        x['res'] = x.da - x.p_da; x = x.dropna(subset=['res', 'at_exp_lim', 'pq_exp_d2']).sort_values(['date', 'he'])
        days = sorted(x.date.unique()); base, adj = [], []
        for i, D in enumerate(days):
            if i < 60: continue
            tr = x[(x.date > days[i - 60]) & (x.date <= days[i - 2])]; te = x[x.date == D]
            F = lambda d: np.column_stack([np.ones(len(d)), d.at_exp_lim / 1000, d.pq_exp_d2 / 1000])
            A = F(tr); lam = 5.0; bcoef = np.linalg.solve(A.T @ A + lam * np.eye(3) * [0, 1, 1], A.T @ tr.res.values)
            base.append(te.res.abs().values); adj.append((te.res - F(te) @ bcoef).abs().values)
        base, adj = np.concatenate(base), np.concatenate(adj)
        RES.setdefault('quebec', {})[f'mae_{z}'] = [round(base.mean(), 3), round(adj.mean(), 3)]
        print(f'\n  {z} DA forecast MAE, walk-forward {len(days)-60} d: model {base.mean():.3f}  | + Quebec (bid-time PQ.AT DA limit, D-2 PQ exports) {adj.mean():.3f}')

if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what in ('ladders', 'all'): ladders()
    if what in ('spread', 'all'): spread()
    if what in ('quebec', 'all'): quebec()
    import json; f = C.DATA / 'zone_bt17.json'; old = json.loads(f.read_text()) if f.exists() else {}
    old.update(RES); f.write_text(json.dumps(old, default=float, indent=1)); print('->', f)
