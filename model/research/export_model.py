"""export_model.py -- Nov 5 2026 research. Net exports at the bid, modelled (not averaged):
  New York net flow = gradient-boosted model of the NY-Ontario spread at the bid (NY DA posted before the bid, in CAD at D-1 USD/CAD,
                      minus our Ontario DA forecast), NY price level, hour, weekday, the NY export limit for D, and the NY flow's own
                      last-14-day median; refit weekly on the last 150 days through D-2; capped at the NY export limit.
  Other interties    = last-14-day median per hour (through D-2).
Writes data/research/export_hat.csv (date, he, exp_hat, ny_hat) for the read test. Compares with today's fixed 14-day median."""
import sys, numpy as np, pandas as pd; sys.path.insert(0, 'model'); import common as C
from sklearn.ensemble import HistGradientBoostingRegressor
pd.set_option('display.width', 250)
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)[['date', 'he', 'da_fc', 'exp_exp', 'wkend', 'wind_fc', 'dem_fc', 'pub_sp']]
I = pd.read_csv('data/intertie_actual.csv')[['date', 'he', 'ny_flow', 'tot_flow']]
ny = pd.read_csv('data/nyiso_zoneA_da.csv')[['date', 'he', 'nyA_da']]
fx = pd.read_csv(C.CACHE / 'fx_usdcad.csv', parse_dates=['Date']).sort_values('Date')
L = pd.read_csv('data/ieso_preda_intertie_limits.csv'); L['mw'] = L.mw.abs()
lim = L[L.zone == 'NYSIN'].groupby(['date', 'he']).mw.mean().rename('ny_lim').reset_index()
L2 = L[~L.zone.str.contains(r'\+') & L.zone.str.endswith('N')].copy(); L2['mw'] = L2.mw.clip(upper=2500)
lim = lim.merge(L2.groupby(['date', 'he']).mw.sum().rename('exp_lim').reset_index(), on=['date', 'he'], how='outer')
import signals_v2 as SV
sc = SV.schedules()[['date', 'he', 'da_net_exp']].copy(); sc['date'] = (pd.to_datetime(sc.date) + pd.Timedelta(days=1)).dt.strftime('%Y-%m-%d')
x = h.merge(I, on=['date', 'he'], how='left').merge(ny, on=['date', 'he'], how='left').merge(lim, on=['date', 'he'], how='left').merge(sc.rename(columns={'da_net_exp': 'exp_d1'}), on=['date', 'he'], how='left')
k = pd.DataFrame({'d': pd.to_datetime(x.date.unique())}).sort_values('d'); k['cut'] = k.d - pd.Timedelta(days=1)
k = pd.merge_asof(k, fx.rename(columns={'Date': 'cut'}), on='cut'); x['ny_cad'] = x.nyA_da * x.date.map(dict(zip(k.d.dt.strftime('%Y-%m-%d'), k.Rate)))
x['spr'] = x.ny_cad - x.da_fc; x['dow'] = pd.to_datetime(x.date).dt.dayofweek
x['rest'] = x.tot_flow - x.ny_flow
x = x.sort_values(['date', 'he']).reset_index(drop=True)
for c in ('ny_flow', 'rest', 'tot_flow'):   # trailing 14-day median per hour, days through D-2 only
    w = x.pivot_table(index='date', columns='he', values=c).sort_index(); w = w.reindex(pd.date_range(w.index.min(), w.index.max()).strftime('%Y-%m-%d'))
    m = w.shift(2).rolling(14, min_periods=7).median().stack().rename(c + '_med').reset_index().rename(columns={'level_0': 'date'})
    x = x.merge(m, on=['date', 'he'], how='left')
FE = ['spr', 'ny_cad', 'da_fc', 'he', 'dow', 'ny_lim', 'ny_flow_med']
days = sorted(x.date.unique()); x['ny_hat'] = np.nan; model = None; last_fit = None
for D in days:
    if D < '2025-12-01': continue
    if last_fit is None or (pd.Timestamp(D) - pd.Timestamp(last_fit)).days >= 7:
        cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=152)).date().isoformat()
        tr = x[(x.date <= cut) & (x.date >= lo)].dropna(subset=['ny_flow', 'spr'])
        if len(tr) < 1500: continue
        model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40, random_state=0).fit(tr[FE], tr.ny_flow); last_fit = D
    m = (x.date == D) & x.spr.notna()
    if model is not None and m.any():
        p = model.predict(x.loc[m, FE]); cap = x.loc[m, 'ny_lim'].fillna(9e9).values; x.loc[m, 'ny_hat'] = np.minimum(p, cap)
x['exp_hat_ny'] = x.ny_hat + x.rest_med
# total net exports modelled directly (all interties respond to the neighbours' prices, not only NY)
FT = ['spr', 'ny_cad', 'da_fc', 'he', 'dow', 'ny_lim', 'exp_lim', 'tot_flow_med', 'exp_exp', 'exp_d1', 'wind_fc', 'dem_fc']
x['exp_hat'] = np.nan; model = None; last_fit = None
for D in days:
    if D < '2025-12-01': continue
    if last_fit is None or (pd.Timestamp(D) - pd.Timestamp(last_fit)).days >= 7:
        cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=152)).date().isoformat()
        tr = x[(x.date <= cut) & (x.date >= lo)].dropna(subset=['tot_flow', 'spr'])
        if len(tr) < 1500: continue
        model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40, random_state=0).fit(tr[FT], tr.tot_flow); last_fit = D
    m = (x.date == D) & x.spr.notna()
    if model is not None and m.any():
        p = model.predict(x.loc[m, FT]); cap = x.loc[m, 'exp_lim'].fillna(9e9).values; x.loc[m, 'exp_hat'] = np.minimum(p, cap)
r = x[(x.date >= '2026-01-01')].dropna(subset=['tot_flow', 'exp_hat', 'exp_exp'])
def rep(g, lab):
    print(f'{lab:28s} hours {len(g):5d} | fixed 14-day median: MAE {(g.tot_flow - g.exp_exp).abs().mean():4.0f} bias {(g.tot_flow - g.exp_exp).mean():+5.0f} | NY model + median rest: MAE {(g.tot_flow - g.exp_hat_ny).abs().mean():4.0f} | total model: MAE {(g.tot_flow - g.exp_hat).abs().mean():4.0f} bias {(g.tot_flow - g.exp_hat).mean():+5.0f}'
          f' | NY part: MAE {(g.ny_flow - g.ny_hat).abs().mean():4.0f} vs median {(g.ny_flow - g.ny_flow_med).abs().mean():4.0f}')
print('== Net exports at the bid, walk-forward (actual net exports vs estimate) ==')
rep(r, '2026 all'); rep(r[r.date >= '2026-10-15'], 'since Oct 15')
for lo, hi, lab in ((-999, -30, 'NY $30+ cheaper'), (-30, -15, 'NY $15-30 cheaper'), (-15, -5, 'NY $5-15 cheaper'), (-5, 5, 'about equal'), (5, 15, 'NY $5-15 dearer'), (15, 30, 'NY $15-30 dearer'), (30, 999, 'NY $30+ dearer')):
    rep(r[(r.spr > lo) & (r.spr <= hi)], lab)
x[['date', 'he', 'exp_hat', 'ny_hat', 'exp_exp', 'tot_flow', 'spr']].to_csv('data/research/export_hat.csv', index=False)
