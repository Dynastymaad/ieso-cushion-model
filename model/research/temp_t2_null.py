# Is T2's gain new information, or does it just echo the read? Null = same T2 values reassigned to other hours with the same read side and tier (within month).
import pandas as pd, numpy as np, runpy, sys, io, contextlib
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path('model/research/temp_card.py')   # reuse frames
L, plan = G['L'], G['plan']; rng = np.random.default_rng(11)
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).merge(L[['date', 'he', 'impl', 't_fc', 't_act_d2']], on=['date', 'he'], how='left')
    h = h.dropna(subset=['rd', 'impl']).reset_index(drop=True); h['m'] = h.date.str[:7]
    slope = np.where(h.t_fc < 12, -150, np.where(h.t_fc > 18, 300, 0)); dL = slope * (h.t_fc - h.t_act_d2).fillna(0)
    p = np.where(dL >= 250, 1, np.where(dL <= -250, -1, 0)); f = p != 0
    base, tb = plan(h, h.score); real = plan(h, h.score + p)[0].sum() - base.sum()
    print(z, f'T2 agrees with read side {100*(np.sign(p[f]) == np.sign(h.read[f])).mean():.0f}% | with card side {100*(np.sign(p[f]) == np.sign(h.score[f]))[h.score[f] != 0].mean():.0f}%')
    grp = h.m + '|' + np.sign(h.read).astype(str) + '|' + tb.astype(str) + '|' + np.sign(h.score).astype(str)
    sims = []
    for _ in range(60):
        q = p.copy()
        for k, idx in pd.Series(np.arange(len(h))).groupby(grp.values):
            q[idx.values] = rng.permutation(p[idx.values])
        sims.append(plan(h, h.score + q)[0].sum() - base.sum())
    sims = np.array(sims); print(f'   real {real:+,.0f} | read-matched null: median {np.median(sims):+,.0f}, 90th pct {np.percentile(sims, 90):+,.0f}, share >= real {(sims >= real).mean():.0%}')
