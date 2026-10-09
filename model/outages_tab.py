"""outages_tab.py -- everything the Outages tab shows, as one dict for the bundle.
  now      : tomorrow's outage MW by fuel at the bid (IESO pre-DA), as a share of capacity, against the 2019-25 normal for the month;
             units that tripped in the last 24 h; MW IESO assumes will return; units out right now (latest GenOutputCapability version)
  fwd35    : IESO's 35-day schedule (data/fwd35.csv from ieso_fwd35.py), daily peak-hour view, plus the 'expected actual' gas outage
             = schedule + the typical unscheduled additions at that lead (measured on 17 months of Adequacy vintages)
  outlook  : IESO 18-month Reliability Outlook weekly reductions (latest and previous edition) + how well past editions did
  seasonal : month x fuel outage ratio P10..P90 (2019-25) and gas trip counts per month
  watch    : plain-language items for the next 35 days"""
import sys, re, zipfile; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
G = C.DATA / 'genoutcap'
MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
J = lambda v, d=0: None if v is None or (isinstance(v, float) and np.isnan(v)) else (round(float(v), d) if d else int(round(float(v))))

def lead_bias():
    """mean (final - scheduled) gas and nuclear outage MW by lead 1..34 days (1 = bid-time)."""
    l = pd.read_csv(C.CACHE / 'ieso_adq2_leads.csv'); l = l[l.subtype.isin(['Gas Outage', 'Nuclear Outage'])]
    w = l.pivot_table(index=['date', 'hour', 'lead'], columns='subtype', values='value').reset_index().rename(columns={'hour': 'he', 'Gas Outage': 'gas', 'Nuclear Outage': 'nuc'})
    f = C.adq2('final')[['date', 'he', 'gas_out', 'nuc_out']]; p = C.adq2('preDA')[['date', 'he', 'gas_out', 'nuc_out']]
    m = w.merge(f, on=['date', 'he']); b = (m.gas_out - m.gas).groupby(m.lead).mean(); n = (m.nuc_out - m.nuc).groupby(m.lead).mean()
    q = p.merge(f, on=['date', 'he'], suffixes=('_p', '')); b[1] = (q.gas_out - q.gas_out_p).mean(); n[1] = (q.nuc_out - q.nuc_out_p).mean()
    f34 = C.CACHE / 'ieso_adq2_leads34.csv'
    if f34.exists():
        x = pd.read_csv(f34); x = x[x.subtype.isin(['Gas Outage', 'Nuclear Outage'])]
        x = x.pivot_table(index=['date', 'hour', 'lead'], columns='subtype', values='value').reset_index().rename(columns={'hour': 'he', 'Gas Outage': 'gas', 'Nuclear Outage': 'nuc'}).merge(f, on=['date', 'he'])
        b = pd.concat([b, (x.gas_out - x.gas).groupby(x.lead).mean()]); n = pd.concat([n, (x.nuc_out - x.nuc).groupby(x.lead).mean()])
    b = b.sort_index(); n = n.sort_index()
    full = pd.DataFrame(index=range(1, 35)); full['gas'] = b; full['nuc'] = n
    full = full.interpolate().ffill()          # beyond the measured leads: hold the last measured value (flagged on the page)
    full['measured'] = [i in b.index for i in full.index]
    return full

def units_out():
    """Units with capability < 50% of their rating in the latest archived GenOutputCapability version."""
    import parse_archive as PA
    zs = sorted((C.ARCH / 'GenOutputCapability').glob('*.zip'))
    if not zs: return [], None
    z = zipfile.ZipFile(zs[-1]); names = z.namelist()
    key = lambda n: (re.search(r'_(\d{8})', n).group(1), int((re.search(r'_v(\d+)', n) or [0, 0])[1]) if re.search(r'_v(\d+)', n) else 999)
    n = sorted(names, key=key)[-1]; r = PA.xml(z.read(n))
    R = pd.read_csv(G / 'unit_ratings.csv').set_index('unit').rating.to_dict()
    now_h = None; out = []
    for g in r.iter('Generator'):
        nm, fu = g.find('GeneratorName').text, g.find('FuelType').text
        if fu not in ('GAS', 'NUCLEAR', 'HYDRO'): continue
        caps = {PA.t(c, 'Hour', int): PA.t(c, 'EnergyMW') for c in g.iter('Capability')}
        caps = {h: v for h, v in caps.items() if h and v is not None}
        if not caps: continue
        h = max(caps); now_h = h; cap = caps[h]; rt = R.get(nm) or 0
        if rt >= 50 and cap < 0.5 * rt: out.append(dict(unit=nm, fuel=fu.title(), rating=round(rt), cap=round(cap), out=round(rt - cap)))
    d = re.search(r'_(\d{8})', n).group(1)
    return sorted(out, key=lambda x: -x['out']), f'{d[:4]}-{d[4:6]}-{d[6:]} HE{now_h} ({n.split("/")[-1]})'

def look30(D):
    """Last 30 delivery days before D plus D itself: outage MW at the bid (peak HE8-21 mean) by fuel, MW added after the bid,
    trips, tightest bid-time headroom, realised East DA-RT. Tomorrow is compared with the 30 days (mean, P75, P90, rank)."""
    import outage_priced as OP
    d = OP.daily(); a = C.adq2('preDA'); a = a[a.he.between(8, 21)].groupby('date')['head'].min().rename('head_min').reset_index()
    p = C.prices('EAST'); p = p[p.he.between(8, 21)].assign(sp=lambda x: x.da - x.rt).groupby('date').sp.mean().rename('sp_east').reset_index()
    d = d.merge(a, on='date', how='left').merge(p, on='date', how='left')
    past = d[(d.date < D)].tail(30); t = d[d.date == D]
    try: last_v = pd.read_csv(C.CACHE / 'ieso_adq2_outage_timeline.csv', usecols=['ieso_createtime']).ieso_createtime.max()[:10]
    except Exception: last_v = D
    rows = [dict(date=r.date, gas=J(r.gas_bid), nuc=J(r.nuc_bid), hyd=J(r.hyd_bid), tot=J(r.out_bid), add=J(r.add_after), final=J(r.out_bid + r.add_after) if pd.notna(r.add_after) else None,
                 trips=J(r.trips), head=J(r.head_min), sp=J(r.sp_east, 2), partial=bool(r.date >= last_v)) for r in past.itertuples()]
    cmp = {}
    if len(t):
        r = t.iloc[0]
        for k, c in (('tot', 'out_bid'), ('gas', 'gas_bid'), ('nuc', 'nuc_bid'), ('hyd', 'hyd_bid')):
            v = past[c]; x = float(r[c])
            cmp[k] = dict(v=J(x), mean=J(v.mean()), p25=J(v.quantile(.25)), p75=J(v.quantile(.75)), p90=J(v.quantile(.9)), mx=J(v.max()),
                          rank=int((v < x).sum()), n=int(v.notna().sum()), z=J((x - v.mean()) / v.std(), 2) if v.std() > 0 else None)
        cmp['head'] = J(r.head_min); cmp['trips'] = J(r.trips)
    return dict(rows=rows, tomorrow=cmp, date=D)

def build(D, trips=None):
    N = pd.read_csv(G / 'norms.csv'); m = pd.Timestamp(D).month
    nr = lambda fu, mo=m: N[(N.fuel == fu) & (N.month == mo)].iloc[0]
    pre = C.adq2('preDA'); x = pre[pre.date == D]
    now = {}
    for fu, o, c in (('gas', 'gas_out', 'gas_cap'), ('nuclear', 'nuc_out', 'nuc_cap'), ('hydro', 'hyd_out', 'hyd_cap')):
        if not len(x): break
        pk = x[x.he.between(8, 21)]; n = nr(fu)
        now[fu] = dict(out=J(pk[o].mean()), cap=J(pk[c].mean()), ratio=J((pk[o] / pk[c]).mean(), 3),
                       p25=J(n.p25, 3), p50=J(n.p50, 3), p75=J(n.p75, 3), p90=J(n.p90, 3))
    o = pd.read_csv(C.DATA / 'outage_features.csv'); o = o[o.date == D]
    ret = J(o.ret_assumed.mean()) if len(o) else None
    uo, uo_asof = units_out()
    # 35-day schedule
    lb = lead_bias(); fwd = []
    f = C.DATA / 'fwd35.csv'
    if f.exists():
        F = pd.read_csv(f); snap = F.snapshot.max(); F = F[F.snapshot == snap]
        for d, g in F.groupby('date'):
            pk = g[g.he.between(8, 21)]; lead = (pd.Timestamp(d) - pd.Timestamp(snap)).days
            add = float(lb.gas.get(min(max(lead, 1), 34), np.nan)); addn = float(lb.nuc.get(min(max(lead, 1), 34), np.nan))
            head = (pk.gas_cap - pk.gas_out + pk.hydro_cap - pk.hydro_out) - (pk.dem_fc - (pk.nuclear_cap - pk.nuclear_out) - pk.wind_fc.fillna(0) - pk.solar_fc.fillna(0))
            n = nr('gas', pd.Timestamp(d).month)
            fwd.append(dict(date=d, lead=lead, gas=J(pk.gas_out.mean()), nuc=J(pk.nuclear_out.mean()), hyd=J(pk.hydro_out.mean()),
                            gas_cap=J(pk.gas_cap.mean()), nuc_cap=J(pk.nuclear_cap.mean()), dem_peak=J(g.dem_fc.max()),
                            gas_exp=J(pk.gas_out.mean() + add), nuc_exp=J(pk.nuclear_out.mean() + addn), add_measured=bool(lb.measured.get(min(max(lead, 1), 34), False)),
                            head_min=J(head.min()), gas_norm_p50=J(n.p50 * pk.gas_cap.mean()), gas_norm_p75=J(n.p75 * pk.gas_cap.mean()), gas_norm_p25=J(n.p25 * pk.gas_cap.mean())))
        fsnap = snap
    else: fsnap = None
    # 18-month outlook
    R = pd.read_csv(C.DATA / 'outlook' / 'ro_weekly.csv'); eds = sorted(R.edition.unique())
    last, prev = eds[-1], (eds[-2] if len(eds) > 1 else None)
    L = R[R.edition == last][['week_end', 'demand', 'nuc_red', 'gas_red']]
    if prev: L = L.merge(R[R.edition == prev][['week_end', 'nuc_red', 'gas_red']].rename(columns={'nuc_red': 'nuc_prev', 'gas_red': 'gas_prev'}), on='week_end', how='left')
    A = pd.read_csv(C.DATA / 'outlook' / 'ro_vs_actual.csv')
    acc = {k: dict(weeks=len(A), corr=J(A[k + '_ro'].corr(A[k + '_act']), 2), bias=J((A[k + '_ro'] - A[k + '_act']).mean()), mae=J((A[k + '_ro'] - A[k + '_act']).abs().mean())) for k in ('gas', 'nuc')}
    io = pd.read_csv(C.DATA / 'outlook' / 'ro_intertie_outages.csv', parse_dates=['start', 'end'])
    io = io[(io.end >= pd.Timestamp(D)) & (io.start <= pd.Timestamp(D) + pd.Timedelta(days=60))]
    ties = [dict(start=r.start.strftime('%Y-%m-%d'), end=r.end.strftime('%Y-%m-%d'), station=str(r.station)[:60], recall=str(r.recall),
                 interface=str(r.interface).replace('\n', ' / '), reduction=str(r.reduction).replace('\n', ' / ')) for r in io.itertuples()]
    # seasonal
    E = pd.read_csv(G / 'events.csv', parse_dates=['start']); E = E[(E.start >= '2019-06-01') & (E.start < '2026-01-01') & (E.fuel == 'GAS')]
    trips_m = (E[E.hours <= 24].groupby('month').size() / 6.5).round(1).to_dict()
    seas = []
    for mo in range(1, 13):
        g_, n_, h_ = nr('gas', mo), nr('nuclear', mo), nr('hydro', mo)
        seas.append(dict(month=MON[mo - 1], gas_p25=J(g_.p25, 3), gas_p50=J(g_.p50, 3), gas_p75=J(g_.p75, 3), gas_p90=J(g_.p90, 3), gas_mw=J(g_.mean_mw),
                         nuc_p50=J(n_.p50, 3), nuc_p90=J(n_.p90, 3), hyd_p50=J(h_.p50, 3), gas_trips=trips_m.get(mo)))
    # watch list: each item tagged baked (already in tomorrow's headroom / DA / sizing), context (later days, not tomorrow's bid), ignore
    W = []
    add = lambda text, tag: W.append(dict(text=text, tag=tag))
    def tie_tag(t):
        big = any(float(x) >= 100 for x in re.findall(r'\d+', t['reduction']) or ['0'])
        near = t['start'] <= (pd.Timestamp(D) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        return ('baked' if near else 'context') if (big or 'PQ' in t['interface'] or 'NY' in t['interface'] or 'QC' in t['interface']) else 'ignore'
    if now.get('gas') and now['gas']['ratio'] is not None:
        g = now['gas']; lvl = 'above' if g['ratio'] > g['p75'] else 'below' if g['ratio'] < g['p25'] else 'inside'
        add(f"Tomorrow's gas outages are {g['out']:,} MW ({g['ratio']*100:.0f}% of capacity), {lvl} the normal {MON[m-1]} range ({g['p25']*100:.0f}–{g['p75']*100:.0f}%).", 'baked')
    if trips:
        t = max(v for v in trips.values() if v is not None) if any(v is not None for v in trips.values()) else None
        if t is not None and t >= 500: add(f'{t:,} MW of units tripped in the last 24 h: tight score-5 sells get the ×1.5 size (tested; no edge on surplus sells).', 'baked')
    if ret is not None and ret >= 500: add(f'IESO assumes {ret:,} MW will be back tomorrow. Returns slip: when it assumes 1,000+ MW, about 700 MW is added back after the bid (already priced into DA on average).', 'baked')
    for a_, b_ in zip(fwd[:-1], fwd[1:]):
        if a_['gas'] is not None and b_['gas'] is not None and b_['gas'] - a_['gas'] >= 800: add(f"{b_['date']}: scheduled gas outages step up {b_['gas']-a_['gas']:,} MW to {b_['gas']:,} MW.", 'context')
        if a_['nuc'] is not None and b_['nuc'] is not None and abs(b_['nuc'] - a_['nuc']) >= 600: add(f"{b_['date']}: scheduled nuclear outages {'rise' if b_['nuc']>a_['nuc'] else 'fall'} {abs(b_['nuc']-a_['nuc']):,} MW to {b_['nuc']:,} MW.", 'context')
    tight = [r for r in fwd if r['head_min'] is not None and r['head_min'] < 6000]
    if tight:
        lo = min(tight, key=lambda r: r['head_min'])
        add(f"Scheduled headroom under 6,000 MW on {len(tight)} of the next {len(fwd)} days ({', '.join(r['date'][5:] for r in tight[:8])}{'…' if len(tight) > 8 else ''}); lowest {lo['head_min']:,} MW on {lo['date']}. That is before the ~300–750 MW of unscheduled gas outages IESO typically adds.", 'context')
    for t in ties:
        if t['interface'] in ('No Impact', 'nan', ''): continue
        add(f"Intertie outage {t['start']} → {t['end']}: {t['station']}, cuts {t['interface']} by {t['reduction']} MW (recall {t['recall']}).", tie_tag(t))
    try: L30 = look30(D)
    except Exception as ex: L30 = None; print('look30 skipped:', ex)
    if L30 and L30['tomorrow'].get('tot'):
        c = L30['tomorrow']['tot']; lvl = 'above the 30-day P75' if c['v'] > c['p75'] else 'inside the 30-day range'
        W.insert(0, dict(tag='baked', text=f"Tomorrow's outages at the bid: {c['v']:,} MW ({lvl}; last 30 days mean {c['mean']:,}, P75 {c['p75']:,}, max {c['mx']:,}; higher than {c['rank']} of {c['n']} days)."))
    import json as _j; pf = C.DATA / 'outage_priced.json'; priced = _j.loads(pf.read_text()) if pf.exists() else None
    try:
        import outage_returns as ORt; rets = dict(day=ORt.target(D), hist={z: ORt.summary(z) for z in ('EAST', 'OTTAWA')})
    except Exception as ex: print('outage returns skipped:', ex); rets = None
    return dict(returns=rets, look30=L30, priced=priced, now=now, ret_assumed=ret, units_out=uo[:25], units_out_asof=uo_asof, units_out_mw=sum(u['out'] for u in uo),
                fwd35=fwd, fwd35_snapshot=fsnap, lead_bias=[dict(lead=int(i), gas=J(r.gas), nuc=J(r.nuc), measured=bool(r.measured)) for i, r in lead_bias().iterrows()],
                outlook=dict(edition=last, prev=prev, weeks=L.round(0).to_dict('records'), accuracy=acc), intertie_outages=ties, seasonal=seas, watch=W)

if __name__ == '__main__':
    import json
    b = build(sys.argv[1] if len(sys.argv) > 1 else '2026-09-27')
    print(json.dumps({k: (v if k not in ('fwd35', 'outlook', 'seasonal', 'lead_bias') else '...') for k, v in b.items()}, indent=1, default=str)[:4000])
    print(b['fwd35'][:3]); print(b['lead_bias'][:5])
