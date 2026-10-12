"""fund_practice.py -- Oct 2026: the Fundamentals tab in the same form as the Ontario Read Practice page.
Bid-time values only. Every cell is ranked against the same hour on up to 60 earlier days that had settled before the bid
(history = data/fund_history.json: one bid-time snapshot per delivery day, seeded from data/replay, appended by each run).
Signed columns (Tesla-IESO, wind 3h, net load 3h, gas ramps, DA vs usual) are coloured by sign first, then size vs past values on
the same side. Display only -- no signal uses this."""
import sys, json, math; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import pandas as pd, common as C
HIST = C.DATA / 'fund_history.json'
FK = ['dem', 'tes', 'dyn', 'met', 'tg', 'w', 'wm', 'wlo', 'whi', 'w3', 'sol', 'res', 'n3', 'nlW', 'head', 'hT', 'hW', 'hX', 'need', 'sp', 'r1', 'r3',
      'hyd', 'exp', 'xy', 'cahr', 'daf', 'vs', 'nuc', 'gav']
SG = {'tg': (1, 50), 'w3': (-1, 50), 'n3': (1, 100), 'r1': (1, 100), 'r3': (1, 150), 'vs': (-1, 2)}
HOL = {'2026-10-12': 'Thanksgiving', '2026-10-10': 'Saturday of Thanksgiving weekend', '2026-10-11': 'Sunday of Thanksgiving weekend',
       '2026-11-11': 'Remembrance Day', '2026-12-25': 'Christmas', '2026-12-26': 'Boxing Day', '2027-01-01': "New Year's Day"}

def to_rows(F):
    """fund_panel rows -> practice-format rows (+ derived columns)."""
    rows = []
    for r in F['rows']:
        tg = None if r.get('tesla') is None or r.get('dem') is None else r['tesla'] - r['dem']
        dg = None if r.get('dyn') is None or r.get('dem') is None else r['dyn'] - r['dem']
        rows.append(dict(he=r['he'], dem=r.get('dem'), tes=r.get('tesla'), dyn=r.get('dyn'), met=r.get('meteo_load'), tg=tg, dg=dg, w=r.get('wind'), wm=r.get('wind_meteo'),
                         wlo=r.get('wind_nwp_min'), whi=r.get('wind_nwp_max'), w3=r.get('wind3'), sol=r.get('solar'), nuc=r.get('nuc'), hyd=r.get('hydro_exp'),
                         exp=None if r.get('net_exp') is None else -r['net_exp'], xy=r.get('exp_cleared_y'), res=r.get('resid'), gav=r.get('gas_av'), need=r.get('gas_need'),
                         sp=r.get('gas_spare'), r1=r.get('ramp1'), r3=r.get('ramp3'), r3p=r.get('ramp3_pct'), head=r.get('head'), cahr=r.get('cahr'), daf=r.get('da_e'), vs=r.get('da_vs')))
    nl = {r['he']: r['res'] for r in rows}
    for r in rows:
        wv = [v for v in (r['w'], r['wm'], r['wlo']) if v is not None]; lv = [v for v in (r['dem'], r['tes'], r['dyn'], r['met']) if v is not None]
        r['n3'] = None if r['res'] is None or nl.get(r['he'] - 3) is None else r['res'] - nl[r['he'] - 3]
        r['nlW'] = None if not wv or not lv or r['res'] is None or r['w'] is None else r['res'] + (max(lv) - r['dem']) + (r['w'] - min(wv))
        r['hT'] = None if r['tes'] is None or r['head'] is None else r['head'] - (r['tes'] - r['dem'])
        r['hW'] = None if r['wlo'] is None or r['w'] is None or r['head'] is None else r['head'] - max(0, r['w'] - r['wlo'])
        r['hX'] = None if r['nlW'] is None or r['head'] is None else r['head'] - (r['nlW'] - r['res'])
        alt = r['dg'] if r['dg'] is not None else (None if r['met'] is None or r['dem'] is None else r['met'] - r['dem'])
        r['lb'] = bool(r['tg'] is not None and r['tg'] <= -300 and alt is not None and alt <= -300)
    return rows

def lookback(D):
    p = pd.read_csv(C.DATA / 'prices_hourly.csv'); E = p[p.zone == 'EAST'].dropna(subset=['da', 'rt']).copy(); E['rd'] = E.rt - E.da
    hi = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); out = {}
    for k in (7, 14):
        lo = (pd.Timestamp(D) - pd.Timedelta(days=k + 2)).date().isoformat(); x = E[(E.date <= hi) & (E.date > lo)]
        for he, g in x.groupby('he'): out.setdefault(int(he), {})[k] = [int((g.rd > 0).sum()), len(g), round(float(g.rd.mean()), 1)]
    return out

def build(D, F):
    rows = to_rows(F)
    try: hist = json.loads(HIST.read_text())
    except Exception: hist = {}
    hist[D] = [{k: r.get(k) for k in FK + ['he']} for r in rows]          # store today's bid-time snapshot
    try: HIST.write_text(json.dumps(hist, separators=(',', ':')))
    except Exception as ex: print('fund history not saved:', ex)
    t = pd.Timestamp(D); prior = [hist[d] for d in sorted(hist) if 2 <= (t - pd.Timestamp(d)).days <= 62][-60:]
    lb = lookback(D)
    for r in rows:
        he = r['he']; H = [x[he - 1] for x in prior if len(x) >= he]; pc = {}
        for k in FK:
            v = r.get(k); h = [x.get(k) for x in H if x.get(k) is not None]
            if v is None or len(h) < 5: continue
            pc[k] = round(100 * (sum(y < v for y in h) + 0.5 * sum(y == v for y in h)) / len(h))
        ps = {}
        for k, (bull, db) in SG.items():
            v = r.get(k)
            if v is None: continue
            if abs(v) <= db: ps[k] = ['n0', None]; continue
            same = [abs(x.get(k)) for xs in prior for x in xs if x.get(k) is not None and x.get(k) * (1 if v > 0 else -1) > db]
            q = round(100 * sum(y < abs(v) for y in same) / len(same)) if same else 50
            ps[k] = [('u' if (v > 0) == (bull > 0) else 'd') + str(3 if q >= 67 else 2 if q >= 33 else 1), q]
        r['pc'], r['ps'] = pc, ps
        b = lb.get(he, {}); r['b7'], r['b14'] = b.get(7), b.get(14)
        r['f7'] = None if not r['b7'] or not r['b7'][1] else r['b7'][0] / r['b7'][1]; r['f14'] = None if not r['b14'] or not r['b14'][1] else r['b14'][0] / r['b14'][1]
    try:
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()): import spike_anatomy as SA
        ss = SA.sunset_est(D); sun = f"{int(ss)}:{int((ss % 1) * 60):02d} EST (HE{int(math.floor(ss)) + 1})"
    except Exception: sun = None
    facts = dict(date=D, hol=HOL.get(D, ''), sunset=sun, nuc=rows[0]['nuc'], pm=F.get('pm_ramp'), pmp=F.get('pm_ramp_pct'), am=F.get('am_ramp'), amp=F.get('am_ramp_pct'),
                 meteo_missing=all(r['wm'] is None for r in rows), models_missing=all(r['wlo'] is None for r in rows), npool=len(prior))
    return dict(rows=rows, facts=facts)

def seed():
    """one-off: fill fund_history.json from the replay bundles (bid-time reruns)."""
    import glob; hist = {}
    try: tz = pd.read_csv(C.DATA / 'da_cleared_ties.csv'); TZ = {(a, int(h)): int(round(v)) for a, h, v in zip(tz.date, tz.he, tz.net_dac) if pd.notna(v)}
    except Exception: TZ = {}
    for f in sorted(glob.glob(str(C.DATA / 'replay' / 'bundle_2026-*.json'))):
        b = json.loads(open(f).read()); F = b.get('fund')
        if not F: continue
        rows = to_rows(F); y = (pd.Timestamp(b['target']) - pd.Timedelta(days=1)).date().isoformat()
        for r in rows:
            if r.get('xy') is None and (y, r['he']) in TZ: r['xy'] = TZ[(y, r['he'])]
        hist[b['target']] = [{k: r.get(k) for k in FK + ['he']} for r in rows]
    HIST.write_text(json.dumps(hist, separators=(',', ':'))); print('seeded', len(hist), 'days', min(hist), max(hist))

if __name__ == '__main__': seed()
