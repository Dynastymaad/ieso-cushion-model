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
    items.sort(key=lambda x: (x['level'] != 'major', -abs(x.get('mw', 0))))
    asof = time.strftime('%b %d %H:%M')
    try: adqv = str(C.adq2('preDA').pipe(lambda a: a[a.date.astype(str) == D]).shape[0] and pd.read_csv(C.CACHE / 'ieso_adq2_preDA.csv', usecols=['date', 'ieso_createtime']).query('date == @D').ieso_createtime.max())[5:16] + ' EST'
    except Exception: adqv = '?'
    return dict(date=D, asof=asof, adq=adqv, items=items)

if __name__ == '__main__':
    D = sys.argv[1] if len(sys.argv) > 1 else json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text())['target']
    for i in build(D)['items']: print(f"[{i['level']:5s}] {i['push']:7s} {i['title']}\n         {i['detail']}")
