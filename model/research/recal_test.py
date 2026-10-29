"""research/recal_test.py -- Oct 28 2026 (TEST ONLY, touches nothing in the model).
Part 1: gas-need (cushion) bias by month/week, and whether a trailing-window bias correction makes it more accurate.
Part 2: RT read candidates, walk-forward, scored against actual RT and on the sign of RT - DA.
Part 3: hour x hour correlation of East RT - DA, and which window (all / 30 / 14 days) best predicts the next 14 days."""
import sys, json, warnings; warnings.filterwarnings('ignore')
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 220)
OUT = C.DATA / 'research'

def part1():
    d = json.loads((C.DATA / 'fund_history.json').read_text())
    f = pd.DataFrame([dict(date=k, **x) for k, v in d.items() for x in v])
    G = C.fuel_actual()[['date', 'he', 'g_gas']]
    m = f.merge(G, on=['date', 'he']).sort_values(['date', 'he'])
    m['miss'] = m.g_gas - m.need                                   # + = more gas ran than the model said was needed
    days = sorted(m.date.unique()); res = []
    for w in (0, 7, 14, 30):
        m[f'c{w}'] = np.nan
        if w:
            for i, D in enumerate(days):
                if i < 3: continue
                tr = m[(m.date < days[max(0, i - 1)]) & (m.date >= days[max(0, i - 1 - w)])]   # through D-2 (D-1 actuals not complete at the bid)
                b = tr.groupby('he').miss.mean()
                k = m.date == D; m.loc[k, f'c{w}'] = m.loc[k, 'need'] + m.loc[k, 'he'].map(b)
        else: m['c0'] = m.need
    t = m[m.date >= '2026-08-01'].dropna(subset=['c30'])
    for w in (0, 7, 14, 30):
        e = t.g_gas - t[f'c{w}']
        res.append(dict(window='none' if w == 0 else f'{w} days', mae=round(e.abs().mean()), bias=round(e.mean()),
                        mae_oct=round(e[t.date >= '2026-10-01'].abs().mean()), mae_last14=round(e[t.date >= days[-14]].abs().mean())))
    m['wk'] = pd.to_datetime(m.date).dt.to_period('W').astype(str).str[:10]
    weekly = m.groupby('wk').agg(need=('need', 'mean'), gas=('g_gas', 'mean'), miss=('miss', 'mean')).round(0)
    return pd.DataFrame(res), weekly, m

def part2():
    import fund_read as FR
    f = FR.feats(pd.read_csv(C.DATA / 'dv_frame_EAST.csv'))
    f = f[f.rt.notna() & f.da.notna()].copy(); f['pred_all'] = np.nan; f['pred_60'] = np.nan
    weeks = pd.date_range('2026-07-06', f.date.max(), freq='7D')
    for s in weeks:
        e = (s + pd.Timedelta(days=6)).date().isoformat(); s0 = s.date().isoformat(); cut = (s - pd.Timedelta(days=2)).date().isoformat()
        te = (f.date >= s0) & (f.date <= e)
        if not te.any(): continue
        for name, lo in (('pred_all', '2025-06-01'), ('pred_60', (s - pd.Timedelta(days=62)).date().isoformat())):
            tr = f[(f.date <= cut) & (f.date >= lo)]
            f.loc[te, name] = -FR._fit(tr).predict(f.loc[te, FR.FE])      # RT - DA
    # trailing 14-day median RT - DA by hour (through D-2)
    f['x'] = f.rt - f.da; days = sorted(f.date.unique()); f['b14'] = np.nan
    for i, D in enumerate(days):
        if i < 16: continue
        tr = f[(f.date <= days[i - 2]) & (f.date > days[i - 16])]; k = f.date == D
        f.loc[k, 'b14'] = f.loc[k, 'he'].map(tr.groupby('he').x.median())
    t = f[(f.date >= '2026-07-06') & f.pred_all.notna()].copy()
    cand = {'Model DA forecast (RT = DA)': t.p_da, 'Current RT forecast (p_rt)': t.p_rt, 'DA fc + fundamentals read (all history)': t.p_da + t.pred_all,
            'DA fc + fundamentals read (last 60 days)': t.p_da + t.pred_60, 'DA fc + 14-day hourly median RT-DA': t.p_da + t.b14}
    rows = []
    for k, v in cand.items():
        e = (v - t.rt); s = np.sign(v - t.p_da); hit = (s == np.sign(t.rt - t.da))[s != 0]
        for per, msk in (('Jul 6 - Oct 27', t.date >= '0'), ('Oct', t.date >= '2026-10-01'), ('last 14 d', t.date >= days[-14])):
            rows.append(dict(candidate=k, period=per, hours=int(msk.sum()), mae=round(e[msk].abs().mean(), 1), median_ae=round(e[msk].abs().median(), 1),
                             bias=round(e[msk].mean(), 1), within_10=round(((e[msk].abs() <= 10).mean()) * 100),
                             sign_hit=None if k.startswith('Model DA') else round(hit[msk[s != 0]].mean() * 100)))
    # direction value: trade the sign of (read - DA fc) at 1 MW, only when |read - DA fc| >= 5
    val = []
    for k in ('DA fc + fundamentals read (all history)', 'DA fc + fundamentals read (last 60 days)', 'DA fc + 14-day hourly median RT-DA', 'Current RT forecast (p_rt)'):
        r = cand[k] - t.p_da; m = r.abs() >= 5; pl = np.sign(r[m]) * (t.rt - t.da)[m]
        val.append(dict(candidate=k, hours=int(m.sum()), usd_mwh=round(pl.mean(), 2), right=round((pl > 0).mean() * 100),
                        oct_usd=round(pl[t.date[m] >= '2026-10-01'].mean(), 2)))
    return pd.DataFrame(rows), pd.DataFrame(val), t

def part3():
    p = C.prices('EAST'); p = p[p.rt.notna() & p.da.notna()].copy(); p['x'] = p.rt - p.da
    W = p.pivot_table(index='date', columns='he', values='x').dropna(); days = list(W.index)
    rows = []
    for i in range(60, len(days) - 14, 3):
        fut = W.iloc[i:i + 14].corr()
        for name, w in (('all history', i), ('last 60 d', 60), ('last 30 d', 30), ('last 14 d', 14)):
            past = W.iloc[i - w:i].corr()
            rows.append(dict(window=name, err=float((past - fut).abs().values[np.triu_indices(24, 1)].mean())))
    R = pd.DataFrame(rows).groupby('window').err.mean().round(3).sort_values()
    return R, W

if __name__ == '__main__':
    r1, wk, _ = part1(); print('=== PART 1: gas need (cushion) miss = actual gas - need, MW ===\n', r1.to_string(index=False)); print(wk.tail(10).to_string())
    r2, v2, _ = part2(); print('\n=== PART 2: RT read candidates (East) ===\n', r2.to_string(index=False)); print('\nTrade the sign, |read - DA fc| >= $5:\n', v2.to_string(index=False))
    r3, W = part3(); print('\n=== PART 3: correlation window -> error predicting the next 14 days (lower = better) ===\n', r3.to_string())
    for name, w in (('all', len(W)), ('30', 30), ('14', 14)):
        c = W.tail(w).corr(); print(f'\n{name} days: adjacent-hour corr', [round(c.loc[h, h + 1], 2) for h in range(1, 24)])
