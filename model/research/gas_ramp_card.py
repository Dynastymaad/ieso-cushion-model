# Nov 5 2026: test a gas-ramp "market ahead / behind" card point. All inputs known at bid time:
#   g3 = gas need into the hour minus 3 h earlier (MW, bid-time physics); d3 = our DA forecast into the hour minus 3 h earlier ($).
#   ahead (up ramp) = DA forecast already climbed >= $X per GW of ramp -> priced in -> -1.  Plan P&L = A/B tiers, 1 MW, side x (RT-DA).
import pandas as pd, numpy as np, sys
def tier(score, read):
    s, r = np.sign(score), np.sign(read)
    return np.where((abs(score) >= 3) & (s == r), 'A', np.where(abs(score) >= 3, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where((abs(score) >= 3) & (s == r), s, np.where(abs(score) >= 3, 0, np.where(abs(read) >= 5, r, 0)))
H = {z: pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']).sort_values(['date', 'he']).reset_index(drop=True) for z in ['EAST', 'OTTAWA']}
for h in H.values():
    h['d3'] = h.groupby('date').da_fc.diff(3); h['m'] = h.date.str[:7]
def point(h, X=20, Y=10, MIN=500, sym=False, behind=False):
    gw = h.g3 / 1000; up = h.g3 >= MIN; dn = h.g3 <= -MIN; p = np.zeros(len(h))
    p[(up & (h.d3 >= X * gw)).values] = -1
    if behind: p[(up & (h.d3 < Y * gw)).values] = 1
    if sym:
        p[(dn & (h.d3 <= X * gw)).values] = 1                # DA already fell >= $X per GW of ramp-down -> priced in -> +1
        if behind: p[(dn & (h.d3 > Y * gw)).values] = -1
    p[h.d3.isna().values] = 0
    return p
def plan(h, score):
    t, s = tier(score, h.read); pnl = np.where(np.isin(t, ['A', 'B']), s * h.rd, 0)
    return pd.Series(pnl, index=h.index), t
V = [('ahead up-ramp -1 ($20/GW, 500 MW)', dict()), ('  same, $15/GW', dict(X=15)), ('  same, $25/GW', dict(X=25)), ('  same, ramp 800 MW', dict(MIN=800)),
     ('ahead -1 + behind +1 (up ramps)', dict(behind=True)), ('both directions (ahead only)', dict(sym=True)), ('both directions + behind', dict(sym=True, behind=True))]
for z, h in H.items():
    base, tb = plan(h, h.score); bm = base.groupby(h.m).sum()
    print(f'{z}  {h.date.min()} to {h.date.max()}  base plan ${base.sum():,.0f}')
    for lab, kw in V:
        p = point(h, **kw); new, tn = plan(h, h.score + p); nm = new.groupby(h.m).sum()
        f = p != 0; alone = (np.sign(p[f]) * h.rd[f]); alone_c = (np.sign(p[f]) * h.rd[f].clip(-150, 150))
        print(f'  {lab:38s} fires {f.sum()//1:5d} h | alone ${alone.mean():6.2f} (clip ${alone_c.mean():5.2f}, right {100*(alone>0).mean():.0f}%) | plan ${new.sum():,.0f} ({new.sum()-base.sum():+,.0f}) | months better {(nm>bm+1).sum()}/worse {(nm<bm-1).sum()} | tier changes {(tn!=tb).sum()}')
    print()
print('--- why: where the ahead point fires ($20/GW, 500 MW)')
for z, h in H.items():
    p = point(h); f = p != 0; tb, sb = tier(h.score, h.read); tn, sn = tier(h.score + p, h.read)
    print(z, 'already short in plan:', f'{100*((sb==-1)&f).sum()/f.sum():.0f}%', '| read already short:', f'{100*((h.read<0)&f).sum()/f.sum():.0f}%', '| DA-priced point already -:', f'{100*((h["c_DA priced"]<0)&f).sum()/f.sum():.0f}%')
    ch = tn != tb; g = pd.DataFrame(dict(fr=tb[ch], to=tn[ch], rd=h.rd[ch], read=h.read[ch]))
    g['old'] = np.where(np.isin(g.fr, ['A','B']), sb[ch] * g.rd, 0); g['new'] = np.where(np.isin(g.to, ['A','B']), sn[ch] * g.rd, 0)
    print(g.groupby(['fr', 'to']).agg(h=('rd', 'size'), old=('old', 'sum'), new=('new', 'sum')).round(0).to_string())
