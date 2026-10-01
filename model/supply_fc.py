"""supply_fc.py -- bid-time forecasts of the two supply pieces IESO does not forecast hour by hour for the DA:
hydro (vs the DA hydro schedule) and net exports (vs the DA intertie schedules).
Alberta-style: curve on tightness (by HE) + carry of the latest known miss, decayed; capped by physical limits.
Every fit uses only days whose DA result was public at the D-1 deadline (DA of D-1 is published D-2 13:30 EST)."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C
CARRY = 0.8   # share of yesterday's same-hour miss carried into D; set on Jun-Dec 2025, tested on 2026 (see __main__)

def hydro_frame():
    pre = C.adq2('preDA')[['date', 'he', 'dem_fc', 'nuc_av', 'wind_fc', 'solar_fc', 'hyd_av', 'hyd_energy', 'resid_fc']]
    fin = pd.read_csv(C.CACHE / 'ieso_adq2_final.csv')
    fin = fin[fin.subtype == 'Hydro Schedule'].rename(columns={'hour': 'he', 'value': 'hyd_sch'})[['date', 'he', 'hyd_sch']]
    d = pre.merge(fin, on=['date', 'he'], how='left').sort_values(['date', 'he']).reset_index(drop=True)
    d['dow'] = pd.to_datetime(d.date).dt.dayofweek; d['wk'] = (d.dow >= 5).astype(int)
    return d

def fit_curve(tr, target, x='resid_fc'):
    """per-HE linear curve target ~ a + b*x (+ weekend shift), ridge-light."""
    out = {}
    for h, g in tr.groupby('he'):
        g = g.dropna(subset=[target, x])
        if len(g) < 10: continue
        X = np.c_[np.ones(len(g)), g[x] / 1000, g.wk]; beta = np.linalg.lstsq(X.T @ X + np.diag([0, .5, .5]), X.T @ g[target].values, rcond=None)[0]
        out[h] = beta
    return out

def walk_hydro(d, win=28, start='2025-06-15', carry_k=None):
    dates = sorted(d.date.unique()); rows = []
    for D in dates:
        if D < start: continue
        last = (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat()          # D-1 DA schedule is public at the deadline
        lo = (pd.Timestamp(D) - pd.Timedelta(days=win + 1)).date().isoformat()
        tr = d[(d.date <= last) & (d.date > lo)]
        if tr.hyd_sch.notna().sum() < 200: continue
        cb = fit_curve(tr, 'hyd_sch'); x = d[d.date == D].copy()
        x['curve'] = [cb[h] @ [1, r / 1000, w] if h in cb and pd.notna(r) else np.nan for h, r, w in zip(x.he, x.resid_fc, x.wk)]
        # ratio to IESO's own hydro energy forecast, learned the same way
        k = (tr.hyd_sch / tr.hyd_energy).replace([np.inf, -np.inf], np.nan).groupby(tr.he).median()
        x['ieso_adj'] = x.hyd_energy * x.he.map(k)
        # carry: yesterday's miss of the curve, same hour
        y = d[d.date == last].set_index('he')
        yb = fit_curve(d[(d.date < last) & (d.date > lo)], 'hyd_sch')
        ycurve = pd.Series({h: yb[h] @ [1, r / 1000, w] for h, r, w in zip(y.index, y.resid_fc, y.wk) if h in yb})
        miss = (y.hyd_sch - ycurve).reindex(x.he).values
        x['miss1'] = miss
        x['carry'] = x.curve + CARRY * np.nan_to_num(miss)
        x['med14'] = x.he.map(d[(d.date <= last) & (d.date > (pd.Timestamp(D) - pd.Timedelta(days=15)).date().isoformat())].groupby('he').hyd_sch.median())
        x['blend'] = 0.5 * x.carry + 0.5 * x.ieso_adj
        x['cap'] = x.hyd_av; rows.append(x)
    r = pd.concat(rows)
    for c in ['med14', 'hyd_energy', 'ieso_adj', 'curve', 'carry', 'blend']:
        r[c] = np.minimum(r[c], r.cap)
    return r

if __name__ == '__main__' and not ({'--exports', '--wind', '--limits'} & set(sys.argv)):
    d = hydro_frame(); r = walk_hydro(d).dropna(subset=['hyd_sch'])
    fit, test = r[r.date < '2026-01-01'], r[r.date >= '2026-01-01']
    for k in [0, .2, .4, .6, .8, 1.0]:
        ef = np.minimum(fit.curve + k * fit.miss1.fillna(0), fit.cap) - fit.hyd_sch; et = np.minimum(test.curve + k * test.miss1.fillna(0), test.cap) - test.hyd_sch
        print(f'  carry {k:.1f}: fit-half MAE {ef.abs().mean():.0f}   test-half MAE {et.abs().mean():.0f}')
    print(f'hydro DA schedule, walk-forward {r.date.min()}..{r.date.max()} ({r.date.nunique()} days, {len(r)} h); mean schedule {r.hyd_sch.mean():.0f} MW')
    for c in ['med14', 'hyd_energy', 'ieso_adj', 'curve', 'carry', 'blend']:
        e = r[c] - r.hyd_sch; print(f'  {c:10s} MAE {e.abs().mean():5.0f}  bias {e.mean():+5.0f}  corr {r[[c,"hyd_sch"]].corr().iloc[0,1]:.3f}')
    r['m'] = r.date.str[:7]
    print(r.groupby('m').apply(lambda g: pd.Series({c: (g[c] - g.hyd_sch).abs().mean() for c in ['med14', 'ieso_adj', 'carry', 'blend']})).round(0).to_string())
    r.to_csv(C.DATA / 'bt_hydro_fc.csv', index=False)

# ------------------------------------------------------------------ net exports
def export_frame():
    """target: DA net exports (exports - imports, MW). Source today: Adequacy3 final (Jun 27+);
    after `pull_history.py --only adq2x` the zonal schedules from the Adequacy2 archive (May 2025+) replace it."""
    pre = C.adq2('preDA')[['date', 'he', 'resid_fc', 'dem_fc']]
    z = C.CACHE / 'ieso_adq2x_final.csv'
    if z.exists():
        f = pd.read_csv(z); f = f.rename(columns={'hour': 'he'})
        f['k'] = f.resourcetype + '|' + f.subtype
        w = f.pivot_table(index=['date', 'he'], columns='k', values='value').reset_index()
        w['da_net_exp'] = w.get('Total Exports|Schedule', 0) - w.get('Total Imports|Schedule', 0)
        w['da_ny_exp'] = w.get('Zonal Export|New York Schedule', 0) - w.get('Zonal Import|New York Schedule', 0)
        t = w[['date', 'he', 'da_net_exp', 'da_ny_exp']]
    else:
        a = pd.read_csv(C.DATA / 'adq3_final.csv'); a['da_net_exp'] = -a.exp_sch.fillna(0) - a.imp_sch.fillna(0)
        t = a[['date', 'he', 'da_net_exp']]; t['da_ny_exp'] = np.nan
    ny = pd.read_csv(C.DATA / 'nyiso_dam_energy.csv')[['date', 'he', 'ny_dni_oh']]
    d = pre.merge(t, on=['date', 'he'], how='left').merge(ny, on=['date', 'he'], how='left').sort_values(['date', 'he']).reset_index(drop=True)
    d['wk'] = (pd.to_datetime(d.date).dt.dayofweek >= 5).astype(int)
    d['rest'] = d.da_net_exp - d.ny_dni_oh.fillna(0)
    return d

def walk_exports(d, win=28, start=None, k=0.8):
    dates = sorted(d.dropna(subset=['da_net_exp']).date.unique()); start = start or dates[min(14, len(dates) - 1)]; rows = []
    for D in sorted(d.date.unique()):
        if D < start: continue
        last = (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=win + 1)).date().isoformat()
        tr = d[(d.date <= last) & (d.date > lo)]
        if tr.rest.notna().sum() < 150: continue
        cb = fit_curve(tr, 'rest'); x = d[d.date == D].copy()
        x['rest_curve'] = [cb[h] @ [1, r / 1000, w] if h in cb and pd.notna(r) else np.nan for h, r, w in zip(x.he, x.resid_fc, x.wk)]
        y = d[d.date == last].set_index('he'); yb = fit_curve(d[(d.date < last) & (d.date > lo)], 'rest')
        yc = pd.Series({h: yb[h] @ [1, r / 1000, w] for h, r, w in zip(y.index, y.resid_fc, y.wk) if h in yb})
        x['miss1'] = (y.rest - yc).reindex(x.he).values
        x['exp_fc'] = x.ny_dni_oh.fillna(0) + x.rest_curve + k * x.miss1.fillna(0)
        x['med14'] = x.he.map(d[(d.date <= last) & (d.date > (pd.Timestamp(D) - pd.Timedelta(days=15)).date().isoformat())].groupby('he').da_net_exp.median())
        rows.append(x)
    return pd.concat(rows)

def main_exports():
    d = export_frame(); r = walk_exports(d).dropna(subset=['da_net_exp'])
    print(f'\nnet exports DA schedule, walk-forward {r.date.min()}..{r.date.max()} ({r.date.nunique()} days); mean {r.da_net_exp.mean():.0f} MW')
    for c in ['med14', 'exp_fc']:
        e = r[c] - r.da_net_exp; print(f'  {c:8s} MAE {e.abs().mean():5.0f}  bias {e.mean():+5.0f}  corr {r[[c,"da_net_exp"]].corr().iloc[0,1]:.3f}')
    for kk in [0, .4, .8, 1.0]:
        e = r.ny_dni_oh.fillna(0) + r.rest_curve + kk * r.miss1.fillna(0) - r.da_net_exp; print(f'  carry {kk}: MAE {e.abs().mean():.0f}')
    r.to_csv(C.DATA / 'bt_exports_fc.csv', index=False)

if __name__ == '__main__' and '--exports' in sys.argv:
    main_exports()

# ------------------------------------------------------------------ wind vendors at bid time
def wind_at_bid():
    """Vendor wind forecasts as they stood at the D-1 08:00 MT deadline. EffectiveDateTime = EST hour-beginning."""
    f = pd.read_csv(C.CACHE / 'ieso_wind_fc.csv')
    f['eff'] = pd.to_datetime(f.EffectiveDateTime.str.slice(0, 19)); f['loaded'] = pd.to_datetime(f.DateCreated.str.slice(0, 19))
    f['issued'] = pd.to_datetime(f.Timestamp.astype(str).str.slice(0, 19))
    f['date'], f['he'] = C._ts_to_key(f.eff + pd.Timedelta(hours=1))
    dl = pd.to_datetime(f.date) - pd.Timedelta(days=1) + pd.Timedelta(hours=8)
    f = f[(f.loaded <= dl)].sort_values('issued')
    w = f.groupby(['DataSourceName', 'date', 'he']).Value.last().unstack(0)
    w.columns = ['wf_' + c.lower().replace('(', '_').replace(')', '').replace('-', '_') for c in w.columns]
    return w.reset_index()

def main_wind():
    w = wind_at_bid(); a = C.fuel_actual()[['date', 'he', 'g_wind']]
    fin = pd.read_csv(C.CACHE / 'ieso_adq2_final.csv'); fin = fin[fin.subtype == 'Wind Schedule'].rename(columns={'hour': 'he', 'value': 'wind_sch'})[['date', 'he', 'wind_sch']]
    pre = C.adq2('preDA')[['date', 'he', 'wind_fc']].rename(columns={'wind_fc': 'wf_adq2'})
    d = w.merge(a, on=['date', 'he'], how='left').merge(fin, on=['date', 'he'], how='left').merge(pre, on=['date', 'he'], how='left')
    d = d[d.date >= '2025-05-02']
    cols = [c for c in d.columns if c.startswith('wf_')]
    rows = []
    for c in cols:
        for tgt in ['g_wind', 'wind_sch']:
            x = d[[c, tgt]].dropna()
            if len(x) < 500: continue
            rows.append(dict(source=c, target=tgt, n=len(x), mae=round((x[c] - x[tgt]).abs().mean()), bias=round((x[c] - x[tgt]).mean()), corr=round(x.corr().iloc[0, 1], 3)))
    print(pd.DataFrame(rows).sort_values(['target', 'mae']).to_string(index=False))
    d.to_csv(C.DATA / 'wind_at_bid.csv', index=False)

if __name__ == '__main__' and '--wind' in sys.argv:
    main_wind()

# ------------------------------------------------------------------ live stack for the page
def live_stack(D):
    """Per-hour bid-time supply stack for delivery day D (all inputs as of D-1 08:00 MT)."""
    pre = C.adq2('preDA'); pre = pre[pre.date == D].set_index('he')
    out = pd.DataFrame(index=range(1, 25)); out.index.name = 'he'
    out['dem_ieso'] = pre.dem_fc; out['nuc'] = pre.nuc_av; out['wind_ieso'] = pre.wind_fc; out['solar'] = pre.solar_fc
    out['gas_av'] = pre.gas_av; out['hyd_av'] = pre.hyd_av; out['hyd_ieso'] = pre.hyd_energy
    lf = C.load_forecasts_at_bid(); lf = lf[lf.date == D].set_index('he')
    out['dem_tesla'] = lf.get('lf_tesla'); out['dem_meteo'] = lf.get('lf_meteologica')
    try:
        w = wind_at_bid(); w = w[w.date == D].set_index('he'); out['wind_meteo'] = w.get('wf_meteologica')
    except Exception: out['wind_meteo'] = np.nan
    try:
        h = walk_hydro(hydro_frame(), start=D); h = h[h.date == D].set_index('he'); out['hydro'] = h.carry
    except Exception: out['hydro'] = np.nan
    try:
        e = walk_exports(export_frame(), start=D, k=0.4); e = e[e.date == D].copy(); e['k'] = 0.4
        L = limits_at_bid(); e = cap_exports(e, L).set_index('he')
        out['exp_uncapped'] = e.exp_fc; out['exp'] = e.exp_fc_capped; out['exp_ny'] = e.ny_capped
    except Exception: out['exp'] = np.nan; out['exp_ny'] = np.nan
    try:   # intertie scheduling limits for D (PreDA, published D-1 ~08:08 EST) - positive MW
        L = limits_at_bid(); L = L[L.date == D].set_index('he')
        for c in ['exp_cap', 'imp_cap', 'exp_ny', 'imp_ny', 'exp_mi', 'imp_mi', 'exp_pq', 'imp_pq']:
            out['lim_' + c] = L.get(c)
        hist = limits_at_bid(); hist = hist[(hist.date < D) & (hist.date >= (pd.Timestamp(D) - pd.Timedelta(days=28)).date().isoformat())]
        norm = hist.groupby('he')[['exp_cap', 'imp_cap']].median()
        out['lim_exp_cut'] = norm.exp_cap - out.lim_exp_cap; out['lim_imp_cut'] = norm.imp_cap - out.lim_imp_cap
    except Exception: pass
    wind = out.wind_meteo.fillna(out.wind_ieso)
    out['gas_need'] = out.dem_ieso - out.nuc - wind - out.solar.fillna(0) - out.hydro + out.exp
    out['gas_need_tesla'] = out.dem_tesla - out.nuc - wind - out.solar.fillna(0) - out.hydro + out.exp
    out['spare'] = out.gas_av + out.hyd_av - (out.dem_ieso - out.nuc - out.wind_ieso.fillna(0) - out.solar.fillna(0))
    return out.reset_index()

# ------------------------------------------------------------------ intertie scheduling limits (known at the bid deadline)
# IESO Pre-DA Intertie Scheduling Limits (published D-1 ~08:08 EST). Zone codes: <IF>SIN / ...N = export limit (negative MW),
# ...X = import limit (positive). NRGStream "DA Intertie Sched Limits" are identical (checked 719 h, 100%) and carry the history.
IF_CODES = {'NY': 'NYSI', 'MI': 'MISI', 'MN': 'MNSI', 'MB': 'MBSI'}
PQ_CODES = ['PQAT', 'PQBE', 'PQDA', 'PQDZ', 'PQHA', 'PQHZ', 'PQPC', 'PQQC', 'PQSK', 'PQXY']

def limits_at_bid():
    """Wide table (date, he): exp_<IF>, imp_<IF> in positive MW for NY MI MN MB and PQ (sum of lines), plus totals.
    Sources merged, IESO file wins where both exist: data/ieso_preda_intertie_limits.csv (all zones incl. PQ),
    data/nrg/da_intertie_limits.csv (NY/MI/MN/MB history), data/nrg/da_intertie_limits_pq.csv (PQ history, if pulled)."""
    parts = []
    n = C.DATA / 'nrg' / 'da_intertie_limits.csv'
    if n.exists():
        x = pd.read_csv(n); w = x[['date', 'he']].copy()
        for k in IF_CODES:
            w[f'exp_{k.lower()}'] = -x[f'LIM_{k}_EXP']; w[f'imp_{k.lower()}'] = x[f'LIM_{k}_IMP']
        parts.append(w)
    q = C.DATA / 'nrg' / 'da_intertie_limits_pq.csv'
    if q.exists():
        x = pd.read_csv(q); w = x[['date', 'he']].copy()
        w['exp_pq'] = -x[[c for c in x if c.endswith('_EXP')]].sum(axis=1); w['imp_pq'] = x[[c for c in x if c.endswith('_IMP')]].sum(axis=1)
        parts = [parts[0].merge(w, on=['date', 'he'], how='outer')] if parts else [w]
    f = C.DATA / 'ieso_preda_intertie_limits.csv'
    if f.exists():
        x = pd.read_csv(f); p = x.pivot_table(index=['date', 'he'], columns='zone', values='mw')
        w = pd.DataFrame(index=p.index)
        for k, c in IF_CODES.items():
            if c + 'N' in p: w[f'exp_{k.lower()}'] = -p[c + 'N']; w[f'imp_{k.lower()}'] = p[c + 'X']
        pqn = [c + 'N' for c in PQ_CODES if c + 'N' in p]; pqx = [c + 'X' for c in PQ_CODES if c + 'X' in p]
        if pqn: w['exp_pq'] = -p[pqn].sum(axis=1); w['imp_pq'] = p[pqx].sum(axis=1)
        if 'MISI+NYSIN' in p: w['exp_mi_ny_joint'] = -p['MISI+NYSIN']; w['imp_mi_ny_joint'] = p['MISI+NYSIX']
        w = w.reset_index()
        if parts:
            base = parts[0].set_index(['date', 'he']); ov = w.set_index(['date', 'he'])
            base = base.reindex(base.index.union(ov.index)); base.update(ov)
            for c in ov.columns:
                if c not in base: base[c] = ov[c]
            parts = [base.reset_index()]
        else: parts = [w]
    if not parts: return pd.DataFrame(columns=['date', 'he'])
    L = parts[0]
    ex = [c for c in L if c.startswith('exp_') and 'joint' not in c]; im = [c for c in L if c.startswith('imp_') and 'joint' not in c]
    L['exp_cap'] = L[ex].sum(axis=1, min_count=len(ex)) if 'exp_pq' in L else np.nan
    L['imp_cap'] = L[im].sum(axis=1, min_count=len(im)) if 'imp_pq' in L else np.nan
    L['he'] = L.he.astype(int)
    return L

def cap_exports(x, L):
    """Alberta rule: the intertie assumption can never exceed what the wires can carry.
    NY part (from NYISO) is capped by the NY limits; the total by the sum of all limits where PQ is known."""
    x = x.merge(L, on=['date', 'he'], how='left')
    if 'exp_ny' in x:
        x['ny_capped'] = x.ny_dni_oh.clip(lower=-x.imp_ny, upper=x.exp_ny)
    else: x['ny_capped'] = x.ny_dni_oh
    tot = x.ny_capped.fillna(0) + x.rest_curve + x.k * x.miss1.fillna(0)
    x['exp_fc_capped'] = np.where(x.exp_cap.notna(), tot.clip(lower=-x.imp_cap, upper=x.exp_cap), tot)
    x['capped'] = (x.exp_fc_capped - tot).abs() > 1
    return x

def main_limits():
    L = limits_at_bid(); print('limits table', len(L), L.date.min(), L.date.max(), [c for c in L.columns][:20])
    d = export_frame(); r = walk_exports(d, k=0.4).dropna(subset=['da_net_exp']); r['k'] = 0.4
    r = cap_exports(r, L)
    for c in ['exp_fc', 'exp_fc_capped']:
        e = r[c] - r.da_net_exp; print(f'  {c:14s} MAE {e.abs().mean():5.0f} bias {e.mean():+5.0f}  n {len(r)}')
    print('  hours where the cap bound:', int(r.capped.sum()), '| NY schedule clipped:', int((r.ny_capped != r.ny_dni_oh).sum()))
    r.to_csv(C.DATA / 'bt_exports_fc.csv', index=False)

if __name__ == '__main__' and '--limits' in sys.argv:
    main_limits()
