"""quebec.py -- the Quebec interties and the East / Ottawa zones.
Per-intertie imports / exports / actual flow (IESO IntertieScheduleFlowYear, 2025-26), intertie limits (DA = PreDA, RT),
East, Ottawa and Ontario (OZP) DA / RT prices. Builds data/qc_frame.csv keyed (date, he)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
PQ = ['PQ.AT', 'PQ.B5D.B31L', 'PQ.D4Z', 'PQ.D5A', 'PQ.H4Z', 'PQ.H9A', 'PQ.P33C', 'PQ.Q4C', 'PQ.X2Y']
OTHER = ['MANITOBA', 'MANITOBA SK', 'MICHIGAN', 'MINNESOTA', 'NEW-YORK', 'Total']

def flows():
    parts = []
    for y in (2025, 2026):
        f = C.ARCH / 'IntertieScheduleFlowYear' / f'PUB_IntertieScheduleFlowYear_{y}.csv'
        raw = pd.read_csv(f, skiprows=3, header=None, low_memory=False)
        names, kinds = raw.iloc[0].tolist(), raw.iloc[1].tolist()
        cols = ['date', 'he'] + [f'{str(n).strip()}|{str(k).strip()}' for n, k in zip(names[2:], kinds[2:])]
        d = raw.iloc[2:].copy(); d.columns = cols[:d.shape[1]]
        for c in d.columns[2:]: d[c] = pd.to_numeric(d[c], errors='coerce')
        d['he'] = pd.to_numeric(d.he, errors='coerce'); parts.append(d.dropna(subset=['he']))
    d = pd.concat(parts); d['he'] = d.he.astype(int)
    out = d[['date', 'he']].copy()
    for n in PQ + OTHER:
        k = n.replace('.', '_').replace(' ', '_').replace('-', '_').lower()
        if f'{n}|Imp' in d:
            out[f'{k}_imp'] = d[f'{n}|Imp'].values; out[f'{k}_exp'] = d[f'{n}|Exp'].values; out[f'{k}_flow'] = d[f'{n}|Flow'].values
    pq = [c for c in out if c.startswith('pq_') and c.endswith('_imp')]
    out['pq_imp'] = out[pq].sum(axis=1); out['pq_exp'] = out[[c.replace('_imp', '_exp') for c in pq]].sum(axis=1)
    out['pq_net_imp'] = out.pq_imp - out.pq_exp
    out['pq_flow'] = out[[c.replace('_imp', '_flow') for c in pq]].sum(axis=1)
    return out

if __name__ == '__main__':
    F = flows(); print(F.date.min(), F.date.max(), len(F))
    print(F[[c for c in F if c.startswith('pq_') and c.endswith(('_imp', '_exp'))]].mean().round(0).to_string())
    F.to_csv(C.DATA / 'qc_flows.csv', index=False)

def frame(history=True):
    """(date, he): East / Ottawa / Ontario DA, RT; PQ + NY flows; PQ.AT and NY limits (DA = bid-time, RT = realised); headroom."""
    p = C.prices(history=history); p = p[p.zone.isin(['EAST', 'OTTAWA', 'ONTARIO', 'TORONTO'])]
    w = p.pivot_table(index=['date', 'he'], columns='zone', values=['da', 'rt']); w.columns = [f'{a}_{b.lower()}' for a, b in w.columns]; w = w.reset_index()
    F = pd.read_csv(C.DATA / 'qc_flows.csv')
    w = w.merge(F, on=['date', 'he'], how='left')
    da = pd.read_csv(C.DATA / 'nrg' / 'da_intertie_limits_pq.csv')[['date', 'he', 'LIM_PQAT_EXP', 'LIM_PQAT_IMP']].rename(columns={'LIM_PQAT_EXP': 'at_exp_lim', 'LIM_PQAT_IMP': 'at_imp_lim'})
    rt = pd.read_csv(C.DATA / 'nrg' / 'rt_intertie_limits.csv')[['date', 'he', 'LIM_PQAT_EXP', 'LIM_PQAT_IMP', 'LIM_NY_EXP', 'LIM_NY_IMP']].rename(columns={'LIM_PQAT_EXP': 'at_exp_lim_rt', 'LIM_PQAT_IMP': 'at_imp_lim_rt', 'LIM_NY_EXP': 'ny_exp_lim_rt', 'LIM_NY_IMP': 'ny_imp_lim_rt'})
    ny = pd.read_csv(C.DATA / 'nrg' / 'da_intertie_limits.csv')[['date', 'he', 'LIM_NY_EXP', 'LIM_NY_IMP']].rename(columns={'LIM_NY_EXP': 'ny_exp_lim', 'LIM_NY_IMP': 'ny_imp_lim'})
    for x in (da, rt, ny): w = w.merge(x, on=['date', 'he'], how='left')
    for c in ['at_exp_lim', 'at_exp_lim_rt', 'ny_exp_lim', 'ny_exp_lim_rt']: w[c] = -w[c]          # positive MW
    a = C.adq2('preDA')[['date', 'he', 'head', 'dem_fc']]; w = w.merge(a, on=['date', 'he'], how='left')
    for z in ('east', 'ottawa'):
        w[f'{z}_da_basis'] = w[f'da_{z}'] - w.da_ontario; w[f'{z}_rt_basis'] = w[f'rt_{z}'] - w.rt_ontario; w[f'{z}_sp'] = w[f'da_{z}'] - w[f'rt_{z}']
    w['eo_da'] = w.da_east - w.da_ottawa; w['eo_rt'] = w.rt_east - w.rt_ottawa
    w['at_exp_use'] = w.pq_at_exp / w.at_exp_lim.replace(0, np.nan)       # share of the Outaouais export limit used (actual)
    w['dow'] = pd.to_datetime(w.date).dt.dayofweek
    return w
