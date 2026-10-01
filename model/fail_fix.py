"""fail_fix.py -- test bid-time fixes for the losing SELL days (fail_study.py). Nothing here uses post-deadline data.
Each candidate is a VETO (drop the SELL) and, separately, a FLIP (buy instead). Scored on v2 SELL hours, 17 months,
both hubs, by half (Jul 25-Jan 26 / Feb-Sep 26), 90% bootstrap by day. A fix passes only if the vetoed hours lost money
with the whole 90% range below zero AND both halves agree AND both hubs agree."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, supply_fc as SF
pd.set_option('display.width', 260); pd.set_option('display.max_rows', 200)
rng = np.random.default_rng(11)

def add_features(e):
    l = pd.read_csv(C.CACHE / 'ieso_adq2_leads.csv'); l = l[l.lead == 2]
    k = {'Gas Outage': 'l2_gas_out', 'Nuclear Outage': 'l2_nuc_out', 'Forecast': 'l2_dem', 'Wind Forecast': 'l2_wind'}
    l = l[l.subtype.isin(k)].pivot_table(index=['date', 'hour'], columns='subtype', values='value').rename(columns=k).reset_index().rename(columns={'hour': 'he'})
    e = e.drop(columns=[c for c in l.columns if c.startswith('l2_') and c in e], errors='ignore').merge(l, on=['date', 'he'], how='left')
    e['out_trend'] = (e.gas_out - e.l2_gas_out) + (e.nuc_out - e.l2_nuc_out)          # outages added between D-2 and the bid
    e['dem_trend'] = e.dem_fc - e.l2_dem
    w = SF.wind_at_bid(); w['vend'] = w[['wf_frontier', 'wf_gem_cmc', 'wf_gfs', 'wf_nam']].mean(axis=1)
    e = e.merge(w[['date', 'he', 'vend', 'wf_meteologica']], on=['date', 'he'], how='left')
    e['wind_gap'] = e.vend - e.wind_fc; e['met_gap'] = e.wf_meteologica - e.wind_fc
    e['nyx'] = e.nyA_da - e.p_da; e['dynT'] = e.lf_dynasty - e.dem_fc
    # yesterday-known: D-2 same-hour spread and D-2 daily mean spread
    d2 = e.groupby('date').sp.mean().rename('sp_day'); d2.index = (pd.to_datetime(d2.index) + pd.Timedelta(days=2)).date.astype(str)
    e = e.merge(d2.rename('sp_day_d2').reset_index().rename(columns={'index': 'date'}), on='date', how='left')
    return e

def boot(pl, dates, n=2000):
    g = pd.DataFrame({'d': dates, 'p': pl}).groupby('d').p.agg(['sum', 'count']); k = len(g)
    if k < 5: return np.nan, np.nan
    s, c = g['sum'].values, g['count'].values
    r = [s[i].sum() / c[i].sum() for i in (rng.integers(0, k, k) for _ in range(n))]
    return tuple(np.percentile(r, [5, 95]))

CANDS = {
  'Tesla load >= IESO (gap >= 0)':           lambda s: s.gapT >= 0,
  'Tesla load >= IESO + 300':                lambda s: s.gapT >= 300,
  'Dynasty load >= IESO':                    lambda s: s.dynT >= 0,
  'Tesla AND Dynasty >= IESO':               lambda s: (s.gapT >= 0) & (s.dynT >= 0),
  'IESO demand fc raised 300+ since D-2':    lambda s: s.dem_trend >= 300,
  'Outages added 300+ between D-2 and bid':  lambda s: s.out_trend >= 300,
  'Vendor wind 300+ below IESO wind':        lambda s: s.wind_gap <= -300,
  'Meteologica wind 300+ below IESO':        lambda s: s.met_gap <= -300,
  'NY Zone A >= our DA fc + $10':            lambda s: s.nyx >= 10,
  'NY Zone A >= our DA fc + $20':            lambda s: s.nyx >= 20,
  'Bid headroom < 2,000 (scarcity)':         lambda s: s['head'] < 2000,
  'Bid headroom < 3,000':                    lambda s: s['head'] < 3000,
  'RT beat DA same HE two days ago (by $10)': lambda s: s.sp_d2 <= -10,
  'D-2 day mean RT beat DA':                 lambda s: s.sp_day_d2 < 0,
  'Hot: yesterday >= 85F':                   lambda s: s.temp_d1 >= 85,
  'Cold: yesterday <= 20F':                  lambda s: s.temp_d1 <= 20,
  'Surplus sell with DA fc < $25':           lambda s: (s['head'] >= 8000) & (s.p_da < 25),
  'Evening peak HE17-21':                    lambda s: s.he.between(17, 21),
}

def test(zone):
    e = add_features(pd.read_csv(C.DATA / f'fs_frame_{zone}.csv'))
    s = e[(e.v2 == 1) & e.sp.notna()].copy(); base = s.sp.mean(); h1 = s.date < '2026-02-01'
    rows = [dict(fix='(baseline v2 SELL)', hours=len(s), vetoed_mean=np.nan, veto_ci='', H1=round(s.sp[h1].mean(), 2), H2=round(s.sp[~h1].mean(), 2),
                 sell_after=round(base, 2), total_after=round(s.sp.sum()), gain_vs_base=0)]
    for n, f in CANDS.items():
        m = f(s).fillna(False).values; v = s[m]
        if len(v) < 20: rows.append(dict(fix=n, hours=len(v))); continue
        lo, hi = boot(v.sp.values, v.date.values); keep = s[~m]
        rows.append(dict(fix=n, hours=len(v), days=v.date.nunique(), vetoed_mean=round(v.sp.mean(), 2), veto_ci=f'{lo:+.2f}..{hi:+.2f}',
                         H1=round(v.sp[v.date < '2026-02-01'].mean(), 2), H2=round(v.sp[v.date >= '2026-02-01'].mean(), 2),
                         sell_after=round(keep.sp.mean(), 2), total_after=round(keep.sp.sum()), gain_vs_base=round(keep.sp.sum() - s.sp.sum()),
                         flip_total=round(keep.sp.sum() - v.sp.sum())))
    R = pd.DataFrame(rows); R.insert(0, 'zone', zone); return R, e

if __name__ == '__main__':
    out = []
    for z in ['TORONTO', 'SOUTHWEST']:
        R, e = test(z); out.append(R); e.to_csv(C.DATA / f'fs_frame_{z}.csv', index=False)
        print(R.to_string(index=False))
    pd.concat(out).to_csv(C.DATA / 'fs_fixes.csv', index=False)

def sell_ladder_test(zone):
    """Score-5 offer ladder on v2 SELL hours: VA tiers (max(.98 DA fc, RT fc), RT fc, RT fc + 5) vs offers priced on our DA range.
    MW 20/30/40 per tier as the VA Hub. Cleared on actual DA, settled at RT."""
    e = pd.read_csv(C.DATA / f'fs_frame_{zone}.csv'); s = e[(e.v2 == 1) & e.sp.notna() & e.q25.notna()].copy()
    V = {'VA tiers (as now)': lambda r: [max(.98 * r.p_da, r.p_rt), r.p_rt, r.p_rt + 5],
         'P25 / P50 / P75 of our DA range': lambda r: [r.q25, r.q50, r.q75],
         'P10 / P25 / P50': lambda r: [r.q10, r.q25, r.q50],
         'P25 / P50 / P75, tight hours only; VA on surplus': lambda r: [r.q25, r.q50, r.q75] if r['head'] < 8000 else [max(.98 * r.p_da, r.p_rt), r.p_rt, r.p_rt + 5]}
    out = []
    for n, f in V.items():
        pl = []
        for r in s.itertuples():
            r = r._asdict(); r['head'] = r['head']; pr = f(pd.Series(r))
            mw = sum(q for q, p in zip([20, 30, 40], pr) if r['da'] >= round(p)); pl.append((r['date'], mw, mw * r['sp']))
        x = pd.DataFrame(pl, columns=['date', 'mw', 'pl']); dd = x.groupby('date').pl.sum(); h1 = dd.index < '2026-02-01'
        bs = [dd.values[rng.integers(0, len(dd), len(dd))].mean() for _ in range(2000)]
        out.append(dict(zone=zone, ladder=n, mwh=int(x.mw.sum()), usd_mwh=round(x.pl.sum() / x.mw.sum(), 2), usd_day=round(dd.mean()), ci90_day=f'{np.percentile(bs,5):+.0f}..{np.percentile(bs,95):+.0f}',
                        H1_day=round(dd[h1].mean()), H2_day=round(dd[~h1].mean()), losing_days=int((dd < 0).sum()), loss_on_losing_days=round(dd[dd < 0].sum()), worst_day=round(dd.min())))
    return pd.DataFrame(out)

def walk_tesla_veto(e, start='2025-09-01', look=120, cands=(0, 200, 300, 500)):
    """Walk-forward veto: on SURPLUS v2 SELL hours (bid headroom >= 8,000), skip the sell when Tesla load - IESO >= t.
    Each day t is re-picked on the trailing `look` days through D-2: the t whose vetoed hours had the most negative mean DA-RT
    (>= 30 h, mean <= -$1). No t qualifying -> no veto that day."""
    s = e[(e.v2 == 1)].copy(); s['surplus'] = s['head'] >= 8000; veto = pd.Series(False, index=s.index); used = {}
    for D in sorted(s.date.unique()):
        if D < start: continue
        c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=look)).date().isoformat()
        tr = s[(s.date <= c2) & (s.date > lo) & s.surplus & s.sp.notna()]; best = None
        for t in cands:
            v = tr[tr.gapT >= t]
            if len(v) >= 30 and v.sp.mean() <= -1 and (best is None or v.sp.mean() < best[1]): best = (t, v.sp.mean())
        if best:
            m = (s.date == D) & s.surplus & (s.gapT >= best[0]); veto[m] = True; used[D] = best[0]
    return veto, used
