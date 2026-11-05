# Nov 5 2026: ways to put "gas need under 4,000 MW = big prints are rare" into the scoring. Plan = A/B tiers, 1 MW, side x (RT-DA). Sep 2025 - Nov 5 2026.
import pandas as pd, numpy as np
def tier(score, read):
    s, r = np.sign(score), np.sign(read); a = abs(score) >= 3
    return np.where(a & (s == r), 'A', np.where(a, 'C', np.where(abs(read) >= 5, 'B', 'N'))), np.where(a & (s == r), s, np.where(a, 0, np.where(abs(read) >= 5, r, 0)))
for z in ['EAST', 'OTTAWA']:
    h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['rd']).reset_index(drop=True); m = h.date.str[:7]
    t0, s0 = tier(h.score, h.read); base = pd.Series(np.where(np.isin(t0, ['A', 'B']), s0 * h.rd, 0)); bm = base.groupby(m).sum()
    print(f'\n{z}: current plan ${base.sum():,.0f}')
    for th in (3500, 4000, 4500):
        lo = (h.gas_hat < th).values
        V = {}
        t, s = tier(h.score - lo, h.read); V['card -1'] = np.where(np.isin(t, ['A', 'B']), s * h.rd, 0)
        V['no longs'] = np.where(lo & (base.values != 0) & (s0 > 0), 0, base.values)
        V['longs only if Tier A'] = np.where(lo & (t0 == 'B') & (s0 > 0), 0, base.values)
        V['long card points halved'] = None
        sc = h.score.where(~(lo & (h.score > 0)), np.floor(h.score / 2)); t, s = tier(sc, h.read); V['long card points halved'] = np.where(np.isin(t, ['A', 'B']), s * h.rd, 0)
        for k, v in V.items():
            v = pd.Series(v); vm = v.groupby(m).sum()
            print(f'  gas < {th:,}  {k:25s} ${v.sum():,.0f} ({v.sum()-base.sum():+,.0f}) | months better {(vm>bm+1).sum()}, worse {(vm<bm-1).sum()} | Sep-Dec 2025 {(v-base)[h.date<"2026-01-01"].sum():+,.0f}, 2026 {(v-base)[h.date>="2026-01-01"].sum():+,.0f}')
    lo = h.gas_hat < 4000; ab = np.isin(t0, ['A', 'B'])
    for lab, k in [('longs', ab & (s0 > 0)), ('shorts', ab & (s0 < 0))]:
        for tt in ['A', 'B']:
            q = k & (t0 == tt)
            print(f'  {lab} tier {tt}: gas<4k {(q&lo).sum():4d} h avg ${(s0*h.rd)[q&lo].mean():6.2f} total ${(s0*h.rd)[q&lo].sum():7,.0f} | 4k+ {(q&~lo).sum():4d} h avg ${(s0*h.rd)[q&~lo].mean():6.2f}')
