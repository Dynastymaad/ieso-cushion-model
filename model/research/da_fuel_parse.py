# Nov 5 2026: wind in the DA: IESO wind forecast at the bid vs the DA wind schedule (first Adequacy3 version after the DA clears). Usage: da_wind_parse.py 202610
import sys, re, zipfile, pandas as pd
M = sys.argv[1]; zf = zipfile.ZipFile(f'archive/Adequacy3/Adequacy3_{M}.zip'); by = {}
for n in zf.namelist():
    m = re.search(r'_(\d{8})_v', n)
    if m: by.setdefault(m.group(1), []).append(n)
cache = {}
def ca(n):
    if n not in cache: t = zf.read(n).decode(errors='ignore'); cache[n] = (re.search(r'<CreatedAt>(.*?)</CreatedAt>', t).group(1), t)
    return cache[n]
def fuel(t, F):
    i = t.find('<FuelType>' + F + '</FuelType>'); j = t.find('</InternalResource>', i); b = t[i:j]; out = {}
    for tag, key in [('Schedules', 'sch')]:
        s = b[b.find('<' + tag + '>'):b.find('</' + tag + '>')]
        for h, v in re.findall(r'<DeliveryHour>(\d+)</DeliveryHour>\s*<EnergyMW>(-?[\d.]+)</EnergyMW>', s): out.setdefault(int(h), {})[key] = float(v)
    return out
rows = []
for d, ns in sorted(by.items()):
    D = f'{d[:4]}-{d[4:6]}-{d[6:]}'; prev = (pd.Timestamp(D) - pd.Timedelta(days=1)).strftime('%Y-%m-%d'); ns = sorted(ns, key=lambda n: int(re.search(r'_v(\d+)', n).group(1)))
    def last_before(cut):
        lo, hi, best = 0, len(ns) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if ca(ns[mid])[0] < cut: best = mid; lo = mid + 1
            else: hi = mid - 1
        return best
    ip = last_before(prev + 'T10:00'); iq = last_before(prev + 'T12:30'); iq = 0 if iq is None else iq + 1
    if ip is None or iq >= len(ns) or not (prev + 'T12:30' <= ca(ns[iq])[0] <= prev + 'T18:00'): continue
    t = ca(ns[iq])[1]; FU = {F: fuel(t, F) for F in ['Nuclear', 'Gas', 'Hydro', 'Wind', 'Solar', 'Biofuel', 'Storage', 'Other']}
    for h in range(1, 25): rows.append(dict(date=D, he=h, **{f'da_{F.lower()}': FU[F].get(h, {}).get('sch') for F in FU}))
pd.DataFrame(rows).to_csv(f'data/research/dabuild/fuel_{M}.csv', index=False); print(M, len(rows) // 24, 'days')
