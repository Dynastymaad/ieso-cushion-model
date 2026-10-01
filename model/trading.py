"""trading.py -- virtual-trading backtest at the hubs, 1 MW per hour, bid-time inputs only.
A DA sell (virtual offer) earns DA - RT; a DA buy (virtual bid) earns RT - DA.
No uplift / fees included (DRSU on virtual offers is not public)."""
import sys, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, hourly as Hm, spread as S

def rules(d):
    tight = d['head'] < 8500; eve = d.he.between(14, 21)
    R = {
      'sell every hour': np.full(len(d), -1),
      'sell HE14-21 only': np.where(eve, -1, 0),
      'sell when tight (headroom < 8,500)': np.where(tight, -1, 0),
      'sell when tight AND HE14-21': np.where(tight & eve, -1, 0),
      'sell when Tesla >=600 MW below IESO': np.where(d.gapT <= -0.6, -1, 0),
      'buy when Tesla >=600 MW above IESO': np.where(d.gapT >= 0.6, 1, 0),
      'model: sell tight|Tesla-low, buy Tesla-high & loose': np.where((tight & eve) | (d.gapT <= -0.6), -1,
                                                              np.where((d.gapT >= 0.6) & ~tight, 1, 0)),
    }
    return R

def score(d, pos):
    m = pos != 0; pnl = pos[m] * (d.rt.values[m] - d.da.values[m])
    if m.sum() == 0: return {}
    dd = pd.Series(pnl).groupby(d.date.values[m]).sum()
    return dict(hours=int(m.sum()), usd_per_MWh=pnl.mean(), win_rate=(pnl > 0).mean(), total_usd_1MW=pnl.sum(),
                worst_hour=pnl.min(), worst_day=dd.min(), days_traded=len(dd), days_positive=(dd > 0).mean())

if __name__ == '__main__':
    out = []
    for z in ['TORONTO', 'SOUTHWEST']:
        d = Hm.frame(z).dropna(subset=['da', 'rt', 'head'])
        d = d[(d.date >= '2026-06-28') & (d.date <= '2026-09-26')].reset_index(drop=True)
        d['gapT'] = d.gapT.fillna(0)
        for k, pos in rules(d).items():
            s = score(d, pos); s.update(hub=z, rule=k); out.append(s)
    T = pd.DataFrame(out)[['hub', 'rule', 'hours', 'usd_per_MWh', 'win_rate', 'total_usd_1MW', 'worst_hour', 'worst_day', 'days_traded', 'days_positive']]
    T.to_csv(C.DATA / 'bt_trading_rules.csv', index=False)
    print(T.round(2).to_string(index=False))
