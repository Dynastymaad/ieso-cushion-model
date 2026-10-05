r"""
ont_probe.py -- LIGHT discovery of Ontario/IESO data in both databases.

Every query is catalog-only, TOP-N, TABLESAMPLE or index-filtered. Nothing
scans a big table. Each query has a 25-second timeout; anything slow is
skipped and logged, never retried.

Run it from this folder in PowerShell:
    cd "$HOME\OneDrive - Dynasty Power\Desktop\Ontario-Cushion Model"
    python ont_probe.py

Credentials: uses db.json in THIS folder if you put one here, otherwise it
READS (never writes) Documents\aeso-cushion model\db.json. Needs pyodbc and
pandas (already installed for the Alberta model).

Output: out\*.csv and out\_summary.txt in this folder. No credentials are
written anywhere.
"""
import json, sys, time, traceback
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out'; OUT.mkdir(exist_ok=True)
LOG = None   # opened in __main__ so importing this file never overwrites a summary
TIMEOUT = 25


def _cfg_candidates():
    import os, glob
    h = Path.home(); out = []
    if os.environ.get('ONT_DB_JSON'): out.append(Path(os.environ['ONT_DB_JSON']))
    out += [HERE / 'db.json', HERE.parent / 'aeso-cushion model' / 'db.json', h / 'Documents' / 'aeso-cushion model' / 'db.json']
    for od in [os.environ.get('OneDriveCommercial'), os.environ.get('OneDrive')] + glob.glob(str(h / 'OneDrive*')):
        if od: out += [Path(od) / 'Documents' / 'aeso-cushion model' / 'db.json', Path(od) / 'Desktop' / 'aeso-cushion model' / 'db.json']
    out.append(h / 'Desktop' / 'aeso-cushion model' / 'db.json')
    return out


def find_cfg():
    tried = _cfg_candidates()
    for p in tried:
        if p.exists():
            return json.loads(p.read_text()), p
    raise SystemExit('db.json not found. Looked in:\n  ' + '\n  '.join(dict.fromkeys(str(p) for p in tried)) +
                     '\nFix: put db.json in one of these, or set ONT_DB_JSON to its full path.')


def _q(v):
    # SQL Server: always brace-quote (a ';' in a password would truncate it)
    return '{' + str(v).replace('}', '}}') + '}'


def _qpg(v):
    # psqlODBC passes braces through literally, so Postgres values go in raw
    return str(v)


def conn_str(c, pg, driver, trust=True):
    if pg:
        if c.get('dsn'):
            return f"DSN={c['dsn']};UID={_qpg(c.get('username',''))};PWD={_qpg(c.get('password',''))};"
        p = [f"DRIVER={{{driver}}}", f"SERVER={c['server']}", f"PORT={c.get('port', 5432)}",
             f"DATABASE={c['database']}", f"UID={_qpg(c.get('username',''))}",
             f"PWD={_qpg(c.get('password',''))}", f"SSLmode={c.get('sslmode','require')}"]
    else:
        p = [f"DRIVER={{{driver}}}", f"SERVER={c['server']}", f"DATABASE={c['database']}"]
        if c.get('trusted_connection'): p.append('Trusted_Connection=yes')
        else: p += [f"UID={_q(c['username'])}", f"PWD={_q(c['password'])}"]
        if trust: p.append('TrustServerCertificate=yes')
    if c.get('odbc_extra'): p.append(str(c['odbc_extra']).strip(';'))
    return ';'.join(p) + ';'


def connect(c, pg, label):
    import pyodbc
    drv = pyodbc.drivers()
    fam = [d for d in drv if ('PostgreSQL' in d if pg else 'SQL Server' in d)]
    want = c.get('driver', '')
    cands = ([want] if want in drv else []) + [d for d in fam if d != want]
    errs = []
    for d in cands:
        for trust in ((True,) if pg else (True, False)):
            try:
                return pyodbc.connect(conn_str(c, pg, d, trust), timeout=30), d
            except Exception as ex:
                errs.append(f'{d}: {str(ex)[:150]}')
    raise SystemExit(f'{label}: could not connect -> ' + ' | '.join(errs))


def log(s=''):
    print(s, flush=True)
    if LOG: LOG.write(s + '\n'); LOG.flush()

def run(cn, name, sql, params=None, pg=False):
    t0 = time.time()
    try:
        if pg:
            cur = cn.cursor(); cur.execute(f"SET statement_timeout = '{TIMEOUT}s'")
        df = pd.read_sql(sql, cn, params=params)
        df.to_csv(OUT / f'{name}.csv', index=False)
        log(f'  OK   {name:<42} {len(df):>7} rows  {time.time()-t0:5.1f}s')
        return df
    except Exception as ex:
        msg = str(ex).replace('\n', ' ')[:160]
        log(f'  SKIP {name:<42} {time.time()-t0:5.1f}s  {msg}')
        try: cn.rollback()
        except Exception: pass
        return None

CANDIDATE_MARKETS = ['IESO', 'Ontario', 'ONTARIO', 'ON', 'IESO-ON', 'ONT', 'IESO_ON']

# ------------------------------------------------------------------ SQL Server
def probe_mssql(cfg):
    log('\n=== SQL Server / Warehouse ===')
    cn, d = connect(cfg, False, 'warehouse'); cn.timeout = TIMEOUT
    log(f'  connected with {d}')

    # 1. every table with its row count, from catalog stats (no scan)
    run(cn, 'ms_01_tables_rowcounts', """
        SELECT s.name AS schema_name, t.name AS table_name, SUM(p.rows) AS rows_
        FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
        JOIN sys.partitions p ON p.object_id=t.object_id AND p.index_id IN (0,1)
        GROUP BY s.name, t.name ORDER BY t.name""")

    # 2. column lists for every table (catalog only)
    run(cn, 'ms_02_columns', """
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.COLUMNS ORDER BY TABLE_NAME, ORDINAL_POSITION""")

    # 3. indexes on the big tables -> tells us which filters are cheap
    run(cn, 'ms_03_indexes', """
        SELECT t.name AS table_name, i.name AS index_name, i.type_desc,
               STRING_AGG(c.name, ',') WITHIN GROUP (ORDER BY ic.key_ordinal) AS key_cols
        FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id
        JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.is_included_column=0
        JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
        WHERE t.name IN ('LoadForecast','LoadActualHourly','WindForecast','SolarForecast',
                         'WeatherHourly','WeatherHourlyForecast','ForwardPrices','PriceForwardDaily',
                         'GenerationOutages','IIRPlantOutage','IIRPlantUnits','ExchangeRate')
        GROUP BY t.name, i.name, i.type_desc ORDER BY 1,2""")

    # 4. which markets live in the vintage / actual tables: small page sample
    for t in ['LoadForecast', 'LoadActualHourly', 'WindForecast', 'SolarForecast']:
        run(cn, f'ms_04_markets_sample_{t}', f"""
            SELECT MarketName, COUNT(*) AS rows_in_sample
            FROM {t} TABLESAMPLE (3000 PAGES) WITH (NOLOCK)
            GROUP BY MarketName ORDER BY 2 DESC""")

    # 5. direct hit test for Ontario market names, index-friendly, last 3 days
    for t in ['LoadForecast', 'WindForecast', 'SolarForecast', 'LoadActualHourly']:
        tcol = 'EffectiveDateTime' if t != 'LoadActualHourly' else None
        for m in CANDIDATE_MARKETS:
            where = f"MarketName = '{m}'" + (f" AND {tcol} >= DATEADD(day,-3,GETDATE())" if tcol else '')
            df = run(cn, f'ms_05_{t}_{m}', f"SELECT TOP 20 * FROM {t} WITH (NOLOCK) WHERE {where}")
            if df is not None and len(df): break

    # 6. small reference tables: dump whole (all < 1 MB on disk)
    for t in ['WeatherHourlyStation', 'EiaGasRegions', 'GenerationOutageCategory', 'UsStates']:
        run(cn, f'ms_06_{t}', f"SELECT * FROM {t} WITH (NOLOCK)")

    # 7. five sample rows from every table that might matter (no ORDER BY = no scan)
    for t in ['LoadForecast','LoadActualHourly','WindForecast','SolarForecast','WeatherHourly',
              'WeatherHourlyForecast','WeatherHourlyNormals','ExchangeRate','GenerationOutages',
              'IIRPlantOutage','IIRPlantUnits','PriceForwardDaily','PriceForwardMonthly',
              'PjmWestHubDaPrices','HydroQuebecDemand','IceDaNaturalGasReport','IceIndices',
              'PlattsGasPrices','UnionGasStorage','GenscapePriceForecasts','FrontierWindForecasts']:
        run(cn, f'ms_07_sample_{t}', f"SELECT TOP 5 * FROM {t} WITH (NOLOCK)")

    # 8. Ontario forward products: definitions (index on ExchangeCode+EffectiveDate assumed; worked for XCU)
    run(cn, 'ms_08_forward_ontario_defs', """
        SELECT TOP 60 * FROM Warehouse.dbo.ForwardPrices WITH (NOLOCK)
        WHERE ExchangeCode IN ('XDE','XDG','XDY','CVX','ADP','PDA')
          AND EffectiveDate >= DATEADD(day,-4,GETDATE())""")
    cn.close()

# ------------------------------------------------------------------ Postgres
def probe_pg(cfg):
    log('\n=== PostgreSQL / sandbox ===')
    c = cfg.get('composition_db') or cfg
    cn, d = connect(c, True, 'sandbox')
    log(f'  connected with {d}')
    tabs = run(cn, 'pg_01_tables', """
        SELECT n.nspname AS schema, c.relname AS table_name, c.relkind,
               c.reltuples::bigint AS est_rows
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE c.relkind IN ('r','p','v','m','f')
          AND n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')
        ORDER BY 1,2""", pg=True)
    run(cn, 'pg_02_columns', """
        SELECT table_schema, table_name, column_name, data_type, ordinal_position
        FROM information_schema.columns
        WHERE table_schema NOT IN ('pg_catalog','information_schema')
        ORDER BY 1,2,5""", pg=True)
    if tabs is not None:
        key = ('ieso','ontario','ont_','ont','canpower','nyiso','weather','gas')
        pick = tabs[tabs.apply(lambda r: r['schema'] in ('canpower','nyiso','weather','gas','congestion')
                               or any(k in r['table_name'].lower() for k in ('ieso','ontario','ont_')), axis=1)]
        for _, r in pick.head(80).iterrows():
            fq = f'"{r["schema"]}"."{r["table_name"]}"'
            run(cn, f'pg_03_sample_{r["schema"]}_{r["table_name"]}'[:120], f'SELECT * FROM {fq} LIMIT 5', pg=True)
    cn.close()

if __name__ == '__main__':
    LOG = open(OUT / '_summary.txt', 'w', encoding='utf-8')
    cfg, where = find_cfg(); log(f'using credentials from {where.parent.name}\\db.json')
    for f in (probe_mssql, probe_pg):
        try: f(cfg)
        except SystemExit as ex: log(f'  {f.__name__} could not connect: {ex}')
        except Exception: log(traceback.format_exc()[-600:])
    log('\nDone. Tell Claude the probe finished; it reads the out folder directly.')
    LOG.close()
