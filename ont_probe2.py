"""
ont_probe2.py -- second LIGHT probe, now that probe 1 found the Ontario data.

Same rules: filtered on indexed columns or small tables only, 25-second cap
per query, slow ones are skipped. Run from this folder:
    python ont_probe2.py
Writes out2\\*.csv and out2\\_summary.txt.
"""
import ont_probe as P
from pathlib import Path

P.OUT = P.HERE / 'out2'; P.OUT.mkdir(exist_ok=True)
P.LOG = open(P.OUT / '_summary.txt', 'w', encoding='utf-8')
run, log = P.run, P.log

def mssql(cfg):
    log('\n=== SQL Server / Warehouse ===')
    cn, d = P.connect(cfg, False, 'warehouse'); cn.timeout = P.TIMEOUT
    # indexes (no STRING_AGG on this server version)
    run(cn, 'a01_indexes', """
        SELECT t.name AS table_name, i.name AS index_name, i.type_desc, ic.key_ordinal, c.name AS col
        FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id
        JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
        JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
        WHERE t.name IN ('LoadForecast','WindForecast','SolarForecast','LoadActualHourly',
                         'WeatherHourly','WeatherHourlyForecast','ForwardPrices','IceIndices')
        ORDER BY 1,2,4""")
    # which vendors forecast Ontario, last 2 days of targets
    run(cn, 'a02_load_sources', """SELECT DataSourceName, NodeName, COUNT(*) AS n, MIN([Timestamp]) AS first_issue,
        MAX([Timestamp]) AS last_issue FROM LoadForecast WITH (NOLOCK)
        WHERE MarketName='IESO' AND EffectiveDateTime >= DATEADD(day,-2,GETDATE()) GROUP BY DataSourceName, NodeName""")
    run(cn, 'a03_wind_sources', """SELECT DataSourceName, NodeName, COUNT(*) AS n FROM WindForecast WITH (NOLOCK)
        WHERE MarketName='IESO' AND EffectiveDateTime >= DATEADD(day,-2,GETDATE()) GROUP BY DataSourceName, NodeName""")
    run(cn, 'a04_solar_sources', """SELECT DataSourceName, COUNT(*) AS n FROM SolarForecast WITH (NOLOCK)
        WHERE MarketName='IESO' AND EffectiveDateTime >= DATEADD(day,-2,GETDATE()) GROUP BY DataSourceName""")
    # every vintage for ONE target hour -> issue cadence + time-zone check
    run(cn, 'a05_load_vintages_one_hour', """SELECT DataSourceName, [Timestamp], EffectiveDateTime, EffectiveDateTimeUtc, Load
        FROM LoadForecast WITH (NOLOCK) WHERE MarketName='IESO'
        AND EffectiveDateTime >= '2026-09-23 16:00' AND EffectiveDateTime < '2026-09-23 19:00'
        ORDER BY DataSourceName, EffectiveDateTime, [Timestamp]""")
    run(cn, 'a06_wind_vintages_one_hour', """SELECT DataSourceName, [Timestamp], EffectiveDateTime, Value
        FROM WindForecast WITH (NOLOCK) WHERE MarketName='IESO'
        AND EffectiveDateTime >= '2026-09-23 16:00' AND EffectiveDateTime < '2026-09-23 19:00'
        ORDER BY DataSourceName, EffectiveDateTime, [Timestamp]""")
    # how far back: spot-check a few target days per source
    for day in ['2024-06-15', '2025-01-15', '2025-05-15', '2025-09-15', '2026-03-15']:
        run(cn, f'a07_load_history_{day}', f"""SELECT DataSourceName, COUNT(*) AS n FROM LoadForecast WITH (NOLOCK)
            WHERE MarketName='IESO' AND EffectiveDateTime >= '{day} 00:00' AND EffectiveDateTime < '{day} 01:00'
            GROUP BY DataSourceName""")
        run(cn, f'a08_wind_history_{day}', f"""SELECT DataSourceName, COUNT(*) AS n FROM WindForecast WITH (NOLOCK)
            WHERE MarketName='IESO' AND EffectiveDateTime >= '{day} 00:00' AND EffectiveDateTime < '{day} 01:00'
            GROUP BY DataSourceName""")
    run(cn, 'a09_loadactual_markets', """SELECT Market, NodeName, COUNT(*) AS n FROM LoadActualHourly WITH (NOLOCK)
        WHERE EffectiveDateTime >= DATEADD(day,-2,GETDATE()) GROUP BY Market, NodeName""")
    # Toronto weather: vendors + a few rows
    run(cn, 'a10_cyyz_fcst_sources', """SELECT DataSourceName, Description, COUNT(*) AS n,
        MIN(ObservationDateTime) AS first_obs, MAX(ObservationDateTime) AS last_obs FROM WeatherHourlyForecast WITH (NOLOCK)
        WHERE WeatherStationId='CYYZ' AND EffectiveDateTime >= DATEADD(day,-1,GETDATE()) GROUP BY DataSourceName, Description""")
    run(cn, 'a11_cyyz_actual_recent', """SELECT TOP 48 * FROM WeatherHourly WITH (NOLOCK)
        WHERE WeatherStationId='CYYZ' AND EffectiveDateTime >= DATEADD(day,-3,GETDATE()) ORDER BY EffectiveDateTime DESC""")
    # small tables: filter in full
    run(cn, 'a12_iir_units_ontario', """SELECT * FROM IIRPlantUnits WITH (NOLOCK)
        WHERE CTRLAREA IN ('IESO','ONT','ON','ONTARIO','IMO')""")
    run(cn, 'a13_ctrlareas', "SELECT CTRLAREA, COUNT(*) AS n FROM IIRPlantUnits WITH (NOLOCK) GROUP BY CTRLAREA")
    run(cn, 'a14_ice_ontario', """SELECT ExternalId, COUNT(*) AS n, MIN(TradeDate) AS first_, MAX(TradeDate) AS last_
        FROM IceIndices WITH (NOLOCK) GROUP BY ExternalId""")
    run(cn, 'a15_fx_tickers', "SELECT Ticker, COUNT(*) AS n, MIN([Date]) AS first_, MAX([Date]) AS last_ FROM ExchangeRate GROUP BY Ticker")
    cn.close()

def pg(cfg):
    log('\n=== PostgreSQL / sandbox ===')
    c = cfg.get('composition_db') or cfg
    cn, d = P.connect(c, True, 'sandbox')
    run(cn, 'b01_indexes', """SELECT schemaname, tablename, indexname, indexdef FROM pg_indexes
        WHERE schemaname IN ('canpower','weather') AND (tablename LIKE 'ieso%%' OR tablename LIKE 'stormvista%%'
        OR tablename='weather_stations')""", pg=True)
    # Adequacy2 archive: subtypes + vintages for ONE delivery date (only fast if date is indexed)
    run(cn, 'b02_adq2_subtypes_one_day', """SELECT resourcetype, subtype, unit, COUNT(*) AS n,
        COUNT(DISTINCT ieso_createtime) AS vintages FROM canpower.ieso_adequacy2_all_archive
        WHERE date = '2026-09-20' GROUP BY 1,2,3 ORDER BY 1,2""", pg=True)
    run(cn, 'b03_adq2_vintage_times_one_day', """SELECT DISTINCT ieso_createtime, version, create_time
        FROM canpower.ieso_adequacy2_all_archive WHERE date = '2026-09-20' ORDER BY 1""", pg=True)
    run(cn, 'b04_adq2_first_date', """SELECT date FROM canpower.ieso_adequacy2_all_archive ORDER BY date ASC LIMIT 1""", pg=True)
    run(cn, 'b05_adq2_last_date', """SELECT date, ieso_createtime FROM canpower.ieso_adequacy2_all_archive ORDER BY date DESC LIMIT 1""", pg=True)
    run(cn, 'b06_adq2small_subtypes', """SELECT resourcetype, subtype, COUNT(*) AS n, MIN(date) AS first_, MAX(date) AS last_
        FROM canpower.ieso_adequacy2_archive GROUP BY 1,2 ORDER BY 1,2""", pg=True)
    # small tables: full dumps
    run(cn, 'b07_dynasty_virtuals_all', "SELECT * FROM canpower.ieso_dynasty_virtual_transactions", pg=True)
    run(cn, 'b08_market_virtuals_all', "SELECT * FROM canpower.ieso_virtual_transactions", pg=True)
    run(cn, 'b09_intertie_lmp_types', """SELECT report_type, intertie_name, COUNT(*) AS n, MIN(delivery_date) AS first_,
        MAX(delivery_date) AS last_ FROM canpower.ieso_da_hourly_intertie_lmp GROUP BY 1,2""", pg=True)
    run(cn, 'b10_weather_stations', "SELECT * FROM weather.weather_stations", pg=True)
    run(cn, 'b11_stormvista_temp_sample', "SELECT * FROM weather.stormvista_temp_fcst LIMIT 5", pg=True)
    cn.close()

if __name__ == '__main__':
    cfg, where = P.find_cfg(); log(f'using credentials from {where.parent.name}\\db.json')
    for f in (mssql, pg):
        try: f(cfg)
        except SystemExit as ex: log(f'  {f.__name__} could not connect: {ex}')
        except Exception: import traceback; log(traceback.format_exc()[-600:])
    log('\nDone. Tell Claude probe 2 finished.')
    P.LOG.close()
