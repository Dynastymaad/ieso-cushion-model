"""gas_ledge_test.py -- Nov 2 2026. Bid-time test: which 'on the ledge' definition should double the load / wind card points?
Recomputes the card and tiers from physics_history (bid-time inputs, daily-refit read) and settles 1 MW per hour at RT - DA."""
import numpy as np, pandas as pd
pd.set_option('display.width', 220)
def card(h, ledge):
    gL, gW = h.load_gap, h.wind_gap
    L = np.select([gL >= 250, gL >= 100, gL <= -250, gL <= -100], [2, 1, -2, -1], 0)
    W = np.select([gW >= 200, gW <= -200], [1, -1], 0)
    m = np.where(ledge, 2, 1)
    R = np.select([h.w3 >= 300, h.w3 <= -300], [-1, 1], 0)
    P = np.select([h.vs >= 18, h.vs >= 8, h.vs <= -8], [-2, -1, 1], 0)
    N = np.select([h.ny >= 10, h.ny <= -10], [1, -1], 0)
    U = np.where(h.w_up >= 800, -1, 0)
    return (L + W) * m + R + P + N + U
def tiers(s, rd_read):
    sg, r = np.sign(s), np.sign(rd_read)
    A = (abs(s) >= 3) & (sg == r); C = (abs(s) >= 3) & (sg != r); B = (abs(s) < 3) & (abs(rd_read) >= 5)
    side = np.where(A, sg, np.where(B, r, 0)); return side, np.where(A, 'A', np.where(C, 'C', np.where(B, 'B', 'N')))
per = lambda d: np.where(d < '2026-01-01', 'Sep-Dec 25', np.where(d < '2026-07-01', 'Jan-Jun 26', 'Jul-Oct 26'))
res = []
for z in ('EAST', 'OTTAWA'):
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']); h = h[h.date <= '2026-11-01']
    sp, da, g3 = h.pub_sp, h.da_fc, h.g3
    V = {'now: spare < 2,500': sp < 2500,
         'DA fc >= 75': da >= 75,
         'spare < 2,500 or DA fc >= 75': (sp < 2500) | (da >= 75),
         '... and not ramping down (g3 > -800)': ((sp < 2500) | (da >= 75)) & (g3 > -800),
         '... or ramping up 800+': (sp < 2500) | (da >= 75) | (g3 >= 800),
         'DA fc >= 65 (robustness)': da >= 65, 'DA fc >= 85 (robustness)': da >= 85}
    s0 = card(h, V['now: spare < 2,500']); print(z, 'baseline reproduces logged card on', round((s0 == h.score).mean() * 100, 1), '% of hours')
    for k, led in V.items():
        s = card(h, led); side, t = tiers(s, h.read); pnl = side * h.rd; strong = np.where(abs(s) >= 3, np.sign(s), 0) * h.rd
        m = pd.DataFrame(dict(date=h.date, mo=h.date.str[:7], pnl=pnl, strong=strong, p=per(h.date)))
        mo = m.groupby('mo').pnl.sum()
        r = dict(zone=z, ledge=k, plan=round(pnl.sum()), months_up=f"{(mo > 0).sum()}/{mo.size}", hrs=int((side != 0).sum()), strong_card=round(strong.sum()))
        r.update({p: round(g.pnl.sum()) for p, g in m.groupby('p')}); r['ledge_hrs%'] = round(led.mean() * 100); res.append(r)
R = pd.DataFrame(res)
for z in ('EAST', 'OTTAWA'):
    x = R[R.zone == z].drop(columns='zone').set_index('ledge'); b = x.iloc[0]
    x['vs_now'] = x.plan - b.plan; x['months_better'] = None
    print(f'\n== {z}: tiers A+B plan, $/MW (1 MW per hour), Sep 8 2025 - Nov 1 2026 =='); print(x[['ledge_hrs%', 'hrs', 'plan', 'vs_now', 'Sep-Dec 25', 'Jan-Jun 26', 'Jul-Oct 26', 'months_up', 'strong_card']].to_string())
