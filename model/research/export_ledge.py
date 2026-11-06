"""export_ledge.py -- Nov 5 2026 research only. Are exports a dynamic, price-driven piece of the stack (boss's description)?
Exports vs the NY - Ontario spread (both in CAD), the intertie limits, and how our static export estimate (14-day median) misses."""
import sys, numpy as np, pandas as pd; sys.path.insert(0, 'model'); import common as C, signals_v2 as SV
pd.set_option('display.width', 250)
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)[['date', 'he', 'da_fc', 'da', 'rt', 'ny', 'exp_exp', 'tot_flow', 'gas_hat', 'pub_sp', 'wind_fc']]
I = pd.read_csv('data/intertie_actual.csv')[['date', 'he', 'ny_flow', 'ny_exp', 'ny_imp']]
p = C.prices('ONTARIO')[['date', 'he', 'da', 'rt']].rename(columns={'da': 'ont_da', 'rt': 'ont_rt'}); p['date'] = p.date.astype(str)
ny = pd.read_csv('data/nyiso_zoneA_da.csv')[['date', 'he', 'nyA_da']]
fx = pd.read_csv(C.CACHE / 'fx_usdcad.csv', parse_dates=['Date']).sort_values('Date')
x = h.merge(I, on=['date', 'he'], how='left').merge(p, on=['date', 'he'], how='left').merge(ny, on=['date', 'he'], how='left')
k = pd.DataFrame({'d': pd.to_datetime(x.date.unique())}).sort_values('d'); k['cut'] = k.d - pd.Timedelta(days=1)
k = pd.merge_asof(k, fx.rename(columns={'Date': 'cut'}), on='cut'); x['fx'] = x.date.map(dict(zip(k.d.dt.strftime('%Y-%m-%d'), k.Rate)))
x['ny_cad'] = x.nyA_da * x.fx
x['spr_bid'] = x.ny_cad - x.da_fc          # what we can see at the bid: NY DA (posted) vs our Ontario DA forecast
x['spr'] = x.ny_cad - x.ont_da            # after DA clears: NY DA vs Ontario DA
L = pd.read_csv('data/ieso_preda_intertie_limits.csv'); L['mw'] = L.mw.abs()
nyl = L[L.zone == 'NYSIN'].groupby(['date', 'he']).mw.mean().rename('ny_lim').reset_index(); x = x.merge(nyl, on=['date', 'he'], how='left')
y = x[(x.date >= '2026-01-01')].dropna(subset=['ny_exp', 'spr', 'tot_flow'])
f = lambda g: pd.Series(dict(h=len(g), ny_exp=g.ny_exp.mean(), ny_imp=g.ny_imp.mean(), net_exports=g.tot_flow.mean(), static_est=g.exp_exp.mean(), miss=(g.tot_flow - g.exp_exp).mean(), ont_da=g.ont_da.mean(), ny_cad=g.ny_cad.mean()))
print('== 1. 2026: exports vs the NY - Ontario DA spread (CAD; + = NY dearer, Ontario should export) ==')
print(y.groupby(pd.cut(y.spr, [-999, -30, -15, -5, 5, 15, 30, 60, 999]), observed=True).apply(f, include_groups=False).round(0).to_string())
print('\n   same, using the spread we can see at the bid (NY DA vs our Ontario DA forecast):')
print(y.groupby(pd.cut(y.spr_bid, [-999, -30, -15, -5, 5, 15, 30, 60, 999]), observed=True).apply(f, include_groups=False).round(0).to_string())
print('\ncorr with actual net exports (2026, hourly): spread after DA %.2f | spread at bid %.2f | our static 14-day median %.2f' % (
    y[['spr', 'tot_flow']].corr().iloc[0, 1], y[['spr_bid', 'tot_flow']].corr().iloc[0, 1], y[['exp_exp', 'tot_flow']].corr().iloc[0, 1]))
print('our static estimate miss (actual - est) vs bid spread: corr %.2f' % y[['spr_bid']].assign(m=y.tot_flow - y.exp_exp).corr().iloc[0, 1])
# 2. where does Ontario DA sit relative to NY when exports are flowing?  the export 'ledge'
print('\n== 2. The export ledge: Ontario DA minus NY (CAD) by NY export level (2026) ==')
print(y.groupby(pd.cut(y.ny_exp, [-1, 100, 500, 1000, 1500, 9999]), observed=True).agg(h=('spr', 'size'), ont_minus_ny=('spr', lambda s: -s.median()), ont_da=('ont_da', 'median'), ny_cad=('ny_cad', 'median')).round(1).to_string())
# 3. limits: when NY export is cut, exports at a given spread
z = y.dropna(subset=['ny_lim']); z = z.assign(cut=np.where(z.ny_lim <= 1100, 'NY export limit <= 1,100', 'NY limit normal'))
print('\n== 3. NY exports by spread, limit cut vs normal (Aug 29 - Nov 4) ==')
print(z.groupby(['cut', pd.cut(z.spr, [-999, -5, 5, 15, 30, 999])], observed=True).agg(h=('ny_exp', 'size'), ny_exp=('ny_exp', 'mean'), at_cap=('ny_exp', lambda s: np.nan), ont_rt=('ont_rt', 'mean'), rt_lt25=('ont_rt', lambda s: (s < 25).mean() * 100)).round(0).unstack(0).to_string())
# 4. dynamic export estimate: fit exports ~ spread_at_bid (piecewise) + hour, trailing 60 days, capped by limits -> error vs static
y2 = x[x.date >= '2025-09-01'].dropna(subset=['tot_flow', 'spr_bid', 'exp_exp']).sort_values(['date', 'he']).reset_index(drop=True)
days = sorted(y2.date.unique()); pred = pd.Series(np.nan, index=y2.index)
def feats(g): s = g.spr_bid.clip(-80, 120); return np.c_[np.ones(len(g)), s.clip(upper=0), s.clip(lower=0), g.exp_exp]
for D in days:
    tr = y2[(y2.date < (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat()) & (y2.date >= (pd.Timestamp(D) - pd.Timedelta(days=61)).date().isoformat())]
    if tr.date.nunique() < 30: continue
    b = np.linalg.lstsq(feats(tr), tr.tot_flow, rcond=None)[0]; m = y2.date == D; pred[m] = feats(y2[m]) @ b
y2['dyn'] = pred
r = y2.dropna(subset=['dyn']); r = r[r.date >= '2026-01-01']
print('\n== 4. Net export estimate at the bid, 2026 walk-forward: average miss (MW) ==')
print('  static 14-day median (now): MAE %.0f bias %+.0f' % ((r.tot_flow - r.exp_exp).abs().mean(), (r.tot_flow - r.exp_exp).mean()))
print('  dynamic (spread at bid + median, refit on 60 days): MAE %.0f bias %+.0f' % ((r.tot_flow - r.dyn).abs().mean(), (r.tot_flow - r.dyn).mean()))
rr = r[r.date >= '2026-10-15']; print('  since Oct 15: static MAE %.0f | dynamic MAE %.0f' % ((rr.tot_flow - rr.exp_exp).abs().mean(), (rr.tot_flow - rr.dyn).abs().mean()))
y2.to_csv('data/research/export_ledge.csv', index=False)
