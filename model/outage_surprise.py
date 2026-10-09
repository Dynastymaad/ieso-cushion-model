"""outage_surprise.py -- Oct 8 2026: outage MW IESO added to day D's hours AFTER D's bid (Adequacy2 outage timeline), May 2025 ->.
surp(D,h) = outages for (D,h) as known at D+1 09:00 EST minus as known at D-1 09:00 EST (the bid). Writes data/outage_surprise.csv."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, outage_timeline as OT
t = OT.load(); days = sorted(d for d in t.date.unique() if d >= '2025-06-01'); hes = list(range(1, 25)); rows = []
for D in days:
    Dt = pd.Timestamp(D)
    a = OT.asof(t, [D] * 24, hes, [Dt + pd.Timedelta(days=1, hours=9)] * 24).sum(axis=1, min_count=1)
    b = OT.asof(t, [D] * 24, hes, [Dt - pd.Timedelta(days=1) + pd.Timedelta(hours=9)] * 24).sum(axis=1, min_count=1)
    for h, x, y in zip(hes, a, b): rows.append((D, h, x - y))
s = pd.DataFrame(rows, columns=['date', 'he', 'surp']); s.to_csv(C.DATA / 'outage_surprise.csv', index=False)
print(len(s), s.date.min(), s.date.max(), s.surp.describe().round(0).to_dict())
