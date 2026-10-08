"""spike_tvu.py -- Oct 7 2026: the biggest recent spikes had Tesla far above its usual gap to IESO (tvu). Test it properly:
precision / RT-DA by tvu bucket, inside sells and outside, both halves. Buy P&L = RT - DA per MW (price-taker)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 260)

def row(x, name):
    pl = x.rd; dd = pl.groupby(x.date).sum(); H = lambda q: round(q.mean(), 1) if len(q) else np.nan
    return dict(group=name, hours=len(x), days=x.date.nunique(), spike50=round(x.spk.mean() * 100) if len(x) else np.nan, rt_gt_da=round((pl > 0).mean() * 100) if len(x) else np.nan,
                mean=H(pl), median=round(pl.median(), 1) if len(x) else np.nan, H1=H(pl[x.date < '2026-02-15']), H2=H(pl[x.date >= '2026-02-15']),
                last90=H(pl[x.date >= '2026-07-08']), n_l90=int((x.date >= '2026-07-08').sum()), top3day_share=f'{dd.nlargest(3).sum()/max(dd.sum(),1e-9)*100:.0f}%' if len(dd) and dd.sum() > 0 else '-')
R = []
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_frame_{z}.csv'); m = m[m.tvu.notna()]
    pk = m.he.between(16, 21); sell = m.why.notna(); tight = m.why == 'tight'
    for lo in (-1e9, 0, 200, 300, 500):
        k = m.tvu >= lo; lab = 'all' if lo < -1e8 else f'tvu>={lo}'
        R.append(dict(zone=z, **row(m[pk & ~sell & k], f'HE16-21 non-sell, {lab}')))
        R.append(dict(zone=z, **row(m[pk & tight & k], f'HE16-21 TIGHT sells, {lab}')))
    R.append(dict(zone=z, **row(m[pk & ~sell & (m.tvu >= 300) & (m['head'] < 9000)], 'HE16-21 non-sell, tvu>=300, head<9k')))
    R.append(dict(zone=z, **row(m[pk & ~sell & (m.tvu >= 300) & (m.cahr >= 10)], 'HE16-21 non-sell, tvu>=300, CAHR>=10')))
    R.append(dict(zone=z, **row(m[~pk & ~sell & (m.tvu >= 300)], 'other hours non-sell, tvu>=300')))
R = pd.DataFrame(R); R.to_csv(C.DATA / 'spike_tvu_2026-10-07.csv', index=False); print(R.to_string(index=False))
m = pd.read_csv(C.DATA / 'spike_frame_EAST.csv'); print('tvu coverage from', m[m.tvu.notna()].date.min(), '; tvu>=300 share of HE16-21 hours', round((m[m.he.between(16,21)].tvu >= 300).mean()*100, 1), '%')
