"""Physics read (V5): expected RT-DA per hour from bid-time fundamentals, with a breakdown of what pushes it.
Ridge on standardized inputs, refit on the trailing 90 days of 2026 data through D-2. Display only - does not touch ladders.
Each piece = weight x (today's input - its 90-day average), so pieces + 'typical recent hour' = the read."""
import sys, json; sys.path.insert(0, 'model/research'); sys.path.insert(0, 'model')   # model/ first: research/ has its own true_tight.py
import pandas as pd, numpy as np
from sklearn.linear_model import Ridge
F = ['gL', 'gW', 'inv_sp', 'xL', 'xW', 'vs', 'rich', 'cheap', 'bias_L', 'bias_W', 'w3', 'g3', 'res3', 'gap_low_W', 'w_spread', 'ny_pull', 'pub_sp', 'wk', 'blk']
GROUPS = {'Load gap': ['gL', 'xL', 'bias_L'], 'Wind gap': ['gW', 'xW', 'bias_W', 'gap_low_W', 'w_spread'], 'Spare': ['inv_sp', 'pub_sp'],
          'DA priced': ['vs', 'rich', 'cheap'], 'Ramps': ['w3', 'g3', 'res3'], 'NY pull': ['ny_pull'], 'Hour/weekend': ['wk', 'blk']}

USE_STAR = False  # Nov 1 2026: starred-forecast gaps tested worse with the live daily refit (E -$5.3k, O -$4.4k/MW Sep25-Oct26), so Meteo first, then Tesla / models median
def star_sources(e):
    """Nov 1 2026: the forecast with the star (lowest mean abs miss over the 7 calendar days ending D-2, needs 3+ days),
    among those available for that day at the bid. Load: IESO / Tesla / Meteologica (Dynasty never reaches the Warehouse before
    the bid). Wind: IESO / Meteologica. Tested (research/star_gap_test.py): tiers A+B East -$3.0k, Ottawa +$4.3k vs Meteo-first
    over Sep 2025-Oct 2026, net +$1.3k/MW. Returns per-date dict {date: (load_src, wind_src)}."""
    import common as C
    a = C.actual_demand()[['date', 'he', 'ont_dem']]; f = C.fuel_actual()[['date', 'he', 'g_wind']]
    x = e[['date', 'he', 'dem_fc', 'lf_tesla', 'lf_meteologica', 'wind_fc', 'wf_meteologica']].merge(a, on=['date', 'he'], how='left').merge(f, on=['date', 'he'], how='left')
    def best(act, srcs):
        d = pd.DataFrame({k: (x[c] - x[act]).abs().groupby(x.date).mean() for k, c in srcs.items()}); d.index = pd.to_datetime(d.index); d = d.asfreq('D')
        r = d.rolling('7D', min_periods=3).mean(); r.index = r.index + pd.Timedelta(days=2); return r
    rl = best('ont_dem', {'IESO': 'dem_fc', 'Tesla': 'lf_tesla', 'Meteo': 'lf_meteologica'}); rw = best('g_wind', {'IESO': 'wind_fc', 'Meteo': 'wf_meteologica'})
    av = x.groupby('date').agg(Tesla=('lf_tesla', lambda s: s.notna().any()), MeteoL=('lf_meteologica', lambda s: s.notna().any()), MeteoW=('wf_meteologica', lambda s: s.notna().any()))
    out = {}
    for d, r in av.iterrows():
        t = pd.Timestamp(d); L = W = None
        if t in rl.index:
            ok = {k: v for k, v in rl.loc[t].items() if pd.notna(v) and (k == 'IESO' or (k == 'Tesla' and r.Tesla) or (k == 'Meteo' and r.MeteoL))}
            L = min(ok, key=ok.get) if ok else None
        if t in rw.index:
            ok = {k: v for k, v in rw.loc[t].items() if pd.notna(v) and (k == 'IESO' or (k == 'Meteo' and r.MeteoW))}
            W = min(ok, key=ok.get) if ok else None
        out[d] = (L, W)
    return out

def prep(e, bias):
    e = e.merge(bias, on=['date', 'he'], how='left').sort_values(['date', 'he']).reset_index(drop=True)
    nw = [c for c in e if c.startswith('wf_') and c != 'wf_meteologica']
    gL0 = (e.lf_meteologica - e.dem_fc).fillna(e.lf_tesla - e.dem_fc).fillna(0)                      # fallback: Meteo first, then Tesla
    gW0 = (e.wind_fc - e.wf_meteologica).fillna(e.wind_fc - e.w_models).fillna(0)                     # fallback: Meteo, then models median
    st = star_sources(e); e['load_src'] = e.date.map(lambda d: st.get(d, (None, None))[0]); e['wind_src'] = e.date.map(lambda d: st.get(d, (None, None))[1])
    lval = np.select([e.load_src == 'IESO', e.load_src == 'Tesla', e.load_src == 'Meteo'], [0.0, e.lf_tesla - e.dem_fc, e.lf_meteologica - e.dem_fc], np.nan)
    wval = np.select([e.wind_src == 'IESO', e.wind_src == 'Meteo'], [0.0, e.wind_fc - e.wf_meteologica], np.nan)
    e['gL'] = pd.Series(lval, index=e.index).fillna(gL0); e['gW'] = pd.Series(wval, index=e.index).fillna(gW0)
    if not USE_STAR: e['gL'], e['gW'] = gL0, gW0   # gap vs IESO from the starred forecast
    e['gap_low_W'] = e.wind_fc - e[nw].min(axis=1)
    e['inv_sp'] = 1000 / e.pub_sp.clip(lower=500); e['rich'] = (e.vs - 18).clip(lower=0); e['cheap'] = (-5 - e.vs).clip(lower=0)
    e['ny_pull'] = e.nyA_da - e.p_da; e['wk'] = e.wkend.astype(float); e['blk'] = pd.cut(e.he, [0, 6, 8, 15, 19, 22, 24], labels=False).astype(float)
    for c in ['bias_L', 'bias_W', 'w3', 'g3', 'res3', 'gap_low_W', 'w_spread']: e[c] = e[c].fillna(0)   # ny_pull left blank when NY DA not loaded
    for c in ['pub_sp', 'inv_sp']: e[c] = e[c].fillna(e[c].median())
    e['xL'] = e.gL * e.inv_sp; e['xW'] = e.gW * e.inv_sp
    return e

def read(e, D):
    D = pd.Timestamp(D); cut = (D - pd.Timedelta(days=2)).strftime('%Y-%m-%d'); lo = (D - pd.Timedelta(days=92)).strftime('%Y-%m-%d')
    tr = e[(e.date <= cut) & (e.date > lo) & e.rd.notna() & e.gas_hat.notna() & e.vs.notna()].dropna(subset=F)
    X = tr[F].values; mu, sd = X.mean(0), X.std(0) + 1e-9; m = Ridge(alpha=50).fit((X - mu) / sd, tr.rd.clip(-80, 150).values)
    t = e[e.date == D.strftime('%Y-%m-%d')].copy(); missing = [f for f in F if t[f].isna().any()]
    Xt = t[F].values.astype(float); Xt = np.where(np.isnan(Xt), mu, Xt)          # a missing input counts as 'typical' (adds nothing) and is flagged
    Z = (Xt - mu) / sd; C = Z * m.coef_
    out = []
    for i, (_, r) in enumerate(t.iterrows()):
        pieces = {g: round(float(sum(C[i][F.index(f)] for f in fs)), 1) for g, fs in GROUPS.items()}
        out.append(dict(he=int(r.he), read=round(float(m.intercept_ + C[i].sum()), 1), base=round(float(m.intercept_), 1), pieces=pieces,
                        inputs=dict(load_gap=round(r.gL), wind_gap=round(r.gW), load_src=r.load_src if isinstance(r.load_src, str) else None, wind_src=r.wind_src if isinstance(r.wind_src, str) else None, wind_fc=None if pd.isna(r.wind_fc) else round(r.wind_fc), pub_sp=round(r.pub_sp), vs=round(r.vs, 1), w3=round(r.w3), g3=round(r.g3), ny=None if pd.isna(r.ny_pull) else round(r.ny_pull, 1)),
                        da_fc=round(r.p_da, 1), rd=None if pd.isna(r.rd) else round(r.rd, 1)))
    return out, len(tr), missing

def ieso_bias(e):
    """IESO's own recent miss for the same hour (7-day mean, days <= D-2): load (actual - fc) and wind (fc - actual)."""
    import common as C
    a = C.actual_demand()[['date', 'he', 'ont_dem']]; f = C.fuel_actual()[['date', 'he', 'g_wind']]
    x = e[['date', 'he', 'dem_fc', 'wind_fc']].merge(a, on=['date', 'he'], how='left').merge(f, on=['date', 'he'], how='left')
    x['s_load'] = x.ont_dem - x.dem_fc; x['s_wind'] = x.wind_fc - x.g_wind; out = None
    for s, c in [('s_load', 'bias_L'), ('s_wind', 'bias_W')]:
        p = x.pivot_table(index='date', columns='he', values=s).sort_index(); p.index = pd.to_datetime(p.index)
        r = p.rolling('7D', min_periods=3).mean(); r.index = r.index + pd.Timedelta(days=2)
        b = r.stack().rename(c).reset_index(); b.columns = ['date', 'he', c]; b['date'] = b.date.dt.strftime('%Y-%m-%d'); b['he'] = b.he.astype(int)
        out = b if out is None else out.merge(b, on=['date', 'he'], how='outer')
    return out

def build(D, bundle=None):
    """Live: frame with the delivery day kept, p_da for D from the bundle when the frame lacks it."""
    import true_tight as T
    res = {'date': D, 'hubs': {}}
    for z in ('EAST', 'OTTAWA'):
        e = T.frame(z, D).sort_values(['date', 'he'])
        if bundle is not None and e.loc[e.date == D, 'p_da'].isna().all():
            H = {h['he']: h for h in bundle['hubs'][z]['hours']}; k = e.date == D; e.loc[k, 'p_da'] = e.loc[k, 'he'].map(lambda h: H.get(int(h), {}).get('p_da')).astype(float)
        e['vs'] = e.p_da - e.groupby('he').p_da.transform(lambda s: s.shift(1).rolling(14, min_periods=5).median())
        e['rd'] = e.rt - e.da
        if (e.date == D).sum() == 0: continue
        e = prep(e, ieso_bias(e)); rows, n, miss = read(e, D)
        res['hubs'][z] = dict(rows=rows, train_hours=n, missing=miss)
    return res

# ---------------- scorecard + tiers + log (Nov 1 2026; tested in research/manual_card.py + tier_test.py) ----------------
LOG = 'data/physics_read_log.csv'
def card_points(i):
    """Points a trader can add up by eye. Fixed from the physics, not fitted."""
    gL, gW, w3, sp, vs, ny = i['load_gap'], i['wind_gap'], i['w3'], i['pub_sp'], i['vs'], i['ny']
    L = 2 if gL >= 250 else 1 if gL >= 100 else -2 if gL <= -250 else -1 if gL <= -100 else 0
    W = 1 if gW >= 200 else -1 if gW <= -200 else 0
    m = 2 if sp is not None and sp < 2500 else 1
    R = -1 if w3 >= 300 else 1 if w3 <= -300 else 0
    P = -2 if vs is not None and vs >= 18 else -1 if vs is not None and vs >= 8 else 1 if vs is not None and vs <= -8 else 0
    N = 0 if ny is None else 1 if ny >= 10 else -1 if ny <= -10 else 0
    pts = {'Load gap': L * m, 'Wind gap': W * m, 'Wind ramp': R, 'DA priced': P, 'NY pull': N}
    return sum(pts.values()), pts, m == 2

def tier_of(score, read):
    s = (score > 0) - (score < 0); r = (read > 0) - (read < 0)
    if abs(score) >= 3 and s == r: return 'A', s, ('Strong long' if s > 0 else 'Strong short') + ': card and physics agree'
    if abs(score) >= 3: return 'C', 0, 'Stand aside: card and physics disagree'
    if abs(read) >= 5: return 'B', r, ('Long' if r > 0 else 'Short') + ' on the physics read'
    return 'N', 0, 'Neutral: no tested edge'

SOFT_SP, SOFT_W = 5500, 2000
def annotate(x):
    """card, tier, action and the soft-system flag for one hour row (in place)."""
    sc, pts, thin = card_points(x['inputs']); t, side, act = tier_of(sc, x['read'])
    i = x['inputs']; soft = bool(side > 0 and t in ('A', 'B') and i.get('pub_sp') is not None and i['pub_sp'] > SOFT_SP and (i.get('wind_fc') or 0) > SOFT_W)
    x.update(card=sc, card_pts=pts, thin=thin, tier=t, side=side, action=act, soft=soft)
    return x

def seed_log():
    import os
    if os.path.exists(LOG): return
    rows = []
    for z in ('EAST', 'OTTAWA'):
        f = f'data/research/physics_history_{z}.csv'
        if os.path.exists(f):
            t = pd.read_csv(f); t['zone'] = z; t['src'] = 'backtest'; rows.append(t[['date', 'zone', 'he', 'read', 'score', 'tier', 'side', 'soft', 'src']])
    if rows: pd.concat(rows).to_csv(LOG, index=False)

def track():
    """Daily log split by tier (A and B, 1 MW per hour) for the last 14 settled days, plus 14/30-day summaries and the soft-flag record."""
    import os, common as C
    if not os.path.exists(LOG): return {}
    l = pd.read_csv(LOG); p = C.prices()[['zone', 'date', 'he', 'da', 'rt']]
    if 'soft' not in l: l['soft'] = False
    l['soft'] = l.soft.fillna(False).astype(bool)
    m = l.merge(p, on=['zone', 'date', 'he'], how='inner').dropna(subset=['da', 'rt']); m['rd'] = m.rt - m.da; m['pnl'] = m.side * m.rd
    out = {}
    def tier_day(x):
        if x.empty: return None
        sd = 'long' if (x.side > 0).all() else 'short' if (x.side < 0).all() else 'mixed'
        return dict(h=int(len(x)), pnl=round(float(x.pnl.sum())), right=int((x.pnl > 0).sum()), hrs=[int(h) for h in x.he], side=sd, soft=int(x.soft.sum()))
    def summ(x, days):
        x = x[x.date.isin(days)]
        if x.empty: return dict(h=0)
        g = x.groupby('date').pnl.sum()
        return dict(h=int(len(x)), pnl=round(float(x.pnl.sum())), per=round(float(x.pnl.mean()), 2), hit=round(float((x.pnl > 0).mean()) * 100), days_up=int((g > 0).sum()), days=int(g.size))
    for z in ('EAST', 'OTTAWA'):
        k = m[m.zone == z]; k = k[k.groupby('date').he.transform('size') >= 20]
        if k.empty: continue
        dates = sorted(k.date.unique()); rows = []
        for d in dates[-14:]:
            g = k[k.date == d]; rows.append(dict(date=d, src=g.src.iloc[-1], A=tier_day(g[g.tier == 'A']), B=tier_day(g[g.tier == 'B'])))
        S = {}
        for t in ('A', 'B'):
            for n in (14, 30): S[f'{t}{n}'] = summ(k[k.tier == t], dates[-n:])
        sl = k[k.soft & k.tier.isin(['A', 'B'])]; S['soft30'] = summ(sl, dates[-30:]); S['soft_all'] = summ(sl, dates)
        if S['soft_all'].get('h'): S['soft_all']['up'] = round(float((sl.rd > 0).mean()) * 100)
        live = k[k.src == 'live']
        out[z] = dict(days=rows, summ=S, live=None if live.empty else dict(days=int(live.date.nunique()), pnl=round(float(live.pnl[live.tier.isin(['A', 'B'])].sum()))))
    return out

def build_bundle(D, bundle):
    import os
    seed_log(); r = build(D, bundle); new = []
    for z, h in r['hubs'].items():
        for x in h['rows']:
            annotate(x)
            new.append(dict(date=D, zone=z, he=x['he'], read=x['read'], score=x['card'], tier=x['tier'], side=x['side'], soft=x['soft'], src='live'))
    if new:
        old = pd.read_csv(LOG) if os.path.exists(LOG) else pd.DataFrame()
        if len(old): old = old[old.date != D]
        pd.concat([old, pd.DataFrame(new)]).to_csv(LOG, index=False)
    try: r['test'] = json.load(open('data/research/physics_tiers_test.json')); r['bands'] = json.load(open('data/research/physics_bands.json'))
    except Exception: pass
    try: r['track'] = track()
    except Exception as ex: r['track'] = {}; print('physics track skipped:', ex)
    return r

if __name__ == '__main__':
    D = sys.argv[1]; r = build(D)
    (Path := __import__('pathlib').Path)('data/research').mkdir(exist_ok=True)
    json.dump(r, open(f'data/research/physics_read_{D}.json', 'w'))
    for z, h in r['hubs'].items():
        print(z, 'trained on', h['train_hours'], 'h; missing:', h['missing'] or 'none')
        for x in h['rows']: print(f" HE{x['he']:>2} read {x['read']:+5.1f}  " + '  '.join(f"{k} {v:+.1f}" for k, v in x['pieces'].items()) + f"  | RT-DA {x['rd']}")
