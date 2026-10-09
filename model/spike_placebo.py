import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, spike_model as SM, spike_model2_robust as R0
z = sys.argv[1]; n = int(sys.argv[2]); m = SM.prep(z).merge(R0.S, on=['date', 'he'], how='left'); rng = np.random.default_rng(int(sys.argv[3])); out = []
for k in range(n):
    mm = m.copy(); mo = mm.date.str[:7]
    for _, idx in mm.groupby(mo).groups.items():
        days = mm.loc[idx, 'date'].unique(); perm = dict(zip(days, rng.permutation(days))); src = mm.loc[idx].set_index(['date', 'he'])[R0.NEW]
        mm.loc[idx, R0.NEW] = src.reindex(list(zip(mm.loc[idx, 'date'].map(perm), mm.loc[idx, 'he']))).values
    r, _ = R0.run(mm, SM.FE + R0.NEW); out.append((r['per_mwh'], r['ex_top5']))
print(z, out)
