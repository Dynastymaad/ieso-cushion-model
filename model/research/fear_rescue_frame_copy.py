"""research/fear_rescue.py -- Oct 31 2026 (TEST ONLY). Read the market, not the numbers:
  PUBLIC view  = what every trader sees at the bid: IESO load + IESO wind -> public gas spare (gas available - gas needed).
  PRIVATE view = our best read of the same hour: best load vendor (Meteologica, else Tesla/Dynasty average) and best wind
                 (Meteologica, else the median of the 8 weather-model wind forecasts) -> private spare.
  RESCUE       = private spare - public spare (+ = things are looser than the market sees; - = tighter, 'danger').
  UNCERTAINTY  = spread of the wind models, disagreement between load vendors (how wrong could the public view be).
  VALVES       = what can save a tight hour in real time: scheduled net exports (IESO can cut them), import capability, spare hydro.
Hypothesis: money is (1) SHORT where the market sees tight but something will save it, (2) LONG where the market sees loose
but something can go wrong. Outcome = RT - DA (East and Ottawa), Jun 2025 -> Oct 2026."""
import sys, warnings; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, supply_fc as S
pd.set_option('display.width', 230); pd.set_option('display.max_columns', 30)
NWP = ['wf_frontier', 'wf_gem_cmc', 'wf_gfs', 'wf_nam', 'wf_nam_nest', 'wf_stormvista_ecmwf', 'wf_stormvista_ecmwf_eps', 'wf_stormvista_gfs', 'wf_stormvista_gfs_ens']

def frame(z):
    e = pd.read_csv(C.DATA / f'dv_frame_{z}.csv')
    L = C.load_forecasts_at_bid()[['date', 'he', 'lf_meteologica']]; W = S.wind_at_bid(); lim = S.limits_at_bid()[['date', 'he', 'exp_cap', 'imp_cap']]
    e = e.merge(L, on=['date', 'he'], how='left').merge(W[['date', 'he', 'wf_meteologica'] + [c for c in NWP if c in W]], on=['date', 'he'], how='left').merge(lim, on=['date', 'he'], how='left')
    e = e[e.rt.notna() & e.da.notna() & e.gas_hat.notna()].copy()
    nw = [c for c in NWP if c in e]
    e['w_models'] = e[nw].median(axis=1); e['w_spread'] = e[nw].max(axis=1) - e[nw].min(axis=1)
    e['priv_wind'] = e.wf_meteologica.fillna(e.w_models)
    e['priv_load'] = e.lf_meteologica.fillna(e[['lf_tesla', 'lf_dynasty']].mean(axis=1))
    e['load_dis'] = (e.lf_tesla - e.lf_dynasty).abs()
    e['pub_sp'] = e.gas_av - e.gas_hat
    e['d_load'] = e.priv_load - e.dem_fc; e['d_wind'] = e.priv_wind - e.wind_fc
    e['rescue'] = -e.d_load.fillna(0) + e.d_wind.fillna(0)
    e['priv_sp'] = e.pub_sp + e.rescue
    e['valve'] = e.exp_exp.clip(lower=0) + e.hyd_av.sub(e.hyd_exp).clip(lower=0)      # scheduled exports that can be cut + unscheduled hydro
    e['x'] = e.rt - e.da; e['spk'] = e.x >= 25; e['col'] = e.x <= -20
    e['per'] = np.select([e.date < '2026-01-01', e.date < '2026-07-01'], ['2025 Jun-Dec', '2026 Jan-Jun'], '2026 Jul-Oct')
    e['tight'] = pd.cut(e.pub_sp, [-1e9, 1500, 3000, 1e9], labels=['public TIGHT (<1.5k)', 'public mid', 'public LOOSE (>3k)'])
    e['view'] = pd.cut(e.rescue, [-1e9, -300, 300, 1e9], labels=['danger (priv tighter 300+)', 'agree', 'rescue (priv looser 300+)'])
    return e

def stats(g):
    return pd.Series(dict(hours=len(g), sell_pl=-g.x.mean(), median_rt_da=g.x.median(), rt_gt_da=(g.x > 0).mean() * 100, spike=g.spk.mean() * 100, collapse=g.col.mean() * 100))

if __name__ == '__main__':
    for z in ('EAST', 'OTTAWA'):
        e = frame(z); print(f'\n================ {z}: {e.date.min()}..{e.date.max()}, {len(e)} h ================')
        print('-- public tightness x private view: sell P&L = DA-RT $/MWh (+ = shorts win) --')
        T = e.groupby(['tight', 'view']).apply(stats).round(1); print(T.to_string())
        print('-- same table, sell P&L by period (stability) --')
        print(e.groupby(['tight', 'view', 'per']).apply(lambda g: round(-g.x.mean(), 1) if len(g) >= 40 else np.nan).unstack('per').to_string())
        print('-- inside public TIGHT hours: what decides it --')
        t = e[e.pub_sp < 1500]
        for c, bins in (('w_spread', [0, 600, 1200, 99999]), ('valve', [-1, 1500, 3000, 99999]), ('load_dis', [0, 150, 400, 99999]), ('rescue', [-9e9, -300, 0, 300, 9e9])):
            print(f'   by {c}:', t.groupby(pd.cut(t[c], bins)).apply(stats)[['hours', 'sell_pl', 'rt_gt_da', 'spike', 'collapse']].round(1).to_dict('index'))
        print('-- inside public LOOSE hours (>3k): what makes a spike --')
        l = e[e.pub_sp > 3000]
        for c, bins in (('w_spread', [0, 600, 1200, 99999]), ('rescue', [-9e9, -300, 0, 300, 9e9]), ('valve', [-1, 1500, 3000, 99999])):
            print(f'   by {c}:', l.groupby(pd.cut(l[c], bins)).apply(stats)[['hours', 'sell_pl', 'rt_gt_da', 'spike']].round(1).to_dict('index'))
        e.to_csv(C.DATA / 'research' / f'fear_rescue_{z}.csv', index=False)
