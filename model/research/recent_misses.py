# Nov 5 2026: what drove the misses Oct 27 - Nov 5? Temperature, line outages (intertie limit cuts), load, wind - day by day, vs the rest of the history.
import pandas as pd, numpy as np
pd.set_option('display.width', 260); pd.set_option('display.max_columns', 40)
H = {z: pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False) for z in ['EAST', 'OTTAWA']}
e = H['EAST'].merge(H['OTTAWA'][['date', 'he', 'rd', 'tier', 'side', 'score', 'read']], on=['date', 'he'], suffixes=('', '_o'))
w = pd.read_csv('data/wx/wx_hourly.csv')[['date', 'he', 't_act', 't_fc']]; w['t_act'] = (w.t_act - 32) / 1.8; w['t_fcw'] = (w.t_fc - 32) / 1.8
L = pd.read_csv('data/ieso_preda_intertie_limits.csv'); L = L[L.zone != 'MISI+NYSIN']; L = L[L.zone != 'MISI+NYSIX']; L['dir'] = np.where(L.zone.str.endswith('N'), 'exp', 'imp'); L['mw'] = L.mw.abs()
lim = L.pivot_table(index=['date', 'he'], columns='dir', values='mw', aggfunc='sum').reset_index().sort_values(['date', 'he'])
for c in ['exp', 'imp']: lim[c + '_norm'] = lim.groupby('he')[c].transform(lambda s: s.shift(1).rolling(30, min_periods=10).median()); lim[c + '_cut'] = lim[c] - lim[c + '_norm']
tf = pd.read_csv('data/research/truth_frame.csv')[['date', 'he', 'ich', 'add_after']]
x = e.merge(w[['date', 'he', 't_act', 't_fcw']], on=['date', 'he'], how='left').merge(lim[['date', 'he', 'exp_cut', 'imp_cut', 'exp', 'imp']], on=['date', 'he'], how='left').merge(tf, on=['date', 'he'], how='left')
x['lm'] = x.ont_dem - x.dem_fc; x['wm'] = x.g_wind - x.wind_fc; x['met_gap'] = x.lf_meteologica - x.dem_fc; x['t_err'] = x.t_act - x.t_fcw
x['pl'] = np.where(x.tier.isin(['A', 'B']), x.side * x.rd, 0); x['pl_o'] = np.where(x.tier_o.isin(['A', 'B']), x.side_o * x.rd_o, 0)
x['tr'] = x.tier.isin(['A', 'B'])
r = x[(x.date >= '2026-10-27') & x.rd.notna()]
d = r.groupby('date').agg(east_pl=('pl', 'sum'), ott_pl=('pl_o', 'sum'), traded=('tr', 'sum'), right=('pl', lambda s: (s > 0).sum()), rt_da=('rd', 'mean'),
                          load_miss=('lm', 'mean'), met_saw=('met_gap', 'mean'), load_gap_bid=('load_gap', 'mean'), temp_fc_err=('t_err', 'mean'), temp_swing_pts=('c_Temp swing', 'sum'),
                          wind_miss=('wm', 'mean'), export_lim_cut=('exp_cut', 'mean'), import_lim_cut=('imp_cut', 'mean'), intertie_chg=('ich', 'mean'), outages_added=('add_after', 'mean')).round(1)
print('### Day by day (means over the day; load/wind miss = actual - IESO; met_saw = Meteologica - IESO at the bid; temp_fc_err = actual - forecast C; limit cut = MW vs 30-day normal)')
print(d.to_string())
print('\n### Same measures, average day in the rest of the history (Sep 2025 - Oct 26 2026)')
q = x[(x.date < '2026-10-27') & x.rd.notna()]; dd = q.groupby('date').agg(east_pl=('pl', 'sum'), ott_pl=('pl_o', 'sum'), load_miss=('lm', lambda s: s.abs().mean()), temp_fc_err=('t_err', lambda s: s.abs().mean()), export_lim_cut=('exp_cut', 'mean'), import_lim_cut=('imp_cut', 'mean'))
print(dd.describe().loc[['mean', '25%', '50%', '75%']].round(1).to_string())
print('\n### Worst traded hours Oct 27 - Nov 5 (East)')
k = r[r.tr].nsmallest(15, 'pl')[['date', 'he', 'tier', 'side', 'score', 'read', 'rd', 'pl', 'lm', 'met_gap', 'load_gap', 'wm', 't_err', 'c_Temp swing', 'exp_cut', 'imp_cut', 'ich', 'pub_sp']].round(1)
print(k.to_string(index=False))
print('\n### Does a limit cut at the bid go with RT-DA, whole history (East, hours)?')
for lab, s in [('export limits cut 500+ MW', x.exp_cut <= -500), ('export limits normal (within 200)', x.exp_cut.abs() <= 200), ('import limits cut 500+ MW', x.imp_cut <= -500), ('import limits normal', x.imp_cut.abs() <= 200)]:
    k = x[s & x.rd.notna()]; print(f'   {lab:36s} {len(k):5d} h, {k.date.nunique():3d} days: RT-DA mean {k.rd.mean():+6.2f}, median {k.rd.median():+6.2f} | plan on those hours ${k.pl.mean():+.2f}/MWh traded-hour avg (all hours ${x.pl[x.tr & x.rd.notna()].mean():+.2f})')
print('\n### Temperature forecast error vs load miss and RT-DA (East, all history with temps)')
k = x.dropna(subset=['t_err', 'lm', 'rd'])
print(f'   corr(temp error, IESO load miss) {k.t_err.corr(k.lm):+.2f} | corr(temp error, Meteologica miss) {k.t_err.corr(k.ont_dem - k.lf_meteologica):+.2f} | corr(temp error, RT-DA) {k.t_err.corr(k.rd):+.2f}')
k['tb'] = pd.cut(k.t_err, [-20, -3, -1.5, 1.5, 3, 20]); print(k.groupby('tb', observed=True).agg(h=('rd', 'size'), load_miss=('lm', 'mean'), rt_da=('rd', 'mean'), plan=('pl', 'mean')).round(1).to_string())
