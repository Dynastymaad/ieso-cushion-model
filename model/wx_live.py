"""wx_live.py -- Nov 5 2026: keep the bid-time temperature history current (Open-Meteo Previous Runs API, public, no key).
Fetches the last 45 days + 2 days ahead for the 6 Ontario load centres, merges into data/wx/openmeteo_prevruns_ontario.csv.gz,
then rebuilds data/wx/wx_hourly.csv (wx_bid.build). Only the 2-day-old run (_pd2) is used for delivery day D: issued before D-1 08:00 MT.
Feeds the 'Temp swing' card point (physics_read_live). A failure here only drops that point to 0."""
import sys, json, urllib.request; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import pandas as pd, common as C
LOC = {'YYZ': (43.68, -79.63), 'YOW': (45.32, -75.67), 'YHM': (43.17, -79.93), 'YXU': (43.04, -81.15), 'BAR': (44.39, -79.69), 'YQG': (42.28, -82.96)}
V = ['temperature_2m', 'dew_point_2m', 'apparent_temperature', 'cloud_cover', 'precipitation', 'wind_speed_10m']
def fetch(past=45):
    hv = ','.join(V + [f'{v}_previous_day{k}' for v in V for k in (1, 2)])
    lat = ','.join(str(v[0]) for v in LOC.values()); lon = ','.join(str(v[1]) for v in LOC.values())
    url = (f'https://previous-runs-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly={hv}'
           f'&past_days={past}&forecast_days=3&timezone=GMT&temperature_unit=fahrenheit&wind_speed_unit=kmh&precipitation_unit=inch')
    with urllib.request.urlopen(url, timeout=60) as r: js = json.loads(r.read().decode())
    if isinstance(js, dict): js = [js]
    out = []
    for code, j in zip(LOC, js):
        d = pd.DataFrame(j['hourly']).rename(columns={'time': 'time_utc'}); d.columns = [c.replace('_previous_day', '_pd') for c in d.columns]
        d.insert(0, 'loc', code); out.append(d)
    return pd.concat(out, ignore_index=True)
if __name__ == '__main__':
    f = C.DATA / 'wx' / 'openmeteo_prevruns_ontario.csv.gz'
    new = fetch(); old = pd.read_csv(f)
    new = new[new.temperature_2m_pd2.notna() | new.temperature_2m.notna()]
    al = pd.concat([old, new[[c for c in old.columns if c in new.columns]]], ignore_index=True).drop_duplicates(['loc', 'time_utc'], keep='last').sort_values(['loc', 'time_utc'])
    al.to_csv(f, index=False); print(f'wx_live: {len(new):,} rows fetched, history {al.time_utc.min()} .. {al.time_utc.max()}')
    import wx_bid; wx_bid.build()
