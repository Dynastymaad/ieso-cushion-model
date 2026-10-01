"""outage_priced.py -- are outages known at the bid priced into DA, and what about the ones added after?
Per day (peak HE8-21 means): out_bid (gas+nuclear+hydro outage MW in the last IESO Adequacy before the bid),
dev30 = out_bid minus its mean over the previous 30 days (all known at the bid), add_after = MW added after the bid.
Hourly regressions, East and Ottawa, 17 months:
  DA level  ~ dev30 + add_after          (does DA move with outages?)
  DA - RT   ~ dev30 + add_after + head   (+ coef = DA over-priced it, - = RT beat DA, 0 = priced in)
Day-block bootstrap 90% intervals. Output data/outage_priced.json."""
import sys, json, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C

def daily():
    o = pd.read_csv(C.DATA / 'outage_features.csv'); pk = o[o.he.between(8, 21)]
    d = pk.groupby('date').agg(gas_bid=('gas_bid', 'mean'), nuc_bid=('nuc_bid', 'mean'), hyd_bid=('hyd_bid', 'mean'), out_bid=('out_bid', 'mean'),
                               add_after=('add_after', 'mean'), gas_add=('gas_add', 'mean'), trips=('trips_d1', 'max'), ret=('ret_assumed', 'mean')).reset_index().sort_values('date')
    for c in ('out_bid', 'gas_bid', 'nuc_bid', 'hyd_bid'):
        d[c + '_m30'] = d[c].shift(1).rolling(30, min_periods=20).mean(); d[c + '_s30'] = d[c].shift(1).rolling(30, min_periods=20).std()
    d['dev30'] = d.out_bid - d.out_bid_m30
    return d

def boot(y, X, days, n=400, seed=3):
    rng = np.random.default_rng(seed); u = np.unique(days); idx = {k: np.where(days == k)[0] for k in u}; B = []
    for _ in range(n):
        s = np.concatenate([idx[k] for k in rng.choice(u, len(u))]); B.append(np.linalg.lstsq(X[s], y[s], rcond=None)[0])
    return np.percentile(np.array(B), [5, 95], axis=0)

def run():
    d = daily(); a = C.adq2('preDA')[['date', 'he', 'head']]; res = {}
    for z in ('EAST', 'OTTAWA'):
        p = C.prices(z)[['date', 'he', 'da', 'rt']]
        x = p.merge(a, on=['date', 'he']).merge(d[['date', 'dev30', 'add_after']], on='date').dropna()
        x = x[(x.he.between(8, 21)) & (x.date >= '2025-07-01')]; x['sp'] = x.da - x.rt
        X = np.column_stack([np.ones(len(x)), x.dev30 / 1000, x.add_after / 1000, x['head'] / 1000]); days = x.date.values
        out = {}
        for y in ('da', 'sp'):
            b = np.linalg.lstsq(X, x[y].values, rcond=None)[0]; ci = boot(x[y].values, X, days)
            out[y] = {k: [round(b[i], 2), round(ci[0][i], 2), round(ci[1][i], 2)] for i, k in enumerate(['const', 'dev30_per_GW', 'add_after_per_GW', 'head_per_GW'])}
        # simple buckets: days with outages well above their 30-day mean
        g = x.groupby('date').agg(sp=('sp', 'mean'), dev=('dev30', 'first'), add=('add_after', 'first'))
        g['bin'] = pd.cut(g.dev, [-1e9, -1000, -300, 300, 1000, 1e9], labels=['< -1 GW', '-1..-0.3', '±0.3 GW', '+0.3..+1', '> +1 GW'])
        out['by_dev30'] = g.groupby('bin').sp.agg(['mean', 'count']).round(2).reset_index().astype({'bin': str}).to_dict('records')
        g['abin'] = pd.cut(g['add'], [-1e9, 100, 500, 1000, 1e9], labels=['< 100', '100-500', '500-1000', '> 1000'])
        out['by_add'] = g.groupby('abin').sp.agg(['mean', 'count']).round(2).reset_index().astype({'abin': str}).to_dict('records')
        out['hours'] = int(len(x)); out['days'] = int(x.date.nunique()); res[z] = out
        print(f'\n{z}  ({out["days"]} days, peak hours)'); print('  DA level:', out['da']); print('  DA - RT :', out['sp'])
        print('  DA-RT by outage vs 30-day mean:', out['by_dev30']); print('  DA-RT by MW added after bid:', out['by_add'])
    (C.DATA / 'outage_priced.json').write_text(json.dumps(res, indent=1, default=float))

if __name__ == '__main__': run()
