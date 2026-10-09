"""all_hours.py -- Oct 9 2026: trade EVERY hour from fundamentals? Walk-forward gradient-boosted regression of DA-RT on all
bid-time fundamentals (ramps for load / gas / wind / residual, headroom, spare gas, outages, exports & hydro expected, Tesla /
Dynasty vs IESO, CAHR, DA level, NY spread, recent after-bid surprises incl. intertie changes and outages, recent RT-DA by hour).
Monthly refit on data through first-of-month - 2 days. Trade the predicted side when |prediction| >= k. Price-taker $ per MW.
Answers: (1) is there money in the hours the live model leaves flat? (2) does a no-bias all-hours model beat the live model?"""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C
from sklearn.ensemble import HistGradientBoostingRegressor
pd.set_option('display.width', 260)
SEG = pd.IntervalIndex.from_tuples([(0, 6), (6, 10), (10, 15), (15, 21), (21, 24)]); SEGN = ['overnight 1-6', 'morning 7-10', 'midday 11-15', 'evening 16-21', 'late 22-24']
FE = ['he', 'month', 'wkend', 'head', 'gas_hat', 'gas_av', 'spare', 'g1', 'g3', 'resid_ramp3', 'dem_r1', 'wind_fc', 'wr3', 'wind_r1', 'solar_fc', 'solar_r1',
      'gas_out', 'nuc_out', 'gas_out_p', 'hyd_exp', 'exp_exp', 'gapT', 'gapDyn', 'tvu', 'cahr', 'p_da', 'prem', 'nyx', 'bias7', 'bias14',
      'tie_miss_tr7', 'surp_tr7', 'load_miss_tr7', 'w_nwp_sd', 'w_gap_min', 'spk_d2_4']

def frame(z):
    m = pd.read_csv(C.DATA / f'spike_feats_{z}.csv'); s = pd.read_csv(C.DATA / 'shock_predict_EAST.csv')[['date', 'he', 'gapDyn', 'tie_miss_tr7', 'surp_tr7', 'load_miss_tr7']]
    m = m.merge(s, on=['date', 'he'], how='left').sort_values(['date', 'he']).reset_index(drop=True)
    m['gapT'] = m.lf_tesla - m.dem_fc; m['nyx'] = m.nyA_da - m.p_da; m['prem'] = m.p_da - m.p_rt; m['spare'] = m.gas_av - m.gas_hat
    g = m.groupby('date')
    m['g1'] = g.gas_hat.diff(); m['g3'] = g.gas_hat.diff(3); m['dem_r1'] = g.dem_fc.diff(); m['wind_r1'] = g.wind_fc.diff(); m['solar_r1'] = g.solar_fc.diff()
    m['sp'] = m.da - m.rt; m['seg'] = pd.cut(m.he, SEG).cat.rename_categories(SEGN)
    m['live'] = np.where(m.why.notna(), 1, np.where(m.buyband == -1, -1, 0))
    return m

def walk(m, clip=60):
    m['pred'] = np.nan
    for M in pd.period_range('2025-10', '2026-10', freq='M'):
        cut = (M.start_time - pd.Timedelta(days=2)).date().isoformat(); te = (m.date >= M.start_time.date().isoformat()) & (m.date <= min(M.end_time.date().isoformat(), '2026-10-06'))
        tr = m[(m.date <= cut) & m.sp.notna()]
        if not te.any(): continue
        r = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.04, max_iter=300, min_samples_leaf=50, l2_regularization=2.0, random_state=0)
        r.fit(tr[FE], tr.sp.clip(-clip, clip)); m.loc[te, 'pred'] = r.predict(m.loc[te, FE])
    return m

def tbl(m, side, name):
    x = m[m.pred.notna() & m.sp.notna()].assign(s=side); x = x[x.s != 0]; x['pl'] = x.s * x.sp; rows = []
    for sg in SEGN + ['ALL']:
        y = x if sg == 'ALL' else x[x.seg == sg]
        rows.append(dict(rule=name, seg=sg, hours=len(y), sells=int((y.s > 0).sum()), buys=int((y.s < 0).sum()), usd_mwh=round(y.pl.mean(), 1) if len(y) else 0,
                         total=round(y.pl.sum()), H1=round(y.pl[y.date < '2026-02-15'].sum()), H2=round(y.pl[y.date >= '2026-02-15'].sum()), last90=round(y.pl[y.date >= '2026-07-08'].sum())))
    return rows

if __name__ == '__main__':
    for z in sys.argv[1:] or ['EAST']:
        m = walk(frame(z)); o = m[m.pred.notna()]; R = []
        R += tbl(m, m.live.where(m.pred.notna(), 0), 'LIVE model')
        for k in (0, 5, 10):
            mdl = np.where(m.pred >= k, 1, np.where(m.pred <= -k, -1, 0))
            R += tbl(m, pd.Series(np.where(m.live == 0, mdl, 0), index=m.index), f'model on LIVE-FLAT hours, |pred|>={k}')
        for k in (5, 10):
            mdl = np.where(m.pred >= k, 1, np.where(m.pred <= -k, -1, 0))
            R += tbl(m, pd.Series(mdl, index=m.index), f'model ALL hours (no live), |pred|>={k}')
        R = pd.DataFrame(R); R.to_csv(C.DATA / f'all_hours_{z}.csv', index=False)
        print(z, '| live flat hours:', int(((o.live == 0) & o.sp.notna()).sum()), 'of', int(o.sp.notna().sum()), '| mean |DA-RT| in flat hours', round(o[o.live == 0].sp.abs().mean(), 1))
        print(R[R.seg.isin(['ALL', 'evening 16-21', 'midday 11-15', 'morning 7-10', 'overnight 1-6', 'late 22-24'])].to_string(index=False))
