"""
ieso_backfill.py -- save IESO's rolling public window before it disappears.

IESO keeps only ~90 days of prices and ~30-46 days of forecast versions on
reports-public.ieso.ca, and nothing in either database holds hourly DA/RT
prices before that. This script copies the window into archive\\ so the
history starts growing from today. Run it now, then once a day (the model's
morning job will call it).

    python ieso_backfill.py            # everything below
    python ieso_backfill.py --quick    # prices + Adequacy3 only

Idempotent: files already in the archive are skipped, so re-running only
downloads what is new. Raw files are stored unchanged, one zip per report per
delivery month (keeps OneDrive from syncing tens of thousands of small files).
"""
import argparse, re, sys, time, zipfile, threading, urllib.request, ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCH = HERE / 'archive'; ARCH.mkdir(exist_ok=True)
BASE = 'https://reports-public.ieso.ca/public/'
UA = {'User-Agent': 'Mozilla/5.0 (DynastyPower ontario-cushion-model backfill)'}
LOCK = threading.Lock()

# report -> which files to keep
#   'final'   : the unversioned daily/hourly file (latest revision)
#   'all'     : every version (forecast vintages)
#   'preDA'   : unversioned + versions created on D-1 before 09:00 (IESO time = EST)
REPORTS = [
    ('DAHourlyZonal',                 'final'),
    ('DAHourlyOntarioZonalPrice',     'final'),
    ('RealtimeZonalEnergyPrices',     'final'),
    ('RealtimeOntarioZonalPrice',     'final'),
    ('Adequacy3',                     'all'),     # every version: outage timeline for the live 'trips in last 24 h' input
    ('DATotals',                      'final'),
    ('DAVirtualTransactions',         'final'),
    ('IntertieScheduleFlow',          'final'),
    ('GenOutputCapability',           'all'),     # every hourly version: per-unit capability, so we can see WHEN a unit was forced out
    ('VGForecastSummary',             'all'),
    ('PredispHourlyOntarioZonalPrice','all'),
    ('PredispHourlyZonal',            'all'),
    ('DAConstrShadowPrices',          'final'),
    ('PreDAIntertieSchedLimits',      'final'),   # published D-1 ~08:08 EST -> known at the bid deadline
    ('DAIntertieSchedLimits2',        'final'),
    ('PredispIntertieSchedLimits',    'final'),
    ('TxOutagesTodayAll',             'all'),     # transmission outages today, every version (CreatedAt stamped)
    ('TxLimitsOutage0to2Days',        'all'),     # transmission outage limits, days 0-2, every ~30 min
    ('TxOutages1to30DaysPlanned',     'final'),
    ('DASecurityConstraints2',        'final'),   # constraints enforced in each DA run (congestion read, Oct 13 2026)
    ('TxLimitsAllInService0to34Days', 'final'),   # all-in-service interface limits (baseline for the outage limits)
]
QUICK = {'DAHourlyZonal','DAHourlyOntarioZonalPrice','RealtimeZonalEnergyPrices',
         'RealtimeOntarioZonalPrice','Adequacy3'}
YEARLY = [('Demand', 'PUB_Demand_{y}.csv'),
          ('GenOutputbyFuelHourly', 'PUB_GenOutputbyFuelHourly_{y}.xml'),
          ('IntertieScheduleFlowYear', 'PUB_IntertieScheduleFlowYear_{y}.csv')]


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as ex:
            if i == tries - 1: raise
            time.sleep(2 * (i + 1))


def listing(report):
    html = get(BASE + report + '/').decode('utf-8', 'replace')
    rows = re.findall(r'href="([^"]+\.(?:xml|csv))">[^<]*</a>\s+(\d{2}-\w{3}-\d{4} \d{2}:\d{2})', html)
    return [(f, datetime.strptime(t, '%d-%b-%Y %H:%M')) for f, t in rows]


def target_date(fname):
    m = re.search(r'_(\d{8})(\d{2})?(?:_v(\d+))?\.(xml|csv)$', fname)
    if not m: return None, None, None
    return datetime.strptime(m.group(1), '%Y%m%d'), m.group(2), m.group(3)


def est_now():
    """IESO files are stamped in EST all year (UTC-5)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)


def settled(report, d, hh):
    """Only archive an unversioned (latest) file once it can no longer change:
    DA reports once published (up to tomorrow); hourly RT files once the hour
    is over; everything else once the delivery day is over."""
    now = est_now()
    if report.startswith(('DA', 'PreDA')):
        return d.date() <= (now + timedelta(days=1)).date()
    if hh is not None:
        return d + timedelta(hours=int(hh)) <= now - timedelta(minutes=30)
    return d.date() < now.date()


def pick(report, mode, files):
    keep = []
    for f, t in files:
        d, hh, v = target_date(f)
        if d is None: continue
        if v is None:
            if mode in ('final', 'preDA', 'all') and settled(report, d, hh): keep.append(f)
        elif mode == 'all':
            keep.append(f)
        elif mode == 'preDA':
            d1 = d - timedelta(days=1)
            if d1 <= t < d1 + timedelta(hours=9): keep.append(f)
    return keep


def zpath(report, fname):
    d, _, _ = target_date(fname)
    return ARCH / report / f'{report}_{d:%Y%m}.zip'


def already(report):
    have = set()
    for z in (ARCH / report).glob('*.zip'):
        try:
            with zipfile.ZipFile(z) as zf: have.update(zf.namelist())
        except zipfile.BadZipFile:
            print(f'  WARNING corrupt {z.name}, it will be rebuilt'); z.unlink()
    return have


def save(report, fname, data):
    zp = zpath(report, fname); zp.parent.mkdir(parents=True, exist_ok=True)
    with LOCK:
        with zipfile.ZipFile(zp, 'a', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(fname, data)


def backfill(report, mode):
    t0 = time.time()
    files = listing(report)
    want = pick(report, mode, files)
    have = already(report)
    todo = [f for f in want if f not in have]
    ok = err = 0
    def one(f):
        nonlocal ok, err
        try:
            save(report, f, get(BASE + report + '/' + f)); ok += 1
        except Exception as ex:
            err += 1; print(f'    fail {f}: {str(ex)[:80]}')
    with ThreadPoolExecutor(8) as ex: list(ex.map(one, todo))
    print(f'  {report:<32} listed {len(files):>6}  kept {len(want):>6}  new {ok:>5}  failed {err:>3}  {time.time()-t0:5.0f}s', flush=True)


def yearly():
    y = datetime.now().year
    for rep, pat in YEARLY:
        for yy in (y - 1, y):
            f = pat.format(y=yy); out = ARCH / rep / f; out.parent.mkdir(parents=True, exist_ok=True)
            if yy < y and out.exists(): continue          # last year's file is final
            try:
                out.write_bytes(get(BASE + rep + '/' + f)); print(f'  {rep:<32} {f}')
            except Exception as ex:
                print(f'  {rep:<32} {f} failed: {str(ex)[:80]}')


def nyiso():
    """NYISO public reports, monthly zips back to START plus the daily tail:
      P-2A  damlbmp   DAM zonal LBMP (Zone A = WEST)          posted ~09:33 ET on D-1
      P-30  damenergy DAM daily energy report: scheduled imports/exports and
                      net imports per proxy, incl. OH (Ontario)   posted ~09:40-09:55 ET
    Both land before the IESO 10:00 ET DAM close on most days."""
    START = (2025, 4)
    base = 'http://mis.nyiso.com/public/csv/'
    reps = [('damlbmp', 'NYISO_damlbmp', '{d}damlbmp_zone_csv.zip', '{d}damlbmp_zone.csv'),
            ('damenergy', 'NYISO_damenergy', '{d}DAM_energy_rep_csv.zip', '{d}DAM_energy_rep.csv')]
    now = datetime.now()
    for sub, folder, zpat, dpat in reps:
        out = ARCH / folder; out.mkdir(parents=True, exist_ok=True)
        y, m = START; new = 0
        while (y, m) <= (now.year, now.month):
            f = zpat.format(d=f'{y}{m:02d}01')
            current = (y, m) >= ((now - timedelta(days=35)).year, (now - timedelta(days=35)).month)
            if current or not (out / f).exists():
                try: (out / f).write_bytes(get(base + sub + '/' + f)); new += 1
                except Exception as ex: print(f'  NYISO {sub} {f} failed: {str(ex)[:60]}')
            m += 1
            if m == 13: y, m = y + 1, 1
        for k in range(-1, 8):
            d = now - timedelta(days=k); f = dpat.format(d=f'{d:%Y%m%d}')
            try: (out / f).write_bytes(get(base + sub + '/' + f))
            except Exception: pass
        print(f'  NYISO {sub:<10} monthly zips refreshed/new: {new}')


def repair_rt(days=10):
    """Nov 1 2026: an hourly RT price file is sometimes archived before IESO finished it (e.g. Oct 17 HE9 has 7 of 12 intervals,
    Oct 23 HE11 has 2). Re-download recent files with fewer than 12 intervals for any zone; a complete copy goes into
    <report>_repair.zip, which parse_archive reads after the monthly zips (an incomplete hour is never used)."""
    import re
    now = est_now()
    for report in ('RealtimeZonalEnergyPrices', 'RealtimeOntarioZonalPrice'):
        tag = '<ZonalPrice>' if report == 'RealtimeZonalEnergyPrices' else '<LmpCap>'
        rz = ARCH / report / f'{report}_repair.zip'; have = set()
        if rz.exists():
            with zipfile.ZipFile(rz) as zf: have = set(zf.namelist())
        bad = []
        for z in sorted((ARCH / report).glob(f'{report}_2*.zip'))[-2:]:
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    d, hh, v = target_date(n)
                    if v is not None or d is None or (now - d).days > days or n in have: continue
                    txt = zf.read(n).decode(errors='ignore')
                    if report == 'RealtimeZonalEnergyPrices':
                        segs = re.split(r'<TransactionZone>', txt)[1:]; ok = bool(segs) and all(seg.count(tag) >= 12 for seg in segs)
                    else:
                        ok = txt.count(tag) >= 12
                    if not ok: bad.append(n)
        fixed = 0
        for n in bad:
            try:
                b = get(BASE + report + '/' + n); txt = b.decode(errors='ignore') if isinstance(b, bytes) else str(b)
                segs = re.split(r'<TransactionZone>', txt)[1:]
                ok = (bool(segs) and all(seg.count(tag) >= 12 for seg in segs)) if report == 'RealtimeZonalEnergyPrices' else txt.count(tag) >= 12
                if ok:
                    with LOCK:
                        with zipfile.ZipFile(rz, 'a', compression=zipfile.ZIP_DEFLATED) as zf: zf.writestr(n, b)
                    fixed += 1
            except Exception as ex: print(f'    repair {n} failed: {str(ex)[:60]}')
        print(f'  {report:<32} incomplete hours found {len(bad)}, repaired {fixed}' + (f' (still incomplete at IESO: {[x[-14:-4] for x in bad][:6]})' if len(bad) > fixed else ''))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--quick', action='store_true'); ap.add_argument('--nyiso', action='store_true', help='with --quick: also refresh the NYISO DAM files'); a = ap.parse_args()
    print(f'IESO backfill -> {ARCH}')
    for rep, mode in REPORTS:
        if a.quick and rep not in QUICK: continue
        try: backfill(rep, mode)
        except Exception as ex: print(f'  {rep:<32} FAILED: {str(ex)[:120]}')
    try: repair_rt()
    except Exception as ex: print('  RT repair skipped:', str(ex)[:120])
    if not a.quick:
        yearly(); nyiso()
    elif a.nyiso:
        nyiso()
    print('done.')
