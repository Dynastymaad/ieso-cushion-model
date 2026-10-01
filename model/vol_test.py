"""vol_test.py -- should score-5 sells be sized down (or skipped) in the hours most exposed to an RT blow-up?
Live rules exactly (v2 SELL = 5, buy band = 1, else 3; x1.5 on tight sells after 500 MW trips; zone caps East 85 / Ottawa 100),
fills on the actual DA, settled at RT. The 'risky hour' flags are all known at the bid and fixed in advance (no tuning):
  head<5000  / head<5500 : bid-time headroom (the band where RT > $100 in 36-46% of past hours)
  pda>=75    / pda>=100  : our own DA forecast is high (scarcity priced in)
  zone40     : the page's own 'RT>$100' column >= 40% (headroom < 5,000 in the current table)
Each flag x {half size, skip}. Only score-5 sell hours are changed; everything else identical.
Also: September 2026 day by day, following the page exactly."""
import sys, json, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV, zone_bt17 as Z
pd.set_option('display.width', 250)

def rows(e, zone, flag=None, k_risky=1.0):
    out = []
    for r in e.dropna(subset=['da', 'rt', 'p_da', 'p_rt']).itertuples():
        s = 5 if r.v2 == 1 else (1 if r.buyband == -1 else 3)
        b, o = DV.ladder(s, r.p_da, r.p_rt)
        k = 1.5 if (s == 5 and r.branch == 'tight' and (0 if pd.isna(r.trips_d1) else r.trips_d1) >= 500) else 1.0
        risky = s == 5 and flag is not None and bool(flag(r))
        if risky: k *= k_risky
        tb = [(q * k, p) for q, p in b if p is not None]; to = [(q * k, p) for q, p in o if p is not None]
        for side in (tb, to):
            tot = sum(q for q, _ in side)
            if tot > Z.LIM[zone]: side[:] = [(q * Z.LIM[zone] / tot, p) for q, p in side]
        mb = sum(q for q, p in tb if r.da <= p); ms = sum(q for q, p in to if r.da >= p)
        out.append((r.date, r.he, s, risky, mb, ms, mb * (r.rt - r.da) + ms * (r.da - r.rt), r.da, r.rt, r.p_da, r.head))
    return pd.DataFrame(out, columns=['date', 'he', 'score', 'risky', 'mw_b', 'mw_s', 'pl', 'da', 'rt', 'p_da', 'head'])

def stats(x):
    d = x.groupby('date').pl.sum(); cum = d.cumsum(); mw = x.mw_b.sum() + x.mw_s.sum(); h = x[x.mw_b + x.mw_s > 0].pl.sort_values()
    return dict(net=round(d.sum()), usd_mwh=round(x.pl.sum() / max(mw, 1), 2), usd_day=round(d.mean()), worst_day=round(d.min()), p5_day=round(d.quantile(.05)),
                max_dd=round((cum - cum.cummax()).min()), days_lt_50k=int((d < -50000).sum()), worst1pct_h=round(h.head(max(1, len(h) // 100)).sum()),
                h1=round(d[d.index < '2026-02-01'].sum()), h2=round(d[d.index >= '2026-02-01'].sum()))

FLAGS = {'head<5000': lambda r: r.head < 5000, 'head<5500': lambda r: r.head < 5500, 'pda>=75': lambda r: r.p_da >= 75, 'pda>=100': lambda r: r.p_da >= 100}

if __name__ == '__main__':
    res = {}
    for z in Z.LIM:
        e = Z.frame(z); base = rows(e, z); B = stats(base); res[z] = {'live': B}
        print(f'\n================ {z} ({e.date.min()}..{e.date.max()}, cap {Z.LIM[z]}) ================')
        print(f"{'rule':34s}{'net':>11s}{'chg':>10s}{'$/MWh':>7s}{'$/day':>8s}{'worst day':>11s}{'P5 day':>9s}{'max DD':>10s}{'<-50k d':>8s}{'worst1%h':>10s}{'Jul-Jan':>11s}{'Feb-Sep':>11s}")
        pr = lambda n, s: print(f"{n:34s}{s['net']:>11,}{s['net']-B['net']:>+10,}{s['usd_mwh']:>7.2f}{s['usd_day']:>8,}{s['worst_day']:>11,}{s['p5_day']:>9,}{s['max_dd']:>10,}{s['days_lt_50k']:>8}{s['worst1pct_h']:>10,}{s['h1']:>11,}{s['h2']:>11,}")
        pr('live (as the page says)', B)
        risky_h = {}
        for fn, f in FLAGS.items():
            for lab, k in (('half size', .5), ('skip', 0.0)):
                x = rows(e, z, f, k); s = stats(x); res[z][f'{fn}|{lab}'] = s; pr(f'{fn:10s} {lab}', s)
            xb = base.copy(); m = rows(e, z, f, 1.0).risky.values; v = xb[m]
            risky_h[fn] = dict(hours=int(len(v)), days=int(v.date.nunique()), pl=round(v.pl.sum()), usd_mwh=round(v.pl.sum() / max((v.mw_b + v.mw_s).sum(), 1), 2),
                               worst=round(v.pl.min()), share_filled=round(((v.mw_s > 0).mean()) * 100))
        print('  what the flagged sell hours contributed in the live run:', risky_h); res[z]['flagged'] = risky_h
        # September 2026, following the page exactly
        s9 = base[base.date >= '2026-09-01']; d = s9.groupby('date').agg(pl=('pl', 'sum'), mwh=('mw_s', 'sum'), mwb=('mw_b', 'sum'), sell_h=('score', lambda v: int((v == 5).sum())))
        d['cum'] = d.pl.cumsum(); res[z]['sep'] = d.reset_index().round(0).to_dict('records')
        by = s9.groupby('score').agg(mwh_sell=('mw_s', 'sum'), mwh_buy=('mw_b', 'sum'), pl=('pl', 'sum')).round(0)
        print(f'\n  September 2026 ({d.index.min()}..{d.index.max()}, {len(d)} days): net {d.pl.sum():+,.0f}, {(d.pl>0).sum()} up / {(d.pl<0).sum()} down days, best {d.pl.max():+,.0f}, worst {d.pl.min():+,.0f}, $/MWh {s9.pl.sum()/max((s9.mw_b+s9.mw_s).sum(),1):.2f}')
        print('  by score:', by.to_dict('index')); res[z]['sep_by_score'] = by.reset_index().to_dict('records')
        print(d[['sell_h', 'mwh', 'mwb', 'pl', 'cum']].round(0).to_string())
    (C.DATA / 'vol_test.json').write_text(json.dumps(res, default=float, indent=1))
