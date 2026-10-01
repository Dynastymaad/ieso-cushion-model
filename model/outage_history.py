"""outage_history.py -- 7 years of generator outages, unit by unit, from IESO's public monthly capability report
(GenOutputCapabilityMonth, May 2019 ->; pulled through the browser into data/genoutcap/genoutcap_month_<year>.csv.gz).
Per unit and hour: rating = 98th percentile of its capability over the trailing 365 days; outage = rating - capability.
Gas outage therefore includes summer ambient derates (as IESO's own Adequacy 'Gas Outage' does).
Outputs
  data/genoutcap/fuel_hourly.csv   date, he, <fuel>_rating, <fuel>_cap, <fuel>_out   (NUCLEAR, GAS, HYDRO)
  data/genoutcap/norms.csv         month x fuel: outage/rating ratio P10 / P25 / P50 / P75 / P90 and mean MW, 2019-2025
  data/genoutcap/events.csv        unit outage events (capability < 50% of rating), start, end, hours, MW, month"""
import sys, glob; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
G = C.DATA / 'genoutcap'; FUELS = ['NUCLEAR', 'GAS', 'HYDRO']

def load():
    parts = []
    for f in sorted(glob.glob(str(G / 'genoutcap_month_*.csv.gz'))):
        x = pd.read_csv(f, header=None, skiprows=1, usecols=range(28))
        x.columns = ['date', 'unit', 'fuel', 'meas'] + [f'h{i}' for i in range(1, 25)]
        parts.append(x[(x.meas == 'Capability') & x.fuel.isin(FUELS)])
    x = pd.concat(parts).drop_duplicates(['date', 'unit'], keep='last')
    L = x.melt(id_vars=['date', 'unit', 'fuel'], value_vars=[f'h{i}' for i in range(1, 25)], var_name='he', value_name='cap')
    L['he'] = L.he.str[1:].astype(int); L['cap'] = pd.to_numeric(L.cap, errors='coerce')
    return L.dropna(subset=['cap'])

def build():
    L = load(); L['d'] = pd.to_datetime(L.date)
    # daily max capability per unit, then trailing-365-day 98th percentile = rating
    dm = L.groupby(['unit', 'fuel', 'd']).cap.max().reset_index().sort_values(['unit', 'd'])
    dm['rating'] = dm.groupby('unit').cap.transform(lambda s: s.rolling(365, min_periods=30).quantile(.98))
    dm['rating'] = dm.rating.fillna(dm.groupby('unit').cap.transform('max'))
    L = L.merge(dm[['unit', 'd', 'rating']], on=['unit', 'd'], how='left')
    dm.sort_values('d').groupby('unit').tail(1)[['unit', 'fuel', 'd', 'rating']].to_csv(G / 'unit_ratings.csv', index=False)
    L['out'] = (L.rating - L.cap).clip(lower=0)
    F = L.groupby(['date', 'he', 'fuel']).agg(rating=('rating', 'sum'), cap=('cap', 'sum'), out=('out', 'sum')).unstack('fuel')
    F.columns = [f'{f.lower()}_{k}' for k, f in F.columns]; F = F.reset_index(); F.to_csv(G / 'fuel_hourly.csv', index=False)
    # monthly norms (2019-05 .. 2025-12 = the 'history' that the current year is compared against)
    F['month'] = pd.to_datetime(F.date).dt.month; F['year'] = pd.to_datetime(F.date).dt.year
    rows = []
    for fu in ('nuclear', 'gas', 'hydro'):
        F[f'{fu}_ratio'] = F[f'{fu}_out'] / F[f'{fu}_rating']
        h = F[F.date < '2026-01-01']
        for m, g in h.groupby('month'):
            q = g[f'{fu}_ratio'].quantile([.1, .25, .5, .75, .9]).values
            rows.append(dict(fuel=fu, month=m, p10=q[0], p25=q[1], p50=q[2], p75=q[3], p90=q[4], mean_mw=g[f'{fu}_out'].mean(), rating_mw=g[f'{fu}_rating'].mean(), years=g.year.nunique()))
    N = pd.DataFrame(rows); N.to_csv(G / 'norms.csv', index=False)
    # outage events per unit: capability below 50% of rating, contiguous hours
    L = L.sort_values(['unit', 'd', 'he']); L['down'] = L.cap < 0.5 * L.rating
    L['ts'] = L.d + pd.to_timedelta(L.he - 1, unit='h')
    ev = []
    for u, g in L[L.fuel.isin(['GAS', 'NUCLEAR'])].groupby('unit'):
        s = g.down.values; ts = g.ts.values; rt = g.rating.values
        i = 0
        while i < len(s):
            if s[i]:
                j = i
                while j + 1 < len(s) and s[j + 1] and (ts[j + 1] - ts[j]) <= np.timedelta64(2, 'h'): j += 1
                ev.append(dict(unit=u, fuel=g.fuel.iloc[0], start=pd.Timestamp(ts[i]), end=pd.Timestamp(ts[j]), hours=j - i + 1, mw=float(np.nanmedian(rt[i:j + 1]))))
                i = j + 1
            else: i += 1
    E = pd.DataFrame(ev); E['month'] = E.start.dt.month; E.to_csv(G / 'events.csv', index=False)
    return F, N, E

if __name__ == '__main__':
    F, N, E = build()
    print(F.date.min(), F.date.max(), len(F))
    print(N.pivot_table(index='month', columns='fuel', values=['p50', 'p90']).round(3).to_string())
    a = C.adq2('final')[['date', 'he', 'gas_out', 'nuc_out']]; m = F.merge(a, on=['date', 'he'])
    print('check vs IESO Adequacy final (overlap', len(m), 'h): gas corr', round(m.gas_out_x.corr(m.gas_out_y) if 'gas_out_x' in m else m['gas_out'].corr(m['gas_out']), 3))
