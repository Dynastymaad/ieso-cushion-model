"""congestion/extract_v1.py -- Oct 13 2026: one JSON for the Congestion Monitor page (v1).
Sources (IESO public archive, already downloaded by ieso_backfill.py):
  RealtimeZonalEnergyPrices  -> hourly RT congestion component per zone (Jun ->)
  DAConstrShadowPrices        -> DA binding constraints, shadow $ per hour (Aug ->; IESO posts ~6 days late)
  TxOutages1to30DaysPlanned   -> planned transmission outages, next 30 days (latest file)
  TxOutagesTodayAll           -> outages in effect today (latest file)
  TxLimitsOutage0to2Days      -> interface / intertie limits changed by outages, days 0-2 (latest file)
Writes data/congestion/cong_v1.json. Read-only on the archive."""
import re, glob, json, zipfile, collections
from pathlib import Path
import numpy as np, pandas as pd
R = Path(__file__).resolve().parents[2]; A = R / 'archive'; OUT = R / 'data' / 'congestion' / 'cong_v1.json'
ZONES = ['NORTHWEST', 'NORTHEAST', 'OTTAWA', 'EAST', 'TORONTO', 'ESSA', 'BRUCE', 'SOUTHWEST', 'WEST', 'NIAGARA']

def rt_components():
    Z = re.compile(r'<ZoneName>([^<]+)</ZoneName>(.*?)</TransactionZone>', re.S)
    I = re.compile(r'<Interval>(\d+)</Interval>\s*<ZonalPrice>([-\d.]+)</ZonalPrice>\s*<EnergyLossPrice>([-\d.]+)</EnergyLossPrice>\s*<EnergyCongPrice>([-\d.]+)</EnergyCongPrice>')
    rows = []
    for f in sorted((A / 'RealtimeZonalEnergyPrices').glob('*.zip')):
        z = zipfile.ZipFile(f); best = {}
        for n in z.namelist():
            m = re.search(r'_(\d{10})(?:_v(\d+))?\.xml$', n)
            if m and (m.group(1) not in best or int(m.group(2) or 1e6) > best[m.group(1)][0]): best[m.group(1)] = (int(m.group(2) or 1e6), n)
        for k, (_, n) in best.items():
            s = z.read(n).decode('utf-8', 'ignore'); d = f'{k[:4]}-{k[4:6]}-{k[6:8]}'; he = int(k[8:])
            for name, body in Z.findall(s):
                v = np.array([[float(a), float(b), float(c)] for _, a, b, c in I.findall(body)])
                if len(v): rows.append((d, he, name.split(':')[0], v[:, 0].mean(), v[:, 2].mean(), v[:, 1].mean()))
    return pd.DataFrame(rows, columns=['date', 'he', 'zone', 'rt', 'cong', 'loss'])

def da_constraints():
    rows = []
    for f in sorted((A / 'DAConstrShadowPrices').glob('*.zip')):
        z = zipfile.ZipFile(f)
        for n in z.namelist():
            if '_v' in n: continue
            s = z.read(n).decode('utf-8', 'ignore'); d = re.search(r'<DELIVERYDATE>(.*?)<', s).group(1)
            for c, body in re.findall(r'<ConstraintName>(.*?)</ConstraintName>\s*<ShadowPrices>(.*?)</ShadowPrices>', s, re.S):
                hv = re.findall(r'<Hour>(\d+)</Hour>\s*<ShadowPrice>([-\d.]+)<', body)
                for h, v in hv:
                    if float(v) != 0: rows.append((d, int(h), ' '.join(c.split()), float(v)))
    return pd.DataFrame(rows, columns=['date', 'he', 'constraint', 'sp'])

def short(c):
    """'BASE CASE 0 S-FETT.TAB6_N582L_24K.EQ4_DSO' -> ('BASE CASE', 'S-FETT', 'S-FETT.TAB6_N582L_24K.EQ4_DSO')"""
    m = re.match(r'(BASE CASE)\s+\d+\s+(.*)', c)
    if m: body = m.group(2); case = 'Base case'
    else: parts = c.split(); body = parts[-1]; case = 'Contingency: ' + ' '.join(parts[:-2])[:40]
    key = re.split(r'[._]', body)[0]
    return case, key, body

def latest(report):
    fs = sorted((A / report).glob('*.zip'))
    if not fs: return None, None
    z = zipfile.ZipFile(fs[-1]); n = sorted(z.namelist(), key=lambda x: (re.search(r'_(\d{8})', x).group(1), int((re.search(r'_v(\d+)', x) or [0, 0])[1]) if re.search(r'_v(\d+)', x) else 999))[-1]
    return n, z.read(n).decode('utf-8', 'ignore')

def outages(report, kv_min=230):
    n, s = latest(report); out = []
    if not s: return n, out
    for b in re.findall(r'<OutageRequest>(.*?)</OutageRequest>', s, re.S):
        g = lambda t: (re.search(f'<{t}>(.*?)</{t}>', b, re.S) or [None, ''])[1].strip()
        eq = re.findall(r'<EquipmentName>(.*?)</EquipmentName>\s*<EquipmentType>(.*?)</EquipmentType>\s*<EquipmentVoltage>(.*?)</EquipmentVoltage>\s*<ConstraintType>(.*?)</ConstraintType>', b)
        hv = [e for e in eq if (re.match(r'(\d+)', e[2]) and int(re.match(r'(\d+)', e[2]).group(1)) >= kv_min) and e[3] != 'INFO']
        if not hv: continue
        out.append(dict(id=g('OutageID'), start=g('PlannedStart')[:16], end=g('PlannedEnd')[:16], pri=g('Priority'), status=g('OutageRequestStatus'),
                         recall=g('EquipmentRecallTime'), eq=[[e[0], e[1], e[2], e[3]] for e in hv]))
    return n, out

def limits():
    n, s = latest('TxLimitsOutage0to2Days'); out = []
    if not s: return n, out
    for sec in re.findall(r'<TransmissionFacilityData>(.*?)</TransmissionFacilityData>', s, re.S):
        fac = (re.search(r'<TransmissionFacility>(.*?)<', sec) or [None, ''])[1]
        for b in re.findall(r'<InterfaceData>(.*?)</InterfaceData>', sec, re.S):
            g = lambda t: (re.search(f'<{t}>(.*?)</{t}>', b, re.S) or [None, ''])[1].strip()
            out.append(dict(fac=fac, name=g('InterfaceName'), start=g('StartDate')[:16], end=g('EndDate')[:16], limit=g('OperatingLimit'), why=g('Comments')))
    return n, out

if __name__ == '__main__':
    rt = rt_components(); print('rt', rt.date.min(), rt.date.max(), len(rt))
    da = da_constraints(); print('da', da.date.min() if len(da) else None, da.date.max() if len(da) else None, len(da))
    # daily zone congestion + last-14-day hour profile + latest days hourly
    dz = rt.groupby(['date', 'zone']).agg(cong=('cong', 'mean'), cmin=('cong', 'min'), rt=('rt', 'mean')).reset_index()
    last = sorted(rt.date.unique())[-14:]
    prof = rt[rt.date.isin(last)].groupby(['zone', 'he']).cong.mean().round(2).unstack().to_dict('index')
    hourly = rt[rt.date.isin(last)].pivot_table(index=['date', 'he'], columns='zone', values='cong').round(1).reset_index()
    # DA constraints summary
    da[['case', 'key', 'body']] = da.constraint.apply(lambda c: pd.Series(short(c)))
    cs = da.groupby('constraint').agg(case=('case', 'first'), key=('key', 'first'), body=('body', 'first'), days=('date', 'nunique'), hrs=('he', 'size'),
                                       tot=('sp', lambda s: s.abs().sum()), mx=('sp', lambda s: s.abs().max()), first=('date', 'min'), last=('date', 'max')).reset_index()
    cday = da.groupby(['constraint', 'date']).agg(hrs=('he', 'size'), tot=('sp', lambda s: s.abs().sum())).reset_index()
    # which zones does each constraint move? corr of daily constraint $ with daily zone RT congestion (DA dates overlap)
    zd = dz.pivot_table(index='date', columns='zone', values='cong')
    eff = {}
    for c, g in cday.groupby('constraint'):
        s = g.set_index('date').tot.reindex(zd.index).fillna(0)
        if (s > 0).sum() < 2: continue
        rng = zd.index[(zd.index >= da.date.min()) & (zd.index <= da.date.max())]
        r = {z: round(float(np.corrcoef(s.loc[rng], zd.loc[rng, z])[0, 1]), 2) for z in zd.columns if zd.loc[rng, z].std() > 0}
        eff[c] = r
    no, od = outages('TxOutages1to30DaysPlanned'); nt, ot = outages('TxOutagesTodayAll'); nl, li = limits()
    J = dict(built=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'), zones=ZONES,
             rt_range=[rt.date.min(), rt.date.max()], da_range=[da.date.min(), da.date.max()] if len(da) else None,
             zone_daily=dz.round(2).to_dict('records'), zone_profile14=prof, zone_hourly14=hourly.to_dict('records'),
             constraints=cs.sort_values('tot', ascending=False).round(1).to_dict('records'), constraint_daily=cday.round(1).to_dict('records'), constraint_zone_corr=eff,
             outages_planned=dict(file=no, rows=od), outages_today=dict(file=nt, rows=ot), limits=dict(file=nl, rows=li))
    OUT.write_text(json.dumps(J, default=str, separators=(',', ':')))
    print('wrote', OUT, round(OUT.stat().st_size / 1e6, 2), 'MB | constraints', len(cs), '| planned outages >=230kV', len(od), '| today', len(ot), '| limits', len(li))
