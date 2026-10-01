"""New York interchange + Tesla load panel for the Next day tab.

NY side (NYISO public reports, pulled by ieso_backfill.nyiso()):
  nyiso_zoneA_da.csv   Zone A (WEST) DA LBMP, posts ~09:33 ET on D-1 -> usually in before the IESO 10:00 ET close
  nyiso_dam_energy.csv NYISO DAM scheduled interchange at the Ontario proxy (ny_dni_oh = NY net import FROM Ontario,
                       i.e. + = Ontario exporting to NY), posts ~09:40-09:55 ET -> sometimes misses the close
Ontario side: IESO Adequacy 'final' zonal NY export/import schedules (what cleared in IESO's DAM), for past days.
Levels are percentiles against the trailing 30 days (hourly) / 60 days (daily). Context only: the quartile test
below is recomputed each run and printed on the page; nothing here feeds the signal.
"""
import numpy as np, pandas as pd
import common as C

PEAK = range(16, 22)


def _lvl(x, ref):
    ref = pd.Series(ref).dropna()
    if x is None or pd.isna(x) or len(ref) < 10: return None, None
    p = float((ref < x).mean() * 100)
    return round(p), ('High' if p >= 75 else 'Low' if p <= 25 else 'Normal')


def _quartile_test(ne, za):
    out = {}
    for z in ('EAST', 'OTTAWA'):
        f = pd.read_csv(C.DATA / f'dv_frame_{z}.csv').drop(columns=['nyA_da'], errors='ignore')
        f = f[(f.date >= '2025-07-01') & f.rt.notna() & (f.v2 == 1)].merge(ne, on=['date', 'he'], how='left').merge(za, on=['date', 'he'], how='left')
        f['pl'] = f.da - f.rt; f['spr'] = f.nyA_da - f.p_da
        r = {}
        for c in ('ny_dni_oh', 'spr'):
            q = pd.qcut(f[c], 4, labels=False)
            g = f.groupby(q).agg(lo=(c, 'min'), hi=(c, 'max'), n=('pl', 'size'), mean=('pl', 'mean'))
            r[c] = [dict(lo=round(a.lo), hi=round(a.hi), n=int(a.n), mean=round(a['mean'], 1)) for _, a in g.iterrows()]
        out[z] = r
    return out


def build(D, p_da_by_he):
    ne = pd.read_csv(C.DATA / 'nyiso_dam_energy.csv')
    za = pd.read_csv(C.DATA / 'nyiso_zoneA_da.csv')
    d30 = (pd.Timestamp(D) - pd.Timedelta(days=30)).date().isoformat()
    d60 = (pd.Timestamp(D) - pd.Timedelta(days=60)).date().isoformat()
    last_posted = ne.date.max(); posted = D in set(ne.date)
    ref_day = D if posted else last_posted
    h30 = ne[(ne.date >= d30) & (ne.date < D)]
    za30 = za[(za.date >= d30) & (za.date < D)]
    hours = []
    for he in range(1, 25):
        x = ne[(ne.date == ref_day) & (ne.he == he)]; v = None if x.empty else float(x.ny_dni_oh.iloc[0])
        ref = h30[h30.he == he].ny_dni_oh
        pct, lab = _lvl(v, ref)
        a = za[(za.date == D) & (za.he == he)]; nyA = None if a.empty else round(float(a.nyA_da.iloc[0]), 2)
        pda = p_da_by_he.get(he)
        hours.append(dict(he=he, ny_oh=None if v is None else round(v), med30=None if ref.empty else round(float(ref.median())),
                          pct=pct, lvl=lab, nyA=nyA, nyA_med30=None if za30[za30.he == he].empty else round(float(za30[za30.he == he].nyA_da.median()), 2),
                          p_da=None if pda is None else round(pda, 2), spr=None if (nyA is None or pda is None) else round(nyA - pda, 2)))
    # daily history: NYISO DAM schedule at the Ontario proxy + IESO's own cleared NY schedules
    ne['pk'] = ne.he.isin(PEAK)
    dd = ne[ne.date >= d60].groupby('date').agg(all=('ny_dni_oh', 'mean'))
    dd['peak'] = ne[(ne.date >= d60) & ne.pk].groupby('date').ny_dni_oh.mean()
    ax = pd.read_csv(C.CACHE / 'ieso_adq2x_final.csv')
    ax = ax[ax.subtype.isin(['New York Schedule']) & ax.resourcetype.isin(['Zonal Export', 'Zonal Import']) & (ax.date >= d60)]
    ax = ax.drop_duplicates(['date', 'hour', 'resourcetype'], keep='last')
    ex = ax[ax.resourcetype == 'Zonal Export'].assign(v=lambda t: t.value.abs())
    im = ax[ax.resourcetype == 'Zonal Import']
    dd['ieso_exp_pk'] = ex[ex.hour.isin(PEAK)].groupby('date').v.mean()
    dd['ieso_imp_pk'] = im[im.hour.isin(PEAK)].groupby('date').value.mean()
    dd = dd.reset_index().sort_values('date')
    days = []
    for _, r in dd.tail(10).iterrows():
        prior = dd[dd.date < r.date].tail(60)
        p1, l1 = _lvl(r.peak, prior.peak); p2, l2 = _lvl(r.ieso_exp_pk, prior.ieso_exp_pk)
        J = lambda v: None if pd.isna(v) else round(float(v))
        days.append(dict(date=r.date, ny_all=J(r['all']), ny_pk=J(r.peak), ny_pk_pct=p1, ny_pk_lvl=l1,
                         ieso_exp_pk=J(r.ieso_exp_pk), ieso_exp_pct=p2, ieso_exp_lvl=l2, ieso_imp_pk=J(r.ieso_imp_pk)))
    return dict(date=D, posted=posted, ref_day=ref_day, hours=hours, days=days, test=_quartile_test(ne[['date', 'he', 'ny_dni_oh']], za))


def tesla(D):
    """Tesla vs IESO at the bid, against the usual gap (30-day median by HE) and each forecast's recent bias vs actual."""
    w = C.load_forecasts_at_bid(); a = C.adq2('preDA')[['date', 'he', 'dem_fc']]
    m = w.merge(a, on=['date', 'he'], how='right')
    m['g'] = m.lf_tesla - m.dem_fc; m['g2'] = m.lf_tesla - m.lf_ieso
    d30 = (pd.Timestamp(D) - pd.Timedelta(days=30)).date().isoformat()
    base = m[(m.date >= d30) & (m.date < D)]
    med = base.groupby('he').g.median(); med2 = base.groupby('he').g2.median()
    # bias vs actual (Jul 1 onward)
    act = pd.read_csv(C.CACHE / 'ieso_load_actual.csv'); t = pd.to_datetime(act.EffectiveDateTime) + pd.Timedelta(hours=1)
    act['date'], act['he'] = C._ts_to_key(t); act = act.dropna(subset=['he']); act['he'] = act.he.astype(int)
    b = m.merge(act[['date', 'he', 'Load']], on=['date', 'he']); b = b[(b.date >= '2026-07-01') & (b.date < D)]
    pk = b.he.between(16, 20)
    bias = {k: dict(all=round(float((b[c] - b.Load).mean())), peak=round(float((b[c] - b.Load)[pk].mean())), mae=round(float((b[c] - b.Load).abs().mean())))
            for k, c in (('tesla', 'lf_tesla'), ('ieso_fc', 'lf_ieso'), ('ieso_adq', 'dem_fc'))}
    f = pd.read_csv(C.CACHE / 'ieso_load_fc.csv', usecols=['DataSourceName', 'Timestamp', 'EffectiveDateTime', 'DateCreated'])
    f = f[(f.DataSourceName == 'Tesla') & f.EffectiveDateTime.str.startswith(D)]
    issued = None if f.empty else f.Timestamp.max()[:16]
    x = m[m.date == D].sort_values('he'); J = lambda v: None if pd.isna(v) else round(float(v))
    hrs = [dict(he=int(r.he), tesla=J(r.lf_tesla), adq=J(r.dem_fc), ieso_fc=J(r.lf_ieso), gap=J(r.g), gap_fc=J(r.g2),
                usual=J(med.get(r.he)), vs_usual=None if pd.isna(r.g) or pd.isna(med.get(r.he)) else round(float(r.g - med.get(r.he))))
           for _, r in x.iterrows()]
    d1 = (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat()
    stale = issued is None or issued[:10] < d1
    return dict(issued=issued, stale=bool(stale), hours=hrs, bias=bias)
