"""zone_backtest.py -- rebuild the walk-forward DA / RT backtest files for any IESO virtual zone (EAST, OTTAWA, ...).
Same method as the Toronto / Southwest files the page reads:
  p_h   hourly hybrid (hourly.py, trailing 21 days)             p_s  p_h rescaled to the block forecast (bt_blocks lead 1, 50/50)
        x the zone's trailing-14-day DA ratio to Ontario (OZP)   p_da = 0.5 p_h + 0.5 p_s
  DA range = p_da x quantiles of ln(DA / p_da) over the trailing 28 days, same time block
  RT range = p_da x quantiles of ln(RT / p_da) over the trailing 28 days through D-2, same block and tight/loose (head < 8,500)
Writes data/bt_hourly_<Z>.csv, bt_quantiles_<Z>.csv, bt_rt_quantiles_<Z>.csv."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, hourly as HR
Q = [.1, .25, .5, .75, .9]

def block_fc(zone):
    b = pd.read_csv(C.DATA / 'bt_blocks.csv'); b = b[b.lead == 1].pivot_table(index='date', columns='block', values='b5050')
    b.columns = [f'fc_{c}' for c in b.columns]
    p = C.prices(); z = p[p.zone == zone].groupby('date').da.mean(); o = p[p.zone == 'ONTARIO'].groupby('date').da.mean()
    ratio = (z / o).dropna().rolling(14, min_periods=5).mean().shift(1)            # known by the bid (D-1's DA is out on D-2)
    b = b.join(ratio.rename('basis'), how='left'); b['basis'] = b.basis.fillna(1.0)
    for c in ('fc_on', 'fc_off', 'fc_flat'): b[c] = b[c] * b.basis
    return b.reset_index()

def run(zone):
    h = HR.walk(zone, block_fc=block_fc(zone)); h['p_da'] = 0.5 * h.p_h + 0.5 * h.p_s.fillna(h.p_h)
    h.to_csv(C.DATA / f'bt_hourly_{zone}.csv', index=False)
    h = h.sort_values(['date', 'he']).reset_index(drop=True); h['tb'] = (h['head'] < 8500).astype(int)
    h['lr_da'] = np.log(h.da.clip(lower=5) / h.p_da); h['lr_rt'] = np.log(h.rt.clip(lower=5) / h.p_da)
    qd, qr = [], []
    for D in sorted(h.date.unique()):
        g = h[h.date == D]; lo = (pd.Timestamp(D) - pd.Timedelta(days=29)).date().isoformat(); c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
        tr = h[(h.date >= lo) & (h.date < D)]
        if tr.date.nunique() < 14: continue
        for r in g.itertuples():
            pool = tr[tr.blk == r.blk]; pr = pool[(pool.tb == r.tb) & (pool.date <= c2)]
            if pr.lr_rt.notna().sum() < 40: pr = pool[pool.date <= c2]
            a = np.nanquantile(pool.lr_da, Q); b = np.nanquantile(pr.lr_rt, Q)
            qd.append(dict(r._asdict(), **{f'q{int(q*100)}': r.p_da * np.exp(v) for q, v in zip(Q, a)}))
            qr.append(dict(date=r.date, he=r.he, rt=r.rt, p_da=r.p_da, **{f'r{int(q*100)}': r.p_da * np.exp(v) for q, v in zip(Q, b)}))
    qd = pd.DataFrame(qd).drop(columns=['Index'], errors='ignore'); qr = pd.DataFrame(qr)
    qd.to_csv(C.DATA / f'bt_quantiles_{zone}.csv', index=False); qr.to_csv(C.DATA / f'bt_rt_quantiles_{zone}.csv', index=False)
    v = qd.dropna(subset=['da']); e = v.p_da - v.da
    print(f'{zone}: {v.date.nunique()} days {v.date.min()}..{v.date.max()}  DA MAE {e.abs().mean():.2f} bias {e.mean():+.2f}  '
          f'P10-P90 cover {((v.da >= v.q10) & (v.da <= v.q90)).mean()*100:.0f}%  RT MAE {(qr.r50 - qr.rt).abs().mean():.2f}')
    return qd, qr

if __name__ == '__main__':
    for z in (sys.argv[1:] or ['EAST', 'OTTAWA']): run(z)
