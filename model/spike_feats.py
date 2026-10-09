"""spike_feats.py -- Oct 8 2026: bid-time feature frame for the spike-prediction test (spike_model.py).
Adds to dv_frame/cahr_frame: NWP wind-model spread at the bid (Frontier/NAM/NAM_Nest/GFS/GEM, DateCreated <= D-1 08:00),
gas spare vs gas need, residual ramp into the hour, Tesla vs usual, spikes in the last days known (D-2..D-4)."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C

def wind_models():
    w = pd.read_csv(C.CACHE / 'ieso_wind_fc.csv')
    w = w[w.DataSourceName.isin(['Frontier', 'NAM', 'NAM_Nest', 'GFS', 'GEM(CMC)', 'IESO'])]
    eff = pd.to_datetime(w.EffectiveDateTime.str[:19]) + pd.Timedelta(hours=1)
    w['date'], w['he'] = C._ts_to_key(eff); w = w.dropna(subset=['he']); w['he'] = w.he.astype(int)
    ld = pd.to_datetime(w.DateCreated.str[:19]); dl = pd.to_datetime(w.date) - pd.Timedelta(days=1) + pd.Timedelta(hours=8)
    w = w[ld <= dl].sort_values('Timestamp')
    last = w.groupby(['date', 'he', 'DataSourceName']).Value.last().unstack()
    nwp = last[['Frontier', 'NAM', 'NAM_Nest', 'GFS', 'GEM(CMC)']]
    out = pd.DataFrame({'w_nwp_mean': nwp.mean(1), 'w_nwp_min': nwp.min(1), 'w_nwp_sd': nwp.std(1), 'w_ieso_vend': last.get('IESO')}).reset_index()
    return out

for z in ('EAST', 'OTTAWA'):
    d = pd.read_csv(C.DATA / f'dv_frame_{z}.csv'); c = pd.read_csv(C.DATA / f'cahr_frame_{z}.csv')[['date', 'he', 'why', 'cahr']]
    s = pd.read_csv(C.DATA / f'spike_frame_{z}.csv')[['date', 'he', 'tvu', 'spk_d2_4', 'max_d2_4', 'gas_out_p', 'wr3']]
    m = d.merge(c, on=['date', 'he'], how='left').merge(s, on=['date', 'he'], how='left').merge(wind_models(), on=['date', 'he'], how='left')
    m['rd'] = m.rt - m.da; m['spk'] = (m.rd >= 50).astype(float); m.loc[m.rt.isna(), 'spk'] = np.nan
    m['gas_spare'] = m.gas_av - m.gas_hat
    m = m.sort_values(['date', 'he']); m['resid'] = m.dem_fc - m.nuc_av - m.wind_fc.fillna(0) - m.solar_fc.fillna(0)
    m['resid_ramp3'] = m.groupby('date').resid.diff(3); m['head_min_day'] = m.groupby('date')['head'].transform('min')
    m['w_gap_nwp'] = m.w_nwp_mean - m.wind_fc; m['w_gap_min'] = m.w_nwp_min - m.wind_fc
    m['month'] = pd.to_datetime(m.date).dt.month; m['sell'] = m.why.notna().astype(int)
    m.to_csv(C.DATA / f'spike_feats_{z}.csv', index=False)
    print(z, len(m), m.date.min(), m.date.max(), 'coverage:', m[['tvu', 'w_nwp_sd', 'gas_spare', 'cahr', 'spk_d2_4']].notna().mean().round(2).to_dict())
