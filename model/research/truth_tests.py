# Nov 5 2026: test every claim made about how DA is built and what moves RT-DA. Bid-time inputs only where a claim is about the bid.
import sys; sys.path.insert(0, 'model'); import pandas as pd, numpy as np, common as C, signals_v2 as SV
pd.set_option('display.width', 250)
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False).dropna(subset=['rd']).drop(columns=['tot_flow'], errors='ignore')
o = pd.read_csv('data/research/physics_history_OTTAWA.csv', low_memory=False).dropna(subset=['rd'])[['date', 'he', 'rd']].rename(columns={'rd': 'rd_o'})
h = h.merge(o, on=['date', 'he'], how='left')
f = C.adq2('final').rename(columns={'dem_fc': 'dem_final'})
fa = pd.read_csv(C.CACHE / 'ieso_adq2_final.csv'); fa['k'] = fa.subtype; fa = fa[fa.resourcetype == 'Internal Resource'].pivot_table(index=['date', 'hour'], columns='k', values='value').reset_index().rename(columns={'hour': 'he'})
sch = [c for c in fa.columns if c.endswith('Schedule')]; fa['da_supply'] = fa[sch].sum(axis=1, min_count=3); fa = fa[['date', 'he', 'da_supply', 'Wind Schedule', 'Gas Schedule'] + [c for c in sch if c not in ('Wind Schedule', 'Gas Schedule')]]
s = SV.schedules(); s['date'] = s.date.astype(str)
it = pd.read_csv(C.DATA / 'intertie_actual.csv')[['date', 'he', 'tot_flow']]; it['date'] = it.date.astype(str)
of = pd.read_csv(C.DATA / 'outage_features.csv')[['date', 'he', 'add_after']]; of['date'] = of.date.astype(str)
x = h.merge(f[['date', 'he', 'dem_final']], on=['date', 'he'], how='left').merge(fa, on=['date', 'he'], how='left').merge(s, on=['date', 'he'], how='left').merge(it, on=['date', 'he'], how='left').merge(of, on=['date', 'he'], how='left')
x['lm'] = x.ont_dem - x.dem_fc; x['wm'] = x.g_wind - x.wind_fc; x['ich'] = x.tot_flow - x.da_net_exp
print('rows', len(x), x.date.min(), x.date.max())

print('\n### CLAIM 1: IESO pre-DA load forecast runs high (actual - IESO < 0)')
print(f'  all hours: mean {x.lm.mean():+.0f} MW, median {x.lm.median():+.0f}, IESO above actual in {100*(x.lm<0).mean():.0f}% of hours')
x['mo'] = x.date.str[:7]; mm = x.groupby('mo').lm.mean().round(0); print('  by month:', ' '.join(f'{k[2:]}:{v:+.0f}' for k, v in mm.items()))
x['blk'] = pd.cut(x.he, [0, 6, 15, 21, 24], labels=['HE1-6', 'HE7-15', 'HE16-21', 'HE22-24']); print('  by block:', x.groupby('blk', observed=True).lm.mean().round(0).to_dict())
for c, n in [('lf_tesla', 'Tesla'), ('lf_dynasty', 'Dynasty'), ('lf_meteologica', 'Meteologica')]:
    k = x[x[c].notna()]; print(f'  {n:11s} bias {(k.ont_dem-k[c]).mean():+5.0f} MW on its {len(k)} h (IESO on same hours {(k.ont_dem-k.dem_fc).mean():+.0f})')

print('\n### CLAIM 2: DA clears against IESO\'s own (average) load forecast')
k = x.dropna(subset=['da_supply', 'da_net_exp']).copy(); k['da_load'] = k.da_supply - k.da_net_exp
for n, c in [('IESO pre-DA forecast (at the bid)', 'dem_fc'), ('IESO post-DA forecast', 'dem_final'), ('actual Ontario demand', 'ont_dem')]:
    d = k.da_load - k[c]; print(f'  DA supply - DA net exports  vs {n:34s}: mean diff {d.mean():+6.0f}, avg abs diff {d.abs().mean():5.0f}, corr {k.da_load.corr(k[c]):.3f}')
r = np.linalg.lstsq(np.c_[np.ones(len(k)), k.dem_fc, k.ont_dem - k.dem_fc], k.da_load, rcond=None)[0]
print(f'  regression DA-implied load = {r[0]:.0f} + {r[1]:.3f} x IESO forecast + {r[2]:.3f} x (actual - IESO forecast)   [claim holds if the last number is ~0]')

print('\n### CLAIM 3: RT settles below DA on average, and IESO\'s high load forecast explains it')
for z, c in [('East', 'rd'), ('Ottawa', 'rd_o')]:
    k = x[x[c].notna() & x.lm.notna() & x.wm.notna()]; b = np.linalg.lstsq(np.c_[np.ones(len(k)), k.lm / 100, k.wm / 100], k[c].clip(-300, 300), rcond=None)[0]
    print(f'  {z}: mean RT-DA {k[c].mean():+.2f}, median {k[c].median():+.2f}, RT below DA in {100*(k[c]<0).mean():.0f}% of hours | capped-at-$300 fit: RT-DA = {b[0]:+.2f} + {b[1]:+.2f}/100 MW load miss + {b[2]:+.2f}/100 MW wind miss')
    k2 = k[k.lm.abs() < 100]; print(f'     hours where IESO load was within 100 MW: mean RT-DA {k2[c].mean():+.2f} (median {k2[c].median():+.2f}, n {len(k2)})')
    for lab, s_ in [('IESO too high (lm<-200)', k.lm < -200), ('IESO about right', k.lm.abs() <= 200), ('IESO too low (lm>200)', k.lm > 200)]: print(f'     {lab:24s} RT below DA {100*(k[c][s_]<0).mean():.0f}%, mean {k[c][s_].mean():+.2f}')

print('\n### CLAIM 4: the four after-bid surprises matter about equally (East)')
k = x.dropna(subset=['lm', 'wm', 'add_after', 'ich']).copy(); k['y'] = k.rd.clip(-300, 300)
F = {'load miss': k.lm, 'wind miss (minus)': -k.wm, 'outages added after bid': k.add_after.fillna(0), 'intertie change (more export)': k.ich}
Z = pd.DataFrame({n: (v - v.mean()) / v.std() for n, v in F.items()}); A = np.c_[np.ones(len(k)), Z.values]; b, *_ = np.linalg.lstsq(A, k.y, rcond=None)
full = 1 - ((k.y - A @ b) ** 2).sum() / ((k.y - k.y.mean()) ** 2).sum(); print(f'  {len(k)} h, {k.date.min()}..{k.date.max()}, all four explain {100*full:.1f}% of RT-DA (capped)')
for i, n in enumerate(F):
    A2 = np.delete(A, i + 1, axis=1); b2, *_ = np.linalg.lstsq(A2, k.y, rcond=None); r2 = 1 - ((k.y - A2 @ b2) ** 2).sum() / ((k.y - k.y.mean()) ** 2).sum()
    top = F[n] >= F[n].quantile(.9); print(f'  {n:31s} $ per 1 std {b[i+1]:+6.2f} | 1 std = {F[n].std():5.0f} MW | adds {100*(full-r2):4.1f} pts of R2 | worst 10%: RT $50+ above DA {100*(k.rd[top]>=50).mean():4.1f}% (all {100*(k.rd>=50).mean():.1f}%)')
k.to_csv('data/research/truth_frame.csv', index=False)
