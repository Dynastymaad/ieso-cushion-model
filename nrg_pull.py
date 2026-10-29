"""nrg_pull.py -- Oct 28 2026. Daily NRGStream pull for the History tab (TEST STAGE: not wired into morning.py yet).
Uses the NRGStream API with YOUR login from nrg.json in this folder (never printed, never saved elsewhere; nrg.json is gitignored).
One token per login: it is always released at the end, even on errors.

    python nrg_pull.py --discover        # 1) catalogue -> data/nrg/stream_list.csv, candidate streams per slot -> data/nrg/stream_candidates.csv
    python nrg_pull.py --test            # 2) pulls the last 21 days for every candidate, keeps the one that matches the IESO archive,
                                         #    writes data/nrg/streams_ontario.json + data/nrg/nrg_test_report.txt  (then tell Claude "nrg test done")
    python nrg_pull.py --update          # 3) (after the test passes) pulls the last 10 days of the chosen streams into data/nrg/nrg_daily.csv

Slots: DA and RT hourly price for the 9 Ontario zones + Ontario zonal price; actual Ontario demand; actual output by fuel
(gas, nuclear, hydro, wind, solar). NRG times are hour-beginning Eastern prevailing time; nrg_import.to_key turns them into IESO keys."""
import json, re, sys, io, time, urllib.request, urllib.parse, urllib.error
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE / 'model'))
from nrg_import import to_key
NRG = HERE / 'data' / 'nrg'; NRG.mkdir(parents=True, exist_ok=True)
BASE = 'https://api.nrgstream.com'
ZONES = {'EAST': r'\beast\b', 'OTTAWA': r'ottawa', 'TORONTO': r'toronto', 'SOUTHWEST': r'south ?west', 'WEST': r'(?<!south)(?<!south )\bwest\b',
         'NIAGARA': r'niagara', 'ESSA': r'\bessa\b', 'NORTHEAST': r'north ?east', 'NORTHWEST': r'north ?west', 'ONTARIO': r'ontario zonal|\bozp\b'}
BAD = re.compile(r'loss|cong|forecast|predisp|pre-disp|shadow|limit|offer|bid|virtual|intertie|load ?fc|capacity|outage', re.I)
FUEL = {'DEMAND': r'ontario demand', 'G_GAS': r'gas', 'G_NUCLEAR': r'nuclear', 'G_HYDRO': r'hydro', 'G_WIND': r'wind', 'G_SOLAR': r'solar'}

def req(method, path, token=None, data=None, accept='application/json', timeout=90):
    h = {'Accept': accept}
    if token: h['Authorization'] = f'Bearer {token}'
    body = None
    if data is not None: body = urllib.parse.urlencode(data).encode(); h['Content-Type'] = 'application/x-www-form-urlencoded'
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp: return resp.status, resp.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e: return e.code, e.read().decode('utf-8', 'replace')

class Session:
    def __enter__(self):
        p = HERE / 'nrg.json'
        if not p.exists(): raise SystemExit('nrg.json not found: copy nrg.example.json to nrg.json and put your NRGStream username and password in it.')
        c = json.loads(p.read_text())
        st, txt = req('POST', '/api/security/token', data={'grant_type': 'password', 'username': c['username'], 'password': c['password']})
        del c
        if st != 200: raise SystemExit(f'NRG login failed (HTTP {st}). Check nrg.json, or log out of other NRG API sessions (one token per login).')
        self.token = json.loads(txt)['access_token']; print('NRG login OK'); return self
    def __exit__(self, *a):
        st, _ = req('DELETE', '/api/ReleaseToken', self.token); print(f'NRG token released ({st})')
    def data(self, sid, d0, d1):
        q = f'/api/StreamData/{sid}?fromDate={urllib.parse.quote(d0.strftime("%m/%d/%Y"))}&toDate={urllib.parse.quote(d1.strftime("%m/%d/%Y"))}'
        st, body = req('GET', q, self.token, accept='text/csv')
        if st != 200: return None, f'HTTP {st}: {body[:120]}'
        return parse(body), body[:300]

def parse(body):
    """NRG CSV -> DataFrame(ts_ept_begin, value). Skips any header block; takes the first date-like column and the first numeric one."""
    lines = [l for l in body.splitlines() if l.strip()]
    start = next((i for i, l in enumerate(lines) if re.match(r'^\s*"?\d{1,4}[-/]\d{1,2}[-/]\d{1,4}', l)), None)
    if start is None: return pd.DataFrame(columns=['ts_ept_begin', 'value'])
    d = pd.read_csv(io.StringIO('\n'.join(lines[start:])), header=None)
    ts = pd.to_datetime(d[0], errors='coerce')
    num = next((c for c in d.columns[1:] if pd.to_numeric(d[c], errors='coerce').notna().mean() > .5), None)
    out = pd.DataFrame({'ts_ept_begin': ts, 'value': pd.to_numeric(d[num], errors='coerce') if num is not None else float('nan')}).dropna(subset=['ts_ept_begin'])
    return out

def hourly(df):
    """sub-hourly -> hourly mean; keys -> (date, he) like the IESO files."""
    if df is None or df.empty: return pd.DataFrame(columns=['date', 'he', 'value'])
    df = df.copy(); df['hb'] = df.ts_ept_begin.dt.floor('h')
    h = df.groupby('hb').value.mean().reset_index().rename(columns={'hb': 'ts_ept_begin'})
    h['date'], h['he'] = to_key(h.ts_ept_begin.astype(str)); h = h[h.date.ne('NaT') & h.he.notna()]; h['he'] = h.he.astype(int)
    return h[['date', 'he', 'value']]

def discover():
    with Session() as s:
        st, txt = req('GET', '/api/StreamList', s.token)
        if st != 200: raise SystemExit(f'StreamList failed: HTTP {st}')
        L = json.loads(txt); L = next((v for v in L.values() if isinstance(v, list)), []) if isinstance(L, dict) else L
    sl = pd.DataFrame(L); sl.to_csv(NRG / 'stream_list.csv', index=False)
    idk = next(c for c in sl.columns if c.lower() in ('streamid', 'stream_id', 'id'))
    sl['text'] = sl.astype(str).agg(' | '.join, axis=1); ont = sl[sl.text.str.contains(r'ontario|ieso|\bON\b', case=False, regex=True)]
    rows = []
    for z, pat in ZONES.items():
        for mkt, mp in (('DA', r'\bDA\b|day.?ahead'), ('RT', r'\bRT\b|real.?time|realtime')):
            m = ont[ont.text.str.contains(pat, case=False, regex=True) & ont.text.str.contains(mp, case=False, regex=True)
                    & ont.text.str.contains(r'price|lmp', case=False, regex=True) & ~ont.text.str.contains(BAD)]
            for _, r in m.head(6).iterrows(): rows.append(dict(slot=f'{z}_{mkt}', stream=r[idk], name=r.text[:200]))
    for k, pat in FUEL.items():
        extra = r'demand' if k == 'DEMAND' else r'output|generation|gen\b|actual'
        m = ont[ont.text.str.contains(pat, case=False, regex=True) & ont.text.str.contains(extra, case=False, regex=True) & ~ont.text.str.contains(r'forecast|capab|capacity|outage|vg|price', case=False, regex=True)]
        for _, r in m.head(6).iterrows(): rows.append(dict(slot=k, stream=r[idk], name=r.text[:200]))
    c = pd.DataFrame(rows); c.to_csv(NRG / 'stream_candidates.csv', index=False)
    print(f'{len(sl):,} streams in the catalogue, {len(ont):,} Ontario-looking; candidates per slot:')
    print(c.groupby('slot').stream.count().to_string())

def ieso_ref():
    p = pd.read_csv(HERE / 'data' / 'prices_hourly.csv')
    ref = {f'{z}_{m}': p[p.zone == z][['date', 'he', m.lower()]].rename(columns={m.lower(): 'ref'}) for z in ZONES for m in ('DA', 'RT')}
    try:
        import common as C
        dm = pd.read_csv(C.ARCH / 'Demand' / f'PUB_Demand_{date.today().year}.csv', skiprows=3).rename(columns={'Date': 'date', 'Hour': 'he', 'Ontario Demand': 'ref'})
        ref['DEMAND'] = dm[['date', 'he', 'ref']]
        G = C.fuel_actual()
        for k in FUEL:
            if k.startswith('G_'): ref[k] = G[['date', 'he', k.lower()]].rename(columns={k.lower(): 'ref'})
    except Exception as ex: print('fundamental reference skipped:', ex)
    return ref

def test(days=21):
    c = pd.read_csv(NRG / 'stream_candidates.csv'); ref = ieso_ref()
    d1 = date.today() - timedelta(days=1); d0 = d1 - timedelta(days=days); rep = [f'NRG test {d0} .. {d1} vs IESO archive\n']; chosen = {}
    with Session() as s:
        for slot, g in c.groupby('slot', sort=False):
            best = None
            for r in g.itertuples():
                df, head = s.data(r.stream, d0, d1 + timedelta(days=1)); time.sleep(0.3)
                if df is None: rep.append(f'{slot:16s} {r.stream}: {head}'); continue
                h = hourly(df); R = ref.get(slot)
                if R is None or h.empty: rep.append(f'{slot:16s} {r.stream}: {len(h)} h, no reference'); continue
                m = h.merge(R, on=['date', 'he']).dropna()
                if m.empty: rep.append(f'{slot:16s} {r.stream}: {len(h)} h, no overlap. head: {head[:100]!r}'); continue
                tol = .05 if slot.endswith('_DA') else .5 if slot.endswith('_RT') else 25
                ok = ((m.value - m.ref).abs() <= tol).mean() * 100; mae = (m.value - m.ref).abs().mean()
                rep.append(f'{slot:16s} {r.stream}: {len(m)} h overlap, within tolerance {ok:.1f}%, MAE {mae:.3f}  [{r.name[:90]}]')
                if best is None or ok > best[1]: best = (r.stream, ok, len(m), r.name)
            if best and best[1] >= 95: chosen[slot] = dict(stream=int(best[0]) if str(best[0]).isdigit() else best[0], match_pct=round(best[1], 1), hours=best[2], name=best[3][:120])
    (NRG / 'streams_ontario.json').write_text(json.dumps(chosen, indent=1))
    rep.append(f'\nCHOSEN ({len(chosen)} of {c.slot.nunique()} slots matched IESO in >= 95% of hours):'); rep += [f'  {k}: {v["stream"]} ({v["match_pct"]}%, {v["hours"]} h)' for k, v in chosen.items()]
    missing = sorted(set(c.slot) - set(chosen)); rep.append(f'NOT MATCHED: {missing}' if missing else 'All slots matched.')
    (NRG / 'nrg_test_report.txt').write_text('\n'.join(rep)); print('\n'.join(rep)); print('\nNow tell Claude "nrg test done".')

def update(days=10):
    S = json.loads((NRG / 'streams_ontario.json').read_text()); d1 = date.today(); d0 = d1 - timedelta(days=days); cols = []
    with Session() as s:
        for slot, v in S.items():
            df, head = s.data(v['stream'], d0, d1 + timedelta(days=1)); time.sleep(0.3)
            if df is None: print(f'  {slot}: {head}'); continue
            cols.append(hourly(df).rename(columns={'value': slot}).set_index(['date', 'he']))
    new = pd.concat(cols, axis=1).reset_index(); p = NRG / 'nrg_daily.csv'
    if p.exists():
        old = pd.read_csv(p); old = old[~old.set_index(['date', 'he']).index.isin(new.set_index(['date', 'he']).index)]; new = pd.concat([old, new])
    new.sort_values(['date', 'he']).to_csv(p, index=False); print(f'nrg_daily.csv -> {new.date.max()}, {len(new):,} rows, {len(cols)} streams')

if __name__ == '__main__':
    a = sys.argv[1:]
    if '--discover' in a: discover()
    elif '--test' in a: test()
    elif '--update' in a: update()
    else: print(__doc__)
