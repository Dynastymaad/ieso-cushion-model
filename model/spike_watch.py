"""spike_watch.py -- Oct 8 2026: a simple, fixed (no fitting) spike-watch score for evening hours we are NOT selling, built only from
factors that showed up in both the long history and the recent weeks:
  +1 headroom 7,000-8,500 (just above the tight line)       +1 CAHR >= 10 (DA already at peaker heat rate)
  +1 Tesla OR Dynasty forecast >= IESO (IESO load under-forecast risk; the one predictable after-bid surprise)
  +1 IESO wind falls >= 150 MW into the hour (3h)
Long = bid DA fc + $30. Reports the payoff shape (avg win vs avg loss, break-even hit rate), not just the average."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 260)
S = pd.read_csv(C.DATA / 'shock_predict_EAST.csv')[['date', 'he', 'gapDyn', 'gapT']]
def shape(x, name):
    b = x[x.da <= x.p_da + 30]; pl = b.rt - b.da; w, l = pl[pl > 0], pl[pl <= 0]; dd = pl.groupby(b.date).sum()
    H = lambda q: round(q.mean(), 1) if len(q) else np.nan
    return dict(group=name, hours=len(b), days=b.date.nunique(), per_mwh=H(pl), win_pct=round(len(w) / max(len(pl), 1) * 100), avg_win=H(w), avg_loss=H(l),
                breakeven_win_pct=round(-l.mean() / (w.mean() - l.mean()) * 100) if len(w) and len(l) else np.nan, spikes50=int((pl >= 50).sum()),
                H1=H(pl[b.date < '2026-02-15']), H2=H(pl[b.date >= '2026-02-15']), last90=H(pl[b.date >= '2026-07-08']), since_aug15=H(pl[b.date >= '2026-08-15']),
                ex_top5days=round(pl.sum() - dd.nlargest(5).sum()) if len(dd) else np.nan, months_pos=f'{(pl.groupby(b.date.str[:7]).sum() > 0).sum()}/{b.date.str[:7].nunique()}')
R = []
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv').merge(S, on=['date', 'he'], how='left')
    m = m[(m.date >= '2025-09-12') & (m.date <= '2026-10-06') & m.rt.notna() & m.why.isna() & m.he.between(16, 21)].copy()
    m['f_head'] = m['head'].between(7000, 8500); m['f_cahr'] = m.cahr >= 10; m['f_load'] = (m.gapT >= 0) | (m.gapDyn >= 0); m['f_wind'] = m.wr3 <= -150
    m['score'] = m[['f_head', 'f_cahr', 'f_load', 'f_wind']].sum(axis=1)
    R.append(dict(zone=z, **shape(m, 'all evening non-sell (no filter)')))
    for s in range(5): R.append(dict(zone=z, **shape(m[m.score == s], f'score = {s}')))
    R.append(dict(zone=z, **shape(m[m.score >= 2], 'score >= 2'))); R.append(dict(zone=z, **shape(m[m.score >= 3], 'score >= 3')))
    for f in ('f_head', 'f_cahr', 'f_load', 'f_wind'): R.append(dict(zone=z, **shape(m[m[f]], f'  {f} alone')))
    if z == 'EAST':
        rec = m[(m.date >= '2026-08-15') & (m.score >= 3)]; print('EAST score>=3 since Aug 15:', rec.groupby('date').apply(lambda g: f"HE{g.he.min()}-{g.he.max()} {(g.rt-g.da).sum():+.0f}").to_dict())
R = pd.DataFrame(R); R.to_csv(C.DATA / 'spike_watch_2026-10-08.csv', index=False); print(R.to_string(index=False))
