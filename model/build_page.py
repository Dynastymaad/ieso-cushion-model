"""build_page.py -- inject the forecast bundle + backtest numbers into the page.
Writes site/index.html (full document, for GitHub Pages) and site/page_fragment.html
(same page without the <html>/<head>/<body> wrapper, for the Claude artifact)."""
import sys, json; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C

ZONES = ['EAST', 'OTTAWA']

def acc():
    out = {}
    rows = []
    for z in ZONES:
        h = pd.read_csv(C.DATA / f'bt_hourly_{z}.csv'); h['p_da'] = 0.5 * h.p_h + 0.5 * h.p_s.fillna(h.p_h)
        v = h.dropna(subset=['da', 'da_y']); v = v[v.date >= '2026-08-02']
        for name, col in (('Yesterday same hour', 'da_y'), ('Model v1', 'p_da')):
            e = v[col] - v.da
            rows.append(dict(hub=z, model=name, hours=len(v), mae=round(e.abs().mean(), 2), eve=round(e[v.he.between(17, 21)].abs().mean(), 2),
                             mape=round((e.abs() / v.da).mean() * 100, 1)))
        q = pd.read_csv(C.DATA / f'bt_quantiles_{z}.csv'); r = pd.read_csv(C.DATA / f'bt_rt_quantiles_{z}.csv')
        out[f'cov_{z}'] = dict(da=[round((q.da < q[f'q{k}']).mean() * 100, 1) for k in (10, 25, 50, 75, 90)],
                               rt=[round((r.rt < r[f'r{k}']).mean() * 100, 1) for k in (10, 25, 50, 75, 90)],
                               rt_mae=round((r.r50 - r.rt).abs().mean(), 2), rt_naive=round((r.p_da - r.rt).abs().mean(), 2),
                               da_days=int(q.date.nunique()), rt_days=int(r.date.nunique()))
    out['next_day'] = rows
    out['blocks'] = pd.read_csv(C.DATA / 'acc_blocks.csv').to_dict('records')
    out['horizon'] = pd.read_csv(C.DATA / 'acc_horizon_hourly.csv').to_dict('records')
    out['trading'] = pd.read_csv(C.DATA / 'bt_trading_rules.csv').round(2).to_dict('records')
    # ---- edge study (notes/Edge_Study.md)
    J = lambda df: json.loads(df.to_json(orient='records'))
    out['drivers'] = J(pd.read_csv(C.DATA / 'es_drivers.csv'))
    out['gasband'] = J(pd.read_csv(C.DATA / 'es_gasband.csv'))
    t = pd.read_csv(C.DATA / 'dynasty_trades_scored.csv')
    for z in ZONES:
        out[f'v2_{z}'] = J(pd.read_csv(C.DATA / f'es_rules_v2_{z}.csv'))
        w = pd.read_csv(C.DATA / f'bt_signals_v2_{z}.csv')
        m = t[t.zone == z].merge(w[['date', 'he', 'signal']], on=['date', 'he'])
        m['state'] = np.where(m.signal == 'NONE', 'no signal', 'v2 sell hour')
        dk = m.groupby(['buysell', 'state']).agg(mwh=('mw', 'sum'), pnl=('pnl', 'sum'), hours=('he', 'count')).reset_index()
        dk['usd_mwh'] = (dk.pnl / dk.mwh).round(2); dk['days'] = m.date.nunique(); dk['from'] = m.date.min(); dk['to'] = m.date.max()
        out[f'desk_{z}'] = J(dk.round(0).assign(usd_mwh=dk.usd_mwh))
        e = pd.read_csv(C.DATA / f'es_da_errors_hourly_{z}.csv')
        e['band'] = pd.cut(e.da, [0, 30, 40, 50, 60, 80, 120, 999], labels=['<30', '30-40', '40-50', '50-60', '60-80', '80-120', '>120'])
        f = lambda g: pd.Series(dict(n=len(g), mean=g.err.mean(), median=g.err.median(), hi=(g.err > 0).mean() * 100, mae=g.err.abs().mean()))
        out[f'bias_level_{z}'] = J(e.groupby('band').apply(f).round(2).reset_index())
        out[f'bias_dow_{z}'] = J(e.groupby('dow').apply(f).round(2).reset_index())
        out[f'bias_he_{z}'] = J(e.groupby('he').apply(f).round(2).reset_index())
        hist = pd.cut(e.err, [-999, -30, -15, -10, -5, -2, 2, 5, 10, 15, 30, 999]).value_counts().sort_index()
        out[f'err_hist_{z}'] = [dict(bin=str(k), n=int(v)) for k, v in hist.items()]
        out[f'err_q_{z}'] = {str(k): round(v, 2) for k, v in e.err.quantile([.05, .1, .25, .5, .75, .9, .95]).items()}
        dd = pd.read_csv(C.DATA / f'es_da_errors_daily_{z}.csv')
        w['sig'] = np.where(w.signal == 'NONE', 0, 1); w['pl'] = np.where(w.sig == 1, w.sp, np.nan)
        wd = w.groupby('date').agg(spread=('sp', 'mean'), sell_all=('sp', 'sum'), core=('signal', lambda s: int((s == 'SELL').sum())),
                                   light=('signal', lambda s: int((s == 'SELL-L').sum())), v2=('pl', 'sum')).reset_index()
        rec = dd[['date', 'dow', 'da', 'fc', 'err', 'err_on', 'worst']].merge(wd, on='date', how='outer').sort_values('date')
        out[f'daily_{z}'] = J(rec.round(2))
    return out

def main():
    b = json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text())
    b['accuracy'] = acc()
    tpl = (C.ROOT / 'model' / 'page_template.html').read_text()
    frag = tpl.replace('/*__BUNDLE__*/null', json.dumps(b, default=float).replace('NaN', 'null'))
    (C.ROOT / 'site' / 'page_fragment.html').write_text(frag)
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + frag + '\n</body>\n</html>\n')
    (C.ROOT / 'site' / 'index.html').write_text(full)
    print('page ->', C.ROOT / 'site' / 'index.html', f'{len(full)/1024:.0f} KB')

if __name__ == '__main__':
    main()
