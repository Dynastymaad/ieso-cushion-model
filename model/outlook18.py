"""outlook18.py -- IESO Reliability Outlook (18-month) weekly tables, every edition we have (data/outlook/*.xlsx).
Reads 'Reductions by Fuel Type: Expected Weather, Firm Scenario' (Table A5 in older editions, Table 3.9 from 2026 Q3):
  week ending, Ontario demand, total internal resources, total reductions, nuclear reductions, biomass/oil/gas reductions,
  hydro/wind/solar/storage unavailable, bottled.   -> data/outlook/ro_weekly.csv  (one row per edition x week)
Also the external-intertie transmission outage list of the latest edition -> data/outlook/ro_intertie_outages.csv"""
import sys, glob, re; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import pandas as pd, openpyxl, common as C
OUT = C.DATA / 'outlook'

def edition(wb):
    m = wb[wb.sheetnames[0]]
    for r in m.iter_rows(max_row=5, values_only=True):
        for c in r:
            if hasattr(c, 'year'): return c.date().isoformat()

def find(wb, key):
    for w in wb.sheetnames:
        t = ' '.join(str(c) for r in wb[w].iter_rows(max_row=4, values_only=True) for c in r if c)
        if key in t: return wb[w]

def weekly():
    rows = []
    for f in sorted(glob.glob(str(OUT / '*.xlsx'))):
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True); ed = edition(wb)
        m = re.search(r'(20\d\d)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', f)
        if m and ed and ed[:4] != m.group(1): ed = m.group(1) + ed[4:]          # 2025 Q1 file is stamped 2024-03-25
        ws = find(wb, 'Reductions by Fuel Type: Expected Weather, Firm')
        if ws is None: print('no table in', f); continue
        for r in ws.iter_rows(min_row=5, values_only=True):
            if r and hasattr(r[0], 'year') and isinstance(r[1], (int, float)):
                v = [x for x in r[1:8]]
                rows.append(dict(edition=ed, file=f.split('/')[-1], week_end=r[0].date().isoformat(), demand=v[0], resources=v[1], reductions=v[2],
                                 nuc_red=v[3], gas_red=v[4], hyd_vg_unavail=v[5], bottled=v[6]))
    d = pd.DataFrame(rows); d.to_csv(OUT / 'ro_weekly.csv', index=False); return d

def intertie_outages():
    f = sorted(glob.glob(str(OUT / '*.xlsx')), key=lambda p: edition(openpyxl.load_workbook(p, read_only=True)))[-1]
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True); ws = find(wb, 'External Interties Transmission Outages')
    rows = []
    if ws is not None:
        for r in ws.iter_rows(min_row=5, values_only=True):
            if r and hasattr(r[0], 'year'):
                rows.append(dict(start=r[0], end=r[1], days=r[2], station=r[3], equipment=r[4], recall=r[6], interface=r[7], reduction=r[8]))
    d = pd.DataFrame(rows); d.to_csv(OUT / 'ro_intertie_outages.csv', index=False); return d

if __name__ == '__main__':
    d = weekly(); print(d.groupby('edition').agg(weeks=('week_end', 'size'), first=('week_end', 'min'), last=('week_end', 'max'), nuc=('nuc_red', 'mean'), gas=('gas_red', 'mean')).round(0))
    print(intertie_outages().head(12).to_string())
