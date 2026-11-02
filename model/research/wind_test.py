"""Nov 1 2026: better wind lean / more weight on wind ramps? Same live method (daily refit, prior 90 days through D-2, bid-time inputs),
Sep 2025 -> latest. Read variants add features; card variants change the points. Tiers A+B, 1 MW, settled RT - DA."""
import sys; sys.path.insert(0, 'model/research'); sys.path.insert(0, 'model')
import pandas as pd, numpy as np, json, common as C, fear_rescue as FR, physics_read_live as P
from sklearn.linear_model import Ridge
z = sys.argv[1]; VARS = sys.argv[2].split(',') if len(sys.argv) > 2 else None
KEEP = json.load(open('site/data/bundle.json'))['target']
e = FR.frame(z, keep=KEEP, all_rows=True).sort_values(['date', 'he']).reset_index(drop=True)
g = e.groupby('date'); e['w3'] = e.wind_fc - g.wind_fc.shift(3); e['g3'] = e.gas_hat - g.gas_hat.shift(3); e['res3'] = e.resid_fc - g.resid_fc.shift(3)
e['w6'] = e.wind_fc - g.wind_fc.shift(6)
e['vs'] = e.p_da - e.groupby('he').p_da.transform(lambda s: s.shift(1).rolling(14, min_periods=5).median()); e['rd'] = e.rt - e.da
nw = [c for c in e if c.startswith('wf_') and c != 'wf_meteologica']; e['w_lo'] = e[nw].min(axis=1); e['w_hi'] = e[nw].max(axis=1)
e['w_up'] = (e.w_hi - e.wind_fc).fillna(0); e['w_dn'] = (e.wind_fc - e.w_lo).fillna(0)                 # wind upside / downside vs IESO across 9 weather models
pw = e.wf_meteologica.fillna(e.w_models); e['wm3'] = (pw - pw.groupby(e.date).shift(3)).fillna(0)       # private (Meteo) wind ramp
e['w3up'] = e.w3.clip(lower=0).fillna(0); e['w3dn'] = e.w3.clip(upper=0).fillna(0)
# vendor own recent bias (7 days to D-2) -> bias-corrected gaps
act = C.actual_demand()[['date', 'he', 'ont_dem']].merge(C.fuel_actual()[['date', 'he', 'g_wind']], on=['date', 'he'], how='outer')
e = e.merge(act, on=['date', 'he'], how='left')
def trail(err, name):
    p = e.assign(x=err).pivot_table(index='date', columns='he', values='x'); p.index = pd.to_datetime(p.index)
    r = p.rolling('7D', min_periods=3).mean(); r.index = r.index + pd.Timedelta(days=2)
    b = r.stack().rename(name).reset_index(); b.columns = ['date', 'he', name]; b['date'] = b.date.dt.strftime('%Y-%m-%d'); b['he'] = b.he.astype(int); return b
privL = e.lf_meteologica.fillna(e.lf_tesla)
e = e.merge(trail(privL - e.ont_dem, 'vbL'), on=['date', 'he'], how='left').merge(trail(pw - e.g_wind, 'vbW'), on=['date', 'he'], how='left')
# accuracy-weighted wind estimate (IESO, Meteo/models): inverse trailing-7-day MAE weights
mI = trail((e.wind_fc - e.g_wind).abs(), 'maeI'); mP = trail((pw - e.g_wind).abs(), 'maeP')
e = e.merge(mI, on=['date', 'he'], how='left').merge(mP, on=['date', 'he'], how='left')
e = e.drop(columns=['ont_dem', 'g_wind'])
e = P.prep(e, P.ieso_bias(e))
e['vbL'] = e.vbL.fillna(0); e['vbW'] = e.vbW.fillna(0)
e['gL_bc'] = e.gL - e.vbL                                       # vendor load gap minus the vendor's own recent overshoot
wI = 1 / e.maeI.clip(lower=50).fillna(300); wP = 1 / e.maeP.clip(lower=50).fillna(300)
west = (wI * e.wind_fc + wP * (pw - e.vbW)) / (wI + wP); e['gW_ens'] = (e.wind_fc - west).fillna(e.gW)   # IESO above the blended best estimate
e['xW3'] = e.w3.fillna(0) * e.inv_sp                            # wind ramp counts more when spare is thin
e = e[e.date <= KEEP]
BASE = list(P.F)
RV = {'R0 base': BASE,
      'R1 +wind upside/downside (models)': BASE + ['w_up', 'w_dn'],
      'R2 +Meteo wind ramp, 6h ramp': BASE + ['wm3', 'w6'],
      'R3 +ramp up/down split, ramp x thin spare': BASE + ['w3up', 'w3dn', 'xW3'],
      'R4 +bias-corrected load gap': [f if f != 'gL' else 'gL_bc' for f in BASE],
      'R5 +blended wind gap': [f if f != 'gW' else 'gW_ens' for f in BASE],
      'R6 R1+R2+R3': BASE + ['w_up', 'w_dn', 'wm3', 'w6', 'w3up', 'w3dn', 'xW3']}
if VARS: RV = {k: v for k, v in RV.items() if k.split()[0] in VARS}
days = sorted(d for d in e.date.unique() if d >= '2025-09-08')
def reads(F):
    out = pd.Series(np.nan, index=e.index)
    for D in days:
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).strftime('%Y-%m-%d'); lo = (pd.Timestamp(D) - pd.Timedelta(days=92)).strftime('%Y-%m-%d')
        tr = e[(e.date <= c2) & (e.date > lo) & e.rd.notna()].dropna(subset=F)
        if len(tr) < 500: continue
        X = tr[F].values; mu, sd = X.mean(0), X.std(0) + 1e-9; m = Ridge(alpha=50).fit((X - mu) / sd, tr.rd.clip(-80, 150).values)
        k = e.date == D; Xt = e.loc[k, F].values.astype(float); Xt = np.where(np.isnan(Xt), mu, Xt); out[k] = m.predict((Xt - mu) / sd)
    return out
def card(r, v):
    L = 2 if r.gL >= 250 else 1 if r.gL >= 100 else -2 if r.gL <= -250 else -1 if r.gL <= -100 else 0
    W = 1 if r.gW >= 200 else -1 if r.gW <= -200 else 0
    thin = r.pub_sp < 2500; m = 2 if thin else 1
    w3 = 0 if pd.isna(r.w3) else r.w3
    if v == 'C1 ramp +/-2 at 600': R = -2 if w3 >= 600 else -1 if w3 >= 300 else 2 if w3 <= -600 else 1 if w3 <= -300 else 0
    elif v == 'C2 ramp doubled when thin': R = (-1 if w3 >= 300 else 1 if w3 <= -300 else 0) * m
    elif v == 'C3 ramp +/-1 at 200': R = -1 if w3 >= 200 else 1 if w3 <= -200 else 0
    elif v == 'C4 wind upside >=800 -1': R = (-1 if w3 >= 300 else 1 if w3 <= -300 else 0) + (-1 if r.w_up >= 800 else 0)
    else: R = -1 if w3 >= 300 else 1 if w3 <= -300 else 0
    vs = r.vs if pd.notna(r.vs) else 0
    Pp = -2 if vs >= 18 else -1 if vs >= 8 else 1 if vs <= -8 else 0
    N = 0 if pd.isna(r.ny_pull) else 1 if r.ny_pull >= 10 else -1 if r.ny_pull <= -10 else 0
    return (L + W) * m + R + Pp + N
def evaluate(read, sc):
    s, v = np.sign(sc), np.sign(read); t = np.select([(abs(sc) >= 3) & (s == v), abs(sc) >= 3, abs(read) >= 5], ['A', 'C', 'B'], 'N')
    side = np.where(abs(sc) >= 3, s, v); ab = np.isin(t, ['A', 'B']) & e.rd.notna().values & ~np.isnan(read)
    pnl = pd.Series(np.where(ab, side * e.rd.values, 0), index=e.index)
    o = e.date < '2026-03-01'; m = e.date.str[:7]
    oct2 = e[(e.date == '2026-10-02') & e.he.between(9, 15)].index
    return dict(total=pnl.sum(), sepfeb=pnl[o].sum(), marcto=pnl[~o].sum(), per=pnl[ab].mean(), share=ab.mean(), months=int((pnl.groupby(m).sum() > 0).sum()), nm=m.nunique(),
                oct2=pnl.loc[oct2].sum(), oct2_tiers=''.join(t[e.index.get_indexer(oct2)]))
res = {}
for name, F in RV.items():
    r = reads(F).values; sc = e.apply(lambda x: card(x, 'C0'), axis=1).values
    res[name + ' | card C0'] = evaluate(r, sc)
    if name.startswith('R0'):
        for cv in ['C1 ramp +/-2 at 600', 'C2 ramp doubled when thin', 'C3 ramp +/-1 at 200', 'C4 wind upside >=800 -1']:
            res['R0 base | ' + cv] = evaluate(r, e.apply(lambda x: card(x, cv), axis=1).values)
out = pd.DataFrame(res).T; out[['total', 'sepfeb', 'marcto', 'oct2']] = out[['total', 'sepfeb', 'marcto', 'oct2']].astype(float).round(0); out['per'] = out.per.astype(float).round(2); out['share'] = out.share.astype(float).round(2)
print(z); print(out[['total', 'sepfeb', 'marcto', 'per', 'share', 'months', 'nm', 'oct2', 'oct2_tiers']].to_string())
out.to_csv(f'data/research/wind_test_{z}_{"_".join(VARS) if VARS else "all"}.csv')
