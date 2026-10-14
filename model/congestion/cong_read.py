"""congestion/cong_read.py -- daily CONGESTION READ for delivery day D, built only from what is known at the bid
(IESO bid deadline D-1 09:00 EST). Read-only: it does not touch the desk model or its ladders.

    python model/congestion/cong_read.py 2026-10-15        # read for delivery Oct 15 (as of the bid, or as of now if earlier)
    python model/congestion/cong_read.py 2026-10-15 --json # also writes data/congestion/read_<D>.json (for the dashboard tab later)

Sources (all already archived by ieso_backfill.py each morning, except where noted):
  TxOutagesTodayAll + TxOutages1to30DaysPlanned  -> 500 kV equipment out on D, what starts / ends on D
  TxLimitsOutage0to2Days                         -> interface + intertie limits in force on D vs all-in-service
  DASecurityConstraints2 (D-1)                   -> which constraints the DA run enforced yesterday (archive added Oct 13)
  prices_hourly.csv (+ NRG zonal file to fill)   -> zone splits vs EAST: D-1 DA, D-2 RT, last 10 days
  Adequacy (pre-DA)                              -> wind / demand forecast for D
"""
import sys, re, json, zipfile, glob, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, nrg_import as N
import xml.etree.ElementTree as ET
NS = '{http://www.ieso.ca/schema}'
ARCH = C.ROOT / 'archive'
OUT = C.DATA / 'congestion'; OUT.mkdir(exist_ok=True)
ZONES = ['WEST', 'SOUTHWEST', 'NIAGARA', 'TORONTO', 'ESSA', 'OTTAWA', 'NORTHEAST', 'NORTHWEST']
MID = (10, 17)                                    # HE10-17: where the southern splits live
# all-in-service limits (IESO TxLimitsAllInService0to34Days, Oct 13 2026); used when that report is not archived yet
AIS = {'QFW': 2800, 'BLIP': 3000, 'NBLIP': 2000, 'FETT': 6400, 'FABCW': 7500, 'FS': 1750, 'FN': 1500, 'CLAN': 2000, 'CHIP': 1600,
       'FIO': 2900, 'FID': 390, 'SLW': 1350, 'EWTE': 500, 'EWTW': 500, 'TEK': 385, 'MissE': 600, 'MissW': 600, 'TEM': 450, 'KAO': 123, 'FAI': 235}
SOUTH_IF = {'QFW', 'BLIP', 'NBLIP', 'FETT', 'FABCW', 'FS', 'FN', 'CLAN', 'CHIP', 'SLW', 'FIO'}
# 500 kV station codes in line-section names -> where they sit (West/Bruce/SW side of FETT vs Toronto / East)
ST = {'LO': 'Longwood (W)', 'NA': 'Nanticoke (SW)', 'MD': 'Middleport (SW)', 'BU': 'Buchanan (W)', 'BR': 'Bruce', 'DE': 'Detweiler (SW)',
      'ML': 'Milton (SW)', 'TR': 'Trafalgar (SW)', 'CL': 'Claireville (TOR)', 'CH': 'Cherrywood (TOR)', 'PJ': 'Parkway Jct (TOR)', 'PR': 'Parkway (TOR)',
      'RV': 'Richview (TOR)', 'BO': 'Bowmanville (E)', 'LE': 'Lennox (E)', 'ES': 'Essa', 'HA': 'Hanmer (NE)', 'PI': 'Pinard (NE)', 'PO': 'Porcupine (NE)'}

def bid_cut(D):                                   # IESO time (EST): D-1 09:00
    return pd.Timestamp(D) - pd.Timedelta(days=1) + pd.Timedelta(hours=9)
def now_est():
    return pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(hours=5)

# ---------- archive helpers ----------
def members(report, d0, d1):
    """(zip, name, file-date) for files dated d0..d1 (dates in the file name)."""
    out = []
    for z in sorted(glob.glob(str(ARCH / report / '*.zip'))):
        for n in zipfile.ZipFile(z).namelist():
            m = re.search(r'_(\d{8})', n)
            if m and d0 <= m.group(1) <= d1: out.append((z, n, m.group(1)))
    return out
def vnum(n):
    m = re.search(r'_v(\d+)\.', n); return int(m.group(1)) if m else 10**6        # unversioned = latest
def created(raw):
    m = re.search(rb'<CreatedAt>([^<]+)', raw[:1500]); return pd.Timestamp(m.group(1).decode().strip()) if m else None
def latest_before(report, cut, back=3):
    d1 = cut.strftime('%Y%m%d'); d0 = (cut - pd.Timedelta(days=back)).strftime('%Y%m%d')
    c = sorted(members(report, d0, d1), key=lambda x: (x[2], vnum(x[1])), reverse=True)
    for z, n, _ in c:
        raw = zipfile.ZipFile(z).read(n); ca = created(raw)
        if ca is not None and ca <= cut: return ET.fromstring(raw), ca, n
    return None, None, None

# ---------- 1. transmission outages ----------
def outages(D, cut):
    D0, D1 = pd.Timestamp(D), pd.Timestamp(D) + pd.Timedelta(days=1); recs = {}; src = []
    for rep in ('TxOutagesTodayAll', 'TxOutages1to30DaysPlanned'):
        r, ca, n = latest_before(rep, cut, back=4)
        if r is None: continue
        src.append(f'{rep} {ca:%b %d %H:%M}')
        for o in r.iter(NS + 'OutageRequest'):
            g = lambda t: (o.find(NS + t).text or '').strip() if o.find(NS + t) is not None else ''
            eq = [(e.find(NS + 'EquipmentName').text.strip(), e.find(NS + 'EquipmentType').text, e.find(NS + 'EquipmentVoltage').text, e.find(NS + 'ConstraintType').text)
                  for e in o.iter(NS + 'EquipmentRequested')]
            big = [x for x in eq if x[2] == '500 kV' and x[3] == 'OOS' and re.search('Line|Transformer|Bus', x[1])]
            if not big: continue
            s, e = pd.Timestamp(g('PlannedStart')), pd.Timestamp(g('PlannedEnd'))
            recs[g('OutageID')] = dict(id=g('OutageID'), start=s, end=e, prio=g('Priority'), status=g('OutageRequestStatus'),
                                       equip='; '.join(sorted({x[0] for x in big})))
    rows = []
    for v in recs.values():
        if not (v['start'] < D1 and v['end'] > D0): continue
        tag = 'STARTS on D' if v['start'] >= D0 else ('ENDS on D' if v['end'] < D1 else ('new since D-1' if v['start'] >= D0 - pd.Timedelta(days=1) else 'in force'))
        codes = sorted({c for sec in re.findall(r'\.([A-Z]{2})X([A-Z]{2})', v['equip']) for c in sec})
        where = ', '.join(ST.get(c, c) for c in codes) or next((ST[k] for k in ST if k and ST[k].split(' (')[0].upper() in v['equip']), '')
        rows.append(dict(v, tag=tag, where=where, long=(v['end'] - v['start']).days > 60))
    o = pd.DataFrame(rows)
    if len(o): o = o.sort_values(['tag', 'start'])
    return o, src

# ---------- 2. interface / intertie limits ----------
def limits(D, cut):
    r, ca, n = latest_before('TxLimitsOutage0to2Days', cut, back=3)
    if r is None: return pd.DataFrame(), None
    D0, D1 = pd.Timestamp(D), pd.Timestamp(D) + pd.Timedelta(days=1); rows = []
    for f in r.iter(NS + 'TransmissionFacilityData'):
        fac = f.find(NS + 'TransmissionFacility').text
        for i in f.iter(NS + 'InterfaceData'):
            nm = i.find(NS + 'InterfaceName').text.strip(); s = pd.Timestamp(i.find(NS + 'StartDate').text); e = pd.Timestamp(i.find(NS + 'EndDate').text)
            if not (s < D1 and e > D0): continue
            k = re.search(r'\[([^\]]+)\]', nm); k = k.group(1) if k else nm
            lim = float(i.find(NS + 'OperatingLimit').text); ais = AIS.get(k)
            hrs = f'HE{max(1, int(((max(s, D0) - D0).total_seconds()) // 3600) + 1)}-{min(24, int(np.ceil((min(e, D1) - D0).total_seconds() / 3600)))}'
            rows.append(dict(fac=fac, iface=nm, key=k, limit=lim, ais=ais, pct=(lim / ais * 100 if ais else np.nan), hours=hrs,
                             south=k in SOUTH_IF or 'New York' in nm or 'Michigan' in nm, why=(i.find(NS + 'Comments').text or '').strip()))
    return pd.DataFrame(rows), ca

# ---------- 3. DA constraints enforced on D-1 ----------
def da_constraints(D):
    Dm1 = (pd.Timestamp(D) - pd.Timedelta(days=1)).strftime('%Y%m%d')
    c = sorted(members('DASecurityConstraints2', Dm1, Dm1), key=lambda x: vnum(x[1]), reverse=True)
    if not c: return None
    r = ET.fromstring(zipfile.ZipFile(c[0][0]).read(c[0][1])); fam = {}
    for h in r.iter(NS + 'HourlyConstraint'):
        he = int(h.find(NS + 'DeliveryHour').text); nm = re.sub(r'\s+', ' ', h.find(NS + 'Constraint').text).strip()
        f = '.'.join(re.sub(r'^.*? 0 ', '', nm).split('.')[:2]); fam.setdefault(f, set()).add(he)
    south = {k: sorted(v) for k, v in fam.items() if re.match(r'(S-|SW-|W-)', k)}
    fett = [k for k in south if 'FETT' in k and 'TAB1_AIS' not in k]
    return dict(south=south, fett_outage_table=fett, n_families=len(fam))

# ---------- 4. prices ----------
NRGMAP = {'NW': 'NORTHWEST', 'NE': 'NORTHEAST', 'NIAG': 'NIAGARA', 'SW': 'SOUTHWEST', 'TOR': 'TORONTO', 'OTT': 'OTTAWA', 'EAST': 'EAST', 'ESSA': 'ESSA', 'WEST': 'WEST'}
def price_frame():
    p = pd.read_csv(C.DATA / 'prices_hourly.csv')[['date', 'he', 'zone', 'da', 'rt']]
    f = C.DATA / 'nrg' / 'on_zones_nrg.csv.gz'
    if f.exists():
        n = pd.read_csv(f); n['date'], n['he'] = N.to_key(n.ts_ept_begin); n = n[n.he.notna()]; n['he'] = n.he.astype(int)
        n = pd.concat([n[['date', 'he']].assign(zone=z, da=n[k + '_DA'], rt=n[k + '_RT']) for k, z in NRGMAP.items()])
        p = p.set_index(['date', 'he', 'zone']); n = n.drop_duplicates(['date', 'he', 'zone']).set_index(['date', 'he', 'zone'])
        p = p.combine_first(n).reset_index()                       # IESO archive first, NRG only fills gaps
    w = p.pivot_table(index=['date', 'he'], columns='zone', values=['da', 'rt'])
    s = pd.DataFrame(index=w.index)
    for z in ZONES: s[z + '_da'] = w['da'][z] - w['da']['EAST']; s[z + '_rt'] = w['rt'][z] - w['rt']['EAST']
    return s.reset_index()
def mid(df, col):
    return df[df.he.between(*MID)].groupby('date')[col].mean()

# ---------- 5. regime history (prices only -> 17 months testable) ----------
def regime_stats(S, adq, D):
    """Episode ON for day X if D-1 DA West-East midday <= -5 or D-2 RT midday <= -5 (both known at the bid).
    Stats of the NEXT-day unpriced (RT split - DA split) midday, i.e. P&L per MW-h of sell zone / buy EAST = -(unpriced)."""
    days = sorted(S.date.unique()); m = {c: mid(S, c) for c in S.columns if c.endswith(('_da', '_rt'))}
    wnd = adq[adq.he.between(*MID)].groupby('date').wind_fc.mean()
    rows = []
    for i, X in enumerate(days):
        if X >= D or i < 2: continue
        x1, x2 = days[i - 1], days[i - 2]
        on = (m['WEST_da'].get(x1, 0) <= -5) or (m['WEST_rt'].get(x2, 0) <= -5)
        r = dict(date=X, on=on, wind=wnd.get(X, np.nan))
        for z in ('WEST', 'SOUTHWEST', 'NIAGARA'): r[z] = -(m[z + '_rt'].get(X, np.nan) - m[z + '_da'].get(X, np.nan))
        rows.append(r)
    h = pd.DataFrame(rows).dropna(subset=['WEST'])
    def st(v): return dict(days=int(len(v)), mean=round(v.mean(), 2), median=round(v.median(), 2), win=round((v > 0).mean() * 100), worst=round(v.min(), 1), best=round(v.max(), 1))
    on = h[h.on]; out = {'all_days': st(h.WEST), 'episode_on': {z: st(on[z]) for z in ('WEST', 'SOUTHWEST', 'NIAGARA')}}
    on = on.assign(wb=pd.cut(on.wind, [-1, 1000, 1800, 2500, 9000], labels=['<1000', '1000-1800', '1800-2500', '2500+']))
    out['episode_on_by_wind'] = {str(k): st(g.WEST) for k, g in on.groupby('wb', observed=True)}
    out['episode_on_since_2026_10_04'] = st(on[on.date >= '2026-10-04'].WEST)
    return out, h

def read(D, write=False):
    D = pd.Timestamp(D).strftime('%Y-%m-%d'); cut = min(bid_cut(D), now_est()); early = cut < bid_cut(D)
    Dm1 = (pd.Timestamp(D) - pd.Timedelta(days=1)).strftime('%Y-%m-%d'); Dm2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).strftime('%Y-%m-%d')
    R = dict(date=D, asof=str(cut), before_bid=bool(early))
    o, src = outages(D, cut); L, lca = limits(D, cut); dc = da_constraints(D)
    S = price_frame(); adq = C.adq2('preDA')
    # recent episode table: last 10 delivery days with DA known; RT only through D-2 (plus D-1 so far if any)
    S = S[S.date <= Dm1]
    rec = pd.DataFrame({'W_da': mid(S, 'WEST_da'), 'W_rt': mid(S, 'WEST_rt'), 'SW_da': mid(S, 'SOUTHWEST_da'), 'SW_rt': mid(S, 'SOUTHWEST_rt'),
                        'N_da': mid(S, 'NIAGARA_da'), 'N_rt': mid(S, 'NIAGARA_rt')})
    rec.loc[rec.index >= Dm1, ['W_rt', 'SW_rt', 'N_rt']] = np.nan                                   # D-1 RT not complete at the bid
    rec['W_unpriced'] = rec.W_rt - rec.W_da
    rec = rec.join(adq[adq.he.between(*MID)].groupby('date')[['wind_fc', 'dem_fc']].mean().round(0)).tail(10)
    wD = adq[(adq.date == D) & adq.he.between(*MID)][['wind_fc', 'dem_fc', 'solar_fc']].mean()
    stats, hist = regime_stats(S, adq, D)
    ep_on = (rec.W_da.get(Dm1, 0) <= -5) or (rec.W_rt.get(Dm2, 0) <= -5)
    # episode length so far (consecutive days with a midday West DA or RT split <= -5)
    k = 0
    for X in rec.index[::-1]:
        if min(rec.W_da.get(X, 0), (rec.W_rt.get(X, 0) if not np.isnan(rec.W_rt.get(X, np.nan)) else 0)) <= -5: k += 1
        else: break
    # ---------- print ----------
    P = print
    P(f'\n==================== CONGESTION READ  delivery {D}  (as of {cut:%b %d %H:%M} EST{"  -- BEFORE the bid: some D-1 files not out yet" if early else ""}) ====================')
    P(f'\n1. 500 kV EQUIPMENT OUT ON {D}   [{" | ".join(src) or "no outage files in archive"}]')
    if len(o):
        for _, r in o.iterrows():
            fd = lambda t: t.strftime('%b %d %H:%M' if t.year == pd.Timestamp(D).year else '%b %d %Y'); P(f"   {r.tag:14s} {fd(r.start)} -> {fd(r.end)}{' (long-term)' if r.long else ''}  {r.equip[:70]:70s} {r['where']}")
    else: P('   none listed')
    P(f'\n2. LIMITS IN FORCE ON {D} (south + interties)   [TxLimitsOutage0to2Days {lca:%b %d %H:%M}]' if lca is not None else '\n2. LIMITS: no file')
    if len(L):
        for _, r in L[L.south].iterrows():
            P(f"   {r.iface[:48]:48s} {r.limit:6.0f} MW{(f' vs {r.ais:.0f} ({r.pct:.0f}%)' if r.ais == r.ais and r.ais else ''):18s} {r.hours:9s} {r.why[:60]}")
        if not L.south.any(): P('   no southern interface or NY/MI intertie limits reduced')
    P(f'\n3. DA CONSTRAINTS ENFORCED YESTERDAY ({Dm1})')
    if dc is None: P('   DASecurityConstraints2 not archived yet (added to ieso_backfill.py; fills on the next morning refresh)')
    else:
        P(f"   FETT outage table enforced: {'YES -> ' + ', '.join(dc['fett_outage_table']) if dc['fett_outage_table'] else 'no (all-in-service table only)'}")
        for f, hs in dc['south'].items(): P(f'   {f:40s} HE {hs[0]}-{hs[-1]} ({len(hs)} h)')
    P(f'\n4. LAST 10 DAYS, HE{MID[0]}-{MID[1]} average, zone minus EAST ($/MWh). Unpriced = RT - DA (negative = RT split deeper than DA priced)')
    P(rec.round(1).to_string(na_rep='-'))
    P(f"\n   Forecast for {D} (pre-DA, HE{MID[0]}-{MID[1]}): wind {wD.wind_fc:,.0f} MW, demand {wD.dem_fc:,.0f} MW" if not wD.isna().all() else f'\n   Pre-DA forecast for {D} not out yet (IESO Adequacy ~06:50 MT on D-1)')
    P(f'\n5. REGIME: split episode {"ON" if ep_on else "OFF"} (yesterday DA West-East midday {rec.W_da.get(Dm1, np.nan):+.1f}, D-2 RT {rec.W_rt.get(Dm2, np.nan):+.1f}); episode day {k + 1 if ep_on else 0}')
    P('   History, sell zone / buy EAST HE10-17 the NEXT day when the episode was ON ($/MWh per hour, May 2025 ->):')
    for z, s in stats['episode_on'].items(): P(f"     {z:10s} days {s['days']:3d}  mean {s['mean']:+6.2f}  median {s['median']:+6.2f}  win {s['win']:3.0f}%  worst {s['worst']:+7.1f}  best {s['best']:+7.1f}")
    P('   WEST by pre-DA wind on D:')
    for w, s in stats['episode_on_by_wind'].items(): P(f"     wind {w:10s} days {s['days']:3d}  mean {s['mean']:+6.2f}  median {s['median']:+6.2f}  win {s['win']:3.0f}%")
    s = stats['episode_on_since_2026_10_04']; P(f"   Current outage regime only (since Oct 4): days {s['days']}  mean {s['mean']:+.2f}  median {s['median']:+.2f}  win {s['win']:.0f}%")
    P('\n   This is a read, not a signal: nothing here is wired into the ladders.')
    R.update(outages=[dict(r, start=str(r['start']), end=str(r['end'])) for r in o.to_dict('records')], out_src=src,
             limits=L.to_dict('records') if len(L) else [], limits_asof=str(lca), da_constraints=dc,
             recent=rec.reset_index().rename(columns={'index': 'date'}).round(2).replace({np.nan: None}).to_dict('records'),
             forecast=None if wD.isna().all() else wD.round(0).to_dict(), episode_on=bool(ep_on), episode_day=(k + 1 if ep_on else 0), stats=stats)
    if write:
        (OUT / f'read_{D}.json').write_text(json.dumps(R, default=str, indent=1)); P(f'\n   wrote data/congestion/read_{D}.json')
    return R

if __name__ == '__main__':
    D = next((a for a in sys.argv[1:] if re.match(r'\d{4}-\d{2}-\d{2}$', a)), (dt.date.today() + dt.timedelta(days=1)).isoformat())
    read(D, write='--json' in sys.argv)
