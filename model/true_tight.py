"""true_tight.py -- Nov 1 2026. 'Is it truly tight?' read for the Market read tab (DISPLAY ONLY, nothing feeds the ladders).
FAIR RT  = what the physics alone says RT should be: a ridge model of the RT heat rate (RT converted with Dawn gas + carbon) on bid-time
           fundamentals only -- public spare, our-view spare, gas expected online, gas ramp 1h/3h, IESO wind + its 3h change,
           net-load 3h ramp, wind-model disagreement, load/wind gaps vs IESO, valves, headroom, outages, solar, hour, weekend, month.
           No prices of any kind go in. Fitted every morning on 2026 data through D-2.
PRICED   = our DA forecast (what the market is expected to pay).   GAP = PRICED - FAIR RT.
Calls use the gap against its own trailing 6-week distribution (log seeded with the walk-forward test, then each morning's live read):
  gap >= p90             priced tight, physics loose  -> SHORT     (test Mar-Oct 2026: +$22 E / +$19 O per MWh, 74% win)
  gap <= p10             physics tight, priced cheap  -> LONG      (+$11 E / +$14 O, 45% win: fat right tail)
  gap <= p25 and DA rich truly tight: do NOT short (current v2 sells in these hours lost $3-6/MWh)
research/true_tight.py + true_tight_check.py + true_tight_ladder.py hold the tests."""
import sys, json; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent / 'research'))
import numpy as np, pandas as pd, common as C, cahr as K
from sklearn.linear_model import Ridge
FE = ['pub_sp', 'priv_sp', 'rescue', 'gas_hat', 'g1', 'g3', 'wind_fc', 'w3', 'res3', 'w_spread', 'd_load', 'd_wind', 'valve', 'head',
      'nuc_out', 'gas_out', 'solar_fc', 'he', 'wkend', 'month']
LOG = C.DATA / 'true_tight_log.csv'
J = lambda v, k=0: None if v is None or pd.isna(v) else (round(float(v), k) if k else int(round(float(v))))

def frame(z, D):
    import fear_rescue as FR
    e = FR.frame(z, keep=D); e = e[e.date >= '2026-01-01'].sort_values(['date', 'he']).copy(); g = e.groupby('date')
    e['g1'] = e.gas_hat - g.gas_hat.shift(1); e['g3'] = e.gas_hat - g.gas_hat.shift(3)
    e['w3'] = e.wind_fc - g.wind_fc.shift(3); e['res3'] = e.resid_fc - g.resid_fc.shift(3); e['month'] = pd.to_datetime(e.date).dt.month
    e = K.add(e.drop(columns=['cahr'], errors='ignore'), 'p_da'); e['den'] = e.gas_cad + K.EF * e.cp; e['off'] = K.BENCH * e.cp
    e['hr_rt'] = (e.rt + e.off) / e.den; e['hr_fc'] = (e.p_da + e.off) / e.den
    return e

def seed_log():
    if LOG.exists(): return
    rows = []
    for z in ('EAST', 'OTTAWA'):
        f = C.DATA / 'research' / f'true_tight_{z}.csv'
        if f.exists():
            t = pd.read_csv(f)[['date', 'he', 'p_da', 'rtfair_lin', 'gap_lin']].rename(columns={'rtfair_lin': 'fair', 'gap_lin': 'gap'}); t['zone'] = z; t['src'] = 'walk-forward test'; rows.append(t)
    if rows: pd.concat(rows).to_csv(LOG, index=False)

def build(D, bundle):
    seed_log(); out = {'date': D, 'hubs': {}}
    for z in ('EAST', 'OTTAWA'):
        e = frame(z, D); c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
        tr = e[(e.date <= c2)].dropna(subset=['hr_rt']); te = e[e.date == D].copy()
        if te.empty: continue
        H = {h['he']: h for h in bundle['hubs'][z]['hours']}; te['p_da'] = te.he.map(lambda h: H.get(int(h), {}).get('p_da')).astype(float)
        te['hr_fc'] = (te.p_da + te.off) / te.den
        X = tr[FE].fillna(tr[FE].median()); mu, sd = X.mean(), X.std().replace(0, 1)
        r = Ridge(alpha=10).fit((X - mu) / sd, tr.hr_rt.clip(0, 30))
        te['fair'] = r.predict((te[FE].fillna(tr[FE].median()) - mu) / sd) * te.den - te.off; te['gap'] = te.p_da - te.fair
        lg = pd.read_csv(LOG); lg = lg[(lg.zone == z) & (lg.date <= c2) & (lg.date > (pd.Timestamp(D) - pd.Timedelta(days=44)).date().isoformat())]
        q = lg.gap.quantile([.1, .25, .75, .9]).to_dict() if len(lg) > 300 else {}
        rich = tr.hr_fc.quantile(2 / 3) if len(tr) else np.nan
        rows = []
        for x in te.itertuples():
            gp = x.gap
            if not q: call = 'n/a'
            elif gp >= q[.9]: call = 'PRICED TIGHT, PHYSICS LOOSE: short'
            elif gp <= q[.1]: call = 'PHYSICS TIGHT, PRICED CHEAP: long'
            elif gp <= q[.25] and x.hr_fc >= rich: call = 'TRULY TIGHT: do not short'
            elif gp >= q[.75]: call = 'leans rich'
            elif gp <= q[.25]: call = 'leans cheap'
            else: call = 'priced about right'
            rows.append(dict(he=int(x.he), da_fc=J(x.p_da, 1), fair=J(x.fair, 1), gap=J(gp, 1), call=call, need=J(x.gas_hat), pub_sp=J(x.pub_sp), priv_sp=J(x.priv_sp),
                             g3=J(x.g3), w3=J(x.w3), res3=J(x.res3), hr_fc=J(x.hr_fc, 1)))
        out['hubs'][z] = dict(rows=rows, thr={k: J(v, 1) for k, v in q.items()}, rich_hr=J(rich, 1), train=f'{tr.date.min()}..{tr.date.max()}')
        new = pd.DataFrame([dict(date=D, he=r_['he'], p_da=r_['da_fc'], fair=r_['fair'], gap=r_['gap'], zone=z, src='live') for r_ in rows])
        lgall = pd.read_csv(LOG); lgall = lgall[~((lgall.date == D) & (lgall.zone == z))]; pd.concat([lgall, new]).to_csv(LOG, index=False)
    out['test'] = {'EAST': dict(short=22.2, short_win=74, long=11.0, long_win=45, tt_sells=-3.3, ladder_now=1168, ladder_with=1366, gap_only=1130),
                   'OTTAWA': dict(short=18.5, short_win=74, long=14.4, long_win=44, tt_sells=-5.8, ladder_now=1021, ladder_with=1341, gap_only=1324)}
    return out

if __name__ == '__main__':
    b = json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text()); o = build(b['target'], b)
    for r in o['hubs']['EAST']['rows']: print(r)
    print(o['hubs']['EAST']['thr'], o['hubs']['EAST']['rich_hr'], o['hubs']['EAST']['train'])
