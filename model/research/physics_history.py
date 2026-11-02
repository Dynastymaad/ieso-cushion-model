"""The physics read, card and tier exactly as the live module would have given them each morning (daily refit through D-2, starred
forecast gaps, bid-time inputs only), Sep 8 2025 -> latest, plus the after-the-fact actuals for the practice page."""
import sys; sys.path.insert(0, 'model/research'); sys.path.insert(0, 'model')
import pandas as pd, numpy as np, json, common as C, fear_rescue as FR, physics_read_live as P
z = sys.argv[1]; NOSTAR = 'nostar' in sys.argv
if NOSTAR: P.USE_STAR = False
try: KEEP = json.load(open(C.ROOT / 'site' / 'data' / 'bundle.json'))['target']         # the delivery day the desk was just built for
except Exception: KEEP = pd.read_csv(C.DATA / f'dv_frame_{z}.csv', usecols=['date']).date.max()
e = FR.frame(z, keep=KEEP, all_rows=True).sort_values(['date', 'he']).reset_index(drop=True)
o = pd.read_csv('data/research/oct31_prices.csv'); o = o[o.zone == z].set_index('he')
k = (e.date == '2026-10-31') & e.rt.isna(); e.loc[k, 'da'] = e.loc[k, 'he'].map(o.da); e.loc[k, 'rt'] = e.loc[k, 'he'].map(o.rt)   # Oct 31 fetched from IESO by hand; used only until the price pull has it
g = e.groupby('date'); e['w3'] = e.wind_fc - g.wind_fc.shift(3); e['g3'] = e.gas_hat - g.gas_hat.shift(3); e['res3'] = e.resid_fc - g.resid_fc.shift(3)
e['vs'] = e.p_da - e.groupby('he').p_da.transform(lambda s: s.shift(1).rolling(14, min_periods=5).median()); e['rd'] = e.rt - e.da
nw = [c for c in e if c.startswith('wf_') and c != 'wf_meteologica']; e['w_lo'] = e[nw].min(axis=1); e['w_hi'] = e[nw].max(axis=1)
e = P.prep(e, P.ieso_bias(e))
act = C.actual_demand()[['date', 'he', 'ont_dem']].merge(C.fuel_actual(), on=['date', 'he'], how='outer').merge(pd.read_csv(C.DATA / 'intertie_actual.csv')[['date', 'he', 'tot_flow']], on=['date', 'he'], how='outer')
out = []
for D in sorted(e.date.unique()):
    if D < '2025-09-08': continue
    try: rows, n, miss = P.read(e, D)
    except Exception as ex: continue
    if n < 500: continue
    for x in rows:
        P.annotate(x); i = x['inputs']
        out.append(dict(date=D, he=x['he'], read=x['read'], base=x['base'], **{'p_' + k: v for k, v in x['pieces'].items()}, score=x['card'], **{'c_' + k: v for k, v in x['card_pts'].items()},
                        thin=x['thin'], tier=x['tier'], side=x['side'], soft=x['soft'], action=x['action'], load_src=i['load_src'], wind_src=i['wind_src'], load_gap=i['load_gap'], wind_gap=i['wind_gap'],
                        w3=i['w3'], w_up=i.get('w_up'), vs=i['vs'], ny=i['ny'], missing='|'.join(miss), rd=x['rd'], da_fc=x['da_fc']))
h = pd.DataFrame(out)
keep = ['date', 'he', 'dem_fc', 'lf_tesla', 'lf_meteologica', 'lf_dynasty', 'wind_fc', 'wf_meteologica', 'w_models', 'w_lo', 'w_hi', 'solar_fc', 'nuc_av', 'hyd_exp', 'exp_exp', 'resid_fc',
        'gas_hat', 'gas_av', 'pub_sp', 'priv_sp', 'head', 'g3', 'res3', 'da', 'rt', 'wkend']
h = h.merge(e[keep], on=['date', 'he'], how='left').merge(act, on=['date', 'he'], how='left')
h.to_csv(f'data/research/physics_history_{z}{"_nostar" if NOSTAR else ""}.csv', index=False)
print(z, len(h), h.date.min(), h.date.max(), 'tiers', h.tier.value_counts().to_dict(), 'soft', int(h.soft.sum()))
