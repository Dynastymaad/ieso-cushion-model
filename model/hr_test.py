"""hr_test.py -- Oct 7 2026: does the implied heat rate (our DA forecast / Dawn gas, both known at the bid) add edge?
IHR = p_da / Dawn (Dawn = last CVX settle for strip D struck on or before D-2). Level shifts with season, so the
rules use IHR's percentile vs the trailing 60 days, same HE, through D-2 (walk-forward, no look-ahead).
Signals rebuilt as live: v2 SELL on a 90-day threshold window, buy band on 120 days. Price-taker DA-RT per MW."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, blocks as B, signals_v2 as S, da_virtual_bt as DV

def walk_v2_90(e, start='2025-07-01'):
    out = pd.Series(0, index=e.index)
    for D in sorted(e.date.unique()):
        if D < start: continue
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=90)).date().isoformat()
        tr = e[(e.date <= c2) & (e.date > lo) & e.sp.notna()]
        th, tg = S.best_thr(tr, 'head', S.HEAD_THR), S.best_thr(tr.dropna(subset=['gas_hat']), 'gas_hat', S.GAS_THR)
        m = e.date == D; out[m] = ((e.loc[m, 'head'] < (th or -1)) | (e.loc[m, 'gas_hat'] < (tg or -1))).astype(int)
    return out

def dawn_table(dates):
    c = B.fwd_asof(B.settles(), 'CVX', 'Dawn Ontario')
    return {D: B.asof(c, pd.Timestamp(D), pd.Timestamp(D) - pd.Timedelta(days=1)) for D in dates}

def pct_walk(e, col, look=60):
    """percentile of col vs trailing `look` days, same HE, through D-2."""
    out = pd.Series(np.nan, index=e.index); g = {he: x for he, x in e.groupby('he')}
    for he, x in g.items():
        x = x.sort_values('date'); dt = pd.to_datetime(x.date).values; v = x[col].values
        for i in range(len(x)):
            hi = dt[i] - np.timedelta64(2, 'D'); lo = dt[i] - np.timedelta64(look, 'D')
            m = (dt <= hi) & (dt > lo) & ~np.isnan(v)
            if m.sum() >= 20 and not np.isnan(v[i]): out[x.index[i]] = (v[m] < v[i]).mean() * 100
    return out

def sc(t, name, side):
    """side: +1 sell, -1 buy, 0 none. P&L per MW = side*(DA-RT)."""
    x = t.assign(s=side)[lambda q: (q.s != 0) & q.sp.notna()]; pl = x.s * x.sp
    if not len(x): return dict(rule=name, hours=0)
    h1 = pl[x.date < '2026-02-15']; h2 = pl[x.date >= '2026-02-15']; l90 = pl[x.date >= '2026-07-08']
    return dict(rule=name, hours=len(x), usd_mwh=round(pl.mean(), 2), total=round(pl.sum()), H1=round(h1.mean(), 2), H2=round(h2.mean(), 2),
                last90=round(l90.mean(), 2), last90_h=len(l90), win=round((pl > 0).mean() * 100))

if __name__ == '__main__':
    R, Q = [], []
    for z in ('EAST', 'OTTAWA'):
        e = pd.read_csv(C.DATA / f'dv_frame_{z}.csv'); e['sp'] = e.da - e.rt
        e['v2'] = walk_v2_90(e)
        dw = dawn_table(sorted(e.date.unique())); e['dawn'] = e.date.map(dw)
        e['ihr'] = e.p_da / e.dawn; e['ihr_p'] = pct_walk(e, 'ihr')
        t = e[(e.date >= '2025-09-01') & e.rt.notna()].copy()
        sell, bb = t.v2 == 1, (t.v2 == 0) & (t.buyband == -1); other = (t.v2 == 0) & (t.buyband == 0)
        lo, hi = t.ihr_p < 20, t.ihr_p > 80
        rules = [('LIVE sells', np.where(sell, 1, 0)), ('LIVE buy band', np.where(bb, -1, 0)),
                 ('LIVE sells + buys', np.where(sell, 1, np.where(bb, -1, 0))),
                 ('  sells, IHR cheap (<20 pct)', np.where(sell & lo, 1, 0)), ('  sells, IHR mid', np.where(sell & ~lo & ~hi, 1, 0)),
                 ('  sells, IHR rich (>80 pct)', np.where(sell & hi, 1, 0)),
                 ('  buy band, IHR cheap', np.where(bb & lo, -1, 0)), ('  buy band, IHR mid', np.where(bb & ~lo & ~hi, -1, 0)),
                 ('  buy band, IHR rich', np.where(bb & hi, -1, 0)),
                 ('NEW: buy no-signal hours, IHR cheap', np.where(other & lo, -1, 0)),
                 ('NEW: sell no-signal hours, IHR rich', np.where(other & hi, 1, 0)),
                 ('ALT A: live, drop sells when IHR cheap', np.where(sell & ~lo, 1, np.where(bb, -1, 0))),
                 ('ALT B: live + buy cheap no-signal hours', np.where(sell, 1, np.where(bb | (other & lo), -1, 0))),
                 ('ALT C: live, buy band only if not rich', np.where(sell, 1, np.where(bb & ~hi, -1, 0))),
                 ('ALT D: live + sell rich no-signal hours', np.where(sell | (other & hi), 1, np.where(bb, -1, 0)))]
        for n, s in rules: R.append(dict(zone=z, **sc(t, n, s)))
        # descriptive: raw IHR quintiles across all hours, and by peak / off-peak
        t['q'] = pd.qcut(t.ihr_p, 5, labels=['Q1 cheap', 'Q2', 'Q3', 'Q4', 'Q5 rich'])
        for blk, m in (('all', t.he > 0), ('HE7-22', t.he.between(7, 22)), ('HE1-6,23-24', ~t.he.between(7, 22))):
            g = t[m].groupby('q', observed=True).agg(hours=('sp', 'size'), ihr=('ihr', 'median'), da_rt=('sp', 'mean'), rt_gt_da=('sp', lambda s: (s < 0).mean() * 100))
            for q, r in g.iterrows(): Q.append(dict(zone=z, block=blk, bucket=q, hours=int(r.hours), ihr_med=round(r.ihr, 1), da_minus_rt=round(r.da_rt, 2), rt_beats_da_pct=round(r.rt_gt_da)))
        print(z, 'IHR median', round(t.ihr.median(), 1), 'range', round(t.ihr.quantile(.05), 1), '-', round(t.ihr.quantile(.95), 1), 'coverage', round(t.ihr_p.notna().mean() * 100))
    R = pd.DataFrame(R); Q = pd.DataFrame(Q)
    R.to_csv(C.DATA / 'hr_test_2026-10-07.csv', index=False); Q.to_csv(C.DATA / 'hr_test_quintiles_2026-10-07.csv', index=False)
    pd.set_option('display.width', 200); print(R.to_string(index=False)); print(Q.to_string(index=False))
