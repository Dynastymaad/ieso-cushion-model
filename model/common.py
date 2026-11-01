"""Shared loaders. Every table comes out keyed on (date, he) in the IESO clock:
EST all year, hour-ending HE1..24."""
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE, DATA, ARCH = ROOT / 'cache', ROOT / 'data', ROOT / 'archive'


def onpeak(date, he):
    """Nov 1 2026: Ontario on-peak block (XDE) is 07:00-23:00 Eastern PREVAILING time. On the IESO clock (EST all year) that is
    HE7-22 while daylight time is on (Mar-Nov) and HE8-23 in standard time (Nov-Mar). Vectorised over date / he."""
    d = pd.to_datetime(pd.Series(date).values) + pd.Timedelta(hours=12)
    dst = pd.Series(d).dt.tz_localize('America/New_York').map(lambda t: bool(t.dst())).values
    h = pd.Series(he).values
    return pd.Series(np.where(dst, (h >= 7) & (h <= 22), (h >= 8) & (h <= 23)), index=he.index if isinstance(he, pd.Series) else None)


def _ts_to_key(ts_he):
    """hour-ending timestamp (EST) -> (date, he)"""
    x = ts_he - pd.Timedelta(minutes=1)
    return x.dt.date.astype(str), x.dt.hour + 1


def actual_demand():
    parts = []
    for f in sorted((ARCH / 'Demand').glob('PUB_Demand_*.csv')):
        d = pd.read_csv(f, skiprows=3); d.columns = ['date', 'he', 'mkt_dem', 'ont_dem']; parts.append(d)
    return pd.concat(parts).drop_duplicates(['date', 'he'], keep='last')


def load_forecasts_at_bid():
    """Vendor load forecasts as they stood at the DA bid deadline (D-1 08:00 MT).
    Warehouse loads once a day ~04:28 (DateCreated); IESO/Tesla/Meteologica rows
    are usable if loaded on or before D-1. DYNASTY rows are the desk's own
    forecast: usable if issued (Timestamp, MT) before D-1 08:00.
    EffectiveDateTime is hour-BEGINNING: IESO/Tesla/DYNASTY in EST,
    Meteologica in Eastern prevailing time (measured alignment, see notes)."""
    f = pd.read_csv(CACHE / 'ieso_load_fc.csv')
    f['eff'] = pd.to_datetime(f.EffectiveDateTime.str.slice(0, 19))
    f['issued'] = pd.to_datetime(f.Timestamp.str.slice(0, 19))
    f['loaded'] = pd.to_datetime(f.DateCreated.str.slice(0, 19))
    met = f.DataSourceName == 'Meteologica'
    eff_est = f.eff.copy()
    eff_est[met] = (f.eff[met].dt.tz_localize('America/New_York', ambiguous='NaT', nonexistent='NaT')
                    .dt.tz_convert('Etc/GMT+5').dt.tz_localize(None))
    if 'EffectiveDateTimeUtc' in f:                     # Nov 1 2026: the UTC stamp is unambiguous (fall-back day keeps all 24 hours)
        utc = pd.to_datetime(f.EffectiveDateTimeUtc.astype(str).str.slice(0, 19), errors='coerce') - pd.Timedelta(hours=5)
        eff_est = utc.fillna(eff_est)
    ts_he = eff_est + pd.Timedelta(hours=1)
    f['date'], f['he'] = _ts_to_key(ts_he)
    d = pd.to_datetime(f.date)
    deadline = d - pd.Timedelta(days=1) + pd.Timedelta(hours=8)
    ok = np.where(f.DataSourceName == 'DYNASTY', f.issued <= deadline, f.loaded <= deadline)
    f = f[ok & f.he.notna()].sort_values('issued')
    last = f.groupby(['DataSourceName', 'date', 'he']).agg(load=('Load', 'last'), issued=('issued', 'last')).reset_index()
    w = last.pivot_table(index=['date', 'he'], columns='DataSourceName', values='load').reset_index()
    w.columns = ['date', 'he'] + [f'lf_{c.lower()}' for c in w.columns[2:]]
    w['he'] = w.he.astype(int)
    return w


def adq2(which='preDA'):
    """IESO Adequacy2 vintage, wide: one row per (date, he)."""
    a = pd.read_csv(CACHE / f'ieso_adq2_{which}.csv')
    a['k'] = (a.resourcetype + '|' + a.subtype)
    w = a.pivot_table(index=['date', 'hour'], columns='k', values='value').reset_index()
    w = w.rename(columns={'hour': 'he'})
    ren = {'Ontario Demand|Forecast': 'dem_fc', 'Internal Resource|Nuclear Capacity': 'nuc_cap',
           'Internal Resource|Nuclear Outage': 'nuc_out', 'Internal Resource|Gas Capacity': 'gas_cap',
           'Internal Resource|Gas Outage': 'gas_out', 'Internal Resource|Hydro Capacity': 'hyd_cap',
           'Internal Resource|Hydro Outage': 'hyd_out', 'Internal Resource|Wind Forecast': 'wind_fc',
           'Internal Resource|Solar Forecast': 'solar_fc', 'Internal Resource|Wind Capacity': 'wind_cap',
           'Internal Resource|Storage Capacity': 'sto_cap', 'Internal Resource|Storage Outage': 'sto_out',
           'Internal Resource|Biofuel Capacity': 'bio_cap', 'Internal Resource|Biofuel Outage': 'bio_out',
           'Excess|Capacity': 'exc_cap', 'Excess|Offered Capacity': 'exc_off', 'Forecast Supply|Capacity': 'sup_cap',
           'Embedded Generation|Wind': 'emb_wind', 'Embedded Generation|Solar': 'emb_solar',
           'Internal Resource|Hydro Forecast Energy': 'hyd_energy', 'Internal Resource|Gas Schedule': 'gas_sch',
           'Internal Resource|Nuclear Schedule': 'nuc_sch', 'Internal Resource|Hydro Schedule': 'hyd_sch'}
    w = w.rename(columns=ren)
    keep = ['date', 'he'] + [c for c in ren.values() if c in w.columns]
    w = w[keep].copy()
    w['nuc_av'] = w.nuc_cap - w.nuc_out; w['gas_av'] = w.gas_cap - w.gas_out; w['hyd_av'] = w.hyd_cap - w.hyd_out
    w['resid_fc'] = w.dem_fc - w.nuc_av - w.wind_fc.fillna(0) - w.solar_fc.fillna(0)
    w['head'] = w.gas_av + w.hyd_av - w.resid_fc
    w['he'] = w.he.astype(int)
    return w


def fuel_actual():
    import xml.etree.ElementTree as ET
    rows = []
    for f in sorted((ARCH / 'GenOutputbyFuelHourly').glob('*.xml')):
        r = ET.parse(f).getroot()
        for e in r.iter():
            if '}' in e.tag: e.tag = e.tag.split('}', 1)[1]
        for day in r.iter('DailyData'):
            d = day.find('Day').text
            for hd in day.iter('HourlyData'):
                h = int(hd.find('Hour').text); row = {'date': d, 'he': h}
                for ft in hd.iter('FuelTotal'):
                    o = ft.find('.//Output'); row['g_' + ft.find('Fuel').text.lower()] = float(o.text) if o is not None and o.text else np.nan
                rows.append(row)
    return pd.DataFrame(rows).drop_duplicates(['date', 'he'], keep='last')


def prices(zone=None, history=True):
    """Hub DA/RT keyed (zone, date, he). IESO archive where we have it (latest ~90 days);
    NRGStream history (data/nrg/hub_prices_nrg.csv, May 2025 ->) fills the rest when history=True."""
    p = pd.read_csv(DATA / 'prices_hourly.csv')
    n = DATA / 'nrg' / 'hub_prices_nrg.csv'
    if history and n.exists():
        h = pd.read_csv(n)[['zone', 'date', 'he', 'da', 'rt']]
        k = p.set_index(['zone', 'date', 'he']).index
        hk = h.set_index(['zone', 'date', 'he'])
        # Nov 1 2026: an hour IESO's archive has without RT (or DA) takes NRG's value when NRG has it
        pi = p.set_index(['zone', 'date', 'he'])
        for c in ('da', 'rt'):
            miss = pi[c].isna(); fill = hk[c].reindex(pi.index[miss])
            pi.loc[miss, c] = fill.values
        p = pi.reset_index()
        h = h[~hk.index.isin(k)]
        p = pd.concat([p, h], ignore_index=True).sort_values(['zone', 'date', 'he']).reset_index(drop=True)
    return p if zone is None else p[p.zone == zone]


def daily_blocks():
    """Settled DA block averages from the warehouse (rows struck AFTER the strip day):
    XDE = on-peak HE8-23 EPT (= IESO HE7-22 in daylight time, HE8-23 in standard time: see onpeak()), XDG = off-peak, XDY = flat. CAD."""
    f = pd.read_csv(CACHE / 'fwd_daily_ontario.csv', parse_dates=['EffectiveDate', 'Strip'])
    f = f[(f.NodeName == 'Ontario Hub') & (f.ExchangeCode.isin(['XDE', 'XDG', 'XDY']))]
    s = f[f.Strip < f.EffectiveDate].sort_values('EffectiveDate').groupby(['Strip', 'ExchangeCode']).Price.last().unstack()
    s.index = s.index.date.astype(str); s.index.name = 'date'
    return s.rename(columns={'XDE': 'da_on', 'XDG': 'da_off', 'XDY': 'da_flat'}).reset_index()
