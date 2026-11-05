"""onpeak_price.py -- Nov 4 2026 research. Pricing the Ontario Hub DA on-peak daily (XDE, HE8-23 EPT) the day before, at the 08:00 MT bid.
Target y = XDE settle for D (the DA average). Candidates, all known on the morning of D-1:
  card    = average of our hourly East P50 over the product hours (what the Next day tab shows)
  card_bc = card minus East-Ontario on-peak basis and minus the card's own error, both trailing 30 settled days through D-2
  fwd     = last XDE settle for strip D struck on or before D-2 (the market price we can see; the live quote at 07:30 MT may differ)
  blend   = the block model (bt_blocks.csv, lead 1): last DA + headroom / gas / PJM changes, blended with the forward
  fair    = walk-forward weights on (card_bc, blend, fwd), trailing 60 days through D-2
Then: P(y > strike) from the trailing 60-day error spread of 'fair', and a betting test against the forward as the strike."""
import sys, numpy as np, pandas as pd; sys.path.insert(0, 'model'); import common as C
pd.set_option('display.width', 220)
def onh(d): return (8, 23) if (pd.Timestamp(d).month in (11, 12, 1, 2, 3) and not (pd.Timestamp(d).month == 3 and pd.Timestamp(d).day >= 8) and not (pd.Timestamp(d).month == 11 and pd.Timestamp(d).day < 1)) else (7, 22)
def onh(d):
    s = pd.Timestamp(d + ' 17:00').tz_localize('UTC').tz_convert('America/New_York').strftime('%Z'); return (7, 22) if s == 'EDT' else (8, 23)
B = pd.read_csv('data/bt_blocks.csv'); B = B[(B.lead == 1) & (B.block == 'on')][['date', 'y', 'forward', 'blend', 'delta', 'persist']]
q = pd.read_csv('data/bt_quantiles_EAST.csv')[['date', 'he', 'q10', 'q50', 'q90', 'p_da', 'da']]
p = C.prices(None); p = p[p.zone.isin(['EAST', 'ONTARIO'])].pivot_table(index=['date', 'he'], columns='zone', values='da').reset_index()
rows = []
for d, g in q.groupby('date'):
    a, b = onh(d); g = g[g.he.between(a, b)]
    if len(g) < 16: continue
    pp = p[(p.date == d) & p.he.between(a, b)]
    rows.append(dict(date=d, card=g.q50.mean(), card_mean=g.p_da.mean(), card10=g.q10.mean(), card90=g.q90.mean(), east_on=g.da.mean(),
                     basis=(pp.EAST - pp.ONTARIO).mean() if len(pp) >= 16 else np.nan))
X = pd.DataFrame(rows).merge(B, on='date', how='inner').sort_values('date').reset_index(drop=True)
X = X.dropna(subset=['y'])
# walk-forward pieces using only days settled by D-2
def trail(col, D, n=30):
    cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); t = X[X.date <= cut].tail(n); return t[col].mean() if len(t) >= 10 else np.nan
X['bas30'] = [trail('basis', d) for d in X.date]
X['card_ont'] = X.card - X.bas30
X['cerr'] = X.card_ont - X.y
X['card_bc'] = [r.card_ont - trail('cerr', r.date) for r in X.itertuples()]
# fair: trailing 60-day least squares on logs of (card_bc, blend, fwd) with intercept, fallback to available
fair, sd = [], []
for i, r in X.iterrows():
    cut = (pd.Timestamp(r.date) - pd.Timedelta(days=2)).date().isoformat()
    t = X[(X.date <= cut)].tail(60).dropna(subset=['card_bc', 'blend', 'forward', 'y'])
    if len(t) < 40 or pd.isna(r.card_bc) or pd.isna(r.forward): fair.append(np.nan); sd.append(np.nan); continue
    Z = np.c_[np.log(t.card_bc.clip(5)), np.log(t.blend.clip(5)), np.log(t.forward.clip(5)), np.ones(len(t))]
    w = np.linalg.lstsq(Z, np.log(t.y.clip(5)), rcond=None)[0]
    zi = np.array([np.log(max(r.card_bc, 5)), np.log(max(r.blend, 5)), np.log(max(r.forward, 5)), 1])
    res = np.log(t.y.clip(5)) - Z @ w
    fair.append(float(np.exp(zi @ w))); sd.append(res.values)
X['fair'] = fair; X['res'] = sd
X['yr'] = np.where(X.date < '2026-01-01', '2025', '2026')
M = ['card', 'card_ont', 'card_bc', 'forward', 'blend', 'fair']
for yr in ('2026', '2025'):
    x = X[(X.yr == yr) & X.fair.notna()]
    print(f'\n== {yr}: {len(x)} days, XDE on-peak settle, $ (forecast - actual) ==')
    print(pd.DataFrame({m: dict(bias=round((x[m] - x.y).mean(), 2), MAE=round((x[m] - x.y).abs().mean(), 2), med_err=round((x[m] - x.y).median(), 2),
                                over=round(((x[m] - x.y) > 0).mean() * 100)) for m in M}).T.to_string())
    print('card P10-P90 band holds the settle', round(((x.y >= x.card10 - x.bas30) & (x.y <= x.card90 - x.bas30)).mean() * 100), '% (should be ~80)')
    print('mean East-Ontario on-peak basis', round(x.basis.mean(), 2), '| card mean vs median', round((x.card_mean - x.card).mean(), 2))
# probability and betting vs the forward as strike
out = []
for r in X[X.fair.notna()].itertuples():
    k = r.forward; pr = float((np.exp(np.log(r.fair) + r.res) > k).mean())
    out.append(dict(date=r.date, yr=r.yr, p_above=pr, edge=r.fair - k, pnl_long=(r.y - k) * 16))
P = pd.DataFrame(out)
print('\n== calibration: predicted P(settle > forward) vs what happened ==')
P['bin'] = pd.cut(P.p_above, [0, .2, .35, .5, .65, .8, 1]); P['hit'] = (P.pnl_long > 0)
print(P.groupby('bin', observed=True).agg(days=('hit', 'size'), said=('p_above', 'mean'), happened=('hit', 'mean')).round(2).to_string())
print('\n== betting vs the forward (1 MW x 16 h, $/day). Long when P(above) >= t, short when <= 1-t ==')
for yr in ('2026', '2025', 'all'):
    x = P if yr == 'all' else P[P.yr == yr]
    for t in (.55, .6, .65, .7):
        s = np.where(x.p_above >= t, 1, np.where(x.p_above <= 1 - t, -1, 0)); pnl = s * x.pnl_long; n = (s != 0).sum()
        mo = pd.Series(pnl.values, index=x.date.str[:7]).groupby(level=0).sum()
        print(f'{yr} t={t}: days {n:3d}/{len(x)}  total ${pnl.sum():8.0f}  per trade ${pnl[s != 0].mean() if n else 0:6.1f}  hit {((pnl > 0)[s != 0]).mean() * 100 if n else 0:4.0f}%  months up {(mo > 0).sum()}/{(mo != 0).sum()}')
    s = np.sign(x.edge); pnl = s * x.pnl_long; print(f'{yr} always side with fair vs forward: total ${pnl.sum():.0f}, hit {(pnl > 0).mean() * 100:.0f}%')
X.drop(columns='res').to_csv('data/research/onpeak_price.csv', index=False)
