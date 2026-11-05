"""pipeline_health.py -- Oct 31 2026. Every morning: newest date in each input the model uses, against how fresh it should be.
Writes data/pipeline_health.json (run_model puts it in the bundle; the page shows a red banner if anything is stale) and prints
a table, so a feed that stops updating is caught the next morning instead of weeks later (the hydro history stopped Sep 27 unseen).
'lag' = how many days old the newest row may be, counted from tomorrow (the delivery day being bid); weekends get +2 for market data."""
import sys, json, os, glob, time; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import pandas as pd, common as C
R = C.ROOT
CHECKS = [  # label, file, date column, max age in days vs the delivery day, what it feeds, critical
 ('IESO pre-DA Adequacy (tomorrow)', 'cache/ieso_adq2_preDA.csv', 'date', 0, 'load / wind / supply at the bid, every tab', True),
 ('Load forecasts (IESO/Tesla/Meteo)', 'cache/ieso_load_fc.csv', 'EffectiveDateTime', 0, 'Fundamentals, signals', True),
 ('Wind forecasts (IESO/Meteologica)', 'cache/ieso_wind_fc.csv', 'EffectiveDateTime', 0, 'Fundamentals, gas need', True),
 ('Pre-DA intertie limits', 'data/ieso_preda_intertie_limits.csv', 'date', 0, 'export caps in gas need', True),
 ('Outage timeline', 'data/outage_features.csv', 'date', 0, 'Outages tab, gas returns', True),
 ('DA / RT prices (IESO)', 'data/prices_hourly.csv', 'date', 2, 'every backtest, History, Correlation', True),
 ('DA cleared ties', 'data/da_cleared_ties.csv', 'date', 2, 'Fundamentals (cleared yday)', False),
 ('Actual load', 'cache/ieso_load_actual.csv', 'EffectiveDateTime', 3, 'accuracy scores, stars', False),
 ('Actual output by fuel', None, 'fuel', 3, 'gas-need miss, spare adj., History', True),
 ('Adequacy3 final (DA schedules)', 'data/adq3_final.csv', 'date', 3, 'gas need: hydro / exports', True),
 ('Intertie flows actual', 'data/intertie_actual.csv', 'date', 3, 'backtest gas need', True),
 ('Hydro forecast history', 'data/bt_hydro_fc.csv', 'date', 3, 'backtest gas need, RT read', True),
 ('Block model features (incl. PJM)', 'data/blocks_features.csv', 'date', 4, 'DA forecast (block half)', True),
 ('Block model backtest', 'data/bt_blocks.csv', 'date', 4, 'DA forecast ranges', True),
 ('DA backtest (accuracy panels)', 'data/bt_hourly_EAST.csv', 'date', 1, 'Next day accuracy, ranges', False),
 ('DA Virtual frame', 'data/dv_frame_EAST.csv', 'date', 0, 'ladders, RT read, Gates', True),
 ('Ontario Hub forward (XDE)', None, 'fwd:XDE', 4, 'DA forecast (block half)', True),
 ('Dawn gas (CVX)', None, 'fwd:CVX', 4, 'DA forecast, CAHR, RT read', True),
 ('PJM West Hub DA forward (PDA)', None, 'fwd:PDA', 4, 'DA forecast: PJM price change feature', True),
 ('NY net imports from PJM', None, 'nypjm', 1, 'NY panel (PJM flows into NY)', False),
 ('FX USD/CAD', 'cache/fx_usdcad.csv', 'Date', 5, 'CAHR (gas in CAD)', False),
 ('NYISO DAM (Zone A, PJM net imports)', 'data/nyiso_dam_energy.csv', 'date', 1, 'DA forecast, NY panel', True),
 ('Market virtuals (all traders)', 'cache/market_virtuals.csv', 'deliverydate', 2, 'market behaviour study', False),
 ('Dynasty virtuals (our trades)', 'cache/dynasty_virtuals.csv', 'date', 4, 'Next day: desk trades panel', False),
 ('Quebec flows', 'data/qc_flows.csv', 'date', 4, 'East-Ottawa & Quebec tab', False),
 ('Toronto weather actual', 'cache/cyyz_weather_actual.csv', 'EffectiveDateTime', 3, 'checks panel', False),
 ('Outage lead history', 'cache/ieso_adq2_leads.csv', 'date', -30, 'Outages tab 35-day "expected" line (weekly pull)', False),
]

def newest(path, col):
    if col == 'fuel': return C.fuel_actual().date.max()
    if col.startswith('fwd:'):
        f = pd.read_csv(R / 'cache' / 'fwd_daily_ontario.csv', usecols=['ExchangeCode', 'EffectiveDate']); return str(f[f.ExchangeCode == col[4:]].EffectiveDate.astype(str).str[:10].max())
    if col == 'nypjm':
        n = pd.read_csv(C.DATA / 'nyiso_dam_energy.csv', usecols=['date', 'ny_dni_pjm']); return str(n.dropna().date.max())
    p = R / path
    if not p.exists(): return None
    return str(pd.read_csv(p, usecols=[col])[col].astype(str).str[:10].max())

def build(D=None):
    D = D or (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).date().isoformat()
    Dt = pd.Timestamp(D); wk = 2 if Dt.dayofweek in (0, 1) else 0          # Monday/Tuesday delivery: weekend gap in market data
    rows = []
    for lab, path, col, lag, feeds, crit in CHECKS:
        try: n = newest(path, col)
        except Exception as ex: n = None
        need = (Dt - pd.Timedelta(days=lag + (wk if lag > 0 else 0))).date().isoformat()
        age = None if n is None else (Dt - pd.Timestamp(n)).days
        ok = n is not None and n >= need
        rows.append(dict(label=lab, newest=n, need=need, age=age, ok=bool(ok), feeds=feeds, critical=crit))
    dc = R / 'archive' / 'DASecurityConstraints2'; want = (Dt - pd.Timedelta(days=1)).strftime('%Y%m%d')
    have = any(want in n for z in dc.glob('*.zip') for n in __import__('zipfile').ZipFile(z).namelist())
    rows.append(dict(label='DA constraint list (gate)', newest=want if have else None, need=want, age=None, ok=have, feeds='Gates: congestion gate', critical=True))
    # Nov 1 2026: does the delivery day itself have each bid-time feed, and which version? (a feed can be 'fresh' by date but
    # still missing tomorrow's hours if the morning run was early: Meteologica wind lands 07:18 MT, NYISO DAM ~07:35 MT)
    def cov(lab, fn, feeds, crit=False):
        try: n, ver = fn()
        except Exception as ex: n, ver = 0, None
        rows.append(dict(label=lab, newest=(f'{n}/24 h' + (f' · {ver}' if ver else '')), need='24/24 h', age=None, ok=bool(n >= 23), feeds=feeds, critical=crit))
    def _adq():
        a = pd.read_csv(R / 'cache' / 'ieso_adq2_preDA.csv', usecols=['date', 'hour', 'ieso_createtime']); a = a[a.date == D]
        d1 = (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat(); ok = a[a.ieso_createtime.astype(str).str[:10] == d1]   # Nov 5 2026: only a D-1 vintage counts
        return ok.hour.nunique(), ((str(a.ieso_createtime.max())[5:16] + ' EST') + ('' if len(ok) else ' (older than D-1: IESO late)')) if len(a) else None
    def _lf(c):
        L = C.load_forecasts_at_bid(); x = L[L.date == D]; return int(x[c].notna().sum()) if c in x else 0, None
    def _wf():
        import supply_fc as S
        w = S.wind_at_bid(); x = w[w.date == D]; return int(x.wf_meteologica.notna().sum()) if 'wf_meteologica' in x else 0, None
    def _ny():
        n = pd.read_csv(C.DATA / 'nyiso_zoneA_da.csv'); return int((n.date == D).sum()), None
    cov('Tomorrow: IESO pre-DA Adequacy version', _adq, 'IESO load / wind / outages at the bid', True)
    cov('Tomorrow: Meteologica load', lambda: _lf('lf_meteologica'), 'load gap (card + physics read)')
    cov('Tomorrow: Tesla load', lambda: _lf('lf_tesla'), 'load gap fallback, stars')
    cov('Tomorrow: Meteologica wind (lands ~07:18 MT)', _wf, 'wind gap (card + physics read): run morning.py --wind if missing')
    cov('Tomorrow: NYISO DAM (posted ~07:35 MT)', _ny, 'NY pull (physics read): run morning.py --wind after 07:40 MT if missing')
    out = dict(date=D, checked=time.strftime('%Y-%m-%d %H:%M'), rows=rows, stale=[r['label'] for r in rows if not r['ok']],
               stale_critical=[r['label'] for r in rows if not r['ok'] and r['critical']])
    (C.DATA / 'pipeline_health.json').write_text(json.dumps(out, indent=1))
    return out

if __name__ == '__main__':
    o = build(sys.argv[1] if len(sys.argv) > 1 else None)
    print(pd.DataFrame(o['rows'])[['label', 'newest', 'need', 'ok', 'critical']].to_string(index=False))
    print('\nSTALE:', o['stale'] or 'none')
