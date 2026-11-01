"""fc_scores.py -- Oct 31 2026. Which load / wind forecast has been most accurate lately (the star on the Fundamentals tab).
Average absolute miss per hour over the last 7 settled days known at the bid (through D-2), forecasts as they stood at the bid.
Window test (research/star_window_test.py, Apr-Oct 2026): a 7-day window picked the day's best vendor more often than 14 days
(load 50% vs 45%, wind since Sep 64% vs 61%); 30 days was similar. Display only."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, supply_fc as S
WIN = 7

def _score(df, act, V, D, n):
    c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
    x = df[(df.date <= c2)].dropna(subset=[act]); days = sorted(x.date.unique())[-n:]; x = x[x.date.isin(days)]
    out = {}
    for v in V:
        e = (x[v] - x[act]).dropna(); nd = x.loc[e.index, 'date'].nunique()
        out[v] = dict(mae=None if nd < max(3, n // 2) else int(round(e.abs().mean())), bias=None if nd < max(3, n // 2) else int(round(e.mean())), days=int(nd))
    ok = {k: v['mae'] for k, v in out.items() if v['mae'] is not None}
    return out, (min(ok, key=ok.get) if ok else None), (days[0] if days else None), (days[-1] if days else None)

def build(D):
    L = C.load_forecasts_at_bid(); a = C.adq2('preDA')[['date', 'he', 'dem_fc', 'wind_fc']]
    act = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'ont_dem']]
    ld = a[['date', 'he', 'dem_fc']].rename(columns={'dem_fc': 'IESO'}).merge(
        L.rename(columns={'lf_tesla': 'Tesla', 'lf_meteologica': 'Meteo', 'lf_dynasty': 'Dynasty'})[['date', 'he', 'Tesla', 'Meteo', 'Dynasty']], on=['date', 'he'], how='left').merge(act, on=['date', 'he'], how='left')
    w = S.wind_at_bid(); g = C.fuel_actual()[['date', 'he', 'g_wind']]
    wd = a[['date', 'he', 'wind_fc']].rename(columns={'wind_fc': 'IESO'}).merge(w[['date', 'he', 'wf_meteologica']].rename(columns={'wf_meteologica': 'Meteo'}), on=['date', 'he'], how='left').merge(g, on=['date', 'he'], how='left')
    out = {'window': WIN}
    for k, (df, ac, V) in {'load': (ld, 'ont_dem', ['IESO', 'Tesla', 'Dynasty', 'Meteo']), 'wind': (wd, 'g_wind', ['IESO', 'Meteo'])}.items():
        s, best, d0, d1 = _score(df, ac, V, D, WIN); s30, b30, _, _ = _score(df, ac, V, D, 30)
        out[k] = dict(scores=s, best=best, frm=d0, to=d1, best30=b30, mae30={v: s30[v]['mae'] for v in V})
    tgt = L[L.date == D]; out['dynasty_live'] = bool(len(tgt) and tgt.lf_dynasty.notna().any())
    return out

if __name__ == '__main__':
    import json; print(json.dumps(build((pd.Timestamp.today() + pd.Timedelta(days=1)).date().isoformat()), indent=1))
