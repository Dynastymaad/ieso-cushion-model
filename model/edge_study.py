"""edge_study.py -- is there a tradeable signal?  Everything walk-forward, bid-time inputs only.
Outputs data/es_*.csv and prints the tables used in notes/Edge_Study.md.
Spread = DA - RT (positive = a virtual SELL / offer made money)."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 400); pd.set_option('display.max_columns', 40)
rng = np.random.default_rng(7)
BLKS = [(1, 6, 'night HE1-6'), (7, 11, 'morning HE7-11'), (12, 16, 'midday HE12-16'), (17, 21, 'evening HE17-21'), (22, 24, 'late HE22-24')]
BLKMAP = {h: n for a, b, n in BLKS for h in range(a, b + 1)}

def prices():
    p = pd.read_csv(C.DATA / 'prices_hourly.csv'); f = C.DATA / 'rt_patch.csv'
    if f.exists():
        x = pd.read_csv(f); p = p.merge(x, on=['date', 'he', 'zone'], how='left', suffixes=('', '_p'))
        for c in ['rt', 'rt_min5', 'rt_max5']: p[c] = p[c].fillna(p[c + '_p'])
        p = p.drop(columns=[c + '_p' for c in ['rt', 'rt_min5', 'rt_max5']])
    return p

def base(zone):
    p = prices(); p = p[p.zone == zone][['date', 'he', 'da', 'rt']]
    a = C.adq2('preDA')[['date', 'he', 'head', 'dem_fc', 'wind_fc', 'solar_fc', 'gas_av', 'hyd_av', 'nuc_av']]
    L = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'lf_tesla', 'lf_adq2', 'ont_dem']]
    ny = pd.read_csv(C.DATA / 'nyiso_zoneA_da.csv'); ne = pd.read_csv(C.DATA / 'nyiso_dam_energy.csv')[['date', 'he', 'ny_dni_oh']]
    h = pd.read_csv(C.DATA / f'bt_hourly_{zone}.csv')[['date', 'he', 'p_h', 'p_s']]
    h['p_da'] = 0.5 * h.p_h + 0.5 * h.p_s.fillna(h.p_h)
    q = pd.read_csv(C.DATA / f'bt_quantiles_{zone}.csv')[['date', 'he', 'q10', 'q25', 'q50', 'q75', 'q90']]
    d = p.merge(a, on=['date', 'he'], how='left').merge(L, on=['date', 'he'], how='left').merge(ny, on=['date', 'he'], how='left') \
         .merge(ne, on=['date', 'he'], how='left').merge(h[['date', 'he', 'p_da']], on=['date', 'he'], how='left').merge(q, on=['date', 'he'], how='left')
    d = d[d.date >= '2026-06-28'].sort_values(['date', 'he']).reset_index(drop=True)
    d['dow'] = pd.to_datetime(d.date).dt.dayofweek; d['wkend'] = (d.dow >= 5).astype(int)
    d['blk'] = d.he.map(BLKMAP); d['sp'] = d.da - d.rt
    d['gapT'] = d.lf_tesla - d.lf_adq2
    return d

def da_errors(d, zone):
    e = d.dropna(subset=['p_da', 'da']).copy(); e['err'] = e.p_da - e.da
    e.to_csv(C.DATA / f'es_da_errors_hourly_{zone}.csv', index=False)
    print(f'\n=== 1. DA forecast error {zone}: model minus published DA (+ = model too high) ===')
    print(f'hours {len(e)}, days {e.date.nunique()}  mean {e.err.mean():+.2f}  median {e.err.median():+.2f}  MAE {e.err.abs().mean():.2f}')
    print('share model too high: %.1f%%   too low: %.1f%%' % ((e.err > 0).mean() * 100, (e.err < 0).mean() * 100))
    print('error percentiles:', dict(e.err.quantile([.01, .05, .1, .25, .5, .75, .9, .95, .99]).round(2)))
    print('error histogram ($):'); print(pd.cut(e.err, [-999, -30, -15, -10, -5, -2, 2, 5, 10, 15, 30, 999]).value_counts().sort_index().to_string())
    print('\nby HE (mean, median, MAE, % too high):')
    print(e.groupby('he').err.agg(mean='mean', median='median', mae=lambda x: x.abs().mean(), hi=lambda x: (x > 0).mean() * 100).round(1).T.to_string())
    print('\nby weekday (0=Mon):'); print(e.groupby('dow').err.agg(mean='mean', median='median', mae=lambda x: x.abs().mean()).round(2).T.to_string())
    e['da_band'] = pd.cut(e.da, [0, 30, 40, 50, 60, 80, 120, 999])
    print('\nby published DA level:'); print(e.groupby('da_band').err.agg(n='count', mean='mean', median='median', mae=lambda x: x.abs().mean()).round(2).to_string())
    dd = e.groupby('date').agg(dow=('dow', 'first'), da=('da', 'mean'), fc=('p_da', 'mean'), err=('err', 'mean'),
                               mae=('err', lambda x: x.abs().mean()), worst=('err', lambda x: x.loc[x.abs().idxmax()]),
                               hi_hours=('err', lambda x: int((x > 0).sum())))
    ep = e[e.he.between(7, 22)].groupby('date').agg(da_on=('da', 'mean'), fc_on=('p_da', 'mean'))
    dd = dd.join(ep); dd['err_on'] = dd.fc_on - dd.da_on
    dd.round(2).to_csv(C.DATA / f'es_da_errors_daily_{zone}.csv')
    print(f'\ndaily: {len(dd)} days, model on-peak too high on {(dd.err_on > 0).sum()} days, too low on {(dd.err_on < 0).sum()}')
    print(dd.round(2).to_string())
    print('\nworst 12 hours model TOO LOW:'); print(e.nsmallest(12, 'err')[['date', 'he', 'da', 'p_da', 'err', 'head']].round(1).to_string(index=False))
    print('\nworst 12 hours model TOO HIGH:'); print(e.nlargest(12, 'err')[['date', 'he', 'da', 'p_da', 'err', 'head']].round(1).to_string(index=False))

def spread_anatomy(d, zone):
    s = d.dropna(subset=['sp']).copy()
    print(f'\n=== 2. DA - RT anatomy {zone}: {s.date.nunique()} days, {len(s)} hours ({s.date.min()} to {s.date.max()}) ===')
    print(f'mean {s.sp.mean():+.2f}  median {s.sp.median():+.2f}  DA>RT in {(s.sp > 0).mean() * 100:.1f}% of hours')
    print('spread percentiles:', dict(s.sp.quantile([.01, .05, .1, .25, .5, .75, .9, .95, .99]).round(2)))
    print('\nby HE, weekday(0) vs weekend(1): mean / median / % DA>RT')
    print(s.groupby(['wkend', 'he']).sp.agg(mean='mean', median='median', win=lambda x: (x > 0).mean() * 100).round(1).unstack(0).to_string())
    blk = s.groupby(['date', 'blk']).sp.mean().unstack()[[n for _, _, n in BLKS]].round(1)
    blk['dow'] = pd.to_datetime(blk.index).dayofweek; blk['day'] = s.groupby('date').sp.mean().round(1)
    blk.to_csv(C.DATA / f'es_spread_daily_blocks_{zone}.csv')
    print('\nper day, mean DA-RT by block (+ = sell won):'); print(blk.to_string())
    print('\nshare of days each block favoured SELL (%):', dict(((blk[[n for _, _, n in BLKS]] > 0).mean() * 100).round(0)))
    mo = blk['morning HE7-11']
    print('morning HE7-11: mean %+.2f, median %+.2f, sell won %d of %d days; weekends mean %+.2f' % (mo.mean(), mo.median(), (mo > 0).sum(), mo.notna().sum(), mo[blk.dow >= 5].mean()))
    print('\nlargest 15 hours RT >> DA (the sell risk):')
    print(s.nsmallest(15, 'sp')[['date', 'he', 'da', 'rt', 'sp', 'head', 'gapT']].round(1).to_string(index=False))

FE = ['head_k', 'gapT_k', 'wind_k', 'dem_k', 'wkend', 'prof', 'lag2', 'nyx', 'pda']

def features(d):
    d = d.copy()
    d['head_k'] = d['head'] / 1000; d['gapT_k'] = d.gapT / 1000; d['wind_k'] = d.wind_fc / 1000; d['dem_k'] = d.dem_fc / 1000
    d['nyx'] = d.nyA_da - d.p_da; d['pda'] = d.p_da
    l2 = d[['date', 'he', 'sp']].copy(); l2['date'] = (pd.to_datetime(l2.date) + pd.Timedelta(days=2)).dt.date.astype(str)
    return d.merge(l2.rename(columns={'sp': 'lag2'}), on=['date', 'he'], how='left')

def walk_signals(d, win=42, minn=21):
    d = features(d); out = []
    for D in sorted(d.date.unique()):
        cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()   # RT fully known through D-2 at the bid deadline
        lo = (pd.Timestamp(cut) - pd.Timedelta(days=win)).date().isoformat()
        tr = d[(d.date <= cut) & (d.date > lo) & d.sp.notna()].copy(); te = d[d.date == D].copy()
        if tr.date.nunique() < minn: continue
        prof = tr.groupby(['wkend', 'he']).sp.median().rename('prof').reset_index()
        te = te.merge(prof, on=['wkend', 'he'], how='left'); tr = tr.merge(prof, on=['wkend', 'he'], how='left')
        feats = [f for f in FE if tr[f].notna().mean() > .8]
        t = tr.dropna(subset=feats); y = t.sp.clip(-40, 40).values
        mu, sd = t[feats].mean(), t[feats].std().replace(0, 1)
        X = np.c_[np.ones(len(t)), ((t[feats] - mu) / sd).values]; R = np.eye(X.shape[1]) * 25.0; R[0, 0] = 0
        beta = np.linalg.solve(X.T @ X + R, X.T @ y)
        te['s_hat'] = np.c_[np.ones(len(te)), ((te[feats].fillna(mu) - mu) / sd).values] @ beta
        best, bthr = -1e9, 99999
        for thr in [7000, 7500, 8000, 8500, 9000, 9500, 10000, 99999]:
            m = tr[tr['head'] < thr]
            if len(m) >= 40 and m.sp.mean() > best: best, bthr = m.sp.mean(), thr
        te['thr_wf'] = bthr; out.append(te)
    return pd.concat(out)

def pnl(sig, sp): return np.where(sig > 0, sp, np.where(sig < 0, -sp, np.nan))

def boot_ci(t, n=2000):
    g = t.groupby('date').pl.agg(['sum', 'count'])
    if len(g) < 5: return (np.nan, np.nan)
    s, c = g['sum'].values, g['count'].values; k = len(g); r = []
    for _ in range(n):
        i = rng.integers(0, k, k); r.append(s[i].sum() / max(c[i].sum(), 1))
    return tuple(np.percentile(r, [5, 95]).round(2))

def score(te, name, sig):
    x = te[['date', 'he', 'sp']].copy(); x['sig'] = np.asarray(sig); x['pl'] = pnl(x.sig, x.sp)
    t = x.dropna(subset=['sp', 'pl'])
    if not len(t): return dict(rule=name, hours=0)
    daily = t.groupby('date').pl.sum(); lo, hi = boot_ci(t)
    return dict(rule=name, hours=len(t), sells=int((t.sig > 0).sum()), buys=int((t.sig < 0).sum()), usd_mwh=round(t.pl.mean(), 2),
                ci90=f'{lo:+.2f}..{hi:+.2f}', win=round((t.pl > 0).mean() * 100, 1), total=round(t.pl.sum()), days=len(daily),
                days_up=round((daily > 0).mean() * 100), worst_day=round(daily.min()), best_day=round(daily.max()))

def signals(d, zone):
    te = walk_signals(d); te.to_csv(C.DATA / f'es_signals_{zone}.csv', index=False)
    ok = te.dropna(subset=['sp', 's_hat']).copy()
    print(f'\n=== 3. Walk-forward signals {zone}: {ok.date.nunique()} test days {ok.date.min()}..{ok.date.max()} ===')
    base = (ok.sp > 0).mean(); hit = (np.sign(ok.s_hat) == np.sign(ok.sp)).mean()
    print(f'sign hit-rate of regression: {hit * 100:.1f}% vs {max(base, 1 - base) * 100:.1f}% for always picking the majority side; corr = {np.corrcoef(ok.s_hat, ok.sp)[0, 1]:.3f}')
    for f in ['prof', 'lag2', 'head_k', 'gapT_k', 'wind_k', 'dem_k', 'nyx', 'pda']:
        c = ok[[f, 'sp']].dropna(); print(f'  corr({f:7s}, spread) = {c.corr().iloc[0, 1]:+.3f}  (n={len(c)})')
    ok['q'] = pd.qcut(ok.s_hat.rank(method='first'), 5, labels=['Q1 lowest', 'Q2', 'Q3', 'Q4', 'Q5 highest'])
    print('regression forecast quintile -> realised spread:')
    print(ok.groupby('q').agg(s_hat=('s_hat', 'mean'), realised=('sp', 'mean'), median=('sp', 'median'), win=('sp', lambda x: (x > 0).mean() * 100), n=('sp', 'count')).round(2).to_string())
    tight = (te['head'] < 8500) & te.he.between(14, 21); tes = te.gapT <= -600; teb = (te.gapT >= 600) & ~tight
    v1 = np.where(tight | tes, 1, np.where(teb, -1, 0)); reg = np.where(te.s_hat > 0, 1, np.where(te.s_hat < -2, -1, 0))
    R = pd.DataFrame([score(te, 'A sell every hour', np.ones(len(te))),
         score(te, 'B v1 rules (in-sample 8,500/600)', v1),
         score(te, 'C v1 sell side only', np.where(tight | tes, 1, 0)),
         score(te, 'D v1 buy side only', np.where(teb, -1, 0)),
         score(te, 'E headroom rule, threshold picked walk-forward', np.where(te['head'] < te.thr_wf, 1, 0)),
         score(te, 'F hour profile: sell if trailing median > 0', np.where(te.prof > 0, 1, 0)),
         score(te, 'G hour profile both ways (buy if < -2)', np.where(te.prof > 0, 1, np.where(te.prof < -2, -1, 0))),
         score(te, 'H regression: sell if > 0', np.where(te.s_hat > 0, 1, 0)),
         score(te, 'I regression both ways (buy if < -2)', reg),
         score(te, 'J regression strong: sell if > 3', np.where(te.s_hat > 3, 1, 0)),
         score(te, 'K sell unless Tesla >= 600 above IESO', np.where(te.gapT >= 600, 0, 1)),
         score(te, 'L sell all except HE17-21 when not tight', np.where(te.he.between(17, 21) & (te['head'] >= 8500), 0, 1))])
    print(R.to_string(index=False)); R.to_csv(C.DATA / f'es_rules_{zone}.csv', index=False)
    q = te.dropna(subset=['q50', 'sp']); rows = []
    for k in ['none', 'q10', 'q25', 'q50', 'q75']:
        cl = np.ones(len(q), bool) if k == 'none' else (q.da >= q[k]).values; t = q[cl]
        rows.append(dict(offer_at=k, cleared=len(t), of=len(q), usd_mwh=round(t.sp.mean(), 2), win=round((t.sp > 0).mean() * 100, 1),
                         total=round(t.sp.sum()), missed_hours_avg=round(q[~cl].sp.mean(), 2) if (~cl).any() else np.nan))
    print(f'\noffer-price execution, sell every hour but only clears if DA >= offer ({q.date.nunique()} days):'); print(pd.DataFrame(rows).to_string(index=False))
    x = te[['date', 'he', 'sp']].copy(); x['A'] = pnl(np.ones(len(te)), te.sp); x['B'] = pnl(v1, te.sp); x['I'] = pnl(reg, te.sp); x['bs'] = v1; x['rs'] = reg
    dr = x.groupby('date').agg(spread=('sp', 'mean'), sell_all=('A', 'sum'), v1_sell=('bs', lambda z: int((z > 0).sum())), v1_buy=('bs', lambda z: int((z < 0).sum())),
                               v1=('B', 'sum'), reg_sell=('rs', lambda z: int((z > 0).sum())), reg_buy=('rs', lambda z: int((z < 0).sum())), reg=('I', 'sum')).round(1)
    dr.insert(0, 'dow', pd.to_datetime(dr.index).dayofweek); dr.to_csv(C.DATA / f'es_daily_record_{zone}.csv')
    print('\ndaily record, 1 MW per hour ($):'); print(dr.to_string())
    sel = (ok.s_hat > 0).values; real = ok.sp.values[sel].mean(); sims = [ok.sp.values[rng.permutation(sel)].mean() for _ in range(2000)]
    print(f'\npermutation: regression-selected sell hours avg {real:+.2f} vs random same-count {np.mean(sims):+.2f}; p = {(np.array(sims) >= real).mean():.3f}')
    x['month'] = x.date.str[:7]; print('\nby month $/MWh:'); print(x.groupby('month')[['A', 'B', 'I']].mean().round(2).to_string())
    return te

def generation(zone):
    p = prices(); p = p[p.zone == zone][['date', 'he', 'da', 'rt']]; p['sp'] = p.da - p.rt
    f = pd.read_csv(C.DATA / 'adq3_final.csv'); f['da_net_exp'] = -f.exp_sch.fillna(0) - f.imp_sch.fillna(0)
    sch = f[['date', 'he', 'nuclear_sch', 'gas_sch', 'hydro_sch', 'wind_sch', 'solar_sch', 'storage_sch', 'da_net_exp']]
    g = pd.read_csv(C.DATA / 'gas_ladder.csv'); g['gas_rt'] = g.cc_out + g.pk_out + g.ln_out
    fa = C.fuel_actual(); fa = fa[[c for c in ['date', 'he', 'g_wind', 'g_solar', 'g_nuclear', 'g_hydro', 'g_gas'] if c in fa]]
    it = pd.read_csv(C.DATA / 'intertie_actual.csv')[['date', 'he', 'tot_flow']]
    dem = C.actual_demand()[['date', 'he', 'ont_dem']]
    pre = C.adq2('preDA')[['date', 'he', 'dem_fc', 'wind_fc', 'head']].rename(columns={'dem_fc': 'dem_pre', 'wind_fc': 'wind_pre'})
    d = p.merge(sch, on=['date', 'he']).merge(g[['date', 'he', 'gas_rt', 'cc_out', 'pk_out', 'ln_out', 'hy_out', 'nu_out']], on=['date', 'he']) \
         .merge(fa, on=['date', 'he'], how='left').merge(it, on=['date', 'he'], how='left').merge(dem, on=['date', 'he'], how='left').merge(pre, on=['date', 'he'], how='left')
    d = d.dropna(subset=['sp'])
    d['d_gas'] = d.gas_rt - d.gas_sch; d['d_hydro'] = d.hy_out - d.hydro_sch; d['d_nuc'] = d.nu_out - d.nuclear_sch
    d['d_wind'] = d.g_wind - d.wind_sch; d['d_solar'] = d.g_solar - d.solar_sch; d['d_exp'] = d.tot_flow - d.da_net_exp
    d['d_dem'] = d.ont_dem - d.dem_pre; d['d_wind_fc'] = d.g_wind - d.wind_pre
    d.to_csv(C.DATA / f'es_generation_{zone}.csv', index=False)
    print(f'\n=== 4. Generation: RT actual minus DA schedule vs DA-RT ({zone}, {d.date.nunique()} days, {len(d)} h) ===')
    cols = ['d_dem', 'd_wind', 'd_wind_fc', 'd_solar', 'd_nuc', 'd_exp', 'd_gas', 'd_hydro']
    print(d[cols].describe(percentiles=[.1, .5, .9]).round(0).T.to_string())
    print('\ncorrelation with DA-RT (causes on top; gas/hydro are the RESPONSE, shown for reading only):')
    for c in cols: print(f'  {c:10s} {d[[c, "sp"]].dropna().corr().iloc[0, 1]:+.3f}')
    dd = d.dropna(subset=['d_wind', 'd_exp', 'd_dem', 'd_solar', 'd_nuc'])
    X = dd[['d_dem', 'd_wind', 'd_solar', 'd_nuc', 'd_exp']].values / 1000; y = dd.sp.clip(-60, 60).values
    Xc = np.c_[np.ones(len(X)), X]; b = np.linalg.lstsq(Xc, y, rcond=None)[0]; r2 = 1 - ((y - Xc @ b) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print('\nOLS DA-RT per +1,000 MW of (actual minus what DA assumed):')
    for n, v in zip(['const', 'demand', 'wind', 'solar', 'nuclear', 'net exports'], b): print(f'  {n:12s} {v:+7.2f} $/MWh')
    print(f'  R2 = {r2:.3f}, n = {len(dd)}')
    corr = {c: d[[c, 'sp']].dropna().corr().iloc[0, 1] for c in cols}
    pd.DataFrame([dict(driver=n, coef=round(v, 2), corr=round(corr.get(k, np.nan), 3), sd_mw=round(d[k].std()) if k in d else np.nan)
                  for n, k, v in zip(['demand', 'wind', 'solar', 'nuclear', 'net exports'], ['d_dem', 'd_wind', 'd_solar', 'd_nuc', 'd_exp'], b[1:])]
                 + [dict(driver='R2', coef=round(r2, 3), corr=np.nan, sd_mw=len(dd))]).to_csv(C.DATA / 'es_drivers.csv', index=False)
    print('\nDA price level vs DA schedule, corr:')
    for c in ['gas_sch', 'hydro_sch', 'nuclear_sch', 'wind_sch', 'da_net_exp']: print(f'  {c:12s} {d[[c, "da"]].corr().iloc[0, 1]:+.3f}')
    d['gas_band'] = pd.cut(d.gas_sch, [0, 2000, 3000, 4000, 5000, 6000, 8000, 12000])
    gb = d.groupby('gas_band').agg(n=('da', 'count'), da=('da', 'mean'), rt=('rt', 'mean'), spread=('sp', 'mean'), sell_win=('sp', lambda x: (x > 0).mean() * 100)).round(1)
    gb.index = gb.index.astype(str); gb.to_csv(C.DATA / 'es_gasband.csv')
    print('\nby DA gas schedule (MW):'); print(d.groupby('gas_band').agg(n=('da', 'count'), da=('da', 'mean'), rt=('rt', 'mean'), spread=('sp', 'mean'), sell_win=('sp', lambda x: (x > 0).mean() * 100)).round(1).to_string())
    print('\nLennox running in RT vs not:'); print(d.groupby(d.ln_out > 0).agg(n=('da', 'count'), da=('da', 'mean'), rt=('rt', 'mean'), spread=('sp', 'mean')).round(1).to_string())
    print('\nIESO pre-DA forecast bias (actual minus forecast), by HE: demand / wind')
    print(d.groupby('he')[['d_dem', 'd_wind_fc']].mean().round(0).T.to_string())
    return d

if __name__ == '__main__':
    for z in (sys.argv[1:] or ['TORONTO']):
        d = base(z); da_errors(d, z); spread_anatomy(d, z); signals(d, z)
        if z == 'TORONTO': generation(z)
