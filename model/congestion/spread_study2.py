"""congestion/spread_study2.py -- Oct 13 2026 (TEST ONLY, nothing wired). Full NRG history May 2025 -> Oct 2026, all 9 zones.
Spread trade buy A / sell B in DA: P&L per MW-h = un = (RT_A-RT_B) - (DA_A-DA_B). Bid-time features only (preDA Adequacy, RT through D-2)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, nrg_import as N, warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
d = pd.read_csv(C.DATA / 'nrg' / 'on_zones_nrg.csv.gz'); d['date'], d['he'] = N.to_key(d.ts_ept_begin)
d = d[d.date.ne('NaT') & d.he.notna()]; d['he'] = d.he.astype(int); d = d.drop_duplicates(['date', 'he'], keep='last')
d = d[(d.date >= '2025-05-03') & (d.date <= '2026-10-12')]
a = C.adq2('preDA')[['date', 'he', 'dem_fc', 'wind_fc', 'solar_fc', 'nuc_out', 'gas_out', 'head']]
d = d.merge(a, on=['date', 'he'], how='left')
m = pd.to_datetime(d.date).dt.month
d['season'] = np.select([m.isin([12, 1, 2]), m.isin([3, 4, 5]), m.isin([6, 7, 8])], ['1 winter', '2 spring', '3 summer'], '4 fall')
d['yr'] = np.where(d.date < '2026-01-01', 'H1: May-Dec25', 'H2: Jan-Oct26')
ZS = ['WEST', 'SW', 'NIAG', 'TOR', 'ESSA', 'NE', 'NW', 'OTT']
def pair(A, B='EAST'):
    x = d[['date', 'he', 'season', 'yr', 'dem_fc', 'wind_fc', 'solar_fc', 'nuc_out', 'gas_out', 'head']].copy()
    x['da'] = d[A + '_DA'] - d[B + '_DA']; x['rt'] = d[A + '_RT'] - d[B + '_RT']; x['un'] = x.rt - x.da
    return x.dropna(subset=['da', 'rt'])
print(f"rows {len(d)}  {d.date.min()} -> {d.date.max()}  days {d.date.nunique()}")
print('\n=== 1. Each zone minus EAST: how big are splits, and does DA already price them? ===')
rows = []
for z in ZS:
    x = pair(z)
    for s, g in x.groupby('season'):
        rows.append(dict(zone=z, season=s, hrs=len(g), rt_mean=g.rt.mean(), rt_absmean=g.rt.abs().mean(), rt_ge5_pct=(g.rt.abs() >= 5).mean() * 100,
                         da_mean=g.da.mean(), da_absmean=g.da.abs().mean(), un_mean=g.un.mean(), un_absmean=g.un.abs().mean(), corr_da_rt=g[['da', 'rt']].corr().iloc[0, 1]))
print(pd.DataFrame(rows).round(2).to_string(index=False))

print('\n=== 2. What drives RT splits vs EAST (mean RT spread / mean unpriced), all seasons ===')
for z in ('WEST', 'SW', 'NIAG', 'NW', 'OTT'):
    x = pair(z); x['dem'] = pd.cut(x.dem_fc, [0, 15000, 17000, 19000, 21000, 30000]); x['wind'] = pd.cut(x.wind_fc, [-1, 1000, 2000, 3000, 9000])
    x['blk'] = pd.cut(x.he, [0, 6, 10, 16, 20, 24], labels=['HE1-6', 'HE7-10', 'HE11-16', 'HE17-20', 'HE21-24'])
    print(f'--- {z} - EAST ---')
    for k in ('dem', 'wind', 'blk'):
        t = x.groupby(k, observed=True).agg(hrs=('un', 'size'), da=('da', 'mean'), rt=('rt', 'mean'), un=('un', 'mean'), rt_abs_ge5=('rt', lambda s: (s.abs() >= 5).mean() * 100))
        print(t.round(2).to_string(), '\n')

print('\n=== 3. Backtests (bid-time only). $/MWh = side x unpriced. H1 = May-Dec 2025, H2 = Jan-Oct 2026 (out of sample check). Fees not deducted. ===')
def rep(t, name):
    v = t[t.side != 0]
    if len(v) < 20: print(f'{name:46s} too few ({len(v)})'); return
    v = v.assign(pl=v.side * v.un); dd = v.groupby('date').pl.sum(); h = v.groupby('yr').pl.agg(['mean', 'size']); s = v.groupby('season').pl.mean()
    print(f'{name:46s} hrs {len(v):5d} $/MWh {v.pl.mean():+6.2f} med {v.pl.median():+6.2f} win {(v.pl>0).mean()*100:3.0f}% days+ {(dd>0).mean()*100:3.0f}% worst day {dd.min():+7.0f} | '
          + ' '.join(f'{i[:2]} {r["mean"]:+6.2f}({int(r["size"])})' for i, r in h.iterrows()) + ' | ' + ' '.join(f'{i[2:5]} {v_:+5.2f}' for i, v_ in s.items()))
def persist(x, look=7, edge=1.0):
    x = x.copy(); x['dt'] = pd.to_datetime(x.date); daily = x.groupby(['dt', 'he']).un.mean().unstack()
    roll = daily.shift(2).rolling(look, min_periods=max(3, look // 2)).mean()   # RT known through D-2 at bid time
    e = roll.stack().rename('edge').reset_index(); x = x.merge(e, on=['dt', 'he'], how='left')
    x['side'] = np.where(x.edge >= edge, 1, np.where(x.edge <= -edge, -1, 0)); return x
for z in ZS:
    x = pair(z)
    print(f'--- {z} - EAST ---')
    for look, edge in ((7, 1.0), (14, 2.0)): rep(persist(x, look, edge), f'persist {look}d edge ${edge:g}')
    x = x.copy(); x['dt'] = pd.to_datetime(x.date); y = x[['dt', 'he', 'da']].copy(); y['dt'] = y.dt + pd.Timedelta(days=1)
    x = x.merge(y.rename(columns={'da': 'da_y'}), on=['dt', 'he'], how='left')   # D-1 DA split, known at bid time (published D-2)
    for q in (5, 10):  # NOTE: today's DA split is NOT known at bid time; yesterday's is
        t = x.copy(); t['side'] = np.where(t.da_y >= q, -1, np.where(t.da_y <= -q, 1, 0)); rep(t, f'fade YESTERDAY DA split >=${q}')
        t = x.copy(); t['side'] = np.where(t.da_y >= q, 1, np.where(t.da_y <= -q, -1, 0)); rep(t, f'follow YESTERDAY DA split >=${q}')
    t = x.copy(); t['side'] = np.where(t.dem_fc >= 19500, 1, 0); rep(t, 'demand>=19.5GW buy zone / sell EAST')
    t = x.copy(); t['side'] = np.where(t.dem_fc >= 19500, -1, 0); rep(t, 'demand>=19.5GW sell zone / buy EAST')
    t = x.copy(); t['side'] = np.where(t.wind_fc >= 2500, -1, 0); rep(t, 'wind>=2500 sell zone / buy EAST')
