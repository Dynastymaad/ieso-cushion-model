"""onpeak_why.py -- Nov 4 2026 research, nothing wired. Why does the on-peak card run high on weekday mid/high-price days?
(A) hourly error of our DA median (East) by bid-time spare / headroom / gas need
(B) does the last 7 days' error carry into tomorrow?  (DA for D-1 is published D-2, so it is known at the D-1 bid)
(C) a '7-day curve': price each hour of D off the last 7 days' DA-vs-spare relationship (on-peak hours, D-7..D-1)"""
import sys, numpy as np, pandas as pd; sys.path.insert(0, 'model'); import common as C
pd.set_option('display.width', 220)
def onh(d):
    s = pd.Timestamp(d + ' 17:00').tz_localize('UTC').tz_convert('America/New_York').strftime('%Z'); return (7, 22) if s == 'EDT' else (8, 23)
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False)[['date', 'he', 'pub_sp', 'head', 'gas_hat', 'gas_av', 'dem_fc', 'wind_fc', 'da', 'da_fc', 'wkend']]
q = pd.read_csv('data/bt_quantiles_EAST.csv')[['date', 'he', 'q50', 'p_da', 'da_y']]
h = h.merge(q, on=['date', 'he'], how='inner').dropna(subset=['da', 'q50'])
h['on'] = [onh(d)[0] <= e <= onh(d)[1] for d, e in zip(h.date, h.he)]
h['err'] = h.q50 - h.da; h['util'] = h.gas_hat / h.gas_av
x = h[(h.date >= '2026-01-01') & h.on & (h.wkend == 0)]
print('== (A) 2026 weekday on-peak hours, East: our DA median minus actual DA ==')
for col, bins in [('pub_sp', [-9e9, 1500, 2500, 3500, 4500, 5500, 7000, 9e9]), ('head', [0, 5000, 6500, 8000, 9500, 11000, 99999]), ('util', [-9, .4, .5, .6, .7, .8, 9])]:
    t = x.groupby(pd.cut(x[col], bins), observed=True).agg(hrs=('err', 'size'), da=('da', 'mean'), fc=('q50', 'mean'), err=('err', 'mean'), med=('err', 'median'), above=('err', lambda s: (s > 0).mean() * 100)).round(1)
    print(f'-- by {col}'); print(t.to_string())
print('-- by month (weekday on-peak)'); print(x.groupby(x.date.str[:7]).agg(err=('err', 'mean'), med=('err', 'median'), above=('err', lambda s: (s > 0).mean() * 100), sp=('pub_sp', 'mean')).round(1).to_string())
# daily on-peak (product) frame
X = pd.read_csv('data/research/onpeak_price.csv')[['date', 'card', 'y', 'persist']]
d = h[h.on].groupby('date').agg(card_e=('q50', 'mean'), da_e=('da', 'mean'), sp=('pub_sp', 'mean'), spmin=('pub_sp', 'min'), head=('head', 'mean'), wk=('wkend', 'max')).reset_index()
X = X.merge(d, on='date', how='inner').sort_values('date').reset_index(drop=True); X['err'] = X.card - X.y
print('\n== (B) does recent error carry into tomorrow? (product = XDE on-peak settle; errors through D-1 are known at the bid) ==')
for n in (1, 3, 7, 14, 30):
    X[f'e{n}'] = [X[(X.date < r.date)].tail(n).err.mean() if (X.date < r.date).sum() >= n else np.nan for r in X.itertuples()]
    t = X[X.date >= '2026-01-01'].dropna(subset=[f'e{n}'])
    print(f'trailing {n:2d} d mean error vs tomorrow\'s error: corr {t[[f"e{n}", "err"]].corr().iloc[0, 1]:+.2f}   (same day type only: {t[t.wk == 0][[f"e{n}", "err"]].corr().iloc[0, 1]:+.2f} weekdays)')
print('\n== (C) 7-day curve: each on-peak hour of D priced off DA vs public spare over the last 7 days (on-peak hours, D-7..D-1, same day type) ==')
H = h[h.on].copy(); H['lda'] = np.log(H.da.clip(5)); rows = []
for D in sorted(H.date.unique()):
    if D < '2025-10-01': continue
    tD = H[H.date == D]; wk = tD.wkend.iloc[0]
    past = H[(H.date < D) & (H.date >= (pd.Timestamp(D) - pd.Timedelta(days=10)).date().isoformat()) & (H.wkend == wk)]
    past = past[past.date.isin(sorted(past.date.unique())[-7:])]
    if past.date.nunique() < 3: continue
    A = np.c_[np.ones(len(past)), past.pub_sp / 1000, past.dem_fc / 1000]; b = np.linalg.lstsq(A, past.lda, rcond=None)[0]
    pr = np.exp(np.c_[np.ones(len(tD)), tD.pub_sp / 1000, tD.dem_fc / 1000] @ b)
    rows.append(dict(date=D, curve7=pr.mean(), slope_per_GW=b[1], lvl7=past.da.mean()))
Cv = pd.DataFrame(rows); X = X.merge(Cv, on='date', how='left')
X['basis7'] = [X[(X.date < r.date)].tail(7).pipe(lambda t: (t.da_e - t.y).mean()) for r in X.itertuples()]   # East minus product, last 7 settled
X['curve7_p'] = X.curve7 - X.basis7
X['mix'] = 0.5 * X.card + 0.5 * X.curve7_p
X['card_e7'] = X.card - X.e7
for lab, t in [('2026 all', X[X.date >= '2026-01-01']), ('2026 weekdays', X[(X.date >= '2026-01-01') & (X.wk == 0)]), ('Oct 2025-Dec 2025', X[X.date < '2026-01-01']), ('last 60 d', X.tail(60))]:
    t = t.dropna(subset=['curve7_p', 'e7'])
    print(f'{lab:18s} days {len(t):3d} | ' + ' | '.join(f"{m}: MAE {(t[m] - t.y).abs().mean():5.2f} bias {(t[m] - t.y).mean():+5.2f}" for m in ['card', 'card_e7', 'curve7_p', 'mix', 'persist']))
X.to_csv('data/research/onpeak_why.csv', index=False)
