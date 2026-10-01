"""limits_study.py -- do the intertie limits (known at bid time) say anything about DA-RT?  17 months, walk-forward.
Inputs: data/nrg/hub_prices_nrg.csv (DA, RT), supply_fc.limits_at_bid() (DA = PreDA limits, all interties incl. PQ),
        data/nrg/rt_intertie_limits.csv (realised RT limits, diagnostic only), cache adequacy (headroom at bid).
Features (all known D-1 08:08 EST):
  cut_exp / cut_imp : trailing 28-day median of the total limit for that HE minus the limit for D (+ = derated)
  cut_imp_ny/mi/pq  : same, by intertie
Rule test: each month, pick on the trailing 90 days the cut threshold (100..1500 MW) and direction with the best mean
DA-RT (>= 40 h, |mean| >= $3), apply it to the next month.  Scored with edge_study.score (bootstrap CI by day)."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, edge_study as E, supply_fc as SF
pd.set_option('display.width', 250)
THR = [100, 250, 500, 750, 1000, 1500]

def frame(zone):
    p = pd.read_csv(C.DATA / 'nrg' / 'hub_prices_nrg.csv'); p = p[p.zone == zone][['date', 'he', 'da', 'rt']]
    L = SF.limits_at_bid()
    a = C.adq2('preDA')[['date', 'he', 'head', 'dem_fc']]
    d = p.merge(L, on=['date', 'he'], how='left').merge(a, on=['date', 'he'], how='left').sort_values(['date', 'he'])
    d['sp'] = d.da - d.rt
    for c in ['exp_cap', 'imp_cap', 'imp_ny', 'imp_mi', 'imp_pq', 'exp_ny', 'exp_mi', 'exp_pq']:
        w = d.pivot_table(index='date', columns='he', values=c)
        med = w.shift(1).rolling(28, min_periods=10).median()
        cut = (med - w).stack().rename('cut_' + c.replace('_cap', '')).reset_index()
        d = d.merge(cut, on=['date', 'he'], how='left')
    for tag, f in (('pd', 'pd_intertie_limits.csv'), ('rt', 'rt_intertie_limits.csv')):   # after the deadline: diagnostics only
        r = C.DATA / 'nrg' / f
        if not r.exists(): continue
        x = pd.read_csv(r); ex = [c for c in x if c.endswith('_EXP')]; im = [c for c in x if c.endswith('_IMP')]
        x[f'{tag}_exp_cap'] = -x[ex].sum(axis=1); x[f'{tag}_imp_cap'] = x[im].sum(axis=1)
        d = d.merge(x[['date', 'he', f'{tag}_exp_cap', f'{tag}_imp_cap']], on=['date', 'he'], how='left')
        d[f'{tag}_imp_surprise'] = d.imp_cap - d[f'{tag}_imp_cap']; d[f'{tag}_exp_surprise'] = d.exp_cap - d[f'{tag}_exp_cap']
    return d

def buckets(d, col):
    b = pd.cut(d[col], [-1e9, -100, 100, 250, 500, 1000, 1e9], labels=['up>100', '~0', '100-250', '250-500', '500-1000', '>1000'])
    g = d.dropna(subset=['sp']).groupby(b)
    return pd.DataFrame({'hours': g.sp.size(), 'mean_DA-RT': g.sp.mean().round(2), 'median': g.sp.median().round(2),
                         'RT>DA+50 %': g.apply(lambda x: ((x.rt - x.da) > 50).mean() * 100).round(1), 'days': g.date.nunique()})

def walk(d, col, start='2025-08-01'):
    d = d.copy(); d['mo'] = d.date.str[:7]; out = []
    for mo in sorted(d.mo.unique()):
        if mo + '-01' < start: continue
        lo = (pd.Timestamp(mo + '-01') - pd.Timedelta(days=90)).date().isoformat()
        tr = d[(d.date >= lo) & (d.date < mo + '-01')].dropna(subset=['sp', col])
        best = None
        for t in THR:
            m = tr[tr[col] >= t]
            if len(m) >= 40 and abs(m.sp.mean()) >= 3 and (best is None or abs(m.sp.mean()) > abs(best[1])): best = (t, m.sp.mean())
        te = d[d.mo == mo].copy()
        te['sig'] = 0 if best is None else np.where(te[col] >= best[0], np.sign(best[1]), 0)
        te['thr'] = None if best is None else best[0]; out.append(te)
    return pd.concat(out)

if __name__ == '__main__':
    for z in (sys.argv[1:] or ['TORONTO', 'SOUTHWEST']):
        d = frame(z); d.to_csv(C.DATA / f'ls_frame_{z}.csv', index=False)
        print(f'\n===== {z}: {d.date.nunique()} days {d.date.min()}..{d.date.max()} =====')
        for c in ['cut_imp', 'cut_exp', 'cut_imp_ny', 'cut_imp_mi', 'cut_imp_pq', 'cut_exp_ny']:
            print(f'\n-- {c} (+ = derated vs 28-day norm) --'); print(buckets(d, c).to_string())
        t = d['head'] < 8000
        print('\n-- cut_imp split by tightness (headroom < 8000 MW) --')
        print('tight:'); print(buckets(d[t], 'cut_imp').to_string()); print('not tight:'); print(buckets(d[~t & d['head'].notna()], 'cut_imp').to_string())
        print('\n-- cut_exp split by tightness --'); print('tight:'); print(buckets(d[t], 'cut_exp').to_string()); print('not tight:'); print(buckets(d[~t & d['head'].notna()], 'cut_exp').to_string())
        for tag in ('pd', 'rt'):
            for side in ('imp', 'exp'):
                c = f'{tag}_{side}_surprise'
                if c in d: print(f'\n-- {tag.upper()} {side}ort limit below the DA limit (post-deadline derate, NOT known at bid) --'); print(buckets(d, c).to_string())
        R = []
        for c in ['cut_imp', 'cut_exp', 'cut_imp_ny', 'cut_imp_mi', 'cut_imp_pq']:
            w = walk(d, c); R.append(E.score(w, f'walk {c} (sign learned)', w.sig))
            R[-1]['thr_used'] = str(w.groupby('mo').thr.first().value_counts().to_dict())
        R = pd.DataFrame(R); R.to_csv(C.DATA / f'ls_rules_{z}.csv', index=False)
        print('\n-- walk-forward (Aug 2025 on) --'); print(R.to_string(index=False))

def walk_buy(d, heads=(6000, 7000, 8000, 9000), cuts=(500, 750, 1000), look=180, start='2025-09-01'):
    """Long-side rule: BUY when headroom < H and total export limit derated >= X vs its 28-day norm.
    Each month (H, X) is re-picked on the trailing `look` days: most negative mean DA-RT with >= 30 h, and only if <= -$5."""
    d = d.copy(); d['mo'] = d.date.str[:7]; out = []
    for mo in sorted(d.mo.unique()):
        if mo + '-01' < start: continue
        lo = (pd.Timestamp(mo + '-01') - pd.Timedelta(days=look)).date().isoformat()
        tr = d[(d.date >= lo) & (d.date < mo + '-01')].dropna(subset=['sp', 'head', 'cut_exp'])
        best = None
        for H in heads:
            for X in cuts:
                m = tr[(tr['head'] < H) & (tr.cut_exp >= X)]
                if len(m) >= 30 and m.sp.mean() <= -5 and (best is None or m.sp.mean() < best[2]): best = (H, X, m.sp.mean())
        te = d[d.mo == mo].copy()
        te['sig'] = 0 if best is None else np.where((te['head'] < best[0]) & (te.cut_exp >= best[1]), -1, 0)
        te['rule'] = None if best is None else f'head<{best[0]} & cut_exp>={best[1]}'; out.append(te)
    return pd.concat(out)
