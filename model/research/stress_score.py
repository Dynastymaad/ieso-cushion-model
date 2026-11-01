"""research/stress_score.py -- Nov 1 2026 (TEST ONLY). A 'how tight is this hour really' score for the Fundamentals tab, built from
EVERYTHING at the bid, not just load and wind: public spare, our spare, gas expected online, gas ramp 1h/3h, wind ramp 3h, net-load ramp,
Meteologica load and wind vs IESO, wind-model disagreement, valves, headroom, and what DA is expected to pay (DA fc vs usual, DA heat rate).
Target = RT - DA (+ = system tighter than DA paid for). Two versions, both walk-forward weekly on 2026 data through D-2:
  SCORECARD  additive points: for each input, the average RT - DA in its bin (quintiles) inside the same regime (scared / mid / calm by
             public spare), shrunk toward 0 when the bin is thin, summed, then scaled to $ by one regression. Every point is readable.
  GBM        gradient boosting on the same inputs (median loss), as the accuracy ceiling.
Scored on Mar 2 -> Oct 30 2026 and on Oct 31 (prices pulled from IESO), both hubs."""
import sys, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0, 'model/research'); sys.path.insert(0, 'model')
import numpy as np, pandas as pd, common as C, true_tight as T
from sklearn.ensemble import HistGradientBoostingRegressor as HGB
pd.set_option('display.width', 240)
F = {'pub_sp': 'public spare', 'priv_sp': 'our spare', 'gas_hat': 'gas expected online', 'g1': 'gas ramp 1h', 'g3': 'gas ramp 3h', 'w3': 'wind ramp 3h',
     'res3': 'net-load ramp 3h', 'd_load': 'Meteo load - IESO', 'd_wind': 'Meteo wind - IESO', 'w_spread': 'wind models spread', 'valve': 'valves',
     'head': 'headroom', 'vs': 'DA fc vs usual', 'hr_fc': 'DA fc heat rate', 'he': 'hour'}
EXTRA = {'w_rel': 'Meteo wind vs IESO, %', 'iesow_vs_models': 'IESO wind minus weather-model median', 'load_vote': 'load vendors above IESO (count)',
         'load_mean_gap': 'avg vendor load - IESO', 'danger_frac': 'danger as share of public spare', 'g3_rel': 'gas ramp 3h as share of gas online'}
if '--extra' in sys.argv: F.update(EXTRA)
OCT31 = {'EAST': ([47.44, 48.23, 50.39, 51.78, 53.82, 60.28, 67.15, 68.25, 64.29, 62.81, 53.83, 53.01, 50.73, 50.32, 53.18, 52.97, 66.1, 84.01, 72.41, 62.9, 55.92, 53.26, 51.04, 48.35],
                  [54.65, 50.94, 46.28, 41.12, 48.63, 57.97, 66.01, 67.31, 72.48, 70.88, 78.39, 81.35, 122.58, 76.27, 72.11, 86.96, 78.74, 68.16] + [None] * 6),
         'OTTAWA': ([48.27, 49.01, 51.21, 52.68, 54.78, 61.27, 68.42, 69.24, 65.01, 63.54, 54.73, 53.95, 51.72, 51.31, 54.22, 54.0, 67.77, 86.14, 74.3, 64.22, 56.94, 54.3, 51.89, 49.17],
                    [55.58, 51.81, 47.01, 41.75, 49.37, 58.81, 66.96, 68.1, 73.33, 71.71, 79.5, 82.53, 124.67, 77.68, 73.54, 88.76, 80.59, 69.38] + [None] * 6)}

def regime(sp): return np.select([sp < 1500, sp < 3000], ['scared', 'mid'], 'calm')

def fit_card(tr):
    tr = tr.copy(); tr['x'] = (tr.rt - tr.da).clip(-80, 150); tr['reg'] = regime(tr.pub_sp); card = {}
    base = tr.groupby('reg').x.mean().to_dict()
    for f in F:
        for r, g in tr.groupby('reg'):
            d = g.dropna(subset=[f])
            if len(d) < 100: continue
            edges = np.unique(d[f].quantile([0, .2, .4, .6, .8, 1]).values)
            if len(edges) < 3: continue
            b = pd.cut(d[f], edges, include_lowest=True); st = d.groupby(b).x.agg(['mean', 'size'])
            pts = ((st['mean'] - base[r]) * st['size'] / (st['size'] + 150)).values
            card[(f, r)] = (edges, pts)
    tr['raw'] = score_raw(tr, card, base)
    k = np.polyfit(tr.raw, tr.x, 1)
    return card, base, k

def score_raw(d, card, base, parts=False):
    reg = regime(d.pub_sp); tot = np.array([base.get(r, 0) for r in reg], dtype=float); P = {}
    for (f, r), (edges, pts) in card.items():
        m = (reg == r) & d[f].notna().values
        if not m.any(): continue
        i = np.clip(np.searchsorted(edges, d.loc[m, f].values, side='right') - 1, 0, len(pts) - 1)
        v = np.zeros(len(d)); v[m] = pts[i]; tot += v; P[f] = P.get(f, 0) + v
    return (tot, P) if parts else tot

def walk(e, start='2026-03-02'):
    e['card'] = np.nan; e['gbm'] = np.nan
    for s in pd.date_range(start, e.date.max(), freq='7D'):
        s0 = s.date().isoformat(); s1 = (s + pd.Timedelta(days=6)).date().isoformat(); cut = (s - pd.Timedelta(days=2)).date().isoformat()
        te = (e.date >= s0) & (e.date <= s1); tr = e[(e.date <= cut) & (e.date >= '2026-01-01')].dropna(subset=['rt', 'da'])
        card, base, k = fit_card(tr); e.loc[te, 'card'] = np.polyval(k, score_raw(e[te], card, base))
        m = HGB(loss='absolute_error', max_depth=3, learning_rate=0.05, max_iter=250, min_samples_leaf=50, l2_regularization=2.0, random_state=0)
        m.fit(tr[list(F)], (tr.rt - tr.da).clip(-80, 150)); e.loc[te, 'gbm'] = m.predict(e.loc[te, list(F)])
    return e

if __name__ == '__main__':
    for z in ('EAST', 'OTTAWA'):
        e = T.frame(z, '2026-10-31'); e = e.sort_values(['date', 'he'])
        e['w_rel'] = e.d_wind / e.wind_fc.clip(lower=50) * 100; e['iesow_vs_models'] = e.wind_fc - e.w_models
        lv = e[['lf_meteologica', 'lf_tesla', 'lf_dynasty']].sub(e.dem_fc, axis=0); e['load_vote'] = (lv > 100).sum(axis=1) - (lv < -100).sum(axis=1); e['load_mean_gap'] = lv.mean(axis=1)
        e['danger_frac'] = -e.rescue / e.pub_sp.clip(lower=300); e['g3_rel'] = e.g3 / e.gas_hat.clip(lower=1000)
        e['vs'] = e.p_da - e.groupby('he').p_da.transform(lambda s: s.shift(1).rolling(14, min_periods=5).median())
        da, rt = OCT31[z]; k = e.date == '2026-10-31'
        e.loc[k, 'da'] = e.loc[k, 'he'].map(dict(zip(range(1, 25), da))); e.loc[k, 'rt'] = e.loc[k, 'he'].map(dict(zip(range(1, 25), rt)))
        e = walk(e); t = e[(e.date >= '2026-03-02') & e.rt.notna() & e.card.notna()].copy(); t['x'] = t.rt - t.da; t['m'] = t.date.str[:7]
        print(f'\n===== {z}: {t.date.min()}..{t.date.max()}, {len(t)} h =====')
        for c in ('card', 'gbm'):
            b = pd.qcut(t[c], 10, labels=False, duplicates='drop')
            dec = t.groupby(b).x.agg(['mean', lambda s: (s > 0).mean() * 100]).round(1)
            top = t[b == b.max()]; bot = t[b == 0]
            mt = top.groupby('m').x.mean(); mb = (-bot.x).groupby(bot.m).mean()
            print(f'{c:5s}: decile RT-DA {dec["mean"].tolist()}  | top decile LONG ${top.x.mean():+.1f} win {(top.x>0).mean()*100:.0f}% months+ {(mt>0).sum()}/{len(mt)}'
                  f' | bottom decile SHORT ${(-bot.x).mean():+.1f} win {((-bot.x)>0).mean()*100:.0f}% months+ {(mb>0).sum()}/{len(mb)} | rank corr {t[c].rank().corr(t.x.rank()):.2f}')
            val = t[t.he.between(9, 15)]; bv = pd.qcut(val[c], 5, labels=False, duplicates='drop')
            print(f'       valley HE9-15 by score quintile (RT-DA): {val.groupby(bv).x.mean().round(1).tolist()}')
        o = e[e.date == '2026-10-31'][['he', 'da', 'rt', 'card', 'gbm']].copy(); o['rt_da'] = o.rt - o.da
        print('Oct 31 (read made with data through Oct 29):'); print(o.round(1).to_string(index=False))
        cuts = t.card.quantile([.1, .2, .5, .8, .9]).round(1).to_dict(); print('card cut-offs', cuts)
        e.to_csv(C.DATA / 'research' / (f'stress_{z}_extra.csv' if '--extra' in sys.argv else f'stress_{z}.csv'), index=False)
