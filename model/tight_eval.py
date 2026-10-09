"""tight_eval.py -- Oct 9 2026: should a TIGHT evening hour be sold, skipped, or bought? Fundamentals-based, walk-forward.
Tight evening = v2 tight branch, HE16-21. Features (all known at the bid): spare gas, headroom, 1h/3h gas ramp, evening ramp
HE15->19 and its 60-day percentile, wind level / 3h change / NWP spread, Tesla & Dynasty vs IESO, DA fc, DA fc vs RT fc,
expected net exports, expected hydro, month, weekend, HE. Target: big loss for a sell (RT >= DA + $50).
Each month: logistic + small boosted model trained on earlier months only (through first-of-month - 2 days).
Decision tested on the real ladders: SELL (live) vs SKIP vs FLIP-to-BUY (bid DA fc + $30) when predicted risk is high."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 260)
FE = ['spare', 'head', 'g1', 'g3', 'pm_ramp', 'pm_pct', 'wind_fc', 'wr3', 'w_nwp_sd', 'w_gap_min', 'gapT', 'gapDyn', 'p_da', 'prem', 'he', 'month', 'wkend', 'hyd_exp', 'exp_exp']

def frame(z):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv'); s = pd.read_csv(C.DATA / 'shock_predict_EAST.csv')[['date', 'he', 'gapDyn']]
    m = m.merge(s, on=['date', 'he'], how='left'); m['gapT'] = m.lf_tesla - m.dem_fc
    m['spare'] = m.gas_av - m.gas_hat; g = m.pivot_table(index='date', columns='he', values='gas_hat')
    g1 = g.diff(axis=1).stack().rename('g1'); g3 = g.diff(3, axis=1).stack().rename('g3')
    m = m.merge(g1.reset_index(), on=['date', 'he'], how='left').merge(g3.reset_index(), on=['date', 'he'], how='left')
    r = m.pivot_table(index='date', columns='he', values='resid'); ramp = (r[19] - r[15]).sort_index()
    pct = ramp.rolling(60, min_periods=20).apply(lambda q: (q.iloc[:-1] < q.iloc[-1]).mean() * 100)
    m['pm_ramp'] = m.date.map(ramp); m['pm_pct'] = m.date.map(pct); m['prem'] = m.p_da - m.p_rt
    t = m[(m.why == 'tight') & m.he.between(16, 21) & m.rt.notna() & m.p_rt.notna()].copy()
    t['sp'] = t.da - t.rt; t['loss50'] = (t.sp <= -50).astype(int)
    def sell(r):
        _, s = DV.ladder(5, r.p_da, r.p_rt)
        if pd.notna(r.cahr): s = [(q, None if p is None else (round(min(p, 0.9 * r.p_rt)) if r.cahr >= 12 else p + 10)) for q, p in s]
        return sum(q for q, p in s if p is not None and r.da >= p) * (r.da - r.rt)
    t['pl_sell'] = [sell(r) for r in t.itertuples()]
    t['pl_buy'] = np.where(t.da <= t.p_da + 30, 85 * (t.rt - t.da), 0.0)        # flip: buy the same 85 MW at DA fc + $30
    return t.reset_index(drop=True)

def walk(t, FE):
    t['p_lr'] = np.nan; t['p_gb'] = np.nan; t['thr_lr'] = np.nan; t['thr_gb'] = np.nan
    for M in pd.period_range('2025-10', '2026-10', freq='M'):
        cut = (M.start_time - pd.Timedelta(days=2)).date().isoformat(); te = (t.date >= M.start_time.date().isoformat()) & (t.date <= M.end_time.date().isoformat())
        tr = t[t.date <= cut]
        if not te.any() or tr.loss50.sum() < 15: continue
        mu, sd = tr[FE].mean(), tr[FE].std().replace(0, 1); X = ((tr[FE] - mu) / sd).fillna(0)
        lr = LogisticRegression(C=0.2, max_iter=3000, class_weight='balanced').fit(X, tr.loss50)
        gb = HistGradientBoostingClassifier(max_depth=2, learning_rate=0.05, max_iter=150, min_samples_leaf=30, l2_regularization=1.0, random_state=0).fit(tr[FE], tr.loss50)
        ptr_lr = lr.predict_proba(X)[:, 1]; ptr_gb = gb.predict_proba(tr[FE])[:, 1]
        t.loc[te, 'p_lr'] = lr.predict_proba(((t.loc[te, FE] - mu) / sd).fillna(0))[:, 1]; t.loc[te, 'p_gb'] = gb.predict_proba(t.loc[te, FE])[:, 1]
        # threshold: riskiest 15% of training hours (no peeking at the test month)
        t.loc[te, 'thr_lr'] = np.quantile(ptr_lr, .85); t.loc[te, 'thr_gb'] = np.quantile(ptr_gb, .85)
    return t

def book(t, flag, name):
    s = t.pl_sell; skip = s.where(~flag, 0); flip = s.where(~flag, t.pl_buy)
    out = []
    for lab, pl in (('SELL all (live)', s), (f'SKIP when {name}', skip), (f'FLIP to buy when {name}', flip)):
        d = pl.groupby(t.date).sum()
        out.append(dict(rule=lab, flagged_h=int(flag.sum()), total=round(pl.sum()), H1=round(pl[t.date < '2026-02-15'].sum()), H2=round(pl[t.date >= '2026-02-15'].sum()),
                        last90=round(pl[t.date >= '2026-07-08'].sum()), worst_day=round(d.min()), days_lt_m25k=int((d < -25000).sum()),
                        ex_best_day_gain=round((pl - s).groupby(t.date).sum().pipe(lambda g: g.sum() - g.max()))))
    return out

if __name__ == '__main__':
    for z in ('EAST', 'OTTAWA'):
        t = walk(frame(z), FE); o = t[t.p_lr.notna()].copy()
        print(f'\n======== {z}: tight evening hours {len(t)} ({t.date.min()}..{t.date.max()}), out-of-sample {len(o)} h / {o.date.nunique()} days, big-loss rate {o.loss50.mean()*100:.0f}% ========')
        for c in ('p_lr', 'p_gb'):
            print(f'AUC {c}: {roc_auc_score(o.loss50, o[c]):.3f} | H1 {roc_auc_score(o[o.date<"2026-02-15"].loss50, o[o.date<"2026-02-15"][c]):.3f} | H2 {roc_auc_score(o[o.date>="2026-02-15"].loss50, o[o.date>="2026-02-15"][c]):.3f}')
        print('single-feature AUC (risk up when value up):', {f: round(roc_auc_score(o.loss50, o[f].fillna(o[f].median())), 2) for f in ['spare', 'head', 'pm_pct', 'g1', 'g3', 'gapT', 'p_da', 'prem', 'wind_fc', 'wr3']})
        R = book(o, o.p_lr >= o.thr_lr, 'logistic risk high') + book(o, o.p_gb >= o.thr_gb, 'boosted risk high')[1:] + book(o, (o.pm_pct >= 90) & (o.spare < 1500), 'ramp90 & spare<1500')[1:]
        print(pd.DataFrame(R).to_string(index=False))
        f = o[o.p_lr >= o.thr_lr]; print('  logistic-flagged hours: RT>DA', round((f.sp < 0).mean() * 100), '% | sell $/MWh', round(f.sp.mean(), 1), '| unflagged sell $/MWh', round(o[o.p_lr < o.thr_lr].sp.mean(), 1))
        lr = LogisticRegression(C=0.2, max_iter=3000, class_weight='balanced'); X = ((t[FE] - t[FE].mean()) / t[FE].std()).fillna(0); lr.fit(X, t.loss50)
        print('  what raises the risk (logistic, all data):', dict(sorted(zip(FE, lr.coef_[0].round(2)), key=lambda kv: -abs(kv[1]))[:8]))
        t.to_csv(C.DATA / f'tight_eval_{z}.csv', index=False)
