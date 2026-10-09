"""mid_band_test.py -- Oct 9 2026 (TEST ONLY): go long when headroom is 7,000-9,000 (no sell signal there).
Fill: long bid at our DA forecast + $30 (filled if DA <= bid). P&L = RT - DA per MW. Checks: halves, last 120 days,
last 60 days, without best 3 days, placebo (random hours, same count per month), sub-bands, by segment; buy band and
tight sells side by side for comparison. Both zones."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
RNG = np.random.default_rng(11)
def stats(pl, m, base=None, k=None, plc=True):
    d = pl.groupby(m.date).sum(); x = pl[k] if k is not None else pl
    out = f"{int(k.sum()) if k is not None else len(pl):5d}h ${x.mean():+6.1f}/MWh win {100*(x>0).mean():3.0f}% total {pl.sum():+8,.0f} | H1 {pl[m.date<'2026-02-15'].sum():+7,.0f} H2 {pl[m.date>='2026-02-15'].sum():+7,.0f} | last120 {pl[m.date>='2026-06-08'].sum():+7,.0f} last60 {pl[m.date>='2026-08-07'].sum():+6,.0f} | w/o best3 days {d.sum()-d.nlargest(3).sum():+7,.0f}"
    if plc and base is not None:
        cnt = k[k].groupby(m.date[k].str[:7]).size(); pb = []
        for _ in range(800):
            s = 0.0
            for mo, c in cnt.items():
                v = base[m.date.str[:7] == mo].values; s += v[RNG.choice(len(v), min(c, len(v)), replace=False)].sum()
            pb.append(s)
        out += f" | beats placebo {(np.array(pb) < pl.sum()).mean()*100:3.0f}%"
    return out
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv'); m = m[(m.date >= '2025-09-12') & m.rt.notna()].reset_index(drop=True)
    m['rd'] = m.rt - m.da; fill = m.da <= m.p_da + 30; L = m.rd.where(fill, 0.0); sell = m.why.notna()
    H = m['head']; ev = m.he.between(16, 21)
    print(f'\n========== {z} ({m.date.min()} to {m.date.max()}) ==========')
    print('LONG, headroom 7-9k, not a sell hour')
    for nm, k in [('all hours', H.between(7000, 9000) & ~sell), ('evening HE16-21', H.between(7000, 9000) & ~sell & ev),
                  ('other hours', H.between(7000, 9000) & ~sell & ~ev), ('  7-8k', H.between(7000, 8000) & ~sell), ('  8-9k', H.between(8000, 9000) & ~sell),
                  ('  7-8k evening', H.between(7000, 8000) & ~sell & ev)]:
        print(f'  {nm:18s}', stats(L.where(k, 0), m, L, k))
    print('For comparison')
    bb = H.between(9500, 11500); print(f"  {'LONG buy band':18s}", stats(L.where(bb, 0), m, L, bb))
    sp = (m.da - m.rt).where(sell, 0); print(f"  {'SELL tight (model)':18s}", stats(sp, m, None, sell, plc=False))
    spe = (m.da - m.rt).where(sell & ev, 0); print(f"  {'SELL tight evening':18s}", stats(spe, m, None, sell & ev, plc=False))
    # walk-forward: each month, pick the 1,000-MW band (from 6-10k) that paid best for longs over the prior 120 days, trade it next month
    mo = sorted(m.date.str[:7].unique()); tot = 0; rows = []
    for i, M in enumerate(mo):
        start = (pd.Timestamp(M + '-01') - pd.Timedelta(days=120)).date().isoformat()
        tr = m[(m.date < M + '-01') & (m.date >= start) & ~sell]
        if tr.date.nunique() < 60: continue
        best = max(range(6000, 10000, 500), key=lambda lo: L[tr.index][tr['head'].between(lo, lo + 1000)].mean())
        te = (m.date.str[:7] == M) & H.between(best, best + 1000) & ~sell; p = L[te].sum(); tot += p; rows.append(f'{M}:{best//100/10:.1f}k {p:+.0f}')
    print('  walk-forward band (chosen on prior 120 days):', tot.__round__(0), '|', ' '.join(rows))
