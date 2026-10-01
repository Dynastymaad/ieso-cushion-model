"""checklist_xlsx.py -- the pre-model checklist as an Excel workbook: raw daily values and their deviations.
Rows: the last 30 delivery days (what was known at each day's bid + what actually happened), tomorrow (the bid file),
and the 13 days after tomorrow (IESO 35-day schedule + Open-Meteo 16-day weather).
Sheets: README | Summary (tomorrow vs last 14 / last 30 days, next 14 days vs last 30) | Next_14_Days | Last_30_Days | Data.
Every average and difference in the workbook is an Excel formula on the Data sheet. Output: site/Checklist_Deviations.xlsx
    python model/checklist_xlsx.py            (morning.py runs it after the model)"""
import sys, json, urllib.request, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.comments import Comment

OM_URL = ('https://api.open-meteo.com/v1/forecast?latitude=43.65,45.42,44.00,42.40&longitude=-79.38,-75.70,-81.60,-82.20'
          '&hourly=temperature_2m,cloud_cover,shortwave_radiation,pressure_msl,wind_speed_100m&timezone=America%2FToronto&past_days=31&forecast_days=16')
OM_CACHE = C.DATA / 'wx' / 'openmeteo_view.json'
PK = (8, 21)                                                     # peak hours HE8-21 (IESO clock)

# (key, label, unit, group, periods it exists for: H history / T tomorrow / F forward, note)
M = [('dem_peak', 'Ontario demand forecast, daily peak', 'MW', 'Load', 'HTF', 'IESO Adequacy at the bid (history, tomorrow); IESO 35-day schedule (forward)'),
     ('dem_onpk', 'Ontario demand forecast, HE8-21 avg', 'MW', 'Load', 'HTF', ''),
     ('dem_act', 'Ontario demand actual, daily peak', 'MW', 'Load', 'H', 'IESO actual (Warehouse)'),
     ('load_miss', 'Demand miss: actual peak - bid-time forecast peak', 'MW', 'Load', 'H', '+ = load came in above what DA priced'),
     ('gas_out', 'Gas outages, HE8-21 avg', 'MW', 'Outages', 'HTF', 'known at the bid = priced into DA'),
     ('nuc_out', 'Nuclear outages, HE8-21 avg', 'MW', 'Outages', 'HTF', ''),
     ('hyd_out', 'Hydro outages, HE8-21 avg', 'MW', 'Outages', 'HTF', ''),
     ('tot_out', 'Total outages (gas+nuclear+hydro), HE8-21 avg', 'MW', 'Outages', 'HTF', ''),
     ('add_after', 'Outage MW added after the bid, HE8-21 avg', 'MW', 'Outages', 'H', 'NOT in DA -- the part that hurts sells'),
     ('trips', 'Trips: outage MW added to the previous day after its bid (max hour)', 'MW', 'Outages', 'HT', '>= 500 = tight sells x1.5; negative = units came back early'),
     ('wind_onpk', 'Wind forecast, HE8-21 avg', 'MW', 'Renewables', 'HTF', 'forward: only the first days carry a wind forecast'),
     ('solar_max', 'Grid solar forecast, daily max', 'MW', 'Renewables', 'HTF', ''),
     ('head_min', 'Headroom (spare flexible supply), tightest HE8-21', 'MW', 'Supply', 'HTF', '< 7,000 = sell zone'),
     ('head_onpk', 'Headroom, HE8-21 avg', 'MW', 'Supply', 'HTF', ''),
     ('pqat_lim', 'PQ.AT (Quebec) DA export limit, daily avg', 'MW', 'Interties', 'HT', 'IESO pre-DA limits'),
     ('pq_exp', 'Exports to Quebec, actual daily avg', 'MW', 'Interties', 'H', ''),
     ('nyA_da', 'NYISO Zone A DA price, HE8-21 avg', 'USD/MWh', 'Neighbours', 'HT', 'NYISO DAM (tomorrow once out, ~07:35 MT)'),
     ('east_da', 'East DA price, HE8-21 avg', '$/MWh', 'Prices', 'H', ''),
     ('east_rt', 'East RT price, HE8-21 avg', '$/MWh', 'Prices', 'H', ''),
     ('east_sp', 'East DA - RT, HE8-21 avg', '$/MWh', 'Prices', 'H', '+ = sells won'),
     ('ott_da', 'Ottawa DA price, HE8-21 avg', '$/MWh', 'Prices', 'H', ''),
     ('ott_rt', 'Ottawa RT price, HE8-21 avg', '$/MWh', 'Prices', 'H', ''),
     ('ott_sp', 'Ottawa DA - RT, HE8-21 avg', '$/MWh', 'Prices', 'H', ''),
     ('ozp_da', 'Ontario zonal DA price, HE8-21 avg', '$/MWh', 'Prices', 'H', ''),
     ('tor_tmax', 'Toronto max temperature', 'deg C', 'Weather', 'HTF', 'Open-Meteo (history = analysis, forward = forecast)'),
     ('ott_tmax', 'Ottawa max temperature', 'deg C', 'Weather', 'HTF', ''),
     ('tor_cloud', 'Toronto cloud cover, 11:00-16:00 avg', '%', 'Weather', 'HTF', 'cloudy = less embedded solar = more midday load'),
     ('tor_solar', 'Toronto solar radiation, 11:00-16:00 avg', 'W/m2', 'Weather', 'HTF', ''),
     ('tor_press', 'Toronto sea-level pressure, daily avg', 'hPa', 'Weather', 'HTF', 'high (above ~1020) = calm, clear'),
     ('wind_huron', 'Wind at 100 m, Lake Huron shore, 08:00-21:00 avg', 'km/h', 'Weather', 'HTF', 'Goderich / Bruce wind farms'),
     ('wind_erie', 'Wind at 100 m, Lake Erie shore, 08:00-21:00 avg', 'km/h', 'Weather', 'HTF', 'Chatham-Kent wind farms'),
     ('sell_line', 'Sell line: headroom below this = v2 tight sell zone', 'MW', 'Reference', 'HTF', 'model constant (tested threshold, re-learned daily; 7,000 on recent days)')]


def openmeteo():
    try:
        with urllib.request.urlopen(OM_URL, timeout=30) as r: txt = r.read().decode()
        OM_CACHE.parent.mkdir(parents=True, exist_ok=True); OM_CACHE.write_text(txt, encoding='utf-8'); src = 'live'
    except Exception as ex:
        if not OM_CACHE.exists(): print('Open-Meteo not reachable and no cache:', ex); return pd.DataFrame(), 'none'
        txt = OM_CACHE.read_text(encoding='utf-8'); src = 'cached ' + pd.Timestamp(OM_CACHE.stat().st_mtime, unit='s').strftime('%Y-%m-%d %H:%M UTC')
    J = json.loads(txt); out = []
    for n, j in zip(['tor', 'ott', 'huron', 'erie'], J):
        h = pd.DataFrame(j['hourly']); h['t'] = pd.to_datetime(h.time); h['date'] = h.t.dt.date.astype(str); h['hr'] = h.t.dt.hour
        g = h.groupby('date')
        if n in ('tor', 'ott'): out.append(g.temperature_2m.max().rename(f'{n}_tmax'))
        if n == 'tor':
            mid = h[h.hr.between(11, 15)].groupby('date')
            out += [mid.cloud_cover.mean().rename('tor_cloud'), mid.shortwave_radiation.mean().rename('tor_solar'), g.pressure_msl.mean().rename('tor_press')]
        if n in ('huron', 'erie'): out.append(h[h.hr.between(8, 20)].groupby('date').wind_speed_100m.mean().rename(f'wind_{n}'))
    return pd.concat(out, axis=1), src


def build(D=None):
    b = json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text(encoding='utf-8')); D = D or b['target']
    days = [(pd.Timestamp(D) + pd.Timedelta(days=k)).date().isoformat() for k in range(-30, 14)]
    X = pd.DataFrame(index=days); X['period'] = ['History' if d < D else 'Tomorrow' if d == D else 'Forward' for d in days]
    # bid-time fundamentals (history + tomorrow): IESO pre-DA Adequacy
    a = C.adq2('preDA'); pk = a[a.he.between(*PK)]
    f = pd.DataFrame({'dem_peak': a.groupby('date').dem_fc.max(), 'dem_onpk': pk.groupby('date').dem_fc.mean(),
                      'gas_out': pk.groupby('date').gas_out.mean(), 'nuc_out': pk.groupby('date').nuc_out.mean(), 'hyd_out': pk.groupby('date').hyd_out.mean(),
                      'wind_onpk': pk.groupby('date').wind_fc.mean(), 'solar_max': a.groupby('date').solar_fc.max(),
                      'head_min': pk.groupby('date')['head'].min(), 'head_onpk': pk.groupby('date')['head'].mean()})
    f['tot_out'] = f.gas_out + f.nuc_out + f.hyd_out
    X = X.join(f[f.index <= D])
    # forward schedule: IESO 35-day Adequacy3 (latest snapshot)
    F = pd.read_csv(C.DATA / 'fwd35.csv'); F = F[F.snapshot == F.snapshot.max()]
    F['date'] = pd.to_datetime(F.date.astype(str)).dt.date.astype(str)
    F['head'] = (F.gas_cap - F.gas_out + F.hydro_cap - F.hydro_out) - (F.dem_fc - (F.nuclear_cap - F.nuclear_out) - F.wind_fc.fillna(0) - F.solar_fc.fillna(0))
    Fp = F[F.he.between(*PK)]; gF, gP = F.groupby('date'), Fp.groupby('date')
    ff = pd.DataFrame({'dem_peak': gF.dem_fc.max(), 'dem_onpk': gP.dem_fc.mean(), 'gas_out': gP.gas_out.mean(),
                       'nuc_out': gP.nuclear_out.mean(), 'hyd_out': gP.hydro_out.mean(),
                       'wind_onpk': gP.wind_fc.mean().where(gP.wind_fc.std() > 1), 'solar_max': gF.solar_fc.max().where(gF.solar_fc.std() > 1),
                       'head_min': gP['head'].min(), 'head_onpk': gP['head'].mean()})
    ff['tot_out'] = ff.gas_out + ff.nuc_out + ff.hyd_out
    fw = [d for d in days if d > D]
    for c in ff.columns: X.loc[fw, c] = ff[c].reindex(fw).values
    # what actually happened (history)
    la = pd.read_csv(C.CACHE / 'ieso_load_actual.csv'); la['date'] = la.EffectiveDateTime.str[:10]; X['dem_act'] = la.groupby('date').Load.max()
    X['load_miss'] = X.dem_act - X.dem_peak
    o = pd.read_csv(C.DATA / 'outage_features.csv'); op = o[o.he.between(*PK)]
    X['add_after'] = op.groupby('date').add_after.mean(); X['trips'] = o.groupby('date').trips_d1.max()
    p = C.prices(); pp = p[p.he.between(*PK)]
    for z, k in (('EAST', 'east'), ('OTTAWA', 'ott'), ('ONTARIO', 'ozp')):
        g = pp[pp.zone == z].groupby('date'); X[f'{k}_da'] = g.da.mean()
        if k != 'ozp':
            X[f'{k}_rt'] = g.rt.mean().where(g.rt.count() >= 12); X[f'{k}_sp'] = X[f'{k}_da'] - X[f'{k}_rt']
    ny = pd.read_csv(C.DATA / 'nyiso_zoneA_da.csv'); X['nyA_da'] = ny[ny.he.between(*PK)].groupby('date').nyA_da.mean()
    q = pd.read_csv(C.DATA / 'qc_flows.csv'); X['pq_exp'] = q.groupby('date').pq_exp.mean()
    lim = []
    fn = C.DATA / 'nrg' / 'da_intertie_limits_pq.csv'
    if fn.exists(): x = pd.read_csv(fn); lim.append((-x.LIM_PQAT_EXP).groupby(x.date).mean())
    li = pd.read_csv(C.DATA / 'ieso_preda_intertie_limits.csv'); li = li[li.zone == 'PQATN']; lim.append(li.mw.abs().groupby(li.date).mean())
    L_ = pd.concat(lim); X['pqat_lim'] = L_[~L_.index.duplicated(keep='last')]
    W, wsrc = openmeteo()
    if len(W):
        for c in W.columns: X[c] = W[c].reindex(X.index)
    X['sell_line'] = 7000.0
    for m in M:                                      # blank what a period cannot know (e.g. tomorrow's DA price)
        k, av = m[0], m[4]
        if k not in X: X[k] = np.nan
        for per, tag in (('History', 'H'), ('Tomorrow', 'T'), ('Forward', 'F')):
            if tag not in av: X.loc[X.period == per, k] = np.nan
    return X, D, wsrc


# ------------------------------------------------------------------ workbook
FONT = 'Arial'
BLUE = Font(name=FONT, color='0000FF', size=10); BLK = Font(name=FONT, size=10); BOLD = Font(name=FONT, size=10, bold=True)
GREEN = Font(name=FONT, size=10, color='008000')
HDR = Font(name=FONT, size=10, bold=True, color='FFFFFF'); HFILL = PatternFill('solid', fgColor='1F3A4D'); GFILL = PatternFill('solid', fgColor='E6EBE9')
TFILL = PatternFill('solid', fgColor='FFF2CC'); THIN = Border(bottom=Side(style='thin', color='C9D1CE'))
RED, GRN = PatternFill('solid', fgColor='F6DDD7'), PatternFill('solid', fgColor='D8EEDF')


def fmt(u):
    if u in ('deg C', 'km/h', 'hPa', '%'): return '0.0;-0.0;0.0'
    if '$' in u or 'USD' in u: return '0.00;-0.00;0.00'
    return '#,##0;-#,##0;0'


def write(X, D, wsrc, path):
    wb = Workbook(); wb.calculation.fullCalcOnLoad = True
    keys = [m[0] for m in M]; meta = {m[0]: m for m in M}
    # ---- Data (raw inputs)
    ws = wb.active; ws.title = 'Data'; last = len(X) + 1
    ws.append(['Date', 'Period'] + [f'{meta[k][1]} ({meta[k][2]})' for k in keys])
    for d, r in X.iterrows():
        ws.append([pd.Timestamp(d).to_pydatetime(), r.period] + [None if pd.isna(r[k]) else float(round(float(r[k]), 2)) for k in keys])
    for c in ws[1]: c.font = HDR; c.fill = HFILL; c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.row_dimensions[1].height = 62
    for row in ws.iter_rows(min_row=2):
        row[0].number_format = 'yyyy-mm-dd ddd'; row[0].font = BLK; row[1].font = BLK
        for i, c in enumerate(row[2:]): c.font = BLUE; c.number_format = fmt(meta[keys[i]][2])
        if row[1].value == 'Tomorrow':
            for c in row: c.fill = TFILL
    ws.column_dimensions['A'].width = 15; ws.column_dimensions['B'].width = 10
    for i in range(len(keys)): ws.column_dimensions[L(i + 3)].width = 14
    ws.freeze_panes = 'C2'
    col = {k: L(i + 3) for i, k in enumerate(keys)}
    rng = lambda k: f'Data!${col[k]}$2:${col[k]}${last}'
    DR = f'Data!$A$2:$A${last}'
    # ---- Summary
    s = wb.create_sheet('Summary')
    s['A1'] = 'Pre-model checklist: tomorrow vs the last 14 and 30 days'; s['A1'].font = Font(name=FONT, size=14, bold=True)
    s['A2'] = 'Tomorrow (delivery day)'; s['A2'].font = BOLD
    s['D2'] = pd.Timestamp(D).to_pydatetime(); s['D2'].number_format = 'yyyy-mm-dd ddd'; s['D2'].font = BLUE; s['D2'].fill = TFILL
    s['D2'].comment = Comment('The delivery day this workbook was built for (the day you are bidding). Rebuilt each morning by morning.py.', 'model')
    s['F2'] = 'Weather:'; s['F2'].font = BOLD; s['G2'] = f'Open-Meteo, {wsrc}'; s['G2'].font = BLK
    import os
    win = str(C.ROOT) if os.name == 'nt' else r'C:\Users\mabbasi\OneDrive - Dynasty Power\Desktop\Ontario-Cushion Model'   # absolute: OneDrive opens the workbook from a web URL, so relative links 404
    fl = lambda f: 'file:///' + (win + '\\' + f).replace('\\', '/').replace(' ', '%20')
    for cell, txt, tgt in (('L1', 'REFRESH: pull all data + rebuild', fl('Refresh_Checklist.bat')), ('O1', 'Rebuild only (no pulls)', fl('Refresh_Model_Only.bat'))):
        c = s[cell]; c.value = txt; c.hyperlink = tgt; c.font = Font(name=FONT, size=11, bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='2F7A4B' if cell == 'L1' else '1D5E86'); c.alignment = Alignment(horizontal='center', vertical='center')
        s.merge_cells(f'{cell}:{chr(ord(cell[0]) + 2)}1')
    s['L2'] = 'Close this workbook first; the refresh opens the new one when it finishes (runs Refresh_Checklist.bat in the model folder).'
    s['L2'].font = Font(name=FONT, size=8, italic=True, color='4E5C57'); s.row_dimensions[1].height = 26
    s['A3'] = ('Last-14 / last-30 = the 14 / 30 delivery days before tomorrow. Next-14 = tomorrow + the 13 days after it. '
               'z = (tomorrow - last-30 mean) / last-30 SD; HIGH / LOW = at least one SD away.')
    s['A3'].font = Font(name=FONT, size=9, italic=True, color='4E5C57')
    H = ['Group', 'Item', 'Unit', 'Tomorrow', 'Last-14 mean', 'Tomorrow - last-14', 'Last-30 mean', 'Tomorrow - last-30', 'Last-30 SD', 'z vs last-30', 'Flag',
         'Last-30 min', 'Last-30 max', 'Next-14 mean', 'Next-14 - last-30', 'Note']
    hr = 5
    for j, h in enumerate(H, start=1):
        c = s.cell(row=hr, column=j, value=h); c.font = HDR; c.fill = HFILL; c.alignment = Alignment(wrap_text=True, vertical='center')
    s.row_dimensions[hr].height = 32
    T, d14, d30, e14 = '$D$2', '$D$2-14', '$D$2-30', '$D$2+13'
    srow = {}
    for i, k in enumerate(keys):
        r = hr + 1 + i; srow[k] = r; lab, u, grp, note = meta[k][1], meta[k][2], meta[k][3], meta[k][5]; R = rng(k)
        cells = [grp, lab, u,
                 f'=IFERROR(IF(INDEX({R},MATCH({T},{DR},0))="","",INDEX({R},MATCH({T},{DR},0))),"")',
                 f'=IFERROR(AVERAGEIFS({R},{DR},">="&{d14},{DR},"<"&{T}),"")',
                 f'=IF(AND(ISNUMBER(D{r}),ISNUMBER(E{r})),D{r}-E{r},"")',
                 f'=IFERROR(AVERAGEIFS({R},{DR},">="&{d30},{DR},"<"&{T}),"")',
                 f'=IF(AND(ISNUMBER(D{r}),ISNUMBER(G{r})),D{r}-G{r},"")',
                 f'=IFERROR(SQRT(SUMPRODUCT(({DR}>={d30})*({DR}<{T})*ISNUMBER({R}),({R}-G{r})^2)/(COUNTIFS({DR},">="&{d30},{DR},"<"&{T},{R},"<>")-1)),"")',
                 f'=IF(AND(ISNUMBER(H{r}),ISNUMBER(I{r})),IF(I{r}>0,H{r}/I{r},""),"")',
                 f'=IF(ISNUMBER(J{r}),IF(J{r}>=1,"HIGH",IF(J{r}<=-1,"LOW","")),"")',
                 f'=IFERROR(_xlfn.MINIFS({R},{DR},">="&{d30},{DR},"<"&{T}),"")',
                 f'=IFERROR(_xlfn.MAXIFS({R},{DR},">="&{d30},{DR},"<"&{T}),"")',
                 f'=IFERROR(AVERAGEIFS({R},{DR},">="&{T},{DR},"<="&{e14}),"")',
                 f'=IF(AND(ISNUMBER(N{r}),ISNUMBER(G{r})),N{r}-G{r},"")', note]
        for j, v in enumerate(cells):
            c = s.cell(row=r, column=j + 1, value=v); c.font = BLK; c.border = THIN
            if j in (3, 4, 5, 6, 7, 8, 11, 12, 13, 14): c.number_format = fmt(u)
        s.cell(row=r, column=10).number_format = '0.0;-0.0;0.0'
        if i == 0 or meta[keys[i - 1]][3] != grp:
            for j in range(1, 17): s.cell(row=r, column=j).border = Border(top=Side(style='thin', color='1F3A4D'), bottom=Side(style='thin', color='C9D1CE'))
    lr = hr + len(keys)
    s.conditional_formatting.add(f'K{hr+1}:K{lr}', CellIsRule(operator='equal', formula=['"HIGH"'], fill=RED))
    s.conditional_formatting.add(f'K{hr+1}:K{lr}', CellIsRule(operator='equal', formula=['"LOW"'], fill=GRN))
    for c, w in zip('ABCDEFGHIJKLMNOP', (11, 46, 9, 11, 11, 12, 11, 12, 10, 9, 7, 11, 11, 11, 12, 52)): s.column_dimensions[c].width = w
    s.freeze_panes = 'D6'

    # ---- Next_14_Days / Last_30_Days
    def grid(name, dates, fwd):
        g = wb.create_sheet(name)
        ks = [k for k in keys if ('F' in meta[k][4] or 'T' in meta[k][4])] if fwd else [k for k in keys if 'H' in meta[k][4]]
        g['A1'] = ('Next 14 days (tomorrow + 13): raw value, then the difference vs the last-14 and last-30 day means' if fwd else
                   'Last 30 delivery days (newest first): raw value, then the difference vs the last-14 and last-30 day means')
        g['A1'].font = Font(name=FONT, size=12, bold=True)
        g['A2'] = 'Red / green = the difference is more than one last-30 SD above / below.'; g['A2'].font = Font(name=FONT, size=9, italic=True, color='4E5C57')
        c = g.cell(row=4, column=1, value='Date'); c.font = HDR; c.fill = HFILL
        for i, k in enumerate(ks):
            c0 = 2 + 3 * i; g.merge_cells(start_row=3, start_column=c0, end_row=3, end_column=c0 + 2)
            h = g.cell(row=3, column=c0, value=f'{meta[k][1]} ({meta[k][2]})'); h.font = HDR; h.fill = HFILL
            h.alignment = Alignment(wrap_text=True, horizontal='center', vertical='center')
            for j, t in enumerate(['Value', 'vs last-14', 'vs last-30']):
                c = g.cell(row=4, column=c0 + j, value=t); c.font = BOLD; c.fill = GFILL; c.alignment = Alignment(horizontal='center')
                g.column_dimensions[L(c0 + j)].width = 10.5
        g.row_dimensions[3].height = 60; g.column_dimensions['A'].width = 15
        r0 = 5
        for r_, d in enumerate(dates, start=r0):
            a_ = g.cell(row=r_, column=1, value=pd.Timestamp(d).to_pydatetime()); a_.number_format = 'yyyy-mm-dd ddd'; a_.font = BLK
            if d == D: a_.fill = TFILL
            for i, k in enumerate(ks):
                c0 = 2 + 3 * i; R = rng(k); sr = srow[k]; vL = L(c0)
                v = g.cell(row=r_, column=c0, value=f'=IFERROR(IF(INDEX({R},MATCH($A{r_},{DR},0))="","",INDEX({R},MATCH($A{r_},{DR},0))),"")')
                x14 = g.cell(row=r_, column=c0 + 1, value=f'=IF(AND(ISNUMBER({vL}{r_}),ISNUMBER(Summary!$E${sr})),{vL}{r_}-Summary!$E${sr},"")')
                x30 = g.cell(row=r_, column=c0 + 2, value=f'=IF(AND(ISNUMBER({vL}{r_}),ISNUMBER(Summary!$G${sr})),{vL}{r_}-Summary!$G${sr},"")')
                for c in (v, x14, x30): c.number_format = fmt(meta[k][2])
                v.font = GREEN; x14.font = BLK; x30.font = BLK
        lr_ = r0 + len(dates) - 1
        for i, k in enumerate(ks):
            for j in (1, 2):
                cl = L(2 + 3 * i + j); sd = f'Summary!$I${srow[k]}'
                g.conditional_formatting.add(f'{cl}{r0}:{cl}{lr_}', FormulaRule(formula=[f'AND(ISNUMBER({cl}{r0}),ISNUMBER({sd}),{cl}{r0}>={sd})'], fill=RED))
                g.conditional_formatting.add(f'{cl}{r0}:{cl}{lr_}', FormulaRule(formula=[f'AND(ISNUMBER({cl}{r0}),ISNUMBER({sd}),{cl}{r0}<=-{sd})'], fill=GRN))
        g.freeze_panes = f'B{r0}'
    grid('Next_14_Days', [d for d in X.index if d >= D], True)
    grid('Last_30_Days', [d for d in X.index if d < D][::-1], False)


    # ---- Charts (native Excel charts on the Data sheet; history = rows before tomorrow, forward = after)
    from openpyxl.chart import LineChart, BarChart, ScatterChart, Reference, Series
    from openpyxl.chart.marker import Marker
    from openpyxl.chart.shapes import GraphicalProperties
    from openpyxl.drawing.line import LineProperties
    PAL = ['2A78D6', 'EB6834', '1BAF7A', 'EDA100']; GREY = '8A8984'
    hist_last = 1 + int((X.period == 'History').sum())                       # last history row on Data
    cs = wb.create_sheet('Charts')
    cs['A1'] = f'How things are projecting: last 30 days (actual / known at each bid) and the next 14 days (tomorrow {D} + 13, IESO schedule and weather forecast)'
    cs['A1'].font = Font(name=FONT, size=12, bold=True)
    cs['A2'] = 'Forward values are forecasts / schedules; prices and actuals stop at the last finished day. Scatter charts use the last 30 days only.'
    cs['A2'].font = Font(name=FONT, size=9, italic=True, color='4E5C57')
    cats = Reference(ws, min_col=1, min_row=2, max_row=last)
    def style(ch, title, ytitle):
        ch.title = title; ch.y_axis.title = ytitle; ch.height = 7.5; ch.width = 16.5; ch.legend.position = 'b'
        ch.x_axis.number_format = 'mm-dd'; ch.x_axis.majorTimeUnit = 'days'
        ch.y_axis.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(solidFill='E6E6E3'))
        ch.x_axis.delete = False; ch.y_axis.delete = False; ch.x_axis.tickLblPos = 'low'
    def line(title, ytitle, ks, dash_last=False):
        ch = LineChart(); style(ch, title, ytitle)
        for i, k in enumerate(ks):
            ref = Reference(ws, min_col=keys.index(k) + 3, min_row=1, max_row=last); ch.add_data(ref, titles_from_data=True)
            se = ch.series[-1]; c = GREY if k == 'sell_line' else PAL[i % 4]
            se.graphicalProperties.line.solidFill = c; se.graphicalProperties.line.width = 22000; se.smooth = False; se.marker = Marker(symbol='none')
            if k == 'sell_line': se.graphicalProperties.line.dashStyle = 'dash'
        ch.set_categories(cats); ch.display_blanks = 'gap'; return ch
    def cols(title, ytitle, ks, stacked=False):
        ch = BarChart(); ch.type = 'col'; style(ch, title, ytitle)
        if stacked: ch.grouping = 'stacked'; ch.overlap = 100
        for i, k in enumerate(ks):
            ref = Reference(ws, min_col=keys.index(k) + 3, min_row=1, max_row=last); ch.add_data(ref, titles_from_data=True)
            ch.series[-1].graphicalProperties.solidFill = PAL[i % 4]; ch.series[-1].graphicalProperties.line.solidFill = PAL[i % 4]
        ch.gapWidth = 40; ch.set_categories(cats); return ch
    def scatter(title, xk, yk, xt, yt):
        ch = ScatterChart(); ch.title = title; ch.style = 13; ch.height = 7.5; ch.width = 16.5; ch.legend = None
        xs = Reference(ws, min_col=keys.index(xk) + 3, min_row=2, max_row=hist_last); ys = Reference(ws, min_col=keys.index(yk) + 3, min_row=2, max_row=hist_last)
        se = Series(ys, xs, title='last 30 days'); se.marker = Marker(symbol='circle', size=8); se.marker.graphicalProperties = GraphicalProperties(solidFill=PAL[0])
        se.marker.graphicalProperties.line.solidFill = 'FFFFFF'; se.graphicalProperties.line.noFill = True; ch.series.append(se)
        ch.x_axis.title = xt; ch.y_axis.title = yt; ch.x_axis.delete = False; ch.y_axis.delete = False
        ch.x_axis.tickLblPos = 'low'; ch.y_axis.tickLblPos = 'low'
        ch.y_axis.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(solidFill='E6E6E3')); return ch
    CH = [line('Demand: daily peak, forecast at the bid / schedule vs actual', 'MW', ['dem_peak', 'dem_act']),
          cols('Outages known at the bid / scheduled (HE8-21 avg)', 'MW', ['nuc_out', 'gas_out', 'hyd_out'], stacked=True),
          line('Headroom vs the 7,000 MW sell line', 'MW', ['head_min', 'head_onpk', 'sell_line']),
          cols('Outage MW added after the bid (not in DA)', 'MW', ['add_after']),
          line('Wind forecast (HE8-21 avg)', 'MW', ['wind_onpk']),
          line('Wind at 100 m: Lake Huron and Lake Erie shores', 'km/h', ['wind_huron', 'wind_erie']),
          line('Max temperature: Toronto and Ottawa', 'deg C', ['tor_tmax', 'ott_tmax']),
          cols('Toronto midday cloud cover (11:00-16:00)', '%', ['tor_cloud']),
          line('Toronto sea-level pressure (high = calm, clear)', 'hPa', ['tor_press']),
          line('East DA vs RT (HE8-21 avg)', '$/MWh', ['east_da', 'east_rt']),
          cols('DA - RT, East and Ottawa (+ = sells won)', '$/MWh', ['east_sp', 'ott_sp']),
          line('Exports to Quebec (actual) and the PQ.AT DA export limit', 'MW', ['pq_exp', 'pqat_lim']),
          scatter('Tightest headroom vs East DA - RT (last 30 days)', 'head_min', 'east_sp', 'Tightest headroom HE8-21 (MW)', 'East DA - RT ($/MWh)'),
          scatter('Outages added after the bid vs East DA - RT', 'add_after', 'east_sp', 'MW added after the bid', 'East DA - RT ($/MWh)'),
          scatter('Demand miss vs East DA - RT', 'load_miss', 'east_sp', 'Actual peak - forecast peak (MW)', 'East DA - RT ($/MWh)'),
          scatter('Total outages at the bid vs East DA price', 'tot_out', 'east_da', 'Total outages (MW)', 'East DA ($/MWh)')]
    for i, ch in enumerate(CH):
        cs.add_chart(ch, f"{'A' if i % 2 == 0 else 'K'}{4 + (i // 2) * 16}")


    # ---- Scenario: change the inputs that move price, see headroom, DA / RT forecast and the model's score change
    B = json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text(encoding='utf-8'))
    sc = wb.create_sheet('Scenario'); YEL = PatternFill('solid', fgColor='FFFF00')
    sc['A1'] = f'Scenario for {D}: change the yellow inputs; headroom, gas need, the DA / RT forecast and the suggested score update'
    sc['A1'].font = Font(name=FONT, size=12, bold=True)
    sc['A2'] = ('Same arithmetic as the desk what-if sliders: headroom = gas + hydro available - (demand - nuclear - wind - solar); DA and RT move by the DA model\'s own '
                'headroom and NY-flow coefficients for that hour; the score re-runs with today\'s learned thresholds. A scenario, not a forecast.')
    sc['A2'].font = Font(name=FONT, size=9, italic=True, color='4E5C57'); sc['A2'].alignment = Alignment(wrap_text=True); sc.merge_cells('A2:Q2'); sc.row_dimensions[2].height = 28
    INP = [('Demand change (MW, + = more load)', 0, 'e.g. +500 for a hotter or cloudier day than IESO assumes'),
           ('Wind change (% of IESO forecast, - = less wind)', 0, 'e.g. -50 for a calm day'),
           ('Solar change (% of IESO forecast)', 0, ''),
           ('Gas available change (MW, - = outage / trip)', 0, 'e.g. -500 for one gas unit tripping'),
           ('Nuclear available change (MW, - = outage)', 0, 'e.g. -880 for one Bruce / Darlington unit'),
           ('Hydro available change (MW)', 0, ''),
           ('Net exports change (MW, + = more exports)', 0, 'e.g. +800 if NY / Quebec pull harder'),
           ('Apply from HE', 1, 'IESO hour-ending, 1-24'), ('Apply to HE', 24, '')]
    for i, (lab, v, note) in enumerate(INP):
        r = 4 + i; sc.cell(row=r, column=1, value=lab).font = BOLD
        c = sc.cell(row=r, column=4, value=v); c.font = BLUE; c.fill = YEL; c.alignment = Alignment(horizontal='center')
        sc.cell(row=r, column=5, value=note).font = Font(name=FONT, size=9, italic=True, color='4E5C57')
    sc['H4'] = 'Model thresholds today (from the desk, re-learned daily)'; sc['H4'].font = BOLD
    TH = [('Tight sell: headroom below (MW)', 'head'), ('Surplus sell: gas need below (MW)', 'gas'), ('Extended sell (score 4): gas need below (MW)', 'gas_ext')]
    zr = {}
    for j, z in enumerate(('EAST', 'OTTAWA')):
        H_ = B['hubs'][z]; th = H_['thr']; bb = H_.get('buy_band') or {}
        c0 = 11 + j * 2; sc.cell(row=4, column=c0, value=z.title()).font = BOLD
        vals = [th.get('head'), th.get('gas'), th.get('gas_ext'), bb.get('lo'), bb.get('hi')]
        for i, v in enumerate(vals):
            c = sc.cell(row=5 + i, column=c0, value=v); c.font = BLUE; c.number_format = '#,##0'
        zr[z] = L(c0)
    for i, lab in enumerate([t[0] for t in TH] + ['Buy band: headroom from (MW)', 'Buy band: headroom to (MW)']):
        sc.cell(row=5 + i, column=8, value=lab).font = BLK
    # hourly table
    hr0 = 15
    hdr = ['HE', 'In range', 'Wind chg', 'Solar chg', 'Headroom chg', 'Headroom base', 'Headroom scen.', 'Gas need base', 'Gas need scen.']
    for z in ('East', 'Ottawa'): hdr += [f'{z} DA fc base', f'{z} DA fc scen.', f'{z} RT fc base', f'{z} RT fc scen.', f'{z} score base', f'{z} score scen.']
    hdr += ['b_head E', 'b_ny E', 'b_head O', 'b_ny O', 'Wind fc', 'Solar fc']
    for j, h in enumerate(hdr, start=1):
        c = sc.cell(row=hr0, column=j, value=h); c.font = HDR; c.fill = HFILL; c.alignment = Alignment(wrap_text=True, horizontal='center', vertical='center')
    sc.row_dimensions[hr0].height = 42
    E, O = {h_['he']: h_ for h_ in B['hubs']['EAST']['hours']}, {h_['he']: h_ for h_ in B['hubs']['OTTAWA']['hours']}
    col_ = {h: L(j) for j, h in enumerate(hdr, start=1)}
    def score(head, gas, z):
        t = zr[z]
        return (f'IF(OR({head}<${t}$5,{gas}<${t}$6),5,IF({gas}<${t}$7,4,IF(AND({head}>=${t}$8,{head}<${t}$9),1,3)))')
    for k, he in enumerate(range(1, 25)):
        r = hr0 + 1 + k; e, o = E[he], O[he]
        put = lambda h, v, f=None, font=BLK: (sc.cell(row=r, column=list(col_).index(h) + 1, value=v), None)[0]
        vals = {'HE': he, 'Headroom base': e['head'], 'Gas need base': e.get('gas_hat'), 'East DA fc base': e['p_da'], 'East RT fc base': e['p_rt'],
                'Ottawa DA fc base': o['p_da'], 'Ottawa RT fc base': o['p_rt'], 'b_head E': e.get('b_h'), 'b_ny E': e.get('b_dni') or 0,
                'b_head O': o.get('b_h'), 'b_ny O': o.get('b_dni') or 0, 'Wind fc': e.get('wind_fc') or 0, 'Solar fc': e.get('solar_fc') or 0,
                'East score base': e['score'], 'Ottawa score base': o['score']}
        for h, v in vals.items():
            c = sc.cell(row=r, column=list(col_).index(h) + 1, value=v); c.font = BLUE if h != 'HE' else BOLD
        f = {'In range': f'=IF(AND(A{r}>=$D$11,A{r}<=$D$12),1,0)',
             'Wind chg': f'={col_["In range"]}{r}*{col_["Wind fc"]}{r}*$D$5/100',
             'Solar chg': f'={col_["In range"]}{r}*{col_["Solar fc"]}{r}*$D$6/100',
             'Headroom chg': f'={col_["In range"]}{r}*(-$D$4+$D$7+$D$8+$D$9)+{col_["Wind chg"]}{r}+{col_["Solar chg"]}{r}',
             'Headroom scen.': f'={col_["Headroom base"]}{r}+{col_["Headroom chg"]}{r}',
             'Gas need scen.': f'=IF(ISNUMBER({col_["Gas need base"]}{r}),{col_["Gas need base"]}{r}+{col_["In range"]}{r}*($D$4-$D$8+$D$10)-{col_["Wind chg"]}{r}-{col_["Solar chg"]}{r},"")'}
        for z, bh, bn in (('East', 'b_head E', 'b_ny E'), ('Ottawa', 'b_head O', 'b_ny O')):
            m = f'EXP({col_[bh]}{r}*{col_["Headroom chg"]}{r}/1000+{col_[bn]}{r}*{col_["In range"]}{r}*$D$10/1000)'
            f[f'{z} DA fc scen.'] = f'={col_[z + " DA fc base"]}{r}*{m}'
            f[f'{z} RT fc scen.'] = f'={col_[z + " RT fc base"]}{r}*{m}'
            f[f'{z} score scen.'] = '=' + score(f'{col_["Headroom scen."]}{r}', f'{col_["Gas need scen."]}{r}', z.upper())
        for h, v in f.items():
            c = sc.cell(row=r, column=list(col_).index(h) + 1, value=v); c.font = BLK
        for h in col_:
            c = sc.cell(row=r, column=list(col_).index(h) + 1); c.border = THIN
            if 'fc' in h and 'Wind' not in h and 'Solar' not in h: c.number_format = '0.00'
            elif h in ('HE', 'In range') or 'score' in h: c.number_format = '0'
            elif h.startswith('b_'): c.number_format = '0.0000'
            else: c.number_format = '#,##0;-#,##0;0'
    rl = hr0 + 24
    for z in ('East', 'Ottawa'):
        cl = col_[f'{z} score scen.']; bl = col_[f'{z} score base']
        sc.conditional_formatting.add(f'{cl}{hr0+1}:{cl}{rl}', FormulaRule(formula=[f'{cl}{hr0+1}<>{bl}{hr0+1}'], fill=TFILL, font=Font(name=FONT, bold=True)))
    for j in range(1, len(hdr) + 1): sc.column_dimensions[L(j)].width = 10.5
    sc.column_dimensions['A'].width = 12
    # results block (rows 4-12 beside the thresholds)
    sc['H11'] = 'Result (HE8-21 unless noted)'; sc['H11'].font = BOLD
    pk = f'{hr0+8}:{hr0+21}'
    a, b_ = hr0 + 8, hr0 + 21
    res = [('Tightest headroom: base / scenario', f'=MIN({col_["Headroom base"]}{a}:{col_["Headroom base"]}{b_})', f'=MIN({col_["Headroom scen."]}{a}:{col_["Headroom scen."]}{b_})', '#,##0'),
           ('East DA forecast avg: base / scenario', f'=AVERAGE({col_["East DA fc base"]}{a}:{col_["East DA fc base"]}{b_})', f'=AVERAGE({col_["East DA fc scen."]}{a}:{col_["East DA fc scen."]}{b_})', '0.00'),
           ('Ottawa DA forecast avg: base / scenario', f'=AVERAGE({col_["Ottawa DA fc base"]}{a}:{col_["Ottawa DA fc base"]}{b_})', f'=AVERAGE({col_["Ottawa DA fc scen."]}{a}:{col_["Ottawa DA fc scen."]}{b_})', '0.00'),
           ('East sell hours (score 4-5, all 24): base / scenario', f'=COUNTIF({col_["East score base"]}{hr0+1}:{col_["East score base"]}{rl},">=4")', f'=COUNTIF({col_["East score scen."]}{hr0+1}:{col_["East score scen."]}{rl},">=4")', '0'),
           ('East buy hours (score 1): base / scenario', f'=COUNTIF({col_["East score base"]}{hr0+1}:{col_["East score base"]}{rl},1)', f'=COUNTIF({col_["East score scen."]}{hr0+1}:{col_["East score scen."]}{rl},1)', '0'),
           ('Ottawa sell hours: base / scenario', f'=COUNTIF({col_["Ottawa score base"]}{hr0+1}:{col_["Ottawa score base"]}{rl},">=4")', f'=COUNTIF({col_["Ottawa score scen."]}{hr0+1}:{col_["Ottawa score scen."]}{rl},">=4")', '0'),
           ('Ottawa buy hours: base / scenario', f'=COUNTIF({col_["Ottawa score base"]}{hr0+1}:{col_["Ottawa score base"]}{rl},1)', f'=COUNTIF({col_["Ottawa score scen."]}{hr0+1}:{col_["Ottawa score scen."]}{rl},1)', '0'),
           ('Hours whose East score changes', '', f'=SUMPRODUCT(--({col_["East score scen."]}{hr0+1}:{col_["East score scen."]}{rl}<>{col_["East score base"]}{hr0+1}:{col_["East score base"]}{rl}))', '0')]
    # put results at the right of the inputs, rows 4-11 in columns S-U
    sc['S3'] = 'Result'; sc['S3'].font = BOLD; sc['V3'] = 'Base'; sc['W3'] = 'Scenario'; sc['V3'].font = BOLD; sc['W3'].font = BOLD
    for i, (lab, fb, fs, nf) in enumerate(res):
        r = 4 + i; sc.cell(row=r, column=19, value=lab).font = BLK
        for cc, v in ((22, fb), (23, fs)):
            c = sc.cell(row=r, column=cc, value=v if v else None); c.font = BOLD; c.number_format = nf
    del sc['H11']
    sc['A13'] = ('Quick scenarios: one gas unit trips in the evening -> Gas -500, HE 16-21 | a nuclear unit out -> Nuclear -880 | calm day -> Wind -60% | '
                 'hot / cloudy day -> Demand +700 | exports pull -> Net exports +800. Set everything back to 0 and HE 1-24 for the base case. '
                 'Scores: 5 sell, 4 extended sell, 1 buy (buy band), 3 neutral straddle; yellow = the score changed.')
    sc['A13'].font = Font(name=FONT, size=9, italic=True, color='4E5C57'); sc['A13'].alignment = Alignment(wrap_text=True); sc.merge_cells('A13:Q13'); sc.row_dimensions[13].height = 30
    # charts: headroom base vs scenario, East DA forecast base vs scenario
    from openpyxl.chart import LineChart, Reference
    for i, (title, yt, hs) in enumerate((('Headroom by hour: base vs scenario', 'MW', ['Headroom base', 'Headroom scen.']),
                                         ('East DA forecast by hour: base vs scenario', '$/MWh', ['East DA fc base', 'East DA fc scen.']))):
        ch = LineChart(); ch.title = title; ch.y_axis.title = yt; ch.height = 7.5; ch.width = 16; ch.legend.position = 'b'
        for k2, h in enumerate(hs):
            ci = list(col_).index(h) + 1; ch.add_data(Reference(sc, min_col=ci, min_row=hr0, max_row=rl), titles_from_data=True)
            se = ch.series[-1]; se.graphicalProperties.line.solidFill = ['8A8984', '2A78D6'][k2]; se.graphicalProperties.line.width = 22000; se.smooth = False
            if k2 == 0: se.graphicalProperties.line.dashStyle = 'dash'
        ch.set_categories(Reference(sc, min_col=1, min_row=hr0 + 1, max_row=rl)); ch.x_axis.title = 'HE'; ch.x_axis.delete = False; ch.y_axis.delete = False
        ch.x_axis.tickLblPos = 'low'
        sc.add_chart(ch, f"{'A' if i == 0 else 'K'}{rl + 3}")
    sc.freeze_panes = f'B{hr0+1}'

    # ---- README
    rd = wb.create_sheet('README')
    lines = [('Pre-model checklist -- how to read this workbook', 'title'), ('', ''),
             ('Summary: one row per item. Tomorrow vs the average of the last 14 and last 30 delivery days, the 30-day spread (SD, min, max), and the next-14-day average vs the last 30.', ''),
             ('   Flag HIGH / LOW = tomorrow is at least one standard deviation above / below the last 30 days.', ''),
             ('Next_14_Days: each of the next 14 days, raw value then the difference vs the last-14 and last-30 means. Red / green = the difference is bigger than one 30-day SD.', ''),
             ('Last_30_Days: each of the last 30 days (newest first), raw value then the difference vs the last-14 and last-30 means.', ''),
             ('Scenario: change demand, wind, solar, gas / nuclear / hydro availability and exports (optionally for a range of hours) and see tomorrow\'s headroom, DA / RT forecast and the model\'s score change, East and Ottawa.', ''),
             ('Charts: the key series over the last 30 days and the next 14 (forecasts), plus scatter plots of what drove DA - RT over the last 30 days.', ''),
             ('Data: the raw daily numbers (blue = inputs written by the script; yellow row = tomorrow). Every average and difference elsewhere is a formula on this sheet. Green values = links to Data.', ''), ('', ''),
             ('What each row is', 'h'),
             ("History rows use what was known at that day's bid (IESO pre-DA Adequacy) plus what then happened (actual demand, prices, outages added after the bid).", ''),
             ("Tomorrow uses today's pre-DA IESO file. Forward rows use IESO's 35-day outage and demand schedule (latest issue) and Open-Meteo's 16-day weather forecast.", ''),
             ('Peak = HE8-21 (IESO clock, EST). Weather hours are Toronto local time. Headroom = gas + hydro available - (demand - nuclear available - wind - solar).', ''),
             ("Items that cannot exist yet are blank: tomorrow's DA price, forward prices and trips, forward wind beyond IESO's short-range forecast.", ''), ('', ''),
             ('How to use it before the model', 'h'),
             ('1. Summary flags: what is unusual tomorrow vs the last month (HIGH / LOW).', ''),
             ('2. Outages: known outages are priced into DA (tested); "added after the bid" is what DA misses -- look at how big it has been lately.', ''),
             ('3. Load and weather: a temperature or cloud departure vs recent days means load-miss risk (the other source of losing days).', ''),
             ('4. Wind: high pressure and low 100 m wind vs recent days = a tighter evening peak.', ''),
             ('5. Next_14_Days: step changes in scheduled outages and headroom that are coming.', ''), ('', ''),
             ('Sources', 'h'),
             ('IESO Adequacy2 pre-DA vintage (canpower archive, pull_history.py); IESO 35-day Adequacy3 schedule (ieso_fwd35.py); IESO actual demand (Warehouse); outage timeline (outage_timeline.py); '
              'IESO pre-DA intertie limits and NRGStream PQ limits; IESO / NRGStream zone prices; NYISO DAM; IESO intertie flows; Open-Meteo forecast API '
              '(Toronto 43.65,-79.38; Ottawa 45.42,-75.70; Lake Huron shore 44.00,-81.60; Lake Erie shore 42.40,-82.20).', ''),
             (f'Built for delivery day {D}. Weather: Open-Meteo {wsrc}.', '')]
    for i, (t, st) in enumerate(lines, start=1):
        c = rd.cell(row=i, column=1, value=t)
        c.font = Font(name=FONT, size=13 if st == 'title' else 10, bold=st in ('title', 'h')); c.alignment = Alignment(wrap_text=True, vertical='top')
    rd.column_dimensions['A'].width = 150
    wb._sheets = [wb['README'], wb['Summary'], wb['Scenario'], wb['Charts'], wb['Next_14_Days'], wb['Last_30_Days'], wb['Data']]
    wb.active = 1
    try: wb.save(path)
    except PermissionError:                      # the workbook is open in Excel: save a new copy instead
        path = path.with_name(f"{path.stem}_{pd.Timestamp.now():%Y%m%d_%H%M}{path.suffix}"); wb.save(path)
        print('Checklist_Deviations.xlsx is open in Excel, so this run was saved as', path.name)
    return path


if __name__ == '__main__':
    X, D, wsrc = build(sys.argv[1] if len(sys.argv) > 1 else None)
    out = write(X, D, wsrc, C.ROOT / 'site' / 'Checklist_Deviations.xlsx')
    print(f'checklist -> {out} (delivery day {D}, weather {wsrc})')
