"""Final morning routine, tested: scorecard (by eye) + physics read (V5). Tiers: A both agree & card |>=3| -> full; C card strong but read disagrees -> stand aside;
B card not strong, read |>=5| -> follow read; N otherwise -> no edge. 1 MW per traded hour, RT-DA settlement, Mar-Oct 2026, bid-time inputs only."""
import pandas as pd, numpy as np, json
def tier(score, read):
    s, r = np.sign(score), np.sign(read)
    return np.select([(abs(score) >= 3) & (s == r), abs(score) >= 3, abs(read) >= 5], ['A', 'C', 'B'], 'N'), np.where(abs(score) >= 3, s, r)
res = {}
for z in ['EAST', 'OTTAWA']:
    t = pd.read_csv(f'data/research/manual_card_{z}.csv'); t['tier'], t['side'] = tier(t.score.values, t.V5.values)
    t['pnl'] = np.where(t.tier.isin(['A', 'B']), t.side * t.rd, 0); d = t.groupby('date').pnl.sum()
    g = t.assign(p=t.side * t.rd).groupby('tier').agg(h=('p', 'size'), avg=('p', 'mean'), hit=('p', lambda x: (x > 0).mean())).round(3)
    g['share'] = (g.h / len(t)).round(3); print(f'\n== {z} =='); print(g.to_string())
    tr = t.tier.isin(['A', 'B'])
    print(f'Trade A+B: {tr.mean():.0%} of hours, ${t.pnl[tr].mean():+.2f}/MWh, hit {(t.pnl[tr]>0).mean():.0%}, total ${t.pnl.sum():,.0f}/MW, months up {(t.groupby("m").pnl.sum()>0).sum()}/8, days up {(d>0).mean():.0%}, worst day ${d.min():,.0f}, ex-July ${t.pnl[t.m!=7].sum():,.0f}')
    print('by month $:', t.groupby('m').pnl.sum().round(0).to_dict())
    ss = t[tr].groupby(['season', 'side']).pnl.agg(['size', 'mean']).round(1); print(ss.to_string())
    res[z] = dict(tiers={k: dict(h=int(v.h), avg=float(v.avg), hit=float(v.hit), share=float(v.share)) for k, v in g.iterrows()},
                  plan=dict(share=float(tr.mean()), avg=float(t.pnl[tr].mean()), hit=float((t.pnl[tr] > 0).mean()), total=float(t.pnl.sum()), months=f'{(t.groupby("m").pnl.sum()>0).sum()}/8', worst=float(d.min())),
                  card_bands=t.groupby(pd.cut(t.score, [-99, -3, -1, 0, 2, 99], labels=['short', 'lean short', 'neutral', 'lean long', 'long']), observed=True).rd.agg(h='size', avg='mean', up=lambda x: (x > 0).mean()).round(2).reset_index().to_dict('records'))
    t[['date', 'he', 'score', 'V5', 'tier', 'side', 'rd', 'pnl']].to_csv(f'data/research/tier_{z}.csv', index=False)
json.dump(res, open('data/research/physics_tiers_test.json', 'w'), default=str)
