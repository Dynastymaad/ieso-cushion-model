"""tesla_check.py -- why is today's Tesla load forecast missing?  Read-only, a few small queries.
    python -X utf8 tesla_check.py
Prints what the warehouse holds for Tesla (any market / node / name spelling) over the last 4 days."""
import pandas as pd, warnings
warnings.filterwarnings('ignore')
import ont_probe as P
cfg, where = P.find_cfg(); cn, d = P.connect(cfg, False, 'warehouse'); cn.timeout = 300
q = lambda s: pd.read_sql(s, cn)
pd.set_option('display.width', 200); pd.set_option('display.max_rows', 200)

print('\n1) Every load source for IESO/ONZN, newest load and newest issue time (last 4 days of loads):')
print(q("""SELECT DataSourceName, COUNT(*) n, MAX(DateCreated) last_loaded, MAX([Timestamp]) last_issued, MAX(EffectiveDateTime) furthest_hour
           FROM LoadForecast WITH (NOLOCK) WHERE MarketName='IESO' AND NodeName='ONZN' AND DateCreated >= DATEADD(day,-4,GETDATE())
           GROUP BY DataSourceName ORDER BY DataSourceName""").to_string(index=False))

print('\n2) Any Tesla rows anywhere in LoadForecast loaded in the last 4 days (any market / node / spelling):')
print(q("""SELECT DataSourceName, MarketName, NodeName, COUNT(*) n, MAX(DateCreated) last_loaded, MAX([Timestamp]) last_issued
           FROM LoadForecast WITH (NOLOCK) WHERE DateCreated >= DATEADD(day,-4,GETDATE()) AND DataSourceName LIKE '%esla%'
           GROUP BY DataSourceName, MarketName, NodeName ORDER BY last_loaded DESC""").to_string(index=False))

print('\n3) Tesla for IESO by load batch (DateCreated) over the last 6 days:')
print(q("""SELECT CAST(DateCreated AS date) load_day, MIN(DateCreated) first_load, MAX(DateCreated) last_load, MAX([Timestamp]) last_issued, COUNT(*) n
           FROM LoadForecast WITH (NOLOCK) WHERE MarketName='IESO' AND DataSourceName LIKE '%esla%' AND DateCreated >= DATEADD(day,-6,GETDATE())
           GROUP BY CAST(DateCreated AS date) ORDER BY load_day""").to_string(index=False))

print('\n4) Newest load of ANY source into LoadForecast (is the whole table stale?):')
print(q("SELECT TOP 8 DataSourceName, MarketName, MAX(DateCreated) last_loaded FROM LoadForecast WITH (NOLOCK) WHERE DateCreated >= DATEADD(day,-3,GETDATE()) GROUP BY DataSourceName, MarketName ORDER BY last_loaded DESC").to_string(index=False))
print('\nwarehouse clock now:', q("SELECT GETDATE() now").iloc[0,0])
print('\nDone. Copy everything above to Claude.')
