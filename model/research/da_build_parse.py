# Nov 5 2026: parse IESO archive reports for the DA-build tests. Usage: da_build_parse.py 202610
# Adequacy3: pre-bid version (last created before D-1 10:00 EST) and post-DA version (first created D-1 12:30-18:00 EST):
#   ForecastOntDemand, PeakDemand, AverageDemand, export/import/internal schedules.  DATotals: DA cleared totals.  DAVirtualTransactions: virtuals by zone.
import sys, re, zipfile, glob, pandas as pd
M = sys.argv[1]; A = 'archive'
def hours(block, tag='EnergyMW'):
    return {int(h): float(v) for h, v in re.findall(r'<DeliveryHour>(\d+)</DeliveryHour>\s*<' + tag + r'>(-?[\d.]+)</' + tag + '>', block)}
def sect(t, path):
    for p in path:
        i = t.find('<' + p + '>');
        if i < 0: return ''
        t = t[i:t.find('</' + p + '>', i)]
    return t
def ver(n): m = re.search(r'_v(\d+)', n); return int(m.group(1)) if m else 0
rows = []
zf = zipfile.ZipFile(f'{A}/Adequacy3/Adequacy3_{M}.zip'); by = {}
for n in zf.namelist():
    m = re.search(r'_(\d{8})_v', n)
    if m: by.setdefault(m.group(1), []).append(n)
cache = {}
def ca(n):
    if n not in cache:
        t = zf.read(n).decode(errors='ignore'); cache[n] = (re.search(r'<CreatedAt>(.*?)</CreatedAt>', t).group(1), t)
    return cache[n]
for d, ns in sorted(by.items()):
    D = f'{d[:4]}-{d[4:6]}-{d[6:]}'; prev = (pd.Timestamp(D) - pd.Timedelta(days=1)).strftime('%Y-%m-%d'); ns = sorted(ns, key=ver)
    def last_before(cut):
        lo, hi, best = 0, len(ns) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if ca(ns[mid])[0] < cut: best = mid; lo = mid + 1
            else: hi = mid - 1
        return best
    i_pre = last_before(prev + 'T10:00'); i_post = last_before(prev + 'T12:30'); i_post = 0 if i_post is None else i_post + 1
    out = {}
    for tag, i in [('pre', i_pre), ('post', i_post)]:
        if i is None or i >= len(ns): continue
        c, t = ca(ns[i])
        if tag == 'post' and not (prev + 'T12:30' <= c <= prev + 'T18:00'): continue
        out[tag] = c
        for k, path, inner in [('ont_fc', ['ForecastOntDemand'], 'EnergyMW'), ('peak', ['OntarioDemand', 'PeakDemand'], 'EnergyMW'), ('avg', ['OntarioDemand', 'AverageDemand'], 'EnergyMW'),
                               ('exp_sch', ['TotalExports', 'Schedules'], 'EnergyMW'), ('imp_sch', ['TotalImports', 'Schedules'], 'EnergyMW'), ('int_sch', ['TotalInternalResources', 'Schedules'], 'EnergyMW'),
                               ('dl_sch', ['DispatchableLoad', 'Schedules'], 'EnergyMW'), ('exp_bid', ['TotalExports', 'Bids'], 'EnergyMW')]:
            s = sect(t, path)
            for h, v in hours(s, inner).items(): out.setdefault(h, {})[f'{tag}_{k}'] = v
    for h in range(1, 25):
        r = {'date': D, 'he': h, 'pre_at': out.get('pre'), 'post_at': out.get('post')}; r.update(out.get(h, {})); rows.append(r)
a = pd.DataFrame(rows)
tz = []
for f in glob.glob(f'{A}/DATotals/DATotals_{M}.zip'):
    z = zipfile.ZipFile(f)
    for n in z.namelist():
        t = z.read(n).decode(errors='ignore'); D = re.search(r'<DeliveryDate>(.*?)</DeliveryDate>', t).group(1); c = re.search(r'<CreatedAt>(.*?)</CreatedAt>', t).group(1)
        for blk in re.findall(r'<HourlyEnergy>(.*?)</HourlyEnergy>', t, re.S):
            h = int(re.search(r'<DeliveryHour>(\d+)', blk).group(1)); r = {'date': D, 'he': h, 'dat_at': c}
            for q, v in re.findall(r'<MarketQuantity>(.*?)</MarketQuantity>\s*<EnergyMW>(-?[\d.]+)', blk): r['da_' + q.lower().replace(' ', '_')] = float(v)
            tz.append(r)
t = pd.DataFrame(tz).sort_values('dat_at').drop_duplicates(['date', 'he'], keep='first') if tz else pd.DataFrame(columns=['date', 'he'])
vz = []
for f in glob.glob(f'{A}/DAVirtualTransactions/DAVirtualTransactions_{M}.zip'):
    z = zipfile.ZipFile(f)
    for n in z.namelist():
        tx = z.read(n).decode(errors='ignore'); D = re.search(r'<DeliveryDate>(.*?)</DeliveryDate>', tx).group(1)
        for zn, body in re.findall(r'<ZoneName>(.*?)</ZoneName>(.*?)</ZonalTransactions>', tx, re.S):
            for blk in re.findall(r'<HourlyTransactions>(.*?)</HourlyTransactions>', body, re.S):
                h = int(re.search(r'<DeliveryHour>(\d+)', blk).group(1)); r = {'date': D, 'he': h, 'zone': zn}
                for ty, v in re.findall(r'<Type>(.*?)</Type>\s*<Value>(-?[\d.]+)', blk): r[ty.lower().replace(' ', '_')] = float(v)
                vz.append(r)
v = pd.DataFrame(vz)
a.merge(t, on=['date', 'he'], how='left').to_csv(f'data/research/dabuild/adq_dat_{M}.csv', index=False)
if len(v): v.drop_duplicates(['date', 'he', 'zone'], keep='last').to_csv(f'data/research/dabuild/vt_{M}.csv', index=False)
print(M, 'adequacy days', a.date.nunique(), 'with pre', a.pre_at.notna().groupby(a.date).any().sum(), 'with post', a.post_at.notna().groupby(a.date).any().sum(), '| DATotals rows', len(t), '| VT rows', len(v))
