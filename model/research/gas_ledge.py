"""gas_ledge.py -- Nov 2 2026 research (display/test only). Where is the gas ledge, and how should a gas ramp be read?
Uses data/research/physics_history_{EAST,OTTAWA}.csv (bid-time inputs + settled DA/RT). 2026 for the read, Sep-Dec 2025 as the robustness check."""
import sys, numpy as np, pandas as pd
pd.set_option('display.width', 220)
z = sys.argv[1] if len(sys.argv) > 1 else 'EAST'
h = pd.read_csv(f'data/research/physics_history_{z}.csv', low_memory=False).dropna(subset=['da', 'rt', 'ont_dem', 'g_wind'])
h['net_miss'] = (h.ont_dem - h.dem_fc) - (h.g_wind - h.wind_fc)          # MW more net load than IESO planned (after the fact)
h['util'] = h.gas_hat / h.gas_av                                          # share of available gas expected to run (bid time)
h['yr'] = np.where(h.date >= '2026-01-01', '2026', '2025')
def slope(g):
    if len(g) < 60: return pd.Series(dict(h=len(g), per100=np.nan, r=np.nan, absrd=np.nan))
    b = np.polyfit(g.net_miss.clip(-2000, 2000), g.rd.clip(-150, 300), 1)[0] * 100
    return pd.Series(dict(h=len(g), per100=round(b, 2), r=round(g[['net_miss', 'rd']].corr(method='spearman').iloc[0, 1], 2), absrd=round(g.rd.abs().median(), 1)))
for yr in ('2026', '2025'):
    x = h[h.yr == yr]
    print(f'\n===== {z} {yr}: RT-DA response per 100 MW of realised net-load miss (load above IESO / wind below IESO) =====')
    for name, col, bins in [('public spare (bid)', 'pub_sp', [-9e9, 1500, 2500, 3500, 4500, 5500, 9e9]),
                            ('DA forecast $ (bid)', 'da_fc', [0, 40, 55, 65, 75, 90, 120, 9e9]),
                            ('actual DA $ (after)', 'da', [0, 40, 55, 65, 75, 90, 120, 9e9]),
                            ('gas utilisation need/avail (bid)', 'util', [-9, .3, .45, .55, .65, .75, 9])]:
        g = x.groupby(pd.cut(x[col], bins), observed=True).apply(slope, include_groups=False)
        print(f'-- by {name}'); print(g.to_string())
    print('-- spare x DA forecast ($/MWh per 100 MW of miss; h in brackets)')
    x = x.assign(sb=pd.cut(x.pub_sp, [-9e9, 2500, 3500, 4500, 9e9], labels=['<2.5k', '2.5-3.5k', '3.5-4.5k', '>4.5k']),
                 pb=pd.cut(x.da_fc, [0, 55, 70, 85, 9e9], labels=['<55', '55-70', '70-85', '85+']))
    t = x.groupby(['sb', 'pb'], observed=True).apply(slope, include_groups=False)
    print(t.apply(lambda r: f"{r.per100:+.1f} ({int(r.h)})" if r.h >= 60 else f"n/a ({int(r.h)})", axis=1).unstack().to_string())
