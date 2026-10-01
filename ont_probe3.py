"""
ont_probe3.py -- LIGHT probe #3: find the historical IESO data (the "datamart").

Catalog queries only (sys.databases, INFORMATION_SCHEMA, pg_catalog) plus a few
TOP-N / MIN-MAX lookups on small tables. 25-second cap per query; slow ones are
skipped. Nothing is written to any database. Run from this folder:
    python ont_probe3.py
Writes out3\\*.csv and out3\\_summary.txt.

It probes the two connections already in db.json, every OTHER database on those
servers that your login can open, and any extra connection block you add to
db.json with a "server" key (for example "datamart_db": {...} in the same shape as
composition_db). Credentials never leave db.json.
"""
import ont_probe as P, copy, re, warnings
import pandas as pd
warnings.filterwarnings('ignore', message='pandas only supports SQLAlchemy')

def truthy(s):
    """ODBC drivers return booleans as 1/0, '1'/'0', 't'/'f' or True/False -- normalise."""
    return s.astype(str).str.strip().str.lower().isin(['1', 't', 'true', 'yes'])

P.OUT = P.HERE / 'out3'; P.OUT.mkdir(exist_ok=True)
P.LOG = open(P.OUT / '_summary.txt', 'w', encoding='utf-8')
run, log = P.run, P.log
PAT = r'ieso|ontario|^ont|onzn|nrg|stream|storm|meteo|skynet|nyiso|intertie|adequacy|zonal|hoep|ozp|vgforecast|predisp|genoutput|sbg|outage|hydro|demand|virtual|hub|lmp|price'
KEEP = re.compile(PAT, re.I)

def ms_db(cfg, db):
    c = copy.deepcopy(cfg); c['database'] = db
    try:
        cn, _ = P.connect(c, False, db); cn.timeout = P.TIMEOUT
    except (SystemExit, Exception) as ex:
        log(f'  SKIP connect {db}: {str(ex)[:120]}'); return
    t = run(cn, f'ms_{db}_tables', """SELECT s.name AS schema_name, t.name AS table_name, t.type_desc,
        SUM(p.rows) AS rows_ FROM sys.objects t JOIN sys.schemas s ON s.schema_id=t.schema_id
        LEFT JOIN sys.partitions p ON p.object_id=t.object_id AND p.index_id IN (0,1)
        WHERE t.type IN ('U','V') GROUP BY s.name, t.name, t.type_desc ORDER BY 1,2""")
    if t is None or not len(t): return
    hit = t[t.table_name.str.contains(KEEP)]
    log(f'    {db}: {len(t)} tables/views, {len(hit)} match Ontario/IESO/NRG/StormVista patterns')
    if len(hit):
        run(cn, f'ms_{db}_columns_hits', """SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME IN (""" + ','.join("'" + x.replace("'", "''") + "'" for x in hit.table_name[:300]) + ') ORDER BY 1,2,5')
        for _, r in hit.head(60).iterrows():
            run(cn, f'ms_{db}_sample_{r.schema_name}_{r.table_name}'[:120], f'SELECT TOP 5 * FROM [{r.schema_name}].[{r.table_name}] WITH (NOLOCK)')

def mssql(cfg, label):
    log(f'\n=== SQL Server: {label} ===')
    cn, d = P.connect(cfg, False, label); cn.timeout = P.TIMEOUT; log(f'  connected with {d}')
    dbs = run(cn, f'ms_{label}_databases', """SELECT name, database_id, state_desc, HAS_DBACCESS(name) AS has_access,
        create_date FROM sys.databases ORDER BY name""")
    run(cn, f'ms_{label}_version', "SELECT @@VERSION AS v")
    # IESO vendor coverage in the Warehouse forecast tables (small TOP-1 lookups on the index)
    if cfg.get('database', '').lower() == 'warehouse':
        for tbl in ['LoadForecast', 'WindForecast', 'SolarForecast']:
            run(cn, f'ms_{tbl}_ieso_first', f"""SELECT TOP 1 EffectiveDateTime FROM {tbl} WITH (NOLOCK)
                WHERE MarketName='IESO' ORDER BY EffectiveDateTime""")
        run(cn, 'ms_weather_stations', "SELECT * FROM WeatherHourlyStation WITH (NOLOCK)")
    if dbs is None: return
    for db in dbs[truthy(dbs.has_access) & ~dbs.name.isin(['master', 'tempdb', 'model', 'msdb'])].name:
        ms_db(cfg, db)

def pg(cfg, label):
    log(f'\n=== PostgreSQL: {label} ===')
    cn, d = P.connect(cfg, True, label); log(f'  connected with {d}')
    dbs = run(cn, f'pg_{label}_databases', """SELECT datname, has_database_privilege(datname,'CONNECT') AS can_connect
        FROM pg_database WHERE NOT datistemplate ORDER BY 1""", pg=True)
    run(cn, f'pg_{label}_schemas', """SELECT nspname, has_schema_privilege(nspname,'USAGE') AS usage
        FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema' ORDER BY 1""", pg=True)
    # columns of the StormVista / weather tables (catalog is readable even without SELECT on the schema)
    run(cn, f'pg_{label}_weather_columns', """SELECT c.relname AS table_name, a.attname AS column_name, format_type(a.atttypid,a.atttypmod) AS type
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='weather' AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1, a.attnum""", pg=True)
    run(cn, f'pg_{label}_table_privs', """SELECT n.nspname, c.relname, has_table_privilege(c.oid,'SELECT') AS can_select, c.reltuples::bigint AS est_rows
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind IN ('r','v','m','p')
        AND (n.nspname IN ('weather','skynet','nyiso','canpower') OR c.relname ~* 'ieso|ontario|stormvista|meteo|nrg|skynet|nyiso')
        ORDER BY 1,2""", pg=True)
    if cfg.get('database') == 'sandbox':
        run(cn, 'pg_nyiso_tables_cols', """SELECT table_name, column_name, data_type FROM information_schema.columns
            WHERE table_schema IN ('nyiso','skynet') ORDER BY 1, ordinal_position""", pg=True)
        run(cn, 'pg_virtuals_span', """SELECT MIN(deliverydate) AS first_, MAX(deliverydate) AS last_, COUNT(*) AS n FROM canpower.ieso_virtual_transactions""", pg=True)
        run(cn, 'pg_adq2_subtypes_all', """SELECT resourcetype, subtype, COUNT(*) AS n FROM canpower.ieso_adequacy2_all_archive
            WHERE date = '2026-09-20' GROUP BY 1,2 ORDER BY 1,2""", pg=True)
    if dbs is None: return
    for db in dbs[truthy(dbs.can_connect) & ~dbs.datname.isin([cfg.get('database'), 'rdsadmin'])].datname:
        c = copy.deepcopy(cfg); c['database'] = db; c.pop('dsn', None)
        try:
            cn2, _ = P.connect(c, True, db)
        except (SystemExit, Exception) as ex:
            log(f'  SKIP connect {db}: {str(ex)[:120]}'); continue
        t = run(cn2, f'pg_db_{db}_tables', """SELECT n.nspname AS schema, c.relname AS table_name, c.relkind, c.reltuples::bigint AS est_rows,
            has_table_privilege(c.oid,'SELECT') AS can_select FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relkind IN ('r','v','m','p') AND n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2""", pg=True)
        if t is not None and len(t):
            hit = t[t.table_name.str.contains(KEEP) | t.schema.str.contains(KEEP)]
            log(f'    {db}: {len(t)} tables, {len(hit)} match')
            for _, r in hit[truthy(hit.can_select)].head(40).iterrows():
                run(cn2, f'pg_db_{db}_sample_{r.schema}_{r.table_name}'[:120], f'SELECT * FROM "{r.schema}"."{r.table_name}" LIMIT 5', pg=True)

if __name__ == '__main__':
    cfg, path = P.find_cfg(); log(f'using credentials from {path}')
    try: mssql(cfg, 'warehouse')
    except (SystemExit, Exception) as ex: log(f'  SQL Server failed: {str(ex)[:300]}')
    comp = cfg.get('composition_db')
    if comp:
        base = {k: v for k, v in cfg.items() if not isinstance(v, dict)}; c = {**base, **comp}
        try: pg(c, 'sandbox')
        except (SystemExit, Exception) as ex: log(f'  Postgres failed: {str(ex)[:300]}')
    for k, v in cfg.items():                       # any extra connection block, e.g. "datamart_db"
        if isinstance(v, dict) and k != 'composition_db' and v.get('server'):
            base = {kk: vv for kk, vv in cfg.items() if not isinstance(vv, dict)}; c = {**base, **v}
            try:
                (pg if str(v.get('dialect', '')).startswith('postgres') else mssql)(c, re.sub(r'\W', '_', k))
            except (SystemExit, Exception) as ex: log(f'  {k} failed: {str(ex)[:300]}')
    log('\nDone. Tell Claude probe 3 finished.')
