"""da_virtual.py -- live pieces of the DA Virtual tab (same rules as the 17-month re-test in da_virtual_bt.py).
  score 5  STRONG SELL : v2 SELL (tight or surplus, signals_v2.py)        4 : v2 SELL-L (extended surplus)
  score 1  STRONG BUY  : headroom inside the 'middle band' learned on the trailing 120 days (walk_buy_band)
  score 3  neutral     : everything else (wide straddle, small MW)
Ladders: the VA Hub 3-tier formulas exactly (da_virtual_bt.ladder), priced off our DA and RT forecasts.
Lean: only the VA Hub signals that passed the re-test (load vs IESO, wind ramp 3h, gas-need ramp); the others are shown
as information in the guide, not scored."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV

BANDS = [-1e9, 5000, 6000, 7000, 8000, 9000, 10000, 12000, 1e9]
BAND_LBL = ['<5k', '5-6k', '6-7k', '7-8k', '8-9k', '9-10k', '10-12k', '12k+']

def history(zone):
    p = C.prices(zone)[['date', 'he', 'da', 'rt']]; a = C.adq2('preDA')[['date', 'he', 'head']]
    d = p.merge(a, on=['date', 'he'], how='outer'); d['sp'] = d.da - d.rt
    return d.sort_values(['date', 'he']).reset_index(drop=True)

def band_for(zone, D, look=120, width=2000):
    """Middle-headroom BUY band for day D, learned on days <= D-2 (same rule as the backtest)."""
    d = history(zone)
    c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=look)).date().isoformat()
    tr = d[(d.date <= c2) & (d.date > lo)].dropna(subset=['sp', 'head']); best = None
    for a in range(5000, 11001, 500):
        m = tr[(tr['head'] >= a) & (tr['head'] < a + width)]
        if len(m) >= 150 and m.sp.mean() <= -3 and (best is None or m.sp.mean() < best[1]): best = (a, float(m.sp.mean()), len(m))
    return None if best is None else dict(lo=best[0], hi=best[0] + width, mean=round(best[1], 2), hours=best[2])

def bias(zone, D):
    """Trailing mean DA-RT by HE, 7 and 14 days, known through D-2 (VA Hub 'hourly bias')."""
    d = history(zone); c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
    out = {}
    for n in (7, 14):
        lo = (pd.Timestamp(c2) - pd.Timedelta(days=n)).date().isoformat()
        x = d[(d.date > lo) & (d.date <= c2)].dropna(subset=['sp'])
        g = x.groupby('he').sp.agg(['mean', lambda s: (s < 0).mean() * 100]); g.columns = ['m', 'rtgt']
        out[n] = g
    return out

def band_table(zone):
    """Measured outcome by pre-DA headroom band, 17 months (from the re-test frame)."""
    f = C.DATA / f'dv_frame_{zone}.csv'
    if not f.exists(): return []
    x = pd.read_csv(f).dropna(subset=['sp', 'head']); x['b'] = pd.cut(x['head'], BANDS, labels=BAND_LBL)
    g = x.groupby('b', observed=True).agg(hours=('sp', 'size'), da_rt=('sp', 'mean'), rt_gt_da=('sp', lambda s: (s < 0).mean() * 100),
                                          rt100=('rt', lambda s: (s > 100).mean() * 100), rt25=('rt', lambda s: (s < 25).mean() * 100)).round(1).reset_index()
    return g.rename(columns={'b': 'band'}).to_dict('records')

def band_label(h):
    for lo, hi, l in zip(BANDS[:-1], BANDS[1:], BAND_LBL):
        if lo <= h < hi: return l
    return None

def lean(rows):
    """rows: list of dicts per HE with dem_fc, lf_tesla, lf_dynasty, wind_fc, gas_hat. + = bullish RT (buy)."""
    df = pd.DataFrame(rows).sort_values('he').reset_index(drop=True)
    wl = df[['lf_tesla', 'lf_dynasty']].mean(axis=1); dl = wl - df.dem_fc
    wr = df.wind_fc - df.wind_fc.shift(3); gp = (df.gas_hat - df.gas_hat.shift(1)) / df.gas_hat.shift(1).clip(lower=500) * 100
    out = {}
    for i, r in df.iterrows():
        sig = []
        if pd.notna(dl[i]): sig.append(('Load vs IESO', int(round(dl[i], -1)), 1 if dl[i] >= 200 else -1 if dl[i] <= -200 else 0))
        if pd.notna(wr[i]): sig.append(('Wind 3h ramp', int(round(wr[i], -1)), 1 if wr[i] <= -400 else -1 if wr[i] >= 400 else 0))
        if pd.notna(gp[i]): sig.append(('Gas-need ramp %', int(round(gp[i])), 1 if gp[i] >= 15 else -1 if gp[i] <= -15 else 0))
        out[int(r.he)] = dict(score=sum(s[2] for s in sig), signals=[dict(label=a, value=b, pts=c) for a, b, c in sig])
    return out

def score_hour(signal, head, band):
    if signal == 'SELL': return 5, 'v2 SELL'
    if signal == 'SELL-L': return 4, 'v2 SELL-L'
    if band and head is not None and band['lo'] <= head < band['hi']: return 1, f"headroom in buy band {band['lo']:,}-{band['hi']:,}"
    return 3, 'no tested edge'

def va_auto(p_da, p_rt):
    g = p_rt - p_da
    return 1 if g >= 10 else 2 if g >= 5 else 5 if g <= -10 else 4 if g <= -5 else 3

def ladders(p_da, p_rt, dq=None):
    """All five VA ladders (VA Hub tier formulas). The protective P25/P50/P75 score-5 variant was tested (notes/Losing_Sell_Days.md)
    and not adopted: it nets less (+2.60M vs +3.33M Toronto)."""
    out = {}
    for s in (1, 2, 3, 4, 5):
        b, o = DV.ladder(s, p_da, p_rt); out[str(s)] = dict(buy=b, sell=o)
    return out

TRIPS_BOOST = 500   # MW; x1.5 on TIGHT score-5 sells only (boost_test.py: tight +22..+32 $/MWh both halves, surplus ~0)

def trips_d1(D):
    """Gas + nuclear + hydro outage MW added to D-1's own hours after D-1's bid, as known at D's bid (D-1 09:00 EST).
    From the Adequacy2 outage timeline (pull_history.py --only outages). Returns {he: MW} or {} if the timeline doesn't cover D-1."""
    import outage_timeline as OT
    try: t = OT.load()
    except Exception: return {}
    d1 = (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat(); hes = list(range(1, 25))
    if not (t.date == d1).any(): return {}
    now = OT.asof(t, [d1] * 24, hes, [pd.Timestamp(D) - pd.Timedelta(days=1) + pd.Timedelta(hours=9)] * 24).sum(axis=1, min_count=1)
    then = OT.asof(t, [d1] * 24, hes, [pd.Timestamp(D) - pd.Timedelta(days=2) + pd.Timedelta(hours=9)] * 24).sum(axis=1, min_count=1)
    return {h: (None if pd.isna(a - b) else int(round(a - b))) for h, a, b in zip(hes, now, then)}
