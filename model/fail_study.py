"""fail_study.py -- the days our SELL calls lost because RT beat DA. What happened, what we could have seen at bid time.
Frame = data/dv_frame_<zone>.csv (walk-forward v2 SELL, bid-time inputs) + what was learned AFTER the deadline:
  final-vintage Adequacy2 (end of D-1): demand fc, gas / nuclear / hydro outages, wind fc  -> 'post-bid surprises'
  actual Ontario demand (IESO), CYYZ temperature, actual intertie flow, RT intertie limits, NRG pre-dispatch hub price."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 260); pd.set_option('display.max_rows', 300); pd.set_option('display.max_columns', 60)

def hourly_actual(f, col, name, ts='EffectiveDateTime'):
    x = pd.read_csv(C.CACHE / f); t = pd.to_datetime(x[ts].str.slice(0, 19)) + pd.Timedelta(hours=1)   # hour-beginning EST -> ending
    x['date'], x['he'] = C._ts_to_key(t); x = x[x.he.notna()]; x['he'] = x.he.astype(int)
    return x.groupby(['date', 'he'])[col].last().rename(name).reset_index()

def frame(zone):
    e = pd.read_csv(C.DATA / f'dv_frame_{zone}.csv')
    fin = C.adq2('final')[['date', 'he', 'dem_fc', 'gas_out', 'nuc_out', 'hyd_out', 'wind_fc', 'head', 'gas_av', 'hyd_av', 'nuc_av']]
    fin.columns = ['date', 'he'] + ['f_' + c for c in fin.columns[2:]]
    e = e.merge(fin, on=['date', 'he'], how='left')
    e = e.merge(hourly_actual('ieso_load_actual.csv', 'Load', 'dem_act'), on=['date', 'he'], how='left')
    e = e.merge(hourly_actual('cyyz_weather_actual.csv', 'Temperature', 'temp'), on=['date', 'he'], how='left')
    ia = pd.read_csv(C.DATA / 'intertie_actual.csv')[['date', 'he', 'tot_flow', 'ny_flow']]
    e = e.merge(ia, on=['date', 'he'], how='left')
    r = pd.read_csv(C.DATA / 'nrg' / 'rt_intertie_limits.csv'); im = [c for c in r if c.endswith('_IMP')]; ex = [c for c in r if c.endswith('_EXP')]
    r['rt_imp_cap'] = r[im].sum(axis=1); r['rt_exp_cap'] = -r[ex].sum(axis=1)
    e = e.merge(r[['date', 'he', 'rt_imp_cap', 'rt_exp_cap']], on=['date', 'he'], how='left')
    import supply_fc as SF
    L = SF.limits_at_bid()[['date', 'he', 'exp_cap', 'imp_cap']]; e = e.merge(L, on=['date', 'he'], how='left')
    n = pd.read_csv(C.DATA / 'nrg' / 'hub_prices_nrg.csv'); n = n[n.zone == zone][['date', 'he', 'pd', 'rt_sd5']]
    e = e.merge(n, on=['date', 'he'], how='left')
    # surprises (after the deadline)
    e['miss_load'] = e.dem_act - e.dem_fc                        # + = load came in above IESO's bid-time forecast
    e['miss_gas_out'] = e.f_gas_out - e.gas_out; e['miss_nuc_out'] = e.f_nuc_out - e.nuc_out
    e['miss_wind'] = e.f_wind_fc - e.wind_fc                      # + = more wind than forecast at bid
    e['miss_head'] = e.f_head - e['head']
    e['miss_exp'] = e.tot_flow - e.exp_exp                        # + = exported more than expected
    e['miss_implim'] = e.rt_imp_cap - e.imp_cap
    # bid-time context
    e['gapT'] = e.lf_tesla - e.dem_fc
    for k in ('temp', 'sp', 'rt'):
        y = e[['date', 'he', k]].copy(); y['date'] = (pd.to_datetime(y.date) + pd.Timedelta(days=2)).dt.date.astype(str)
        e = e.merge(y.rename(columns={k: k + '_d2'}), on=['date', 'he'], how='left')
    y = e[['date', 'he', 'temp']].copy(); y['date'] = (pd.to_datetime(y.date) + pd.Timedelta(days=1)).dt.date.astype(str)
    e = e.merge(y.rename(columns={'temp': 'temp_d1'}), on=['date', 'he'], how='left')
    return e

def days(e):
    s = e[(e.v2 == 1) & e.sp.notna()].copy()
    g = s.groupby('date').agg(sell_h=('sp', 'size'), pl=('sp', 'sum'), worst=('sp', 'min'), rt_max=('rt', 'max'), da_mean=('da', 'mean'),
                              head=('head', 'mean'), f_head=('f_head', 'mean'), miss_load=('miss_load', 'mean'), miss_gas_out=('miss_gas_out', 'mean'),
                              miss_nuc_out=('miss_nuc_out', 'mean'), miss_wind=('miss_wind', 'mean'), miss_exp=('miss_exp', 'mean'),
                              miss_implim=('miss_implim', 'mean'), gapT=('gapT', 'mean'), temp=('temp', 'max'), temp_d1=('temp_d1', 'max'),
                              sp_d2=('sp_d2', 'mean'), dow=('dow', 'first'))
    return g

if __name__ == '__main__':
    z = sys.argv[1] if len(sys.argv) > 1 else 'TORONTO'
    e = frame(z); e.to_csv(C.DATA / f'fs_frame_{z}.csv', index=False)
    g = days(e); g.to_csv(C.DATA / f'fs_days_{z}.csv')
    print(f'{z}: SELL days {len(g)}, losing days {(g.pl < 0).sum()}, loss on losing days {g.pl[g.pl < 0].sum():,.0f} $/MW, gains on winning days {g.pl[g.pl > 0].sum():,.0f}')
    L = g[g.pl < 0].sort_values('pl'); print(L.head(40).round(0).to_string())

DRIVERS = {'load above IESO fc': 'miss_load', 'wind below fc': 'neg_wind', 'outages added after bid': 'miss_out', 'exports above expected': 'miss_exp', 'RT import limit cut': 'neg_implim'}
def diagnose(e, n=25):
    """Worst losing SELL days. For each, the loss-weighted mean of each post-bid surprise in MW of lost headroom,
    and what we could have seen at bid time (Tesla/Dynasty vs IESO, bid headroom, D-2 spread, yesterday's temp)."""
    s = e[(e.v2 == 1) & e.sp.notna()].copy()
    s['neg_wind'] = -s.miss_wind; s['miss_out'] = s.miss_gas_out.fillna(0) + s.miss_nuc_out.fillna(0); s['neg_implim'] = -s.miss_implim
    s['w'] = (-s.sp).clip(lower=0)
    rows = []
    for d, g in s.groupby('date'):
        if g.sp.sum() >= 0: continue
        w = g.w if g.w.sum() > 0 else pd.Series(1, index=g.index)
        mw = {k: float(np.average(g[c].fillna(0), weights=w)) for k, c in DRIVERS.items()}
        top = max(mw, key=mw.get); big = mw[top]
        lh = g[g.sp < 0]; hrs = f"HE{int(lh.he.min())}-{int(lh.he.max())}" if len(lh) else ''
        why = top if big >= 250 else ('scarcity: bid headroom < 3,000' if g['head'].min() < 3000 else 'no single surprise >= 250 MW')
        rows.append(dict(date=d, dow='MTWTFSS'[int(g.dow.iloc[0])], sell_h=len(g), loss_per_mw=round(g.sp.sum()), rt_max=round(g.rt.max()), da_avg=round(g.da.mean()),
                         loss_hours=hrs, bid_head_min=round(g['head'].min()), **{k: round(v) for k, v in mw.items()}, main_cause=why,
                         tesla_minus_ieso=round(g.gapT.mean()), dyn_minus_ieso=round((g.lf_dynasty - g.dem_fc).mean()) if g.lf_dynasty.notna().any() else None,
                         sp_d2=round(g.sp_d2.mean(), 1), temp_max=g.temp.max(), temp_d1=g.temp_d1.max(), why_sell='tight' if g['head'].mean() < 8000 else 'surplus'))
    return pd.DataFrame(rows).sort_values('loss_per_mw')
