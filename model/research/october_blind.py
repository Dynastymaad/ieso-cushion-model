"""research/october_blind.py -- read every October 2026 hour from the bid-time fundamentals only (the Fundamentals tab's own saved values),
with rules learned on Jan-Sep 2026 (scenario_2026.py). Prices are NOT used to make the read; they are joined afterwards in a separate score."""
import sys, json; sys.path.insert(0, 'model'); sys.path.insert(0, 'model/research')
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 240)
h = json.loads((C.DATA / 'fund_history.json').read_text())
F = pd.DataFrame([dict(date=k, **x) for k, v in h.items() for x in v if '2026-10-01' <= k <= '2026-10-31'])
F['load_best'] = F.met.fillna(F.tes); F['wind_best'] = F.wm.fillna((F.wlo + F.whi) / 2)
F['private_sp'] = F.sp - (F.load_best - F.dem) + (F.wind_best - F.w); F['rescue'] = F.private_sp - F.sp; F['spread'] = F.whi - F.wlo
F['load_gap'] = F.load_best - F.dem; F['wind_gap'] = F.wind_best - F.w
print('hours where Meteologica load missing:', int(F.met.isna().sum()), ' Meteologica wind missing:', int(F.wm.isna().sum()), ' days:', sorted(F[F.met.isna() | F.wm.isna()].date.unique()))
def read(r):
    if pd.isna(r.rescue) or pd.isna(r.sp): return 'n/a', ''
    if r.sp < 1500:
        if r.rescue >= 300 and (pd.isna(r.spread) or r.spread <= 1200):
            return 'scared+rescue', ('SHORT, full size' if (r.vs or 0) >= 18 else 'SHORT')
        if r.rescue <= -300 or (not pd.isna(r.spread) and r.spread > 1200):
            return 'scared+danger', ('SHORT (premium priced in)' if (r.vs or 0) >= 24 and r.sp <= 971 else 'stand aside')
        return 'scared, agree', 'small short'
    if r.rescue <= -300:
        boost = sum([(r.vs or 0) >= 4, (r.w3 or 0) <= -2, (r.load_gap or 0) >= 370, r.he <= 9])
        return 'calm+danger', ('LONG' if boost >= 2 else 'small long' if boost == 1 else 'skip (no trigger)')
    if r.rescue >= 300: return 'calm+rescue', 'small short'
    return 'calm, agree', '-'
F[['scen', 'call']] = F.apply(lambda r: pd.Series(read(r)), axis=1)
print('October 2026 days with a saved Fundamentals tab:', F.date.nunique(), sorted(set(pd.date_range('2026-10-01', '2026-10-31').strftime('%Y-%m-%d')) - set(F.date)))
print('\n-- hours per scenario --'); print(F.groupby(['scen', 'call']).size().to_string())
print('\n-- day by day (blind read) --')
for d, g in F.groupby('date'):
    parts = []
    for c in ('SHORT, full size', 'SHORT', 'SHORT (premium priced in)', 'LONG', 'small long', 'stand aside'):
        hs = g[g.call == c].he.tolist()
        if hs: parts.append(f"{c}: HE{','.join(map(str, hs))}")
    print(f'{d} {pd.Timestamp(d).day_name()[:3]}  ' + (' | '.join(parts) if parts else 'nothing stands out'))
F.to_csv(C.DATA / 'research' / 'october_blind_reads.csv', index=False)
