"""spike_anatomy.py -- Oct 9 2026 (TEST / UNDERSTANDING ONLY): what do the RT spikes have in common, so a trader can spot the risk?
Event = RT >= DA + $50 (East). For every event: segment, month, what the model did, the bid-time picture, and which after-bid surprise
was biggest (load above IESO forecast, wind below forecast, outages IESO added after the bid, intertie schedules changed).
Then a risk checklist: for evening hours (HE16-21), how much each bid-time warning sign raises the spike odds, and how it pays."""
import sys, math; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 260)

def sunset_est(date):      # Toronto (43.65N, 79.38W), NOAA approximation, returns EST decimal hour
    d = pd.Timestamp(date); n = d.dayofyear; g = 2 * math.pi / 365 * (n - 1)
    decl = 0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    lat = math.radians(43.65); ha = math.degrees(math.acos(math.cos(math.radians(90.833)) / (math.cos(lat) * math.cos(decl)) - math.tan(lat) * math.tan(decl)))
    return (720 - 4 * (-79.38 - ha) - eqt) / 60 - 5     # UTC -> EST

m = pd.read_csv(C.DATA / 'after_bid_EAST.csv'); s = pd.read_csv(C.DATA / 'shock_predict_EAST.csv')[['date', 'he', 'gapDyn']]
m = m.merge(s, on=['date', 'he'], how='left'); m = m[(m.date >= '2025-09-01') & (m.date <= '2026-10-06') & m.rt.notna()].copy()
m['gapT'] = m.lf_tesla - m.dem_fc; m['spare'] = m.gas_av - m.gas_hat; m['rd'] = m.rt - m.da; m['ev'] = m.rd >= 50
m['seg'] = pd.cut(m.he, [0, 6, 10, 15, 21, 24], labels=['overnight 1-6', 'morning 7-10', 'midday 11-15', 'evening 16-21', 'late 22-24'])
ss = {d: sunset_est(d) for d in m.date.unique()}; m['sunset_he'] = m.date.map(lambda d: int(math.floor(ss[d])) + 1)      # HE that contains sunset
m['dusk'] = (m.he >= m.sunset_he) & (m.he <= m.sunset_he + 1)                                                              # sunset hour and the one after
m['side'] = np.where(m.why.notna(), 'SHORT', np.where(m.buyband == -1, 'LONG', 'flat'))
sh = pd.DataFrame({'load above fc': m.load_miss.clip(lower=0), 'wind short': (-m.wind_miss).clip(lower=0), 'outages added': m.surp.clip(lower=0), 'interties': m.tie_miss.clip(lower=0)})
m['main_cause'] = np.where(sh.max(axis=1) < 250, 'no big surprise (<250 MW)', sh.idxmax(axis=1)); m['shock'] = sh.sum(axis=1)
r = m.pivot_table(index='date', columns='he', values='resid'); pm = (r[19] - r[15]).sort_index()
m['pm_pct'] = m.date.map(pm.rolling(60, min_periods=20).apply(lambda q: (q.iloc[:-1] < q.iloc[-1]).mean() * 100))
e = m[m.ev]
print(f'EVENTS (RT >= DA + $50), East, Sep 2025 - Oct 6 2026: {len(e)} hours on {e.date.nunique()} days ({len(e)/len(m)*100:.1f}% of hours)')
print('\nBy segment (events, share of segment hours, what the model held):')
print(pd.concat([e.groupby('seg', observed=True).size().rename('events'), (m.groupby('seg', observed=True).ev.mean() * 100).round(1).rename('rate %'),
                 pd.crosstab(e.seg, e.side)], axis=1).to_string())
print('\nBy month (events / rate):', {k: f'{v} / {r_:.0f}%' for (k, v), r_ in zip(e.groupby(e.date.str[:7]).size().items(), (m.groupby(m.date.str[:7]).ev.mean() * 100).reindex(e.date.str[:7].unique()))})
print('\nMain after-bid cause (all events | evening events):')
print(pd.concat([e.main_cause.value_counts().rename('all'), e[e.seg == 'evening 16-21'].main_cause.value_counts().rename('evening')], axis=1).fillna(0).astype(int).to_string())
print('\nMedian after-bid surprise, MW (events vs normal hours):'); print(m.groupby('ev')[['load_miss', 'wind_miss', 'surp', 'tie_miss', 'shock']].median().round(0).to_string())
print(f"\nEvening events in the sunset hour or the hour after: {e[e.seg=='evening 16-21'].dusk.mean()*100:.0f}% (those hours are {m[m.seg=='evening 16-21'].dusk.mean()*100:.0f}% of evening hours)")
# risk checklist (evening only)
ev = m[m.seg == 'evening 16-21'].copy(); base = ev.ev.mean()
ev['wkday'] = ev.wkend == 0; ev['shoulder'] = ev.date.str[5:7].isin(['03', '04', '05', '06', '10', '11', '12'])
day_ev = m.groupby('date').ev.sum(); ev['spike_recent'] = ev.date.map(lambda d: day_ev[(day_ev.index < (pd.Timestamp(d) - pd.Timedelta(days=1)).date().isoformat()) & (day_ev.index >= (pd.Timestamp(d) - pd.Timedelta(days=4)).date().isoformat())].sum() > 0)
C_ = {'Tesla above IESO': ev.gapT > 0, 'Tesla 200+ above IESO': ev.gapT > 200, 'Dynasty above IESO': ev.gapDyn > 0, 'wind fc >= 1,500 (windy)': ev.wind_fc >= 1500,
      'wind fc < 600 (calm)': ev.wind_fc < 600, 'wind falling 300+ into the hour (3h)': ev.wr3 <= -300, 'sunset hour or the hour after': ev.dusk,
      'headroom < 6,000': ev['head'] < 6000, 'headroom 6,000-7,000': ev['head'].between(6000, 7000), 'spare gas < 1,000': ev.spare < 1000, 'CAHR >= 12': ev.cahr >= 12,
      'evening ramp top 10%': ev.pm_pct >= 90, 'gas outages high (top third of 30d)': ev.gas_out_p >= 66, 'spike in the last 3 days': ev.spike_recent,
      'weekday': ev.wkday, 'shoulder month (Mar-Jun, Oct-Dec)': ev.shoulder,
      'Tesla>IESO + windy': (ev.gapT > 0) & (ev.wind_fc >= 1500), 'Tesla>IESO + sunset hour': (ev.gapT > 0) & ev.dusk, 'windy + wind falling 300+': (ev.wind_fc >= 1500) & (ev.wr3 <= -300),
      'Tesla>IESO + shoulder month': (ev.gapT > 0) & ev.shoulder}
rows = []
for n, k in C_.items():
    x = ev[k]; y = ev[~k]
    rows.append(dict(sign=n, hours=len(x), days=x.date.nunique(), spike_rate=round(x.ev.mean() * 100, 1), vs_base=round(x.ev.mean() / base, 2), RT_beat_DA=round((x.rd > 0).mean() * 100),
                     mean_RT_minus_DA=round(x.rd.mean(), 1), H1_rate=round(x[x.date < '2026-02-15'].ev.mean() * 100, 1), H2_rate=round(x[x.date >= '2026-02-15'].ev.mean() * 100, 1),
                     last120_rate=round(x[x.date >= '2026-06-08'].ev.mean() * 100, 1), when_not=round(y.ev.mean() * 100, 1)))
R = pd.DataFrame(rows).sort_values('vs_base', ascending=False); R.to_csv(C.DATA / 'spike_checklist_EAST.csv', index=False)
print(f'\nEVENING RISK CHECKLIST (HE16-21, base spike rate {base*100:.1f}%):'); print(R.to_string(index=False))
e[['date', 'he', 'seg', 'side', 'da', 'rt', 'head', 'spare', 'cahr', 'gapT', 'wind_fc', 'wr3', 'dusk', 'load_miss', 'wind_miss', 'surp', 'tie_miss', 'main_cause']].to_csv(C.DATA / 'spike_events_EAST.csv', index=False)
