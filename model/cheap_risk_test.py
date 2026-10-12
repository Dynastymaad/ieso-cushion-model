"""cheap_risk_test.py -- Oct 9 2026 (TEST ONLY): 'cheap hour + something might go wrong' long, vs the headroom buy band.
Cheap = our DA forecast below its own 30-day median for that HE (known at the bid). Risk = Tesla >= IESO+150 or wind falling
>= 200 MW over 3 h or gas need rising >= 500 MW over 3 h. Long bid = DA fc + $30, non-sell hours. Both zones."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
RNG = np.random.default_rng(3)
d = pd.read_csv(C.DATA / 'dv_frame_EAST.csv', usecols=['date', 'he', 'gas_hat']).sort_values(['date', 'he']); d['g3'] = d.groupby('date').gas_hat.diff(3)
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv').merge(d[['date', 'he', 'g3']], on=['date', 'he'], how='left')
    m = m.sort_values(['he', 'date']); m['med30'] = m.groupby('he').p_da.transform(lambda s: s.rolling(30, min_periods=10).median().shift(1))
    m = m[(m.date >= '2025-09-12') & m.rt.notna()].sort_values(['date', 'he']).reset_index(drop=True)
    m['rd'] = m.rt - m.da; L = m.rd.where(m.da <= m.p_da + 30, 0.0); sell = (m.why.notna()) | (m.v2 == 1)
    cheap = m.p_da < m.med30; gapT = m.lf_tesla - m.dem_fc
    r_t = gapT >= 150; r_w = m.wr3 <= -200; r_g = m.g3 >= 500; risk = r_t | r_w | r_g
    def show(nm, k):
        pl = L.where(k, 0); x = pl[k]; dd = pl.groupby(m.date).sum()
        cnt = k[k].groupby(m.date[k].str[:7]).size(); pb = []
        for _ in range(500):
            s = 0.0
            for mo, c in cnt.items():
                v = L[(m.date.str[:7] == mo) & ~sell].values; s += v[RNG.choice(len(v), min(c, len(v)), replace=False)].sum()
            pb.append(s)
        print(f"  {nm:40s} {int(k.sum()):5d}h ${x.mean():+6.1f}/MWh win {100*(x>0).mean():3.0f}% total {pl.sum():+8,.0f} | H1 {pl[m.date<'2026-02-15'].sum():+7,.0f} H2 {pl[m.date>='2026-02-15'].sum():+7,.0f} | last120 {pl[m.date>='2026-06-08'].sum():+6,.0f} last60 {pl[m.date>='2026-08-07'].sum():+6,.0f} | w/o best3 {dd.sum()-dd.nlargest(3).sum():+7,.0f} | placebo {(np.array(pb)<pl.sum()).mean()*100:3.0f}%")
    print(f'\n=== {z} ===')
    show('headroom buy band 9.5-11.5k (fixed)', m['head'].between(9500, 11500) & ~sell)
    show('cheap (DA fc < its 30d median)', cheap & ~sell)
    show('risk (Tesla+150 | wind -200 | gas +500)', risk & ~sell)
    show('cheap + risk', cheap & risk & ~sell)
    show('cheap + Tesla>=IESO+150', cheap & r_t & ~sell)
    show('cheap + wind falling 200+', cheap & r_w & ~sell)
    show('cheap + gas need +500/3h', cheap & r_g & ~sell)
    show('cheap + risk, evening HE16-21', cheap & risk & ~sell & m.he.between(16, 21))
    show('cheap + risk, other hours', cheap & risk & ~sell & ~m.he.between(16, 21))
    show('NOT cheap + risk', ~cheap & risk & ~sell)
