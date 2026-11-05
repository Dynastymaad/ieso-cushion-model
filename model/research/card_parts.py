# Nov 5 2026: when does each card point earn its keep? Edge of trading each point's sign alone (+ = RT above DA), by season and block. Read only.
import pandas as pd, numpy as np, sys
R = 'data/research/physics_history_{}.csv'
P = ['c_Load gap', 'c_Wind gap', 'c_Wind ramp', 'c_Wind upside', 'c_DA priced', 'c_NY pull', 'c_Exports']
def load(z):
    e = pd.read_csv(R.format(z), low_memory=False); e['z'] = z
    e = e[e.rt.notna() & e.da.notna()].copy(); e['d'] = (e.rt - e.da).clip(-150, 150)   # clip spikes so one hour can't carry a whole cell
    m = pd.to_datetime(e.date).dt.month
    e['season'] = np.select([m.isin([12, 1, 2]), m.isin([3, 4, 5]), m.isin([6, 7, 8])], ['Winter', 'Spring', 'Summer'], 'Fall')
    e['block'] = pd.cut(e.he, [0, 6, 15, 21, 24], labels=['HE1-6', 'HE7-15', 'HE16-21', 'HE22-24']).astype(str)
    e['tight'] = np.where(e.pub_sp < 2500, 'spare<2500', 'spare>=2500')
    return e
e = pd.concat([load('EAST'), load('OTTAWA')])
print('rows', len(e), e.date.min(), e.date.max())
def tab(by):
    out = []
    for p in P:
        g = e[e[p] != 0].copy(); g['pl'] = np.sign(g[p]) * g.d; g['hit'] = g.pl > 0
        for k, h in g.groupby(by):
            if len(h) < 60: continue
            out.append(dict(point=p[2:], **{by: k}, hours=len(h) // 2, edge=round(h.pl.mean(), 2), hit=round(100 * h.hit.mean())))
    t = pd.DataFrame(out).pivot(index='point', columns=by, values=['edge', 'hit'])
    return t
pd.set_option('display.width', 250)
for by in ['season', 'block', 'tight']: print('\n=== by', by, '(edge $/MWh per MW, spike-clipped; hit %) ==='); print(tab(by).to_string())
# overall + when the point agrees / fights the read
o = []
for p in P:
    g = e[e[p] != 0].copy(); s = np.sign(g[p]); pl = s * g.d
    agr = np.sign(g.read) == s
    o.append(dict(point=p[2:], hours=len(g) // 2, edge=round(pl.mean(), 2), hit=round(100 * (pl > 0).mean()), with_read=round(pl[agr].mean(), 2), against_read=round(pl[~agr].mean(), 2), n_against=int((~agr).sum()) // 2))
print('\n=== overall ==='); print(pd.DataFrame(o).to_string(index=False))
# does a bigger card help? edge by |card|
e['cs'] = e[P].sum(axis=1); g = e[e.cs != 0].copy(); g['pl'] = np.sign(g.cs) * g.d; g['a'] = g.cs.abs().clip(upper=5)
print('\n=== by card size ==='); print(g.groupby('a').pl.agg(['size', 'mean', lambda x: (x > 0).mean()]).round(2).to_string())
