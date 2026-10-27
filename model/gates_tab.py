"""gates_tab.py -- Oct 26 2026. DISPLAY ONLY: the morning gate checks for an East trader, as one dict for the bundle (out['gates']).
Nothing here feeds the ladders. Everything is bid-time (D-1 morning) except the outcome columns of past days.

Gates (per hour where it applies):
  1 gas floor      gas expected online (need) < 2,000 / < 2,500 MW  -> gas not on the margin, RT tends to collapse under DA
  2 congestion     did yesterday's DA enforce an outage-specific FETT (West->Toronto) table?  closed = no spread trade.
                   open -> wind decides: IESO wind HE10-20 >= 2,000 go-with; < 1,300 and Meteologica lighter -> fade;
                   Meteologica windier by 75+ -> go-with lean; else pass.  (rule drawn from 13 open days: track live)
  3 spare / spike  need >= 6,000 with spare < 1,500
  4 gas shift      (Meteologica load - IESO load) + (IESO wind - Meteologica wind); + = more gas needed than IESO shows
  5 wind miss      Meteologica wind - IESO wind <= -300
  6 outage returns gas MW IESO assumes comes back on D (returns arrive on time ~40% of the time)
History tables are recomputed every morning from data/fund_history.json (bid-time reads) + East prices."""
import sys, io, json, contextlib; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent / 'congestion'))
import numpy as np, pandas as pd, common as C
J = lambda v, d=0: None if v is None or (isinstance(v, float) and np.isnan(v)) else (round(float(v), d) if d else int(round(float(v))))
SHIFT_BINS = [-9e9, -600, -400, -200, 200, 400, 9e9]
SHIFT_LBL = ['≤ −600', '−600 to −400', '−400 to −200', '−200 to +200', '+200 to +400', '≥ +400']

def shift_band(s):
    if s is None: return None
    return 'strong bear' if s <= -400 else 'mild bear' if s <= -200 else 'strong bull' if s >= 400 else 'neutral'

def hist_frame(D):
    """bid-time fundamentals (fund_history.json) joined to East DA/RT, delivery days before D."""
    d = json.loads((C.DATA / 'fund_history.json').read_text())
    f = pd.DataFrame([dict(date=k, **x) for k, v in d.items() if k < D for x in v])
    p = pd.read_csv(C.DATA / 'prices_hourly.csv'); p = p[p.zone == 'EAST'][['date', 'he', 'da', 'rt']]
    f = f.merge(p, on=['date', 'he']).dropna(subset=['rt', 'da'])
    f['x'] = f.rt - f.da; f['shift'] = (f.met - f.dem) + (f.w - f.wm); f['wgap'] = f.wm - f.w
    return f

def st(v):
    v = v.dropna()
    return dict(hrs=int(len(v)), avg=J(v.mean(), 1) if len(v) else None, med=J(v.median(), 1) if len(v) else None, up=J((v > 0).mean() * 100) if len(v) else None,
                spike=J((v > 25).mean() * 100) if len(v) else None)

def hist_tables(f):
    out = {'from': f.date.min(), 'to': f.date.max(), 'days': int(f.date.nunique())}
    s = f.dropna(subset=['shift']); b = pd.cut(s['shift'], SHIFT_BINS, labels=SHIFT_LBL)
    out['shift'] = [dict(bin=k, **st(g.x)) for k, g in s.groupby(b, observed=False)]
    hg = s[s.need >= 6000]; b2 = pd.cut(hg['shift'], SHIFT_BINS, labels=SHIFT_LBL)
    out['shift_highgas'] = [dict(bin=k, **st(g.x)) for k, g in hg.groupby(b2, observed=False)]
    out['floor'] = [dict(bin='need < 2,000', **st(f[f.need < 2000].x)), dict(bin='2,000–2,500', **st(f[f.need.between(2000, 2500)].x)),
                    dict(bin='≥ 2,500', **st(f[f.need > 2500].x))]
    out['tight'] = [dict(bin='need ≥ 6,000 & spare < 1,500', **st(f[(f.need >= 6000) & (f.sp < 1500)].x)),
                    dict(bin='need ≥ 6,000 & spare ≥ 1,500', **st(f[(f.need >= 6000) & (f.sp >= 1500)].x)),
                    dict(bin='need < 6,000', **st(f[f.need < 6000].x))]
    w = f.dropna(subset=['wgap'])
    out['wind'] = [dict(bin='Meteologica ≤ −300 vs IESO', **st(w[w.wgap <= -300].x)), dict(bin='−300 to +300', **st(w[w.wgap.between(-300, 300)].x)),
                   dict(bin='Meteologica ≥ +300 vs IESO', **st(w[w.wgap >= 300].x))]
    return out

def hour_rows(fund):
    rows = []
    for r in fund['prac']['rows']:
        met, dem, w, wm, need, sp = (r.get(k) for k in ('met', 'dem', 'w', 'wm', 'need', 'sp'))
        lg = None if met is None or dem is None else met - dem
        wg = None if w is None or wm is None else wm - w
        sh = None if lg is None or wg is None else lg - wg
        fl = []
        if need is not None and need < 2000: fl.append(('floor', 'bear', 'Gas < 2,000: not on the margin'))
        elif need is not None and need < 2500: fl.append(('floor', 'bear', 'Gas < 2,500: weak price-setter'))
        if need is not None and sp is not None and need >= 6000 and sp < 1500: fl.append(('tight', 'warn', f'Spare {sp:,}: DA rich, spike tail'))
        if sh is not None and sh <= -400: fl.append(('shift', 'bear', f'Shift {sh:+,}: strong bear'))
        elif sh is not None and sh <= -200: fl.append(('shift', 'bear', f'Shift {sh:+,}: mild bear'))
        elif sh is not None and sh >= 400: fl.append(('shift', 'bull', f'Shift {sh:+,}: bull lean'))
        elif sh is not None and need is not None and need >= 6000 and 0 < sh < 200: fl.append(('shift', 'warn', f'Shift {sh:+,}, high gas: spike-prone'))
        if wg is not None and wg <= -300: fl.append(('wind', 'bull', f'Meteologica {wg:+,} MW wind: miss risk'))
        elif wg is not None and wg >= 300: fl.append(('wind', 'bear', f'Meteologica {wg:+,} MW wind: extra cushion'))
        bull = sum(1 for x in fl if x[1] == 'bull'); bear = sum(1 for x in fl if x[1] == 'bear')
        rows.append(dict(he=r['he'], dem=dem, met=met, lgap=lg, w=w, wm=wm, wgap=wg, shift=sh, band=shift_band(sh), need=need, sp=sp,
                         lean='bull' if bull > bear else 'bear' if bear > bull else 'neutral', flags=[dict(k=a, tone=b, text=c) for a, b, c in fl]))
    return rows

# ---------------- congestion ----------------
def cong_call(gate, w_ieso, w_met):
    if not gate: return 'pass', 'Gate closed: DA used normal limits, the East–West split averages about $2. No spread trade.'
    if w_ieso is not None and w_ieso >= 2000: return 'go-with', f'Gate open and IESO wind {w_ieso:,.0f} MW ≥ 2,000: more power trapped west, split widens.'
    if w_ieso is not None and w_met is not None and w_ieso < 1300 and w_met < w_ieso: return 'fade', f'Gate open, wind {w_ieso:,.0f} MW < 1,300 and Meteologica lighter ({w_met:,.0f}): split tends to collapse.'
    if w_ieso is not None and w_met is not None and w_met - w_ieso >= 75: return 'go-with', f'Gate open, Meteologica windier by {w_met - w_ieso:,.0f} MW: go-with lean.'
    return 'pass', 'Gate open but wind is in between: no edge.'

def wind_mid(rows, k):
    v = [r[k] for r in rows if 10 <= r['he'] <= 20 and r.get(k) is not None]
    return float(np.mean(v)) if v else None

def congestion(D, fund_rows):
    with contextlib.redirect_stdout(io.StringIO()):
        import cong_read as R
        rd = R.read(D, write=True)
    dc = rd.get('da_constraints') or {}
    gate = bool(dc.get('fett_outage_table'))
    wi, wm = wind_mid(fund_rows, 'w'), wind_mid(fund_rows, 'wm')
    call, why = cong_call(gate, wi, wm)
    S = R.price_frame()
    S['W_go'] = (-S.WEST_rt) - (-S.WEST_da); S['SW_go'] = (-S.SOUTHWEST_rt) - (-S.SOUTHWEST_da)
    hist = json.loads((C.DATA / 'fund_history.json').read_text())
    days = sorted({n[-12:-4] for z in sorted((C.ROOT / 'archive' / 'DASecurityConstraints2').glob('*.zip')) for n in __import__('zipfile').ZipFile(z).namelist()})
    log = []
    for d8 in days:                                   # file d8 = DA for delivery d8 -> gate for delivery d8+1
        X = (pd.Timestamp(d8) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        if X >= D: continue
        c = R.da_constraints(X) or {}; g = bool(c.get('fett_outage_table'))
        s = S[(S.date == X) & S.he.between(10, 20)]
        if s.WEST_rt.isna().all(): continue
        fr = [dict(he=x['he'], w=x.get('w'), wm=x.get('wm')) for x in hist.get(X, [])]
        a, b = wind_mid(fr, 'w'), wind_mid(fr, 'wm'); cl, _ = cong_call(g, a, b)
        wgo = s.W_go.mean(); swgo = s.SW_go.mean()
        res = None if cl == 'pass' else (wgo if cl == 'go-with' else -wgo)
        log.append(dict(date=X, gate=g, table=', '.join(c.get('fett_outage_table') or []), wind=J(a), wmet=J(b), call=cl,
                        da_split=J(-s.WEST_da.mean(), 1), rt_split=J(-s.WEST_rt.mean(), 1), go_west=J(wgo, 1), go_sw=J(swgo, 1), pnl=J(res, 1)))
    L = pd.DataFrame(log)
    gs = []
    for k, g in (('Gate closed', L[~L.gate]), ('Gate open', L[L.gate])) if len(L) else ():
        gs.append(dict(state=k, days=int(len(g)), da=J(g.da_split.mean(), 1), rt=J(g.rt_split.mean(), 1)))
    tr = L[L.call != 'pass'] if len(L) else L
    rule = dict(days=int(len(tr)), wins=int((tr.pnl > 0).sum()) if len(tr) else 0, avg=J(tr.pnl.mean(), 1) if len(tr) else None)
    south_out = [dict(tag=o['tag'], start=o['start'][:16], end=o['end'][:16], equip=o['equip'][:80], where=o['where'], long=o['long'])
                 for o in rd.get('outages', []) if any(t in (o.get('where') or '') for t in ('(W)', '(SW)', 'Bruce', '(TOR)'))]
    lim = [dict(iface=l['iface'], limit=J(l['limit']), ais=J(l['ais']), hours=l['hours'], why=l['why'][:80]) for l in rd.get('limits', []) if l.get('south')]
    return dict(gate=gate, tables=dc.get('fett_outage_table') or [], south_families=dc.get('south') or {}, call=call, why=why,
                wind_ieso=J(wi), wind_met=J(wm), episode_day=rd.get('episode_day'), recent=rd.get('recent'), outages=south_out, limits=lim,
                gate_stats=gs, rule=rule, log=log[::-1], dc_known=bool(rd.get('da_constraints')))

def outage_gate(ob):
    try:
        d = ob['returns']['day']; ev = [e for e in d['events'] if e['fuel'] == 'Gas']
        back = sum(e['mw'] for e in ev if e['kind'] == 'back'); rel = d['rel']['Gas']
        return dict(back=back, out=sum(e['mw'] for e in ev if e['kind'] == 'out'), events=ev, ontime=rel.get('back_ontime'), byend=rel.get('back_byend'),
                    big=back >= 300, he1=d['totals']['Gas']['he1'], today_he24=d.get('today_he24'))
    except Exception: return None

def build(D, out):
    fund = out['fund']; rows = hour_rows(fund)
    H = hist_frame(D); tables = hist_tables(H)
    try: cg = congestion(D, rows)
    except Exception as ex: cg = dict(error=str(ex))
    og = outage_gate(out.get('outages') or {})
    blk = {'HE1–4': range(1, 5), 'HE5–8': range(5, 9), 'HE9–15': range(9, 16), 'HE16–19': range(16, 20), 'HE20–24': range(20, 25)}
    blocks = []
    for k, hs in blk.items():
        g = [r for r in rows if r['he'] in hs]
        m = lambda c: J(np.mean([r[c] for r in g if r[c] is not None])) if any(r[c] is not None for r in g) else None
        blocks.append(dict(blk=k, need=m('need'), sp_min=min((r['sp'] for r in g if r['sp'] is not None), default=None), shift=m('shift'),
                           bull=sum(r['lean'] == 'bull' for r in g), bear=sum(r['lean'] == 'bear' for r in g)))
    floor_hrs = [r['he'] for r in rows if r['need'] is not None and r['need'] < 2500]
    tight_hrs = [r['he'] for r in rows if r['need'] is not None and r['sp'] is not None and r['need'] >= 6000 and r['sp'] < 1500]
    bear_hrs = [r['he'] for r in rows if r['shift'] is not None and r['shift'] <= -400]
    bull_hrs = [r['he'] for r in rows if r['shift'] is not None and r['shift'] >= 400]
    wmiss = [r['he'] for r in rows if r['wgap'] is not None and r['wgap'] <= -300]
    wplus = [r['he'] for r in rows if r['wgap'] is not None and r['wgap'] >= 300]
    T = {x['bin']: x for x in tables['tight']}['need ≥ 6,000 & spare < 1,500']; W = {x['bin']: x for x in tables['wind']}
    Fl = {x['bin']: x for x in tables['floor']}['need < 2,000']
    hh = lambda L: ', '.join(f'HE{h}' for h in L) if L else 'none'
    summ = [dict(gate='1 Gas floor', tone='bear' if floor_hrs else 'neutral', status='ON' if floor_hrs else 'off',
                 text=(f"Gas expected < 2,500 MW in {hh(floor_hrs)}: gas is not reliably setting the price; only short (need < 2,000 history: RT−DA {Fl['avg']:+}, up {Fl['up']}%)." if floor_hrs else 'Gas expected ≥ 2,500 MW all day: gas is on the margin.')),
            dict(gate='2 Congestion', tone='info' if not cg.get('gate') else 'bull', status='OPEN' if cg.get('gate') else 'CLOSED',
                 text=(cg.get('why') or cg.get('error', ''))),
            dict(gate='3 Spare / spike', tone='warn' if tight_hrs else 'neutral', status=f'{len(tight_hrs)} h' if tight_hrs else 'off',
                 text=(f"High gas with spare < 1,500 in {hh(tight_hrs)}. History: DA prices these rich (median RT−DA {T['med']:+}, RT above DA {T['up']}%) but {T['spike']}% of hours spike $25+. Size small either way."
                       if tight_hrs else 'No high-gas / thin-spare hours.')),
            dict(gate='4 Gas shift', tone='bear' if len(bear_hrs) > len(bull_hrs) else 'bull' if bull_hrs else 'neutral',
                 status=f'{len(bear_hrs)} bear / {len(bull_hrs)} bull',
                 text=f'Strong bear (≤ −400) in {hh(bear_hrs)}; bull lean (≥ +400) in {hh(bull_hrs)}.'),
            dict(gate='5 Wind miss', tone='bull' if len(wmiss) > len(wplus) else 'bear' if wplus else 'neutral', status=f'{len(wmiss)} light / {len(wplus)} windy',
                 text=(f"Meteologica ≥ 300 MW lighter in {hh(wmiss)} (history RT−DA {W['Meteologica ≤ −300 vs IESO']['avg']:+}, spike {W['Meteologica ≤ −300 vs IESO']['spike']}%); "
                       f"≥ 300 MW windier in {hh(wplus)} (history {W['Meteologica ≥ +300 vs IESO']['avg']:+}, up {W['Meteologica ≥ +300 vs IESO']['up']}%).") if (wmiss or wplus) else 'Meteologica and IESO within 300 MW on wind all day.'),
            dict(gate='6 Gas returns', tone='bull' if og and og['big'] else 'neutral', status=f"{og['back']:,} MW" if og else 'n/a',
                 text=(f"IESO assumes {og['back']:,} MW of gas returns on D; gas returns arrive on time {og['ontime']}% of the time. A slip leaves gas short (bullish)." if og and og['back']
                       else 'No gas returns scheduled on D.' if og else 'Outage data missing.'))]
    return dict(date=D, summary=summ, hours=rows, blocks=blocks, hist=tables, cong=cg, outage=og)

if __name__ == '__main__':
    b = json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text())
    g = build(b['target'], b)
    for s in g['summary']: print(f"{s['gate']:16s} {s['status']:14s} {s['text']}")
    print('cong:', {k: g['cong'].get(k) for k in ('gate', 'call', 'wind_ieso', 'wind_met', 'gate_stats', 'rule')})
    for r in g['cong'].get('log', [])[:40]: print(r)
    print(json.dumps(g['hist']['shift'], ensure_ascii=False)); print(g['hist']['floor']); print(g['hist']['tight']); print(g['hist']['wind'])
