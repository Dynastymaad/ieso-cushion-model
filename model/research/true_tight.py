"""research/true_tight.py -- Nov 1 2026 (TEST ONLY). Is the market truly tight, or just somewhat tight?
Step 1  FUNDAMENTAL fair RT: a model that sees ONLY physical bid-time fundamentals (no prices, no price history) and predicts the
        RT heat rate (RT converted with that day's Dawn gas + carbon, so gas-price swings do not drive it). Inputs:
        public spare, our-view (rescue) spare, gas expected online, gas ramp 1h/3h, IESO wind and its 3h change, net-load 3h ramp,
        wind-model disagreement, load/wind gaps vs IESO, valves (exports + spare hydro), headroom, nuclear/gas outages, hour, weekend, month.
Step 2  PRICED scarcity: our DA forecast for the hour (what the market is expected to pay), same heat-rate units.
Step 3  GAP = priced - fundamental. Big +: market pays for scarcity the physics does not support -> short. Big -: physics tighter than
        the price -> long.  Walk-forward: retrained weekly on 2026 data through D-2, tested Mar 2 -> Oct 30 2026, both hubs."""
import sys, warnings, time; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd, common as C, market_read as MR, cahr as K
from sklearn.ensemble import HistGradientBoostingRegressor as HGB
from sklearn.linear_model import Ridge
pd.set_option('display.width', 240); pd.set_option('display.max_columns', 40)
FE = ['pub_sp', 'priv_sp', 'rescue', 'gas_hat', 'g1', 'g3', 'wind_fc', 'w3', 'res3', 'w_spread', 'd_load', 'd_wind', 'valve', 'head',
      'nuc_out', 'gas_out', 'solar_fc', 'he', 'wkend', 'month']

def frame(z, since='2025-12-01'):
    e = MR.history(z); e = e[e.date >= since].copy().sort_values(['date', 'he']); g = e.groupby('date')
    e['g1'] = e.gas_hat - g.gas_hat.shift(1); e['g3'] = e.gas_hat - g.gas_hat.shift(3)
    e['w3'] = e.wind_fc - g.wind_fc.shift(3); e['res3'] = e.resid_fc - g.resid_fc.shift(3); e['month'] = pd.to_datetime(e.date).dt.month
    e = K.add(e.drop(columns=['cahr'], errors='ignore'), 'p_da')
    e['den'] = e.gas_cad + K.EF * e.cp; e['off'] = K.BENCH * e.cp
    e['hr_rt'] = (e.rt + e.off) / e.den; e['hr_fc'] = (e.p_da + e.off) / e.den
    return e[e.den.notna()]

def walk(e, start='2026-03-02', train_from='2026-01-01'):
    for c in ('fair_gbm', 'fair_q90', 'fair_lin'): e[c] = np.nan
    for s in pd.date_range(start, e.date.max(), freq='7D'):
        s0 = s.date().isoformat(); s1 = (s + pd.Timedelta(days=6)).date().isoformat(); cut = (s - pd.Timedelta(days=2)).date().isoformat()
        te = (e.date >= s0) & (e.date <= s1); tr = e[(e.date <= cut) & (e.date >= train_from)].dropna(subset=['hr_rt'])
        y = tr.hr_rt.clip(-5, 60)
        m = HGB(loss='absolute_error', max_depth=3, learning_rate=0.05, max_iter=250, min_samples_leaf=40, l2_regularization=2.0, random_state=0).fit(tr[FE], y)
        q = HGB(loss='quantile', quantile=0.9, max_depth=3, learning_rate=0.05, max_iter=250, min_samples_leaf=40, l2_regularization=2.0, random_state=0).fit(tr[FE], y)
        X = tr[FE].fillna(tr[FE].median()); mu, sd = X.mean(), X.std().replace(0, 1)
        r = Ridge(alpha=10).fit((X - mu) / sd, y.clip(0, 30))
        e.loc[te, 'fair_gbm'] = m.predict(e.loc[te, FE]); e.loc[te, 'fair_q90'] = q.predict(e.loc[te, FE])
        e.loc[te, 'fair_lin'] = r.predict((e.loc[te, FE].fillna(tr[FE].median()) - mu) / sd)
    return e

if __name__ == '__main__':
    out = {}
    for z in ('EAST', 'OTTAWA'):
        t0 = time.time(); e = walk(frame(z)); t = e[e.date >= '2026-03-02'].dropna(subset=['fair_gbm', 'rt', 'da']).copy()
        for c in ('fair_gbm', 'fair_lin'): t[c.replace('fair', 'rtfair')] = t[c] * t.den - t.off
        t['rtfair_q90'] = t.fair_q90 * t.den - t.off
        t['gap'] = t.p_da - t.rtfair_gbm; t['gap_lin'] = t.p_da - t.rtfair_lin; t['x'] = t.rt - t.da
        print(f'\n===== {z}: test {t.date.min()}..{t.date.max()}, {len(t)} h, {time.time()-t0:.0f}s =====')
        print(f'fundamental fair RT (no prices) MAE ${(t.rtfair_gbm - t.rt).abs().mean():.1f}  (linear ${(t.rtfair_lin - t.rt).abs().mean():.1f}); DA forecast as RT guess ${(t.p_da - t.rt).abs().mean():.1f}')
        for gcol in ('gap', 'gap_lin'):
            print(f'-- {gcol}: priced minus fundamental, trade the sign beyond a threshold (shorts when +, longs when -), $/MWh --')
            for T in (5, 10, 15, 20, 30):
                s = t[gcol] >= T; l = t[gcol] <= -T; ps = (t.da - t.rt)[s]; pl = (t.rt - t.da)[l]
                print(f'   T={T:2d}: SHORT {int(s.sum()):5d} h ${ps.mean():+6.2f} win {(ps>0).mean()*100:3.0f}% | LONG {int(l.sum()):5d} h ${pl.mean():+6.2f} win {(pl>0).mean()*100:3.0f}%')
        b = pd.qcut(t.gap, 5); print('-- by gap quintile (gbm) --'); print(t.groupby(b).agg(h=('x', 'size'), gap=('gap', 'mean'), rt_minus_da=('x', 'mean'), rt_gt_da=('x', lambda s: (s > 0).mean() * 100), spike=('x', lambda s: (s >= 25).mean() * 100), collapse=('x', lambda s: (s <= -20).mean() * 100)).round(1).to_string())
        print('-- by month: short gap>=15 / long gap<=-15 ($/MWh, hours) --')
        print(t.groupby(t.date.str[:7]).apply(lambda g: pd.Series({'short': round((g.da - g.rt)[g.gap >= 15].mean(), 1), 'sh_h': int((g.gap >= 15).sum()), 'long': round((g.rt - g.da)[g.gap <= -15].mean(), 1), 'lg_h': int((g.gap <= -15).sum())})).to_string())
        t.to_csv(C.DATA / 'research' / f'true_tight_{z}.csv', index=False); out[z] = t
