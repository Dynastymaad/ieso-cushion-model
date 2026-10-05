"""'Your checks' panel for the Next day tab: the handful of numbers for the pre-model routine
(notes/Fundamentals_Wind_Solar_Temp_Load.md). Context only; nothing here feeds the signal.

Temperature: Open-Meteo forecast for Toronto (same request and cache as checklist_xlsx), curve from
CYYZ actuals vs IESO actual daily peak, May 2025 ->. Load: IESO Adequacy (pre-DA), Tesla, last week's actual.
"""
import json, urllib.request
import numpy as np, pandas as pd
import common as C

OM_URL = ('https://api.open-meteo.com/v1/forecast?latitude=43.65,45.42,44.00,42.40&longitude=-79.38,-75.70,-81.60,-82.20'
          '&hourly=temperature_2m,cloud_cover,shortwave_radiation,pressure_msl,wind_speed_100m&timezone=America%2FToronto&past_days=31&forecast_days=16')
OM_CACHE = C.DATA / 'wx' / 'openmeteo_view.json'
HOL = {'2025-05-19', '2025-07-01', '2025-08-04', '2025-09-01', '2025-10-13', '2025-12-25', '2025-12-26', '2026-01-01', '2026-02-16',
       '2026-04-03', '2026-05-18', '2026-07-01', '2026-08-03', '2026-09-07', '2026-10-12', '2026-12-25', '2026-12-26', '2027-01-01'}
DT_NAMES = {0: 'Monday', 1: 'Tue-Thu', 2: 'Tue-Thu', 3: 'Tue-Thu', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}


def _dtype(d):
    return 'Holiday' if d in HOL else DT_NAMES[pd.Timestamp(d).dayofweek]


def _om():
    try:
        with urllib.request.urlopen(OM_URL, timeout=20) as r: txt = r.read().decode()
        OM_CACHE.parent.mkdir(parents=True, exist_ok=True); OM_CACHE.write_text(txt, encoding='utf-8'); src = 'Open-Meteo, live'
    except Exception:
        if not OM_CACHE.exists(): return None, 'none'
        txt = OM_CACHE.read_text(encoding='utf-8')
        src = 'Open-Meteo, cached ' + pd.Timestamp(OM_CACHE.stat().st_mtime, unit='s').strftime('%b %d %H:%M UTC')
    J = json.loads(txt); h = pd.DataFrame(J[0]['hourly']); h['date'] = h.time.str[:10]; h['hr'] = h.time.str[11:13].astype(int)
    return h, src


def _history():
    act = pd.read_csv(C.CACHE / 'ieso_load_actual.csv'); t = pd.to_datetime(act.EffectiveDateTime) + pd.Timedelta(hours=1)
    act['date'], act['he'] = C._ts_to_key(t); act = act.dropna(subset=['he'])
    wx = pd.read_csv(C.CACHE / 'cyyz_weather_actual.csv'); t = pd.to_datetime(wx.EffectiveDateTime) + pd.Timedelta(hours=1)
    wx['date'], wx['he'] = C._ts_to_key(t); wx = wx.dropna(subset=['he'])
    d = act.groupby('date').Load.max().rename('peak').to_frame().join(
        wx.groupby('date').Temperature.agg(['max', 'min']).rename(columns={'max': 'tmax', 'min': 'tmin'}), how='inner').reset_index()
    d['tavg'] = (d.tmax + d.tmin) / 2; d['typ'] = d.date.map(_dtype)
    return d[d.date >= '2025-05-01']


def _curve(d):
    """Tue-Thu daily peak vs daily-average °F (2°F bins, smoothed), plus day-type offsets at the same temperature."""
    b = d[d.typ == 'Tue-Thu']; co = np.polyfit(b.tavg, b.peak, 4)
    f = lambda t: float(np.polyval(co, np.clip(t, b.tavg.quantile(.02), b.tavg.quantile(.98))))
    d = d.assign(res=d.peak - d.tavg.map(f))
    off = d.groupby('typ').res.mean().to_dict(); off['Tue-Thu'] = 0.0
    return f, off


def build(target, bundle):
    D = target; hub = bundle['hubs']['EAST']; H = {h['he']: h for h in hub['hours']}
    hist = _history(); f, off = _curve(hist[hist.date < D])
    typ = _dtype(D); mon = pd.Timestamp(D).month
    out = dict(date=D, day_type=typ, month=pd.Timestamp(D).strftime('%B'))
    # ---- 1. temperature
    h, src = _om(); T = None
    if h is not None and (h.date == D).any():
        x = h[h.date == D]; tmax = x.temperature_2m.max() * 9 / 5 + 32; tmin = x.temperature_2m.min() * 9 / 5 + 32; tavg = (tmax + tmin) / 2
        slope = (f(tavg + 3) - f(tavg - 3)) / 6
        zone = 'flat (50-62°F)' if 50 <= tavg <= 62 else ('hot side' if tavg > 62 else 'cold side')
        T = dict(src=src, tmax=round(tmax), tmin=round(tmin), tavg=round(tavg), zone=zone, slope=round(slope),
                 bust=round(abs(slope) * 3), curve_peak=round(f(tavg) + off.get(typ, 0)), offset=round(off.get(typ, 0)))
        if 4 <= mon <= 9:
            out['cloud'] = dict(mid=round(float(x[x.hr.between(11, 15)].cloud_cover.mean())))
        p = x.pressure_msl; out['pressure'] = dict(avg=round(float(p.mean())), change=round(float(p.iloc[-1] - p.iloc[0]), 1))
    out['temp'] = T
    # ---- 2. load
    ieso = max(h_['dem_fc'] for h_ in hub['hours'])
    pk_he = max(hub['hours'], key=lambda h_: h_['dem_fc'])['he']
    a = C.adq2('preDA')[['date', 'he', 'dem_fc']]
    dp = a.groupby('date').dem_fc.max().rename('fc').to_frame().join(hist.set_index('date').peak, how='inner')
    last30 = dp[(dp.index < (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat())].tail(30)
    bias = float((last30.peak - last30.fc).mean()) if len(last30) else 0.0
    TS = bundle.get('tesla') or {}
    tes = [x['tesla'] for x in TS.get('hours', []) if x.get('tesla') is not None]
    tes_pk = max(tes) if tes else None
    adj = ieso + bias; blend = adj if tes_pk is None else (adj + tes_pk) / 2
    vs = [x['vs_usual'] for x in TS.get('hours', []) if 16 <= x['he'] <= 20 and x.get('vs_usual') is not None]
    lw = (pd.Timestamp(D) - pd.Timedelta(days=7)).date().isoformat(); L = hist.set_index('date')
    lwk = None
    if lw in L.index:
        r = L.loc[lw]; base = float(r.peak)
        if T: base += f(T['tavg']) - f(float(r.tavg))
        lw_fc = dp.fc.get(lw) if lw in dp.index else None
        lwk = dict(date=lw, peak=round(float(r.peak)), tavg=round(float(r.tavg)), base=round(base), gap=round(ieso - base),
                   t_adj=round(base - float(r.peak)), lw_fc=None if lw_fc is None or pd.isna(lw_fc) else round(float(lw_fc)),
                   lw_miss=None if lw_fc is None or pd.isna(lw_fc) else round(float(r.peak) - float(lw_fc)))
    out['load'] = dict(ieso=round(ieso), ieso_he=pk_he, bias30=round(bias), ieso_adj=round(adj), tesla=None if tes_pk is None else round(tes_pk),
                       tesla_stale=bool(TS.get('stale')), tesla_issued=TS.get('issued'), blend=round(blend),
                       vs_usual=None if not vs else round(float(np.mean(vs))), lastweek=lwk)
    # ---- 3. wind (evening HE17-20)
    pk = [H[k] for k in range(17, 21) if k in H]
    wi = np.mean([x['stack']['wind_ieso'] for x in pk if x['stack'].get('wind_ieso') is not None])
    wm = [x['stack']['wind_meteo'] for x in pk if x['stack'].get('wind_meteo') is not None]
    wm = float(np.mean(wm)) if wm else None
    w = C.adq2('preDA')[['date', 'he', 'wind_fc']]; w = w[w.he.between(17, 20) & (pd.to_datetime(w.date).dt.month == mon) & (w.date < D)]
    ramp = None
    if 15 in H and 20 in H and H[15]['stack'].get('wind_ieso') is not None:
        ramp = round(H[20]['stack']['wind_ieso'] - H[15]['stack']['wind_ieso'])
    out['wind'] = dict(ieso=round(wi), meteo=None if wm is None else round(wm), gap=None if wm is None else round(wm - wi),
                       normal=None if w.empty else round(float(w.wind_fc.mean())), ramp=ramp)
    # ---- 4. supply
    o = bundle.get('outages') or {}; tm = (o.get('look30') or {}).get('tomorrow') or {}
    a2 = C.adq2('preDA'); x = a2[a2.date == D].set_index('he').sort_index()
    steps = []
    for col, lab in (('gas_out', 'gas'), ('nuc_out', 'nuclear'), ('hyd_out', 'hydro')):
        dd = x[col].diff()
        for he_, v in dd.items():
            if 14 <= he_ <= 24 and abs(v) >= 150: steps.append(dict(he=int(he_), fuel=lab, mw=round(float(v))))
    out['supply'] = dict(tot=(tm.get('tot') or {}), nuc=(tm.get('nuc') or {}), gas=(tm.get('gas') or {}), steps=steps,
                         trips=tm.get('trips'))
    # ---- net
    heads = {k: H[k]['head'] for k in range(17, 21) if k in H}
    mh = min(heads, key=heads.get)
    out['net'] = dict(peak_head=round(heads[mh]), peak_head_he=mh, load_surprise=round(blend - adj),
                      wind_surprise=None if wm is None else round(wm - wi))
    # ---- gas & ramp: gas need from tomorrow's stack, ramps of residual load (demand - wind - solar) vs the last 60 days
    gn = {k: H[k]['stack'].get('gas_need') for k in H}; ga = {k: H[k]['stack'].get('gas_av') for k in H}
    pk_he2 = max((k for k in gn if gn[k] is not None), key=lambda k: gn[k])
    steps = [(k, gn[k] - gn[k - 1]) for k in range(2, 25) if gn.get(k) is not None and gn.get(k - 1) is not None]
    up = max(steps, key=lambda t: t[1]); dn = min(steps, key=lambda t: t[1])
    a3 = C.adq2('preDA')[['date', 'he', 'dem_fc', 'wind_fc', 'solar_fc']]
    a3['res'] = a3.dem_fc - a3.wind_fc.fillna(0) - a3.solar_fc.fillna(0)
    rw = a3.pivot_table(index='date', columns='he', values='res')
    rmp = pd.DataFrame({'am': rw[8] - rw[5], 'pm': rw[19] - rw[15]})
    hist60 = rmp[(rmp.index < D) & (rmp.index >= (pd.Timestamp(D) - pd.Timedelta(days=60)).date().isoformat())]
    def _r(k):
        if D not in rmp.index or pd.isna(rmp.loc[D, k]): return None
        v = float(rmp.loc[D, k]); allh = rmp[(rmp.index < D) & (rmp.index >= '2025-07-01')][k].dropna()
        q = int((allh < v).mean() * 5) + 1 if len(allh) else None
        return dict(mw=round(v), pct=round(float((hist60[k] < v).mean() * 100)) if len(hist60) else None, quint=min(q, 5) if q else None)
    out['ramp'] = dict(gas_av=round(ga[pk_he2]), gas_need_pk=round(gn[pk_he2]), gas_pk_he=pk_he2, spare=round(ga[pk_he2] - gn[pk_he2]),
                       up_he=up[0], up_mw=round(up[1]), dn_he=dn[0], dn_mw=round(dn[1]), am=_r('am'), pm=_r('pm'))
    return out
