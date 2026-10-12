"""practice_build.py -- Oct 9 2026: build the practice data (bid-time fundamentals only, no model signals) and Claude's framework
read per hour (written by fixed rules from the four questions -- never looks at prices after the bid), plus settled prices for the
DA View tab. Output: data/replay/practice_v2.json"""
import sys, json, glob, math; sys.path.insert(0, 'model')
import pandas as pd, numpy as np, spike_anatomy as SA
p = pd.read_csv('data/prices_hourly.csv'); p = p[p.zone.isin(['EAST', 'OTTAWA'])]
EXTRA = {('2026-10-09', 'EAST'): {9: (54.1, 75), 10: (62.9, 104), 11: (34.6, 97)}, ('2026-10-09', 'OTTAWA'): {9: (54.9, 77), 10: (64.0, 106), 11: (35.2, 99)}}
HOL = {'2026-09-07': 'Labour Day', '2026-10-12': 'Thanksgiving', '2026-10-10': 'Saturday of Thanksgiving weekend', '2026-10-11': 'Sunday of Thanksgiving weekend', '2026-09-05': 'Saturday of Labour Day weekend', '2026-09-06': 'Sunday of Labour Day weekend'}
def seg(he): return 'HE1-4' if he <= 4 else 'HE5-8' if he <= 8 else 'HE9-15' if he <= 15 else 'HE16-19' if he <= 19 else 'HE20-24'
def px(D, z, he):
    x = p[(p.date == D) & (p.zone == z) & (p.he == he)]
    da = None if x.empty or pd.isna(x.da.iloc[0]) else round(float(x.da.iloc[0]), 2)
    rt = None if x.empty or pd.isna(x.rt.iloc[0]) else round(float(x.rt.iloc[0]), 2)
    mx = None if x.empty or pd.isna(x.rt_max5.iloc[0]) else round(float(x.rt_max5.iloc[0]))
    e = EXTRA.get((D, z), {}).get(he)
    if e and rt is None: rt, mx = e
    return da, rt, mx
E = p[p.zone == 'EAST'].dropna(subset=['da', 'rt']).copy(); E['rd'] = E.rt - E.da
def lookback(D, he, k):
    """RT vs DA at this hour over the last k settled days known at the bid (D-2 back), East."""
    hi = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); lo = (pd.Timestamp(D) - pd.Timedelta(days=k + 2)).date().isoformat()
    x = E[(E.he == he) & (E.date <= hi) & (E.date > lo)]
    return (int((x.rd > 0).sum()), len(x), None if x.empty else round(float(x.rd.mean()), 1))
days = []
for f in sorted(glob.glob('data/replay/bundle_2026-*.json')):
    b = json.load(open(f)); D = b['target']; F = b.get('fund')
    if not F: continue
    rows = []
    for r in F['rows']:
        tg = None if r['tesla'] is None or r['dem'] is None else r['tesla'] - r['dem']
        rows.append(dict(he=r['he'], dem=r['dem'], tes=r['tesla'], dyn=r['dyn'], met=r['meteo_load'], tg=tg, w=r['wind'], wm=r['wind_meteo'], wlo=r['wind_nwp_min'], whi=r['wind_nwp_max'],
                         w3=r.get('wind3'), sol=r['solar'], nuc=r['nuc'], hyd=r['hydro_exp'], exp=None if r['net_exp'] is None else -r['net_exp'], res=r['resid'], gav=r['gas_av'],
                         need=r['gas_need'], sp=r['gas_spare'], r1=r['ramp1'], r1p=r['ramp1_pct'], r3=r['ramp3'], r3p=r['ramp3_pct'], head=r['head'], cahr=r['cahr'], daf=r['da_e'], vs=r.get('da_vs')))
    # ---- Claude's framework read (fixed rules; uses only the bid-time row values above) ----
    own = {}
    for r in rows:
        s = []
        if r['tg'] is not None and r['tg'] >= 150: s.append(f"load +{r['tg']:,}")
        if r['w3'] is not None and r['w3'] <= -200: s.append(f"wind {r['w3']:,}")
        if r['r3'] is not None and r['r3'] >= 500: s.append(f"gas ramp +{r['r3']:,}")
        own[r['he']] = s
    nwin = {h: max(len(own[h]), len(own.get(h - 1, []))) for h in own}
    for r in rows:
        he = r['he']; s = own[he]; n = nwin[he]; nb = max(nwin.get(he - 1, 0), nwin.get(he + 1, 0))
        rich = (r['cahr'] or 0) >= 10 or r['head'] < 7000 or (r['vs'] or 0) >= 10
        cheap = (r['cahr'] or 99) < 8.5 and (r['vs'] or 0) <= 0
        unsure = r['wlo'] is not None and r['whi'] is not None and r['w'] is not None and (r['whi'] - r['wlo']) >= 1000 and r['w'] >= r['wlo'] + 0.6 * (r['whi'] - r['wlo'])
        if n >= 2: call = 'LONG' if not rich else 'NO SHORT'
        elif rich and n == 0: call = 'SHORT'
        elif rich and n == 1: call = 'PASS' if nb >= 2 else 'SHORT SMALL'
        elif 7000 <= r['head'] <= 8500: call = 'PASS'
        elif cheap and n == 1: call = 'LONG SMALL'
        else: call = 'PASS'
        if unsure and call == 'SHORT': call = 'SHORT SMALL'
        mw = {'SHORT': -10, 'SHORT SMALL': -5, 'LONG': 10, 'LONG SMALL': 5}.get(call, 0)
        why = []
        if rich: why.append('DA rich (' + ', '.join(x for x in [f"CAHR {r['cahr']:.1f}" if (r['cahr'] or 0) >= 10 else '', f"headroom {r['head']:,}" if r['head'] < 7000 else '', f"{r['vs']:+.0f} vs usual" if (r['vs'] or 0) >= 10 else ''] if x) + ')')
        elif cheap: why.append(f"DA cheap (CAHR {r['cahr']:.1f})")
        else: why.append('DA not rich')
        if s: why.append('signs: ' + ', '.join(s))
        if len(own.get(he - 1, [])) > len(s): why.append(f"HE{he-1} had {len(own[he-1])} sign{'s' if len(own[he-1]) > 1 else ''}")
        if 7000 <= r['head'] <= 8500 and not rich: why.append('7,000-8,500 danger band')
        if unsure: why.append(f"wind models {r['wlo']:,}-{r['whi']:,}, IESO near top")
        r['my'] = dict(call=call, mw=mw, why='; '.join(why))
        r['b7'] = lookback(D, he, 7); r['b14'] = lookback(D, he, 14)
        for z, k in (('EAST', ''), ('OTTAWA', 'o')):
            da, rt, mx = px(D, z, he); r['da' + k] = da; r['rt' + k] = rt; r['mx' + k] = mx
    # segment summaries
    segs = []
    for sname in ('HE1-4', 'HE5-8', 'HE9-15', 'HE16-19', 'HE20-24'):
        g = [r for r in rows if seg(r['he']) == sname]; calls = {}
        for r in g: calls.setdefault(r['my']['call'], []).append(r['he'])
        ss = sorted({x for r in g for x in own[r['he']]}, key=lambda x: x)
        txt = ' · '.join(f"{c} HE{','.join(map(str, h))}" for c, h in calls.items())
        segs.append(dict(seg=sname, calls=txt, rich=sum(1 for r in g if r['my']['why'].startswith('DA rich')), signs=sum(1 for r in g if own[r['he']])))
    ss = SA.sunset_est(D)
    days.append(dict(date=D, hol=HOL.get(D, ''), sunset=f"{int(ss)}:{int((ss % 1) * 60):02d} EST (HE{int(math.floor(ss)) + 1})", pm=F.get('pm_ramp'), pmp=F.get('pm_ramp_pct'), am=F.get('am_ramp'), amp=F.get('am_ramp_pct'),
                     nuc=rows[0]['nuc'], meteo_missing=all(r['wm'] is None for r in rows), models_missing=all(r['wlo'] is None for r in rows), rows=rows, segs=segs))
json.dump(days, open('data/replay/practice_v2.json', 'w'), separators=(',', ':'))
for d in days[:2] + days[-3:]: print(d['date'], d['sunset'], d['hol'], [s['calls'] for s in d['segs']])
print(len(days), 'days')
