"""morning_long_test.py -- Oct 9 2026 (TEST ONLY): Maad's morning thesis. HE5-9, DA expects an easy ramp (gas need falling over 3 h),
DA cheap, Tesla above IESO -> long (bid DA fc + $30). Does a load/wind miss pay enough to make it work?"""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
RNG = np.random.default_rng(5)
d = pd.read_csv(C.DATA / 'dv_frame_EAST.csv', usecols=['date', 'he', 'gas_hat']).sort_values(['date', 'he'])
d['g3'] = d.groupby('date').gas_hat.diff(3)
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv').merge(d[['date', 'he', 'g3']], on=['date', 'he'], how='left')
    m = m[(m.date >= '2025-09-12') & m.rt.notna() & m.he.between(5, 9)].copy()
    m['rd'] = m.rt - m.da; L = m.rd.where(m.da <= m.p_da + 30, 0.0); gap = m.lf_tesla - m.dem_fc
    base = L
    def show(nm, k):
        pl = L.where(k, 0); x = pl[k]; dd = pl.groupby(m.date).sum()
        cnt = k[k].groupby(m.date[k].str[:7]).size(); pb = []
        for _ in range(600):
            s = 0.0
            for mo, c in cnt.items():
                v = base[m.date.str[:7] == mo].values; s += v[RNG.choice(len(v), min(c, len(v)), replace=False)].sum()
            pb.append(s)
        print(f"  {nm:44s} {int(k.sum()):4d}h ${x.mean():+6.1f}/MWh win {100*(x>0).mean():3.0f}% total {pl.sum():+7,.0f} | H1 {pl[m.date<'2026-02-15'].sum():+6,.0f} H2 {pl[m.date>='2026-02-15'].sum():+6,.0f} | last120 {pl[m.date>='2026-06-08'].sum():+6,.0f} | w/o best3 {dd.sum()-dd.nlargest(3).sum():+6,.0f} | placebo {(np.array(pb)<pl.sum()).mean()*100:3.0f}%")
    print(f'\n{z}  HE5-9, {len(m)} hours, all-hours long avg ${L.mean():+.1f}/MWh')
    fall = m.g3 <= 0; cheap = m.cahr < 9; tes = gap > 0; tes150 = gap >= 150
    show('all HE5-9', m.he > 0)
    show('gas need falling (3h)', fall)
    show('falling + cheap (CAHR<9)', fall & cheap)
    show('falling + cheap + Tesla>IESO', fall & cheap & tes)
    show('falling + cheap + Tesla>=IESO+150', fall & cheap & tes150)
    show('Tesla>=IESO+150 (any ramp, any price)', tes150)
    show('rising gas need + Tesla>=IESO+150', ~fall & tes150)
