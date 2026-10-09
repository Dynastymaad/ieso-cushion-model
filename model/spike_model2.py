"""spike_model2.py -- Oct 8 2026: does adding the after-bid-surprise predictors (shock_predict.py) make the spike ranking pay?
Same walk-forward as spike_model.py; baseline features vs baseline + new ones. Out of sample Nov 2025 -> Oct 6 2026."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, spike_model as SM
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 250)
NEW = ['gapDyn', 'lf_sd', 'load_miss_hat', 'tie_miss_hat', 'imp_da', 'net_exp_da', 'tie_miss_tr7', 'surp_tr7', 'load_miss_tr7']
S = pd.read_csv(C.DATA / 'shock_predict_EAST.csv')[['date', 'he'] + NEW]

def walk(m, FE):
    p = pd.Series(np.nan, index=m.index); q = p.copy()
    for M in pd.period_range('2025-11', '2026-10', freq='M'):
        cut = (M.start_time - pd.Timedelta(days=2)).date().isoformat(); te = (m.date >= M.start_time.date().isoformat()) & (m.date <= M.end_time.date().isoformat())
        tr = m[(m.date <= cut) & m.spk.notna() & (m.date >= '2025-09-01')]
        if not te.any(): continue
        h = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=250, l2_regularization=1.0, min_samples_leaf=40, random_state=0).fit(tr[FE], tr.spk.astype(int))
        p[te] = h.predict_proba(m.loc[te, FE])[:, 1]
        mu, sd = tr[FE].mean(), tr[FE].std().replace(0, 1)
        lr = LogisticRegression(C=0.3, max_iter=3000).fit(((tr[FE] - mu) / sd).fillna(0), tr.spk.astype(int)); q[te] = lr.predict_proba(((m.loc[te, FE] - mu) / sd).fillna(0))[:, 1]
    return p, q

for z in ('EAST', 'OTTAWA'):
    m = SM.prep(z).merge(S, on=['date', 'he'], how='left')
    m['b_hgb'], m['b_lr'] = walk(m, SM.FE); m['n_hgb'], m['n_lr'] = walk(m, SM.FE + NEW)
    t = m[m.n_hgb.notna() & m.spk.notna()].copy(); ns = t[t.sell == 0]
    print(f'\n=========== {z}: OOS {t.date.min()}..{t.date.max()}, {len(t)} h, base spike {t.spk.mean()*100:.1f}% ===========')
    for c in ('b_hgb', 'b_lr', 'n_hgb', 'n_lr'):
        print(f'AUC {c}: all {roc_auc_score(t.spk, t[c]):.3f} | H1 {roc_auc_score(t[t.date<"2026-02-15"].spk, t[t.date<"2026-02-15"][c]):.3f} | H2 {roc_auc_score(t[t.date>="2026-02-15"].spk, t[t.date>="2026-02-15"][c]):.3f} | non-sell {roc_auc_score(ns.spk, ns[c]):.3f}')
    R = []
    for c, n in (('b_lr', 'baseline logistic'), ('n_lr', 'NEW logistic'), ('b_hgb', 'baseline boosted'), ('n_hgb', 'NEW boosted')):
        R += SM.topk(t, c, (2, 5, 10), n) + SM.topk(ns, c, (5, 10), n + ', non-sell')
    print(pd.DataFrame(R).to_string(index=False))
