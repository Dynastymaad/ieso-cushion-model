# Nov 5 2026: can the temperature -> load numbers be trusted? (1) raw buckets, no fitting  (2) same season, different years  (3) how the numbers moved month by month
import sys; sys.path.insert(0, '.'); import numpy as np, pandas as pd, temp_conv as TC
x = TC.frame(); f = x[x.same & x.dL.notna() & x.dH.notna() & x.dK.notna()].copy(); f['yr'] = f.date.str[:4]; f['mo'] = f.date.str[5:7].astype(int)
print('pairs', len(f), f.date.min(), f.date.max())
print('\n(1) Raw: winter evenings HE16-21, both days below 15 C. Change in temperature (D minus 2 days earlier) vs average change in load')
g = f[(f.season == 'Winter') & (f.blk == 'HE16-21') & (f.dK == 0) & (f.t_act < 15) & (f.t_act_2 < 15)].copy(); g['dT'] = g.t_act - g.t_act_2
b = g.groupby(pd.cut(g.dT, [-15, -8, -5, -3, -1, 1, 3, 5, 8, 15]), observed=True).agg(hours=('dL', 'size'), load_change=('dL', 'mean'), temp_change=('dT', 'mean'))
b['MW_per_C'] = (b.load_change / b.temp_change).where(b.temp_change.abs() > 1.5); print(b.round(0).to_string())
print('\n(1b) Raw: summer evenings HE16-21, both days feels-like above 20 C')
g = f[(f.season == 'Summer') & (f.blk == 'HE16-21') & (f.dH == 0) & (f.feel_act > 20) & (f.feel_act_2 > 20)].copy(); g['dT'] = g.feel_act - g.feel_act_2
b = g.groupby(pd.cut(g.dT, [-15, -6, -4, -2, -0.5, 0.5, 2, 4, 6, 15]), observed=True).agg(hours=('dL', 'size'), load_change=('dL', 'mean'), feels_change=('dT', 'mean'))
b['MW_per_C'] = (b.load_change / b.feels_change).where(b.feels_change.abs() > 1.5); print(b.round(0).to_string())
print('\n(2) Same season, different years (MW per C; heat = per C colder below 15, cool = per C hotter feels-like above 20; blank = under 150 h of that weather)')
def row(g):
    out = {}
    for _, _, bk in TC.BLK:
        h, c = TC._coef(g[g.blk == bk]); out[bk] = f"{'' if np.isnan(h) else round(h, -1):>5} / {'' if np.isnan(c) else round(c, -1):<5}"
    return out
R = {}
for lab, k in [('Spring 2025 (Apr-May)', (f.yr == '2025') & f.mo.isin([4, 5])), ('Spring 2026 (Apr-May)', (f.yr == '2026') & f.mo.isin([4, 5])),
               ('Summer 2025', (f.yr == '2025') & (f.season == 'Summer')), ('Summer 2026', (f.yr == '2026') & (f.season == 'Summer')),
               ('Fall 2025 (Sep-Oct)', (f.yr == '2025') & f.mo.isin([9, 10])), ('Fall 2026 (Sep-Oct)', (f.yr == '2026') & f.mo.isin([9, 10])),
               ('Late fall 2025 (Nov)', (f.yr == '2025') & (f.mo == 11)), ('Winter 2025-26', f.season == 'Winter')]:
    R[lab] = row(f[k]); R[lab]['hours'] = int(k.sum())
print(pd.DataFrame(R).T.to_string())
print('\n(3) The numbers as they stood at each month-end (what the model would have used the next month)')
ms = sorted(f.date.str[:7].unique()); rows = []
for m in ms[4:] + ['2026-10']:
    S = TC.slopes(f[f.date.str[:7] < m]); rows.append(dict(month=m, winter_eve_heat=round(S[('Winter', 'HE16-21')][0]), fall_eve_heat=round(S[('Fall', 'HE16-21')][0]),
                summer_eve_cool=round(S[('Summer', 'HE16-21')][1]), summer_night_cool=round(S[('Summer', 'HE1-6')][1]), spring_aft_heat=round(S[('Spring', 'HE11-15')][0])))
print(pd.DataFrame(rows).to_string(index=False))
