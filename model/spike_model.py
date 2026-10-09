"""spike_model.py -- Oct 8 2026: can bid-time data rank hours by spike risk (RT-DA >= $50) well enough to buy the top ones?
Walk-forward: one model per month, trained only on days <= first-of-month - 2. Out-of-sample Oct 2025 -> Oct 6 2026.
Compares a gradient-boosted model and a logistic model against one-variable ranks (headroom, CAHR). Buy = bid DA fc + $30."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 250)
FE = ['he', 'wkend', 'month', 'head', 'head_min_day', 'gas_spare', 'gas_hat', 'cahr', 'p_da', 'tvu', 'gapT', 'wind_fc', 'wr3', 'w_nwp_sd', 'w_gap_nwp',
      'w_gap_min', 'resid_ramp3', 'gas_out_p', 'spk_d2_4', 'max_d2_4', 'bias7', 'nyx', 'sell']

def prep(z):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv'); m['gapT'] = m.lf_tesla - m.dem_fc; m['nyx'] = m.nyA_da - m.p_da
    return m[m.date <= '2026-10-06'].reset_index(drop=True)

def walk(m):
    m['p_hgb'] = np.nan; m['p_lr'] = np.nan
    for M in pd.period_range('2025-10', '2026-10', freq='M'):
        lo = M.start_time; cut = (lo - pd.Timedelta(days=2)).date().isoformat()
        tr = m[(m.date <= cut) & m.spk.notna()]; te = (m.date >= lo.date().isoformat()) & (m.date <= M.end_time.date().isoformat())
        if not te.any(): continue
        X, y = tr[FE], tr.spk.astype(int)
        h = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=250, l2_regularization=1.0, min_samples_leaf=40, random_state=0).fit(X, y)
        m.loc[te, 'p_hgb'] = h.predict_proba(m.loc[te, FE])[:, 1]
        mu, sd = X.mean(), X.std().replace(0, 1); Xs = ((X - mu) / sd).fillna(0)
        lr = LogisticRegression(C=0.3, max_iter=2000).fit(Xs, y); m.loc[te, 'p_lr'] = lr.predict_proba(((m.loc[te, FE] - mu) / sd).fillna(0))[:, 1]
    return m

def topk(t, col, q, name, asc=False):
    rows = []
    for pct in q:
        thr = t.groupby(t.date.str[:7])[col].transform(lambda s: s.quantile(pct / 100 if asc else 1 - pct / 100))   # same share every month (no look-ahead on level)
        k = (t[col] <= thr) if asc else (t[col] >= thr)
        x = t[k]; b = x[x.da <= x.p_da + 30]; pl = b.rd
        rows.append(dict(ranker=name, top=f'{pct}%', hours=len(x), spike_rate=round(x.spk.mean() * 100, 1), mean_rd=round(x.rd.mean(), 1), median_rd=round(x.rd.median(), 1),
                         buy_per_mwh=round(pl.mean(), 2), H1=round(pl[b.date < '2026-02-15'].mean(), 1), H2=round(pl[b.date >= '2026-02-15'].mean(), 1),
                         last90=round(pl[b.date >= '2026-07-08'].mean(), 1), days=x.date.nunique(), ex_top5days=round(pl.sum() - pl.groupby(b.date).sum().nlargest(5).sum())))
    return rows

if __name__ == '__main__':
    for z in ('EAST', 'OTTAWA'):
        m = walk(prep(z)); t = m[m.p_hgb.notna() & m.spk.notna()].copy()
        print(f'\n==================== {z}: out-of-sample {t.date.min()} .. {t.date.max()}, {len(t)} h, base spike rate {t.spk.mean()*100:.1f}% ====================')
        print('AUC  boosted', round(roc_auc_score(t.spk, t.p_hgb), 3), '| logistic', round(roc_auc_score(t.spk, t.p_lr), 3),
              '| headroom alone', round(roc_auc_score(t.spk, -t['head']), 3), '| CAHR alone', round(roc_auc_score(t.spk, t.cahr.fillna(t.cahr.median())), 3),
              '| H1/H2 boosted', round(roc_auc_score(t[t.date < '2026-02-15'].spk, t[t.date < '2026-02-15'].p_hgb), 3), round(roc_auc_score(t[t.date >= '2026-02-15'].spk, t[t.date >= '2026-02-15'].p_hgb), 3))
        R = topk(t, 'p_hgb', (1, 2, 5, 10), 'boosted model') + topk(t, 'p_lr', (2, 5, 10), 'logistic') + topk(t, 'head', (2, 5, 10), 'lowest headroom', asc=True)
        ns = t[t.sell == 0]; R += topk(ns, 'p_hgb', (2, 5, 10), 'boosted, NON-SELL hours only')
        print(pd.DataFrame(R).to_string(index=False))
        # what the model keys on (refit on everything, permutation importance on last 3 months)
        from sklearn.inspection import permutation_importance
        tr = m[m.spk.notna() & (m.date < '2026-07-01')]; te = m[m.spk.notna() & (m.date >= '2026-07-01')]
        h = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=250, l2_regularization=1.0, min_samples_leaf=40, random_state=0).fit(tr[FE], tr.spk.astype(int))
        pi = permutation_importance(h, te[FE], te.spk.astype(int), scoring='roc_auc', n_repeats=5, random_state=0)
        print('top drivers (AUC lost when shuffled, Jul-Oct):', pd.Series(pi.importances_mean, FE).sort_values(ascending=False).head(8).round(3).to_dict())
        m[['date', 'he', 'p_hgb', 'p_lr']].to_csv(C.DATA / f'spike_model_oos_{z}.csv', index=False)
