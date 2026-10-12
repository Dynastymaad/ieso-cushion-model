"""da_cleared_ties.py -- Oct 2026: day-ahead CLEARED net exports by hour, from the first IESO Adequacy3 version published after the
day-ahead market clears (D-1 12:30-18:00 EST). Writes data/da_cleared_ties.csv (date, he, exp_dac, imp_dac, net_dac, da_ver).
Display only: the Fundamentals tab shows YESTERDAY's cleared exports for each hour (known before the 08:00 MT bid)."""
import sys, re, zipfile, glob; from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
def ver(n): m = re.search(r'_v(\d+)', n); return int(m.group(1)) if m else 10**6
def sched(t, tag):
    m = re.search(r'<' + tag + r'>.*?<Schedules>(.*?)</Schedules>', t, re.S)
    return {int(h): abs(float(v)) for h, v in re.findall(r'<DeliveryHour>(\d+)</DeliveryHour>\s*<EnergyMW>(-?[\d.]+)</EnergyMW>', m.group(1))} if m else {}
def main():
    out = ROOT / 'data' / 'da_cleared_ties.csv'
    old = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=['date', 'he', 'exp_dac', 'imp_dac', 'net_dac', 'da_ver'])
    have = set(old.date.astype(str)); rows = []
    for z in sorted(glob.glob(str(ROOT / 'archive' / 'Adequacy3' / 'Adequacy3_*.zip')))[-3:]:
        zf = zipfile.ZipFile(z); by = {}
        for n in zf.namelist():
            m = re.search(r'_(\d{8})', n)
            if m: by.setdefault(m.group(1), []).append(n)
        for d, ns in by.items():
            D = f'{d[:4]}-{d[4:6]}-{d[6:]}'
            if D in have: continue
            prev = (pd.Timestamp(D) - pd.Timedelta(days=1)).strftime('%Y-%m-%d'); hit = None
            for n in sorted([x for x in ns if '_v' in x], key=ver):
                t = zf.read(n).decode(errors='ignore'); ca = re.search(r'<CreatedAt>(.*?)</CreatedAt>', t).group(1)
                if prev + 'T12:30' <= ca <= prev + 'T18:00': hit = (t, ca); break
                if ca > prev + 'T18:00': break
            if not hit: continue
            ex, im = sched(hit[0], 'TotalExports'), sched(hit[0], 'TotalImports')
            for h in range(1, 25):
                if h in ex: rows.append((D, h, ex.get(h), im.get(h, 0.0), ex.get(h) - im.get(h, 0.0), hit[1]))
    new = pd.DataFrame(rows, columns=['date', 'he', 'exp_dac', 'imp_dac', 'net_dac', 'da_ver'])
    allx = pd.concat([old, new]).drop_duplicates(['date', 'he'], keep='last').sort_values(['date', 'he'])
    allx.to_csv(out, index=False); print(f'da_cleared_ties: {allx.date.nunique()} days, latest {allx.date.max()}')
if __name__ == '__main__':
    try: main()
    except Exception as ex: print('da_cleared_ties skipped:', ex)
