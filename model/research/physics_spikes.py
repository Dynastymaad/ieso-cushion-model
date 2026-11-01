"""STEP 1 - physics, after the fact: in hours where RT blew through DA (or collapsed), what physically happened vs the bid-time view?
Surprise = actual - what the IESO/our gas-need build said at bid. Sign: + = system ended tighter than expected."""
import sys; sys.path.insert(0, 'model'); import common as C, pandas as pd, numpy as np
z = sys.argv[1] if len(sys.argv) > 1 else 'EAST'
e = pd.read_csv(f'data/research/stress_{z}_extra.csv'); e['rd'] = e.rt - e.da
f = pd.read_csv('data/research/fuel_actual.csv'); d = C.actual_demand()[['date', 'he', 'ont_dem']]
ia = pd.read_csv('data/intertie_actual.csv')[['date', 'he', 'tot_flow']]
tr = pd.read_csv('data/unit_trips.csv').groupby(['date', 'he']).mw_lost.sum().rename('trips').reset_index()
e = e.merge(f, on=['date', 'he'], how='left').merge(d, on=['date', 'he'], how='left').merge(ia, on=['date', 'he'], how='left').merge(tr, on=['date', 'he'], how='left')
e['trips'] = e.trips.fillna(0); e = e[e.date >= '2026-01-01'].dropna(subset=['rd', 'ont_dem', 'g_gas', 'tot_flow', 'gas_hat']).copy()
e['s_load'] = e.ont_dem - e.dem_fc                      # demand above IESO forecast
e['s_wind'] = e.wind_fc - e.g_wind                      # wind below IESO forecast
e['s_solar'] = e.solar_fc - e.g_solar
e['s_nuc'] = e.nuc_av - e.g_nuclear                     # nuclear below available (derates/trips)
e['s_exp'] = e.tot_flow - e.exp_exp                     # more net exports than expected
e['s_hyd'] = e.hyd_exp - e.g_hydro                      # less hydro than expected
e['gas_call'] = e.g_gas - e.gas_hat                     # = what gas actually had to do vs our need (net of everything)
e['rt_gas_room'] = e.gas_av - e.g_gas                   # gas still available but not running in RT
e['gas_ramp_act'] = e.groupby('date').g_gas.diff()
e['out'] = pd.cut(e.rd, [-1e9, -25, -5, 5, 25, 1e9], labels=['collapse <=-25', 'down -25..-5', 'flat', 'up 5..25', 'SPIKE >=+25'])
S = ['s_load', 's_wind', 's_solar', 's_nuc', 's_exp', 's_hyd', 'gas_call', 'trips', 'rt_gas_room', 'gas_ramp_act', 'pub_sp', 'vs']
print(f'===== {z}: {e.date.min()}..{e.date.max()}, {len(e)} hours with actuals =====')
print('\nAverage surprise (MW, + = tighter than the bid-time view) by what RT did vs DA:')
print(e.groupby('out', observed=True)[S].mean().round(0).assign(hours=e.groupby('out', observed=True).size()).to_string())
print('\nSpike / collapse rate by realized gas call (gas had to run X MW more than our need):')
b = pd.cut(e.gas_call, [-1e9, -1000, -500, 0, 500, 1000, 1e9])
print(e.groupby(b, observed=True).rd.agg(hours='size', avg='mean', spike=lambda x: (x >= 25).mean(), collapse=lambda x: (x <= -25).mean()).round(2).to_string())
print('\n...split by public spare at bid (spike rate):')
sp = pd.cut(e.pub_sp, [-1e9, 1500, 2500, 3500, 1e9], labels=['spare<1500', '1500-2500', '2500-3500', '>3500'])
print(e.groupby([b, sp], observed=True).rd.apply(lambda x: f'{(x>=25).mean():.0%} / {(x<=-25).mean():.0%} (n{len(x)})').unstack().to_string())
print('\nWhich single surprise explains RT-DA best? (rank corr, all hours / spare<2500 hours)')
lo = e[e.pub_sp < 2500]
for s in S: print(f'  {s:14s} {e[s].corr(e.rd, method="spearman"):+.2f}   {lo[s].corr(lo.rd, method="spearman"):+.2f}')
e.to_csv(f'data/research/physics_{z}.csv', index=False)
