"""boost_test.py -- should the x1.5 'trips in the last 24 h' boost apply to all score-5 sells, or only the TIGHT ones?
No new parameter: 'tight' is the v2 signal's own branch (headroom below the threshold v2 learned that day on trailing
spreads through D-2), 'surplus' is its other branch (gas need below its learned threshold). Same VA ladders, same
clearing (bid clears if DA <= price, offer if DA >= price, settled at RT), Jul 2025 - Sep 2026, both hubs.
Hindsight guard: the choice is judged on Jul 2025 - Jan 2026 only, then checked untouched on Feb - Sep 2026."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, signals_v2 as S, da_virtual_bt as DV, fail_fix as FF
pd.set_option('display.width', 250)
rng = np.random.default_rng(5)

def branch(e, start='2025-07-01'):
    """re-run walk_v2 keeping which branch fired (identical thresholds to da_virtual_bt.walk_v2)."""
    out = pd.Series('', index=e.index)
    for D in sorted(e.date.unique()):
        if D < start: continue
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=120)).date().isoformat()
        tr = e[(e.date <= c2) & (e.date > lo) & e.sp.notna()]
        th, tg = S.best_thr(tr, 'head', S.HEAD_THR), S.best_thr(tr.dropna(subset=['gas_hat']), 'gas_hat', S.GAS_THR)
        m = e.date == D; tight = e.loc[m, 'head'] < (th or -1); surp = e.loc[m, 'gas_hat'] < (tg or -1)
        out[m] = np.where(tight, 'tight', np.where(surp, 'surplus', ''))
    return out

def frame(zone):
    e = pd.read_csv(C.DATA / 'of_frame.csv')
    if zone == 'SOUTHWEST':
        sw = pd.read_csv(C.DATA / f'dv_frame_{zone}.csv')[['date', 'he', 'sp', 'rt', 'da', 'v2', 'buyband', 'p_da', 'p_rt']]
        e = e.drop(columns=['sp', 'rt', 'da', 'v2', 'buyband', 'p_da', 'p_rt']).merge(sw, on=['date', 'he'])
    e = e.sort_values(['date', 'he']).reset_index(drop=True); e['branch'] = branch(e)
    return e

def run(e, mode, thr=500):
    t = e[(e.date >= '2025-07-01')].dropna(subset=['da', 'rt', 'p_da', 'p_rt']).copy()
    t['sc'] = np.where(t.v2 == 1, 5, np.where(t.buyband == -1, 1, 3))
    rows = []
    for r in t.itertuples():
        b, s_ = DV.ladder(int(r.sc), r.p_da, r.p_rt)
        trip = (r.trips_d1 if not pd.isna(r.trips_d1) else 0) >= thr
        k = 1.5 if (r.sc == 5 and trip and (mode == 'all' or (mode == 'tight' and r.branch == 'tight'))) else 1.0
        mb = sum(q * k for q, p in b if p is not None and r.da <= p); ms = sum(q * k for q, p in s_ if p is not None and r.da >= p)
        rows.append((r.date, mb + ms, mb * (r.rt - r.da) + ms * (r.da - r.rt)))
    x = pd.DataFrame(rows, columns=['date', 'mw', 'pl']); d = x.groupby('date').pl.sum()
    cum = d.cumsum(); dd = (cum - cum.cummax()).min()
    return d, dict(net=round(d.sum()), made=round(d[d > 0].sum()), lost=round(d[d < 0].sum()), usd_mwh=round(x.pl.sum() / x.mw.sum(), 2),
                   worst_day=round(d.min()), p5_day=round(d.quantile(.05)), days_lt_50k=int((d < -50000).sum()), max_drawdown=round(dd))

if __name__ == '__main__':
    for z in ['TORONTO', 'SOUTHWEST']:
        e = frame(z); e.to_csv(C.DATA / f'bt_boost_frame_{z}.csv', index=False)
        s = e[(e.v2 == 1) & e.sp.notna() & (e.date >= '2025-07-01')]; b = s.trips_d1 >= 500
        print(f'\n===== {z} =====  v2 SELL hours by branch: {s.branch.value_counts().to_dict()}')
        for half, m in (('Jul-Jan (decide)', s.date < '2026-02-01'), ('Feb-Sep (check)', s.date >= '2026-02-01')):
            for br in ('tight', 'surplus'):
                v = s[m & b & (s.branch == br)]; w = s[m & ~b & (s.branch == br)]
                lo, hi = FF.boot(v.sp.values, v.date.values) if len(v) > 20 else (np.nan, np.nan)
                print(f'  {half:17s} {br:8s} trips>=500: h {len(v):4d} DA-RT {v.sp.mean():+7.2f} ({lo:+.2f}..{hi:+.2f}) | trips<500: h {len(w):4d} {w.sp.mean():+6.2f}')
        R = []
        for mode in ('none', 'all', 'tight'):
            d, r = run(e, mode); r['boost'] = mode; R.append(r)
            h2 = d[d.index >= '2026-02-01']; r['net_Feb_Sep'] = round(h2.sum()); r['worst_Feb_Sep'] = round(h2.min())
        print(pd.DataFrame(R)[['boost', 'net', 'made', 'lost', 'usd_mwh', 'worst_day', 'p5_day', 'days_lt_50k', 'max_drawdown', 'net_Feb_Sep', 'worst_Feb_Sep']].to_string(index=False))
        print('  threshold robustness (tight-only vs all), net:')
        for thr in (250, 500, 750, 1000):
            print(f'    trips >= {thr}: all {run(e, "all", thr)[1]["net"]:,}  tight-only {run(e, "tight", thr)[1]["net"]:,}  none {R[0]["net"]:,}')
