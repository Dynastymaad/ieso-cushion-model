"""
nrg_probe.py -- LIGHT probe of NRGStream (Arcobi) for Ontario history.

What it does (read-only, ~1-3 minutes):
  1. gets an API token with YOUR login, read from nrg.json in this folder (never printed, never saved elsewhere)
  2. downloads the stream catalogue (StreamList) -> out_nrg/stream_list.csv
  3. picks the Ontario / IESO streams (hub prices, OZP, interties, wind/solar forecasts, demand, ...)
  4. for each, pulls two tiny windows (1 day in Jun 2025, 1 day last week) to prove how far back it goes
  5. releases the token (NRGStream allows one live token per login)

Setup once:  copy nrg.example.json to nrg.json and fill in username / password.
             nrg.json is in .gitignore -- it never goes to GitHub.
Run:         python nrg_probe.py
Then tell Claude "nrg probe finished".
"""
import json, re, sys, time, csv, io, urllib.request, urllib.parse, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out_nrg'; OUT.mkdir(exist_ok=True)
BASE = 'https://api.nrgstream.com'
LOG = open(OUT / '_summary.txt', 'w', encoding='utf-8')
PAT = re.compile(r'ontario|ieso|toronto|south ?west|\bozp\b|hoep|zonal|virtual|intertie|michigan|new york|quebec|manitoba|minnesota|'
                 r'\bont\b|\bon\b|adequacy|wind|solar|demand|load|outage|nuclear|hydro|gas|lennox|shadow|limit', re.I)
ONT = re.compile(r'ontario|ieso|toronto|south ?west|\bozp\b|hoep|\bont\b', re.I)
WINDOWS = [('06/01/2025', '06/02/2025'), ('09/20/2026', '09/21/2026')]
MAX_STREAMS = 120

def log(s=''):
    print(s, flush=True); LOG.write(s + '\n'); LOG.flush()

def req(method, path, token=None, data=None, accept='application/json', timeout=60):
    h = {'Accept': accept}
    if token: h['Authorization'] = f'Bearer {token}'
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode(); h['Content-Type'] = 'application/x-www-form-urlencoded'
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')

def main():
    cfgp = HERE / 'nrg.json'
    if not cfgp.exists(): raise SystemExit('nrg.json not found -- copy nrg.example.json to nrg.json and add your NRGStream login')
    cfg = json.loads(cfgp.read_text())
    st, txt = req('POST', '/api/security/token', data={'grant_type': 'password', 'username': cfg['username'], 'password': cfg['password']})
    if st != 200: raise SystemExit(f'login failed ({st}): {txt[:200]}')
    token = json.loads(txt)['access_token']; log('token OK')
    try:
        st, txt = req('GET', '/api/StreamList', token)
        log(f'StreamList: HTTP {st}, {len(txt):,} bytes')
        if st != 200: log(txt[:500]); return
        streams = json.loads(txt)
        if isinstance(streams, dict): streams = next((v for v in streams.values() if isinstance(v, list)), [])
        keys = sorted({k for s in streams for k in s})
        with open(OUT / 'stream_list.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(streams)
        log(f'  {len(streams):,} streams, fields: {keys}')
        text = lambda s: ' | '.join(str(v) for v in s.values())
        ont = [s for s in streams if ONT.search(text(s))]
        log(f'  Ontario/IESO-looking streams: {len(ont)}')
        with open(OUT / 'stream_list_ontario.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(ont)
        idk = next((k for k in keys if k.lower() in ('streamid', 'stream_id', 'id')), keys[0])
        pick = [s for s in ont if PAT.search(text(s))][:MAX_STREAMS]
        res = []
        for i, s in enumerate(pick):
            sid = s[idk]; row = {'streamId': sid, 'name': text(s)[:160]}
            for k, (a, b) in enumerate(WINDOWS):
                q = f'/api/StreamData/{sid}?fromDate={urllib.parse.quote(a)}&toDate={urllib.parse.quote(b)}'
                st, body = req('GET', q, token, accept='text/csv', timeout=90)
                lines = [l for l in body.splitlines() if l.strip()]
                row[f'w{k}_status'] = st; row[f'w{k}_lines'] = len(lines)
                row[f'w{k}_head'] = ' || '.join(lines[:4])[:400]
                time.sleep(0.3)
            res.append(row); log(f'  [{i+1}/{len(pick)}] {sid}: jun-2025 {row["w0_status"]}/{row["w0_lines"]} lines, sep-2026 {row["w1_status"]}/{row["w1_lines"]} lines  {row["name"][:80]}')
        with open(OUT / 'stream_samples.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(res[0]) if res else ['streamId']); w.writeheader(); w.writerows(res)
    finally:
        st, _ = req('DELETE', '/api/ReleaseToken', token); log(f'token released ({st})')
    log('\nDone. Tell Claude "nrg probe finished".')

if __name__ == '__main__':
    main()
