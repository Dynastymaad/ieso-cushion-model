"""temp_conv.py -- Nov 5 2026: temperature -> Ontario load conversion (MW per C) by season and time of day, and the Temp swing card point.
Tested in model/research/temp_slope.py + temp_card2.py (walk-forward, Sep 2025 - Sep 2026): best of 5 rules at predicting the 2-day load change
(MAE 673 MW vs 803 for the old fixed rule) and the card point made E +$520 / O +$970 more than the old rule (8 of 13 months better on both hubs).
  heating degrees = max(15 - temp, 0)        cooling degrees = max(20 - feels-like, 0) reversed: max(feels-like - 20, 0)
  MW = heat slope x (change in heating degrees) + cool slope x (change in cooling degrees), tomorrow's forecast vs the actual 2 days earlier, same hour.
  Slopes: fitted on same-hour pairs (D vs D-2, same day type) in the complete months BEFORE the delivery month, by season x block;
  a cell with under 150 hours of that kind of weather falls back to the block across seasons, then to all hours.
Temps: Open-Meteo, Ontario load-weighted (data/wx/wx_hourly.csv via wx_live.py); forecast = run issued 2 days before the hour (bid-safe)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
BLK = [(1, 6, 'HE1-6'), (7, 10, 'HE7-10'), (11, 15, 'HE11-15'), (16, 21, 'HE16-21'), (22, 24, 'HE22-24')]
SEAS = {12: 'Winter', 1: 'Winter', 2: 'Winter', 3: 'Spring', 4: 'Spring', 5: 'Spring', 6: 'Summer', 7: 'Summer', 8: 'Summer', 9: 'Fall', 10: 'Fall', 11: 'Fall'}
MIN = 150
H = lambda t: np.clip(15 - t, 0, None); K = lambda t: np.clip(t - 20, 0, None)
def blk(he): return pd.cut(he, [0, 6, 10, 15, 21, 24], labels=[b[2] for b in BLK]).astype(str)

def frame():
    w = pd.read_csv(C.DATA / 'wx' / 'wx_hourly.csv', usecols=['date', 'he', 't_act', 'feel_act', 't_fc', 'feel_fc'])
    for c in ['t_act', 'feel_act', 't_fc', 'feel_fc']: w[c] = (w[c] - 32) * 5 / 9
    L = pd.read_csv(C.DATA / 'load_at_bid.csv', usecols=['date', 'he', 'ont_dem'])
    x = w.merge(L, on=['date', 'he'], how='left')
    d2 = x[['date', 'he', 'ont_dem', 't_act', 'feel_act']].copy(); d2['date'] = (pd.to_datetime(d2.date) + pd.Timedelta(days=2)).dt.strftime('%Y-%m-%d')
    x = x.merge(d2, on=['date', 'he'], how='left', suffixes=('', '_2'))
    dt = pd.to_datetime(x.date); x['m'] = dt.dt.strftime('%Y-%m'); x['season'] = dt.dt.month.map(SEAS); x['blk'] = blk(x.he)
    x['same'] = (dt.dt.dayofweek < 5) == (((dt.dt.dayofweek - 2) % 7) < 5)
    x['dL'] = x.ont_dem - x.ont_dem_2; x['dH'] = H(x.t_act) - H(x.t_act_2); x['dK'] = K(x.feel_act) - K(x.feel_act_2)
    x['fH'] = H(x.t_fc) - H(x.t_act_2); x['fK'] = K(x.feel_fc) - K(x.feel_act_2)
    return x

def _coef(g):
    if len(g) <= 50: return np.nan, np.nan
    b = np.linalg.lstsq(np.c_[g.dH, g.dK], g.dL, rcond=None)[0]
    return (b[0] if (g.dH != 0).sum() >= MIN else np.nan), (b[1] if (g.dK != 0).sum() >= MIN else np.nan)

def slopes(tr):
    """{(season, blk): (heat, cool, source)} plus fallbacks; heat = MW per heating degree (per C colder below 15), cool = MW per C hotter (feels-like) above 20."""
    al = _coef(tr); bl = {b: _coef(g) for b, g in tr.groupby('blk')}; out = {}
    for s in ['Winter', 'Spring', 'Summer', 'Fall']:
        for _, _, b in BLK:
            g = tr[(tr.season == s) & (tr.blk == b)]; h, c = _coef(g); src = ['season', 'season']
            if np.isnan(h): h, src[0] = (bl.get(b, al)[0] if not np.isnan(bl.get(b, al)[0]) else al[0]), 'all seasons'
            if np.isnan(c): c, src[1] = (bl.get(b, al)[1] if not np.isnan(bl.get(b, al)[1]) else al[1]), 'all seasons'
            out[(s, b)] = (float(np.nan_to_num(h)), float(np.nan_to_num(c)), tuple(src), int(((g.dH != 0)).sum()), int((g.dK != 0).sum()))
    return out

def mw_table(x=None):
    """Walk-forward MW for every hour with a bid-time forecast (slopes from complete months before the delivery month)."""
    x = frame() if x is None else x; fit = x[x.same & x.dL.notna() & x.dH.notna() & x.dK.notna()]; parts = []
    for m in sorted(x.m[x.fH.notna()].unique()):
        tr = fit[fit.m < m]
        if tr.m.nunique() < 4: continue
        S = slopes(tr); te = x[(x.m == m) & x.fH.notna() & x.fK.notna()].copy()
        te['heat'] = [S[(s, b)][0] for s, b in zip(te.season, te.blk)]; te['cool'] = [S[(s, b)][1] for s, b in zip(te.season, te.blk)]
        te['tmw'] = te.heat * te.fH + te.cool * te.fK; parts.append(te)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=['date', 'he', 'tmw'])

def point(mw): return 0 if mw is None or pd.isna(mw) else 1 if mw >= 250 else -1 if mw <= -250 else 0

def bundle(D):
    """Fundamentals tab: the conversion table in force for D (fitted through the month before) and D's 24 hours."""
    x = frame(); D = str(D)[:10]; m = D[:7]
    fit = x[x.same & x.dL.notna() & x.dH.notna() & x.dK.notna() & (x.m < m)]
    S = slopes(fit); seas = SEAS[int(D[5:7])]
    tab = [dict(season=s, rows=[dict(blk=b, heat=int(round(S[(s, b)][0] / 10) * 10), cool=int(round(S[(s, b)][1] / 10) * 10), hsrc=S[(s, b)][2][0], csrc=S[(s, b)][2][1], nh=S[(s, b)][3], nk=S[(s, b)][4]) for _, _, b in BLK])
           for s in ['Winter', 'Spring', 'Summer', 'Fall']]
    d = x[x.date == D].sort_values('he'); hrs = []
    for r in d.itertuples():
        h_, c_ = S[(r.season, r.blk)][:2]; ok = not (pd.isna(r.fH) or pd.isna(r.fK)); mw = h_ * r.fH + c_ * r.fK if ok else None
        hrs.append(dict(he=int(r.he), t_fc=None if pd.isna(r.t_fc) else round(r.t_fc, 1), feel_fc=None if pd.isna(r.feel_fc) else round(r.feel_fc, 1),
                        t_d2=None if pd.isna(r.t_act_2) else round(r.t_act_2, 1), feel_d2=None if pd.isna(r.feel_act_2) else round(r.feel_act_2, 1),
                        heat=int(round(h_)), cool=int(round(c_)), hmw=int(round(h_ * r.fH)) if ok else None, cmw=int(round(c_ * r.fK)) if ok else None, mw=None if mw is None else int(round(mw)), pt=point(mw)))
    d2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).strftime('%Y-%m-%d')
    return dict(date=D, d2=d2, season=seas, fit_through=(pd.Timestamp(m + '-01') - pd.Timedelta(days=1)).strftime('%Y-%m-%d'), table=tab, hours=hrs,
                wx_through=str(x.date[x.t_fc.notna()].max()))

if __name__ == '__main__':
    import json; D = sys.argv[1] if len(sys.argv) > 1 else json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text())['target']
    b = bundle(D); print(json.dumps(b['table'][['Winter', 'Spring', 'Summer', 'Fall'].index(b['season'])], indent=0)); print(b['hours'][:3], b['wx_through'])
    t = mw_table(); print('walk-forward rows', len(t), t.date.min(), t.date.max())
