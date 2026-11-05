# Nov 5 2026: temperature as a card point. Bid-safe temps only: Open-Meteo pd2 (run ~48 h before the hour, published before D-1 08:00 MT),
# Ontario load-weighted (data/wx/wx_hourly.csv from model/wx_bid.py; Apr 2025 - Sep 30 2026). The Warehouse only keeps ~3 weeks of forecast vintages.
#  T1 temperature-implied load (model on past bid-time temps, refit weekly, data through D-2) minus IESO load forecast: +-300 MW -> +-1
#  T2 temperature swing: forecast vs the actual two days earlier, turned into MW with the season slope: +-250 MW -> +-1
#  T3 extreme temperature (load-weighted <= -15 C or >= 30 C) -> +1
import pandas as pd, numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor as HGB
w = pd.read_csv('data/wx/wx_hourly.csv')
for c in ['t_fc', 't_act', 'feel_fc', 'dp_fc']: w[c] = (w[c] - 32) * 5 / 9
a2 = w[['date', 'he', 't_act']].copy(); a2['date'] = (pd.to_datetime(a2.date) + pd.Timedelta(days=2)).dt.date.astype(str)
w = w.merge(a2.rename(columns={'t_act': 't_act_d2'}), on=['date', 'he'], how='left')
L = pd.read_csv('data/load_at_bid.csv')[['date', 'he', 'ont_dem', 'lf_adq2']].merge(w, on=['date', 'he'], how='inner').sort_values(['date', 'he'])
L['dow'] = pd.to_datetime(L.date).dt.dayofweek; L['mo'] = pd.to_datetime(L.date).dt.month
lvl = L.groupby('date').ont_dem.mean(); L['lvl2'] = L.date.map(lvl.shift(2))
X = ['t_fc', 'feel_fc', 'dp_fc', 'cc_fc', 'he', 'dow', 'mo', 'lvl2']; L['impl'] = np.nan
days = sorted(L.date.unique())
for i in range(60, len(days), 7):
    tr = L[(L.date <= days[i - 2]) & L.ont_dem.notna()]; te = L.date.isin(days[i:i + 7])
    L.loc[te, 'impl'] = HGB(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40).fit(tr[X], tr.ont_dem).predict(L.loc[te, X])
def tier(score, read):
    s, r = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s == r), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s == r), s, np.where(a, 0, np.where(abs(read) >= 5, r, 0)))
def plan(h, sc):
    t, s = tier(sc, h.read); return pd.Series(np.where(np.isin(t, ['A', 'B']), s * h.rd, 0), index=h.index), t
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).merge(L[['date', 'he', 'impl', 't_fc', 't_act_d2']], on=['date', 'he'], how='left')
    h = h.dropna(subset=['rd', 'impl']).copy(); h['m'] = h.date.str[:7]
    mae = lambda c: (h[c] - h.ont_dem).abs().mean(); k = h.lf_meteologica.notna()
    print(f'\n{z} {h.date.min()} to {h.date.max()} ({h.date.nunique()} days) | load MAE (MW): IESO {mae("dem_fc"):.0f}, temperature model {mae("impl"):.0f}'
          f' | hours with Meteologica: IESO {(h.dem_fc-h.ont_dem)[k].abs().mean():.0f}, Meteologica {(h.lf_meteologica-h.ont_dem)[k].abs().mean():.0f}, temp model {(h.impl-h.ont_dem)[k].abs().mean():.0f}')
    gT = h.impl - h.dem_fc; slope = np.where(h.t_fc < 12, -150, np.where(h.t_fc > 18, 300, 0)); dL = slope * (h.t_fc - h.t_act_d2).fillna(0)
    thin = np.where(h.pub_sp < 2500, 2, 1); t1 = np.where(gT >= 300, 1, np.where(gT <= -300, -1, 0))
    P = {'T1 temp-implied load gap +-300 MW': t1, 'T1 same, doubled when spare < 2,500': t1 * thin,
         'T2 temperature swing +-250 MW': np.where(dL >= 250, 1, np.where(dL <= -250, -1, 0)),
         'T3 extreme temperature +1': np.where((h.t_fc <= -15) | (h.t_fc >= 30), 1, 0)}
    base, tb = plan(h, h.score); bm = base.groupby(h.m).sum(); print(f'  base plan ${base.sum():,.0f}')
    for lab, p in P.items():
        f = p != 0; al = np.sign(p[f]) * h.rd[f]; lg = np.sign(h.load_gap[f]); agree = (np.sign(p[f]) == lg)[lg != 0].mean()
        new, tn = plan(h, h.score + p); nm = new.groupby(h.m).sum()
        print(f'  {lab:37s} fires {f.sum():5d} h | alone ${al.mean():6.2f} (clip ${(np.sign(p[f]) * h.rd[f].clip(-150, 150)).mean():5.2f}, right {100*(al>0).mean():.0f}%)'
              f' | agrees w/ load gap {100*agree:.0f}% | plan ${new.sum():,.0f} ({new.sum()-base.sum():+,.0f}) | months better {(nm>bm+1).sum()}/worse {(nm<bm-1).sum()}')
# --- T2 robustness: thresholds, halves, where the gain comes from, and a placebo (same points shuffled across days within the month)
print('\n--- T2 checks')
rng = np.random.default_rng(7)
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).merge(L[['date', 'he', 'impl', 't_fc', 't_act_d2']], on=['date', 'he'], how='left')
    h = h.dropna(subset=['rd', 'impl']).reset_index(drop=True); h['m'] = h.date.str[:7]
    slope = np.where(h.t_fc < 12, -150, np.where(h.t_fc > 18, 300, 0)); dL = slope * (h.t_fc - h.t_act_d2).fillna(0)
    base, tb = plan(h, h.score); first = h.date < '2026-03-15'
    for th in (250, 400, 600):
        p = np.where(dL >= th, 1, np.where(dL <= -th, -1, 0)); new, tn = plan(h, h.score + p); d = new - base
        print(f'{z} T2 +-{th}: fires {int((p!=0).sum())} h, plan {d.sum():+,.0f} (Sep-Mar {d[first].sum():+,.0f}, Mar-Sep {d[~first].sum():+,.0f})')
        if th == 250:
            ch = tn != tb; g = pd.DataFrame(dict(fr=tb[ch], to=tn[ch], d=d[ch])); print(g.groupby(['fr', 'to']).d.agg(['size', 'sum']).round(0).T.to_string())
            ds = h[['date', 'm']].drop_duplicates(); sims = []
            P = pd.DataFrame(dict(date=h.date, he=h.he, p=p))
            for _ in range(40):
                perm = ds.groupby('m').date.transform(lambda x: rng.permutation(x.values)); mp = dict(zip(ds.date, perm))
                q = h[['date', 'he']].assign(src=h.date.map(mp)).merge(P.rename(columns={'date': 'src'}), on=['src', 'he'], how='left').p.fillna(0).values
                sims.append(plan(h, h.score + q)[0].sum() - base.sum())
            sims = np.array(sims); print(f'   placebo (shuffled days): median {np.median(sims):+,.0f}, best {sims.max():+,.0f}, share >= real: {(sims >= d.sum()).mean():.0%}')
