# Nov 5 2026: where does M2 lose money on the card? Hours that change tier, by type of change.
import pandas as pd, numpy as np
p = pd.read_csv('data/research/iesomiss_pred.csv')[['date', 'he', 'p2']]
def tier(score, read):
    s_, r_ = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s_ == r_), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s_ == r_), s_, np.where(a, 0, np.where(abs(read) >= 5, r_, 0)))
pts = lambda g: np.where(g >= 250, 2, np.where(g >= 100, 1, np.where(g <= -250, -2, np.where(g <= -100, -1, 0))))
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']).merge(p, on=['date', 'he']).dropna(subset=['p2']).reset_index(drop=True)
    m = np.where(h.pub_sp < 2500, 2, 1); s0 = h.score - h['c_Load gap']; new = s0 + pts(h.p2) * m
    t0, d0 = tier(h.score, h.read); t1, d1 = tier(new, h.read)
    pl0 = np.where(np.isin(t0, ['A', 'B']), d0 * h.rd, 0); pl1 = np.where(np.isin(t1, ['A', 'B']), d1 * h.rd, 0)
    g = pd.DataFrame(dict(fr=t0, to=t1, d=pl1 - pl0, side0=d0, side1=d1)); ch = g.fr != g.to
    print(f'{z}: total change {g.d.sum():+,.0f} | hours that change tier {ch.sum()} of {len(g)}')
    print(g[ch].groupby(['fr', 'to']).d.agg(hours='size', change='sum').sort_values('change').to_string())
    k = h[(t0 == 'A') & (t1 == 'B')]; print(f'   A->B hours: same side {100*(d0[(t0=="A")&(t1=="B")] == d1[(t0=="A")&(t1=="B")]).mean():.0f}% (same trade, smaller size in real life)')
    k = (t0 == 'C') & (t1 == 'B'); print(f'   C->B hours ({k.sum()}): the read was right {100*((np.sign(h.read[k]) * h.rd[k]) > 0).mean():.0f}% , made ${(np.sign(h.read[k]) * h.rd[k]).sum():+,.0f}')
    k = (t0 == 'B') & (t1 == 'C'); print(f'   B->C hours ({k.sum()}): standing aside gave up ${(np.sign(h.read[k]) * h.rd[k]).sum():+,.0f}')
