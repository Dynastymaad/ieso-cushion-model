"""nrg_import.py -- NRGStream history (pulled through the browser, saved as data/nrg/nrg2_<KEY>.csv.gz)
-> data/nrg/<KEY>.csv keyed like prices_hourly.csv (date, he).
NRG labels are hour-BEGINNING Eastern prevailing time. Verified against the IESO archive (Jun 28-Sep 26 2026):
DA 98.9% of hours identical to the cent, RT hourly average 97.4% (remaining = rounding of the 12 five-minute prices).
KEY: TOR_/SW_ + DA (price, loss, congestion) | RT (std_dev of 5-min, avg_price) | PD (pre-dispatch price, loss, congestion)."""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]; NRG = ROOT / 'data' / 'nrg'

def to_key(ts_begin):
    t = pd.to_datetime(ts_begin) + pd.Timedelta(hours=1)          # -> hour-ending EPT
    loc = t.dt.tz_localize('America/New_York', ambiguous='NaT', nonexistent='NaT')
    est = loc.dt.tz_convert('Etc/GMT+5').dt.tz_localize(None) - pd.Timedelta(minutes=1)
    return est.dt.date.astype(str), est.dt.hour + 1

def load(key):
    d = pd.read_csv(NRG / f'nrg2_{key}.csv.gz')
    d['date'], d['he'] = to_key(d.ts_ept_begin)
    d = d[d.date.ne('NaT') & d.he.notna()]; d['he'] = d.he.astype(int)
    return d.drop_duplicates(['date', 'he'], keep='last')

if __name__ == '__main__':
    p = pd.read_csv(ROOT / 'data' / 'prices_hourly.csv')
    out = []
    for hub, z in (('TOR', 'TORONTO'), ('SW', 'SOUTHWEST'), ('EAST', 'EAST'), ('OTT', 'OTTAWA'), ('OZP', 'ONTARIO')):
        if not (NRG / f'nrg2_{hub}_DA.csv.gz').exists(): print('skip', hub); continue
        da, rt = load(f'{hub}_DA'), load(f'{hub}_RT')
        pd_ = load(f'{hub}_PD') if (NRG / f'nrg2_{hub}_PD.csv.gz').exists() else pd.DataFrame(columns=['date', 'he', 'price'])
        for c in ('loss', 'congestion'):
            if c not in da: da[c] = float('nan')
        if 'std_dev' not in rt: rt['std_dev'] = float('nan')
        x = da[['date', 'he', 'price', 'loss', 'congestion']].rename(columns={'price': 'da', 'loss': 'da_loss', 'congestion': 'da_cong'}) \
            .merge(rt[['date', 'he', 'avg_price', 'std_dev']].rename(columns={'avg_price': 'rt', 'std_dev': 'rt_sd5'}), on=['date', 'he'], how='outer') \
            .merge(pd_[['date', 'he', 'price']].rename(columns={'price': 'pd'}), on=['date', 'he'], how='outer')
        x['zone'] = z; out.append(x)
        m = x.merge(p[p.zone == z][['date', 'he', 'da', 'rt']], on=['date', 'he'], suffixes=('', '_ieso'))
        for c in ('da', 'rt'):
            q = m.dropna(subset=[c, c + '_ieso'])
            print(f'{z} {c}: {len(q)} overlap h, identical(<=2c) {((q[c]-q[c+"_ieso"]).abs()<=0.02).mean()*100:.1f}%, MAE {(q[c]-q[c+"_ieso"]).abs().mean():.3f}')
    h = pd.concat(out).sort_values(['zone', 'date', 'he'])
    h.to_csv(NRG / 'hub_prices_nrg.csv', index=False)
    for z, g in h.groupby('zone'):
        full = pd.MultiIndex.from_product([sorted(g.date.unique()), range(1, 25)])
        have = pd.MultiIndex.from_frame(g[['date', 'he']])
        print(f'{z}: {g.date.min()}..{g.date.max()} days {g.date.nunique()}; missing DA {g.da.isna().sum() + len(full.difference(have))} h, RT {g.rt.isna().sum()} h, PD {g.pd.isna().sum()} h')
