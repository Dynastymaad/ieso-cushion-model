"""blocks.py -- daily block DA forecasts (on-peak HE7-22 IESO / off-peak / flat) for any
lead 1..14 days, walk-forward, all seasons since May 2025. Everything is taken as it
stood at the forecast origin O = D - lead, before 09:00 EST (08:00 MT deadline for lead 1).

Models
  persist : last DA known at the origin (day O's DA, published O-1)
  forward : Ontario Hub daily forward for strip D, last settle struck on or before O-1
  delta   : persist * exp(b_head * dHead + b_gas * dln(Dawn) + b_ny * dln(NYISO fwd))
            dHead = IESO-forecast headroom for D (vintage issued on O) minus headroom of day O
  blend   : weights on (delta, forward) refit on the trailing window by least squares on logs
"""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C

BLOCKS = {'on': (7, 22), 'off': None, 'flat': None}


def settles():
    f = pd.read_csv(C.CACHE / 'fwd_daily_ontario.csv', parse_dates=['EffectiveDate', 'Strip'])
    f['node'] = f.ExchangeCode + '|' + f.NodeName
    return f


def fwd_asof(f, code, node):
    """table (strip, eff, price) for one product, strips AFTER eff only (true forwards)."""
    g = f[(f.ExchangeCode == code) & (f.NodeName == node) & (f.Strip > f.EffectiveDate)][['Strip', 'EffectiveDate', 'Price']]
    return g.sort_values('EffectiveDate')


def asof(tbl, strip, origin):
    """last price for `strip` struck on or before origin-1 day."""
    g = tbl[(tbl.Strip == strip) & (tbl.EffectiveDate <= origin - pd.Timedelta(days=1))]
    return g.Price.iloc[-1] if len(g) else np.nan


def headroom_by_lead():
    """headroom per (date, he, lead): lead 1 = pre-deadline vintage, 2..15 from the leads pull."""
    pre = C.adq2('preDA')[['date', 'he', 'head', 'dem_fc']].assign(lead=1)
    a = pd.read_csv(C.CACHE / 'ieso_adq2_leads.csv')
    a['k'] = a.subtype
    w = a.pivot_table(index=['date', 'hour', 'lead'], columns='k', values='value').reset_index().rename(columns={'hour': 'he'})
    w['head'] = (w['Gas Capacity'] - w['Gas Outage'] + w['Hydro Capacity'] - w['Hydro Outage']
                 - (w['Forecast'] - (w['Nuclear Capacity'] - w['Nuclear Outage']) - w['Wind Forecast'].fillna(0) - w['Solar Forecast'].fillna(0)))
    w['dem_fc'] = w['Forecast']
    return pd.concat([pre, w[['date', 'he', 'head', 'dem_fc', 'lead']]], ignore_index=True)


def build(leads=range(1, 15)):
    b = C.daily_blocks(); b['date'] = b.date.astype(str)
    H = headroom_by_lead(); H['on'] = H.he.between(7, 22)
    hb = H.groupby(['date', 'lead', 'on'])['head'].mean().unstack('on')
    hb.columns = ['head_off', 'head_on']; hb = hb.reset_index(); hb['head_flat'] = hb[['head_off', 'head_on']].mean(axis=1)
    f = settles()
    xde, xdg, xdy = (fwd_asof(f, c, 'Ontario Hub') for c in ('XDE', 'XDG', 'XDY'))
    cvx = fwd_asof(f, 'CVX', 'Dawn Ontario'); pda = fwd_asof(f, 'PDA', 'WESTERN HUB')
    # Dawn "spot" known at origin: last price for the nearest strip after origin
    B = b.set_index('date')
    rows = []
    for D in pd.to_datetime(b.date):
        ds = D.date().isoformat()
        for L in leads:
            O = D - pd.Timedelta(days=L); os_ = O.date().isoformat()
            if os_ not in B.index: continue
            r = dict(date=ds, lead=L, origin=os_, dow=D.dayofweek, month=D.month)
            for k in ('on', 'off', 'flat'):
                r[f'y_{k}'] = B.at[ds, f'da_{k}']; r[f'anch_{k}'] = B.at[os_, f'da_{k}']
            r['fwd_on'] = asof(xde, D, O); r['fwd_off'] = asof(xdg, D, O); r['fwd_flat'] = asof(xdy, D, O)
            r['gas_D'] = asof(cvx, D, O); r['gas_O'] = asof(cvx, O, O)
            r['pjm_D'] = asof(pda, D, O); r['pjm_O'] = asof(pda, O, O)
            rows.append(r)
    X = pd.DataFrame(rows)
    hD = hb.rename(columns={'head_on': 'hD_on', 'head_off': 'hD_off', 'head_flat': 'hD_flat'})
    X = X.merge(hD, on=['date', 'lead'], how='left')
    hO = hb[hb.lead == 1].drop(columns='lead').rename(columns={'date': 'origin', 'head_on': 'hO_on', 'head_off': 'hO_off', 'head_flat': 'hO_flat'})
    X = X.merge(hO, on='origin', how='left')
    return X


def walk(X, win=60, lam=1.0):
    """walk-forward per (lead, block). Returns long table of predictions."""
    out = []
    X = X.sort_values('date')
    for L, g in X.groupby('lead'):
        g = g.reset_index(drop=True)
        for k in ('on', 'off', 'flat'):
            y, a, fw = np.log(g[f'y_{k}'].clip(lower=3)), np.log(g[f'anch_{k}'].clip(lower=3)), np.log(g[f'fwd_{k}'].clip(lower=3))
            dh = (g[f'hD_{k}'] - g[f'hO_{k}']) / 1000
            dg = np.log(g.gas_D / g.gas_O); dp = np.log(g.pjm_D / g.pjm_O)
            F = pd.DataFrame({'dh': dh, 'dg': dg, 'dp': dp}).fillna(0)
            ok = y.notna() & a.notna()
            dates = g.date.values
            for i in range(len(g)):
                if not ok[i]: continue
                tr = np.where(ok.values & (dates < dates[i]) & (dates >= (pd.Timestamp(dates[i]) - pd.Timedelta(days=win * 1.45)).date().isoformat()))[0]
                tr = tr[g.date.values[tr] <= (pd.Timestamp(dates[i]) - pd.Timedelta(days=L)).date().isoformat()]   # only outcomes known at origin
                if len(tr) < 25: continue
                Xd = F.values[tr]; yd = (y - a).values[tr]
                beta = np.linalg.solve(Xd.T @ Xd + lam * np.eye(Xd.shape[1]), Xd.T @ yd)
                p_delta = a[i] + F.values[i] @ beta
                # delta in-sample preds on train to fit blend weight with forward
                pd_tr = a.values[tr] + Xd @ beta
                fw_ok = ~np.isnan(fw.values[tr])
                if not np.isnan(fw[i]) and fw_ok.sum() > 20:
                    Z = np.c_[pd_tr[fw_ok], fw.values[tr][fw_ok]]; yz = y.values[tr][fw_ok]
                    w = np.linalg.lstsq(np.c_[Z, np.ones(len(Z))], yz, rcond=None)[0]
                    p_blend = w[0] * p_delta + w[1] * fw[i] + w[2]
                    p_5050 = 0.5 * p_delta + 0.5 * fw[i]
                else:
                    p_blend = p_5050 = p_delta
                out.append(dict(date=dates[i], lead=L, block=k, dow=g.dow[i], y=np.exp(y[i]), persist=np.exp(a[i]),
                                forward=np.exp(fw[i]) if not np.isnan(fw[i]) else np.nan, delta=np.exp(p_delta),
                                blend=np.exp(p_blend), b5050=np.exp(p_5050)))
    return pd.DataFrame(out)


if __name__ == '__main__':
    import time; t0 = time.time()
    X = build(); X.to_csv(C.DATA / 'blocks_features.csv', index=False); print('features', X.shape, round(time.time() - t0), 's')
