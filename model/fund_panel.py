"""fund_panel.py -- Fundamentals tab (Oct 8 2026): every bid-time forecast we have, hour by hour, with the gas ramp coloured
bullish / bearish against its own history. Context only -- nothing here changes the model's signals or ladders.

Ramp colour: the hour-over-hour (and 3-hour) change in gas need, ranked against the same HE over the last 60 days (through D-2).
>= 80th pct = bullish (gas has to ramp hard), >= 95th = strongly bullish; <= 20th = bearish (gas backing down), <= 5th = strongly.
Why: Oct 8 HE19 ($95 DA -> $272 RT, all zones, no trips, no congestion) came at the end of a 98th-percentile evening ramp."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C

def _nwp(D):
    """Lowest / highest of the 5 weather-model wind forecasts at the bid. Oct 9 2026: a model hour is dropped as STALE when its
    value is identical to the same hour on each of the previous 2 days (NAM HE10-24 froze in the Warehouse from Sep 26 2026 at
    932, 716, ... 247, 243, 308 -- it was setting the 'models low')."""
    try:
        w = pd.read_csv(C.CACHE / 'ieso_wind_fc.csv'); w = w[w.DataSourceName.isin(['Frontier', 'NAM', 'NAM_Nest', 'GFS', 'GEM(CMC)'])]
        eff = pd.to_datetime(w.EffectiveDateTime.str[:19]) + pd.Timedelta(hours=1); w['date'], w['he'] = C._ts_to_key(eff)
        w = w.dropna(subset=['he']); w['he'] = w.he.astype(int); w['ts'] = pd.to_datetime(w.Timestamp.str[:19])
        dl = pd.Timestamp(D) - pd.Timedelta(days=1) + pd.Timedelta(hours=8); w = w[pd.to_datetime(w.DateCreated.str[:19]) <= dl].sort_values('ts')
        ds = [(pd.Timestamp(D) - pd.Timedelta(days=k)).date().isoformat() for k in (0, 1, 2)]
        v = w[w.date.isin(ds)].groupby(['date', 'he', 'DataSourceName']).Value.last().unstack(0)
        stale = (v[ds[0]] == v[ds[1]]) & (v[ds[0]] == v[ds[2]])
        last = v[ds[0]][~stale.fillna(False)].unstack()
        return last.min(1).to_dict(), last.max(1).to_dict()
    except Exception: return {}, {}

def _hist(D):
    d = pd.read_csv(C.DATA / 'dv_frame_EAST.csv', usecols=['date', 'he', 'gas_hat', 'dem_fc', 'nuc_av', 'wind_fc', 'solar_fc'])
    lo = (pd.Timestamp(D) - pd.Timedelta(days=62)).date().isoformat(); hi = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
    d = d[(d.date > lo) & (d.date <= hi)]
    g = d.pivot_table(index='date', columns='he', values='gas_hat'); r1 = g.diff(axis=1); r3 = g.diff(3, axis=1)
    d['resid'] = d.dem_fc - d.nuc_av - d.wind_fc.fillna(0) - d.solar_fc.fillna(0)
    rs = d.pivot_table(index='date', columns='he', values='resid'); pm = (rs[19] - rs[15]).dropna(); am = (rs[8] - rs[5]).dropna()
    return r1, r3, pm, am

def _pct(v, s):
    s = pd.Series(s).dropna()
    return None if v is None or pd.isna(v) or len(s) < 15 else int(round((s < v).mean() * 100))

def build(D, bundle):
    H = bundle['hubs']['EAST']['hours']; O = {h['he']: h for h in bundle['hubs'].get('OTTAWA', {}).get('hours', [])}
    r1, r3, pm, am = _hist(D); nmin, nmax = _nwp(D)
    J = lambda v, k=0: None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), k) if k else int(round(float(v)))
    gh = {h['he']: h.get('gas_hat') for h in H}; rows = []
    for h in H:
        he = h['he']; s = h['stack']; g0 = gh.get(he); g1 = gh.get(he - 1); g3 = gh.get(he - 3)
        ramp1 = None if g0 is None or g1 is None else g0 - g1; ramp3 = None if g0 is None or g3 is None else g0 - g3
        resid = None if s.get('dem_ieso') is None else s['dem_ieso'] - (s.get('nuc') or 0) - (s.get('wind_ieso') or 0) - (s.get('solar') or 0)
        rows.append(dict(he=he, dem=J(s.get('dem_ieso')), tesla=J(h.get('tesla')), dyn=J(h.get('dyn')), meteo_load=J(s.get('dem_meteo')),
            wind=J(s.get('wind_ieso')), wind_meteo=J(s.get('wind_meteo')), wind_nwp_min=J(nmin.get(he)), wind_nwp_max=J(nmax.get(he)),
            solar=J(s.get('solar')), nuc=J(s.get('nuc')), hyd_av=J(s.get('hyd_av')), hydro_exp=J(s.get('hydro')), net_exp=J(s.get('exp')),
            resid=J(resid), gas_av=J(s.get('gas_av')), gas_need=J(g0), gas_spare=None if g0 is None or s.get('gas_av') is None else J(s['gas_av'] - g0),
            ramp1=J(ramp1), ramp1_pct=_pct(ramp1, r1[he] if he in r1 else []), ramp3=J(ramp3), ramp3_pct=_pct(ramp3, r3[he] if he in r3 else []),
            head=J(h.get('head')), cahr=h.get('cahr'), da_e=h.get('p_da'), rt_e=h.get('p_rt'), da_o=(O.get(he) or {}).get('p_da'), signal=h.get('signal'), score=h.get('score'), guard=h.get('guard'), gauge=h.get('gauge'), sw=(h.get('sw') or {}).get('flag'),
            rtda7=None if not h.get('bias7') else -h['bias7']['m'], win7=None if not h.get('bias7') else int(round(h['bias7']['rtgt'] * 7 / 100))))
    try:                                                    # fund_read.py: all-fundamentals model, RT - DA expected (+ = longs)
        import fund_read as FR
        P = FR.predict(D, bundle); T = pd.read_csv(C.DATA / 'fund_read_track.csv')
        for r in rows:
            r['read'] = P.get('EAST', {}).get(r['he']); r['read_o'] = P.get('OTTAWA', {}).get(r['he'])
            if r['read'] is not None:
                k = 10 if abs(r['read']) >= 10 else 5 if abs(r['read']) >= 5 else 0
                t = T[(T.zone == 'EAST') & (T.seg == FR.seg(r['he'])) & (T.min_read == k)]
                if len(t): t = t.iloc[0]; r['read_track'] = dict(seg=t.seg, k=int(k), right=int(t.right_side_pct), usd=float(t.usd_mwh), last90=float(t.last90), hours=int(t.hours))
    except Exception as ex: print('fundamentals read skipped:', ex)
    # Oct 9 2026 (cheap_risk_test.py / what_matters.py): bid-time signs that something MIGHT go wrong and DA has NOT priced it.
    # Any of: Tesla >= IESO + 150 | IESO wind falling >= 200 MW over 3 h | gas need rising >= 500 MW over 3 h. Non-sell hours with a sign:
    # long +$8.4/MWh East (1,937 h, both halves +, last 120 days +, w/o best 3 days +, placebo 100%); on top of the current longs +$4.5k/MW.
    # Display only -- scoring unchanged. DA fc vs usual = our DA forecast minus its 30-day median for the same HE (context).
    try:
        dv = pd.read_csv(C.DATA / 'dv_frame_EAST.csv', usecols=['date', 'he', 'p_da']); dv = dv[dv.date < D]
        last30 = sorted(dv.date.unique())[-30:]; usual = dv[dv.date.isin(last30)].groupby('he').p_da.median().to_dict()
    except Exception: usual = {}
    wmap = {r['he']: r['wind'] for r in rows}
    for r in rows:
        f = []; tg = None if r['tesla'] is None or r['dem'] is None else r['tesla'] - r['dem']
        w3 = None if wmap.get(r['he']) is None or wmap.get(r['he'] - 3) is None else wmap[r['he']] - wmap[r['he'] - 3]
        if tg is not None and tg >= 150: f.append(f'Load +{tg:,}')
        if w3 is not None and w3 <= -200: f.append(f'Wind {w3:,}')
        if r['ramp3'] is not None and r['ramp3'] >= 500: f.append(f'Gas ramp +{r["ramp3"]:,}')
        r['risk'] = f; r['wind3'] = w3
        u = usual.get(r['he']); r['da_usual'] = None if u is None else round(float(u), 2)
        r['da_vs'] = None if u is None or r['da_e'] is None else round(float(r['da_e'] - u), 1)
    # Oct 2026: yesterday's DAY-AHEAD CLEARED net exports, same hour (da_cleared_ties.py; published D-2 ~12:50 EST, known at the bid). Display only.
    try:
        tz = pd.read_csv(C.DATA / 'da_cleared_ties.csv'); y = (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat()
        tz = tz[tz.date == y].set_index('he').net_dac.to_dict()
    except Exception: tz = {}
    for r in rows: r['exp_cleared_y'] = None if tz.get(r['he']) is None or pd.isna(tz.get(r['he'])) else int(round(float(tz[r['he']])))
    res = {r['he']: r['resid'] for r in rows}
    pmv = None if res.get(19) is None or res.get(15) is None else res[19] - res[15]; amv = None if res.get(8) is None or res.get(5) is None else res[8] - res[5]
    F = dict(date=D, rows=rows, pm_ramp=J(pmv), pm_ramp_pct=_pct(pmv, pm), am_ramp=J(amv), am_ramp_pct=_pct(amv, am))
    try:
        import fund_practice as FPR; F['prac'] = FPR.build(D, F)          # same table + colours as the Ontario Read Practice page
    except Exception as ex: print('practice-format table skipped:', ex)
    return F
