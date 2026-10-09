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

def target(D):
    o = frame(); t = o[o.date == D]
    if t.empty: return None
    p = o[o.date == (pd.Timestamp(D) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')].set_index('he')
    rows = [dict(he=int(r.he), gas=J(r.gas_bid), nuc=J(r.nuc_bid), hyd=J(r.hyd_bid), tot=J(r.out_bid),
                 gret=J(r.gas_ret), nret=J(r.nuc_ret), hret=J(r.hyd_ret), ret=J(r.ret),
                 vs_d1=J(r.out_bid - p.out_final.get(r.he, np.nan)) if len(p) else None) for r in t.itertuples()]
    t2 = t[t.he.between(12, 21)]
    return dict(rows=rows, gret_pm=J(t2.gas_ret.clip(lower=0).sum()), ret_day=bool(t2.gas_ret.clip(lower=0).sum() >= 300),
                ret_assumed=J(t.ret_assumed.mean()))

if __name__ == '__main__':
    import json
    for z in ('EAST', 'OTTAWA'): print(z, json.dumps(summary(z), indent=1))
    print(json.dumps(target('2026-10-09'), indent=0)[:1500])
