"""research/true_tight_load.py -- does adding explicit LOAD ramps and deviations improve the fair-RT / gap read?
Adds: IESO load 1h and 3h change, load vs the same hour's 7-day average, Tesla-Dynasty disagreement, and IESO's own recent load miss
(trailing 14-day mean of actual - IESO forecast, same hour, through D-2). Same walk-forward, same scoring as true_tight_ladder."""
import sys, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0, 'model'); sys.path.insert(0, 'model/research')
import numpy as np, pandas as pd, common as C, true_tight as T
from sklearn.linear_model import Ridge
LOADX = ['dl1', 'dl3', 'dem_vs7', 'load_dis', 'ieso_bias14']
def add(e):
    e = e.sort_values(['date', 'he']).copy(); g = e.groupby('date')
    e['dl1'] = e.dem_fc - g.dem_fc.shift(1); e['dl3'] = e.dem_fc - g.dem_fc.shift(3)
    p = e.pivot_table(index='date', columns='he', values='dem_fc'); p.index = pd.to_datetime(p.index); p = p.asfreq('D')
    s = p.shift(1).rolling(7, min_periods=4).mean().stack().rename('d7m').reset_index(); s['date'] = s.date.dt.strftime('%Y-%m-%d'); e = e.merge(s, on=['date', 'he'], how='left')
    e['dem_vs7'] = e.dem_fc - e.d7m
    L = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'ont_dem']]; x = e[['date', 'he', 'dem_fc']].merge(L, on=['date', 'he'], how='left'); x['miss'] = x.ont_dem - x.dem_fc
    q = x.pivot_table(index='date', columns='he', values='miss'); q.index = pd.to_datetime(q.index); q = q.asfreq('D')
    b = q.shift(2).rolling(14, min_periods=7).mean().stack().rename('ieso_bias14').reset_index(); b['date'] = b.date.dt.strftime('%Y-%m-%d')
    return e.merge(b, on=['date', 'he'], how='left')
def walk(e, fe, start='2026-03-02'):
    e['fair'] = np.nan
    for s in pd.date_range(start, e.date.max(), freq='7D'):
        s0 = s.date().isoformat(); s1 = (s + pd.Timedelta(days=6)).date().isoformat(); cut = (s - pd.Timedelta(days=2)).date().isoformat()
        te = (e.date >= s0) & (e.date <= s1); tr = e[(e.date <= cut) & (e.date >= '2026-01-01')].dropna(subset=['hr_rt'])
        X = tr[fe].fillna(tr[fe].median()); mu, sd = X.mean(), X.std().replace(0, 1)
        r = Ridge(alpha=10).fit((X - mu) / sd, tr.hr_rt.clip(0, 30))
        e.loc[te, 'fair'] = r.predict((e.loc[te, fe].fillna(tr[fe].median()) - mu) / sd) * e.loc[te, 'den'] - e.loc[te, 'off']
    return e
for z in ('EAST', 'OTTAWA'):
    base = add(T.frame(z)); res = {}
    for nm, fe in (('current inputs', T.FE), ('+ load ramps & deviations', T.FE + LOADX)):
        e = walk(base.copy(), fe); t = e[(e.date >= '2026-03-02') & e.rt.notna() & e.fair.notna()].copy(); t['gap'] = t.p_da - t.fair
        for q in (.1, .25, .9): t[f't{int(q*100)}'] = np.nan
        for D in sorted(t.date.unique()):
            past = t[(t.date <= (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()) & (t.date > (pd.Timestamp(D) - pd.Timedelta(days=44)).date().isoformat())].gap
            if len(past) > 300:
                for q in (.1, .25, .9): t.loc[t.date == D, f't{int(q*100)}'] = past.quantile(q)
        t = t.dropna(subset=['t90']); x = t.rt - t.da; s = t.gap >= t.t90; l = t.gap <= t.t10
        hi = t.hr_fc >= t.groupby(t.date.str[:7]).hr_fc.transform(lambda v: v.quantile(2 / 3)); tt = hi & (t.gap <= t.t25)
        ms = (-x[s]).groupby(t.date[s].str[:7]).mean(); ml = x[l].groupby(t.date[l].str[:7]).mean()
        print(f'{z} {nm:26s} fair-RT MAE ${(t.fair - t.rt).abs().mean():.1f} | SHORT p90 {int(s.sum())}h ${(-x[s]).mean():+.2f} win {((-x[s])>0).mean()*100:.0f}% months+ {(ms>0).sum()}/{len(ms)}'
              f' | LONG p10 {int(l.sum())}h ${x[l].mean():+.2f} win {(x[l]>0).mean()*100:.0f}% months+ {(ml>0).sum()}/{len(ml)} | truly-tight DA-rich hours: shorts ${(-x[tt]).mean():+.2f} ({int(tt.sum())}h)')
