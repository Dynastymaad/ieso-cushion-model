"""evening_regime.py -- Oct 9 2026 (TEST ONLY, nothing wired): the evening sell edge comes and goes by month (Oct-Nov 2025 and
Mar-Jun 2026 ~0 or negative, Jan-Feb / Jul / Sep strong). Can a short look-back switch catch the regime?
Rule: before day D, look at what the model's evening (HE16-21) sells did over the last N days (through D-2). If their average
DA-RT < 0 (or their blow-up rate is high) -> stop evening sells on D (or flip them to longs). Price-taker $ per MW."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 250)
RT8 = {'EAST': [56,47,38,37,44,59,78,53,47,37,35,54,79,53,46,51,56,76,272,72,48], 'OTTAWA': [57,47,39,37,44,60,79,54,48,38,36,55,81,54,47,52,57,77,277,73,49]}
for z in ('EAST', 'OTTAWA'):
    d = pd.read_csv(C.DATA / f'dv_frame_{z}.csv')
    for h, v in enumerate(RT8[z], 1): d.loc[(d.date == '2026-10-08') & (d.he == h), 'rt'] = v
    d['sp'] = d.da - d.rt; e = d[(d.v2 == 1) & d.he.between(16, 21) & d.sp.notna()].copy(); e['dt'] = pd.to_datetime(e.date)
    days = sorted(e.date.unique()); out = {}
    for N in (7, 14, 21, 30, 45, 60):
        for mode in ('mean<0', 'blowups>=15%'):
            sk = {}
            for D in days:
                Dt = pd.Timestamp(D); tr = e[(e.dt <= Dt - pd.Timedelta(days=2)) & (e.dt > Dt - pd.Timedelta(days=N + 2))]
                if len(tr) < 6: sk[D] = False; continue
                sk[D] = tr.sp.mean() < 0 if mode == 'mean<0' else (tr.sp <= -50).mean() >= 0.15
            off = e.date.map(sk)
            out[(N, mode)] = off
    base = e.sp; rows = [dict(rule='LIVE: sell every evening signal', total=round(base.sum()), H1=round(base[e.date < '2026-02-15'].sum()), H2=round(base[e.date >= '2026-02-15'].sum()),
                              since_aug=round(base[e.date >= '2026-08-01'].sum()), since_sep24=round(base[e.date >= '2026-09-24'].sum()), hrs_off=0)]
    for (N, mode), off in out.items():
        for act, mult in (('skip', 0), ('flip', -1)):
            pl = base.where(~off, base * mult)
            rows.append(dict(rule=f'{act} when last {N}d evening sells {mode}', total=round(pl.sum()), H1=round(pl[e.date < '2026-02-15'].sum()), H2=round(pl[e.date >= '2026-02-15'].sum()),
                             since_aug=round(pl[e.date >= '2026-08-01'].sum()), since_sep24=round(pl[e.date >= '2026-09-24'].sum()), hrs_off=int(off.sum())))
    R = pd.DataFrame(rows); R.to_csv(C.DATA / f'evening_regime_{z}.csv', index=False); print(f'\n=== {z} evening sells, $ per MW (Jul 2025 - Oct 8 2026) ==='); print(R.to_string(index=False))
