# Nov 5 2026: do ensembles of the forecasts we already have beat the single forecasts the card uses? All bid-time; weights/bias learned on days <= D-2.
import sys; sys.path.insert(0, 'model/research'); sys.path.insert(0, 'model')
import pandas as pd, numpy as np, json, common as C, fear_rescue as FR
pd.set_option('display.width', 250)
KEEP = json.load(open(C.ROOT / 'site' / 'data' / 'bundle.json'))['target']
e = FR.frame('EAST', keep=KEEP, all_rows=True).sort_values(['date', 'he']).reset_index(drop=True)
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)[['date', 'he', 'ont_dem', 'g_wind']]
e = e.drop(columns=[c for c in ('ont_dem', 'g_wind') if c in e]).merge(h, on=['date', 'he'], how='inner')
e = e[e.date >= '2025-09-08'].reset_index(drop=True)
WF = [c for c in e if c.startswith('wf_')]; print('wind sources:', {c: round(e[c].notna().mean(), 2) for c in WF})
days = sorted(e.date.unique()); dd = pd.to_datetime(e.date)
def walk(cols, y, win=45, lam=1.0):
    """bias-corrected (per HE, trailing 30 d) + stacked (ridge on corrected, trailing win d), all through D-2. Missing sources -> filled with IESO-like base."""
    bc = {c: pd.Series(np.nan, index=e.index) for c in cols}; st = pd.Series(np.nan, index=e.index)
    for D in days[40:]:
        Dt = pd.Timestamp(D); tr = e[(dd <= Dt - pd.Timedelta(days=2)) & (dd > Dt - pd.Timedelta(days=2 + win))]; te = e.index[e.date == D]
        if tr[y].notna().sum() < 300: continue
        cor = {}
        for c in cols:
            t30 = tr[dd[tr.index] > Dt - pd.Timedelta(days=32)]; b = (t30[y] - t30[c]).groupby(t30.he).mean()
            bc[c][te] = e.loc[te, c] + e.loc[te, 'he'].map(b).fillna(0).values; cor[c] = tr[c] + tr.he.map(b).fillna(0)
        X = pd.DataFrame(cor); ok = X.notna().all(axis=1) & tr[y].notna()
        if ok.sum() < 300: continue
        from scipy.optimize import nnls
        w = nnls(X[ok].values, tr[y][ok].values)[0]; w = w / w.sum() if w.sum() > 0 else np.ones(len(cols)) / len(cols)
        Xt = pd.DataFrame({c: bc[c][te] for c in cols}); st[te] = (Xt.values * w).sum(1)
    return bc, st
print('\n===== LOAD (MW) =====')
LC = ['dem_fc', 'lf_tesla', 'lf_dynasty']
All4 = None
bc, st = walk(LC, 'ont_dem')
ok = st.notna() & e[LC].notna().all(axis=1) & e.ont_dem.notna(); k = e[ok]; miss = k.ont_dem - k.dem_fc
print(f'scored {ok.sum()} h, {k.date.min()}..{k.date.max()}')
F = {'IESO': k.dem_fc, 'Tesla': k.lf_tesla, 'Dynasty': k.lf_dynasty, 'Average of 3': k[LC].mean(1), 'Tesla bias-corrected': bc['lf_tesla'][ok], 'Dynasty bias-corrected': bc['lf_dynasty'][ok], 'IESO bias-corrected': bc['dem_fc'][ok], 'Ensemble (corrected + weighted)': st[ok]}
for n, f in F.items(): print(f'  {n:32s} MAE {(f - k.ont_dem).abs().mean():5.0f} | its gap vs IESO tracks IESO miss: corr {np.corrcoef(f - k.dem_fc, miss)[0,1]:.2f}')
km = k[k.lf_meteologica.notna()]
if len(km): print(f'  [Meteologica subset {km.date.min()}..: {len(km)} h] Meteologica MAE {(km.lf_meteologica-km.ont_dem).abs().mean():.0f}, corr {np.corrcoef(km.lf_meteologica-km.dem_fc, km.ont_dem-km.dem_fc)[0,1]:.2f} | ensemble MAE {(st[km.index]-km.ont_dem).abs().mean():.0f}, corr {np.corrcoef(st[km.index]-km.dem_fc, km.ont_dem-km.dem_fc)[0,1]:.2f} | IESO {(km.dem_fc-km.ont_dem).abs().mean():.0f}')
e['lens'] = st; e['lsp'] = e[LC].std(axis=1)
print('\n===== WIND (MW) =====')
WC = ['wind_fc'] + [c for c in WF if e[c].notna().mean() > 0.9]
bcw, stw = walk(WC, 'g_wind')
ok = stw.notna() & e[WC].notna().all(axis=1) & e.g_wind.notna(); k = e[ok]; wm = k.g_wind - k.wind_fc
print(f'scored {ok.sum()} h, {k.date.min()}..{k.date.max()}; ensemble members: {WC}')
G = {'IESO': k.wind_fc, 'Models median (9)': k.w_models, **{c[3:]: k[c] for c in WC[1:]}, 'Ensemble (corrected + weighted)': stw[ok]}
for n, f in G.items(): print(f'  {n:32s} MAE {(f - k.g_wind).abs().mean():5.0f} | gap vs IESO tracks IESO miss: corr {np.corrcoef(f - k.wind_fc, wm)[0,1]:.2f}')
km = k[k.wf_meteologica.notna()]
if len(km): print(f'  [Meteologica subset {km.date.min()}..: {len(km)} h] Meteologica MAE {(km.wf_meteologica-km.g_wind).abs().mean():.0f}, corr {np.corrcoef(km.wf_meteologica-km.wind_fc, km.g_wind-km.wind_fc)[0,1]:.2f} | ensemble MAE {(stw[km.index]-km.g_wind).abs().mean():.0f}, corr {np.corrcoef(stw[km.index]-km.wind_fc, km.g_wind-km.wind_fc)[0,1]:.2f} | IESO {(km.wind_fc-km.g_wind).abs().mean():.0f}')
nw = [c for c in WF if c != 'wf_meteologica']; e['wens'] = stw; e['wsp'] = e[nw].max(axis=1) - e[nw].min(axis=1)
print('\n===== DISAGREEMENT -> size of the miss and of RT-DA (East) =====')
r = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)[['date', 'he', 'rd']]
x = e.merge(r, on=['date', 'he']); x = x[x.rd.notna()]
for n, s, m in [('load forecasts spread (std of 3)', x.lsp, (x.ont_dem - x.dem_fc).abs()), ('wind models range (hi - lo)', x.wsp, (x.g_wind - x.wind_fc).abs())]:
    q = pd.qcut(s, 4, labels=['lowest 25%', '2nd', '3rd', 'highest 25%'])
    print(n); print(pd.DataFrame({'avg miss MW': m.groupby(q, observed=True).mean(), 'avg |RT-DA|': x.rd.abs().groupby(q, observed=True).mean(), 'RT $50+ above %': 100 * (x.rd >= 50).groupby(q, observed=True).mean()}).round(1).to_string())
e[['date', 'he', 'lens', 'wens', 'lsp', 'wsp']].to_csv('data/research/ensemble_fc.csv', index=False)

print('\n===== CARD P&L with a different load gap source (same thresholds, x2 in thin spare) =====')
def tier(score, read):
    s_, r_ = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s_ == r_), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s_ == r_), s_, np.where(a, 0, np.where(abs(read) >= 5, r_, 0)))
pts = lambda g: np.where(g >= 250, 2, np.where(g >= 100, 1, np.where(g <= -250, -2, np.where(g <= -100, -1, 0))))
V = e[['date', 'he', 'dem_fc', 'lf_tesla', 'lf_dynasty', 'lf_meteologica', 'lens']]
for z in ['EAST', 'OTTAWA']:
    hh = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']).merge(V.drop(columns=['dem_fc']), on=['date', 'he'], how='left', suffixes=('', '_v'))
    hh = hh[hh.date >= '2025-10-19']; m = np.where(hh.pub_sp < 2500, 2, 1); s0 = hh.score - hh['c_Load gap']; mo = hh.date.str[:7]
    vend = hh[['lf_meteologica_v', 'lf_tesla_v', 'lf_dynasty_v']].mean(axis=1)
    G = {'current (Meteologica, else Tesla)': None, 'vendor average (Meteo/Tesla/Dynasty) - IESO': vend - hh.dem_fc, 'Tesla + Dynasty average - IESO': hh[['lf_tesla_v', 'lf_dynasty_v']].mean(axis=1) - hh.dem_fc, 'ensemble - IESO': hh.lens - hh.dem_fc}
    R = {}
    for n, g in G.items():
        sc = hh.score if g is None else s0 + pts(g.fillna(0)) * m; t, sd = tier(sc, hh.read); R[n] = pd.Series(np.where(np.isin(t, ['A', 'B']), sd * hh.rd, 0), index=hh.index)
    b = R['current (Meteologica, else Tesla)']; bm = b.groupby(mo).sum(); print(f'{z} {hh.date.min()}..{hh.date.max()} current ${b.sum():,.0f}')
    for n, v in R.items():
        if n.startswith('current'): continue
        vm = v.groupby(mo).sum(); print(f'   {n:44s} ${v.sum():,.0f} ({v.sum()-b.sum():+,.0f}) | months better {(vm>bm+1).sum()}, worse {(vm<bm-1).sum()}')
