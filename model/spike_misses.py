"""spike_misses.py -- Oct 7 2026: every RT spike (RT-DA >= $50), East/Ottawa, Sep 2025 -> Oct 6 2026. What did the live model do
(caught / band but bid too low / short / no signal), what did the spikes have in common, and can a few bid-time factors pick
out the most likely ones? All features known at the bid (RT through D-2)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV, spike_study as SS
pd.set_option('display.width', 260)

def feats(z):
    m = SS.frame(z); m = m[m.rt.notna() & (m.date >= '2025-09-01')].copy()
    # persistence: spikes in the last days known at the bid (D-2, D-3, D-4)
    day = m.groupby('date').agg(nspk=('spk', 'sum'), maxrd=('rd', 'max'), eve_rd=('rd', lambda s: s.max()))
    day.index = pd.to_datetime(day.index)
    def lag(D, k): 
        x = day.reindex([pd.Timestamp(D) - pd.Timedelta(days=i) for i in range(2, 2 + k)]); return x.nspk.sum(), x.maxrd.max()
    L = {D: lag(D, 3) for D in m.date.unique()}
    m['spk_d2_4'] = m.date.map(lambda d: L[d][0]); m['max_d2_4'] = m.date.map(lambda d: L[d][1])
    # Tesla vs its usual gap (30d median of Tesla - IESO, same HE, through D-2)
    m['usual'] = np.nan
    for he, g in m.groupby('he'):
        s = g.set_index(pd.to_datetime(g.date)).tg
        m.loc[g.index, 'usual'] = s.shift(2).rolling(30, min_periods=10).median().values
    m['tvu'] = m.tg - m.usual
    m['fc_gap'] = m.p_rt - m.p_da
    return m

def status(m):
    st = np.where(m.why.notna(), 'SHORT (sell)', np.where(m.buyband == -1, 'band', 'no signal'))
    clr = []
    for r in m.itertuples():
        if r.buyband == -1 and pd.isna(r.why):
            b, _ = DV.ladder(1, r.p_da, r.p_rt); clr.append(any(r.da <= p for q, p in b))
        else: clr.append(False)
    st = np.where((st == 'band') & np.array(clr), 'CAUGHT', np.where(st == 'band', 'band, bid too low', st))
    return st

FE = ['he', 'head', 'cahr', 'tg', 'tvu', 'wr3', 'gas_out_p', 'bias7', 'spk_d2_4', 'max_d2_4', 'fc_gap', 'wkend', 'p_da']
for z in ('EAST', 'OTTAWA'):
    m = feats(z); m['st'] = status(m); s = m[m.spk]
    print(f'\n================= {z}: {len(s)} spike hours on {s.date.nunique()} days =================')
    print(s.st.value_counts().to_string())
    print('-- spike hours: median features by status, vs all non-spike hours')
    g = s.groupby('st')[FE].median().round(1); g.loc['(non-spike hours)'] = m[~m.spk][FE].median().round(1); g['n'] = s.st.value_counts(); print(g.to_string())
    print('-- spike hours by HE block / month'); print(pd.crosstab(pd.cut(s.he, [0, 6, 16, 22, 24]), s.st).to_string()); print(s.groupby(s.date.str[:7]).size().to_dict())
    sm = s[s.date >= '2026-09-01'][['date', 'he', 'rd', 'st', 'head', 'cahr', 'tvu', 'wr3', 'spk_d2_4', 'p_da', 'da']].round(0)
    print('-- Sep/Oct 2026 spikes:'); print(sm.to_string(index=False))
    m.to_csv(C.DATA / f'spike_frame_{z}.csv', index=False)
