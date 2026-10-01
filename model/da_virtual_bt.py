"""da_virtual_bt.py -- re-test of the VA Hub "DA Virtual" tab rules on 17 months (May 2025 - Sep 2026), per hub.
Everything bid-time (D-1 before 08:00 MT); every threshold either the VA Hub's own or learned on past days only.
Builds one frame (data/dv_frame_<zone>.csv) with:
  p_da   our walk-forward DA forecast (hourly.py hybrid, trailing 21 d)      q10..q90 DA range
  p_rt   RT forecast = p_da x trailing-28d median RT/DA ratio (same block, same tight/loose)
  VA Hub lean signals (1-10, rain excluded: no weather history), lean total, auto-score proxy,
  spike/collapse flags from total headroom, trailing RT-DA 7d/14d by HE ("hourly bias badges")
Then scores each rule as a price-taker (sell = DA-RT, buy = RT-DA, $/MWh, 90% bootstrap by day),
and back-tests the VA Hub 1-5 ladders (3 tiers, % of RT/DA) with clearing on the actual DA price."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, hourly as HR, edge_study as E
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
Q = [.1, .25, .5, .75, .9]

def build(zone):
    e = HR.walk(zone)                                           # p_h, trailing-21d ridge, all bid-time inputs
    e = e[['date', 'he', 'p_h', 'da', 'rt', 'head', 'dem_fc', 'resid_fc', 'gas_av', 'hyd_av', 'nyA_da', 'lf_tesla', 'lf_dynasty', 'blk', 'dow', 'wkend']].copy()
    e = e.rename(columns={'p_h': 'p_da'}).sort_values(['date', 'he']).reset_index(drop=True)
    a = C.adq2('preDA')[['date', 'he', 'wind_fc', 'solar_fc', 'gas_out', 'nuc_out', 'nuc_av']]
    e = e.merge(a, on=['date', 'he'], how='left')
    e['sp'] = e.da - e.rt; e['tb'] = (e['head'] < 8500).astype(int)
    e['lr_da'] = np.log(e.da.clip(lower=5) / e.p_da); e['lr_rt'] = np.log(e.rt.clip(lower=5) / e.p_da)
    # RT forecast + DA range: trailing 28 days of realised ratios, known through D-2 (RT) / D-1 (DA)
    days = sorted(e.date.unique()); out = []
    for D in days:
        g = e[e.date == D].copy()
        lo = (pd.Timestamp(D) - pd.Timedelta(days=29)).date().isoformat(); c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
        tr = e[(e.date >= lo) & (e.date < D)]
        if tr.date.nunique() < 14: continue
        for b in range(5):
            m = g.blk == b; pool = tr[tr.blk == b]
            for tb in (0, 1):
                mm = m & (g.tb == tb); pr = pool[(pool.tb == tb) & (pool.date <= c2)]
                if (pr.lr_rt.notna().sum()) < 40: pr = pool[pool.date <= c2]
                g.loc[mm, 'p_rt'] = g.loc[mm, 'p_da'] * np.exp(pr.lr_rt.median())
            qd = np.nanquantile(pool.lr_da, Q)
            for k, q in zip(['q10', 'q25', 'q50', 'q75', 'q90'], qd): g.loc[m, k] = g.loc[m, 'p_da'] * np.exp(q)
        out.append(g)
    e = pd.concat(out).reset_index(drop=True)
    # expected hydro and net exports (for gas need): hydro carry model where available, else 14-d median of actuals
    hy = pd.read_csv(C.DATA / 'bt_hydro_fc.csv')[['date', 'he', 'carry']].rename(columns={'carry': 'hyd_exp'})
    ia = pd.read_csv(C.DATA / 'intertie_actual.csv')[['date', 'he', 'tot_flow']]
    w = ia.pivot_table(index='date', columns='he', values='tot_flow').sort_index()
    med = w.shift(2).rolling(14, min_periods=7).median().stack().rename('exp_exp').reset_index()
    e = e.merge(hy, on=['date', 'he'], how='left').merge(med, on=['date', 'he'], how='left')
    e['hyd_exp'] = e.hyd_exp.fillna(e.groupby('he').hyd_exp.transform('median'))
    e['gas_hat'] = e.resid_fc - e.hyd_exp + e.exp_exp
    # ---- VA Hub lean signals (+ = bullish RT = buy DA) ----
    e = e.sort_values(['date', 'he']).reset_index(drop=True)
    grp = e.groupby('date')
    wl = e[['lf_tesla', 'lf_dynasty']].mean(axis=1)
    s = pd.DataFrame(index=e.index)
    s['l_daa'] = np.sign((wl - e.dem_fc).where(lambda x: x.abs() >= 200, 0))
    d7 = e.pivot_table(index='date', columns='he', values='dem_fc').shift(1).rolling(7, min_periods=5).mean().stack().rename('d7').reset_index()
    e = e.merge(d7, on=['date', 'he'], how='left'); s.index = e.index
    s['l_7d'] = np.sign((e.dem_fc - e.d7).where(lambda x: x.abs() >= 300, 0))
    wr = e.wind_fc - grp.wind_fc.shift(3); s['wind'] = -np.sign(wr.where(wr.abs() >= 400, 0))
    sr = e.solar_fc - grp.solar_fc.shift(1); s['solar'] = -np.sign(sr.where(sr.abs() >= 150, 0))
    gp = (e.gas_hat - grp.gas_hat.shift(1)) / grp.gas_hat.shift(1).clip(lower=500) * 100
    s['gas_ramp'] = np.sign(gp.where(gp.abs() >= 15, 0))
    s['gas_ledge'] = np.where(e.gas_hat >= 7200, 1, np.where(e.gas_hat <= 2500, -1, 0))
    s['gas_out'] = np.where(e.gas_out >= e.gas_out.expanding().quantile(.8), 1, np.where(e.gas_out <= e.gas_out.expanding().quantile(.2), -1, 0))
    s['nuc_out'] = np.where(e.nuc_out >= 4500, 1, np.where(e.nuc_out <= 2500, -1, 0))
    pct = (e.p_rt - e.p_da) / e.p_da.abs() * 100
    s['rt_vs_da'] = np.select([pct >= 30, pct >= 20, pct >= 10, pct <= -30, pct <= -20, pct <= -10], [3, 2, 1, -3, -2, -1], 0)
    for c in s: e['s_' + c] = s[c].fillna(0).astype(int)
    e['lean'] = s.fillna(0).sum(axis=1).clip(-13, 13).astype(int)
    # auto-score proxy: RT forecast vs DA forecast gap (VA Hub: 1 if gap >= +10, 2 if >= +5, 4 if <= -5, 5 if <= -10)
    gap = e.p_rt - e.p_da
    e['auto'] = np.select([gap >= 10, gap >= 5, gap <= -10, gap <= -5], [1, 2, 5, 4], 3)
    # spike / collapse flags from total headroom (VA Hub thresholds)
    e['flag'] = np.select([e['head'] < 5000, e['head'] < 7000, e['head'] >= 9000], ['SPIKE-HIGH', 'SPIKE-MED', 'COLLAPSE-HIGH'], '')
    e.loc[(e.flag == '') & e['head'].between(7000, 9000), 'flag'] = 'COLLAPSE-MED'
    # hourly bias badges: trailing 7d / 14d mean RT-DA by HE, known through D-2
    for n in (7, 14):
        b = e.pivot_table(index='date', columns='he', values='sp').shift(2).rolling(n, min_periods=max(4, n // 2)).mean().stack().rename(f'bias{n}').reset_index()
        e = e.merge(b, on=['date', 'he'], how='left')
    return e

BASE = {1: [40, 30, 20], 2: [30, 25, 20], 3: [15, 12, 10], 4: [10, 12, 15], 5: [20, 30, 40]}
def ladder(score, da, rt, spike=False, collapse=False):
    """VA Hub _ladder(), exactly (server.py 7107): returns buy [(q,p)x3], sell [(q,p)x3]; prices whole $, MW to 5s."""
    b = BASE[score]; half = [max(1, x // 2) for x in b]
    if score == 1: bp, bq, sp_, sq = [min(da * 1.20, rt * 1.10), rt * .95, rt * .85], b, [None] * 3, [0] * 3
    elif score == 2: bp, bq, sp_, sq = [rt * .90, rt * .85, rt * .80], b, [rt * 1.4, rt * 1.6, rt * (2.2 if spike else 1.8)], half
    elif score == 3: bp, bq, sp_, sq = [rt * .793, rt * .741, rt * .690], b, [rt * 1.207, rt * 1.311, rt * 1.414], b
    elif score == 4: bp, bq, sp_, sq = [rt * .65, rt * .62, rt * (.45 if collapse else .60)], half, [rt * 1.10, rt * 1.15, rt * 1.20], b
    else: bp, bq, sp_, sq = [None] * 3, [0] * 3, [max(da * .98, rt), rt, rt + 5], b
    r5 = lambda q: 0 if not q else max(5, int(round(q / 5) * 5))
    fp = lambda p: None if p is None else max(-100, min(2000, int(round(p))))
    return [(r5(q), fp(p)) for q, p in zip(bq, bp)], [(r5(q), fp(p)) for q, p in zip(sq, sp_)]

def run_ladder(e, score_col, name):
    """Clear each tier on the ACTUAL DA: bid clears if DA <= bid, offer clears if DA >= offer. P&L = MW x (RT-DA) / (DA-RT)."""
    rows = []
    for r in e.dropna(subset=['da', 'rt', 'p_da', 'p_rt']).itertuples():
        s = int(getattr(r, score_col)) if not pd.isna(getattr(r, score_col)) else 0
        if s not in BASE: continue
        buy, sell = ladder(s, r.p_da, r.p_rt)
        mw_b = sum(q for q, p in buy if p is not None and r.da <= p); mw_s = sum(q for q, p in sell if p is not None and r.da >= p)
        rows.append((r.date, r.he, s, mw_b, mw_s, mw_b * (r.rt - r.da) + mw_s * (r.da - r.rt)))
    x = pd.DataFrame(rows, columns=['date', 'he', 'score', 'mw_buy', 'mw_sell', 'pl'])
    dd = x.groupby('date').pl.sum(); mw = x.mw_buy.sum() + x.mw_sell.sum()
    bs = np.random.default_rng(3); k = len(dd); bt = [dd.values[bs.integers(0, k, k)].mean() for _ in range(2000)] if k > 5 else [np.nan]
    return dict(ladder=name, days=k, mwh_cleared=int(mw), buy_mwh=int(x.mw_buy.sum()), sell_mwh=int(x.mw_sell.sum()),
                usd_per_mwh=round(x.pl.sum() / max(mw, 1), 2), usd_per_day=round(dd.mean()), ci90_day=f'{np.percentile(bt, 5):+.0f}..{np.percentile(bt, 95):+.0f}',
                total=round(x.pl.sum()), days_up=round((dd > 0).mean() * 100), worst_day=round(dd.min()))

def walk_v2(e, start='2025-07-01'):
    """Our tested sell rule on 17 months: TIGHT (head < thr) or SURPLUS (gas_hat < thr), thresholds re-learned each day on
    trailing spreads through D-2 (same candidates and >= 40 h rule as signals_v2.py)."""
    import signals_v2 as S
    out = pd.Series(0, index=e.index)
    for D in sorted(e.date.unique()):
        if D < start: continue
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=120)).date().isoformat()
        tr = e[(e.date <= c2) & (e.date > lo) & e.sp.notna()]
        th, tg = S.best_thr(tr, 'head', S.HEAD_THR), S.best_thr(tr.dropna(subset=['gas_hat']), 'gas_hat', S.GAS_THR)
        m = e.date == D
        out[m] = ((e.loc[m, 'head'] < (th or -1)) | (e.loc[m, 'gas_hat'] < (tg or -1))).astype(int)
    return out

def report(zone):
    e = build(zone); e['v2'] = walk_v2(e); e.to_csv(C.DATA / f'dv_frame_{zone}.csv', index=False)
    t = e[e.date >= '2025-07-01'].copy()
    print(f'\n================ {zone}: {t.date.nunique()} test days {t.date.min()}..{t.date.max()} ================')
    ok = t.dropna(subset=['da', 'p_da'])
    err = ok.p_da - ok.da
    print(f'DA forecast: MAE {err.abs().mean():.2f}, bias {err.mean():+.2f}, hours {len(ok)}; P10-P90 coverage {((ok.da >= ok.q10) & (ok.da <= ok.q90)).mean()*100:.0f}%')
    okr = t.dropna(subset=['rt', 'p_rt']); print(f'RT forecast: MAE {(okr.p_rt - okr.rt).abs().mean():.2f}, bias {(okr.p_rt - okr.rt).mean():+.2f}')
    R = []
    lab = {'l_daa': 'Load vs DAA (Tesla/Dynasty vs IESO, 200 MW)', 'l_7d': 'IESO load vs 7-day same HE (300 MW)', 'wind': 'Wind ramp 3h (400 MW)',
           'solar': 'Solar ramp 1h (150 MW)', 'gas_ramp': 'Gas-need ramp (15%)', 'gas_ledge': 'Gas ledge (<2,500 / >7,200)', 'gas_out': 'Gas outages (top/bottom 20%)',
           'nuc_out': 'Nuclear outages (4,500 / 2,500)', 'rt_vs_da': 'RT fc vs DA fc level (10/20/30%)'}
    for c, n in lab.items():
        v = t['s_' + c]; R.append(E.score(t, 'VA ' + n, np.where(v > 0, -1, np.where(v < 0, 1, 0))))
    for lo_ in (2, 3, 4): R.append(E.score(t, f'VA lean total >= +{lo_} buy / <= -{lo_} sell', np.where(t.lean >= lo_, -1, np.where(t.lean <= -lo_, 1, 0))))
    R.append(E.score(t, 'VA auto-score 1/2 buy, 4/5 sell', np.where(t.auto <= 2, -1, np.where(t.auto >= 4, 1, 0))))
    R.append(E.score(t, '  auto-score 5 only (sell)', np.where(t.auto == 5, 1, 0))); R.append(E.score(t, '  auto-score 1 only (buy)', np.where(t.auto == 1, -1, 0)))
    for n in (7, 14):
        b = t[f'bias{n}']; R.append(E.score(t, f'VA hist RT-DA {n}d by HE: follow sign (|mean| >= $3)', np.where(b >= 3, 1, np.where(b <= -3, -1, 0))))
    R.append(E.score(t, 'OURS v2 SELL (tight or surplus, walk-forward)', t.v2))
    R.append(E.score(t, 'sell every hour', np.ones(len(t)))); R.append(E.score(t, 'buy every hour', -np.ones(len(t))))
    R = pd.DataFrame(R); print('\n-- price-taker tests, $/MWh per cleared MWh (+ = rule made money) --'); print(R[['rule', 'hours', 'sells', 'buys', 'usd_mwh', 'ci90', 'win', 'total', 'days_up']].to_string(index=False))
    print('\n-- lean total vs outcome --'); x = t.dropna(subset=['sp'])
    print(x.groupby(x.lean.clip(-5, 5)).agg(hours=('sp', 'size'), mean_DA_RT=('sp', 'mean'), RT_gt_DA=('sp', lambda s: (s < 0).mean() * 100)).round(1).T.to_string())
    print('\n-- spike / collapse flags (total headroom) --')
    print(x.groupby('flag').agg(hours=('sp', 'size'), RT_gt100=('rt', lambda s: (s > 100).mean() * 100), RT_gt150=('rt', lambda s: (s > 150).mean() * 100),
                                RT_lt25=('rt', lambda s: (s < 25).mean() * 100), mean_DA_RT=('sp', 'mean')).round(1).to_string())
    pk = x[x.he.between(15, 22)]; print('peak HE15-22 only:'); print(pk.groupby('flag').agg(hours=('sp', 'size'), RT_gt100=('rt', lambda s: (s > 100).mean() * 100)).round(1).T.to_string())
    L = [run_ladder(t.assign(sc=s), 'sc', f'every hour at score {s}') for s in (1, 2, 3, 4, 5)]
    L.append(run_ladder(t, 'auto', 'VA auto-score per hour'))
    t['lean_sc'] = np.select([t.lean >= 4, t.lean >= 2, t.lean <= -4, t.lean <= -2], [1, 2, 5, 4], 3); L.append(run_ladder(t, 'lean_sc', 'lean-driven score (+-2 / +-4)'))
    t['ours5'] = np.where(t.v2 == 1, 5, 3); L.append(run_ladder(t, 'ours5', 'OURS: v2 SELL -> 5, else 3'))
    t['ours4'] = np.where(t.v2 == 1, 5, 0); L.append(run_ladder(t, 'ours4', 'OURS: v2 SELL -> 5, else nothing'))
    L = pd.DataFrame(L); L.to_csv(C.DATA / f'dv_ladders_{zone}.csv', index=False); R.to_csv(C.DATA / f'dv_rules_{zone}.csv', index=False)
    print('\n-- VA Hub 3-tier ladders, cleared on the actual DA (base MW, no 1.5x boost) --'); print(L.to_string(index=False))
    return e

def walk_buy_band(e, start='2025-09-01', look=120, width=2000):
    """Long-side rule found in this re-test: BUY when headroom sits in the 'middle' band where RT tends to beat DA.
    Each day the band [a, a+width) is re-picked on the trailing `look` days through D-2 (candidates a = 5,000..11,000 step 500):
    most negative mean DA-RT with >= 150 h and mean <= -$3; if none qualifies, no buys."""
    out = pd.Series(0, index=e.index); bands = {}
    for D in sorted(e.date.unique()):
        if D < start: continue
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=look)).date().isoformat()
        tr = e[(e.date <= c2) & (e.date > lo)].dropna(subset=['sp', 'head']); best = None
        for a in range(5000, 11001, 500):
            m = tr[(tr['head'] >= a) & (tr['head'] < a + width)]
            if len(m) >= 150 and m.sp.mean() <= -3 and (best is None or m.sp.mean() < best[1]): best = (a, m.sp.mean())
        if best:
            m = (e.date == D) & (e['head'] >= best[0]) & (e['head'] < best[0] + width); out[m] = -1; bands[D] = best[0]
    return out, bands

def finalize(zone):
    """Adds the buy-band rule to the frame and writes the tables the page shows: dv_rules_<zone>.csv (price-taker),
    dv_ladders2_<zone>.csv (VA Hub ladder formulas driven by VA auto-score vs by our score). Test window Sep 2025 ->."""
    e = pd.read_csv(C.DATA / f'dv_frame_{zone}.csv')
    if 'buyband' not in e: s, _ = walk_buy_band(e); e['buyband'] = s.values; e.to_csv(C.DATA / f'dv_frame_{zone}.csv', index=False)
    t = e[e.date >= '2025-09-01'].copy()
    R = pd.read_csv(C.DATA / f'dv_rules_{zone}.csv')
    R = R[~R.rule.str.contains('buy band|combined', regex=True)]
    add = [E.score(t, 'OURS buy band (middle headroom, walk-forward)', np.where(t.v2 == 1, 0, t.buyband)),
           E.score(t, 'OURS combined: v2 SELL + buy band', np.where(t.v2 == 1, 1, t.buyband))]
    R = pd.concat([R, pd.DataFrame(add)], ignore_index=True); R.to_csv(C.DATA / f'dv_rules_{zone}.csv', index=False)
    t['ours'] = np.where(t.v2 == 1, 5, np.where(t.buyband == -1, 1, 3))
    L = []
    for c, n in (('auto', 'VA Hub auto-score'), ('ours', 'Ours: v2 SELL=5, buy band=1, else 3')):
        r = run_ladder(t, c, n); r['h2_usd_mwh'] = run_ladder(t[t.date >= '2026-02-01'], c, n)['usd_per_mwh']; L.append(r)
    pd.DataFrame(L).to_csv(C.DATA / f'dv_ladders2_{zone}.csv', index=False); print(zone); print(pd.DataFrame(L).to_string(index=False))


if __name__ == '__main__':
    for z in ([a for a in sys.argv[1:] if not a.startswith('--')] or ['TORONTO', 'SOUTHWEST']):
        if '--final' not in sys.argv: report(z)
        finalize(z)
