"""band_fix_test.py -- Oct 9 2026 (TEST ONLY): the live buy band is learned on ALL hours, including the model's own tight
sell hours (where DA > RT), which drags 6-9k down and pushes the band up to 9.5-11.5k. Test: same live rule (daily,
trailing 120 days to D-2, 2,000 MW wide, mean DA-RT <= -3, >= 150 h) but learned and traded on NON-sell hours only."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
def run(m, L, sell, excl):
    days = sorted(m.date.unique()); pl = pd.Series(0.0, index=m.index); bands = {}
    for D in days:
        if D < '2025-10-01': continue
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=120)).date().isoformat()
        tr = m[(m.date <= c2) & (m.date > lo)]
        if excl: tr = tr[~sell[tr.index]]
        best = None
        for a in range(5000, 11001, 500):
            x = tr[(tr['head'] >= a) & (tr['head'] < a + 2000)]; s = (x.da - x.rt).mean()
            if len(x) >= 150 and s <= -3 and (best is None or s < best[1]): best = (a, s)
        if best is None: continue
        bands[D] = best[0]; k = (m.date == D) & m['head'].between(best[0], best[0] + 2000 - 1e-9) & ~sell
        pl[k] = L[k]
    return pl, bands
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv'); m = m[(m.date >= '2025-06-01') & m.rt.notna()].reset_index(drop=True)
    L = (m.rt - m.da).where(m.da <= m.p_da + 30, 0.0); sell = m.why.notna(); T = m.date >= '2025-10-01'
    print(f'\n=== {z} (trading Oct 1 2025 - {m.date.max()}) ===')
    for nm, ex in (('live rule (all hours)', False), ('non-sell hours only', True)):
        pl, b = run(m, L, sell, ex); x = pl[T]; d = x.groupby(m.date[T]).sum(); n = int((x != 0).sum())
        bs = pd.Series(b); recent = bs[bs.index >= '2026-09-01'].value_counts().to_dict()
        print(f"{nm:24s} {n:5d}h ${x[x!=0].mean():+5.1f}/MWh total {x.sum():+8,.0f} | H1 {x[m.date<'2026-02-15'].sum():+7,.0f} H2 {x[m.date>='2026-02-15'].sum():+7,.0f} | last120 {x[m.date>='2026-06-08'].sum():+6,.0f} last60 {x[m.date>='2026-08-07'].sum():+5,.0f} | w/o best3 {d.sum()-d.nlargest(3).sum():+7,.0f} | bands since Sep {recent}")
