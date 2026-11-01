"""Load/wind gap from the starred (most accurate, last 7 settled days through D-2) forecast instead of always Meteologica.
If IESO itself has the star the gap is 0. Dynasty excluded (never in the Warehouse before the bid). Compare tiers A+B, walk-forward."""
import sys; sys.path.insert(0, 'model/research'); sys.path.insert(0, 'model')
import pandas as pd, numpy as np, common as C, fear_rescue as FR, physics_read_live as P
from sklearn.linear_model import Ridge
z = sys.argv[1]
def trailing_best(e, act, srcs):
    """per date: source with the lowest mean abs miss over the 7 calendar days ending D-2 (needs >=3 days)."""
    x = e[['date', 'he', act] + list(srcs.values())].copy()
    daily = {}
    for k, c in srcs.items(): daily[k] = (x[c] - x[act]).abs().groupby(x.date).mean()
    d = pd.DataFrame(daily); d.index = pd.to_datetime(d.index); d = d.asfreq('D')
    r = d.rolling('7D', min_periods=3).mean(); r.index = r.index + pd.Timedelta(days=2)
    return r
e = FR.frame(z).sort_values(['date', 'he']).reset_index(drop=True); g = e.groupby('date')
e['w3'] = e.wind_fc - g.wind_fc.shift(3); e['g3'] = e.gas_hat - g.gas_hat.shift(3); e['res3'] = e.resid_fc - g.resid_fc.shift(3)
e['vs'] = e.p_da - e.groupby('he').p_da.transform(lambda s: s.shift(1).rolling(14, min_periods=5).median()); e['rd'] = e.rt - e.da
a = C.actual_demand()[['date', 'he', 'ont_dem']]; f = C.fuel_actual()[['date', 'he', 'g_wind']]
e = e.merge(a, on=['date', 'he'], how='left').merge(f, on=['date', 'he'], how='left')
rl = trailing_best(e, 'ont_dem', {'IESO': 'dem_fc', 'Tesla': 'lf_tesla', 'Meteo': 'lf_meteologica'})
rw = trailing_best(e, 'g_wind', {'IESO': 'wind_fc', 'Meteo': 'wf_meteologica'})
dd = pd.to_datetime(e.date)
def pick(r, avail):
    out = []
    for i, d in enumerate(dd):
        row = r.loc[d] if d in r.index else None; best = None
        if row is not None:
            ok = {k: v for k, v in row.items() if pd.notna(v) and avail[k][i]}
            if ok: best = min(ok, key=ok.get)
        out.append(best)
    return out
e['starL'] = pick(rl, {'IESO': np.ones(len(e), bool), 'Tesla': e.lf_tesla.notna().values, 'Meteo': e.lf_meteologica.notna().values})
e['starW'] = pick(rw, {'IESO': np.ones(len(e), bool), 'Meteo': e.wf_meteologica.notna().values})
e = e.drop(columns=['ont_dem', 'g_wind'])
bias = P.ieso_bias(e); base = P.prep(e.copy(), bias)
star = base.copy()
lsrc = {'IESO': star.dem_fc, 'Tesla': star.lf_tesla, 'Meteo': star.lf_meteologica}
star['gL'] = [ (lsrc[s].iloc[i] - star.dem_fc.iloc[i]) if s else base.gL.iloc[i] for i, s in enumerate(star.starL)]
star['gW'] = [ (0.0 if s == 'IESO' else star.wind_fc.iloc[i] - star.wf_meteologica.iloc[i]) if s else base.gW.iloc[i] for i, s in enumerate(star.starW)]
star['xL'] = star.gL * star.inv_sp; star['xW'] = star.gW * star.inv_sp
print(z, 'load star share:', star.starL.value_counts(normalize=True).round(2).to_dict(), '| wind star share:', star.starW.value_counts(normalize=True).round(2).to_dict())
res = {}
for lab, x in [('meteo-first (now)', base), ('starred forecast', star)]:
    x = x.copy()
    x['score'] = x.apply(lambda r: P.card_points(dict(load_gap=r.gL, wind_gap=r.gW, w3=r.w3, pub_sp=r.pub_sp, vs=None if pd.isna(r.vs) else r.vs, ny=None if pd.isna(r.ny_pull) else r.ny_pull))[0], axis=1)
    x['read'] = np.nan
    for s in pd.date_range('2025-09-08', x.date.max(), freq='7D'):
        s0 = s.strftime('%Y-%m-%d'); s1 = (s + pd.Timedelta(days=6)).strftime('%Y-%m-%d'); cut = (s - pd.Timedelta(days=2)).strftime('%Y-%m-%d'); lo = (s - pd.Timedelta(days=92)).strftime('%Y-%m-%d')
        tr = x[(x.date <= cut) & (x.date > lo) & x.rd.notna()].dropna(subset=P.F); te = (x.date >= s0) & (x.date <= s1)
        if te.sum() == 0 or len(tr) < 500: continue
        X = tr[P.F].values; mu, sd = X.mean(0), X.std(0) + 1e-9; m = Ridge(alpha=50).fit((X - mu) / sd, tr.rd.clip(-80, 150).values)
        Xt = x.loc[te, P.F].values.astype(float); Xt = np.where(np.isnan(Xt), mu, Xt); x.loc[te, 'read'] = m.predict((Xt - mu) / sd)
    t = x.dropna(subset=['read', 'rd']).copy(); s_, v_ = np.sign(t.score), np.sign(t.read)
    t['tier'] = np.select([(t.score.abs() >= 3) & (s_ == v_), t.score.abs() >= 3, t.read.abs() >= 5], ['A', 'C', 'B'], 'N'); t['side'] = np.where(t.score.abs() >= 3, s_, v_)
    t['pnl'] = np.where(t.tier.isin(['A', 'B']), t.side * t.rd, 0); t['per'] = np.where(t.date < '2026-03-01', 'OUT Sep25-Feb26', 'IN Mar-Oct26')
    for per, k in t.groupby('per'):
        tr_ = k.tier.isin(['A', 'B']); A = k.tier == 'A'
        print(f'{lab:18s} {per}: A+B ${k.pnl.sum():,.0f}/MW, ${k.pnl[tr_].mean():+.2f}/MWh on {tr_.mean():.0%} h, months+ {(k.groupby(k.date.str[:7]).pnl.sum()>0).sum()}/{k.date.str[:7].nunique()} | A ${(k.side*k.rd)[A].mean():+.2f} on {A.mean():.0%} h | read all-hours ${(np.sign(k.read)*k.rd).mean():+.2f}')
    t[['date', 'he', 'score', 'read', 'tier', 'side', 'rd', 'pnl']].to_csv(f'data/research/star_{z}_{"star" if lab.startswith("starred") else "base"}.csv', index=False)
