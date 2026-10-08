"""hr_test2.py -- follow-up to hr_test.py: is the IHR effect inside sells just 'tight' again? and sizing tests."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, signals_v2 as S, hr_test as H

def walk_why(e, start='2025-07-01'):
    out = pd.Series('', index=e.index)
    for D in sorted(e.date.unique()):
        if D < start: continue
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=90)).date().isoformat()
        tr = e[(e.date <= c2) & (e.date > lo) & e.sp.notna()]
        th, tg = S.best_thr(tr, 'head', S.HEAD_THR), S.best_thr(tr.dropna(subset=['gas_hat']), 'gas_hat', S.GAS_THR)
        m = e.date == D; ti = e.loc[m, 'head'] < (th or -1); su = e.loc[m, 'gas_hat'] < (tg or -1)
        out[m] = np.where(ti, 'tight', np.where(su, 'surplus', ''))
    return out

R = []
for z in ('EAST', 'OTTAWA'):
    e = pd.read_csv(C.DATA / f'dv_frame_{z}.csv'); e['sp'] = e.da - e.rt
    e['why'] = walk_why(e); dw = H.dawn_table(sorted(e.date.unique())); e['dawn'] = e.date.map(dw)
    e['ihr'] = e.p_da / e.dawn; e['ihr_p'] = H.pct_walk(e, 'ihr')
    t = e[(e.date >= '2025-09-01') & e.rt.notna()].copy()
    sell = t.why != ''; bb = ~sell & (t.buyband == -1); lo, hi = t.ihr_p < 20, t.ihr_p > 80
    for w in ('tight', 'surplus'):
        for n, m in (('cheap', lo), ('mid', ~lo & ~hi), ('rich', hi)):
            R.append(dict(zone=z, **H.sc(t, f'{w} sells, IHR {n}', np.where((t.why == w) & m, 1, 0))))
    # rich vs not, by peak/off-peak inside sells
    for n, m in (('HE7-22', t.he.between(7, 22)), ('HE1-6,23-24', ~t.he.between(7, 22))):
        R.append(dict(zone=z, **H.sc(t, f'sells {n}, IHR rich', np.where(sell & hi & m, 1, 0))))
        R.append(dict(zone=z, **H.sc(t, f'sells {n}, IHR not rich', np.where(sell & ~hi & m, 1, 0))))
    base = np.where(sell, 1.0, np.where(bb, -1.0, 0))
    for k in (1.5, 2.0):
        s = base.copy(); s[(sell & hi).values] = k; R.append(dict(zone=z, **H.sc(t, f'SIZE: live, rich sells x{k}', s)))
    s = base.copy(); s[(sell & lo).values] = 0.5; R.append(dict(zone=z, **H.sc(t, 'SIZE: live, cheap sells x0.5', s)))
    R.append(dict(zone=z, **H.sc(t, 'LIVE sells + buys', base)))
    # tight cut by IHR at higher headroom: is IHR doing more than a looser tight threshold? rich sells vs a 'head<8000' extra
    R.append(dict(zone=z, **H.sc(t, 'non-sell hours, head<8000 (compare)', np.where(~sell & (t['head'] < 8000), 1, 0))))
    R.append(dict(zone=z, **H.sc(t, 'non-sell hours, IHR rich (compare)', np.where(~sell & ~bb & hi, 1, 0))))
R = pd.DataFrame(R); R.to_csv(C.DATA / 'hr_test2_2026-10-07.csv', index=False)
pd.set_option('display.width', 200); print(R.drop(columns=['win']).to_string(index=False))
