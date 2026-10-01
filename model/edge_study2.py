"""edge_study2.py -- follow-ups: bid-time gas-need forecast, NY-vs-Ontario gap, DA error persistence, Sep 27 hour detail, robustness."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, edge_study as E
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300); pd.set_option('display.max_columns', 40)
zone = sys.argv[1] if len(sys.argv) > 1 else 'TORONTO'
te = pd.read_csv(C.DATA / f'es_signals_{zone}.csv')
f = pd.read_csv(C.DATA / 'adq3_final.csv'); f['da_net_exp'] = -f.exp_sch.fillna(0) - f.imp_sch.fillna(0)
f = f[['date', 'he', 'gas_sch', 'hydro_sch', 'da_net_exp']]
a = C.adq2('preDA')[['date', 'he', 'nuc_av', 'solar_fc']]
d = te.merge(f, on=['date', 'he'], how='left').merge(a.rename(columns={'nuc_av': 'nuc_av2', 'solar_fc': 'sol2'}), on=['date', 'he'], how='left')
allf = E.base(zone).merge(f, on=['date', 'he'], how='left').merge(a.rename(columns={'nuc_av': 'nuc_av2', 'solar_fc': 'sol2'}), on=['date', 'he'], how='left')
# bid-time gas need = IESO demand fc - nuclear avail - wind fc - solar fc - expected hydro + expected net exports
# expected hydro / exports = trailing 14-day median of DA schedule at that HE, using days <= D-2 (known)
rows = []
dates = sorted(allf.date.unique())
for D in dates:
    cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(cut) - pd.Timedelta(days=14)).date().isoformat()
    tr = allf[(allf.date <= cut) & (allf.date > lo)].dropna(subset=['hydro_sch'])
    if tr.date.nunique() < 7: continue
    m = tr.groupby('he')[['hydro_sch', 'da_net_exp']].median().rename(columns={'hydro_sch': 'hyd_exp', 'da_net_exp': 'exp_exp'}).reset_index()
    x = allf[allf.date == D].merge(m, on='he', how='left'); rows.append(x)
g = pd.concat(rows)
g['gas_hat'] = g.dem_fc - g.nuc_av2 - g.wind_fc.fillna(0) - g.sol2.fillna(0) - g.hyd_exp + g.exp_exp
ok = g.dropna(subset=['gas_hat', 'gas_sch'])
print(f'=== gas-need forecast (bid time) vs DA gas schedule: corr {ok[["gas_hat","gas_sch"]].corr().iloc[0,1]:.3f}, MAE {(ok.gas_hat-ok.gas_sch).abs().mean():.0f} MW, bias {(ok.gas_hat-ok.gas_sch).mean():+.0f}')
g['gb'] = pd.cut(g.gas_hat, [-9e9, 2000, 3000, 4000, 5000, 6000, 7000, 9e9])
s = g.dropna(subset=['sp'])
print('\nrealised DA-RT by BID-TIME gas-need band (all days Jul-Sep):')
print(s.groupby('gb').agg(n=('sp', 'count'), days=('date', 'nunique'), da=('da', 'mean'), spread=('sp', 'mean'), median=('sp', 'median'), sell_win=('sp', lambda x: (x > 0).mean() * 100)).round(1).to_string())
print('\n  same, weekday vs weekend:'); print(s.groupby(['wkend', 'gb']).sp.agg(n='count', mean='mean', median='median', win=lambda x: (x > 0).mean() * 100).round(1).to_string())
# walk-forward: learn the low-gas threshold on trailing data
d2 = te.merge(g[['date', 'he', 'gas_hat']], on=['date', 'he'], how='left')
out = []
for D in sorted(d2.date.unique()):
    cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
    tr = s[(s.date <= cut)]; best, bt = -1e9, -1
    for thr in [2500, 3000, 3500, 4000, 4500]:
        m = tr[tr.gas_hat < thr]
        if len(m) >= 40 and m.sp.mean() > best: best, bt = m.sp.mean(), thr
    x = d2[d2.date == D].copy(); x['gthr'] = bt; out.append(x)
d2 = pd.concat(out)
low = (d2.gas_hat < d2.gthr) & (d2.gthr > 0); tight = d2['head'] < d2.thr_wf
d2.assign(sig_tight=tight.astype(int), sig_lowgas=low.astype(int), sig_N=(tight | low).astype(int)).to_csv(C.DATA / f'es_signals2_{zone}.csv', index=False)
R = pd.DataFrame([E.score(d2, 'A sell every hour', np.ones(len(d2))),
    E.score(d2, 'E tight (headroom thr walk-forward)', np.where(tight, 1, 0)),
    E.score(d2, 'M low gas need (thr walk-forward)', np.where(low, 1, 0)),
    E.score(d2, 'N tight OR low gas need', np.where(tight | low, 1, 0)),
    E.score(d2, 'O N + regression sell > 3', np.where(tight | low | (d2.s_hat > 3), 1, 0)),
    E.score(d2, 'P regression > 0, weekday only', np.where((d2.s_hat > 0) & (d2.wkend == 0), 1, 0)),
    E.score(d2, 'Q sell if NY Zone A below our ON forecast', np.where(d2.nyx < 0, 1, 0)),
    E.score(d2, 'R buy if NY Zone A > our ON forecast + $10', np.where(d2.nyx > 10, -1, 0))])
print('\n=== walk-forward rules (test days Jul 20 - Sep 27) ==='); print(R.to_string(index=False)); R.to_csv(C.DATA / f'es_rules2_{zone}.csv', index=False)
# robustness: drop the 3 best and 3 worst days of each rule
print('\nrobustness: $/MWh after dropping each rule\'s 3 best and 3 worst days')
for name, sig in [('A', np.ones(len(d2))), ('E', np.where(tight, 1, 0)), ('M', np.where(low, 1, 0)), ('N', np.where(tight | low, 1, 0)), ('H', np.where(d2.s_hat > 0, 1, 0))]:
    x = d2[['date', 'sp']].copy(); x['pl'] = E.pnl(sig, d2.sp); x = x.dropna(subset=['pl', 'sp'])
    dd = x.groupby('date').pl.agg(['sum', 'count']); keep = dd.sort_values('sum').iloc[3:-3].index
    y = x[x.date.isin(keep)]; print(f'  {name}: all {x.pl.mean():+.2f} ({len(x)} h)   trimmed {y.pl.mean():+.2f} ({len(y)} h)')
# DA forecast error persistence -> can yesterday's error correct today's forecast?
e = pd.read_csv(C.DATA / f'es_da_errors_hourly_{zone}.csv')
dly = e.groupby('date').err.mean(); print(f'\n=== DA error persistence: corr(daily error D, D-1) = {dly.autocorr(1):.3f}, (D, D-2) = {dly.autocorr(2):.3f}')
e['blk'] = e.he.map(E.BLKMAP)
eb = e.groupby(['date', 'blk']).err.mean().unstack()
prev = eb.shift(1)   # D-1 DA is published before the D bid deadline, so D-1's error is known
for k in [0.25, 0.5, 0.75]:
    adj = e.merge(prev.stack().rename('e1').reset_index(), on=['date', 'blk'], how='left')
    adj['p2'] = adj.p_da - k * adj.e1.fillna(0)
    print(f'  subtract {k:.2f} x yesterday\'s block error: MAE {(adj.p2 - adj.da).abs().mean():.2f} vs {e.err.abs().mean():.2f}, bias {(adj.p2 - adj.da).mean():+.2f}')
# weekend-specific bias
print('\nDA error by weekday x block (mean, + = model too high):'); print(e.groupby(['dow', 'blk']).err.mean().unstack().round(1).to_string())
# Sep 27 hour detail
x = d2[d2.date == '2026-09-27'][['he', 'da', 'rt', 'sp', 'head', 'thr_wf', 'gas_hat', 'gthr', 'gapT', 'nyx', 's_hat', 'prof']].copy()
x = x.merge(f[f.date == '2026-09-27'][['he', 'gas_sch']], on='he', how='left')
print('\n=== Sep 27 hour detail (bid-time features; gas_sch is the DA result for reading only) ==='); print(x.round(1).to_string(index=False))
