"""congestion/spread_study.py -- Oct 13 2026 (TEST ONLY). Zone spreads: what drives them, and can bid-time info trade the unpriced part.
un = (RT_A - RT_B) - (DA_A - DA_B) = P&L per MW of buying A / selling B in DA. Bid-time features only (preDA Adequacy, D-2 prices)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width', 220)
p = pd.read_csv(C.DATA / 'prices_hourly.csv'); p = p[p.date >= '2026-06-27']
w = p.pivot_table(index=['date', 'he'], columns='zone', values=['da', 'rt'])
a = C.adq2('preDA')[['date', 'he', 'dem_fc', 'wind_fc', 'solar_fc', 'head', 'nuc_out', 'gas_out']]
ZS = ['WEST', 'SOUTHWEST', 'NIAGARA', 'TORONTO', 'ESSA', 'EAST', 'OTTAWA', 'NORTHEAST', 'NORTHWEST']
def pair(A, B):
    x = pd.DataFrame({'da': w['da'][A] - w['da'][B], 'rt': w['rt'][A] - w['rt'][B]}).dropna().reset_index()
    x['un'] = x.rt - x.da; return x.merge(a, on=['date', 'he'], how='left')
print('=== 1. Size of the opportunity: |unpriced| by zone vs ONTARIO, Jun 27 - Oct 12 ===')
rows = []
for z in ZS:
    x = pair(z, 'ONTARIO'); x = x[x.date <= '2026-10-12']
    rows.append(dict(zone=z, hrs=len(x), mean_un=x.un.mean(), mean_abs_un=x.un.abs().mean(), p95_abs=x.un.abs().quantile(.95),
                     hrs_abs_ge5=(x.un.abs() >= 5).mean() * 100, mean_rt=x.rt.mean(), mean_da=x.da.mean(), corr_da_rt=x[['da', 'rt']].corr().iloc[0, 1]))
print(pd.DataFrame(rows).round(2).to_string(index=False))
x = pair('WEST', 'EAST'); x = x[x.date <= '2026-10-12']; x['mon'] = x.date.str[:7]
print('\n=== 2. West - East by month (unpriced = RT spread - DA spread) ===')
print(x.groupby('mon').agg(hrs=('un', 'size'), da=('da', 'mean'), rt=('rt', 'mean'), un=('un', 'mean'), abs_un=('un', lambda s: s.abs().mean()), big=('rt', lambda s: (s.abs() >= 5).sum())).round(2).to_string())
print('\n=== 3. Fundamentals (bid-time IESO preDA) vs West - East, all hours ===')
x['wb'] = pd.cut(x.wind_fc, [0, 1000, 2000, 3000, 9000]); x['hb'] = pd.cut(x.he, [0, 6, 10, 16, 20, 24])
x['db'] = pd.qcut(x.dem_fc, 4); x['era'] = np.where(x.date >= '2026-10-04', 'Oct4+ (outages)', 'before Oct 4')
for k in ('wb', 'hb', 'db'):
    print(x.groupby(['era', k], observed=True).agg(hrs=('un', 'size'), da=('da', 'mean'), rt=('rt', 'mean'), un=('un', 'mean')).round(2).unstack('era').to_string(), '\n')
x.to_csv(C.DATA / 'congestion' / 'west_east.csv', index=False)

print('\n=== 4. Backtests, bid-time only. P&L per MW per hour = side x unpriced. Fills assumed (price-taker legs both sides). ===')
def persist(x, look=7, edge=1.0, by='he'):
    x = x.sort_values(['date', 'he']).copy(); days = sorted(x.date.unique()); out = []
    for i, D in enumerate(days):
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).strftime('%Y-%m-%d'); lo = (pd.Timestamp(D) - pd.Timedelta(days=look + 1)).strftime('%Y-%m-%d')
        h = x[(x.date <= c2) & (x.date >= lo)]
        if h.date.nunique() < max(3, look // 2): continue
        m = h.groupby(by).un.mean(); t = x[x.date == D].copy(); t['edge'] = t[by].map(m); out.append(t)
    t = pd.concat(out); t['side'] = np.where(t.edge >= edge, 1, np.where(t.edge <= -edge, -1, 0)); t['pl'] = t.side * t.un
    return t
def report(t, name):
    v = t[t.side != 0]
    if not len(v): print(f'{name:42s} no trades'); return
    d = v.groupby('date').pl.sum(); h1 = v[v.date < '2026-09-01'].pl; h2 = v[v.date >= '2026-09-01'].pl
    print(f'{name:42s} hrs {len(v):5d} | $/MWh {v.pl.mean():+6.2f} median {v.pl.median():+6.2f} win {(v.pl>0).mean()*100:3.0f}% | total/MW {v.pl.sum():+8.0f} | days + {(d>0).mean()*100:3.0f}% worst day {d.min():+7.0f} | Jun-Aug {h1.mean():+6.2f} ({len(h1)}) Sep-Oct {h2.mean():+6.2f} ({len(h2)})')
for z in ZS:
    x = pair(z, 'ONTARIO'); x = x[x.date <= '2026-10-12']
    for look, edge in ((7, 1.0), (14, 1.0), (7, 3.0)): report(persist(x, look, edge), f'{z} vs ONT persist {look}d edge${edge:g}')
x = pair('WEST', 'EAST'); x = x[x.date <= '2026-10-12']
for look, edge in ((7, 1.0), (14, 1.0), (7, 3.0), (3, 1.0)): report(persist(x, look, edge), f'WEST-EAST persist {look}d edge${edge:g}')
x['blk'] = pd.cut(x.he, [0, 6, 10, 16, 20, 24], labels=False); report(persist(x, 7, 1.0, 'blk'), 'WEST-EAST persist 7d by block')
for wmin in (1500, 2000, 2500):
    t = x.copy(); t['side'] = np.where((t.wind_fc >= wmin) & t.he.between(11, 16), -1, 0); t['pl'] = t.side * t.un; report(t, f'WEST-EAST wind>={wmin} HE11-16 sell West')
    t = x.copy(); t['side'] = np.where((t.wind_fc >= wmin), -1, 0); t['pl'] = t.side * t.un; report(t, f'WEST-EAST wind>={wmin} all hrs sell West')
t = x.copy(); t['side'] = np.where(t.dem_fc >= 19500, 1, 0); t['pl'] = t.side * t.un; report(t, 'WEST-EAST demand>=19.5GW buy West (fade DA)')
