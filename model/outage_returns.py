"""outage_returns.py -- Oct 9 2026 (TEST/INFO): outage returns scheduled for the target day, and what history says about them.
Return in HE h = outage MW at the bid in HE h-1 minus HE h (positive = units coming back), by fuel (gas/nuc/hyd).
Slip = outage MW added after the bid (out_final - out_bid) in hours AFTER a scheduled return.
Risk = East RT-DA and spike rate (RT >= DA+50) in HE16-21 on days with 300+ MW gas returning HE12-21 vs other days."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
J = lambda v: None if v is None or pd.isna(v) else int(round(float(v)))

def frame():
    o = pd.read_csv(C.DATA / 'outage_features.csv').sort_values(['date', 'he'])
    for f in ('gas', 'nuc', 'hyd'):
        o[f'{f}_ret'] = -o.groupby('date')[f'{f}_bid'].diff()            # +ve = coming back this hour
    o['ret'] = o[['gas_ret', 'nuc_ret', 'hyd_ret']].sum(axis=1)
    return o

def day_stats(o):
    g = o.copy(); g['gret_win'] = np.where(g.he.between(12, 21), g.gas_ret.clip(lower=0), 0)
    d = g.groupby('date').agg(gret=('gret_win', 'sum'), gas_add_pm=('gas_add', lambda s: s[g.loc[s.index, 'he'].between(16, 21)].max()))
    return d

def history(z='EAST'):
    o = frame(); d = day_stats(o)
    s = pd.read_csv(C.DATA / f'spike_feats_{z}.csv')[['date', 'he', 'rt', 'da']]
    s = s[s.he.between(16, 21) & s.rt.notna() & (s.date >= '2025-09-12')]
    s['rd'] = s.rt - s.da; s['spk'] = s.rd >= 50
    e = s.groupby('date').agg(rd=('rd', 'mean'), spk=('spk', 'mean'), anyspk=('spk', 'max')).join(d, how='inner')
    e['ret_day'] = e.gret >= 300; e['slip'] = e.gas_add_pm >= 200
    return e

def summary(z='EAST'):
    e = history(z); out = {}
    for k, sub in (('returns 300+', e[e.ret_day]), ('no big return', e[~e.ret_day])):
        out[k] = dict(days=len(sub), rd=round(sub.rd.mean(), 1), spk_hr=round(sub.spk.mean() * 100, 1), spk_day=round(sub.anyspk.mean() * 100, 1),
                      slip=round(sub.slip.mean() * 100, 1))
    r = e[e.ret_day]
    out['slip vs not'] = dict(slip_rd=round(r[r.slip].rd.mean(), 1), slip_spkday=round(r[r.slip].anyspk.mean() * 100, 1),
                             ok_rd=round(r[~r.slip].rd.mean(), 1), ok_spkday=round(r[~r.slip].anyspk.mean() * 100, 1), n_slip=int(r.slip.sum()))
    h1 = e[e.index < '2026-02-15']; h2 = e[e.index >= '2026-02-15']
    out['halves'] = {n: dict(ret_rd=round(x[x.ret_day].rd.mean(), 1), no_rd=round(x[~x.ret_day].rd.mean(), 1),
                             ret_spk=round(x[x.ret_day].anyspk.mean() * 100, 1), no_spk=round(x[~x.ret_day].anyspk.mean() * 100, 1)) for n, x in (('H1', h1), ('H2', h2))}
    return out

# ---- Oct 9 2026: hour-by-hour return / new-outage events by fuel, as known at the bid (D-1 09:00 EST), incl. the overnight step into HE1
SUBF = {'Gas Outage': 'Gas', 'Nuclear Outage': 'Nuclear', 'Hydro Outage': 'Hydro'}
_TL = None
def _timeline():
    global _TL
    if _TL is None:
        t = pd.read_csv(C.CACHE / 'ieso_adq2_outage_timeline.csv'); t = t[t.subtype.isin(list(SUBF))].copy()
        t['ct'] = pd.to_datetime(t.ieso_createtime); _TL = t
    return _TL

def bid_view(D):
    """outage MW by fuel for D-1 HE24 and D HE1..24, last IESO value created before D-1 09:00 EST (what we bid on)."""
    t = _timeline(); p = (pd.Timestamp(D) - pd.Timedelta(days=1)).strftime('%Y-%m-%d'); cut = pd.Timestamp(p) + pd.Timedelta(hours=9)
    x = t[((t.date == D) | ((t.date == p) & (t.hour == 24))) & (t.ct <= cut)].sort_values('ct')
    w = x.groupby(['date', 'hour', 'subtype']).value.last().unstack('subtype').rename(columns=SUBF).reset_index()
    return w.sort_values(['date', 'hour']).reset_index(drop=True)

def events(D, thr=50):
    w = bid_view(D)
    if len(w) < 2: return [], {}
    E = []; tot = {}
    for f in ('Gas', 'Nuclear', 'Hydro'):
        if f not in w: continue
        v = w[f].values; hs = w.hour.values; ds = w.date.values
        back = out = 0
        for i in range(1, len(v)):
            if ds[i] != D: continue
            c = v[i] - v[i - 1]
            if c < 0: back += -c
            else: out += c
            if abs(c) >= thr:
                E.append(dict(he=int(hs[i]), fuel=f, mw=J(abs(c)), kind='back' if c < 0 else 'out', overnight=bool(ds[i - 1] != D), level=J(v[i])))
        tot[f] = dict(back=J(back), out=J(out), he1=J(v[1]) if len(v) > 1 else None, he24=J(v[-1]))
    return sorted(E, key=lambda e: (e['he'], e['fuel'])), tot

def reliability(since='2025-10-01'):
    """How often a scheduled step (>=100 MW within D, at the bid) actually happened, from final outage MW."""
    o = pd.read_csv(C.DATA / 'outage_features.csv').sort_values(['date', 'he']); o = o[o.date >= since]; R = {}
    for f, k in (('Gas', 'gas'), ('Nuclear', 'nuc'), ('Hydro', 'hyd')):
        o['fin'] = o[k + '_bid'] + o[k + '_add']; G = o.groupby('date')
        o['s'] = G[k + '_bid'].diff(); o['prev'] = G.fin.shift(1)
        o['a3'] = G.fin.shift(-1) - G.fin.shift(2)
        o['minrest'] = G.fin.transform(lambda s: s[::-1].cummin()[::-1]); o['maxrest'] = G.fin.transform(lambda s: s[::-1].cummax()[::-1])
        b = o[o.s <= -100]; n = o[o.s >= 100]
        gb = (b.prev - b.minrest) / -b.s; gn = (n.maxrest - n.prev) / n.s
        R[f] = dict(back_n=int(len(b)), back_ontime=J(((-b.a3 / -b.s) >= .5).mean() * 100), back_byend=J((gb >= .5).mean() * 100), back_slip=J((gb < .1).mean() * 100),
                    out_n=int(len(n)), out_ontime=J(((n.a3 / n.s) >= .5).mean() * 100), out_byend=J((gn >= .5).mean() * 100))
    return R

def target(D):
    o = frame(); t = o[o.date == D]
    if t.empty: return None
    try: E, tot = events(D); bv = bid_view(D); h24 = bv[bv.date != D]
    except Exception as ex: print('outage events skipped:', ex); E, tot, h24 = [], {}, pd.DataFrame()
    y24 = float(h24[['Gas', 'Nuclear', 'Hydro']].sum(axis=1).iloc[0]) if len(h24) else np.nan
    rows = [dict(he=int(r.he), gas=J(r.gas_bid), nuc=J(r.nuc_bid), hyd=J(r.hyd_bid), tot=J(r.out_bid),
                 gret=J(r.gas_ret), nret=J(r.nuc_ret), hret=J(r.hyd_ret), ret=J(r.ret)) for r in t.itertuples()]
    if rows and np.isfinite(y24):        # overnight step into HE1 (today HE24 -> tomorrow HE1, both as IESO had them at the bid)
        r1 = t.iloc[0]; f24 = {k: float(h24[k].iloc[0]) for k in ('Gas', 'Nuclear', 'Hydro') if k in h24}
        rows[0].update(gret=J(f24.get('Gas', np.nan) - r1.gas_bid), nret=J(f24.get('Nuclear', np.nan) - r1.nuc_bid), hret=J(f24.get('Hydro', np.nan) - r1.hyd_bid), ret=J(y24 - r1.out_bid))
    t2 = t[t.he.between(12, 21)]
    return dict(rows=rows, gret_pm=J(t2.gas_ret.clip(lower=0).sum()), ret_day=bool(t2.gas_ret.clip(lower=0).sum() >= 300),
                ret_assumed=J(t.ret_assumed.mean()), events=E, totals=tot, today_he24=J(y24), rel=reliability())

if __name__ == '__main__':
    import json
    for z in ('EAST', 'OTTAWA'): print(z, json.dumps(summary(z), indent=1))
    print(json.dumps(target('2026-10-09'), indent=0)[:1500])
