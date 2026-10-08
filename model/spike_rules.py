"""spike_rules.py -- Oct 7 2026: candidate 'spike buy' rules from spike_study.py, evaluated as price-taker buys per MW
and as a flat bid at DA forecast + $X (clears if actual DA <= bid). Non-sell hours only. Sep 2025 -> Oct 6 2026."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, spike_study as SS
pd.set_option('display.width', 250)

def ev(m, mask, name, bid=None):
    x = m[mask].copy()
    if bid is not None: x = x[x.da <= x.p_da + bid]
    pl = x.rd; dd = pl.groupby(x.date).sum()
    H = lambda q: round(q.mean(), 2) if len(q) else np.nan
    return dict(rule=name, bid='taker' if bid is None else f'DA fc+{bid}', hours=len(x), days=x.date.nunique(), mean=H(pl), median=round(pl.median(), 1) if len(x) else np.nan,
                hit_rt_gt_da=round((pl > 0).mean() * 100) if len(x) else np.nan, spike50=round((pl >= 50).mean() * 100) if len(x) else np.nan,
                total=round(pl.sum()), H1=H(pl[x.date < '2026-02-15']), H2=H(pl[x.date >= '2026-02-15']), last90=H(pl[x.date >= '2026-07-08']),
                l90_h=int((x.date >= '2026-07-08').sum()), sep_oct=round(pl[x.date >= '2026-09-15'].sum()), worst_hr=round(pl.min()) if len(x) else np.nan, worst_day=round(dd.min()) if len(dd) else np.nan,
                pct_days_up=round((dd > 0).mean() * 100) if len(dd) else np.nan)

R = []
for z in ('EAST', 'OTTAWA'):
    m = SS.frame(z); m = m[m.rt.notna() & m.why.isna()]
    eve = m.he.between(17, 22); near = m['head'].between(7000, 8999); c10 = m.cahr >= 10; wf = m.wr3 <= -150
    rules = [('all non-sell HE17-22', eve), ('S1 HE17-22, head 7-9k', eve & near), ('S2 S1 + CAHR>=10', eve & near & c10),
             ('S3 HE17-22, CAHR>=10', eve & c10), ('S4 S1 + wind falling >150 (3h)', eve & near & wf), ('S5 S2 + wind falling', eve & near & c10 & wf),
             ('S6 S1, weekdays', eve & near & (m.wkend == 0)), ('ctrl: HE17-22 head 9k+', eve & (m['head'] >= 9000))]
    for n, k in rules:
        for b in (None, 10, 30):
            R.append(dict(zone=z, **ev(m, k, n, b)))
    # which October/late-Sep spike hours each rule caught
    sp = m[(m.date >= '2026-09-15') & (m.rd >= 40)][['date', 'he', 'rd', 'head', 'cahr', 'wr3']].copy()
    sp['S1'] = sp.he.between(17, 22) & sp['head'].between(7000, 8999); sp['S2'] = sp.S1 & (sp.cahr >= 10); sp['S3'] = sp.he.between(17, 22) & (sp.cahr >= 10)
    print(z, 'non-sell spike hours since Sep 15 and which rule caught them:'); print(sp.round(1).to_string(index=False))
R = pd.DataFrame(R); R.to_csv(C.DATA / 'spike_rules_2026-10-07.csv', index=False); print(R.to_string(index=False))
