"""onpeak_read.py -- next-day Ontario on-peak read (Nov 10 2026, TEST STAGE: separate from the virtual-bid model).

Run on day O around 12:00 Calgary for delivery day D = O+1 (trade cutoff 12:30 Calgary; IESO posts the DA clear ~12:31 Calgary in winter).

    python onpeak\\onpeak_read.py                 # refresh NYISO DAM + latest IESO files + noon Adequacy, then the read for tomorrow
    python onpeak\\onpeak_read.py --mkt 67.5      # same, plus the lean vs the market you see on screen
    python onpeak\\onpeak_read.py --no-pull       # skip the refresh (use what is already in cache)
    python onpeak\\onpeak_read.py --date 2026-11-12 --no-pull   # read for another delivery day (made as of the day before)
    python onpeak\\onpeak_read.py --score         # fill in the DA clears for past reads in out\\read_log.csv and show the running record
    python onpeak\\onpeak_read.py --backtest      # walk-forward backtest of this exact code (Oct 2025 ->), ~1-2 min

What it uses (all known by 12:00 Calgary on O): IESO Adequacy as it stood at 12:00 EST on O (pull_history --only adq2noon), NY Zone A DA
for D (NYISO posts ~08:33 Calgary), today's Ontario DA clear, the last Ontario Hub / NY / PJM / Dawn settles, typical intertie flows.
Model P50: log on-peak DA on spare (tight/loose), NY + PJM forwards, Dawn, typical exports, weekend, NY DA; refit on the last 240 days,
blended with the Ontario Hub mark. Bands: last 180 days of errors on days with similar spare. Like-days: past weekdays within +/-500 MW of
spare, ranked on spare, Ontario Hub mark, NY DA (x0.5), exports vs last 30 days (x0.5), gas outages, solar (x0.25); 5 closest, each scaled
by the Ontario Hub and NY DA ratios. Catch-up: when the last two clears missed the read the same way by >8%, the P50 moves by a
learned share of that miss (refit daily on past days). Call = model and like-days lean the same way by more than $3 vs the reference; otherwise no call.
Reads the model folder's cache/data/archive only; writes only to onpeak\\out.
"""
import argparse, sys, os, subprocess, json, glob, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent; OUT = HERE / 'out'; OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / 'model'))
import common as C
CACHE, ARCH, DATA = ROOT / 'cache', ROOT / 'archive', ROOT / 'data'
OFF = 2263                                   # desk spare scale
X = ['tight', 'loose', 'lny', 'lpjm', 'ldawn', 'expk', 'wkend', 'lnyda']
LD_W = {'sp': 1.0, 'xde': 1.0, 'ny_da': 0.5, 'exp_vs30': 0.5, 'gas_out': 1.0, 'solar': 0.25}
REG = [-9e9, 1500, 2500, 4000, 9e9]; Q = [.1, .5, .75, .9]
REN = {'Ontario Demand|Forecast': 'dem_fc', 'Internal Resource|Nuclear Capacity': 'nuc_cap', 'Internal Resource|Nuclear Outage': 'nuc_out',
       'Internal Resource|Gas Capacity': 'gas_cap', 'Internal Resource|Gas Outage': 'gas_out', 'Internal Resource|Hydro Capacity': 'hyd_cap',
       'Internal Resource|Hydro Outage': 'hyd_out', 'Internal Resource|Wind Forecast': 'wind_fc', 'Internal Resource|Solar Forecast': 'solar_fc'}

def say(s=''): print(s, flush=True)

# ------------------------------------------------------------------ refresh
def refresh():
    py = sys.executable; env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    for cmd, opt in [(['ieso_backfill.py', '--quick', '--nyiso'], False), (['model/parse_archive.py'], False),
                     (['pull_history.py', '--only', 'adq2noon', '--recent', '5'], False)]:
        say(f'>>> {" ".join(cmd)}'); r = subprocess.run([py, '-X', 'utf8'] + cmd, cwd=ROOT, env=env)
        if r.returncode != 0: sys.exit(f'STOPPED: {cmd[0]} failed. Fix that step (network/VPN?) and run again, or use --no-pull.')

# ------------------------------------------------------------------ inputs
def adq(which):
    f = CACHE / f'ieso_adq2_{which}.csv'
    if not f.exists(): return None
    a = C.adq2(which); a['date'] = a.date.astype(str); a = a[['date', 'he'] + [c for c in REN.values() if c in a.columns]].copy()
    a['nuc_av'] = a.nuc_cap - a.nuc_out; a['gas_av'] = a.gas_cap - a.gas_out; a['hyd_av'] = a.hyd_cap - a.hyd_out
    a['head'] = a.gas_av + a.hyd_av - (a.dem_fc - a.nuc_av - a.wind_fc.fillna(0) - a.solar_fc.fillna(0))
    a = a[C.onpeak(a.date, a.he).values]; return a

def ties():
    out = []
    for f in sorted(glob.glob(str(ARCH / 'IntertieScheduleFlowYear' / 'PUB_IntertieScheduleFlowYear_*.csv'))):
        x = pd.read_csv(f, skiprows=3, header=[0, 1])
        x.columns = [f'{a}|{b}' if not str(a).startswith('Unnamed') else b for a, b in x.columns]
        d = pd.DataFrame({'date': x['Date'].astype(str), 'he': pd.to_numeric(x['Hour'], errors='coerce')})
        tot = lambda k: pd.to_numeric(x[f'Total|{k}'], errors='coerce').fillna(0)
        d['net_exp'] = tot('Exp') - tot('Imp'); out.append(d.dropna(subset=['he']))
    t = pd.concat(out); t['he'] = t.he.astype(int); t = t[C.onpeak(t.date, t.he).values]
    s = t.groupby('date').net_exp.mean(); s.index = pd.to_datetime(s.index); return s

def fx():
    x = pd.read_csv(CACHE / 'fx_usdcad.csv'); x['date'] = pd.to_datetime(x.Date)
    d = pd.DataFrame({'date': pd.date_range('2025-01-01', dt.date.today() + dt.timedelta(days=10))})
    x = pd.merge_asof(d, x.sort_values('date')[['date', 'Rate']], on='date'); return x.set_index('date').Rate.ffill()

def fwd_asof(ft, code, D, O):
    g = ft[(ft.ExchangeCode == code) & (ft.Strip == D) & (ft.EffectiveDate <= O - pd.Timedelta(days=1))]
    return g.sort_values('EffectiveDate').Price.iloc[-1] if len(g) else np.nan

def holidays(y):
    def nth(m, wd, n):
        d = dt.date(y, m, 1); d += dt.timedelta((wd - d.weekday()) % 7); return d + dt.timedelta(7 * (n - 1))
    a = y % 19; b = y // 100; c = y % 100; d_ = b // 4; e = b % 4; f = (b + 8) // 25; g = (b - f + 1) // 3; h = (19 * a + b - d_ - g + 15) % 30
    i = c // 4; k = c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7; m = (a + 11 * h + 22 * l) // 451
    easter = dt.date(y, (h + l - 7 * m + 114) // 31, ((h + l - 7 * m + 114) % 31) + 1)
    vd = dt.date(y, 5, 24); vd -= dt.timedelta(vd.weekday())
    s = {dt.date(y, 1, 1), nth(2, 0, 3), easter - dt.timedelta(2), vd, dt.date(y, 7, 1), nth(8, 0, 1), nth(9, 0, 1), nth(10, 0, 2), dt.date(y, 12, 25), dt.date(y, 12, 26)}
    for d in [dt.date(y, 1, 1), dt.date(y, 7, 1), dt.date(y, 12, 25), dt.date(y, 12, 26)]:
        if d.weekday() >= 5: s.add(d + dt.timedelta(7 - d.weekday()))
    return s
HOL = set().union(*[holidays(y) for y in range(2015, 2031)])

def demand_actual():
    old = pd.read_csv(HERE / 'data' / 'dem_onpk_2015_2024.csv', parse_dates=['date']).set_index('date').dem_on
    new = []
    for f in sorted(glob.glob(str(ARCH / 'Demand' / 'PUB_Demand_*.csv'))):
        t = pd.read_csv(f, skiprows=3); t = t[t.Date.astype(str).str.match(r'\d{4}-\d{2}-\d{2}')]
        t['Hour'] = t.Hour.astype(int); t = t[C.onpeak(t.Date, t.Hour).values]
        s = t.groupby('Date')['Ontario Demand'].mean(); s.index = pd.to_datetime(s.index); new.append(s)
    s = pd.concat([old] + new); s = s[~s.index.duplicated(keep='last')].sort_index()
    D = pd.DataFrame({'act': s}); D['wd'] = [(d.dayofweek < 5) and (d.date() not in HOL) for d in D.index]; return D

def demand_normal(day, D, years=5, win=10):
    """Season + year normal: same day type, +/-win days, prior 5 years, each re-levelled by the trailing-365-day ratio."""
    day = pd.Timestamp(day); wd = (day.dayofweek < 5) and (day.date() not in HOL); e = day - pd.Timedelta(days=1); vals = []
    cur = D.act[(D.index > e - pd.Timedelta(days=365)) & (D.index <= e)].mean()
    for k in range(1, years + 1):
        c = day - pd.DateOffset(years=k); m = (D.index >= c - pd.Timedelta(days=win)) & (D.index <= c + pd.Timedelta(days=win)) & (D.wd == wd)
        ek = e - pd.DateOffset(years=k); prev = D.act[(D.index > ek - pd.Timedelta(days=365)) & (D.index <= ek)].mean()
        if m.any() and prev > 0: vals.append(D.act[m].median() * cur / prev)
    return np.mean(vals) if vals else np.nan

def build(D_target):
    """One row per delivery day D (lead 1, made on O=D-1), noon Adequacy where available (else pre-DA)."""
    pre = adq('preDA'); noon = adq('noon')
    if pre is None: sys.exit('STOPPED: cache\\ieso_adq2_preDA.csv missing -- run morning.py first.')
    if noon is not None:
        nd = set(noon.date); a = pd.concat([noon, pre[~pre.date.isin(nd)]], ignore_index=True); a['noon'] = a.date.isin(nd)
    else: a = pre.copy(); a['noon'] = False
    g = a.groupby('date').agg(dem=('dem_fc', 'mean'), wind=('wind_fc', 'mean'), solar=('solar_fc', 'mean'), nuc=('nuc_av', 'mean'),
                              gas_out=('gas_out', 'mean'), hyd_av=('hyd_av', 'mean'), head=('head', 'mean'), head_min=('head', 'min'), noon=('noon', 'max'))
    g.index = pd.to_datetime(g.index)
    p = C.prices('ONTARIO'); p['date'] = p.date.astype(str); p = p[C.onpeak(p.date, p.he).values]
    P = p.groupby('date').agg(da_on=('da', 'mean'), rt_on=('rt', 'mean')); P.index = pd.to_datetime(P.index)
    ft = pd.read_csv(CACHE / 'fwd_daily_ontario.csv', parse_dates=['EffectiveDate', 'Strip'])
    ft = ft[ft.ExchangeCode.isin(['XDE', 'ADP', 'PDA', 'CVX']) & (ft.Strip > ft.EffectiveDate)]
    FX = fx(); NE = ties()
    ny = pd.read_csv(DATA / 'nyiso_zoneA_da.csv'); ny['date'] = ny.date.astype(str); ny = ny[C.onpeak(ny.date, ny.he).values]
    NY = ny.groupby('date').nyA_da.mean(); NY.index = pd.to_datetime(NY.index)
    days = [d for d in g.index if d >= pd.Timestamp('2025-05-03') and d <= D_target]
    rows = []
    for D in days:
        O = D - pd.Timedelta(days=1); r = g.loc[D].to_dict(); r.update(date=D, origin=O, dow=D.dayofweek)
        h15 = NE[(NE.index < O) & (NE.index >= O - pd.Timedelta(days=15))]; h30 = NE[(NE.index < O) & (NE.index >= O - pd.Timedelta(days=30))]
        r['exp_typ'] = h15.median() if len(h15) else np.nan; r['exp30'] = h30.mean() if len(h30) else np.nan
        fxo = FX.get(O, np.nan)
        r['xde'] = fwd_asof(ft, 'XDE', D, O); r['ny_fwd'] = fwd_asof(ft, 'ADP', D, O) * fxo; r['pjm_fwd'] = fwd_asof(ft, 'PDA', D, O) * fxo; r['dawn'] = fwd_asof(ft, 'CVX', D, O)
        r['ny_da'] = NY.get(D, np.nan) * fxo; r['persist'] = P.da_on.get(O, np.nan); r['da_on'] = P.da_on.get(D, np.nan); r['rt_on'] = P.rt_on.get(D, np.nan)
        rows.append(r)
    d = pd.DataFrame(rows)
    d['spare'] = d['head'] - d.exp_typ; d['sp'] = d.spare - OFF; d['spmin'] = d.head_min - d.exp_typ - OFF; d['exp_vs30'] = d.exp_typ - d.exp30
    d['tight'] = np.clip(2500 - d.sp, 0, None) / 1000; d['loose'] = np.clip(d.sp - 2500, 0, None) / 1000
    d['lny'] = np.log(d.ny_fwd); d['lpjm'] = np.log(d.pjm_fwd); d['ldawn'] = np.log(d.dawn); d['expk'] = d.exp_typ / 1000
    d['wkend'] = (d.dow >= 5).astype(int); d['lnyda'] = np.log(d.ny_da.clip(lower=5)); d['lxde'] = np.log(d.xde)
    d['wd'] = [(x.dayofweek < 5) and (x.date() not in HOL) for x in d.date]
    return d.sort_values('date').reset_index(drop=True)

# ------------------------------------------------------------------ model, bands, like-days
def walk(d, win=240, minN=90):
    d = d.copy(); d['m_fund'] = np.nan
    for i, row in d.iterrows():
        if row[X].isna().any(): continue
        tr = d[(d.date < row.origin) & (d.date >= row.origin - pd.Timedelta(days=win))].dropna(subset=X + ['da_on'])
        if len(tr) < minN: continue
        A = np.c_[np.ones(len(tr)), tr[X].values]; b = np.linalg.lstsq(A, np.log(tr.da_on.clip(lower=5)), rcond=None)[0]
        d.at[i, 'm_fund'] = np.r_[1, row[X].values.astype(float)] @ b
    d['m_blend'] = np.nan; d['w'] = np.nan
    for i, row in d[d.m_fund.notna() & d.lxde.notna()].iterrows():
        past = d[(d.date < row.origin) & d.da_on.notna() & d.m_fund.notna() & d.lxde.notna()].tail(120)
        if len(past) < 30: w = 0.5
        else:
            yp = np.log(past.da_on.clip(lower=5)); a = past.m_fund - past.lxde; w = float(np.clip(((yp - past.lxde) * a).sum() / (a * a).sum(), 0, 1))
        d.at[i, 'm_blend'] = w * row.m_fund + (1 - w) * row.lxde; d.at[i, 'w'] = w
    d['res'] = np.log(d.da_on.clip(lower=5)) - d.m_blend; d['rg'] = pd.cut(d.sp, REG, labels=False)
    return d

def bands(d, i, win=180, minN=30):
    row = d.loc[i]; past = d[(d.date < row.origin) & (d.date >= row.origin - pd.Timedelta(days=win)) & d.res.notna()]
    p = past[past.rg == row.rg]
    if len(p) < minN: p = past
    if len(p) < minN or pd.isna(row.m_blend): return None
    return {f'P{int(q*100)}': float(np.exp(row.m_blend + v)) for q, v in zip(Q, np.quantile(p.res, Q))}

CATCH_TH = 0.08
def catchup(d, th=CATCH_TH, minN=60):
    """Nov 10 2026 'catch-up': when the last two known clears both beat (or both fell short of) the read by more than 8%, move the P50 by
    a learned share of their average miss. The share is refit each day on past days only. Backtest (278 weekdays Oct 2025-Nov 2026):
    P50 miss $11.51 -> $10.26, gain +1.25 [+0.56,+2.03], positive in both halves; significant for thresholds 4-15%. Off with --no-catchup."""
    d = d.sort_values('date').copy()
    r = d.loc[d.res.notna(), ['date', 'res']]
    pos = np.searchsorted(r.date.values, d.date.values)                      # known clears strictly before delivery day D (last one = day O)
    rv = r.res.values; r1 = np.array([rv[p - 1] if p >= 1 else np.nan for p in pos]); r2 = np.array([rv[p - 2] if p >= 2 else np.nan for p in pos])
    gate = (np.sign(r1) == np.sign(r2)) & (np.abs(r1) > th) & (np.abs(r2) > th)
    d['catch_x'] = np.where(np.isnan(r1) | np.isnan(r2), np.nan, np.where(gate, (r1 + r2) / 2, 0.0)); d['catch_r1'] = r1; d['catch_r2'] = r2; d['catch'] = 0.0
    for i, row in d.iterrows():
        if pd.isna(row.catch_x) or row.catch_x == 0 or pd.isna(row.m_blend): continue
        tr = d[(d.date < row.origin) & d.res.notna() & d.catch_x.notna()]
        if len(tr) < minN: continue
        d.at[i, 'catch'] = np.polyfit(tr.catch_x, tr.res, 1)[0] * row.catch_x
    d['m_blend0'] = d.m_blend; d['m_blend'] = d.m_blend + d.catch
    d['res'] = np.log(d.da_on.clip(lower=5)) - d.m_blend; d['rg'] = pd.cut(d.sp, REG, labels=False)
    return d

def likedays(d, i, k=5, band=500):
    t = d.loc[i]; F = list(LD_W); w = np.array([LD_W[f] for f in F])
    pool = d[(d.date < t.date) & d.wd & d.da_on.notna()].dropna(subset=F)
    c = pool[(pool.sp - t.sp).abs() <= band]
    if len(c) < k: c = pool.loc[(pool.sp - t.sp).abs().nsmallest(15).index]
    sd = c[F].std().replace(0, 1).fillna(1).values
    dist = (np.abs(c[F].values - t[F].values.astype(float)) / sd * w).sum(1)
    a = c.iloc[np.argsort(dist, kind='stable')[:k]].copy()
    a['scaled'] = a.da_on * np.sqrt((t.xde / a.xde) * (t.ny_da / a.ny_da)); return a

def call(m, l, ref, thr=3.0):
    if pd.isna(ref): return 'no reference'
    lm, ll = m - ref, l - ref
    if np.sign(lm) == np.sign(ll) and abs(lm) > thr and abs(ll) > thr: return 'UP (buy)' if lm > 0 else 'DOWN (sell)'
    return 'no call'

# ------------------------------------------------------------------ outputs
def hourly(d, D, ld):
    p = C.prices('ONTARIO'); p['date'] = pd.to_datetime(p.date.astype(str)); p = p[C.onpeak(p.date.dt.strftime('%Y-%m-%d'), p.he).values]
    shapes = []
    for _, r in ld.iterrows():
        h = p[p.date == r.date].set_index('he').da
        if len(h): shapes.append(h / h.mean())
    shape = pd.concat(shapes, axis=1).mean(1) if shapes else None
    a = adq('noon'); a = a if a is not None and (a.date == D.strftime('%Y-%m-%d')).any() else adq('preDA')
    a = a[a.date == D.strftime('%Y-%m-%d')].set_index('he')
    return shape, a

def html(res, path):
    def tbl(df):
        return df.to_html(index=False, border=0, classes='t', float_format=lambda v: f'{v:,.1f}', na_rep='—')
    css = """<style>:root{--bg:#fbfbfa;--fg:#1d1f22;--mut:#5f6670;--line:#dcdfe3;--up:#1f7a3a;--dn:#b3261e;--nc:#2457a6}
@media(prefers-color-scheme:dark){:root{--bg:#16181b;--fg:#e8e9eb;--mut:#a0a7b0;--line:#33373d;--up:#5cc27f;--dn:#ff8a80;--nc:#8ab4ff}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,sans-serif;margin:0;padding:16px 20px;max-width:1100px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:22px 0 8px}.mut{color:var(--mut)}.call{font-size:20px;font-weight:600}
.UP{color:var(--up)}.DOWN{color:var(--dn)}.no{color:var(--nc)}.t{border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:13px}
.t th,.t td{padding:4px 9px;border-bottom:1px solid var(--line);text-align:right}.t th:first-child,.t td:first-child{text-align:left}
.wrap{overflow-x:auto}.warn{color:var(--dn)}</style>"""
    cl = lambda s: 'UP' if s.startswith('UP') else ('DOWN' if s.startswith('DOWN') else 'no')
    body = [f"<h1>Ontario on-peak read for {res['D']}</h1><div class='mut'>Made {res['made']} (as of {res['O']}). Test stage, separate from the virtual-bid model.</div>"]
    for w_ in res['warn']: body.append(f"<p class='warn'>{w_}</p>")
    body.append(f"<p class='call {cl(res['call_today'])}'>Call vs today's clear (${res['today']:.1f}): {res['call_today']}</p>")
    if res.get('mkt') is not None: body.append(f"<p class='call {cl(res['call_mkt'])}'>Call vs market ${res['mkt']:.1f}: {res['call_mkt']}</p>")
    body.append('<h2>Read</h2><div class="wrap">' + tbl(res['summary']) + '</div>')
    body.append('<h2>Like-days</h2><p class="mut">Closest past weekdays (spare within ±500 MW, then ranked on the weighted fundamentals). "Scaled DA" = that day\'s on-peak DA × the Ontario Hub and NY DA ratios to tomorrow. Demand vs normal = season + year normal.</p><div class="wrap">' + tbl(res['ld']) + '</div>')
    if res['hourly'] is not None: body.append('<h2>Hourly</h2><p class="mut">P50 by hour = read P50 × the like-days\' average hourly shape. Fundamentals: IESO Adequacy for tomorrow (noon version where available).</p><div class="wrap">' + tbl(res['hourly']) + '</div>')
    body.append('<h2>How to use it</h2><p class="mut">Only act on a call (model and like-days lean the same way by more than $3). Backtest of this code, 279 weekdays Oct 2025 – Nov 2026, read made the day before: there was a call on 177 days (63%), and the clear landed on that side of today\'s clear on 90% of them; a lean under $3 is close to a coin flip. P50 miss $10.3 (catch-up on; $11.5 without); 6% of clears fell below P10, 9% above P90. That is direction against a reference, not P&L after fills: log every trade with --mkt and --score.</p>')
    path.write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>On-peak read ' + res['D'] + '</title>' + css + '\n'.join(body), encoding='utf-8')

# ------------------------------------------------------------------ main
def read(D, mkt=None, catch=True):
    d = build(D); i = d.index[d.date == D]
    if not len(i): sys.exit(f'STOPPED: no IESO Adequacy for {D.date()} yet -- run morning.py, then this again.')
    i = i[0]; t = d.loc[i]; warn = []
    if not t.noon: warn.append('Noon Adequacy not in for tomorrow -- using the pre-DA version (run without --no-pull, or pull_history.py --only adq2noon --recent 5).')
    if pd.isna(t.ny_da): sys.exit('STOPPED: NY Zone A DA for tomorrow is not in yet (NYISO posts ~08:33 Calgary). Run again without --no-pull after that.')
    if pd.isna(t.persist): warn.append("Today's Ontario DA clear is missing from data\\prices_hourly.csv.")
    if t.date.dayofweek >= 5: warn.append('Tomorrow is a weekend day: not part of the weekday on-peak contract.')
    d = walk(d)
    if catch: d = catchup(d)
    t = d.loc[i]; b = bands(d, i); ld = likedays(d, i)
    ca = float(t.get('catch', 0.0)) if catch else 0.0
    if catch and ca != 0: warn.append(f"Catch-up ON: the last two clears both {'beat' if ca > 0 else 'fell short of'} the read by more than 8% ({100*(np.exp(t.catch_r2)-1):+.0f}%, {100*(np.exp(t.catch_r1)-1):+.0f}%), so the P50 is moved {100*(np.exp(ca)-1):+.1f}% to catch up with the market.")
    if b is None: sys.exit('STOPPED: not enough history for the bands.')
    lv = float(ld.scaled.mean()); p50 = b['P50']
    Dm = demand_actual()
    ld_show = pd.DataFrame({'Day': ld.date.dt.strftime('%a %b %d %y'), 'Spare': ld.sp, 'Ont Hub mark': ld.xde, 'NY DA C$': ld.ny_da, 'Gas out': ld.gas_out,
                            'Solar': ld.solar, 'Exports vs 30d': ld.exp_vs30, 'Demand': ld.dem,
                            'Demand vs normal %': [100 * (r.dem / demand_normal(r.date, Dm) - 1) for _, r in ld.iterrows()],
                            'DA on-peak': ld.da_on, 'RT on-peak': ld.rt_on, 'Scaled DA': ld.scaled})
    trow = pd.DataFrame({'Day': ['TOMORROW ' + D.strftime('%a %b %d')], 'Spare': [t.sp], 'Ont Hub mark': [t.xde], 'NY DA C$': [t.ny_da], 'Gas out': [t.gas_out],
                         'Solar': [t.solar], 'Exports vs 30d': [t.exp_vs30], 'Demand': [t.dem], 'Demand vs normal %': [100 * (t.dem / demand_normal(D, Dm) - 1)],
                         'DA on-peak': [np.nan], 'RT on-peak': [np.nan], 'Scaled DA': [lv]})
    summ = pd.DataFrame([{'P10': b['P10'], 'P50': p50, 'P75': b['P75'], 'P90': b['P90'], 'Like-day': lv, "Today's clear": t.persist,
                          'Catch-up %': 100 * (np.exp(ca) - 1), 'Model lean vs today': p50 - t.persist, 'Like-day lean vs today': lv - t.persist, 'Ont Hub mark': t.xde, 'NY DA C$': t.ny_da, 'Spare (desk)': t.sp}])
    res = dict(D=D.strftime('%a %b %d %Y'), O=(D - pd.Timedelta(days=1)).strftime('%a %b %d'), made=dt.datetime.now().strftime('%Y-%m-%d %H:%M'), warn=warn,
               today=t.persist, call_today=call(p50, lv, t.persist), mkt=mkt, call_mkt=call(p50, lv, mkt) if mkt is not None else None,
               summary=summ, ld=pd.concat([trow, ld_show], ignore_index=True), hourly=None)
    shape, a = hourly(d, D, ld)
    if shape is not None and len(a):
        hh = pd.DataFrame({'HE': a.index, 'P50': [p50 * shape.get(h, np.nan) for h in a.index], 'Demand': a.dem_fc.values, 'Wind': a.wind_fc.values,
                           'Solar': a.solar_fc.values, 'Gas out': a.gas_out.values, 'Spare (desk)': (a['head'] - t.exp_typ - OFF).values})
        res['hourly'] = hh
    path = OUT / f'read_{D:%Y-%m-%d}.html'; html(res, path)
    # console
    say(f"\n=== Ontario on-peak read for {res['D']} (made {res['made']}) ===")
    for w_ in warn: say('  ! ' + w_)
    say(f"  P10 {b['P10']:.1f} | P50 {p50:.1f} | P75 {b['P75']:.1f} | P90 {b['P90']:.1f}   like-day {lv:.1f}")
    say(f"  today's clear {t.persist:.1f}: model lean {p50 - t.persist:+.1f}, like-day lean {lv - t.persist:+.1f}  ->  {res['call_today']}")
    if mkt is not None: say(f"  market {mkt:.1f}: model lean {p50 - mkt:+.1f}, like-day lean {lv - mkt:+.1f}  ->  {res['call_mkt']}")
    say(f"  like-days: " + ', '.join(f"{r.date:%b %d %y} ({r.scaled:.1f})" for _, r in ld.iterrows()))
    say(f"  page: {path}")
    # log
    lg = OUT / 'read_log.csv'; row = dict(delivery=D.strftime('%Y-%m-%d'), made=res['made'], P10=b['P10'], P50=p50, P75=b['P75'], P90=b['P90'], likeday=lv,
                                          today=t.persist, call_today=res['call_today'], mkt=mkt, call_mkt=res['call_mkt'], noon_adequacy=bool(t.noon), da_clear=np.nan)
    L = pd.read_csv(lg) if lg.exists() else pd.DataFrame(columns=list(row))
    L = pd.concat([L[L.delivery != row['delivery']], pd.DataFrame([row])], ignore_index=True).sort_values('delivery'); L.to_csv(lg, index=False)

def score():
    lg = OUT / 'read_log.csv'
    if not lg.exists(): sys.exit('No reads logged yet.')
    L = pd.read_csv(lg); p = C.prices('ONTARIO'); p['date'] = p.date.astype(str); p = p[C.onpeak(p.date, p.he).values]
    da = p.groupby('date').da.mean(); L['da_clear'] = L.delivery.map(da); L.to_csv(lg, index=False)
    s = L.dropna(subset=['da_clear'])
    say(f'{len(s)} scored reads.')
    for ref, c in [('today', 'call_today'), ('mkt', 'call_mkt')]:
        k = s[s[c].astype(str).str.startswith(('UP', 'DOWN')) & s[ref].notna()]
        if len(k):
            right = np.where(k[c].str.startswith('UP'), k.da_clear > k[ref], k.da_clear < k[ref])
            pnl = np.where(k[c].str.startswith('UP'), k.da_clear - k[ref], k[ref] - k.da_clear)
            say(f'  calls vs {ref}: {len(k)}, right {right.mean():.0%}, avg $/MWh at that price {pnl.mean():+.2f}')
    say(f'  P50 average miss ${(s.P50 - s.da_clear).abs().mean():.1f}; clears inside P10-P75: {((s.da_clear >= s.P10) & (s.da_clear <= s.P75)).mean():.0%}')

def backtest(catch=True):
    last = pd.Timestamp(dt.date.today()); d = build(last); d = walk(d)
    if catch: d = catchup(d)
    rows = []
    T = d[(d.date >= '2025-10-01') & d.wd & d.da_on.notna() & d.m_blend.notna() & d.ny_da.notna()].index
    for i in T:
        b = bands(d, i)
        if b is None: continue
        lv = likedays(d, i).scaled.mean(); t = d.loc[i]
        rows.append(dict(date=t.date, da=t.da_on, today=t.persist, ld=lv, **b))
    E = pd.DataFrame(rows); E.to_csv(OUT / 'backtest.csv', index=False)
    o = np.sign(E.da - E.today); k = o != 0; lm = E.P50 - E.today; ll = E.ld - E.today
    both = k & (np.sign(lm) == np.sign(ll)) & (lm.abs() > 3) & (ll.abs() > 3)
    say(f'Backtest {E.date.min():%Y-%m-%d} to {E.date.max():%Y-%m-%d}: {len(E)} weekdays')
    say(f'  P50 miss ${(E.P50 - E.da).abs().mean():.2f} | like-day miss ${(E.ld - E.da).abs().mean():.2f}')
    say('  below P10/P50/P75/P90: ' + ' / '.join(f'{(E.da < E[q]).mean():.0%}' for q in ['P10', 'P50', 'P75', 'P90']))
    say(f'  direction vs today\'s clear: model {(np.sign(lm) == o)[k].mean():.0%}, like-day {(np.sign(ll) == o)[k].mean():.0%}, '
        f'both agree >$3: {(np.sign(lm) == o)[both].mean():.0%} on {both.sum()} days ({both.sum() / k.sum():.0%} of days)')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--date'); ap.add_argument('--mkt', type=float); ap.add_argument('--no-pull', action='store_true')
    ap.add_argument('--score', action='store_true'); ap.add_argument('--backtest', action='store_true')
    ap.add_argument('--no-catchup', action='store_true', help='turn off the catch-up correction'); a = ap.parse_args()
    if a.score: score(); raise SystemExit
    if a.backtest: backtest(not a.no_catchup); raise SystemExit
    if not a.no_pull: refresh()
    D = pd.Timestamp(a.date) if a.date else pd.Timestamp(dt.date.today() + dt.timedelta(days=1))
    read(D, a.mkt, not a.no_catchup)
