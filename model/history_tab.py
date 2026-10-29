"""history_tab.py -- Oct 28 2026. History tab (display only): the last 7 settled delivery days, hour by hour, for East and Ottawa:
DA, RT (hourly average of the 5-minute prices, IESO archive), RT - DA, and the fundamentals as they stood at the bid next to what
actually happened. Sources:
  prices        data/prices_hourly.csv (IESO public reports); cross-checked against the NRG zonal file where it overlaps
  at the bid    IESO pre-DA Adequacy (load, wind, solar, nuclear, gas available), Meteologica load / wind as loaded before the bid,
                gas need / spare from the saved bid-time read (data/fund_history.json) -- blank on days no read was saved
  actual        Ontario demand (IESO), generator output by fuel (IESO GenOutputbyFuelHourly)
Also: daily RT - DA by hour for every settled day (both hubs) for the Correlation tab."""
import sys, json; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, supply_fc as S
J = lambda v, k=0: None if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v) else (round(float(v), k) if k else int(round(float(v))))

def _checks(p, days):
    """data checks for the days shown: missing hours, and (where it overlaps) agreement with the independent NRG zonal file."""
    out = {}
    for z in ('EAST', 'OTTAWA'):
        q = p[(p.zone == z) & p.date.isin(days)]
        out[z] = dict(missing_rt=[f"{r.date[5:]} HE{int(r.he)}" for r in q[q.rt.isna()].itertuples()], missing_da=int(q.da.isna().sum()),
                      dup=int(q.duplicated(['date', 'he']).sum()))
    try:
        import nrg_import as N
        n = pd.read_csv(C.DATA / 'nrg' / 'on_zones_nrg.csv.gz'); n['date'], n['he'] = N.to_key(n.ts_ept_begin); n = n.dropna(subset=['he']); n['he'] = n.he.astype(int)
        m = p[p.zone == 'EAST'].merge(n[['date', 'he', 'EAST_DA', 'EAST_RT']], on=['date', 'he']); m = m[m.date >= '2026-09-01']
        out['nrg'] = dict(through=n.date.max(), hours=len(m), da_off=int(((m.da - m.EAST_DA).abs() > .05).sum()), rt_off=int(((m.rt - m.EAST_RT).abs() > .5).sum()))
    except Exception as ex: out['nrg'] = {'error': str(ex)}
    try:
        dm = pd.read_csv(C.ARCH / 'Demand' / f'PUB_Demand_{D_YEAR}.csv', skiprows=3).rename(columns={'Date': 'date', 'Hour': 'he'})
        L = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'ont_dem']]; m = dm[dm.date.isin(days)].merge(L, on=['date', 'he'])
        out['load'] = dict(hours=len(m), off=int(((m['Ontario Demand'] - m.ont_dem).abs() > 2).sum()))
    except Exception as ex: out['load'] = {'error': str(ex)}
    return out
D_YEAR = 2026

def bid_need(D):
    """gas expected online at the bid, rebuilt from the archives with the live formula (signals_v2.day):
    IESO load - nuclear available - IESO wind - solar - hydro + net exports, hydro / exports = 14-day median of DA schedules through D-2.
    Matches every saved morning read to within 0.5 MW (checked Oct 20-28)."""
    import signals_v2 as SV
    a = C.adq2('preDA'); t = a[a.date == D].set_index('he'); s = SV.schedules()
    cut = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(cut) - pd.Timedelta(days=14)).date().isoformat()
    m = s[(s.date <= cut) & (s.date > lo)].dropna(subset=['hydro_sch']).groupby('he')[['hydro_sch', 'da_net_exp']].median()
    need = t.dem_fc - t.nuc_av - t.wind_fc.fillna(0) - t.solar_fc.fillna(0) - m.hydro_sch + m.da_net_exp
    return pd.DataFrame({'he': need.index, 'need_r': need.values, 'sp_r': (t.gas_av - need).values})

def build(D, n=7):
    p = pd.read_csv(C.DATA / 'prices_hourly.csv'); p = p[p.zone.isin(['EAST', 'OTTAWA'])]
    rtn = p.groupby(['date', 'zone']).rt.count().unstack().min(axis=1); dan = p.groupby(['date', 'zone']).da.count().unstack().min(axis=1)
    days = [d for d in sorted(rtn.index) if d < D and rtn.get(d, 0) >= 20 and dan.get(d, 0) >= 24][-n:]
    a = C.adq2('preDA')[['date', 'he', 'dem_fc', 'wind_fc', 'solar_fc', 'nuc_av', 'gas_av', 'head']]
    L = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'lf_meteologica', 'lf_tesla', 'ont_dem']]
    W = S.wind_at_bid()[['date', 'he', 'wf_meteologica']]
    G = C.fuel_actual()[['date', 'he', 'g_gas', 'g_wind', 'g_nuclear', 'g_hydro', 'g_solar']]
    h = json.loads((C.DATA / 'fund_history.json').read_text())
    F = pd.DataFrame([dict(date=k, he=x['he'], need=x.get('need'), sp=x.get('sp')) for k, v in h.items() for x in v])
    x = a[a.date.isin(days)].merge(L, on=['date', 'he'], how='left').merge(W, on=['date', 'he'], how='left').merge(G, on=['date', 'he'], how='left')
    x = x.merge(F, on=['date', 'he'], how='left')
    R = pd.concat([bid_need(d).assign(date=d) for d in days]); x = x.merge(R, on=['date', 'he'], how='left')
    x['need'] = x.need.fillna(x.need_r); x['sp'] = x.sp.fillna(x.sp_r)
    out = {'days': [], 'hubs': {}, 'checks': _checks(p, days)}
    for d in days:
        g = x[x.date == d].sort_values('he'); saved = d in h
        rows = [dict(he=int(r.he), dem=J(r.dem_fc), met=J(r.lf_meteologica), tes=J(r.lf_tesla), act=J(r.ont_dem), w=J(r.wind_fc), wm=J(r.wf_meteologica),
                     wact=J(r.g_wind), need=J(r.need), gas=J(r.g_gas), sp=J(r.sp), head=J(getattr(r, 'head')),
                     shift=None if pd.isna(r.lf_meteologica) or pd.isna(r.wf_meteologica) else J((r.lf_meteologica - r.dem_fc) + (r.wind_fc - r.wf_meteologica)))
                for r in g.itertuples()]
        out['days'].append(dict(date=d, dow=pd.Timestamp(d).day_name()[:3], saved=saved, rebuilt=not saved, rows=rows))
    for z in ('EAST', 'OTTAWA'):
        q = p[(p.zone == z) & p.date.isin(days)]
        out['hubs'][z] = {d: [[int(r.he), J(r.da, 2), J(r.rt, 2)] for r in q[q.date == d].sort_values('he').itertuples()] for d in days}
    return out

def corr_data():
    """{zone: {date: [RT-DA HE1..24]}} for every day with all 24 hours settled (both hubs)."""
    p = C.prices(None)
    out = {}
    for z in ('EAST', 'OTTAWA'):
        q = p[p.zone == z].dropna(subset=['da', 'rt']); q = q.assign(x=q.rt - q.da)
        w = q.pivot_table(index='date', columns='he', values='x').reindex(columns=range(1, 25)).dropna()
        out[z] = {d: [round(float(v), 1) for v in r] for d, r in w.iterrows()}
    return out

if __name__ == '__main__':
    b = json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text()); o = build(b['target'])
    print([ (d['date'], d['saved']) for d in o['days']]); print(o['checks']); print(o['days'][-1]['rows'][16])
    print(o['hubs']['EAST'][o['days'][-1]['date']][16])
    c = corr_data(); print({z: (len(v), min(v), max(v)) for z, v in c.items()})
