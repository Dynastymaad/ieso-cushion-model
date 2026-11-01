"""Does the 2026 season pattern hold outside Mar-Oct 2026? Out-of-sample: Jun 2025 - Feb 2026 (Ontario's DA market started May 1 2025).
Same card (Tesla load gap; weather-model wind gap, since Meteologica isn't in the archive before Mar 2026) and same physics read (90-day weights, through D-2)."""
import sys; sys.path.insert(0, 'model/research'); sys.path.insert(0, 'model')
import pandas as pd, numpy as np, common as C, fear_rescue as FR, physics_read_live as P
from sklearn.linear_model import Ridge
def season(d):
    m = int(d[5:7]); y = d[:4]
    s = 'winter' if m in (12, 1, 2) else 'spring' if m in (3, 4, 5) else 'summer' if m in (6, 7, 8) else 'fall'
    yy = (str(int(y) + 1) if m == 12 else y) if s == 'winter' else y
    return f'{s} {yy if s != "winter" else str(int(yy)-1)[-2:]+"/"+yy[-2:]}'
# 1. base rate by month
p = C.prices(); p = p[p.zone.isin(['EAST', 'OTTAWA'])].dropna(subset=['da', 'rt']); p['rd'] = p.rt - p.da; p['m'] = p.date.str[:7]
b = p.groupby(['m', 'zone']).rd.agg(avg='mean', med='median', up=lambda x: (x > 0).mean()).round(2).unstack('zone')
print('RT - DA by month (avg / median / share of hours RT above DA):'); print(b.to_string())
p['season'] = p.date.map(season); print('\nby season (EAST avg, OTTAWA avg):'); print(p.groupby(['season', 'zone']).rd.mean().round(1).unstack().to_string())
# outages by month (bid-time IESO view)
e0 = pd.read_csv(C.DATA / 'dv_frame_EAST.csv', usecols=['date', 'he', 'gas_out', 'nuc_out', 'gas_av', 'head']); e0['m'] = e0.date.str[:7]
print('\nPlanned+forced outages in the IESO bid-time view, MW (monthly avg):'); print(e0.groupby('m')[['gas_out', 'nuc_out', 'head']].mean().round(0).T.to_string())
# 2. card + read out of sample
res = []
for z in ['EAST', 'OTTAWA']:
    e = FR.frame(z).sort_values(['date', 'he']).reset_index(drop=True); g = e.groupby('date')
    e['w3'] = e.wind_fc - g.wind_fc.shift(3); e['g3'] = e.gas_hat - g.gas_hat.shift(3); e['res3'] = e.resid_fc - g.resid_fc.shift(3)
    e['vs'] = e.p_da - e.groupby('he').p_da.transform(lambda s: s.shift(1).rolling(14, min_periods=5).median()); e['rd'] = e.rt - e.da
    e['bias_L'] = np.nan; e['bias_W'] = np.nan
    bias = P.ieso_bias(e); e = P.prep(e.drop(columns=['bias_L', 'bias_W']), bias)
    pts = e.apply(lambda r: P.card_points(dict(load_gap=r.gL, wind_gap=r.gW, w3=r.w3, pub_sp=r.pub_sp, vs=None if pd.isna(r.vs) else r.vs, ny=None if pd.isna(r.ny_pull) else r.ny_pull))[0], axis=1)
    e['score'] = pts
    e['read'] = np.nan; F = P.F
    for s in pd.date_range('2025-09-08', e.date.max(), freq='7D'):
        s0 = s.strftime('%Y-%m-%d'); s1 = (s + pd.Timedelta(days=6)).strftime('%Y-%m-%d'); cut = (s - pd.Timedelta(days=2)).strftime('%Y-%m-%d'); lo = (s - pd.Timedelta(days=92)).strftime('%Y-%m-%d')
        tr = e[(e.date <= cut) & (e.date > lo) & e.rd.notna()].dropna(subset=F); te = (e.date >= s0) & (e.date <= s1)
        if te.sum() == 0 or len(tr) < 500: continue
        X = tr[F].values; mu, sd = X.mean(0), X.std(0) + 1e-9; m = Ridge(alpha=50).fit((X - mu) / sd, tr.rd.clip(-80, 150).values)
        Xt = e.loc[te, F].values.astype(float); Xt = np.where(np.isnan(Xt), mu, Xt); e.loc[te, 'read'] = m.predict((Xt - mu) / sd)
    e['zone'] = z; e['season'] = e.date.map(season); res.append(e[['zone', 'date', 'he', 'season', 'score', 'read', 'rd', 'vs', 'pub_sp']])
r = pd.concat(res).dropna(subset=['rd']); r['period'] = np.where(r.date < '2026-03-01', 'OUT of sample', 'in sample (Mar-Oct 26)')
big = r[r.score.abs() >= 3].copy(); big['side'] = np.sign(big.score); big['pnl'] = big.side * big.rd
print('\nStrong card (|score|>=3): $/MWh made by trading its side, by season:')
q = big.groupby(['season', 'zone', 'side']).pnl.agg(['size', 'mean']).round(1).unstack('side'); print(q.to_string())
rr = r.dropna(subset=['read']).copy(); s, v = np.sign(rr.score), np.sign(rr.read)
rr['tier'] = np.select([(rr.score.abs() >= 3) & (s == v), rr.score.abs() >= 3, rr.read.abs() >= 5], ['A', 'C', 'B'], 'N'); rr['side'] = np.where(rr.score.abs() >= 3, s, v); rr['pnl'] = rr.side * rr.rd
print('\nTiers by season (read available from Sep 2025), $/MWh traded side [hours]:')
print(rr.groupby(['season', 'zone', 'tier']).pnl.agg(lambda x: f'{x.mean():+.1f} [{len(x)}]').unstack('tier').to_string())
ab = rr[rr.tier.isin(['A', 'B'])]; print('\nTiers A+B by season and side, $/MWh [hours]:'); print(ab.groupby(['season', 'zone', 'side']).pnl.agg(lambda x: f'{x.mean():+.1f} [{len(x)}]').unstack('side').to_string())
print('\nTiers A+B total $/MW by month:'); print(ab.groupby([ab.date.str[:7], 'zone']).pnl.sum().round(0).unstack().to_string())
r.to_csv('data/research/season_check.csv', index=False)
