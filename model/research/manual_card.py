"""A scorecard a trader can do by eye from the Fundamentals tab. Points fixed from the physics (not fitted). 2026, bid-time inputs only."""
import pandas as pd, numpy as np, sys
def season(m): return {3: 'spring', 4: 'spring', 5: 'spring', 6: 'summer', 7: 'summer', 8: 'summer', 9: 'fall', 10: 'fall'}.get(m, 'winter')
def card(t):
    L = np.select([t.gL >= 250, t.gL >= 100, t.gL <= -250, t.gL <= -100], [2, 1, -2, -1], 0)          # vendors' load vs IESO
    W = np.select([t.gW >= 200, t.gW <= -200], [1, -1], 0)                                               # IESO wind above Meteo = wind may not show
    R = np.select([t.w3 >= 300, t.w3 <= -300], [-1, 1], 0)                                               # wind arriving / leaving into the hour
    thin = t.pub_sp < 2500                                                                               # thin spare: misses hit harder
    P = np.select([t.vs >= 18, t.vs >= 8, t.vs <= -8], [-2, -1, 1], 0)                                   # what DA already priced
    N = np.select([t.ny_pull >= 10, t.ny_pull <= -10], [1, -1], 0)                                       # NY pulling exports
    return (L + W) * np.where(thin, 2, 1) + R + P + N, L, W, R, P, N
for z in sys.argv[1:] or ['EAST', 'OTTAWA']:
    t = pd.read_csv(f'data/research/physics_read_{z}.csv'); t['m'] = pd.to_datetime(t.date).dt.month; t['season'] = t.m.map(season)
    t['ny_pull'] = t.ny_pull.fillna(0)
    t['score'], t['pL'], t['pW'], t['pR'], t['pP'], t['pN'] = card(t)
    t['call'] = pd.cut(t.score, [-99, -3, -1, 0, 2, 99], labels=['SHORT (<=-3)', 'lean short (-2,-1)', 'neutral (0)', 'lean long (+1,+2)', 'LONG (>=+3)'])
    print(f'\n===== {z} Mar-Oct 2026, {len(t)} h =====')
    g = t.groupby('call', observed=True).rd.agg(h='size', avg='mean', up=lambda x: (x > 0).mean(), spike=lambda x: (x >= 25).mean(), drop=lambda x: (x <= -25).mean()).round(2)
    print(g.to_string())
    print('\nAvg RT-DA by call and season:'); print(t.pivot_table(index='call', columns='season', values='rd', aggfunc='mean', observed=True).round(1)[['spring', 'summer', 'fall']].to_string())
    side = np.sign(t.score); p = side * t.rd; tr = t.score.abs() >= 1; d = p.groupby(t.date).sum()
    print(f'\nTrade every non-zero score 1 MW: {tr.mean():.0%} of hours, ${p[tr].mean():+.2f}/MWh, hit {(p[tr]>0).mean():.0%}, total ${p.sum():,.0f}/MW, months up {(p.groupby(t.m).sum()>0).sum()}/8, days up {(d[d!=0]>0).mean():.0%}, worst day ${d.min():,.0f}')
    big = t.score.abs() >= 3; print(f'Only |score|>=3: {big.mean():.0%} of hours, ${p[big].mean():+.2f}/MWh, hit {(p[big]>0).mean():.0%}, total ${p[big].sum():,.0f}')
    print('By month $/MWh (non-zero):', p[tr].groupby(t.m[tr]).mean().round(1).to_dict())
    pv = np.sign(t.V5) * t.rd; print(f'For reference V5 physics read: ${pv.mean():+.2f}/MWh all hours, total ${pv.sum():,.0f}. Agreement card vs V5 direction (non-zero card): {(np.sign(t.score[tr])==np.sign(t.V5[tr])).mean():.0%}')
    print('\nEach ingredient alone, avg RT-DA when it points long / short, by season:')
    for c, n in [('pL', 'load gap'), ('pW', 'wind gap'), ('pR', 'wind ramp'), ('pP', 'DA priced'), ('pN', 'NY pull')]:
        r = t[t[c] != 0].assign(s=lambda x: np.sign(x[c])); q = r.pivot_table(index='s', columns='season', values='rd', aggfunc='mean').round(1)
        print(f'  {n:10s} long: {q.loc[1].to_dict() if 1 in q.index else "-"}  short: {q.loc[-1].to_dict() if -1 in q.index else "-"}')
    t.to_csv(f'data/research/manual_card_{z}.csv', index=False)
