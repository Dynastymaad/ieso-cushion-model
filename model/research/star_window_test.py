"""research/star_window_test.py -- Oct 31 2026 (TEST ONLY). Which trailing window should pick the 'star' forecast?
Each morning, star the vendor with the lowest average miss over the last N settled days (through D-2, what is known at the bid),
then score how often that pick was really the best on D, and the miss you would have had following it. N = 3, 7, 14, 30."""
import sys, warnings; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C, supply_fc as S

def frames():
    L = C.load_forecasts_at_bid(); a = C.adq2('preDA')[['date', 'he', 'dem_fc', 'wind_fc']]
    act = pd.read_csv(C.DATA / 'load_at_bid.csv')[['date', 'he', 'ont_dem']]
    ld = a[['date', 'he', 'dem_fc']].rename(columns={'dem_fc': 'IESO'}).merge(L.rename(columns={'lf_tesla': 'Tesla', 'lf_meteologica': 'Meteologica', 'lf_dynasty': 'Dynasty'})[['date', 'he', 'Tesla', 'Meteologica', 'Dynasty']], on=['date', 'he'], how='left').merge(act, on=['date', 'he'])
    w = S.wind_at_bid(); g = C.fuel_actual()[['date', 'he', 'g_wind']]
    wd = a[['date', 'he', 'wind_fc']].rename(columns={'wind_fc': 'IESO'}).merge(w[['date', 'he', 'wf_meteologica']].rename(columns={'wf_meteologica': 'Meteologica'}), on=['date', 'he']).merge(g, on=['date', 'he'])
    return (ld, 'ont_dem', ['IESO', 'Tesla', 'Meteologica', 'Dynasty']), (wd, 'g_wind', ['IESO', 'Meteologica'])

def run(df, act, V, start='2026-04-01'):
    E = pd.DataFrame({v: (df[v] - df[act]).abs() for v in V}); E['date'] = df.date
    d = E.groupby('date').mean(numeric_only=True); cnt = E.groupby('date').count()
    d = d.where(cnt >= 20)                                     # a vendor counts on a day only with 20+ hours
    days = list(d.index); rows = []
    for N in (3, 7, 14, 30):
        for i, D in enumerate(days):
            if D < start or i < 2: continue
            past = d.iloc[max(0, i - 1 - N):i - 1]                # through D-2
            avail = [v for v in V if not np.isnan(d.loc[D, v])]
            if len(avail) < 2: continue
            m = past[avail].mean()
            if m.isna().all() or past[avail].count().min() < max(2, N // 2): continue
            pick = m.idxmin(); best = d.loc[D, avail].idxmin()
            rows.append(dict(N=N, date=D, pick=pick, best=best, hit=pick == best, miss=d.loc[D, pick], best_miss=d.loc[D, best]))
    R = pd.DataFrame(rows)
    return R.groupby('N').agg(days=('hit', 'size'), picked_best_pct=('hit', lambda s: round(s.mean() * 100)), avg_miss_following_star=('miss', 'mean'),
                              avg_miss_best_possible=('best_miss', 'mean')).round(1)

if __name__ == '__main__':
    (ld, la, lv), (wd, wa, wv) = frames()
    print('LOAD (from Apr 1 2026)'); print(run(ld, la, lv).to_string())
    always = {v: round((ld[v] - ld[la]).abs()[ld.date >= '2026-04-01'].mean(), 1) for v in lv}; print('  always one vendor:', always)
    print('\nWIND (from Apr 1 2026)'); print(run(wd, wa, wv).to_string())
    always = {v: round((wd[v] - wd[wa]).abs()[wd.date >= '2026-04-01'].mean(), 1) for v in wv}; print('  always one vendor:', always)
    print('\nLOAD since Sep 1'); print(run(ld, la, lv, '2026-09-01').to_string()); print('\nWIND since Sep 1'); print(run(wd, wa, wv, '2026-09-01').to_string())
