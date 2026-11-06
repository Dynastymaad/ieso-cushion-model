# Nov 5 2026: every East trade we have for you (Dynasty feed Sep 27-30 + your Oct 27 - Nov 4 list), each with the model's bid-time picture and the result.
import pandas as pd, numpy as np
pd.set_option('display.width', 260); pd.set_option('display.max_rows', 300)
d = pd.read_csv('cache/dynasty_virtuals.csv'); d = d[d.zone.str.upper().str.contains('EAST') & (d.date >= '2026-09-27')].copy()
print('Dynasty feed East rows Sep 27+:', len(d), '| uploads:', d.uploaded_at.str[:16].value_counts().to_dict())
d = d.sort_values('uploaded_at').drop_duplicates(['date', 'hour', 'buysell'], keep='last')
a = pd.DataFrame({'date': d.date, 'he': d.hour, 'side': np.where(d.buysell.str.lower().str.startswith('b'), 'BUY', 'SELL'), 'mw': d.volume.abs(), 'src': 'feed'})
b = pd.read_csv('data/research/my_virts_oct27_nov4.csv'); b['src'] = 'your list'
t = pd.concat([a, b], ignore_index=True)
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)
t = t.merge(h[['date', 'he', 'da', 'rt', 'rd', 'da_fc', 'vs', 'pub_sp', 'gas_hat', 'load_gap', 'wind_gap', 'ny', 'read', 'score', 'tier', 'side', 'c_DA priced', 'ont_dem', 'dem_fc', 'g_wind', 'wind_fc']].rename(columns={'side': 'm_side'}), on=['date', 'he'], how='left')
t['s'] = np.where(t.side == 'BUY', 1, -1); t['pnl'] = t.s * t.rd * t.mw; t['per'] = t.s * t.rd
t['model'] = np.where(t.tier.isin(['A', 'B']), np.where(t.m_side == t.s, 'WITH', 'AGAINST'), 'no trade')
t['lm'] = t.ont_dem - t.dem_fc; t['wm'] = t.g_wind - t.wind_fc
t['tight'] = t.pub_sp < 2500; t['priced'] = t.vs >= 18
print(f'\nTrades: {len(t)} hour-trades, {t.mw.sum():.0f} MWh, {t.date.nunique()} days; total ${t.pnl.sum():,.0f}')
print('\n### By day'); print(t.groupby('date').agg(trades=('pnl', 'size'), MWh=('mw', 'sum'), pnl=('pnl', 'sum'), buys=('s', lambda s: (s > 0).sum()), sells=('s', lambda s: (s < 0).sum()), right=('pnl', lambda s: (s > 0).sum()), with_model=('model', lambda s: (s == 'WITH').sum()), against=('model', lambda s: (s == 'AGAINST').sum())).round(0).to_string())
print('\n### By side x model'); print(t.groupby(['side', 'model']).agg(trades=('pnl', 'size'), MWh=('mw', 'sum'), pnl=('pnl', 'sum'), per_MWh=('per', 'mean'), right=('per', lambda s: 100 * (s > 0).mean())).round(1).to_string())
print('\n### Buys: tight / priced / vendor load gap'); bb = t[t.s > 0]
print(bb.groupby([bb.tight.map({True: 'spare<2.5k', False: 'spare 2.5k+'}), bb.priced.map({True: 'DA 18+ over usual', False: 'DA not priced up'}), np.sign(bb.load_gap).map({1: 'vendors above IESO', -1: 'vendors below IESO', 0: '0'})]).agg(n=('pnl', 'size'), pnl=('pnl', 'sum'), per=('per', 'mean')).round(1).to_string())
print('\n### By hour block and side'); print(t.groupby([pd.cut(t.he, [0, 6, 15, 21, 24]), 'side'], observed=True).agg(n=('pnl', 'size'), pnl=('pnl', 'sum'), per=('per', 'mean')).round(1).to_string())
print('\n### Every trade')
print(t[['date', 'he', 'side', 'mw', 'da', 'rt', 'pnl', 'model', 'tier', 'read', 'score', 'vs', 'pub_sp', 'gas_hat', 'load_gap', 'lm', 'wind_gap', 'wm', 'ny']].round(0).to_string(index=False))
t.to_csv('data/research/my_trades_scored.csv', index=False)
