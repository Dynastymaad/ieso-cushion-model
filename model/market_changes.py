"""market_changes.py -- Nov 5 2026 (trimmed same day: only items that change what IESO publishes before the bid AND were tested, or are major supply events). 'Market changes' banner for the top of the Fundamentals tab (display only, no ladder or read effect).
Flags structural shifts that the read does not see, using only what is known at the D-1 bid:
  export / import capability   IESO pre-DA intertie limits for D vs the median of the last 30 days
  nuclear / gas / hydro available   IESO pre-DA Adequacy for D vs the median of the same hours over the last 30 days
  hydro output, actual exports  last 3 settled days (through D-2) vs the 30 days before
  hidden cushion                spare that will likely exist vs public spare: yesterday's DA export schedule + each hour's
                                trailing-30-day gas miss (tested Jul-Nov 2026: bias +661 -> -23 MW, miss 928 -> 712 MW)
  wind regime                   IESO wind forecast for D vs the last 14 days
Each item says which way it pushes RT vs DA. Thresholds are fixed rules of thumb, not fitted."""
import sys, json, time; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C

def _days(D, n, lag=1):
    end = pd.Timestamp(D) - pd.Timedelta(days=lag); return [(end - pd.Timedelta(days=i)).date().isoformat() for i in range(n)]


TIE_LINES = {'New York': r'^(PA27|PA301|PA302|BP76|L33P|L34P)\b|^NY NIAGARA', 'Michigan': r'^(J5D|L4D|L51D|B3N)\b',
             'Quebec': r'^(D4Z|D5A|H4Z|H9A|P33C|Q4C|X2Y|B5D|B31L|A41T|A42T)\b|OUTAOUAIS'}
def tie_outages(D, ahead=21):
    """Nov 5 2026: planned / in-progress outages on intertie lines from IESO's TxOutagesTodayAll + TxOutages1to30DaysPlanned
    (newest file of each, both published before 07:00 your time). Returns {intertie: [(code, start, end, status)]}."""
    import zipfile, re, glob
    recs = {}
    for rep in ('TxOutages1to30DaysPlanned', 'TxOutagesTodayAll'):          # TodayAll last: its end times are the most current
        zs = sorted(glob.glob(str(C.ARCH / rep / f'{rep}_*.zip')))[-2:]
        names = []
        for zp in zs:
            with zipfile.ZipFile(zp) as zf: names += [(n, zp) for n in zf.namelist()]
        if not names: continue
        n, zp = sorted(names)[-1]
        with zipfile.ZipFile(zp) as zf: t = zf.read(n).decode('utf8', 'replace')
        for r in re.findall(r'<OutageRequest>(.*?)</OutageRequest>', t, re.S):
            g = lambda tag: (re.search(f'<{tag}>([^<]*)</{tag}>', r) or [None, ''])[1]
            st = g('OutageRequestStatus')
            if st not in ('IMPL', 'AA', 'FA', 'SUB', 'STDY'): continue   # SUB / STDY = requested, not yet approved
            eq = [(e, c) for e, c in re.findall(r'<EquipmentName>([^<]*)</EquipmentName>.*?<ConstraintType>([^<]*)</ConstraintType>', r, re.S) if c == 'OOS']
            recs[g('OutageID')] = (g('PlannedStart'), g('PlannedEnd'), st, [e for e, _ in eq])
    end_win = (pd.Timestamp(D) + pd.Timedelta(days=ahead)).isoformat()
    out = {}
    for oid, (a, b, st, eqs) in recs.items():
        if not a or not b or b < D or a > end_win: continue
        for tie, pat in TIE_LINES.items():
            codes = sorted({re.split(r'[ .:]', e)[0] if not e.startswith('NY NIAGARA') else 'NY Niagara breakers' for e in eqs if re.search(pat, e)})
            if codes: out.setdefault(tie, []).append((', '.join(codes), a, b, st))
    for k in out: out[k] = sorted(set(out[k]), key=lambda x: (x[2], x[1]))
    return out

def build(D):
    items = []
    add = lambda lvl, push, title, detail, **k: items.append(dict(level=lvl, push=push, title=title, detail=detail, **k))
    # 1. intertie limits (pre-DA, known at the bid). N = export (out of Ontario), X = import
    try:
        L = pd.read_csv(C.DATA / 'ieso_preda_intertie_limits.csv'); L['mw'] = L.mw.abs()
        L = L[~L.zone.str.contains(r'\+')]
        def side(suf, cap):
            z = L[L.zone.str.endswith(suf)].copy(); z['grp'] = z.zone.str[:2].map({'NY': 'New York', 'MI': 'Michigan', 'PQ': 'Quebec', 'MB': 'Manitoba', 'MN': 'Minnesota'})
            t = z.groupby(['date', 'he', 'grp']).mw.sum().clip(upper=cap).groupby(['date', 'grp']).mean().unstack()
            return t
        for suf, word, push in (('N', 'Export', 'bearish'), ('X', 'Import', 'bullish')):
            t = side(suf, 2500)
            if D not in t.index: continue
            base = t.loc[[d for d in t.index if d < D][-30:]].median(); now = t.loc[D]
            dl = (now - base).dropna(); tot = dl[['New York', 'Michigan', 'Quebec']].sum() if set(['New York', 'Michigan', 'Quebec']) <= set(dl.index) else dl.sum()
            cut = dl[dl <= -250]
            if tot <= -400 or (dl <= -500).any():   # small single-interface wiggles are noise
                parts = ', '.join(f'{k} {base[k]:,.0f} → {now[k]:,.0f}' for k in cut.index)
                since = ''
                for k in cut.index:
                    s = t[k][t.index <= D]; run = s[::-1]; n = 0
                    for v in run.values:
                        if v <= base[k] - 250: n += 1
                        else: break
                    since += f' {k} cut {n} day(s) in a row.'
                add('major' if tot <= -500 else 'watch', push,
                    f'{word} capability cut {abs(tot):,.0f} MW vs normal',
                    (f'{parts} MW (D vs 30-day median).' + since +
                     (' Surplus cannot leave Ontario: overnight and valley RT sinks toward the floor, more so with wind 2,000+. Aug 29-Nov 5: with total export limit under 4,000 MW, '
                      'overnight RT was under $25 in 12-16% of hours (6% normally), median RT-DA -$4 to -$5 (69 days of limit data, still building).' if word == 'Export' else
                      ' Less import help: tighter if load or wind miss.')), mw=round(float(tot)))
    except Exception as ex: print('market changes: limits skipped', ex)
    # 2. availability from pre-DA Adequacy (one bid-time vintage per day)
    try:
        a = C.adq2('preDA'); a['date'] = a.date.astype(str); a['hyd_av2'] = a.hyd_cap - a.hyd_out
        cur = a[a.date == D]; prev = a[a.date.isin(_days(D, 30, 1))]
        for col, lab, thr, push_dn in (('nuc_av', 'Nuclear available', 400, 'bullish'), ('gas_av', 'Gas available', 1000, 'bullish'), ('hyd_av2', 'Hydro available', 1000, 'bullish')):
            if cur.empty or prev.empty: break
            now, base = cur[col].mean(), prev.groupby('date')[col].mean().median(); d = now - base
            if abs(d) >= thr:
                dn = d < 0
                add('major' if col == 'nuc_av' or abs(d) >= 1.5 * thr else 'watch', push_dn if dn else ('bearish' if push_dn == 'bullish' else 'bullish'),
                    f'{lab} {"down" if dn else "up"} {abs(d):,.0f} MW vs the last 30 days',
                    f'{base:,.0f} → {now:,.0f} MW for {D} (IESO pre-DA). ' + ('Less supply: tighter.' if dn else 'More supply: softer.') + ' Context, not an edge: DA prices it (Jun 2025-Nov 2026, days with availability moves like this had RT-DA within $3 of normal).', mw=round(float(d)), tested='context')
    except Exception as ex: print('market changes: adequacy skipped', ex)
    # 5. wind regime
    try:
        a = C.adq2('preDA'); a['date'] = a.date.astype(str)
        w = a[a.date == D].wind_fc.mean(); w14 = a[a.date.isin(_days(D, 14, 1))].wind_fc.mean()
        if w14 - w >= 1000:
            add('major', 'bullish', f'Wind {w14 - w:,.0f} MW below the last 2 weeks',
                f'IESO wind for {D} averages {w:,.0f} MW vs {w14:,.0f}. Tested Jun 2025-Nov 2026: on days like this RT spiked $50+ over DA in 15% of hours, about double normal (7%). The median hour is still short: size longs for the spike, not the average.', mw=round(float(w - w14)), tested='spikes x2')
    except Exception as ex: print('market changes: wind skipped', ex)
    # 1b. pre-DA limits for D post ~09:08 EST (08:08 your time): before that, use IESO's transmission limits report (0-2 days, refreshed through the night)
    try:
        if not any(i['title'].startswith('Export capability') for i in items):
            f = C.DATA / 'congestion' / f'read_{D}.json'
            L = pd.read_csv(C.DATA / 'ieso_preda_intertie_limits.csv'); have_D = (L.date == D).any()
            if f.exists() and not have_D:
                r = json.loads(f.read_text()); lim = {}
                for x in r.get('limits', []):
                    if x.get('fac') == 'Intertie' and 'Export' in x['iface'] and x['iface'].startswith('Ontario-'):
                        k = x['iface']; lim[k] = min(lim.get(k, (9e9, ''))[0], x['limit']), x['why']
                L['mw'] = L.mw.abs(); base = L[(L.zone == 'NYSIN') & (L.date < D)].groupby('date').mw.mean().tail(30).median()
                ny = lim.get('Ontario-New York Export'); pq = {k: v for k, v in lim.items() if 'Quebec' in k}
                if (ny and ny[0] <= base - 400) or pq:
                    parts = ([f"New York export {ny[0]:,.0f} MW vs normal {base:,.0f} ({ny[1]})"] if ny else []) + [f"{k.replace('Ontario-Quebec ', 'Quebec ')} {v[0]:,.0f} MW ({v[1]})" for k, v in pq.items()]
                    add('major', 'bearish', 'Export capability cut (early read)', '; '.join(parts) + '. From IESO\'s transmission limits report: the pre-DA intertie limits for D post about 08:08 your time and replace this on the late run. '
                        'Surplus cannot leave Ontario: overnight and valley RT sinks toward the floor, more so with wind 2,000+.', mw=-500)
    except Exception as ex: print('market changes: early limits skipped', ex)
    # 7. what is coming on the interties (planned outage start / end dates, next 21 days)
    try:
        T = tie_outages(D)
        if T:
            fmt = lambda x: pd.Timestamp(x).strftime('%b %d %H:%M').replace(' 00:00', '')
            lines = []
            for tie in ('New York', 'Quebec', 'Michigan'):
                now_, later = {}, []
                for code, a_, b_, st in T.get(tie, []):
                    if pd.Timestamp(b_) - pd.Timestamp(a_) < pd.Timedelta(hours=6): continue          # short switching jobs are noise
                    if a_ <= D: now_[code] = max(now_.get(code, ''), b_)
                    else: later.append(f"{code} {fmt(a_)} → {fmt(b_)}" + (' (requested, not yet approved)' if st in ('SUB', 'STDY') else ''))
                bits = [f"{c} out until {fmt(e)}" for c, e in sorted(now_.items(), key=lambda kv: kv[1])] + [f"then {x}" for x in later]
                if bits: lines.append(f"<b>{tie}</b>: " + ' · '.join(bits))
            add('watch', 'info', 'Intertie outages: when they start and end', '<br>'.join(lines) + '<br>IESO planned dates (can move); the export-capability line above shows what is actually in force each morning.', mw=0)
    except Exception as ex: print('market changes: tie outages skipped', ex)
    # 8. generation outages: what goes out / comes back in the next 3 weeks (IESO 35-day schedule, newest snapshot) + nuclear units out now
    try:
        F = pd.read_csv(C.DATA / 'fwd35.csv'); F = F[F.snapshot == F.snapshot.max()]
        g = F.groupby('date')[['nuclear_out', 'gas_out']].max().sort_index()
        g = g[(g.index >= D) & (g.index <= (pd.Timestamp(D) + pd.Timedelta(days=21)).date().isoformat())]
        ev = []
        for col, lab in (('nuclear_out', 'Nuclear'), ('gas_out', 'Gas')):
            if col not in g: continue
            v = g[col].round(-1); ch = v.diff()
            for d_, c_ in ch[ch.abs() >= (300 if col == 'nuclear_out' else 600)].items():   # gas schedules wobble day to day
                ev.append((d_, f"{lab} {'back' if c_ < 0 else 'out'} {abs(c_):,.0f} MW from {pd.Timestamp(d_).strftime('%b %d')} (out {v.shift(1)[d_]:,.0f} → {v[d_]:,.0f})"))
        try:
            import outages_tab as OT
            uo, asof = OT.units_out(); nu = [f"{u['unit']} {u['out']:,.0f}" for u in uo if u.get('fuel') == 'Nuclear']
        except Exception: nu = []
        if ev or nu:
            add('watch', 'info', 'Generation outages: what is out and what changes next',
                ('Nuclear units out now: ' + ', '.join(nu) + '.<br>' if nu else '') + ('<br>'.join(e for _, e in sorted(ev)) + '<br>' if ev else 'No nuclear or gas step of 300+ MW in the next 3 weeks.<br>') +
                'IESO 35-day schedule (peak hour, MW out). Planned dates can move; tomorrow\'s exact numbers are in the nuclear / gas lines above when they change.', mw=0)
    except Exception as ex: print('market changes: generation outages skipped', ex)
    # 9. exports today: the export floor (NY DA in CAD minus the ~$13 exporters need) vs our Ontario DA forecast, modelled exports vs usual, export room
    try:
        X = pd.read_csv(C.DATA / 'export_hat.csv'); X = X[X.date == D]
        if len(X) and X.ny_cad.notna().any():
            X = X.assign(flr=X.ny_cad - 13, ont=X.ny_cad - X.spr, xsh=X.exp_exp - X.exp_hat)
            parts = []
            for lab, a_, b_ in (('Overnight HE1-6', 1, 6), ('Valley HE9-15', 9, 15), ('Evening HE16-21', 16, 21)):
                g = X[X.he.between(a_, b_)]
                if not len(g): continue
                parts.append(f"<b>{lab}</b>: floor ${g.flr.mean():,.0f} vs our DA ${g.ont.mean():,.0f} · exports {g.exp_hat.mean():,.0f} MW modelled vs {g.exp_exp.mean():,.0f} usual"
                             + (f" ({'short' if g.xsh.mean() > 0 else 'above'} {abs(g.xsh.mean()):,.0f})" if abs(g.xsh.mean()) >= 250 else '') + f" · export limit {g.exp_lim.mean():,.0f}")
            pts = int((X.xsh >= 500).sum()); ptu = int((X.xsh <= -500).sum())
            side = 'above' if X.spr.mean() >= 0 else 'below'
            push = 'bearish' if X.spr.mean() <= -10 else 'bullish' if X.spr.mean() >= 10 else 'info'
            add('watch', push, f"Exports: NY ${abs(X.spr.mean()):,.0f} {side} our Ontario DA forecast (CAD, day average)" + (f" · card −1 in {pts} h" if pts else '') + (f" · card +1 in {ptu} h" if ptu else ''),
                '<br>'.join(parts) + '<br>Floor = where exporters start buying Ontario power (NY minus about $13). Our DA well above the floor = exports will not rescue a loose day (price has room to fall). DA at or near the floor = exporters step in and price cannot fall much further.', mw=0)
    except Exception as ex: print('market changes: exports skipped', ex)
    items.sort(key=lambda x: (x['level'] != 'major', -abs(x.get('mw', 0))))
    asof = time.strftime('%b %d %H:%M')
    try: adqv = str(C.adq2('preDA').pipe(lambda a: a[a.date.astype(str) == D]).shape[0] and pd.read_csv(C.CACHE / 'ieso_adq2_preDA.csv', usecols=['date', 'ieso_createtime']).query('date == @D').ieso_createtime.max())[5:16] + ' EST'
    except Exception: adqv = '?'
    return dict(date=D, asof=asof, adq=adqv, items=items)

if __name__ == '__main__':
    D = sys.argv[1] if len(sys.argv) > 1 else json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text())['target']
    for i in build(D)['items']: print(f"[{i['level']:5s}] {i['push']:7s} {i['title']}\n         {i['detail']}")
