# Nov 5 2026: real trades vs the model. (1) your Oct 27-Nov 4 trades (2) Dynasty's virtuals Jun 2025 - Sep 2026, scored at RT-DA, and vs the model's side on East/Ottawa.
import pandas as pd, numpy as np, sys
sys.path.insert(0, 'model'); import common as C
pd.set_option('display.width', 250)
r = pd.read_csv('data/research/my_virts_review.csv')
r['model_side'] = r.log_side; r['you'] = np.where(r.side == 'BUY', 1, -1)
print('### (1) Your trades Oct 27 - Nov 4:', len(r), 'hour-trades, total $', round(r.pnl.sum()))
print(r.groupby('date').agg(trades=('pnl', 'size'), mw=('mw', 'sum'), pnl=('pnl', 'sum'), right=('pnl', lambda s: (s > 0).sum()), model_agreed=('agree', 'sum')).to_string())
print(r.groupby('side').agg(n=('pnl', 'size'), pnl=('pnl', 'sum'), per_mwh=('pnl', lambda s: s.sum() / r.loc[s.index, 'mw'].sum())).round(2).to_string())
print(r.groupby('log_tier').agg(n=('pnl', 'size'), pnl=('pnl', 'sum')).round(0).to_string())
print('   when you agreed with the model side:', round(r.pnl[r.agree].sum()), '| disagreed or model no trade:', round(r.pnl[~r.agree].sum()))
d = pd.read_csv('cache/dynasty_virtuals.csv'); d['he'] = d.hour; d['side'] = np.where(d.buysell.str.lower().str.startswith('b'), 1, -1); d['zone'] = d.zone.str.upper(); d['volume'] = d.volume.abs()
print('\n### (2) Dynasty virtuals:', len(d), 'rows', d.date.min(), '..', d.date.max(), '| zones', d.zone.value_counts().to_dict())
P = []
for z, f in [('EAST', 'EAST'), ('OTTAWA', 'OTTAWA')]:
    h = pd.read_csv(f'data/research/physics_history_{f}.csv', low_memory=False)[['date', 'he', 'da', 'rt', 'tier', 'side', 'read', 'score']].rename(columns={'side': 'm_side'})
    k = d[d.zone.str.contains(z)].merge(h, on=['date', 'he'], how='inner').dropna(subset=['rt', 'da'])
    k['pl'] = k.side * (k.rt - k.da) * k.volume; k['zz'] = z; P.append(k)
k = pd.concat(P)
if len(k):
    k['m'] = k.date.str[:7]; k['agree'] = np.where(k.tier.isin(['A', 'B']), np.where(k.m_side == k.side, 'model same side', 'model OPPOSITE'), 'model no trade (C/N)')
    print(f'   East/Ottawa trades matched to model history: {len(k)} rows, {k.date.min()}..{k.date.max()}, total ${k.pl.sum():,.0f} on {k.volume.sum():,.0f} MWh (${k.pl.sum()/k.volume.sum():+.2f}/MWh)')
    print(k.groupby(['zz', 'side']).apply(lambda g: pd.Series({'MWh': g.volume.sum(), 'pnl': g.pl.sum(), 'per_MWh': g.pl.sum() / g.volume.sum(), 'right%': 100 * (g.pl > 0).mean()})).round(2).to_string())
    print(k.groupby('agree').apply(lambda g: pd.Series({'MWh': g.volume.sum(), 'pnl': g.pl.sum(), 'per_MWh': g.pl.sum() / g.volume.sum()})).round(2).to_string())
    print(k.groupby('m').apply(lambda g: pd.Series({'MWh': g.volume.sum(), 'pnl': g.pl.sum()})).round(0).T.to_string())
# all zones, firm level, with prices from the zonal price file if available
try:
    zp = C.zone_prices() if hasattr(C, 'zone_prices') else None
except Exception as ex: zp = None
print('\n   all Dynasty rows by zone (count, MWh):'); print(d.groupby(['zone', 'side']).volume.agg(['size', 'sum']).to_string())
