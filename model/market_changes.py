"""market_changes.py -- Nov 5 2026. 'Market changes' banner for the top of the Fundamentals tab (display only, no ladder or read effect).
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
            if tot <= -400 or len(cut):
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
                      'overnight RT was under $25 in 12-16% of hours (6% normally), median RT-DA -$4 to -$5.' if word == 'Export' else
                      ' Less import help: tighter if load or wind miss.')), mw=round(float(tot)))
    except Exception as ex: print('market changes: limits skipped', ex)
    # 2. availability from pre-DA Adequacy (one bid-time vintage per day)
    try:
        a = C.adq2('preDA'); a['date'] = a.date.astype(str); a['hyd_av2'] = a.hyd_cap - a.hyd_out
        cur = a[a.date == D]; prev = a[a.date.isin(_days(D, 30, 1))]
        for col, lab, thr, push_dn in (('nuc_av', 'Nuclear available', 400, 'bullish'), ('gas_av', 'Gas available', 600, 'bullish'), ('hyd_av2', 'Hydro available', 500, 'bullish')):
            if cur.empty or prev.empty: break
            now, base = cur[col].mean(), prev.groupby('date')[col].mean().median(); d = now - base
            if abs(d) >= thr:
                dn = d < 0
                add('major' if abs(d) >= 1.5 * thr else 'watch', push_dn if dn else ('bearish' if push_dn == 'bullish' else 'bullish'),
                    f'{lab} {"down" if dn else "up"} {abs(d):,.0f} MW vs the last 30 days',
                    f'{base:,.0f} → {now:,.0f} MW for {D} (IESO pre-DA). ' + ('Less supply: tighter, but DA sees it too.' if dn else 'More supply than usual: softer, and DA sees it too.'), mw=round(float(d)))
    except Exception as ex: print('market changes: adequacy skipped', ex)
    # 3. what actually ran: hydro output and net exports, last 3 settled days vs the 30 before
    try:
        f = C.fuel_actual(); f['date'] = f.date.astype(str); last = sorted(f.date.unique()); last = [d for d in last if d <= (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()]
        r3, r30 = last[-3:], last[-33:-3]
        dh = f[f.date.isin(r3)].g_hydro.mean() - f[f.date.isin(r30)].g_hydro.mean()
        if abs(dh) >= 250:
            add('watch', 'bearish' if dh > 0 else 'bullish', f'Hydro running {"above" if dh > 0 else "below"} normal by {abs(dh):,.0f} MW',
                f'Actual hydro output last 3 settled days vs the 30 before. Our hydro estimate is a 14-day median, so it lags: real spare is {"bigger" if dh > 0 else "smaller"} than shown.', mw=round(float(dh)))
        I = pd.read_csv(C.DATA / 'intertie_actual.csv'); I['date'] = I.date.astype(str)
        dx = I[I.date.isin(r3)].tot_flow.mean() - I[I.date.isin(r30)].tot_flow.mean()
        if abs(dx) >= 500:
            add('watch', 'bearish' if dx < 0 else 'bullish', f'Net exports {"down" if dx < 0 else "up"} {abs(dx):,.0f} MW vs normal',
                f'Actual net exports last 3 settled days ({I[I.date.isin(r3)].tot_flow.mean():,.0f} MW) vs the 30 before ({I[I.date.isin(r30)].tot_flow.mean():,.0f}). '
                + ('Less power leaving Ontario: more of it has to be absorbed at home.' if dx < 0 else 'More power leaving: firmer.'), mw=round(float(dx)))
    except Exception as ex: print('market changes: actuals skipped', ex)
    # 4. hidden cushion: likely real spare vs public spare
    try:
        import signals_v2 as SV
        h = pd.read_csv(C.DATA / 'research' / 'physics_history_EAST.csv', low_memory=False, usecols=['date', 'he', 'gas_hat', 'exp_exp', 'pub_sp'])
        sc = SV.schedules()[['date', 'he', 'da_net_exp']].copy(); sc['date'] = (pd.to_datetime(sc.date) + pd.Timedelta(days=1)).dt.strftime('%Y-%m-%d')
        fa = C.fuel_actual()[['date', 'he', 'g_gas']]; fa['date'] = fa.date.astype(str)
        h = h.merge(sc.rename(columns={'da_net_exp': 'exp_d1'}), on=['date', 'he'], how='left').merge(fa, on=['date', 'he'], how='left')
        h['gh'] = h.gas_hat - h.exp_exp + h.exp_d1.fillna(h.exp_exp); h['miss'] = h.g_gas - h.gh
        past = h[h.date.isin(_days(D, 30, 2))].groupby('he').miss.mean()
        t = h[h.date == D].set_index('he')
        if len(t) and len(past):
            gap = ((t.exp_exp - t.exp_d1.fillna(t.exp_exp)) - past.reindex(t.index).fillna(0))   # real spare minus public spare
            real = t.pub_sp + gap; ev = gap.loc[[x for x in range(16, 22) if x in gap.index]]
            if gap.mean() >= 500:
                lo = t.pub_sp.idxmin()
                add('major' if gap.mean() >= 900 else 'watch', 'bearish', f'Real spare likely {gap.mean():,.0f} MW bigger than public spare',
                    f'Tightest public hour HE{lo}: {t.pub_sp[lo]:,.0f} MW shown, about {real[lo]:,.0f} likely (evening HE16-21 +{ev.mean():,.0f} MW). '
                    'Built from yesterday\'s DA export schedule and each hour\'s last-30-day gas miss. "Tight" hours may not be: no longs on tightness alone.',
                    mw=round(float(gap.mean())), hours={int(k): [round(float(t.pub_sp[k])), round(float(real[k]))] for k in t.index})
    except Exception as ex: print('market changes: cushion skipped', ex)
    # 5. wind regime
    try:
        a = C.adq2('preDA'); a['date'] = a.date.astype(str)
        w = a[a.date == D].wind_fc.mean(); w14 = a[a.date.isin(_days(D, 14, 1))].wind_fc.mean()
        if w - w14 >= 1000:
            add('watch', 'bearish', f'Wind {w - w14:,.0f} MW above the last 2 weeks', f'IESO wind for {D} averages {w:,.0f} MW vs {w14:,.0f}. With export limits cut, high-wind hours have the least room to clear.', mw=round(float(w - w14)))
        elif w14 - w >= 1000:
            add('watch', 'bullish', f'Wind {w14 - w:,.0f} MW below the last 2 weeks', f'IESO wind for {D} averages {w:,.0f} MW vs {w14:,.0f}.', mw=round(float(w - w14)))
    except Exception as ex: print('market changes: wind skipped', ex)
    # 6. transmission: 500 kV equipment starting or ending around D, and internal limits cut hard (congestion read for D, if built first)
    try:
        f = C.DATA / 'congestion' / f'read_{D}.json'
        if f.exists():
            r = json.loads(f.read_text()); seen = set(); new = []; ends = []
            for o in r.get('outages', []):
                k = o['equip']
                if k in seen: continue
                seen.add(k)
                if 'new' in o['tag'].lower(): new.append(f"{o['equip']} ({o['where']}, to {o['end'][:10]})")
                elif 'ENDS' in o['tag']: ends.append(f"{o['equip']} ({o['where']})")
            cuts = [f"{x['iface']} {x['limit']:,.0f} vs {x['ais']:,.0f} MW ({x['why']})" for x in r.get('limits', []) if x.get('pct') is not None and x['pct'] <= 70]
            if new or cuts:
                add('watch', 'info', f'Transmission: {len(new)} new 500 kV outage(s), {len(cuts)} limit(s) cut below 70%',
                    ('New since yesterday: ' + '; '.join(new) + '. ' if new else '') + ('Limits: ' + '; '.join(cuts) + '. ' if cuts else '') +
                    ('Returning on D: ' + '; '.join(ends) + '. ' if ends else '') + 'Mostly moves zone splits (West/South vs East), see the congestion read.', mw=0)
    except Exception as ex: print('market changes: transmission skipped', ex)
    items.sort(key=lambda x: (x['level'] != 'major', -abs(x.get('mw', 0))))
    asof = time.strftime('%b %d %H:%M')
    try: adqv = str(C.adq2('preDA').pipe(lambda a: a[a.date.astype(str) == D]).shape[0] and pd.read_csv(C.CACHE / 'ieso_adq2_preDA.csv', usecols=['date', 'ieso_createtime']).query('date == @D').ieso_createtime.max())[5:16] + ' EST'
    except Exception: adqv = '?'
    return dict(date=D, asof=asof, adq=adqv, items=items)

if __name__ == '__main__':
    D = sys.argv[1] if len(sys.argv) > 1 else json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text())['target']
    for i in build(D)['items']: print(f"[{i['level']:5s}] {i['push']:7s} {i['title']}\n         {i['detail']}")
