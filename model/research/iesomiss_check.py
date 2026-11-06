# Nov 5 2026: audit of the IESO-miss backtest. (1) leakage checks (2) does each forecast predict PRICE (RT-DA), not just load (3) which part of the miss is already priced.
import pandas as pd, numpy as np
pd.set_option('display.width', 250)
p = pd.read_csv('data/research/iesomiss_pred.csv')
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)[['date', 'he', 'rd', 'c_Load gap', 'pub_sp', 'load_gap', 'tier', 'side', 'read']]
o = pd.read_csv('data/research/physics_history_OTTAWA.csv', low_memory=False)[['date', 'he', 'rd']].rename(columns={'rd': 'rd_o'})
x = p.merge(h, on=['date', 'he']).merge(o, on=['date', 'he']).dropna(subset=['rd', 'p2', 'g_tes', 'miss'])
print(f'{len(x)} h, {x.date.min()}..{x.date.max()}')
print('\n(1) leakage checks')
print(f'   bias7 uses misses from D-2 back: corr(bias7, same-day miss) {x.bias7.corr(x.miss):.2f}, corr(bias7, D-2 miss) {x.bias7.corr(x.groupby("he").miss.shift(2)):.2f}')
print(f'   load gap the card used = Tesla/Meteologica - IESO? max abs diff vs g_met.fillna(g_tes): {(x.load_gap - x.g_met.fillna(x.g_tes)).abs().max():.0f} MW')
print('\n(2) what each forecast says, and whether it predicts LOAD and PRICE (East RT-DA, spike-capped at $150)')
x['rdc'] = x.rd.clip(-150, 150); x['rdoc'] = x.rd_o.clip(-150, 150)
S = {'card load gap (Meteo else Tesla - IESO)': x.load_gap, 'Tesla - IESO': x.g_tes, 'Dynasty - IESO': x.g_dyn, 'IESO recent bias (7 d)': x.bias7, 'M1 linear': x.p1, 'M2 boosted': x.p2}
for n, s in S.items():
    pt = np.where(s >= 250, 2, np.where(s >= 100, 1, np.where(s <= -250, -2, np.where(s <= -100, -1, 0))))
    print(f'   {n:40s} mean {s.mean():+5.0f} sd {s.std():4.0f} | points: -2 {100*(pt==-2).mean():3.0f}% -1 {100*(pt==-1).mean():3.0f}% 0 {100*(pt==0).mean():3.0f}% +1 {100*(pt==1).mean():3.0f}% +2 {100*(pt==2).mean():3.0f}%'
          f' | corr w load miss {s.corr(x.miss):.2f} | corr w RT-DA E {s.corr(x.rdc):+.2f} O {s.corr(x.rdoc):+.2f} | corr after removing each one\'s 28-day mean {(s - s.groupby(x.he).transform(lambda q: q.shift(48).rolling(28, min_periods=5).mean())).corr(x.rdc):+.2f}')
print('\n(3) split the IESO miss into the part everyone can see (IESO\'s recent bias) and the surprise')
x['surp'] = x.miss - x.bias7
print(f'   corr(RT-DA, full miss) {x.miss.corr(x.rdc):+.2f} | corr(RT-DA, recent-bias part) {x.bias7.corr(x.rdc):+.2f} | corr(RT-DA, surprise part) {x.surp.corr(x.rdc):+.2f}')
for n, s in [('Tesla - IESO', x.g_tes), ('M2 boosted', x.p2), ('M1 linear', x.p1)]:
    print(f'   {n:14s} corr with the surprise part {s.corr(x.surp):+.2f}, with the recent-bias part {s.corr(x.bias7):+.2f}')
b = pd.qcut(x.bias7, 5)
print('   RT-DA by IESO\'s recent bias (is a known-high IESO already priced?):'); print(x.groupby(b, observed=True).agg(h=('rd', 'size'), miss=('miss', 'mean'), rt_da=('rdc', 'mean'), rt_below=('rd', lambda s: 100 * (s < 0).mean())).round(1).to_string())
print('\n(4) trade each forecast on its own: sign of (forecast - its trailing 28-day mean), 1 MW, all hours, East / Ottawa $ total')
for n, s in S.items():
    c = s - s.groupby(x.he).transform(lambda q: q.shift(48).rolling(28, min_periods=5).mean()); sg = np.sign(c).where(c.abs() >= 100, 0)
    raw = np.sign(s).where(s.abs() >= 100, 0)
    print(f'   {n:40s} raw sign: E ${(raw*x.rd).sum():8,.0f} O ${(raw*x.rd_o).sum():8,.0f} | vs its own norm: E ${(sg*x.rd).sum():8,.0f} O ${(sg*x.rd_o).sum():8,.0f}')
