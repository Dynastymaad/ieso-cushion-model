# Nov 5 2026: remaining claims: wind in the DA, what is predictable at the bid, Meteologica by month, the export floor, ensemble thresholds.
import pandas as pd, numpy as np, glob
pd.set_option('display.width', 250)
H = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)
print('### CLAIM: DA wind = IESO\'s wind forecast?  (Aug 14 - Nov 5 2026)')
w = pd.concat([pd.read_csv(f) for f in glob.glob('data/research/dabuild/wind_*.csv')]).merge(H[['date', 'he', 'wind_fc', 'g_wind', 'da']], on=['date', 'he'], how='left').dropna(subset=['pre_wfc', 'post_wsch', 'g_wind'])
for n, c in [('IESO wind forecast at the bid', 'pre_wfc'), ('DA wind schedule', 'post_wsch')]: print(f'   {n:30s} vs actual: mean {(w.g_wind - w[c]).mean():+5.0f}, avg abs {(w.g_wind - w[c]).abs().mean():4.0f}')
d = w.post_wsch - w.pre_wfc; print(f'   DA schedule - IESO forecast: mean {d.mean():+.0f}, avg abs {d.abs().mean():.0f}, corr {w.post_wsch.corr(w.pre_wfc):.3f}; schedule 100+ below forecast in {100*(d<=-100).mean():.0f}% of hours, 100+ above in {100*(d>=100).mean():.0f}%')
for lab, k in [('DA price < $0', w.da < 0), ('$0-30', w.da.between(0, 30)), ('$30+', w.da > 30)]: print(f'     when {lab:13s} ({k.sum():4d} h): schedule - forecast {d[k].mean():+5.0f}')
print('\n### CLAIM: only the load miss is predictable at the bid (East, correlation of the best bid-time predictor with the miss)')
x = pd.read_csv('data/research/truth_frame.csv'); x = x.sort_values(['date', 'he'])
for n, c in [('outages added after the bid', 'add_after'), ('intertie change after the bid', 'ich'), ('wind miss', 'wm'), ('load miss', 'lm')]:
    p = x.groupby('he')[c].transform(lambda s: s.shift(2 * 1).rolling(7, min_periods=3).mean())   # same HE, days D-2..D-8
    r = {'trailing 7 days, same hour': x[c].corr(p), 'public spare': x[c].corr(x.pub_sp), 'gas need': x[c].corr(x.gas_hat)}
    if c == 'lm':
        for v in ['lf_tesla', 'lf_dynasty', 'lf_meteologica']: r[v[3:] + ' - IESO'] = x[c].corr(x[v] - x.dem_fc)
    if c == 'wm': r['meteologica - IESO'] = x[c].corr(x.wf_meteologica - x.wind_fc); r['9-model median - IESO'] = x[c].corr(x.w_models - x.wind_fc)
    print(f'   {n:30s}', ' | '.join(f'{k} {v:+.2f}' for k, v in r.items()))
print('\n### CLAIM: Meteologica is the best load and wind forecast (avg abs miss, MW, same hours, by month)')
H['m'] = H.date.str[:7]
k = H[H.lf_meteologica.notna() & H.ont_dem.notna()]
print('   LOAD', k.groupby('m').apply(lambda g: pd.Series({'h': len(g), 'IESO': (g.dem_fc - g.ont_dem).abs().mean(), 'Meteologica': (g.lf_meteologica - g.ont_dem).abs().mean(), 'Tesla': (g.lf_tesla - g.ont_dem).abs().mean(), 'Dynasty': (g.lf_dynasty - g.ont_dem).abs().mean()})).round(0).to_string().replace('\n', '\n   '))
k = H[H.wf_meteologica.notna() & H.g_wind.notna()]
print('   WIND', k.groupby('m').apply(lambda g: pd.Series({'h': len(g), 'IESO': (g.wind_fc - g.g_wind).abs().mean(), 'Meteologica': (g.wf_meteologica - g.g_wind).abs().mean(), 'models median': (g.w_models - g.g_wind).abs().mean()})).round(0).to_string().replace('\n', '\n   '))
print('\n### CLAIM: exports put a floor near NY (CAD) minus ~$13')
e = pd.read_csv('data/export_hat.csv').drop_duplicates(['date', 'he'], keep='last')[['date', 'he', 'ny_cad', 'exp_lim']]
it = pd.read_csv('data/intertie_actual.csv')[['date', 'he', 'tot_flow']]; it['date'] = it.date.astype(str)
f = e.merge(H[['date', 'he', 'da', 'rt']], on=['date', 'he']).merge(it, on=['date', 'he']).dropna(subset=['ny_cad', 'da', 'tot_flow'])
f['gap'] = f.da - f.ny_cad; f['use'] = f.tot_flow / f.exp_lim
b = pd.cut(f.gap, [-999, -40, -25, -13, -5, 5, 15, 999])
print(f.groupby(b, observed=True).agg(hours=('gap', 'size'), net_exports=('tot_flow', 'mean'), share_of_limit=('use', 'mean'), east_da=('da', 'mean'), ny_cad=('ny_cad', 'mean')).round(2).to_string())
print(f'   East DA below NY-13 in {100*(f.gap < -13).mean():.0f}% of hours; below NY-25 in {100*(f.gap < -25).mean():.0f}%; below NY-40 in {100*(f.gap < -40).mean():.0f}%  ({len(f)} h, {f.date.min()}..{f.date.max()})')
