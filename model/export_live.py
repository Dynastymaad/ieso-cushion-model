"""export_live.py -- Nov 5 2026. Net exports for the delivery day, modelled at the bid (wired into the card as the 'Exports' point).
Same model as research/export_model.py (walk-forward tested Dec 2025-Nov 2026: net-export miss 635 -> 524 MW; NY $30+ cheaper 1,207 -> 758):
gradient-boosted on the NY-Ontario spread (NY DA in CAD at D-1 USD/CAD minus our Ontario DA forecast), NY price, hour, weekday, the NY
and total export limits for D, yesterday's DA export schedule, the last-14-day median, IESO wind and load; fit on the last 150 days
through D-2; capped at the export limit. Writes the D rows into data/export_hat.csv (date, he, exp_hat, exp_exp, spr)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
FT = ['spr', 'ny_cad', 'da_fc', 'he', 'dow', 'ny_lim', 'exp_lim', 'tot_flow_med', 'exp_exp', 'exp_d1', 'wind_fc', 'dem_fc']
OUT = C.DATA / 'export_hat.csv'

def frame(rows):
    """rows: date, he, da_fc, exp_exp, wind_fc, dem_fc (bid-time). Adds actual flows, NY price, limits, schedules, medians."""
    import signals_v2 as SV
    I = pd.read_csv(C.DATA / 'intertie_actual.csv')[['date', 'he', 'ny_flow', 'tot_flow']]
    ny = pd.read_csv(C.DATA / 'nyiso_zoneA_da.csv')[['date', 'he', 'nyA_da']]
    fx = pd.read_csv(C.CACHE / 'fx_usdcad.csv', parse_dates=['Date']).sort_values('Date')
    L = pd.read_csv(C.DATA / 'ieso_preda_intertie_limits.csv'); L['mw'] = L.mw.abs()
    lim = L[L.zone == 'NYSIN'].groupby(['date', 'he']).mw.mean().rename('ny_lim').reset_index()
    L2 = L[~L.zone.str.contains(r'\+') & L.zone.str.endswith('N')].copy(); L2['mw'] = L2.mw.clip(upper=2500)
    lim = lim.merge(L2.groupby(['date', 'he']).mw.sum().rename('exp_lim').reset_index(), on=['date', 'he'], how='outer')
    sc = SV.schedules()[['date', 'he', 'da_net_exp']].copy(); sc['date'] = (pd.to_datetime(sc.date) + pd.Timedelta(days=1)).dt.strftime('%Y-%m-%d')
    x = rows.merge(I, on=['date', 'he'], how='left').merge(ny, on=['date', 'he'], how='left').merge(lim, on=['date', 'he'], how='left') \
            .merge(sc.rename(columns={'da_net_exp': 'exp_d1'}), on=['date', 'he'], how='left')
    k = pd.DataFrame({'d': pd.to_datetime(x.date.unique())}).sort_values('d'); k['cut'] = k.d - pd.Timedelta(days=1)
    k = pd.merge_asof(k, fx.rename(columns={'Date': 'cut'}), on='cut'); x['ny_cad'] = x.nyA_da * x.date.map(dict(zip(k.d.dt.strftime('%Y-%m-%d'), k.Rate)))
    x['spr'] = x.ny_cad - x.da_fc; x['dow'] = pd.to_datetime(x.date).dt.dayofweek
    w = x.pivot_table(index='date', columns='he', values='tot_flow').sort_index(); w = w.reindex(pd.date_range(w.index.min(), x.date.max()).strftime('%Y-%m-%d'))
    m = w.shift(2).rolling(14, min_periods=7).median().stack().rename('tot_flow_med').reset_index().rename(columns={'level_0': 'date'})
    return x.merge(m, on=['date', 'he'], how='left')

def update(D, rowsD):
    """rowsD: the delivery day's bid-time rows (date, he, da_fc, exp_exp, wind_fc, dem_fc). Returns D's rows with exp_hat."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    h = pd.read_csv(C.DATA / 'research' / 'physics_history_EAST.csv', low_memory=False, usecols=['date', 'he', 'da_fc', 'exp_exp', 'wind_fc', 'dem_fc'])
    h = h[h.date < D]
    x = frame(pd.concat([h, rowsD[['date', 'he', 'da_fc', 'exp_exp', 'wind_fc', 'dem_fc']]], ignore_index=True))
    cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=152)).date().isoformat()
    tr = x[(x.date <= cut) & (x.date >= lo)].dropna(subset=['tot_flow', 'spr'])
    t = x[x.date == D].copy()
    if len(tr) < 1500 or t.spr.isna().all(): print('export model: not enough data or no NY price for', D); return None
    mdl = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40, random_state=0).fit(tr[FT], tr.tot_flow)
    t['exp_hat'] = np.minimum(mdl.predict(t[FT]), t.exp_lim.fillna(9e9).values)
    t.loc[t.spr.isna(), 'exp_hat'] = np.nan
    old = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame()
    keep = old[old.date != D] if len(old) else old
    pd.concat([keep, t[['date', 'he', 'exp_hat', 'exp_exp', 'spr', 'ny_cad', 'exp_lim', 'ny_lim']]], ignore_index=True).sort_values(['date', 'he']).to_csv(OUT, index=False)
    return t
