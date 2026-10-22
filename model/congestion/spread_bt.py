"""congestion/spread_bt.py -- Oct 21 2026 (TEST ONLY). When East-West / East-Southwest splits exist, what decides FADE vs GO-WITH?
GO-WITH = buy East / sell West: P&L per MW-h = (East RT-DA) - (West RT-DA) = RT split - DA split (split = East - West).
FADE = the negative. Part A: hours where the DA split is present (>= $5), all history (May 2025 ->). Part B: bid-time triggers."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import io, contextlib, numpy as np, pandas as pd, common as C, supply_fc as S
pd.set_option('display.width', 250)
with contextlib.redirect_stdout(io.StringIO()):
    import cong_read as R
P = R.price_frame()                      # zone minus EAST columns: WEST_da, WEST_rt (zone - EAST)
P = P[(P.date >= '2025-05-03')].copy()
for z in ('WEST', 'SOUTHWEST'):
    P[z + '_sp_da'] = -P[z + '_da']; P[z + '_sp_rt'] = -P[z + '_rt']          # East - zone
    P[z + '_go'] = P[z + '_sp_rt'] - P[z + '_sp_da']
a = C.adq2('preDA')[['date', 'he', 'dem_fc', 'wind_fc', 'solar_fc', 'nuc_out']]
w = S.wind_at_bid()[['date', 'he', 'wf_meteologica']]
lf = C.load_forecasts_at_bid()[['date', 'he', 'lf_tesla', 'lf_meteologica']]
f = C.fuel_actual()[['date', 'he', 'g_wind']]
x = P.merge(a, on=['date', 'he'], how='left').merge(w, on=['date', 'he'], how='left').merge(lf, on=['date', 'he'], how='left').merge(f, on=['date', 'he'], how='left')
x = x.sort_values(['date', 'he'])
x['met_gap'] = x.wf_meteologica - x.wind_fc                     # + = Meteologica windier than IESO
x['load_gap'] = x[['lf_tesla', 'lf_meteologica']].mean(axis=1) - x.dem_fc
x['wind_miss'] = x.g_wind - x.wind_fc                           # after the fact
x['w3'] = x.groupby('date').wind_fc.diff(3)
m = pd.to_datetime(x.date).dt.month
x['season'] = np.select([m.isin([12, 1, 2]), m.isin([3, 4, 5]), m.isin([6, 7, 8])], ['winter', 'spring', 'summer'], 'fall')
x['blk'] = pd.cut(x.he, [0, 6, 9, 16, 20, 24], labels=['HE1-6', 'HE7-9', 'HE10-16', 'HE17-20', 'HE21-24'])
# day-level bid-time context: yesterday's DA split and D-2 RT split (midday HE10-16), episode day
dm = x[x.he.between(10, 16)].groupby('date').agg(dsp=('WEST_sp_da', 'mean'), rsp=('WEST_sp_rt', 'mean')).reset_index()
dm['dt'] = pd.to_datetime(dm.date); dm = dm.set_index('dt').asfreq('D')
dm['dsp_y'] = dm.dsp.shift(1); dm['rsp_d2'] = dm.rsp.shift(2)
on = (dm.dsp >= 5) | (dm.rsp >= 5); ep = []; k = 0
for v in on.fillna(False): k = k + 1 if v else 0; ep.append(k)
dm['ep_day_prev'] = pd.Series(ep, index=dm.index).shift(1).fillna(0)   # consecutive split days up to D-1 (known at bid)
x = x.merge(dm.reset_index()[['date', 'dsp_y', 'rsp_d2', 'ep_day_prev']].dropna(subset=['date']), on='date', how='left')
x.to_csv(C.DATA / 'congestion' / 'spread_bt_frame.csv', index=False)

def st(g, col='WEST_go'):
    v = g[col].dropna(); d = g.assign(v=g[col]).groupby('date').v.sum()
    return pd.Series(dict(hrs=len(v), days=g.date.nunique(), go_mean=v.mean(), go_med=v.median(), go_win=(v > 0).mean() * 100, fade_win=(v < 0).mean() * 100,
                          days_go_up=(d > 0).mean() * 100)).round(1)
def tab(g, by, col='WEST_go'):
    return g.groupby(by, observed=True).apply(lambda s: st(s, col)).to_string()

print(f'frame {x.date.min()} -> {x.date.max()}  hours {len(x)}')
for z in ('WEST', 'SOUTHWEST'):
    col = z + '_go'; s = x[(x[z + '_sp_da'] >= 5) & x[col].notna()]
    print(f'\n================ {z}: hours with DA split East-{z} >= $5 (spread present)  ================')
    print('ALL:', st(s, col).to_dict())
    print('-- by size of DA split'); print(tab(s, pd.cut(s[z + '_sp_da'], [5, 10, 20, 40, 1e9]), col))
    print('-- by hour block'); print(tab(s, 'blk', col))
    print('-- by season'); print(tab(s, 'season', col))
    print('-- by IESO wind forecast'); print(tab(s, pd.cut(s.wind_fc, [-1, 1000, 1800, 2500, 9000]), col))
    print('-- by Meteologica minus IESO wind (bid time, Mar 2026 ->)'); print(tab(s.dropna(subset=['met_gap']), pd.cut(s.met_gap.dropna(), [-9e9, -200, -50, 50, 200, 9e9]), col))
    print('-- by vendor load minus IESO (bid time)'); print(tab(s.dropna(subset=['load_gap']), pd.cut(s.load_gap.dropna(), [-9e9, -300, -100, 100, 300, 9e9]), col))
    print('-- by IESO wind 3h change'); print(tab(s.dropna(subset=['w3']), pd.cut(s.w3.dropna(), [-9e9, -300, -100, 100, 300, 9e9]), col))
    print('-- by yesterday DA split (midday)'); print(tab(s.dropna(subset=['dsp_y']), pd.cut(s.dsp_y.dropna(), [-9e9, 2, 5, 10, 20, 9e9]), col))
    print('-- by episode day (consecutive split days before D)'); print(tab(s, pd.cut(s.ep_day_prev, [-1, 0, 1, 3, 100], labels=['first day', 'day 2', 'day 3-4', 'day 5+']), col))
    print('-- AFTER THE FACT: actual wind minus IESO forecast'); print(tab(s.dropna(subset=['wind_miss']), pd.cut(s.wind_miss.dropna(), [-9e9, -400, -150, 150, 400, 9e9]), col))
