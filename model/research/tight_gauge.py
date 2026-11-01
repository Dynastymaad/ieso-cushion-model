"""Survey: which physical 'tight vs priced' signals line up with RT-DA in 2026 (Mar-Oct). Bid-time features only."""
import pandas as pd, numpy as np, sys
z = sys.argv[1] if len(sys.argv) > 1 else 'EAST'
e = pd.read_csv(f'data/research/stress_{z}_extra.csv'); e['rd'] = e.rt - e.da; e = e.dropna(subset=['rd'])
e['m'] = e.date.str[:7]; e['valley'] = e.he.between(9, 15)
e['wlow_gap'] = e.wind_fc - e[[c for c in e if c.startswith('wf_') and c != 'wf_meteologica']].min(axis=1)
S = {  # name: (mask, physical direction +1 = tighter than public view)
 'load: vendors above IESO >=250': (e.d_load >= 250, 1), 'load: vendors below IESO <=-250': (e.d_load <= -250, -1),
 'wind: Meteo below IESO <=-150': (e.d_wind <= -150, 1), 'wind: Meteo above IESO >=150': (e.d_wind >= 150, -1),
 'wind: IESO >=250 above model median': (e.iesow_vs_models >= 250, 1),
 'wind: IESO >=300 above models low': (e.wlow_gap >= 300, 1),
 'danger: our spare 300+ below public': (e.rescue <= -300, 1), 'rescue: our spare 300+ above public': (e.rescue >= 300, -1),
 'spare: public < 1500': (e.pub_sp < 1500, 1), 'spare: public > 3500': (e.pub_sp > 3500, -1),
 'gas ramp 3h > +1000': (e.g3 > 1000, 1), 'gas ramp 3h < -1000': (e.g3 < -1000, -1),
 'wind ramp 3h < -300': (e.w3 < -300, 1), 'wind ramp 3h > +300': (e.w3 > 300, -1),
 'net-load ramp 3h > +1000': (e.res3 > 1000, 1), 'net-load ramp 3h < -1000': (e.res3 < -1000, -1),
 'DA priced cheap (vs <= -5)': (e.vs <= -5, 1), 'DA priced rich (vs >= 18)': (e.vs >= 18, -1),
 'wind spread > 1500': (e.w_spread > 1500, 1), 'hydro valve < 500': (e.valve < 500, 1),
}
rows = []
for k, (msk, d) in S.items():
    for lab, sub in [('all', e), ('valley', e[e.valley])]:
        on = sub[msk.reindex(sub.index)]
        if len(on) < 40: rows.append((k, lab, len(on), np.nan, np.nan, '')); continue
        ex = (on.rd.mean() - sub.rd.mean()) * d   # >0 means signal moves RT-DA the physical way
        mm = on.groupby('m').rd.mean() - sub.groupby('m').rd.mean().reindex(on.groupby('m').rd.mean().index)
        rows.append((k, lab, len(on), round(on.rd.mean(), 1), round(ex, 1), f'{int(((mm*d) > 0).sum())}/{len(mm)}'))
r = pd.DataFrame(rows, columns=['signal', 'hours', 'n', 'RT-DA when on', 'edge in expected dir', 'months agree'])
print(z, 'base RT-DA all', round(e.rd.mean(), 1), 'valley', round(e[e.valley].rd.mean(), 1))
print(r.to_string(index=False))

# ---- gauge: pick signals on Jan-Jun only (months agree >= 2/3, edge > 1), test on Jul-Oct ----
def pick(sub):
    keep = {}
    for k, (msk, d) in S.items():
        on = sub[msk.reindex(sub.index)]
        if len(on) < 40: continue
        mm = (on.groupby('m').rd.mean() - sub.groupby('m').rd.mean().reindex(on.groupby('m').rd.mean().index)) * d
        ex = (on.rd.mean() - sub.rd.mean()) * d
        if abs(ex) > 1 and ((mm * np.sign(ex)) > 0).mean() >= 2 / 3: keep[k] = d * int(np.sign(ex))
    return keep
train = e[e.date < '2026-07-01']; test = e[e.date >= '2026-07-01'].copy()
K = pick(train); print('\nsignals picked on Jan-Jun (+1 = pushes RT above DA):'); [print(f'  {v:+d}  {k}') for k, v in K.items()]
e['gauge'] = sum(S[k][0].astype(int) * v for k, v in K.items())
t = e[e.date >= '2026-07-01']
g = t.groupby(t.gauge.clip(-3, 3)).rd.agg(['mean', 'count']).round(1); g['months +'] = [f"{int((t[t.gauge.clip(-3,3)==i].groupby('m').rd.mean()>0).sum())}/{t[t.gauge.clip(-3,3)==i].m.nunique()}" for i in g.index]
print('\nOUT-OF-SAMPLE Jul-Oct: RT-DA by gauge'); print(g.to_string())
for lab, s in [('all', t), ('valley', t[t.valley])]:
    hi, lo = s[s.gauge >= 2], s[s.gauge <= -2]
    print(f'{lab}: gauge>=+2 long ${hi.rd.mean():+.1f} ({len(hi)} h, win {(hi.rd>0).mean():.0%}) | gauge<=-2 short ${-lo.rd.mean():+.1f} ({len(lo)} h, win {(lo.rd<0).mean():.0%}) | rank corr {s.gauge.corr(s.rd, method="spearman"):.2f}  card {s.card.corr(s.rd, method="spearman"):.2f}  gbm {s.gbm.corr(s.rd, method="spearman"):.2f}')
d = e[e.date == '2026-10-31']
print('\nOct 31 (signals on):')
for _, r in d.iterrows():
    on = [('+' if v > 0 else '-') + k.split(':')[0] for k, v in K.items() if S[k][0].loc[_]]
    print(f" HE{int(r.he):>2} gauge {int(r.gauge):+d}  RT-DA {r.rd:+6.1f}  {', '.join(on)}")
