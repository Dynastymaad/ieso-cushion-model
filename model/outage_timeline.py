"""outage_timeline.py -- WHEN did the outage MW that hurt us appear? From every IESO Adequacy2 re-issue
(cache/ieso_adq2_outage_timeline.csv: only the moments a value changed, with ieso_createtime, EST).
Per delivery hour (D, he):
  out_bid      gas + nuclear + hydro outage MW in the last version before D-1 09:00 EST (= what we bid on)
  out_final    same, last version up to the end of D
  add_after    out_final - out_bid (MW that arrived after the bid)
  first_add_h  hours before delivery when the first post-bid addition of >= 200 MW appeared
  ret_assumed  outage IESO shows for the SAME HE of D-1 (as of the bid) minus out_bid for D
               = MW IESO assumes will come back by D (return-to-service assumption)
  trips_d1     MW added to D-1's own hours after D-1's bid, known by D's bid (units tripping in the last 24 h)
Output data/outage_features.csv."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
SUB = {'Gas Outage': 'gas', 'Nuclear Outage': 'nuc', 'Hydro Outage': 'hyd'}

def load():
    t = pd.read_csv(C.CACHE / 'ieso_adq2_outage_timeline.csv'); t = t[t.subtype.isin(SUB)].copy()
    t['ts'] = pd.to_datetime(t.ieso_createtime); t['sub'] = t.subtype.map(SUB); t['he'] = t.hour.astype(int)
    return t.sort_values('ts')

def asof(t, dates, hes, T):
    """value per (date, he, sub) as of timestamps T (Series aligned with dates)."""
    q = pd.DataFrame({'date': dates, 'he': hes, 'T': T}).reset_index(drop=True); q['i'] = q.index
    out = {}
    for s in SUB.values():
        x = t[t['sub'] == s][['date', 'he', 'ts', 'value']].sort_values('ts')
        qq = q.sort_values('T')
        m = pd.merge_asof(qq, x, left_on='T', right_on='ts', by=['date', 'he'], direction='backward')
        out[s] = m.set_index('i').value.reindex(q.i).values
    return pd.DataFrame(out)

def build():
    t = load()
    keys = t[['date', 'he']].drop_duplicates().sort_values(['date', 'he']).reset_index(drop=True)
    D = pd.to_datetime(keys.date)
    bid = D - pd.Timedelta(days=1) + pd.Timedelta(hours=9); end = D + pd.Timedelta(days=1)
    b = asof(t, keys.date, keys.he, bid); f = asof(t, keys.date, keys.he, end)
    keys['out_bid'] = b.sum(axis=1, min_count=1).values; keys['out_final'] = f.sum(axis=1, min_count=1).values
    for s in SUB.values(): keys[f'{s}_bid'] = b[s].values; keys[f'{s}_add'] = (f[s] - b[s]).values
    keys['add_after'] = keys.out_final - keys.out_bid
    # same HE of D-1, as of D's bid (current state of the fleet)
    d1 = (D - pd.Timedelta(days=1)).dt.date.astype(str)
    p = asof(t, d1, keys.he, bid); keys['out_d1_now'] = p.sum(axis=1, min_count=1).values
    keys['ret_assumed'] = keys.out_d1_now - keys.out_bid
    # D-1's own post-bid additions, known by D's bid
    p0 = asof(t, d1, keys.he, D - pd.Timedelta(days=2) + pd.Timedelta(hours=9))
    keys['trips_d1'] = keys.out_d1_now - p0.sum(axis=1, min_count=1).values
    # timing of the first post-bid addition >= 200 MW (all fuels together)
    tt = t.copy(); tt = tt.merge(keys[['date', 'he', 'out_bid']], on=['date', 'he'])
    tt['bidT'] = pd.to_datetime(tt.date) - pd.Timedelta(days=1) + pd.Timedelta(hours=9)
    tt = tt[tt.ts > tt.bidT].sort_values('ts')
    rows = []
    for (dd, h), g in tt.groupby(['date', 'he']):
        cur = {}; ob = keys_idx.get((dd, h)) if False else None
        rows.append((dd, h, g))
    first = {}
    for (dd, h), g in tt.groupby(['date', 'he']):
        state = {}; base = g.out_bid.iloc[0]
        for s in SUB.values():
            v = keys.loc[(keys.date == dd) & (keys.he == h), f'{s}_bid']
            state[s] = float(v.iloc[0]) if len(v) and pd.notna(v.iloc[0]) else 0.0
        for r in g.itertuples():
            state[r.sub] = r.value
            if sum(state.values()) - base >= 200:
                deliv = pd.Timestamp(dd) + pd.Timedelta(hours=h - 1); first[(dd, h)] = (deliv - r.ts).total_seconds() / 3600; break
    keys['first_add_h'] = [first.get((a, b_), np.nan) for a, b_ in zip(keys.date, keys.he)]
    keys.to_csv(C.DATA / 'outage_features.csv', index=False)
    return keys

if __name__ == '__main__':
    k = build(); print(k.describe().round(0).T.to_string())
