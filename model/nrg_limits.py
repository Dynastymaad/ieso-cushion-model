"""nrg_limits.py -- NRGStream intertie-limit pulls (long format: stream_id, stream, ts_ept_begin, v1)
-> wide tables keyed (date, he) with LIM_<IESO code>_<EXP|IMP> columns (EXP negative, IMP positive, as IESO/NRG publish).
  nrg2_DA_INTERTIE_LIMITS_PQ.csv.gz -> data/nrg/da_intertie_limits_pq.csv   (DA = IESO PreDA limits, known at bid time)
  nrg2_PD_INTERTIE_LIMITS.csv.gz    -> data/nrg/pd_intertie_limits.csv      (latest pre-dispatch run, hourly)
  nrg2_RT_INTERTIE_LIMITS.csv.gz    -> data/nrg/rt_intertie_limits.csv      (real-time, hourly average of the 5-min limit)"""
import re, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nrg_import import to_key
NRG = Path(__file__).resolve().parents[1] / 'data' / 'nrg'
LINE = {'Manitoba.SK1': 'PQSK', 'Manitoba': 'MB', 'Michigan': 'MI', 'Minnesota': 'MN', 'New York': 'NY',
        'PQ.AT': 'PQAT', 'PQ.B5D-B31L': 'PQBE', 'PQ.D4Z': 'PQDZ', 'PQ.D5A': 'PQDA', 'PQ.H4Z': 'PQHZ', 'PQ.H9A': 'PQHA',
        'PQ.P33C': 'PQPC', 'PQ.Q4C': 'PQQC', 'PQ.X2Y': 'PQXY'}

def code(name):
    m = re.match(r'ON - (.+?)\s*-\s*(?:DA|Predisp|RT) Intertie Sched Limits - (EXP|IMP)', name)
    return f'LIM_{LINE[m.group(1).strip()]}_{m.group(2)}'

def convert(src, dst):
    d = pd.read_csv(NRG / src)
    d['col'] = d.stream.map(code)
    d['date'], d['he'] = to_key(d.ts_ept_begin)
    d = d[d.date.ne('NaT') & d.he.notna()]; d['he'] = d.he.astype(int)
    agg = 'last'   # one value per hour (RT = NRG hourly average of the 5-min limit)
    w = d.pivot_table(index=['date', 'he'], columns='col', values='v1', aggfunc=agg).reset_index()
    w.to_csv(NRG / dst, index=False)
    print(f'{dst}: {len(w)} h, {w.date.min()}..{w.date.max()}, cols {len(w.columns)-2}')
    return w

if __name__ == '__main__':
    for s, t in (('nrg2_DA_INTERTIE_LIMITS_PQ.csv.gz', 'da_intertie_limits_pq.csv'),
                 ('nrg2_PD_INTERTIE_LIMITS.csv.gz', 'pd_intertie_limits.csv'),
                 ('nrg2_RT_INTERTIE_LIMITS.csv.gz', 'rt_intertie_limits.csv')):
        if (NRG / s).exists(): convert(s, t)
