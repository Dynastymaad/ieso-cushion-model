"""horizon.py -- hourly DA for D+2..D+14: block forecast (blocks.py, 50/50 delta+forward)
times the recent hourly shape of the same day-type. Walk-forward, origin-time data only."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C

def shapes(p, origin, n=14):
    """hourly shape = DA_h / block mean, median over the last n days known at origin, by day-type"""
    q = p[(p.date <= origin) & (p.date > (pd.Timestamp(origin) - pd.Timedelta(days=n)).date().isoformat())].copy()
    q['wk'] = pd.to_datetime(q.date).dt.dayofweek >= 5; q['on'] = q.he.between(7, 22)
    q['bm'] = q.groupby(['date', 'on']).da.transform('mean'); q['s'] = q.da / q.bm
    return q.groupby(['wk', 'he']).s.median()

def run(zone):
    p = C.prices(zone)[['date', 'he', 'da']].dropna()
    R = pd.read_csv(C.DATA / 'bt_blocks.csv')
    R = R.pivot_table(index=['date', 'lead'], columns='block', values=['b5050', 'forward', 'persist']).reset_index()
    R.columns = ['_'.join([c for c in col if c]) for col in R.columns]
    out = []
    for (D, L), r in R.set_index(['date', 'lead']).iterrows():
        act = p[p.date == D]
        if len(act) < 24: continue
        origin = (pd.Timestamp(D) - pd.Timedelta(days=L)).date().isoformat()
        sh = shapes(p, (pd.Timestamp(origin) - pd.Timedelta(days=1)).date().isoformat())   # DA of origin day known
        if sh.empty: continue
        wk = pd.Timestamp(D).dayofweek >= 5
        for _, a in act.iterrows():
            on = 7 <= a.he <= 22
            k = 'on' if (on and not wk) else ('flat' if on else 'off')
            s = sh.get((wk, a.he), np.nan)
            last = p[(p.date == origin) & (p.he == a.he)].da
            out.append(dict(date=D, lead=L, he=a.he, y=a.da, model=r[f'b5050_{k}'] * s, forward=r[f'forward_{k}'] * s,
                            persist_hour=last.iloc[0] if len(last) else np.nan))
    return pd.DataFrame(out)

if __name__ == '__main__':
    for z in ['TORONTO', 'SOUTHWEST']:
        o = run(z); o.to_csv(C.DATA / f'bt_horizon_{z}.csv', index=False)
        o = o.dropna()
        t = o.groupby('lead').apply(lambda g: pd.Series({'hours': len(g), 'model_MAE': (g.model - g.y).abs().mean(),
             'forward_x_shape_MAE': (g.forward - g.y).abs().mean(), 'same_hour_last_known_MAE': (g.persist_hour - g.y).abs().mean(),
             'model_MAPE%': ((g.model - g.y).abs() / g.y).mean() * 100}), include_groups=False).round(2)
        print(z, o.date.min(), o.date.max()); print(t.to_string())
