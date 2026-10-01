"""
parse_archive.py -- turn archive\\ (raw IESO/NYISO files) into tidy CSVs in data\\.

    python model\\parse_archive.py

Outputs (all hours are IESO hour-ending HE1-24, IESO clock = EST all year):
  data/prices_hourly.csv   date, he, zone, da, rt, rt_min5, rt_max5   (zones: ONTARIO + 9 hubs)
  data/adq3_preDA.csv      date, he, <fundamentals>, issued          (last Adequacy3 issued D-1 < 09:00 EST)
  data/adq3_final.csv      same, final version
  data/gas_ladder.csv      date, he, cc/peaker/lennox/hydro/nuclear output + capability
  data/nyiso_zoneA_da.csv  date, he, nyA_da (USD)                    (mapped to IESO HE)
Re-run any time; it rebuilds everything from the archive.
"""
import re, zipfile, io, sys
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARCH, DATA = ROOT / 'archive', ROOT / 'data'; DATA.mkdir(exist_ok=True)
NS = '{http://www.ieso.ca/schema}'


def files(report):
    for z in sorted((ARCH / report).glob('*.zip')):
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                yield n, zf.read(n)


def strip(el):                       # drop namespace from every tag
    for e in el.iter():
        if '}' in e.tag: e.tag = e.tag.split('}', 1)[1]
    return el


def xml(b): return strip(ET.fromstring(b))


def t(el, tag, cast=float):
    e = el.find(tag)
    if e is None or e.text in (None, ''): return None
    try: return cast(e.text)
    except ValueError: return None


# ---------------------------------------------------------------- prices
def prices():
    rows = []
    for n, b in files('DAHourlyOntarioZonalPrice'):
        if '_v' in n: continue
        r = xml(b); d = r.find('.//DeliveryDate').text
        for h in r.iter('HourlyPriceComponents'):
            rows.append((d, int(t(h, 'PricingHour')), 'ONTARIO', 'da', t(h, 'ZonalPrice')))
    for n, b in files('DAHourlyZonal'):
        if '_v' in n: continue
        r = xml(b); d = r.find('.//DeliveryDate').text
        for z in r.iter('TransactionZone'):
            zn = z.find('ZoneName').text.replace(':HUB', '')
            for c in z.iter('Components'):
                if c.find('PriceComponent').text != 'Zonal Price': continue
                for h in c.iter('DeliveryHour'):
                    rows.append((d, int(t(h, 'Hour')), zn, 'da', t(h, 'LMP')))
    da = pd.DataFrame(rows, columns=['date', 'he', 'zone', 'k', 'v'])
    rows = []
    for n, b in files('RealtimeOntarioZonalPrice'):
        if '_v' in n: continue
        r = xml(b); d = r.find('.//DeliveryDate').text; he = int(r.find('.//DeliveryHour').text)
        iv = [t(z, 'LmpCap') for z in r.iter('ZonalPrice')]; iv = [x for x in iv if x is not None]
        if len(iv) == 12: rows.append((d, he, 'ONTARIO', sum(iv) / 12, min(iv), max(iv)))
    for n, b in files('RealtimeZonalEnergyPrices'):
        if '_v' in n: continue
        r = xml(b); d = r.find('.//DELIVERYDATE').text; he = int(r.find('.//DELIVERYHOUR').text)
        for z in r.iter('TransactionZone'):
            iv = [t(i, 'ZonalPrice') for i in z.iter('IntervalPrice')]; iv = [x for x in iv if x is not None]
            if len(iv) == 12:
                rows.append((d, he, z.find('ZoneName').text.replace(':HUB', ''), sum(iv) / 12, min(iv), max(iv)))
    rt = pd.DataFrame(rows, columns=['date', 'he', 'zone', 'rt', 'rt_min5', 'rt_max5'])
    da = da.pivot_table(index=['date', 'he', 'zone'], columns='k', values='v').reset_index()
    out = da.merge(rt, on=['date', 'he', 'zone'], how='outer').sort_values(['date', 'zone', 'he'])
    out.to_csv(DATA / 'prices_hourly.csv', index=False)
    print(f'prices_hourly: {len(out):,} rows, {out.date.min()} -> {out.date.max()}, zones {sorted(out.zone.unique())}')


# ---------------------------------------------------------------- Adequacy3
def hv(parent, group):
    g = parent.find(group) if parent is not None else None
    out = [None] * 24
    if g is None: return out
    for c in g:
        h = t(c, 'DeliveryHour', int); vals = [x for x in c if x.tag != 'DeliveryHour']
        if h and vals and vals[0].text not in (None, ''): out[h - 1] = float(vals[0].text)
    return out


def adq_rows(b):
    r = xml(b); d = r.find('.//DeliveryDate').text; created = r.find('.//CreatedAt').text
    FS, FD = r.find('.//ForecastSupply'), r.find('.//ForecastDemand')
    cols = {}
    for ir in FS.iter('InternalResource'):
        f = ir.find('FuelType').text.lower()
        for k, g in (('cap', 'Capacities'), ('out', 'Outages'), ('fc', 'Forecasts'), ('sch', 'Schedules'), ('off', 'Offers')):
            v = hv(ir, g)
            if any(x is not None for x in v): cols[f'{f}_{k}'] = v
    ti, te = FS.find('.//TotalImports'), FD.find('.//TotalExports')
    cols['imp_cap'] = hv(ti, 'Capacities'); cols['imp_sch'] = hv(ti, 'Schedules'); cols['exp_sch'] = hv(te, 'Schedules')
    od = FD.find('.//OntarioDemand')
    lst = lambda e: [t(c, 'EnergyMW') for c in e] if e is not None else [None] * 24
    cols['dem_fc'] = lst(od.find('ForecastOntDemand')); cols['emb_wind'] = lst(od.find('WindEmbedded'))
    cols['emb_solar'] = lst(od.find('SolarEmbedded'))
    cols['exc_cap'] = hv(FD, 'ExcessCapacities'); cols['exc_off'] = hv(FD, 'ExcessOfferedCapacities')
    tr = FD.find('TotalRequirements'); cols['req'] = [t(c, 'EnergyMW') for c in tr] if tr is not None else [None] * 24
    rows = []
    for i in range(24):
        row = {'date': d, 'he': i + 1, 'issued': created}
        for k, v in cols.items(): row[k] = v[i] if i < len(v) else None
        rows.append(row)
    return rows


def adequacy():
    pre, fin = {}, {}
    for n, b in files('Adequacy3'):
        try: rows = adq_rows(b)
        except Exception as ex: print('  skip', n, ex); continue
        d = rows[0]['date']
        if '_v' in n:
            if d not in pre or rows[0]['issued'] > pre[d][0]['issued']: pre[d] = rows
        else: fin[d] = rows
    for name, dct in (('adq3_preDA', pre), ('adq3_final', fin)):
        df = pd.DataFrame([r for rows in dct.values() for r in rows]).sort_values(['date', 'he'])
        df.to_csv(DATA / f'{name}.csv', index=False)
        print(f'{name}: {len(df):,} rows, {df.date.min()} -> {df.date.max()}')


# ---------------------------------------------------------------- gas ladder
PEAK = {'YORKCGS-G1', 'YORKCGS-G2', 'HYDROGEN READY POWER PLANT (HRPP)'}
LENNOX = {'LENNOX-G1', 'LENNOX-G2', 'LENNOX-G3', 'LENNOX-G4'}

def ladder():
    rows = []
    for n, b in files('GenOutputCapability'):
        if '_v' in n: continue
        d = re.search(r'_(\d{8})', n).group(1); d = f'{d[:4]}-{d[4:6]}-{d[6:]}'
        r = xml(b); H = [dict(cc_out=0, cc_cap=0, pk_out=0, pk_cap=0, ln_out=0, ln_cap=0,
                              hy_out=0, hy_cap=0, nu_out=0, nu_cap=0) for _ in range(24)]
        for g in r.iter('Generator'):
            nm, fu = g.find('GeneratorName').text, g.find('FuelType').text
            cap = {t(c, 'Hour', int): t(c, 'EnergyMW') or 0 for c in g.iter('Capability')}
            for o in g.iter('Output'):
                h = t(o, 'Hour', int); v = t(o, 'EnergyMW') or 0
                if not h or h > 24: continue
                x = H[h - 1]; c = cap.get(h, 0) or 0
                if fu == 'GAS':
                    k = 'pk' if nm in PEAK else 'ln' if nm in LENNOX else 'cc'
                elif fu == 'HYDRO': k = 'hy'
                elif fu == 'NUCLEAR': k = 'nu'
                else: continue
                x[f'{k}_out'] += v; x[f'{k}_cap'] += c
        for i, x in enumerate(H): rows.append({'date': d, 'he': i + 1, **x})
    df = pd.DataFrame(rows).sort_values(['date', 'he']); df.to_csv(DATA / 'gas_ladder.csv', index=False)
    print(f'gas_ladder: {len(df):,} rows, {df.date.min()} -> {df.date.max()}')


# ---------------------------------------------------------------- NYISO
def _nyiso_rows(folder, fn):
    src = ARCH / folder
    for z in sorted(src.glob('*.zip')):
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist(): fn(zf.read(n).decode())
    for f in sorted(src.glob('*.csv')): fn(f.read_text())


def _to_ieso_key(ts_ept):
    """NYISO hour-beginning Eastern prevailing -> IESO (date, HE) in EST."""
    ts = pd.to_datetime(ts_ept).dt.tz_localize('America/New_York', ambiguous='NaT', nonexistent='NaT')
    est_he = ts.dt.tz_convert('Etc/GMT+5').dt.tz_localize(None) + pd.Timedelta(hours=1)
    x = est_he - pd.Timedelta(minutes=1)
    return x.dt.date.astype(str), x.dt.hour + 1


def nyiso():
    rows = []
    def lbmp(txt):
        for line in txt.splitlines()[1:]:
            p = line.replace('"', '').split(',')
            if len(p) > 3 and p[1] == 'WEST': rows.append((p[0], float(p[3])))
    _nyiso_rows('NYISO_damlbmp', lbmp)
    df = pd.DataFrame(rows, columns=['ts', 'nyA_da']).drop_duplicates('ts', keep='last')
    df['date'], df['he'] = _to_ieso_key(pd.to_datetime(df.ts, format='%m/%d/%Y %H:%M'))
    df = df.dropna(subset=['he']); df['he'] = df.he.astype(int)
    df[['date', 'he', 'nyA_da']].sort_values(['date', 'he']).to_csv(DATA / 'nyiso_zoneA_da.csv', index=False)
    print(f'nyiso_zoneA_da: {len(df):,} rows, {df.date.min()} -> {df.date.max()}')
    rows = []
    want = ['Net Imports DNI OH', 'Gross Imports OH', 'Gross Exports OH', 'Net Imports DNI HQ',
            'Net Imports DNI PJM', 'NYISO Load Forecast']
    def energy(txt):
        L = txt.splitlines();
        if not L: return
        hd = L[0].split(','); idx = [hd.index(w) if w in hd else None for w in want]
        for line in L[1:]:
            p = line.split(',')
            if len(p) < 10 or not re.match(r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}$', p[0]): continue
            rows.append([p[0]] + [float(p[i]) if i is not None and p[i] not in ('', None) else None for i in idx])
    _nyiso_rows('NYISO_damenergy', energy)
    df = pd.DataFrame(rows, columns=['ts', 'ny_dni_oh', 'ny_imp_oh', 'ny_exp_oh', 'ny_dni_hq', 'ny_dni_pjm', 'ny_load_fc'])
    df = df.drop_duplicates('ts', keep='last')
    df['date'], df['he'] = _to_ieso_key(pd.to_datetime(df.ts, format='%m/%d/%Y %H:%M'))
    df = df.dropna(subset=['he']); df['he'] = df.he.astype(int)
    df.drop(columns='ts').sort_values(['date', 'he']).to_csv(DATA / 'nyiso_dam_energy.csv', index=False)
    print(f'nyiso_dam_energy: {len(df):,} rows, {df.date.min()} -> {df.date.max()}')




# ---------------------------------------------------------------- intertie scheduling limits (pre-DA = known at the bid deadline)
def limits():
    rows = []
    for n, b in files('PreDAIntertieSchedLimits'):
        if '_v' in n: continue
        r = xml(b); d = r.find('.//DeliveryDate').text
        for z in r.iter('IntertieZonalEnergies'):
            zn = z.find('IntertieZoneName').text
            for h in z.iter('HourlyEnergy'):
                rows.append((d, int(h.find('DeliveryHour').text), zn, float(h.find('EnergyMW').text)))
    if not rows: print('preDA limits: no archived files yet'); return
    df = pd.DataFrame(rows, columns=['date', 'he', 'zone', 'mw']).drop_duplicates(['date', 'he', 'zone'], keep='last')
    old = DATA / 'ieso_preda_intertie_limits.csv'
    if old.exists(): df = pd.concat([pd.read_csv(old), df]).drop_duplicates(['date', 'he', 'zone'], keep='last')
    df.sort_values(['date', 'zone', 'he']).to_csv(old, index=False)
    print(f'preDA intertie limits: {len(df):,} rows, {df.date.min()} -> {df.date.max()}, {df.zone.nunique()} zones')


if __name__ == '__main__':
    for f in (prices, adequacy, ladder, nyiso, limits):
        try: f()
        except Exception as ex:
            import traceback; traceback.print_exc()
