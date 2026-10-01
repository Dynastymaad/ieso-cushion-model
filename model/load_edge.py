"""load_edge.py -- whose load forecast is best at the DA bid deadline, and does
beating IESO's number predict the RT-DA spread?  Writes notes/load_edge.md."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
def _md(df, idx):
    try: return df.to_markdown(index=idx)
    except ImportError: return df.to_string(index=idx)   # tabulate not installed
import numpy as np, pandas as pd, common as C

act = C.actual_demand()
lf = C.load_forecasts_at_bid()
adq = C.adq2('preDA')[['date', 'he', 'dem_fc']].rename(columns={'dem_fc': 'lf_adq2'})
df = act.merge(adq, on=['date', 'he']).merge(lf, on=['date', 'he'], how='left')
df = df[df.date >= '2025-05-02']
src = [c for c in df.columns if c.startswith('lf_')]
df['month'] = df.date.str.slice(0, 7)
out = []
def stats(g, c):
    m = g[c].notna(); e = g.loc[m, c] - g.loc[m, 'ont_dem']
    return m.sum(), e.abs().mean(), e.mean()
rows = []
for c in src:
    n, mae, bias = stats(df, c); rows.append((c, n, mae, bias))
tab = pd.DataFrame(rows, columns=['source', 'hours', 'MAE', 'bias(fc-act)']).round(0)
# common sample: hours where adq2, tesla, dynasty all present
com = df.dropna(subset=['lf_adq2', 'lf_tesla', 'lf_ieso'])
rows = []
for c in src:
    if com[c].notna().mean() < 0.8: continue
    n, mae, bias = stats(com, c); rows.append((c, n, mae, bias))
tabc = pd.DataFrame(rows, columns=['source', 'hours', 'MAE', 'bias']).round(0)
# monthly MAE, common sample
mon = com.groupby('month').apply(lambda g: pd.Series({c: (g[c] - g.ont_dem).abs().mean() for c in src if com[c].notna().mean() >= 0.8})).round(0)
# the edge: does (vendor - IESO adq2) predict (actual - IESO adq2)?
edge = []
for c in src:
    if c == 'lf_adq2': continue
    g = df.dropna(subset=[c]); x = g[c] - g.lf_adq2; y = g.ont_dem - g.lf_adq2
    big = x.abs() > 300
    edge.append((c, len(g), np.corrcoef(x, y)[0, 1], (np.sign(x[big]) == np.sign(y[big])).mean(), big.sum(),
                 np.polyfit(x, y, 1)[0]))
edge = pd.DataFrame(edge, columns=['source', 'hours', 'corr(src-IESO, act-IESO)', 'sign hit when |gap|>300', 'n |gap|>300', 'slope']).round(3)
# blends: simple average of tesla & dynasty, bias-corrected tesla (trailing 28d per HE)
df = df.sort_values(['date', 'he'])
for c in ['lf_tesla', 'lf_dynasty', 'lf_ieso']:
    if c not in df: continue
    e = (df[c] - df.ont_dem)
    df[c + '_bc'] = df[c] - e.groupby(df.he).transform(lambda s: s.shift(2 * 1).rolling(28, min_periods=10).mean())
df['lf_tes_dyn'] = df[['lf_tesla', 'lf_dynasty']].mean(axis=1, skipna=False)
extra = []
for c in ['lf_tesla_bc', 'lf_dynasty_bc', 'lf_ieso_bc', 'lf_tes_dyn']:
    if c in df:
        n, mae, bias = stats(df.dropna(subset=['lf_adq2']), c); extra.append((c, n, mae, bias))
extra = pd.DataFrame(extra, columns=['source', 'hours', 'MAE', 'bias']).round(0)
df.to_csv(C.DATA / 'load_at_bid.csv', index=False)

md = ['# Load forecasts at the DA bid deadline (D-1 08:00 MT)', '',
      f'Sample {df.date.min()} → {df.date.max()}. Actual = IESO Ontario Demand. `lf_adq2` = the demand forecast in IESO Adequacy2 issued D-1 before 09:00 EST — the number the DA clears on.', '',
      '## All available hours per source', '', tab.pipe(_md, False), '',
      '## Common sample (hours where IESO, Adequacy2 and Tesla all exist)', '', tabc.pipe(_md, False), '',
      '## Monthly MAE, common sample', '', mon.pipe(_md, True), '',
      '## The edge: does a vendor disagreeing with IESO predict IESO\'s miss?', '', edge.pipe(_md, False), '',
      '## Bias-corrected / blended (trailing 28-day bias per HE, lagged 2 days)', '', extra.pipe(_md, False)]
(C.ROOT / 'notes' / 'load_edge.md').write_text('\n'.join(md))
print('\n'.join(md))
