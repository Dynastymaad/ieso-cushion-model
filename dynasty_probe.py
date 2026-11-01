"""dynasty_probe.py -- Oct 31 2026. Where does Dynasty's own Ontario load forecast live BEFORE the 08:00 MT bid?
Read-only. Uses the same db.json as pull_history.py (never printed). Run it after Dynasty issues its forecast (~07:30 MT):

    python dynasty_probe.py

It checks:
  1. Warehouse LoadForecast: the newest DYNASTY rows and WHEN they arrived (DateCreated). Today they arrive 04:28 the next day.
  2. Warehouse + sandbox catalogues: every table or column whose name mentions dynasty / ontario / ieso / onzn / load forecast,
     with its newest timestamp, so we can see if any copy of the forecast lands the same morning.
Writes out_dyn/dynasty_probe.txt -- then tell Claude "dynasty probe done"."""
import time
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import ont_probe as P
OUT = Path(__file__).resolve().parent / 'out_dyn'; OUT.mkdir(exist_ok=True); LOG = open(OUT / 'dynasty_probe.txt', 'w', encoding='utf-8')
def say(s=''): print(s, flush=True); LOG.write(str(s) + '\n'); LOG.flush()

def main():
    cfg, where = P.find_cfg(); say(f'credentials file found ({where.parent.name}), not printed')
    tom = (date.today() + timedelta(days=1)).isoformat()
    cn, d = P.connect(cfg, False, 'warehouse')
    say('=== Warehouse: newest DYNASTY rows in LoadForecast ===')
    q = pd.read_sql(f"""SELECT TOP 20 DataSourceName, [Timestamp], MIN(EffectiveDateTime) eff_from, MAX(EffectiveDateTime) eff_to, MAX(DateCreated) arrived, COUNT(*) n
        FROM LoadForecast WITH (NOLOCK) WHERE MarketName='IESO' AND DataSourceName LIKE '%ynasty%' AND [Timestamp] >= '{(date.today() - timedelta(days=4)).isoformat()}'
        GROUP BY DataSourceName, [Timestamp] ORDER BY [Timestamp] DESC""", cn)
    say(q.to_string(index=False))
    say(f'\nRows for tomorrow ({tom}) already in LoadForecast right now:')
    say(pd.read_sql(f"""SELECT DataSourceName, COUNT(*) n, MAX([Timestamp]) issued, MAX(DateCreated) arrived FROM LoadForecast WITH (NOLOCK)
        WHERE MarketName='IESO' AND EffectiveDateTime >= '{tom}' AND EffectiveDateTime < '{(date.today() + timedelta(days=2)).isoformat()}' GROUP BY DataSourceName""", cn).to_string(index=False))
    say('\n=== Warehouse catalogue: tables / columns mentioning dynasty, ontario, ieso, onzn, load forecast ===')
    t = pd.read_sql("""SELECT s.name sch, t.name tbl, c.name col FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.columns c ON c.object_id=t.object_id
        WHERE t.name LIKE '%ynasty%' OR t.name LIKE '%ntario%' OR t.name LIKE '%IESO%' OR t.name LIKE '%LoadF%' OR c.name LIKE '%ynasty%'""", cn)
    say(t.groupby(['sch', 'tbl']).col.apply(lambda s: ', '.join(s[:12])).to_string()); cn.close()
    c = cfg.get('composition_db') or cfg
    try:
        cn, d = P.connect(c, True, 'sandbox')
        say('\n=== sandbox catalogue: tables mentioning dynasty / ontario / ieso / onzn / load ===')
        t = pd.read_sql("""SELECT table_schema, table_name, string_agg(column_name, ', ') cols FROM information_schema.columns
            WHERE table_name ~* '(dynasty|ontario|ieso|onzn|load_?f|loadfc|lf_)' OR column_name ~* 'dynasty' GROUP BY 1,2 ORDER BY 1,2""", cn)
        say(t.to_string(index=False)); cn.close()
    except Exception as ex: say(f'sandbox step failed: {str(ex)[:200]}')
    say('\nDone. Tell Claude "dynasty probe done".')

if __name__ == '__main__':
    main()
