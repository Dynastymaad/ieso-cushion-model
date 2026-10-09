"""cheap_da.py -- Oct 8 2026: when our DA forecast is cheap, is selling still right, or is buying +EV?
Per MW, price-taker and at a buy bid of DA fc + $30. Sep 2025 -> Oct 6 2026, East and Ottawa. Sell = live tight/surplus rule."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 250)
def stats(x, side, name):
    pl = side * (x.da - x.rt); dd = pl.groupby(x.date).sum()
    H = lambda q: round(q.mean(), 1) if len(q) else np.nan
    return dict(group=name, hours=len(x), days=x.date.nunique(), per_mwh=H(pl), median=round(pl.median(), 1) if len(x) else np.nan, win=round((pl > 0).mean() * 100) if len(x) else np.nan,
                big_win50=round((pl >= 50).mean() * 100, 1) if len(x) else np.nan, big_loss50=round((pl <= -50).mean() * 100, 1) if len(x) else np.nan,
                H1=H(pl[x.date < '2026-02-15']), H2=H(pl[x.date >= '2026-02-15']), last90=H(pl[x.date >= '2026-07-08']), ex_top5days=round(pl.sum() - dd.nlargest(5).sum()) if len(dd) else np.nan)
R = []
for z in ('EAST', 'OTTAWA'):
    f = pd.read_csv(C.DATA / f'cahr_frame_{z}.csv'); f = f[f.date <= '2026-10-06'].dropna(subset=['da', 'rt', 'p_da'])
    f['band'] = pd.cut(f.p_da, [-99, 40, 50, 60, 75, 999], labels=['<40', '40-50', '50-60', '60-75', '75+'])
    sell = f.why.notna(); tight = f.why == 'tight'
    for b in ['<40', '40-50', '50-60', '60-75', '75+']:
        x = f[(f.band == b)]
        R.append(dict(zone=z, **stats(x[sell[x.index]], 1, f'SELL (live) | DA fc {b}')))
        R.append(dict(zone=z, **stats(x[sell[x.index]], -1, f'  if BOUGHT instead | DA fc {b}')))
        y = x[~sell[x.index]]; R.append(dict(zone=z, **stats(y, -1, f'BUY non-sell hours | DA fc {b}')))
R = pd.DataFrame(R); R.to_csv(C.DATA / 'cheap_da_2026-10-08.csv', index=False); print(R.to_string(index=False))
