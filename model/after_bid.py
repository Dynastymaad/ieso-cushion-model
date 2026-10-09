"""after_bid.py -- Oct 8 2026: the three after-the-bid surprises behind RT spikes, and whether anything at the bid predicts them.
 load miss  = IESO actual load - Adequacy demand forecast at the bid
 wind miss  = actual wind output (GenOutputbyFuelHourly) - wind forecast at the bid
 outage add = outage MW IESO added to the hour after the bid (outage_surprise.py)
 intertie   = RT scheduled net export (IntertieScheduleFlowYear) - DA net export (Adequacy2 final schedules)
Writes data/after_bid_<zone>.csv used by spike_model2.py."""
import sys, re; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 250)
A = C.ROOT / 'archive'
# actual wind
rows = []
for f in sorted((A / 'GenOutputbyFuelHourly').glob('*.xml')):
    s = f.read_text(encoding='utf-8', errors='ignore')
    for day, body in re.findall(r'<Day>([\d-]+)</Day>(.*?)</DailyData>', s, re.S):
        for h, hb in re.findall(r'<Hour>(\d+)</Hour>(.*?)</HourlyData>', body, re.S):
            m = re.search(r'<Fuel>WIND</Fuel>.*?<Output>([-\d.]+)</Output>', hb, re.S)
            if m: rows.append((day, int(h), float(m.group(1))))
wa = pd.DataFrame(rows, columns=['date', 'he', 'wind_act'])
# RT intertie schedules
ir = []
for f in sorted((A / 'IntertieScheduleFlowYear').glob('*.csv')):
    x = pd.read_csv(f, skiprows=4, header=None); x = x[[0, 1, x.columns[-3], x.columns[-2]]]; x.columns = ['date', 'he', 'imp_rt', 'exp_rt']; ir.append(x)
ir = pd.concat(ir); ir = ir[pd.to_numeric(ir.he, errors='coerce').notna()]; ir['he'] = ir.he.astype(int); ir[['imp_rt', 'exp_rt']] = ir[['imp_rt', 'exp_rt']].astype(float)
ax = pd.read_csv(C.CACHE / 'ieso_adq2x_final.csv'); ax = ax[ax.resourcetype.isin(['Total Exports', 'Total Imports']) & (ax.subtype == 'Schedule')]
ax = ax.drop_duplicates(['date', 'hour', 'resourcetype'], keep='last').pivot_table(index=['date', 'hour'], columns='resourcetype', values='value').reset_index()
ax.columns = ['date', 'he', 'exp_da', 'imp_da']
# actual load
act = pd.read_csv(C.CACHE / 'ieso_load_actual.csv'); t = pd.to_datetime(act.EffectiveDateTime) + pd.Timedelta(hours=1)
act['date'], act['he'] = C._ts_to_key(t); act = act.dropna(subset=['he']); act['he'] = act.he.astype(int); act = act.groupby(['date', 'he']).Load.mean().rename('load_act').reset_index()
os_ = pd.read_csv(C.DATA / 'outage_surprise.csv')
for z in ('EAST', 'OTTAWA'):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv')
    for x in (wa, ir, ax, act, os_): m = m.merge(x, on=['date', 'he'], how='left')
    m['load_miss'] = m.load_act - m.dem_fc; m['wind_miss'] = m.wind_act - m.wind_fc
    m['tie_miss'] = (m.exp_rt.abs() - m.imp_rt.abs()) - (m.exp_da.abs() - m.imp_da.abs())
    m['supply_shock'] = m.load_miss.fillna(0) - m.wind_miss.fillna(0) + m.surp.fillna(0) + m.tie_miss.fillna(0)
    m.to_csv(C.DATA / f'after_bid_{z}.csv', index=False)
    t = m[m.spk.notna() & (m.date >= '2025-09-01') & (m.date <= '2026-10-06')]
    print(f'\n========== {z}: {len(t)} h, coverage', t[['load_miss', 'wind_miss', 'surp', 'tie_miss']].notna().mean().round(2).to_dict())
    print('MECHANISM -- median surprise (MW, + = tighter except wind) in spike vs other hours, and spike rate by shock size:')
    print(t.groupby('spk')[['load_miss', 'wind_miss', 'surp', 'tie_miss', 'supply_shock']].median().round(0).to_string())
    print(t.groupby(pd.cut(t.supply_shock, [-1e9, -500, 0, 500, 1000, 1500, 1e9]), observed=True).agg(hours=('spk', 'size'), spike_rate=('spk', lambda s: round(s.mean() * 100, 1)), mean_rd=('rd', 'mean')).round(1).to_string())
    from sklearn.linear_model import LogisticRegression
    for c in ('load_miss', 'wind_miss', 'surp', 'tie_miss'):
        q = t.dropna(subset=[c]); r = q[c].rank(pct=True)
        print(f'  {c:10s} spike rate top 10% of surprise: {q[r >= .9].spk.mean()*100:5.1f}%  | bottom 50%: {q[r <= .5].spk.mean()*100:4.1f}%' if c != 'wind_miss' else
              f'  {c:10s} spike rate bottom 10% (wind short): {q[r <= .1].spk.mean()*100:5.1f}%  | top 50%: {q[r >= .5].spk.mean()*100:4.1f}%')
