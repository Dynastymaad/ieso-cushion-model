"""spike_study.py -- Oct 7 2026: what, known at the bid, comes before RT spikes (RT-DA >= $50) in hours we are NOT selling?
Frame: dv_frame (walk-forward forecasts) + cahr_frame (live sell branch). Sep 2025 -> Oct 6 2026. EAST and OTTAWA."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 250)

def frame(z):
    d = pd.read_csv(C.DATA / f'dv_frame_{z}.csv'); c = pd.read_csv(C.DATA / f'cahr_frame_{z}.csv')[['date', 'he', 'why', 'cahr']]
    m = d.merge(c, on=['date', 'he'], how='inner'); m['rd'] = m.rt - m.da; m['spk'] = m.rd >= 50
    m['tg'] = m.lf_tesla - m.dem_fc
    # wind change into the hour (IESO fc, 3h) and gas outages vs trailing 30 days
    m = m.sort_values(['date', 'he']); m['wr3'] = m.groupby('date').wind_fc.diff(3)
    go = m.groupby('date').gas_out.mean(); gp = go.rolling(30, min_periods=10).apply(lambda s: (s.iloc[:-1] < s.iloc[-1]).mean() * 100 if len(s) > 1 else np.nan)
    m['gas_out_p'] = m.date.map(gp)
    return m

def tbl(m, col, bins, labels):
    b = pd.cut(m[col], bins, labels=labels)
    g = m.groupby(b, observed=True).agg(hours=('rd', 'size'), spike_pct=('spk', lambda s: s.mean() * 100), mean=('rd', 'mean'), median=('rd', 'median'))
    h1 = m[m.date < '2026-02-15'].groupby(b[m.date < '2026-02-15'], observed=True).spk.mean() * 100
    h2 = m[m.date >= '2026-02-15'].groupby(b[m.date >= '2026-02-15'], observed=True).spk.mean() * 100
    g['spk_H1'] = h1; g['spk_H2'] = h2; return g.round(1)

for z in ('EAST', 'OTTAWA'):
    m = frame(z); m = m[m.rt.notna() & m.why.isna()]          # hours we are not selling
    print(f'\n=========== {z}: {len(m)} non-sell hours, spike (RT-DA>=50) base rate {m.spk.mean()*100:.1f}% ===========')
    print('-- by HE block'); print(tbl(m, 'he', [0, 6, 16, 22, 24], ['HE1-6', 'HE7-16', 'HE17-22', 'HE23-24']).to_string())
    ev = m[m.he.between(17, 22)]
    print('-- evening HE17-22 by headroom'); print(tbl(ev, 'head', [0, 7000, 8000, 9000, 10000, 12000, 1e9], ['<7k', '7-8k', '8-9k', '9-10k', '10-12k', '12k+']).to_string())
    print('-- evening HE17-22 by Tesla - IESO (MW)  [Tesla coverage %.0f%%]' % (ev.tg.notna().mean() * 100)); print(tbl(ev, 'tg', [-1e9, -500, -200, 0, 200, 400, 1e9], ['<-500', '-500..-200', '-200..0', '0..200', '200..400', '>400']).to_string())
    print('-- evening HE17-22 by CAHR'); print(tbl(ev, 'cahr', [0, 7.5, 9, 10, 12, 99], ['<7.5', '7.5-9', '9-10', '10-12', '12+']).to_string())
    print('-- evening HE17-22 by gas outages pct vs 30d'); print(tbl(ev, 'gas_out_p', [-1, 33, 66, 101], ['low', 'mid', 'high']).to_string())
    print('-- evening HE17-22 by wind change last 3h (IESO fc)'); print(tbl(ev, 'wr3', [-1e9, -400, -150, 150, 400, 1e9], ['falls >400', '-400..-150', 'flat', '+150..400', 'rises >400']).to_string())
    print('-- evening HE17-22 by weekend'); print(tbl(ev, 'wkend', [-1, 0.5, 2], ['weekday', 'weekend']).to_string())
    print('-- evening HE17-22 by bias7 (trailing DA-RT)'); print(tbl(ev, 'bias7', [-1e9, -10, 0, 10, 1e9], ['<-10 (RT>DA lately)', '-10..0', '0..10', '>10 (DA>RT lately)']).to_string())
