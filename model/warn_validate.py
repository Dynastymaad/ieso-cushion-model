"""warn_validate.py -- Oct 9 2026 (TEST ONLY): can the 'pays longs' evening warning signs be traded?
Signs (bid-time, HE16-21): A windy (>=1,500) & wind falling 300+ over 3h | B Tesla>IESO & sunset hour (or next) | C wind falling 300+ |
D Tesla or Dynasty 200+ above IESO. Actions: LONG in flagged hours (bid DA fc + $30), and SKIP the model's sell in flagged hours.
Checks: total, halves, last 120 days, without best 3 days, placebo (same count per month, random evening hours), both zones."""
import sys, math; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, spike_anatomy as SA
pd.set_option('display.width', 250); RNG = np.random.default_rng(9)
S = pd.read_csv(C.DATA / 'shock_predict_EAST.csv')[['date', 'he', 'gapDyn']]
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv').merge(S, on=['date', 'he'], how='left')
    m = m[(m.date >= '2025-09-12') & (m.date <= '2026-10-06') & m.rt.notna() & m.he.between(16, 21)].copy()
    m['gapT'] = m.lf_tesla - m.dem_fc; m['rd'] = m.rt - m.da
    ss = {d: SA.sunset_est(d) for d in m.date.unique()}; sh = m.date.map(lambda d: int(math.floor(ss[d])) + 1); m['dusk'] = (m.he >= sh) & (m.he <= sh + 1)
    m['long'] = np.where(m.da <= m.p_da + 30, m.rd, 0.0); sell = m.why.notna()
    F = {'A windy & falling 300+': (m.wind_fc >= 1500) & (m.wr3 <= -300), 'B Tesla>IESO & sunset hr': (m.gapT > 0) & m.dusk,
         'C wind falling 300+': m.wr3 <= -300, 'D Tesla/Dynasty 200+ > IESO': (m.gapT > 200) | (m.gapDyn > 200)}
    print(f'\n=========== {z}: evening hours {len(m)} ===========')
    for n, k in F.items():
        out = {}
        for act, pl in (('LONG all flagged', m.long.where(k, 0)), ('skip model SELLS flagged', (-(m.da - m.rt)).where(k & sell, 0))):
            d = pl.groupby(m.date).sum(); x = pl[pl != 0] if act.startswith('skip') else pl[k]
            cnt = k[k].groupby(m.date[k].str[:7]).size(); base = m.long if act.startswith('LONG') else (-(m.da - m.rt)).where(sell, 0)
            pb = []
            for _ in range(1500):
                s = 0.0
                for mo, c in cnt.items():
                    v = base[m.date.str[:7] == mo].values; s += v[RNG.choice(len(v), min(c, len(v)), replace=False)].sum()
                pb.append(s)
            out[act] = f"total {pl.sum():+7,.0f} | H1 {pl[m.date < '2026-02-15'].sum():+6,.0f} H2 {pl[m.date >= '2026-02-15'].sum():+6,.0f} | last120 {pl[m.date >= '2026-06-08'].sum():+6,.0f} | w/o best3 days {d.sum() - d.nlargest(3).sum():+7,.0f} | placebo beats {(np.array(pb) < pl.sum()).mean()*100:3.0f}%"
        print(f'{n} ({int(k.sum())} h, {m.date[k].nunique()} d):'); [print('   ', a, '|', v) for a, v in out.items()]
