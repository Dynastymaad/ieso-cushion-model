"""spike_gasneed.py -- Nov 5 2026, research only. What did bid-time gas need (and friends) look like in hours that spiked and on volatile upside days?"""
import numpy as np, pandas as pd
pd.set_option('display.width', 250)
h = pd.read_csv('data/research/physics_history_EAST.csv', low_memory=False); h['rd'] = h.rt - h.da; h = h.dropna(subset=['rt', 'da'])
h['lm'] = h.ont_dem - h.dem_fc; h['wm'] = h.g_wind - h.wind_fc; h['gm'] = h.g_gas - h.gas_hat
for yr, x in [('2026', h[h.date >= '2026-01-01']), ('Sep-Dec 2025', h[h.date < '2026-01-01'])]:
    print(f'\n################ {yr} ################')
    x = x.copy(); x['cls'] = np.select([x.rd > 100, x.rd > 50, x.rd < -25], ['spike >$100', 'spike $50-100', 'collapse <-$25'], 'normal')
    print('-- bid-time picture by outcome (medians; gas need and spare at the bid, misses after the fact) --')
    t = x.groupby('cls').agg(hours=('rd', 'size'), gas_need=('gas_hat', 'median'), gn_p25=('gas_hat', lambda s: s.quantile(.25)), gn_p75=('gas_hat', lambda s: s.quantile(.75)),
                             spare=('pub_sp', 'median'), wind_fc=('wind_fc', 'median'), da=('da', 'median'), g3=('g3', 'median'),
                             load_gap_bid=('load_gap', 'median'), wind_gap_bid=('wind_gap', 'median'), ny=('ny', 'median'),
                             load_miss=('lm', 'median'), wind_miss=('wm', 'median'), gas_ran_vs_need=('gm', 'median')).round(0)
    print(t.to_string())
    print('-- spike rate by gas need at the bid (all hours) --')
    g = x.groupby(pd.cut(x.gas_hat, [-9e9, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9e9]), observed=True).agg(
        hours=('rd', 'size'), p_gt50=('rd', lambda s: (s > 50).mean() * 100), p_gt100=('rd', lambda s: (s > 100).mean() * 100), mean=('rd', 'mean'), med=('rd', 'median')).round(1)
    g['share_of_all_spikes50'] = (x.groupby(pd.cut(x.gas_hat, [-9e9, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9e9]), observed=True).rd.apply(lambda s: (s > 50).sum()) / (x.rd > 50).sum() * 100).round(0)
    print(g.to_string())
    print('-- spike hours under 4,000 gas need: what was different? (median, spike vs normal) --')
    lo = x[x.gas_hat < 4000]
    print(lo.groupby(lo.rd > 50).agg(hours=('rd', 'size'), gas_need=('gas_hat', 'median'), g3=('g3', 'median'), w3=('w3', 'median'), wind_fc=('wind_fc', 'median'), load_gap=('load_gap', 'median'),
                                     wind_gap=('wind_gap', 'median'), load_miss=('lm', 'median'), wind_miss=('wm', 'median'), he=('he', 'median'), spare=('pub_sp', 'median')).round(0).to_string())
    # volatile upside days
    d = x.groupby('date').agg(max_rd=('rd', 'max'), up_sum=('rd', lambda s: s.clip(lower=0).sum()), mean_rd=('rd', 'mean'), gn_min=('gas_hat', 'min'), gn_max=('gas_hat', 'max'),
                              gn_eve=('gas_hat', lambda s: np.nan), sp_min=('pub_sp', 'min'), wind=('wind_fc', 'mean'), g3max=('g3', 'max'), lgap=('load_gap', 'mean'), wgap=('wind_gap', 'mean'), ny=('ny', 'mean'))
    d['swing'] = d.gn_max - d.gn_min
    top = d.up_sum >= d.up_sum.quantile(.8)
    print(f'-- volatile upside days (top 20% by sum of RT-DA above zero, {top.sum()} days) vs the rest: medians --')
    print(d.groupby(top.map({True: 'top 20% upside', False: 'other days'})).agg(days=('max_rd', 'size'), max_rd=('max_rd', 'median'), mean_rd=('mean_rd', 'median'), gas_min=('gn_min', 'median'),
          gas_max=('gn_max', 'median'), swing=('swing', 'median'), max_3h_ramp=('g3max', 'median'), min_spare=('sp_min', 'median'), wind=('wind', 'median'), load_gap=('lgap', 'median'), wind_gap=('wgap', 'median'), ny=('ny', 'median')).round(0).to_string())
    print('-- share of days that were top-20% upside, by the day\'s biggest 3 h gas ramp at the bid --')
    print(d.assign(top=top).groupby(pd.cut(d.g3max, [-9e9, 1000, 1500, 2000, 2500, 9e9]), observed=True).top.agg(['size', lambda s: s.mean() * 100]).round(0).to_string())
    print('-- ... and by the day\'s swing in gas need (max - min) --')
    print(d.assign(top=top).groupby(pd.cut(d.swing, [-9e9, 2000, 3000, 4000, 5000, 9e9]), observed=True).top.agg(['size', lambda s: s.mean() * 100]).round(0).to_string())
