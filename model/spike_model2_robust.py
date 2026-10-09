"""spike_model2_robust.py -- stress test of the one promising result in spike_model2.py: boosted model + after-bid-surprise
predictors, buying the top 10% (by month) of NON-SELL hours at DA fc + $30. Checks: seeds/settings, dropping each new input,
placebo (new inputs shuffled across days within the month), months, overlap with the buy band."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, spike_model as SM
from sklearn.ensemble import HistGradientBoostingClassifier
pd.set_option('display.width', 250)
NEW = ['gapDyn', 'lf_sd', 'load_miss_hat', 'tie_miss_hat', 'tie_miss_tr7', 'surp_tr7', 'load_miss_tr7']   # no DA intertie schedules (look-ahead)
S = pd.read_csv(C.DATA / 'shock_predict_EAST.csv')[['date', 'he'] + NEW]

def run(m, FE, seed=0, depth=3, lr=0.05, it=250):
    p = pd.Series(np.nan, index=m.index)
    for M in pd.period_range('2025-11', '2026-10', freq='M'):
        cut = (M.start_time - pd.Timedelta(days=2)).date().isoformat(); te = (m.date >= M.start_time.date().isoformat()) & (m.date <= M.end_time.date().isoformat())
        tr = m[(m.date <= cut) & m.spk.notna() & (m.date >= '2025-09-01')]
        if not te.any(): continue
        h = HistGradientBoostingClassifier(max_depth=depth, learning_rate=lr, max_iter=it, l2_regularization=1.0, min_samples_leaf=40, random_state=seed).fit(tr[FE], tr.spk.astype(int))
        p[te] = h.predict_proba(m.loc[te, FE])[:, 1]
    t = m.assign(p=p); t = t[t.p.notna() & t.spk.notna() & (t.sell == 0)]
    thr = t.groupby(t.date.str[:7]).p.transform(lambda s: s.quantile(.9)); x = t[t.p >= thr]; b = x[x.da <= x.p_da + 30]; pl = b.rd
    return dict(per_mwh=round(pl.mean(), 1), H1=round(pl[b.date < '2026-02-15'].mean(), 1), H2=round(pl[b.date >= '2026-02-15'].mean(), 1), last90=round(pl[b.date >= '2026-07-08'].mean(), 1),
                ex_top5=round(pl.sum() - pl.groupby(b.date).sum().nlargest(5).sum()), hours=len(b)), b

if __name__ == '__main__':
    for z in ('EAST', 'OTTAWA'):
        m = SM.prep(z).merge(S, on=['date', 'he'], how='left'); R = []
        base, _ = run(m, SM.FE); R.append(dict(test='baseline (no new inputs)', **base))
        main, b = run(m, SM.FE + NEW); R.append(dict(test='NEW (as reported)', **main))
        for s, d, l, it in ((1, 3, .05, 250), (2, 3, .05, 250), (3, 3, .05, 250), (0, 2, .05, 300), (0, 4, .03, 300), (0, 3, .1, 150)):
            r, _ = run(m, SM.FE + NEW, s, d, l, it); R.append(dict(test=f'seed {s} depth {d} lr {l}', **r))
        for f in NEW:
            r, _ = run(m, SM.FE + [x for x in NEW if x != f]); R.append(dict(test=f'drop {f}', **r))
        rng = np.random.default_rng(0)
        for k in range(4):
            mm = m.copy(); mo = mm.date.str[:7]
            for _, idx in mm.groupby(mo).groups.items():
                days = mm.loc[idx, 'date'].unique(); perm = dict(zip(days, rng.permutation(days)))
                src = mm.loc[idx].set_index(['date', 'he'])[NEW]
                mm.loc[idx, NEW] = src.reindex(list(zip(mm.loc[idx, 'date'].map(perm), mm.loc[idx, 'he']))).values
            r, _ = run(mm, SM.FE + NEW); R.append(dict(test=f'PLACEBO shuffle {k}', **r))
        print(f'\n========== {z} =========='); print(pd.DataFrame(R).to_string(index=False))
        print('by month (NEW, $/MWh):', b.groupby(b.date.str[:7]).rd.mean().round(1).to_dict())
        print('share already in buy band:', round((b.buyband == -1).mean() * 100), '% | HE mix:', b.groupby(pd.cut(b.he, [0, 6, 16, 22, 24])).size().to_dict())
