"""run_model.py -- build the forecast bundle for one bid morning.

    python model/run_model.py                 # origin = latest morning the data supports
    python model/run_model.py --origin 2026-09-26

Origin O is the bid morning (D-1). Produces site/data/bundle.json:
  * next day (O+1), Toronto and Southwest, hourly: DA P10..P90, RT P10..P90, headroom,
    Tesla-IESO gap, NY-OH schedule, P(Lennox), the trade signal and suggested offer/bid prices
  * bid-time supply stack (demand, nuclear, wind, solar, modelled hydro and net exports, gas need)
  * the backtest numbers (from data/bt_*.csv) shown on the page
Every input is filtered to what existed at the origin's 08:00 MT deadline."""
import sys, json, argparse, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, hourly as Hm, blocks as B, signals_v2 as S, edge_study as E, supply_fc as SF, da_virtual as V

HUBS = {'EAST': 85, 'OTTAWA': 100}      # IESO virtual trading zone limits, MW per side per hour (Introduction to Virtual Trading, Table 2)
Q = [0.1, 0.25, 0.5, 0.75, 0.9]
LENNOX_P = [(6000, 0.82), (7000, 0.62), (8000, 0.35), (9000, 0.13), (1e9, 0.02)]   # share of hours Lennox ran in RT by pre-DA headroom, Jun 28-Sep 25 2026 (2,160 h)
MISS_GRID = {  # median RT-DA by pre-DA headroom band x load-miss band (notes, 1,056 h)
    'bands_head': [7000, 8500, 10000, 11500], 'bands_miss': [-600, -200, 200, 600],
    'median': [[-46, -25, -10, -5, 6], [-19, -5, 3, 7, 20], [-8, -5, 4, 9, 29], [-7, -4, 3, 5, 6], [-13, -5, -1, 1, 3]]}


def p_lennox(h):
    for thr, p in LENNOX_P:
        if h < thr: return p
    return 0.01


def block_means(p, day):
    x = p[p.date == day]
    if len(x) < 24: return None
    on = x.he.between(7, 22)
    return {'on': x.da[on].mean(), 'off': x.da[~on].mean(), 'flat': x.da.mean()}


def block_forecast(O, leads=range(1, 15)):
    """50/50 anchored-delta + forward, per lead and block, fitted on history known at O."""
    X = pd.read_csv(C.DATA / 'blocks_features.csv')
    f = B.settles(); xde, xdg, xdy = (B.fwd_asof(f, c, 'Ontario Hub') for c in ('XDE', 'XDG', 'XDY'))
    cvx = B.fwd_asof(f, 'CVX', 'Dawn Ontario'); pda = B.fwd_asof(f, 'PDA', 'WESTERN HUB')
    H = B.headroom_by_lead(); H['on'] = H.he.between(7, 22)
    hb = H.groupby(['date', 'lead', 'on'])['head'].mean().unstack('on'); hb.columns = ['off', 'on']; hb['flat'] = hb.mean(axis=1)
    oz = C.prices('ONTARIO'); anch = block_means(oz, O)
    Ot = pd.Timestamp(O); rows = []
    R = pd.read_csv(C.DATA / 'bt_blocks.csv')                       # for residual quantiles by lead
    for L in leads:
        D = (Ot + pd.Timedelta(days=L)).date().isoformat(); Dt = pd.Timestamp(D)
        hist = X[(X.lead == L) & (X.date <= (Ot - pd.Timedelta(days=0)).date().isoformat())]
        hist = hist[hist.date >= (Ot - pd.Timedelta(days=87)).date().isoformat()]
        gD, gO = B.asof(cvx, Dt, Ot), B.asof(cvx, Ot, Ot); pD, pO = B.asof(pda, Dt, Ot), B.asof(pda, Ot, Ot)
        r = dict(date=D, lead=L, dow=int(Dt.dayofweek))
        for k, tbl in (('on', xde), ('off', xdg), ('flat', xdy)):
            y = np.log(hist[f'y_{k}'].clip(lower=3)); a = np.log(hist[f'anch_{k}'].clip(lower=3))
            F = pd.DataFrame({'dh': (hist[f'hD_{k}'] - hist[f'hO_{k}']) / 1000, 'dg': np.log(hist.gas_D / hist.gas_O),
                              'dp': np.log(hist.pjm_D / hist.pjm_O)}).fillna(0)
            ok = y.notna() & a.notna()
            beta = np.linalg.solve(F[ok].T.values @ F[ok].values + np.eye(3), F[ok].T.values @ (y - a)[ok].values)
            try: hD = hb.loc[(D, L), k]
            except KeyError: hD = np.nan
            try: hO = hb.loc[(O, 1), k]
            except KeyError: hO = np.nan
            f0 = np.array([(hD - hO) / 1000 if pd.notna(hD) and pd.notna(hO) else 0,
                           np.log(gD / gO) if gD and gO else 0, np.log(pD / pO) if pD and pO else 0])
            f0 = np.nan_to_num(f0)
            base = anch[k] if anch else np.nan
            p_delta = np.exp(np.log(base) + f0 @ beta)
            fw = B.asof(tbl, Dt, Ot)
            p50 = 0.5 * p_delta + 0.5 * fw if pd.notna(fw) else p_delta
            e = R[(R.lead == L) & (R.block == k) & (R.date < O)].tail(120)
            lr = np.log(e.y / e.b5050).dropna()
            qs = np.quantile(lr - np.median(lr), [0.1, 0.9]) if len(lr) > 30 else [-0.25, 0.25]
            r.update({f'{k}_p50': p50, f'{k}_p10': p50 * np.exp(qs[0]), f'{k}_p90': p50 * np.exp(qs[1]),
                      f'{k}_fwd': fw, f'{k}_delta': p_delta, f'{k}_head': hD})
        rows.append(r)
    return pd.DataFrame(rows)


def hub_next_day(zone, O, bf):
    D = (pd.Timestamp(O) + pd.Timedelta(days=1)).date().isoformat()
    d = Hm.frame(zone)
    known = d[(d.date <= O) & d.da.notna()]
    days = sorted(known.date.unique())[-21:]
    tr = d[d.date.isin(days) & d.da.notna()]
    te = d[d.date == D].copy()
    te['da'] = np.nan; te['rt'] = np.nan                                      # never let the answer in
    e = Hm.fit_predict(tr, te)
    b1 = bf[bf.lead == 1].iloc[0]; e['on'] = e.he.between(7, 22)
    wk = pd.Timestamp(D).dayofweek >= 5
    basis = (known.groupby('date').da.mean() / C.prices('ONTARIO').groupby('date').da.mean()).dropna().tail(14).mean()
    tgt = np.where(e.on, b1.flat_p50 if wk else b1.on_p50, b1.off_p50) * basis
    e['p_s'] = e.p_h * tgt / e.groupby('on').p_h.transform('mean')
    e['p_da'] = 0.5 * e.p_h + 0.5 * e.p_s
    # residual quantiles from the walk-forward backtest (trailing 28 days), DA and RT
    bt = pd.read_csv(C.DATA / f'bt_hourly_{zone}.csv'); bt['p_da'] = 0.5 * bt.p_h + 0.5 * bt.p_s.fillna(bt.p_h)
    bt = bt[(bt.date <= O) & bt.da.notna()]; bt = bt[bt.date >= sorted(bt.date.unique())[-28]]
    bt['lr_da'] = np.log(bt.da.clip(lower=5) / bt.p_da); bt['lr_rt'] = np.log(bt.rt.clip(lower=5) / bt.p_da)
    bt['tb'] = (bt['head'] < 8500).astype(int)
    lf = C.load_forecasts_at_bid(); lf = lf[lf.date == D][['date', 'he', 'lf_tesla', 'lf_dynasty']]
    e = e.drop(columns=[c for c in ('lf_tesla', 'lf_dynasty', 'gapT') if c in e]).merge(lf, on=['date', 'he'], how='left')
    e['gapT'] = (e.lf_tesla - e.dem_fc) / 1000
    e['tb'] = (e['head'] < 8500).astype(int)
    # v2 signal (the walk-forward-tested rule) -- same code path as the backtest
    hist = E.base(zone); hist.loc[hist.date == D, ['da', 'rt', 'sp']] = np.nan
    if D not in set(hist.date):
        a2 = C.adq2('preDA')[['date', 'he', 'head', 'dem_fc', 'wind_fc', 'solar_fc', 'gas_av', 'hyd_av', 'nuc_av']]
        hist = pd.concat([hist, a2[a2.date == D]], ignore_index=True)
    m = e.set_index('he')
    sel = hist.date == D
    hist.loc[sel, 'p_da'] = hist.loc[sel, 'he'].map(m.p_da).values
    hist.loc[sel, 'gapT'] = hist.loc[sel, 'he'].map(m.gapT * 1000).values
    hist.loc[sel, 'nyA_da'] = hist.loc[sel, 'he'].map(m.nyA_da).values
    hist.loc[sel, 'wkend'] = int(pd.Timestamp(D).dayofweek >= 5)
    v2 = S.walk(hist[hist.date <= D], start=D).set_index('he')
    stk = SF.live_stack(D).set_index('he')
    J = lambda v: None if v is None or pd.isna(v) else int(round(float(v)))
    # DA Virtual tab inputs (da_virtual.py)
    band = V.band_for(zone, D); bias = V.bias(zone, D); trips = V.trips_d1(D)
    ln = V.lean([dict(he=int(r.he), dem_fc=r.dem_fc, lf_tesla=r.lf_tesla, lf_dynasty=r.get('lf_dynasty', np.nan),
                      wind_fc=stk.loc[int(r.he), 'wind_ieso'] if int(r.he) in stk.index else np.nan,
                      gas_hat=v2.loc[int(r.he), 'gas_hat'] if int(r.he) in v2.index else np.nan) for _, r in e.iterrows()])
    import cahr as K                                                   # carbon-adjusted heat rate (cahr_test.py / cahr_ladder.py)
    g_usd, g_fx, g_cad = K.gas_table([D])[D]; g_cp = K.cprice(D)
    hrs = []
    for _, r in e.sort_values('he').iterrows():
        pool = bt[bt.blk == r.blk]; poolr = pool[pool.tb == r.tb] if (pool.tb == r.tb).sum() > 40 else pool
        qd = r.p_da * np.exp(np.quantile(pool.lr_da, Q)); qr = r.p_da * np.exp(np.quantile(poolr.lr_rt.dropna(), Q))
        w = v2.loc[int(r.he)]; sig = w.signal
        hb = np.searchsorted(MISS_GRID['bands_head'], r['head'])
        hrs.append(dict(he=int(r.he), head=round(r['head']), dem_fc=round(r.dem_fc), tesla=None if pd.isna(r.lf_tesla) else round(r.lf_tesla),
                        gapT=None if pd.isna(r.gapT) else round(r.gapT * 1000), ny_oh=None if pd.isna(r.ny_dni_oh) else round(r.ny_dni_oh),
                        nyA=None if pd.isna(r.nyA_da) else round(r.nyA_da, 2), p_lennox=p_lennox(r['head']),
                        da=[round(x, 2) for x in qd], rt=[round(x, 2) for x in qr], signal=sig,
                        offer_p25=round(qd[1], 2), offer_p50=round(qd[2], 2), bid_p75=round(qd[3], 2),
                        miss_row=MISS_GRID['median'][hb], why=w.why, lean=None if pd.isna(w.lean) else round(float(w.lean), 1),
                        gas_hat=None if pd.isna(w.gas_hat) else round(float(w.gas_hat)),
                        stack={k: J(stk.loc[int(r.he), k]) for k in stk.columns}))
        he_ = int(r.he); p_rt = float(qr[2]); sc, why_sc = V.score_hour(sig, float(r['head']), band)
        b7, b14 = bias[7], bias[14]
        hrs[-1].update(b_h=None if pd.isna(r.get('b_h', np.nan)) else round(float(r.b_h), 4), b_dni=None if pd.isna(r.get('b_dni', np.nan)) else round(float(r.b_dni), 4),
                       wind_fc=None if pd.isna(stk.loc[he_, 'wind_ieso']) else round(float(stk.loc[he_, 'wind_ieso'])),
                       solar_fc=None if pd.isna(stk.loc[he_, 'solar']) else round(float(stk.loc[he_, 'solar'])))
        hrs[-1].update(p_da=round(float(r.p_da), 2), p_rt=round(p_rt, 2), score=sc, score_why=why_sc, va_auto=V.va_auto(float(r.p_da), p_rt),
                       band=V.band_label(float(r['head'])), in_band=bool(band and band['lo'] <= r['head'] < band['hi']),
                       lean2=ln.get(he_), dyn=None if pd.isna(r.get('lf_dynasty', np.nan)) else round(r.lf_dynasty),
                       bias7=None if he_ not in b7.index else dict(m=round(b7.loc[he_, 'm'], 1), rtgt=round(b7.loc[he_, 'rtgt'])),
                       bias14=None if he_ not in b14.index else dict(m=round(b14.loc[he_, 'm'], 1), rtgt=round(b14.loc[he_, 'rtgt'])),
                       ladders=V.ladders(round(float(r.p_da), 2), round(p_rt, 2), [float(x) for x in qd]),
                       scarcity=bool(r['head'] < 2000), trips24=trips.get(he_),
                       boost=bool(sc == 5 and w.why == 'tight' and (trips.get(he_) or 0) >= V.TRIPS_BOOST),
                       cahr=None if pd.isna(g_cad) else round(float(K.hr(float(r.p_da), g_cad, g_cp)), 2),
                       grade=None if not (sc == 5 and w.why == 'tight') or pd.isna(g_cad) else ('A' if K.hr(float(r.p_da), g_cad, g_cp) >= K.A_GRADE else 'B'))
    # Spike Watch (spike_watch.py / spike_watch_2026.py, Oct 8 2026): evening HE16-21 hours we are NOT selling, score >= 2 of
    # headroom 7,000-8,500 | CAHR >= 10 | Tesla or Dynasty >= IESO demand | IESO wind down >= 150 MW over 3 h -> small long, bid DA fc + $30.
    # Tested Sep 2025 -> Oct 2026: +$14 (East) / +$17.5 (Ottawa) per MWh, 2026 at 20 MW +$153k / +$205k. Context flag: Tesla above IESO on a
    # tight evening sell (tight_guard.py: those sells earned ~$0 and carried 30% of the bad days, incl. Oct 1 and Oct 7).
    wmap = {h['he']: h['stack'].get('wind_ieso') for h in hrs}
    for h in hrs:
        he_ = h['he']; f = []
        if 7000 <= h['head'] <= 8500: f.append('headroom 7-8.5k')
        if h.get('cahr') is not None and h['cahr'] >= 10: f.append('CAHR>=10')
        if (h.get('tesla') is not None and h['tesla'] >= h['dem_fc']) or (h.get('dyn') is not None and h['dyn'] >= h['dem_fc']): f.append('Tesla/Dynasty>=IESO')
        w0, w3 = wmap.get(he_), wmap.get(he_ - 3)
        if w0 is not None and w3 is not None and w0 - w3 <= -150: f.append('wind falling')
        sell = h['score'] == 5
        h['sw'] = dict(score=len(f), flags=f, flag=bool(16 <= he_ <= 21 and not sell and len(f) >= 2), mw=20, bid=int(round(h['p_da'] + 30)),
                       tight_tesla=bool(16 <= he_ <= 21 and sell and h.get('tesla') is not None and h['tesla'] > h['dem_fc']))
    # Oct 9 2026: a tight-evening guard (Tesla > IESO -> no edge; + wind fc >= 1,500 -> flip to buy) was wired and then REMOVED after
    # guard_validate.py: the no-edge part cost money (-$58k E / -$70k O); the flip beat random placebos (98.6%) but lost money without its
    # best 3 days and with thresholds chosen walk-forward (-$219k E / -$84k O). Not backed -> live signals unchanged.
    for h in hrs: h['guard'] = None
    th = v2.iloc[0]
    return dict(date=D, hub=zone, cap_mw=HUBS[zone], hours=hrs, gas=dict(dawn_usd=None if pd.isna(g_usd) else round(float(g_usd), 3), fx=None if pd.isna(g_fx) else round(g_fx, 4),
                gas_cad=None if pd.isna(g_cad) else round(float(g_cad), 3), carbon=g_cp, bench=K.BENCH, ef=K.EF, a_grade=K.A_GRADE), thr=dict(head=th.thr_head, gas=th.thr_gas, gas_ext=th.thr_gas_ext),
                buy_band=band, band_table=V.band_table(zone), dv_results=dv_results(zone))


def dv_results(zone):
    """17-month re-test tables for the DA Virtual tab (written by da_virtual_bt.py / the ladder comparison)."""
    out = {}
    for k, f in (('rules', f'dv_rules_{zone}.csv'), ('ladders', f'dv_ladders2_{zone}.csv')):
        p = C.DATA / f
        if p.exists(): out[k] = pd.read_csv(p).fillna('').to_dict('records')
    return out


def eo_bundle(target):
    """East-Ottawa pair + Quebec panel. Everything per HE is from days <= D-2 (target minus 2) except the bid-time PQ.AT DA limits."""
    import quebec as Q
    c2 = (pd.Timestamp(target) - pd.Timedelta(days=2)).date().isoformat()
    w = Q.frame(history=True).dropna(subset=['da_east', 'rt_east', 'da_ottawa', 'rt_ottawa']); w = w[w.date <= c2].copy()
    w['pair'] = w.eo_da - w.eo_rt
    t28 = w[w.date > (pd.Timestamp(c2) - pd.Timedelta(days=28)).date().isoformat()]
    per = []
    for he, g in w.groupby('he'):
        g28 = t28[t28.he == he]
        per.append(dict(he=int(he), mean=round(g.pair.mean(), 2), wins=round(g.pair.clip(-50, 50).mean(), 2), win=round((g.pair > 0).mean() * 100), n=int(len(g)),
                        big=int((g.pair > 50).sum()), bad=int((g.pair < -50).sum()), m28=round(g28.pair.mean(), 2) if len(g28) else None,
                        da_eo=round(g.eo_da.mean(), 2), rt_eo=round(g.eo_rt.mean(), 2)))
    lim = {}
    f = C.DATA / 'ieso_preda_intertie_limits.csv'
    if f.exists():
        x = pd.read_csv(f); x = x[(x.date == target) & x.zone.isin(['PQATN', 'PQATX'])]
        for r in x.itertuples(): lim.setdefault(int(r.he), {})['exp' if r.zone.endswith('N') else 'imp'] = abs(float(r.mw))
    F = pd.read_csv(C.DATA / 'qc_flows.csv'); last = sorted(F.date.unique())[-7:]
    fl = F[F.date.isin(last)].groupby('he')[['pq_at_exp', 'pq_at_imp', 'pq_exp', 'pq_imp']].mean().round(0)
    qc = [dict(he=int(he), lim_exp=lim.get(int(he), {}).get('exp'), lim_imp=lim.get(int(he), {}).get('imp'),
               at_exp7=float(fl.loc[he, 'pq_at_exp']) if he in fl.index else None, pq_exp7=float(fl.loc[he, 'pq_exp']) if he in fl.index else None,
               pq_imp7=float(fl.loc[he, 'pq_imp']) if he in fl.index else None) for he in range(1, 25)]
    j = C.DATA / 'zone_bt17.json'; R = json.loads(j.read_text()) if j.exists() else {}
    j2 = C.DATA / 'quebec2.json'; R['q2'] = json.loads(j2.read_text()) if j2.exists() else None
    hqt = None                                                   # Quebec demand: no real history for 2025-26 (modelled demand dropped)
    j3 = C.DATA / 'qc_adq2x.json'; R['adq2x'] = json.loads(j3.read_text()) if j3.exists() else None
    if False:
        h = pd.read_csv(hq); h7 = h[(h.date < target) & (h.date >= (pd.Timestamp(target) - pd.Timedelta(days=9)).date().isoformat()) & (h.date <= c2)]
        ht = h[h.date == target]
        if len(ht) and ht.hq_fc.notna().any(): hqt = dict(fc=round(ht.hq_fc.mean()), t_fc=round(ht.t_fc.mean(), 1), last7=round(h7.hq.mean()) if len(h7) else None, peak_fc=round(ht.hq_fc.max()))
    return dict(asof=c2, per_he=per, qc=qc, flows_days=[last[0], last[-1]], results=R, hq_tomorrow=hqt)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--origin'); a = ap.parse_args()
    O = a.origin or pd.read_csv(C.CACHE / 'ieso_adq2_preDA.csv', usecols=['ieso_createtime']).ieso_createtime.max()[:10]
    bf = block_forecast(O)
    out = dict(origin=O, target=(pd.Timestamp(O) + pd.Timedelta(days=1)).date().isoformat(), hubs={})
    for z in HUBS: out['hubs'][z] = hub_next_day(z, O, bf)
    # actuals if already published (for the review strip)
    p = C.prices(); act = {}
    for z in HUBS:
        x = p[(p.zone == z) & (p.date == out['target'])]
        act[z] = {int(r.he): dict(da=None if pd.isna(r.da) else r.da, rt=None if pd.isna(r.rt) else r.rt) for _, r in x.iterrows()}
    out['actual'] = act
    out['miss_grid'] = MISS_GRID
    try: out['eo'] = eo_bundle(out['target'])
    except Exception as ex: print('east-ottawa panel skipped:', ex)
    try:
        import ny_panel as NYP
        pda = {h['he']: h['p_da'] for h in out['hubs']['EAST']['hours']}
        out['ny'] = NYP.build(out['target'], pda); out['tesla'] = NYP.tesla(out['target'])
    except Exception as ex: print('ny / tesla panel skipped:', ex)
    try:
        import outages_tab as OTB
        out['outages'] = OTB.build(out['target'], V.trips_d1(out['target']))
    except Exception as ex: print('outages tab skipped:', ex)
    try:
        import fund_panel as FP
        out['fund'] = FP.build(out['target'], out)
    except Exception as ex: print('fundamentals panel skipped:', ex)
    try:
        import checks_panel as CK
        out['checks'] = CK.build(out['target'], out)
    except Exception as ex: print('checks panel skipped:', ex)
    site = C.ROOT / 'site' / 'data'; site.mkdir(parents=True, exist_ok=True)
    (site / 'bundle.json').write_text(json.dumps(out, default=float))
    print('bundle ->', site / 'bundle.json', 'origin', O, 'target', out['target'])

if __name__ == '__main__':
    main()
