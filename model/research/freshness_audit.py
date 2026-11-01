"""Nov 1 2026: for each recent delivery day, which version of each input the bid-time model used, vs the latest version that existed
before the bid, and whether two sources for the same number agree."""
import sys; sys.path.insert(0, 'model'); import pandas as pd, numpy as np, common as C, supply_fc as S
D0 = '2026-09-01'
# 1 IESO Adequacy: sandbox (what the model uses) vs public archive, same cutoff
a2 = pd.read_csv('cache/ieso_adq2_preDA.csv'); a2 = a2[a2.date >= D0]
a2t = a2.groupby('date').ieso_createtime.max(); a2t = pd.to_datetime(a2t)
a3 = pd.read_csv('data/adq3_preDA.csv'); a3 = a3[a3.date >= D0]; a3t = pd.to_datetime(a3.groupby('date').issued.max())
j = pd.DataFrame({'sandbox': a2t, 'public': a3t}).dropna()
j['sandbox_older_min'] = (j.public - j.sandbox).dt.total_seconds() / 60
print('1) IESO pre-DA Adequacy version used (EST), last 61 days:')
print('   sandbox time of day', a2t.dt.strftime('%H:%M').value_counts().head(4).to_dict())
print('   public  time of day', a3t.dt.strftime('%H:%M').value_counts().head(4).to_dict())
print(f'   days public has a NEWER version than the sandbox: {(j.sandbox_older_min > 5).sum()} of {len(j)} (median gap {j.sandbox_older_min[j.sandbox_older_min>5].median() if (j.sandbox_older_min>5).any() else 0:.0f} min)')
s2 = C.adq2('preDA')[['date', 'he', 'dem_fc', 'wind_fc', 'gas_out', 'nuc_out']]; s3 = a3[['date', 'he', 'dem_fc', 'wind_fc', 'gas_out', 'nuclear_out']].rename(columns={'nuclear_out': 'nuc_out'})
m = s2.merge(s3, on=['date', 'he'], suffixes=('_sb', '_pub'))
for c in ['dem_fc', 'wind_fc', 'gas_out', 'nuc_out']:
    d = (m[c + '_sb'] - m[c + '_pub']).abs(); print(f'   {c:8s} sandbox vs public: identical {(d < 1).mean():.0%} of hours, mean abs diff {d.mean():.0f} MW')
# 2 vendor wind at bid: was Meteologica there?
w = S.wind_at_bid(); w = w[w.date >= D0]; cov = w.groupby('date').wf_meteologica.apply(lambda s: s.notna().mean())
print(f'2) Meteologica wind present at bid: {(cov > .9).sum()} of {len(cov)} days; missing days: {list(cov[cov <= .9].index)[-8:]}')
# 3 vendor load at bid
L = C.load_forecasts_at_bid(); L = L[L.date >= D0]; cl = L.groupby('date')[['lf_meteologica', 'lf_tesla']].apply(lambda x: x.notna().mean())
print(f'3) Meteologica load at bid: {(cl.lf_meteologica > .9).sum()} of {len(cl)} days (first {cl[cl.lf_meteologica>.9].index.min()}); Tesla: {(cl.lf_tesla > .9).sum()} days')
# 4 NYISO DAM for the delivery day: the file exists, but was it there at the morning run? (posted ~07:35 MT)
ny = pd.read_csv('data/nyiso_zoneA_da.csv'); nyd = ny[ny.date >= D0].groupby('date').size()
print(f'4) NYISO Zone A DA in archive: {len(nyd)} days since {D0}, latest {ny.date.max()}')
# 5 prices: missing RT / DA hours
p = C.prices(); p = p[(p.zone == 'EAST') & (p.date >= D0)]; full = p.groupby('date').agg(da=('da', 'count'), rt=('rt', 'count'))
print(f'5) EAST prices: days with <24 DA hours {list(full[full.da<24].index)}; days with <24 RT hours {list(full[full.rt<24].index)}')
# 6 actuals and flows (feed bias terms and the D-2 export median)
ad = C.actual_demand(); fu = C.fuel_actual(); ia = pd.read_csv('data/intertie_actual.csv')
print(f'6) actual demand to {ad.date.max()}, fuel to {fu.date.max()}, intertie flows to {ia.date.max()}')
# 7 forwards / gas settles
f = pd.read_csv('cache/fwd_daily_ontario.csv', usecols=['EffectiveDate', 'ExchangeCode']); print(f'7) forward settles (XDE/CVX/PDA) latest EffectiveDate {f.EffectiveDate.max()}')
