"""cahr_test.py -- Oct 7 2026: carbon-adjusted heat rate (cahr.py) vs our live signals, both zones.
Signals rebuilt as live (sells 90-day thresholds, buy band 120 days). Price-taker DA-RT per MW, Sep 2025 -> Oct 6 2026.
Fixed physical bins (no fitting) plus the 60-day same-HE percentile used in hr_test.py for comparison."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, cahr as K, hr_test as H, hr_test2 as H2

BINS = [-1, 7.5, 9, 10, 12, 999]; LBL = ['<7.5 (CCGT)', '7.5-9', '9-10', '10-12 (peaker)', '>12 (scarcity)']
R, F = [], []
for z in ('EAST', 'OTTAWA'):
    e = pd.read_csv(C.DATA / f'dv_frame_{z}.csv'); e['sp'] = e.da - e.rt
    e['why'] = H2.walk_why(e); e = K.add(e); e['cahr_p'] = H.pct_walk(e, 'cahr')
    t = e[(e.date >= '2025-09-01') & e.rt.notna()].copy(); t['bin'] = pd.cut(t.cahr, BINS, labels=LBL)
    t.assign(zone=z)[['zone', 'date', 'he', 'da', 'rt', 'sp', 'p_da', 'head', 'why', 'buyband', 'gas_cad', 'cp', 'cahr', 'cahr_p', 'bin']].to_csv(C.DATA / f'cahr_frame_{z}.csv', index=False)
    sell = t.why != ''; bb = ~sell & (t.buyband == -1)
    groups = {'tight sells': t.why == 'tight', 'surplus sells': t.why == 'surplus', 'buy band': bb, 'no signal': ~sell & ~bb}
    for g, m in groups.items():
        side = -1 if g == 'buy band' else 1
        for b in LBL:
            R.append(dict(zone=z, group=g, cahr=b, **{k: v for k, v in H.sc(t, '', np.where(m & (t.bin == b), side, 0)).items() if k != 'rule'}))
    base = np.where(sell, 1.0, np.where(bb, -1.0, 0)); F.append(dict(zone=z, **H.sc(t, 'LIVE sells + buys', base)))
    for thr in (7.5, 8.0):
        s = np.where(sell, 1.0, np.where(bb & (t.cahr >= thr), -1.0, 0)); F.append(dict(zone=z, **H.sc(t, f'buy band only if CAHR >= {thr}', s)))
    s = np.where(sell, 1.0, np.where(bb & (t.cahr_p >= 20), -1.0, 0)); F.append(dict(zone=z, **H.sc(t, 'buy band only if CAHR pct >= 20', s)))
    for thr in (10, 12):
        a = (t.why == 'tight') & (t.cahr >= thr)
        F.append(dict(zone=z, **H.sc(t, f'A-grade: tight & CAHR >= {thr}', np.where(a, 1, 0))))
        F.append(dict(zone=z, **H.sc(t, f'  other tight (CAHR < {thr})', np.where((t.why == 'tight') & ~a, 1, 0))))
    a = (t.why == 'tight') & (t.cahr_p > 80); F.append(dict(zone=z, **H.sc(t, 'A-grade: tight & CAHR pct > 80', np.where(a, 1, 0))))
    print(z, 'CAHR pct of hours by bin:', (t.bin.value_counts(normalize=True).reindex(LBL) * 100).round(1).to_dict())
R = pd.DataFrame(R); F = pd.DataFrame(F)
R.to_csv(C.DATA / 'cahr_test_bins_2026-10-07.csv', index=False); F.to_csv(C.DATA / 'cahr_test_rules_2026-10-07.csv', index=False)
pd.set_option('display.width', 220); print(R.drop(columns=['win']).to_string(index=False)); print(F.to_string(index=False))
