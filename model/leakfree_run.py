import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import pandas as pd, spike_model as SM, spike_model2_robust as R0
for z in ('EAST', 'OTTAWA'):
    m = SM.prep(z).merge(R0.S, on=['date', 'he'], how='left')
    rows = []
    for nm, FE, kw in (('baseline', SM.FE, {}), ('NEW leak-free', SM.FE + R0.NEW, {}), ('NEW depth 2', SM.FE + R0.NEW, dict(depth=2, it=300)), ('NEW lr .1', SM.FE + R0.NEW, dict(lr=.1, it=150)), ('NEW depth4', SM.FE + R0.NEW, dict(depth=4, lr=.03, it=300))):
        r, b = R0.run(m, FE, **kw); rows.append(dict(test=nm, **r))
        if nm == 'NEW leak-free': bb = b
    print(z); print(pd.DataFrame(rows).to_string(index=False)); print('  months:', bb.groupby(bb.date.str[:7]).rd.mean().round(1).to_dict())
    bb[['date','he','da','rt','rd','p_da','head','buyband']].to_csv(f'../data/spike_buy_picks_{z}.csv', index=False)
