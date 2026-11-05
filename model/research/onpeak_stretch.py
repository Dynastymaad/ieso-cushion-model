"""onpeak_stretch.py -- test only. If the DA model under-reacts to spare (high when soft, low when tight), does a walk-forward
'stretch' fix it? Per hour: corrected = q50 - predicted error, error model fit on the trailing N days (through D-1), on-peak hours, same day type."""
import numpy as np, pandas as pd
pd.set_option('display.width', 220)
def onh(d):
    s = pd.Timestamp(d + ' 17:00').tz_localize('UTC').tz_convert('America/New_York').strftime('%Z'); return (7, 22) if s == 'EDT' else (8, 23)
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)[['date', 'he', 'pub_sp', 'head', 'gas_hat', 'gas_av', 'da', 'wkend']]
q = pd.read_csv('data/bt_quantiles_EAST.csv')[['date', 'he', 'q50']]
h = h.merge(q, on=['date', 'he']).dropna(subset=['da', 'q50', 'pub_sp']); h['on'] = [onh(d)[0] <= e <= onh(d)[1] for d, e in zip(h.date, h.he)]; h = h[h.on]
h['lq'] = np.log(h.q50.clip(5)); h['lerr'] = np.log(h.q50.clip(5)) - np.log(h.da.clip(5)); h['sp'] = h.pub_sp.clip(-1000, 9000) / 1000
X = pd.read_csv('data/research/onpeak_why.csv')[['date', 'card', 'y', 'da_e', 'wk']]
res = {}
for N in (30, 60, 90):
    for form in ('spare', 'level', 'both'):
        out = []
        for D in sorted(h.date.unique()):
            if D < '2025-11-01': continue
            tD = h[h.date == D]; wk = tD.wkend.iloc[0]
            tr = h[(h.date < D) & (h.date >= (pd.Timestamp(D) - pd.Timedelta(days=int(N * 1.45))).date().isoformat()) & (h.wkend == wk)]
            tr = tr[tr.date.isin(sorted(tr.date.unique())[-N:])]
            if tr.date.nunique() < 20: continue
            cols = {'spare': ['sp'], 'level': ['lq'], 'both': ['sp', 'lq']}[form]
            A = np.c_[np.ones(len(tr)), tr[cols].values]; b = np.linalg.lstsq(A, tr.lerr.clip(-1, 1), rcond=None)[0]
            adj = np.exp(tD.lq.values - np.c_[np.ones(len(tD)), tD[cols].values] @ b)
            out.append(dict(date=D, card_adj=adj.mean(), card_raw=tD.q50.mean(), b_sp=b[1] if form != 'level' else np.nan))
        O = pd.DataFrame(out); res[(N, form)] = O
M = X.copy()
for (N, form), O in res.items(): M = M.merge(O[['date', 'card_adj']].rename(columns={'card_adj': f'{form}{N}'}), on='date', how='left')
cols = [c for c in M.columns if c[:5] in ('spare', 'level') or c.startswith('both')]
for lab, t in [('Nov-Dec 2025', M[(M.date >= '2025-11-01') & (M.date < '2026-01-01')]), ('2026 all', M[M.date >= '2026-01-01']), ('2026 weekdays', M[(M.date >= '2026-01-01') & (M.wk == 0)]), ('last 60 d', M.tail(60))]:
    t = t.dropna(subset=cols)
    print(f'\n{lab}: {len(t)} days   card MAE {(t.card - t.y).abs().mean():.2f} bias {(t.card - t.y).mean():+.2f}')
    print('   ' + ' | '.join(f"{c}: {(t[c] - t.y).abs().mean():.2f} ({(t[c] - t.y).mean():+.2f})" for c in cols))
O = res[(60, 'spare')]; print('\nfitted error per 1,000 MW of spare (log pts, 60-day, recent):', O.b_sp.tail(5).round(3).tolist(), ' mean 2026', round(O[O.date >= '2026-01-01'].b_sp.mean(), 3))
# monthly view of 'spare60' vs card
M['m'] = M.date.str[:7]; t = M[M.date >= '2026-01-01'].dropna(subset=['spare60'])
print(t.groupby('m').apply(lambda g: pd.Series(dict(card=(g.card - g.y).abs().mean(), spare60=(g.spare60 - g.y).abs().mean())), include_groups=False).round(2).T.to_string())
