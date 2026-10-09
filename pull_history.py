"""
pull_history.py -- pull the Ontario modelling history out of both databases
into cache\\ (CSV). Heavier than the probes, but every query is either on an
indexed column or chunked by month, and progress prints as it goes.

    python pull_history.py              # everything, from 2024-06-01
    python pull_history.py --only adq2  # one piece: load wind solar actual wx fwd fx adq2 adq2x virt horizon
    python pull_history.py --only wxfc --since 2025-04-01      # weather forecast vintages (Warehouse)
    python pull_history.py --only outages --since 2025-05-01   # outage timeline from the Adequacy2 archive (sandbox)
    python pull_history.py --only fwd35 --since 2025-05-01     # 35-day outage schedule now + its 16-34 day history
    python pull_history.py --only quebec --since 2025-05-01    # Hydro-Quebec demand (Warehouse) + IESO DA intertie LMPs (sandbox)
    python pull_history.py --since 2025-04-01
    python pull_history.py --only windtopup   # last 3 days of vendor wind (Meteologica lands ~07:18 MT), merged into the cache

Re-running overwrites the CSVs. Expect 5-20 minutes the first time, most of it
the Adequacy2 archive (121M rows, no index, so it is read in ONE pass).
"""
import argparse, time, warnings
warnings.filterwarnings('ignore', message='pandas only supports SQLAlchemy')
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd
import ont_probe as P

CACHE = P.HERE / 'cache'; CACHE.mkdir(exist_ok=True)


def say(s): print(s, flush=True)


def months(since):
    d = date.fromisoformat(since).replace(day=1); end = date.today() + timedelta(days=40)
    while d < end:
        n = (d.replace(day=28) + timedelta(days=4)).replace(day=1); yield d, n; d = n


def chunked(cn, name, sql, since):
    t0 = time.time(); parts = []
    for a, b in months(since):
        df = pd.read_sql(sql.format(a=a.isoformat(), b=b.isoformat()), cn); parts.append(df)
        say(f'    {name} {a:%Y-%m}: {len(df):>8,} rows  ({time.time()-t0:4.0f}s)')
    df = pd.concat(parts, ignore_index=True); df.to_csv(CACHE / f'{name}.csv', index=False)
    say(f'  -> cache\\{name}.csv  {len(df):,} rows'); return df


def one(cn, name, sql):
    t0 = time.time(); df = pd.read_sql(sql, cn); df.to_csv(CACHE / f'{name}.csv', index=False)
    say(f'  -> cache\\{name}.csv  {len(df):,} rows  ({time.time()-t0:.0f}s)'); return df


# lead filter: keep vintages issued up to 4 days ahead (and a little after, for 'latest' views)
LEAD = "DATEDIFF(hour, [Timestamp], EffectiveDateTime) BETWEEN -3 AND 96"

def mssql(cfg, since, only):
    cn, d = P.connect(cfg, False, 'warehouse'); cn.timeout = 900
    say(f'\n=== Warehouse ({d}) ===')
    if only in (None, 'load'):
        chunked(cn, 'ieso_load_fc', f"""SELECT DataSourceName, [Timestamp], EffectiveDateTime, EffectiveDateTimeUtc, Load, DateCreated
            FROM LoadForecast WITH (NOLOCK) WHERE MarketName='IESO' AND NodeName='ONZN'
            AND EffectiveDateTime >= '{{a}}' AND EffectiveDateTime < '{{b}}' AND {LEAD}""", since)
    if only in (None, 'wind'):
        chunked(cn, 'ieso_wind_fc', f"""SELECT DataSourceName, [Timestamp], EffectiveDateTime, Value, DateCreated
            FROM WindForecast WITH (NOLOCK) WHERE MarketName='IESO'
            AND EffectiveDateTime >= '{{a}}' AND EffectiveDateTime < '{{b}}' AND {LEAD}""", since)
    if only == 'windtopup':
        # Oct 8 2026: Meteologica (and the other wind vendors) land in the Warehouse ~07:18 MT, after an early morning run.
        # Pull only the last 3 days and MERGE into cache\ieso_wind_fc.csv (no truncation of history).
        a = (date.today() - timedelta(days=3)).isoformat(); b = (date.today() + timedelta(days=5)).isoformat()
        new = pd.read_sql(f"""SELECT DataSourceName, [Timestamp], EffectiveDateTime, Value, DateCreated
            FROM WindForecast WITH (NOLOCK) WHERE MarketName='IESO'
            AND EffectiveDateTime >= '{a}' AND EffectiveDateTime < '{b}' AND {LEAD}""", cn)
        f = CACHE / 'ieso_wind_fc.csv'; old = pd.read_csv(f) if f.exists() else new.iloc[:0]
        for c in ('Timestamp', 'EffectiveDateTime', 'DateCreated'): new[c] = new[c].astype(str); old[c] = old[c].astype(str)
        both = pd.concat([old, new], ignore_index=True).drop_duplicates(['DataSourceName', 'Timestamp', 'EffectiveDateTime', 'DateCreated'], keep='last')
        both.to_csv(f, index=False)
        tom = (date.today() + timedelta(days=1)).isoformat(); m = new[(new.DataSourceName == 'Meteologica') & new.EffectiveDateTime.str.startswith(tom)]
        say(f'  wind top-up: {len(new):,} rows pulled, cache now {len(both):,}; Meteologica rows for {tom}: {len(m)}'
            + ('' if len(m) else '  <-- not loaded yet (Warehouse loads it ~07:18 MT); try again in a few minutes'))
        return
    if only in (None, 'solar'):
        chunked(cn, 'ieso_solar_fc', """SELECT DataSourceName, TimeStamp, EffectiveDateTime, Value, DateCreated
            FROM SolarForecast WITH (NOLOCK) WHERE MarketName='IESO'
            AND EffectiveDateTime >= '{a}' AND EffectiveDateTime < '{b}'""", since)
    if only in (None, 'actual'):
        nid = pd.read_sql("SELECT TOP 1 NodeId FROM LoadActualHourly WITH (NOLOCK) WHERE Market='IESO' AND NodeName='ONZN'", cn)
        if len(nid):
            one(cn, 'ieso_load_actual', f"""SELECT EffectiveDateTime, Load, DateCreated FROM LoadActualHourly WITH (NOLOCK)
                WHERE NodeId={int(nid.NodeId[0])} AND Market='IESO' AND EffectiveDateTime >= '{since}'""")
    if only in ('quebec',):
        # Hydro-Quebec system demand (15-min actuals, as loaded) -- the Quebec side of the PQ interties
        one(cn, 'hq_demand', "SELECT EffectiveDateTime, Value, DateCreated FROM HydroQuebecDemand WITH (NOLOCK) WHERE EffectiveDateTime >= '2024-01-01'")
    if only in ('wxfc',):
        # Weather forecast vintages for Ontario load centres, as issued (ObservationDateTime) up to 72 h ahead.
        # Used to rebuild the temperature forecast as it stood at the DA bid deadline (D-1 08:00 MT).
        chunked(cn, 'ieso_wx_fc', """SELECT WeatherStationId, DataSourceName, Description, ObservationDateTime, EffectiveDateTime, Value, DateCreated
            FROM WeatherHourlyForecast WITH (NOLOCK)
            WHERE WeatherStationId IN ('CYYZ','CYOW','CYXU','CYHM','CYSB','CYQT')
              AND Description IN ('Temperature','Dew Point','Relative Humidity','Cloud Cover','Precip (In)','Wind Speed')
              AND EffectiveDateTime >= '{a}' AND EffectiveDateTime < '{b}'
              AND DATEDIFF(hour, ObservationDateTime, EffectiveDateTime) BETWEEN 12 AND 72""", since)
    if only in (None, 'wx'):
        one(cn, 'cyyz_weather_actual', f"""SELECT * FROM WeatherHourly WITH (NOLOCK)
            WHERE WeatherStationId='CYYZ' AND EffectiveDateTime >= '{since}'""")
    if only in (None, 'fwd'):
        one(cn, 'fwd_daily_ontario', f"""SELECT EffectiveDate, Strip, ExchangeCode, NodeName, Price, DateCreated
            FROM ForwardPrices WITH (NOLOCK)
            WHERE CommodityName IN ('Electricity','Natural Gas') AND MonthlyDaily='D' AND EffectiveDate >= '{since}'
              AND ExchangeCode IN ('XDE','XEA','XDG','XDZ','XDY','CVX','XCL','PDA','ADP','HHD')""")
    if only in (None, 'fx'):
        one(cn, 'fx_usdcad', "SELECT [Date], Rate FROM ExchangeRate WHERE Ticker='USD/CAD' AND [Date] >= '2024-01-01'")
    cn.close()


ADQ2_SUBTYPES = ("'Forecast','Gas Capacity','Gas Outage','Nuclear Capacity','Nuclear Outage','Hydro Capacity',"
                 "'Hydro Outage','Hydro Forecast Energy','Wind Capacity','Wind Forecast','Wind Outage','Solar Capacity',"
                 "'Solar Forecast','Biofuel Capacity','Biofuel Outage','Storage Capacity','Storage Outage','Wind','Solar',"
                 "'Capacity','Offered Capacity','Energy','Gas Schedule','Nuclear Schedule','Hydro Schedule',"
                 "'Wind Schedule','Solar Schedule','Biofuel Schedule','Storage Schedule','Other Schedule'")

def pg(cfg, since, only):
    c = cfg.get('composition_db') or cfg
    cn, d = P.connect(c, True, 'sandbox'); cur = cn.cursor(); cur.execute("SET statement_timeout = '1800s'")
    say(f'\n=== sandbox ({d}) ===')
    if only in (None, 'adq2'):
        say('  Adequacy2 pre-deadline vintage (last version issued on D-1 before 09:00 EST) -- one pass, be patient')
        one(cn, 'ieso_adq2_preDA', f"""
            SELECT DISTINCT ON (date, hour, resourcetype, subtype)
                   date, hour, resourcetype, subtype, value, ieso_createtime
            FROM canpower.ieso_adequacy2_all_archive
            WHERE date >= '{since}' AND subtype IN ({ADQ2_SUBTYPES})
              AND ieso_createtime >= date - interval '2 days'
              AND ieso_createtime <  date - interval '1 day' + interval '9 hours'
            ORDER BY date, hour, resourcetype, subtype, ieso_createtime DESC""")
        say('  Adequacy2 final vintage (last version issued up to the end of the delivery day)')
        one(cn, 'ieso_adq2_final', f"""
            SELECT DISTINCT ON (date, hour, resourcetype, subtype)
                   date, hour, resourcetype, subtype, value, ieso_createtime
            FROM canpower.ieso_adequacy2_all_archive
            WHERE date >= '{since}' AND subtype IN ({ADQ2_SUBTYPES})
              AND ieso_createtime >= date - interval '1 day'
              AND ieso_createtime <  date + interval '1 day'
            ORDER BY date, hour, resourcetype, subtype, ieso_createtime DESC""")
    if only in (None, 'adq2x'):
        X = ("resourcetype IN ('Total Exports','Total Imports','Zonal Export','Zonal Import','Unscheduled','Dispatchable Load','Demand Response')"
             " OR subtype IN ('Hydro Offer','Gas Offer','Nuclear Offer','Biofuel Offer','Offer Forecast')")
        say('  Adequacy2 interties + offers, pre-deadline vintage (for bid-time forecasts)')
        one(cn, 'ieso_adq2x_preDA', f"""
            SELECT DISTINCT ON (date, hour, resourcetype, subtype)
                   date, hour, resourcetype, subtype, value, ieso_createtime
            FROM canpower.ieso_adequacy2_all_archive
            WHERE date >= '{since}' AND ({X})
              AND ieso_createtime >= date - interval '2 days'
              AND ieso_createtime <  date - interval '1 day' + interval '9 hours'
            ORDER BY date, hour, resourcetype, subtype, ieso_createtime DESC""")
        say('  Adequacy2 interties + offers, final vintage (= DA schedules by interface)')
        one(cn, 'ieso_adq2x_final', f"""
            SELECT DISTINCT ON (date, hour, resourcetype, subtype)
                   date, hour, resourcetype, subtype, value, ieso_createtime
            FROM canpower.ieso_adequacy2_all_archive
            WHERE date >= '{since}' AND ({X})
              AND ieso_createtime >= date - interval '1 day'
              AND ieso_createtime <  date + interval '1 day'
            ORDER BY date, hour, resourcetype, subtype, ieso_createtime DESC""")
    if only in ('outages',):
        say('  Adequacy2 outage timeline: every change in gas / nuclear / hydro outage and capacity, D-3 .. end of D (one pass)')
        one(cn, 'ieso_adq2_outage_timeline', f"""
            SELECT date, hour, subtype, value, ieso_createtime FROM (
              SELECT date, hour, subtype, value, ieso_createtime,
                     LAG(value) OVER (PARTITION BY date, hour, subtype ORDER BY ieso_createtime) AS prev
              FROM canpower.ieso_adequacy2_all_archive
              WHERE date >= '{since}'
                AND subtype IN ('Gas Outage','Nuclear Outage','Hydro Outage','Gas Capacity','Nuclear Capacity','Hydro Capacity','Wind Forecast','Forecast')
                AND ieso_createtime >= date - interval '3 days' AND ieso_createtime < date + interval '1 day') s
            WHERE prev IS NULL OR value <> prev
            ORDER BY date, hour, subtype, ieso_createtime""")
    if only in ('quebec',):
        say('  IESO DA intertie LMPs (Quebec, New York and all other interties), all report types')
        one(cn, 'ieso_da_intertie_lmp', f"""
            SELECT report_type, delivery_date, intertie_name, lmp_component, delivery_hour, lmp_value, created_at
            FROM canpower.ieso_da_hourly_intertie_lmp WHERE delivery_date >= '{since}'""")
    if only in ('fwd35',):
        say('  Adequacy2 35-day outage schedule: latest vintage for every future date (as of now)')
        one(cn, 'ieso_adq2_fwd35', f"""
            SELECT DISTINCT ON (date, hour, subtype) date, hour, resourcetype, subtype, value, ieso_createtime
            FROM canpower.ieso_adequacy2_all_archive
            WHERE date > CURRENT_DATE - 1 AND date <= CURRENT_DATE + 36
              AND subtype IN ('Forecast','Gas Outage','Nuclear Outage','Hydro Outage','Gas Capacity','Nuclear Capacity','Hydro Capacity','Wind Forecast','Solar Forecast')
              AND ieso_createtime >= CURRENT_DATE - 3
            ORDER BY date, hour, subtype, ieso_createtime DESC""")
        say('  Adequacy2 outage schedule at 16-34 days lead (history, for measuring how the 35-day view drifts) -- one pass')
        one(cn, 'ieso_adq2_leads34', f"""
            SELECT DISTINCT ON (date, hour, subtype, lead)
                   date, hour, subtype, value, ieso_createtime, lead
            FROM (SELECT date, hour, subtype, value, ieso_createtime, (date - ieso_createtime::date) AS lead
                  FROM canpower.ieso_adequacy2_all_archive
                  WHERE date >= '{since}' AND subtype IN ('Gas Outage','Nuclear Outage','Hydro Outage','Forecast')
                    AND ieso_createtime::time < '09:00' AND hour IN (8, 12, 17, 20)
                    AND (date - ieso_createtime::date) BETWEEN 16 AND 34) s
            ORDER BY date, hour, subtype, lead, ieso_createtime DESC""")
    if only in (None, 'virt'):
        one(cn, 'dynasty_virtuals', "SELECT * FROM canpower.ieso_dynasty_virtual_transactions")
        one(cn, 'market_virtuals', "SELECT * FROM canpower.ieso_virtual_transactions")
    cn.close()


# ---------------------------------------------------------------- 2-week horizon
HORIZON_SUBTYPES = ("'Forecast','Nuclear Capacity','Nuclear Outage','Gas Capacity','Gas Outage',"
                    "'Hydro Capacity','Hydro Outage','Wind Forecast','Solar Forecast'")

def horizon(cfg, since):
    """Forecast vintages at 2-15 days lead, for testing the 2-week view.
    Warehouse: load (IESO/Tesla/DYNASTY) and wind (IESO/Meteologica/Frontier) up to 16 days out.
    sandbox: for each delivery date and lead k = 2..15 days, the last Adequacy2 vintage issued
    on day D-k before 09:00 EST (what we would have known that morning)."""
    cn, d = P.connect(cfg, False, 'warehouse'); cn.timeout = 900
    say(f'\n=== Warehouse horizon ({d}) ===')
    chunked(cn, 'ieso_load_fc_long', """SELECT DataSourceName, [Timestamp], EffectiveDateTime, Load, DateCreated
        FROM LoadForecast WITH (NOLOCK) WHERE MarketName='IESO' AND NodeName='ONZN'
        AND EffectiveDateTime >= '{a}' AND EffectiveDateTime < '{b}'
        AND DATEDIFF(hour, [Timestamp], EffectiveDateTime) BETWEEN 96 AND 390""", since)
    chunked(cn, 'ieso_wind_fc_long', """SELECT DataSourceName, [Timestamp], EffectiveDateTime, Value, DateCreated
        FROM WindForecast WITH (NOLOCK) WHERE MarketName='IESO' AND DataSourceName IN ('IESO','Meteologica','Frontier')
        AND EffectiveDateTime >= '{a}' AND EffectiveDateTime < '{b}'
        AND DATEDIFF(hour, [Timestamp], EffectiveDateTime) BETWEEN 96 AND 390""", since)
    cn.close()
    c = cfg.get('composition_db') or cfg
    cn, d = P.connect(c, True, 'sandbox'); cur = cn.cursor(); cur.execute("SET statement_timeout = '2400s'")
    say(f'\n=== sandbox horizon ({d}) -- one pass over the Adequacy2 archive ===')
    one(cn, 'ieso_adq2_leads', f"""
        SELECT DISTINCT ON (date, hour, subtype, lead)
               date, hour, resourcetype, subtype, value, ieso_createtime, lead
        FROM (SELECT date, hour, resourcetype, subtype, value, ieso_createtime,
                     (date - ieso_createtime::date) AS lead
              FROM canpower.ieso_adequacy2_all_archive
              WHERE date >= '{since}' AND subtype IN ({HORIZON_SUBTYPES})
                AND ieso_createtime::time < '09:00'
                AND (date - ieso_createtime::date) BETWEEN 2 AND 15) s
        ORDER BY date, hour, subtype, lead, ieso_createtime DESC""")
    cn.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--since', default='2024-06-01'); ap.add_argument('--only')
    a = ap.parse_args()
    cfg, where = P.find_cfg(); say(f'credentials: {where.parent.name}\\db.json   cache -> {CACHE}')
    t0 = time.time()
    if a.only == 'horizon':
        horizon(cfg, a.since if a.since != '2024-06-01' else '2025-05-01')
        say(f'\ndone in {(time.time()-t0)/60:.1f} min. Tell Claude pull_history finished.'); raise SystemExit
    if a.only not in ('adq2', 'adq2x', 'virt', 'outages', 'fwd35', 'quebec_pg'):
        try: mssql(cfg, a.since, a.only)
        except Exception as ex: say(f'  Warehouse step failed: {str(ex)[:300]}')
    if a.only in (None, 'adq2', 'adq2x', 'virt', 'outages', 'fwd35', 'quebec'):
        try: pg(cfg, a.since, a.only)
        except Exception as ex: say(f'  sandbox step failed: {str(ex)[:300]}')
    say(f'\ndone in {(time.time()-t0)/60:.1f} min. Tell Claude pull_history finished.')
