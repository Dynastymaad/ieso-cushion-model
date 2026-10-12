"""gauge_wire_test.py -- Oct 9 2026 (TEST ONLY): apply the short risk-reward gauge to the MODEL's sells (and add gauge longs).
Signs = Tesla >= IESO+T | IESO wind falling >= W over 3 h | gas need rising >= G over 3 h. Flat size per hour; P&L per MW.
Variants: skip sells with 2+ signs; half-size with 1 sign; drop surplus sells HE10-19; add long (DA fc + $30) on non-sell hours with 2+ signs.
Checks: halves, last 120 / 60 days, w/o best 3 days, threshold grid (robustness), both zones."""
import sys, itertools; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
d = pd.read_csv(C.DATA / 'dv_frame_EAST.csv', usecols=['date', 'he', 'gas_hat']).sort_values(['date', 'he']); d['g3'] = d.groupby('date').gas_hat.diff(3)
def load(z):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv').merge(d[['date', 'he', 'g3']], on=['date', 'he'], how='left')
    m = m[(m.date >= '2025-09-12') & m.rt.notna() & m.da.notna()].sort_values(['date', 'he']).reset_index(drop=True)
    m['sell'] = (m.why.notna()) | (m.v2 == 1); m['short'] = m.da - m.rt; m['long'] = (m.rt - m.da).where(m.da <= m.p_da + 30, 0.0)
    return m
def signs(m, T=150, W=200, G=500): return ((m.lf_tesla - m.dem_fc) >= T).astype(int) + (m.wr3 <= -W).astype(int) + (m.g3 >= G).astype(int)
def stat(pl, m):
    dd = pl.groupby(m.date).sum()
    return dict(total=pl.sum(), H1=pl[m.date < '2026-02-15'].sum(), H2=pl[m.date >= '2026-02-15'].sum(), l120=pl[m.date >= '2026-06-08'].sum(),
                l60=pl[m.date >= '2026-08-07'].sum(), wo3=dd.sum() - dd.nlargest(3).sum(), worst_day=dd.min())
def variants(m, n):
    base = m.short.where(m.sell, 0.0)
    sur_mid = m.sell & (m.why == 'surplus') & m.he.between(10, 19)
    V = {'A baseline sells': base,
         'B skip sells 2+ signs': base.where(n < 2, 0.0),
         'C B + half size 1 sign': base.where(n < 2, 0.0) * np.where(n == 1, 0.5, 1.0),
         'D drop surplus sells HE10-19': base.where(~sur_mid, 0.0)}
    V['E B + D'] = V['B skip sells 2+ signs'].where(~sur_mid, 0.0)
    V['F B + long non-sell 2+ signs'] = V['B skip sells 2+ signs'] + m.long.where(~m.sell & (n >= 2), 0.0)
    V['G E + long non-sell 2+ signs'] = V['E B + D'] + m.long.where(~m.sell & (n >= 2), 0.0)
    return V
pd.set_option('display.width', 250)
for z in ('EAST', 'OTTAWA'):
    m = load(z); n = signs(m)
    print(f'\n=== {z} (per MW, $) ===')
    print(pd.DataFrame({k: stat(v, m) for k, v in variants(m, n).items()}).T.round(0).to_string())
    # robustness grid on variant B and F: change in total & last120 vs baseline
    rows = []
    for T, W, G in itertools.product((100, 150, 250), (150, 200, 300), (400, 500, 800)):
        nn = signs(m, T, W, G); V = variants(m, nn); a = stat(V['A baseline sells'], m)
        for k in ('B skip sells 2+ signs', 'F B + long non-sell 2+ signs'):
            s = stat(V[k], m); rows.append(dict(T=T, W=W, G=G, v=k[0], d_total=s['total'] - a['total'], d_l120=s['l120'] - a['l120'], d_wo3=s['wo3'] - a['wo3'], d_worst=s['worst_day'] - a['worst_day']))
    g = pd.DataFrame(rows)
    print('threshold grid (27 combos): share of combos that beat baseline')
    print(g.groupby('v').agg(total_pos=('d_total', lambda s: (s > 0).mean()), l120_pos=('d_l120', lambda s: (s > 0).mean()), wo3_pos=('d_wo3', lambda s: (s > 0).mean()),
                             med_d_total=('d_total', 'median'), med_d_l120=('d_l120', 'median')).round(2).to_string())
