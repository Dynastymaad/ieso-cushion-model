"""wx_bid.py -- temperature forecast as it stood at the DA bid deadline, Ontario load-weighted.
Source: Open-Meteo Previous Runs API (public, no key; pulled through the browser, data/wx/openmeteo_prevruns_ontario.csv.gz).
  <var>_pd2 = the forecast for that hour issued two days earlier (run ~48 h before the hour). For every hour of delivery day D
  that run was published before D-1 08:00 MT, so pd2 is always bid-safe. pd1 (24 h earlier) is NOT safe for most of D.
  <var> (no suffix) = the latest analysis ~ what happened.
Weights (share of Ontario load, rounded): Toronto .40, Ottawa .16, Hamilton .12, London .12, Barrie .12, Windsor .08.
Output data/wx/wx_hourly.csv keyed (date, he) in the IESO clock (EST, hour ending)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
W = {'YYZ': .40, 'YOW': .16, 'YHM': .12, 'YXU': .12, 'BAR': .12, 'YQG': .08}
V = ['temperature_2m', 'dew_point_2m', 'apparent_temperature', 'cloud_cover', 'precipitation', 'wind_speed_10m']
SHORT = {'temperature_2m': 't', 'dew_point_2m': 'dp', 'apparent_temperature': 'feel', 'cloud_cover': 'cc', 'precipitation': 'pr', 'wind_speed_10m': 'ws'}

def build():
    x = pd.read_csv(C.DATA / 'wx' / 'openmeteo_prevruns_ontario.csv.gz')
    x['w'] = x['loc'].map(W)
    t = pd.to_datetime(x.time_utc) - pd.Timedelta(hours=5) + pd.Timedelta(hours=1)          # instant at hour-beginning EST -> HE
    x['date'], x['he'] = C._ts_to_key(t)
    cols = {}
    for v in V:
        for suf, tag in (('', 'act'), ('_pd2', 'fc')):
            cols[f'{SHORT[v]}_{tag}'] = v + suf
    g = x.groupby(['date', 'he'])
    out = pd.DataFrame({k: g.apply(lambda d, c=c: np.average(d[c], weights=d.w) if d[c].notna().all() else np.nan) for k, c in cols.items()})
    out = out.reset_index(); out['he'] = out.he.astype(int)
    out['yyz_t_fc'] = x[x['loc'] == 'YYZ'].set_index(['date', 'he'])['temperature_2m_pd2'].reindex(pd.MultiIndex.from_frame(out[['date', 'he']])).values
    out.to_csv(C.DATA / 'wx' / 'wx_hourly.csv', index=False)
    e = (out.t_fc - out.t_act); print(f'wx_hourly: {len(out)} h {out.date.min()}..{out.date.max()}; bid-time temp fc error MAE {e.abs().mean():.2f}F bias {e.mean():+.2f}F')
    return out

if __name__ == '__main__':
    o = build()
    a = pd.read_csv(C.CACHE / 'cyyz_weather_actual.csv'); t = pd.to_datetime(a.EffectiveDateTime.str.slice(0, 19)) + pd.Timedelta(hours=1)
    a['date'], a['he'] = C._ts_to_key(t); a = a.groupby(['date', 'he']).Temperature.last().reset_index(); a['he'] = a.he.astype(int)
    m = o.merge(a, on=['date', 'he'])
    print(f'check vs CYYZ observed: Open-Meteo Toronto fc (pd2) MAE {(m.yyz_t_fc - m.Temperature).abs().mean():.2f}F, corr {m.yyz_t_fc.corr(m.Temperature):.3f}, n {len(m)}')
