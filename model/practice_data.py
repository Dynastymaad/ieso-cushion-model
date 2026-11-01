"""Nov 1 2026: data for the Ontario Read Practice page (all days with a physics read, Sep 2025 -> latest).
Bid-time fundamentals + the physics read/card/tier exactly as the live module would have given them (research/physics_history.py),
and the after-the-fact actuals (prices, load, wind, solar, nuclear, hydro, exports, gas)."""
import pandas as pd, numpy as np, json
def r0(v):
    try: return None if v is None or (isinstance(v, float) and np.isnan(v)) else int(round(float(v)))
    except Exception: return None
def r1(v):
    try: return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), 1)
    except Exception: return None
E_ = pd.read_csv('data/research/physics_history_EAST.csv'); O_ = pd.read_csv('data/research/physics_history_OTTAWA.csv')
FUND = ['dem_fc', 'lf_tesla', 'lf_meteologica', 'wind_fc', 'wf_meteologica', 'w_models', 'w_lo', 'w_hi', 'w3', 'solar_fc', 'resid_fc', 'res3', 'gas_av', 'gas_hat', 'pub_sp', 'g3', 'hyd_exp', 'exp_exp', 'head', 'nuc_av']
HUB = ['da_fc', 'vs', 'read', 'base', 'p_Load gap', 'p_Wind gap', 'p_Spare', 'p_DA priced', 'p_Ramps', 'p_NY pull', 'p_Hour/weekend', 'score', 'c_Load gap', 'c_Wind gap', 'c_Wind ramp', 'c_DA priced', 'c_NY pull', 'thin', 'tier', 'side', 'soft', 'da', 'rt', 'load_gap', 'wind_gap', 'ny']
ACT = ['ont_dem', 'g_wind', 'g_solar', 'g_nuclear', 'g_hydro', 'g_gas', 'tot_flow']
days = []
for D, g in E_.groupby('date'):
    g = g.sort_values('he'); o = O_[O_.date == D].set_index('he')
    def hub(x):
        out = []
        for _, r in x.iterrows():
            row = []
            for c in HUB:
                v = r.get(c)
                if c in ('tier',): row.append(v if isinstance(v, str) else 'N')
                elif c in ('thin', 'soft'): row.append(1 if v is True or v == 'True' or v == 1 else 0)
                elif c in ('vs', 'read', 'base', 'da', 'rt', 'da_fc', 'ny') or c.startswith('p_'): row.append(r1(v))
                else: row.append(r0(v))
            out.append(row)
        return out
    days.append(dict(d=D, wk=int(g.wkend.iloc[0]) if pd.notna(g.wkend.iloc[0]) else 0, miss=str(g.missing.iloc[0]) if isinstance(g.missing.iloc[0], str) else '',
                     he=[int(h) for h in g.he], f=[[r0(r[c]) for c in FUND] for _, r in g.iterrows()], E=hub(g), O=hub(o.reset_index().sort_values('he')) if len(o) else [],
                     a=[[r0(r[c]) for c in ACT] for _, r in g.iterrows()]))
json.dump(dict(FUND=FUND, HUB=HUB, ACT=ACT, days=days), open('data/research/practice_data.json', 'w'), separators=(',', ':'))
print(len(days), days[0]['d'], days[-1]['d'])

# build the page: python model/practice_data.py  -> site/practice.html (publish that file as the practice artifact)
shell = open('model/practice_shell.html', encoding='utf-8').read()
open('site/practice.html', 'w', encoding='utf-8').write(shell.replace('const P=__DATA__;', 'const P=' + open('data/research/practice_data.json', encoding='utf-8').read() + ';'))
print('page -> site/practice.html')
