"""tx_limits_test.py -- Oct 9 2026 (TEST ONLY): do transmission limits known at the bid (IESO TxLimitsOutage0to2Days,
versions created before D-1 09:00 EST) flag the days when southern Ontario (West/Southwest/Niagara) gets bottled and
East RT runs above DA? Feature: lowest Ontario->New York export limit in force on day D (normal ~1,750-2,000)."""
import sys, zipfile, glob; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import xml.etree.ElementTree as ET, pandas as pd, numpy as np, common as C
NS = '{http://www.ieso.ca/schema}'
def limits():
    rows = []
    for z in sorted(glob.glob(str(C.ROOT / 'archive/TxLimitsOutage0to2Days/*.zip'))):
        zf = zipfile.ZipFile(z)
        for n in zf.namelist():
            r = ET.fromstring(zf.read(n)); ca = r.find(f'.//{NS}CreatedAt').text
            for i in r.iter(NS + 'InterfaceData'):
                rows.append((ca, i.find(NS + 'InterfaceName').text.strip(), i.find(NS + 'StartDate').text, i.find(NS + 'EndDate').text, float(i.find(NS + 'OperatingLimit').text)))
    return pd.DataFrame(rows, columns=['created', 'iface', 'start', 'end', 'lim'])
L = limits(); L['created'] = pd.to_datetime(L.created); L['start'] = pd.to_datetime(L.start); L['end'] = pd.to_datetime(L.end)
days = pd.date_range('2026-06-28', '2026-10-08'); feat = []
for D in days:
    bid = D - pd.Timedelta(days=1) + pd.Timedelta(hours=9)
    v = L[L.created <= bid]; v = v[v.created >= bid - pd.Timedelta(days=1)]         # latest day of versions before the bid
    act = v[(v.start < D + pd.Timedelta(days=1)) & (v.end > D)]
    ny = act[act.iface.str.contains('New York Export')].lim.min(); mi = act[act.iface.str.contains('Michigan Export')].lim.min()
    fett = act[act.iface.str.contains('FETT')].lim.min()
    feat.append(dict(date=D.date().isoformat(), ny_exp=ny, mi_exp=mi, fett=fett, n_ver=v.created.nunique()))
F = pd.DataFrame(feat)
r = pd.read_csv(C.DATA / 'rt_components.csv'); w = r[r.zone.isin(['WEST', 'SOUTHWEST', 'NIAGARA'])].groupby(['date', 'he']).cong.min().reset_index()
p = pd.read_csv(C.DATA / 'prices_hourly.csv'); e = p[p.zone == 'EAST'][['date', 'he', 'da', 'rt']]; e['rd'] = e.rt - e.da
x = e.merge(w, on=['date', 'he'], how='inner').merge(F, on='date'); x['bottled'] = x.cong < -10
x['ny_cut'] = x.ny_exp <= 1400
print('days with versions', (F.n_ver > 0).sum(), 'of', len(F))
d = x.groupby('date').agg(ny=('ny_exp', 'first'), bott=('bottled', 'sum'), rd=('rd', 'mean'), cut=('ny_cut', 'first'))
print(d[(d.bott > 0) | d.cut].to_string())
for nm, k in (('NY export limit <= 1,400 at the bid', x.ny_cut), ('normal', ~x.ny_cut)):
    dd = x[k].groupby('date').bottled.max()
    print(f"{nm}: {x[k].date.nunique()} days | days with West bottled {int(dd.sum())} ({dd.mean()*100:.0f}%) | East RT-DA all hours {x[k].rd.mean():+.1f} | HE10-16 {x[k & x.he.between(10,16)].rd.mean():+.1f} | HE17-22 {x[k & x.he.between(17,22)].rd.mean():+.1f}")
