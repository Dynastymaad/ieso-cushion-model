"""dv_grid.py -- single-tier limit orders priced off our bid-time forecasts, cleared on the actual DA.
Bid at price P clears if DA <= P (P&L RT-DA); offer at P clears if DA >= P (P&L DA-RT). Per MW, 17 months.
Reference prices: p_rt (RT fc), p_da (DA fc), q10/q25/q75/q90 (DA range). Split into two halves to check stability."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 250)
def one(t, side, px):
    c = (t.da <= px) if side == 'bid' else (t.da >= px)
    pl = np.where(side == 'bid', t.rt - t.da, t.da - t.rt)[c.values]
    dd = pd.Series(pl, index=t.date[c.values]).groupby(level=0).sum()
    return len(pl), (np.mean(pl) if len(pl) else np.nan), dd
def grid(t, tag):
    rows = []
    for side, refs in (('bid', [('p_rt', [.6, .7, .8, .9, 1.0]), ('p_da', [.7, .8, .9, 1.0]), ('q10', [1.0]), ('q25', [1.0])]),
                       ('offer', [('p_rt', [1.0, 1.1, 1.2, 1.3, 1.4]), ('p_da', [1.0, 1.1, 1.2, 1.3]), ('q75', [1.0]), ('q90', [1.0])])):
        for ref, ks in refs:
            for k in ks:
                px = t[ref] * k; n, m, dd = one(t, side, px)
                h1 = t.date < '2026-02-01'; n1, m1, _ = one(t[h1], side, px[h1]); n2, m2, _ = one(t[~h1], side, px[~h1])
                bs = np.random.default_rng(1); v = dd.reindex(sorted(t.date.unique()), fill_value=0).values
                ci = np.percentile([v[bs.integers(0, len(v), len(v))].sum() / max(n, 1) for _ in range(1000)], [5, 95])
                rows.append(dict(zone=tag, side=side, price=f'{k:.2f} x {ref}', clear_pct=round(n / len(t) * 100, 1), usd_mwh=round(m, 2),
                                 ci90=f'{ci[0]:+.2f}..{ci[1]:+.2f}', H1_jul_jan=round(m1, 2), H2_feb_sep=round(m2, 2), usd_day_10mw=round(n * m * 10 / t.date.nunique())))
    return pd.DataFrame(rows)
if __name__ == '__main__':
    for z in ['TORONTO', 'SOUTHWEST']:
        e = pd.read_csv(C.DATA / f'dv_frame_{z}.csv'); t = e[(e.date >= '2025-07-01')].dropna(subset=['da', 'rt', 'p_da', 'p_rt', 'q10'])
        g = grid(t, z); g.to_csv(C.DATA / f'dv_grid_{z}.csv', index=False); print(g.to_string(index=False))
        # the long side by flag: bids at 0.9 x p_rt
        print('\nbids at 0.90 x RT fc, by headroom flag:'); 
        for f, s in t.groupby('flag'):
            n, m, _ = one(s, 'bid', s.p_rt * .9); print(f'  {f or "none":14s} clears {n:5d} h ({n/len(s)*100:4.1f}%)  {m:+6.2f} $/MWh')
        print('offers at 1.10 x RT fc, by flag:')
        for f, s in t.groupby('flag'):
            n, m, _ = one(s, 'offer', s.p_rt * 1.1); print(f'  {f or "none":14s} clears {n:5d} h ({n/len(s)*100:4.1f}%)  {m:+6.2f} $/MWh')
