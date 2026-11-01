"""research/audit_oct31.py -- Oct 31 2026: end-of-season health check of every tab (TEST ONLY, changes nothing)."""
import sys, json, warnings, os, time; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, da_virtual_bt as B
pd.set_option('display.width', 220)
P = print
P('=== 1. INPUT FRESHNESS ===')
def last(path, col='date'):
    try: d = pd.read_csv(path, usecols=[col]); return str(d[col].astype(str).str[:10].max())
    except Exception as ex: return f'ERR {str(ex)[:40]}'
for name, path, col in [('prices_hourly', 'data/prices_hourly.csv', 'date'), ('adq2 preDA', 'cache/ieso_adq2_preDA.csv', 'date'), ('load fc (Warehouse)', 'cache/ieso_load_fc.csv', 'EffectiveDateTime'),
                        ('wind fc (Warehouse)', 'cache/ieso_wind_fc.csv', 'EffectiveDateTime'), ('load actual', 'cache/ieso_load_actual.csv', 'EffectiveDateTime'), ('fwd settles', 'cache/fwd_daily_ontario.csv', 'EffectiveDate'),
                        ('fx', 'cache/fx_usdcad.csv', 'Date'), ('NYISO DAM', 'data/nyiso_dam_energy.csv', 'date'), ('intertie actual', 'data/intertie_actual.csv', 'date'), ('adq3 final', 'data/adq3_final.csv', 'date'),
                        ('outage features', 'data/outage_features.csv', 'date'), ('hydro fc bt', 'data/bt_hydro_fc.csv', 'date'), ('wx forecast cache', 'cache/ieso_wx_fc.csv', 'EffectiveDateTime'),
                        ('CYYZ actual wx', 'cache/cyyz_weather_actual.csv', 'EffectiveDateTime'), ('NRG zones', 'data/nrg/on_zones_nrg.csv.gz', 'ts_ept_begin'), ('dynasty virtuals', 'cache/dynasty_virtuals.csv', 'date')]:
    P(f'  {name:22s} {last(path, col)}')
P(f'  fuel actual            {C.fuel_actual().date.max()}')
for z in ('EAST', 'OTTAWA'):
    e = pd.read_csv(C.DATA / f'dv_frame_{z}.csv'); e = e[e.da.notna()]; e['m'] = e.date.str[:7]
    P(f'\n=== 2. {z}: DA forecast by month (MAE, bias, P10-P90 coverage target 80%) ===')
    g = e[e.date >= '2026-05-01'].groupby('m')
    P(pd.DataFrame({'hours': g.size(), 'mae': g.apply(lambda x: (x.p_da - x.da).abs().mean()), 'bias': g.apply(lambda x: (x.p_da - x.da).mean()),
                    'cover': g.apply(lambda x: ((x.da >= x.q10) & (x.da <= x.q90)).mean() * 100), 'below_q10': g.apply(lambda x: (x.da < x.q10).mean() * 100),
                    'above_q90': g.apply(lambda x: (x.da > x.q90).mean() * 100)}).round(1).to_string())
    e['ours'] = np.where(e.v2 == 1, 5, np.where(e.buyband == -1, 1, 0)); x = e[e.rt.notna()]
    P(f'--- {z}: ladder P&L by month (v2 sell=5 / buy band=1), $ ---')
    rows = []
    for m, t in x[x.date >= '2026-05-01'].groupby('m'):
        r = B.run_ladder(t, 'ours', m); s5 = B.run_ladder(t.assign(sc=np.where(t.ours == 5, 5, 0)), 'sc', ''); s1 = B.run_ladder(t.assign(sc=np.where(t.ours == 1, 1, 0)), 'sc', '')
        rows.append(dict(month=m, total=r['total'], usd_mwh=r['usd_per_mwh'], sells=s5['total'], sell_mwh=s5['usd_per_mwh'], buys=s1['total'], buy_mwh=s1['usd_per_mwh'], days_up=r['days_up']))
    P(pd.DataFrame(rows).to_string(index=False))
    P(f'--- {z}: last 30 days split ---'); t = x[x.date >= (pd.Timestamp(x.date.max()) - pd.Timedelta(days=30)).date().isoformat()]
    for nm, msk in (('v2 sell hours', t.v2 == 1), ('buy band hours', (t.buyband == -1) & (t.v2 != 1)), ('no-signal hours', (t.v2 != 1) & (t.buyband != -1))):
        q = t[msk]; P(f'  {nm:16s} hours {len(q):4d}  DA-RT avg {(q.da - q.rt).mean():+6.2f}  RT>DA {(q.rt > q.da).mean()*100:4.0f}%')
P('\n=== 3. Gates thresholds: stable across seasons? (East RT-DA, bid-time reads) ===')
import gates_tab as G
f = G.hist_frame('2026-11-01'); f['half'] = np.where(f.date < '2026-09-01', 'Jul-Aug', 'Sep-Oct')
def b(x):
    return pd.Series(dict(hrs=len(x), avg=x.x.mean(), med=x.x.median(), up=(x.x > 0).mean() * 100))
f['shiftb'] = pd.cut(f['shift'], [-9e9, -400, -200, 200, 400, 9e9]); P(f.groupby(['shiftb', 'half']).apply(b).round(1).unstack('half').to_string())
f['tight'] = np.select([(f.need >= 6000) & (f.sp < 1500), f.need >= 6000], ['need6k+ spare<1.5k', 'need6k+ spare ok'], 'need<6k'); P(f.groupby(['tight', 'half']).apply(b).round(1).unstack('half').to_string())
f['floor'] = pd.cut(f.need, [-1, 2500, 3500, 99999], labels=['<2.5k', '2.5-3.5k', '>3.5k']); P(f.groupby(['floor', 'half']).apply(b).round(1).unstack('half').to_string())
P('\n=== 4. RT P50 live log ===')
try:
    l = pd.read_csv(C.DATA / 'rt_read_log.csv'); p = C.prices('EAST'); m = l[l.zone == 'EAST'].merge(p, on=['date', 'he']).dropna(subset=['rt'])
    P(f'  days {m.date.nunique()}, MAE {(m.rt_p50 - m.rt).abs().mean():.1f}, DA-fc-only MAE {(m.da_fc - m.rt).abs().mean():.1f}, in P10-P90 {((m.rt >= m.rt_p10) & (m.rt <= m.rt_p90)).mean()*100:.0f}%')
except Exception as ex: P('  ', ex)
