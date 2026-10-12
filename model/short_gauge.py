"""short_gauge.py -- Oct 9 2026 (TEST/INFO): risk-reward of a SHORT by bid-time fundamentals. Short P&L = DA - RT per MWh.
Rich DA = CAHR >= 10 or headroom < 7,000 or DA fc >= its 30-day median + $10. Risk signs = Tesla >= IESO+150 | IESO wind falling
200+ MW over 3 h | gas need rising 500+ MW over 3 h. East (and Ottawa check), Sep 12 2025 - Oct 8 2026, all hours."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
d = pd.read_csv(C.DATA / 'dv_frame_EAST.csv', usecols=['date', 'he', 'gas_hat']).sort_values(['date', 'he']); d['g3'] = d.groupby('date').gas_hat.diff(3)
out = []
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv').merge(d[['date', 'he', 'g3']], on=['date', 'he'], how='left')
    m = m.sort_values(['he', 'date']); m['med30'] = m.groupby('he').p_da.transform(lambda s: s.rolling(30, min_periods=10).median().shift(1))
    m = m[(m.date >= '2025-09-12') & m.rt.notna() & m.da.notna()].copy()
    m['pl'] = m.da - m.rt
    rich = (m.cahr >= 10) | (m['head'] < 7000) | (m.p_da >= m.med30 + 10)
    n = ((m.lf_tesla - m.dem_fc) >= 150).astype(int) + (m.wr3 <= -200).astype(int) + (m.g3 >= 500).astype(int)
    m['rich'] = np.where(rich, 'DA rich', 'DA normal/cheap'); m['signs'] = np.where(n >= 2, '2-3 signs', np.where(n == 1, '1 sign', 'no sign'))
    for (a, b), g in m.groupby(['rich', 'signs']):
        w = g.pl[g.pl > 0]; l = -g.pl[g.pl < 0]; dd = g.groupby('date').pl.sum()
        out.append(dict(zone=z, da=a, signs=b, hours=len(g), avg=round(g.pl.mean(), 1), win=round((g.pl > 0).mean() * 100), avg_win=round(w.mean(), 1), avg_loss=round(l.mean(), 1),
                        loss50=round((g.pl <= -50).mean() * 100, 1), p95_loss=round(-g.pl.quantile(0.05), 0), pf=round(w.sum() / l.sum(), 2),
                        h1=round(g[g.date < '2026-02-15'].pl.mean(), 1), h2=round(g[g.date >= '2026-02-15'].pl.mean(), 1), last120=round(g[g.date >= '2026-06-08'].pl.mean(), 1)))
o = pd.DataFrame(out); pd.set_option('display.width', 250); print(o.to_string(index=False)); o.to_csv(C.DATA / 'short_gauge.csv', index=False)
