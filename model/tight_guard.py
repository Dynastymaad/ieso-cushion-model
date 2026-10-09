"""tight_guard.py -- Oct 8 2026: can bid-time forecasts keep us off the short side on Oct-1/Oct-7-type evenings?
Candidates (fixed, no fitting): Tesla above IESO (gapT > 0); one weather model >= 1,000 MW below IESO wind (nwpmin gap); both.
Ladder-level P&L of tight sells (live score-5 ladder with CAHR A/B repricing) if those hours are skipped. Sep 12 2025 -> Oct 6 2026."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, tesla_rules_bt as TB
pd.set_option('display.width', 250)
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv'); m['gapT'] = m.lf_tesla - m.dem_fc
    t = m[(m.why == 'tight') & (m.date >= '2025-09-12') & (m.date <= '2026-10-06') & m.rt.notna() & m.p_rt.notna() & m.cahr.notna()].copy()
    t['pl'] = [TB.sell_pl(r) for r in t.itertuples()]
    eve = t.he.between(16, 21); g1 = t.gapT > 0; g2 = (t.w_nwp_min - t.wind_fc) <= -1000
    R = [TB.stats(t.pl, t.date, 'all tight sells (live)')]
    for nm, k in (('skip: Tesla > IESO, HE16-21', eve & g1), ('skip: Tesla > IESO, all hours', g1), ('skip: a weather model 1,000+ below IESO wind, HE16-21', eve & g2),
                  ('skip: either, HE16-21', eve & (g1 | g2)), ('skip: Tesla > IESO by 300+, HE16-21', eve & (t.gapT > 300))):
        R.append(TB.stats(t.pl.where(~k, 0), t.date, nm, skipped=int(k.sum()), skipped_pl=round(t.pl[k].sum()), skipped_H2=round(t.pl[k & (t.date >= '2026-02-15')].sum()), skipped_l90=round(t.pl[k & (t.date >= '2026-07-08')].sum())))
    print(f'\n===== {z} (ladder $, base MW 20/30/40) ====='); print(pd.DataFrame(R).to_string(index=False))
    for nm, k in (('Tesla>IESO HE16-21', eve & g1), ('wx model low HE16-21', eve & g2)):
        x = t[k]; print(f'  {nm}: worst skipped days', x.groupby('date').pl.sum().nsmallest(4).round(0).to_dict(), '| best', x.groupby('date').pl.sum().nlargest(3).round(0).to_dict())
