"""what_matters.py -- Oct 9 2026 (TEST ONLY): which bid-time fundamentals tell us (A) an hour is CHEAP (RT tends to beat DA on
average) and (B) something MIGHT GO WRONG (RT >= DA + $50). Each feature split into quintiles; results adjusted for hour of day
(compare to that HE's own base rate) and checked in both halves. East, Sep 12 2025 - Oct 6 2026."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
m = pd.read_csv(C.DATA / 'spike_feats_EAST.csv'); m = m[(m.date >= '2025-09-12') & m.rt.notna()].copy()
d = pd.read_csv(C.DATA / 'dv_frame_EAST.csv', usecols=['date', 'he', 'gas_hat']).sort_values(['date', 'he']); d['g3'] = d.groupby('date').gas_hat.diff(3)
m = m.merge(d[['date', 'he', 'g3']], on=['date', 'he'], how='left')
m['rd'] = m.rt - m.da; m['spk'] = (m.rd >= 50).astype(float)
m['gapT'] = m.lf_tesla - m.dem_fc; m['sol_r3'] = m.groupby('date').solar_fc.diff(3)
m['prem_fc'] = m.p_da - m.groupby('he').p_da.transform(lambda s: s.rolling(30, min_periods=10).median().shift(1))
F = {'Tesla - IESO load': 'gapT', 'Gas need change 3h (ramp)': 'g3', 'Net-load change 3h': 'resid_ramp3', 'Gas spare': 'gas_spare',
     'Headroom': 'head', 'CAHR (DA fc as heat rate)': 'cahr', 'Our DA fc': 'p_da', 'DA fc vs its 30d median (same HE)': 'prem_fc',
     'Wind forecast': 'wind_fc', 'Wind change 3h': 'wr3', 'IESO wind - models low': 'w_gap_min', 'Wind models spread (sd)': 'w_nwp_sd',
     'Solar change 3h': 'sol_r3', 'Gas outages': 'gas_out', 'Hydro expected': 'hyd_exp', 'Net exports expected': 'exp_exp',
     'Last 7d RT-DA same HE': 'bias7', 'Spikes in last 2-4 days': 'spk_d2_4'}
m['spk_he'] = m.groupby('he').spk.transform('mean'); m['rd_he'] = m.groupby('he').rd.transform('mean')
H1 = m.date < '2026-02-15'; out = []
for nm, c in F.items():
    x = m.dropna(subset=[c]).copy()
    if x[c].nunique() < 5: continue
    x['q'] = pd.qcut(x[c].rank(method='first'), 5, labels=False)
    g = x.groupby('q').agg(lo=(c, 'min'), hi=(c, 'max'), spk=('spk', 'mean'), spk_he=('spk_he', 'mean'), rd=('rd', 'mean'), rd_he=('rd_he', 'mean'))
    lift = (g.spk / g.spk_he); exc = g.rd - g.rd_he
    def half(k):
        y = x[k]; gg = y.groupby('q').agg(s=('spk', 'mean'), sh=('spk_he', 'mean'), r=('rd', 'mean'), rh=('rd_he', 'mean'))
        return (gg.s / gg.sh).iloc[4] - (gg.s / gg.sh).iloc[0], (gg.r - gg.rh).iloc[4] - (gg.r - gg.rh).iloc[0]
    a, b = half(H1.reindex(x.index)), half(~H1.reindex(x.index))
    out.append(dict(feature=nm, spike_low=round(lift.iloc[0], 2), spike_high=round(lift.iloc[4], 2), rd_low=round(exc.iloc[0], 1), rd_high=round(exc.iloc[4], 1),
                    spike_spread=round(lift.iloc[4] - lift.iloc[0], 2), rd_spread=round(exc.iloc[4] - exc.iloc[0], 1),
                    same_sign_halves_spike=bool(np.sign(a[0]) == np.sign(b[0])), same_sign_halves_rd=bool(np.sign(a[1]) == np.sign(b[1])),
                    q1=f'{g.lo.iloc[0]:.0f}..{g.hi.iloc[0]:.0f}', q5=f'{g.lo.iloc[4]:.0f}..{g.hi.iloc[4]:.0f}'))
o = pd.DataFrame(out); o['abs_spk'] = o.spike_spread.abs(); o = o.sort_values('abs_spk', ascending=False)
pd.set_option('display.width', 250); print(o.drop(columns='abs_spk').to_string(index=False))
o.to_csv(C.DATA / 'what_matters_EAST.csv', index=False)
