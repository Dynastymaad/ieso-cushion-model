"""market_read.py -- Oct 31 2026. 'Market read' tab (DISPLAY ONLY, nothing feeds the ladders).
Reads each hour the way the market does, then asks what the market is missing:
  PUBLIC spare  = gas available - gas needed on IESO's own load + wind (what every trader sees at the bid)
  PRIVATE spare = same, on our best load (Meteologica, else Tesla/Dynasty avg) and best wind (Meteologica, else median of 9 weather models)
  RESCUE        = private - public (+ looser than the market sees, - tighter: 'danger')
  UNCERTAINTY   = spread of the 9 wind models (how wrong the public picture could be)
  CROWD         = all traders' cleared virtual net for the same hour yesterday (+ net short, - net long)
Cells (research/fear_rescue.py, Jun 2025 -> Oct 2026, East):
  FEAR -> RESCUE  public spare < 1,500, rescue >= +300, wind models agree: shorts +$21.5/MWh, 76% win, positive in every period
  CALM -> DANGER  public spare >= 1,500, rescue <= -300: longs +$4 (E) / +$6 (O), win 41% -- a tail bet
  FEAR + DANGER   public spare < 1,500 and rescue <= -300 or models disagree: shorts ~ break-even, spikes 25-31% -> stand aside,
                  except: crowd NOT long yesterday -> shorts lost ~$20 (the danger was not priced)
History stats are recomputed every morning; 'what is mattering lately' compares the last 60 days with all history."""
import sys, json; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent / 'research'))
import numpy as np, pandas as pd, common as C, supply_fc as S
J = lambda v, k=0: None if v is None or pd.isna(v) else (round(float(v), k) if k else int(round(float(v))))
NWP = ['wf_frontier', 'wf_gem_cmc', 'wf_gfs', 'wf_nam', 'wf_nam_nest', 'wf_stormvista_ecmwf', 'wf_stormvista_ecmwf_eps', 'wf_stormvista_gfs', 'wf_stormvista_gfs_ens']
T_SP, T_R, T_W = 1500, 300, 1200

def cell(pub, resc, ws):
    if pub is None or resc is None: return 'n/a'
    if pub < T_SP:
        if resc >= T_R and (ws is None or ws <= T_W): return 'FEAR -> RESCUE'
        if resc <= -T_R or (ws is not None and ws > T_W): return 'FEAR + DANGER'
        return 'FEAR, views agree'
    if resc <= -T_R: return 'CALM -> DANGER'
    if resc >= T_R: return 'CALM -> RESCUE'
    return 'CALM, views agree'
ACTION = {'FEAR -> RESCUE': 'short', 'FEAR + DANGER': 'depends on how rich DA is', 'FEAR, views agree': 'small short', 'CALM -> DANGER': 'long if triggered',
          'CALM -> RESCUE': 'no edge', 'CALM, views agree': 'no edge', 'n/a': ''}
SINCE = '2026-01-01'      # Nov 1 2026: stats and rules use 2026 only (the market changed); rules learned Jan-Sep 2026, Oct 2026 read blind
def action(c, vs, sp, w3, lgap, he):
    """scenario_2026.py: inside each read, what decided it in Jan-Sep 2026 (same sign Jan-Jun and Jul-Sep)."""
    vs = vs or 0
    if c == 'FEAR -> RESCUE': return 'SHORT, full size' if vs >= 18 else 'SHORT'
    if c == 'FEAR + DANGER':
        if vs >= 24 and sp is not None and sp <= 971: return 'SHORT (danger already priced: DA well above usual)'
        if vs < 24: return 'stand aside / small long (danger not priced: DA near usual)'
        return 'stand aside'
    if c == 'FEAR, views agree': return 'small short'
    if c == 'CALM -> DANGER':
        k = sum([vs >= 4, (w3 or 0) <= -2, (lgap or 0) >= 370, he <= 9])
        return 'LONG' if k >= 2 else 'small long' if k == 1 else 'skip (no trigger)'
    return '-'

def crowd(zone):
    m = pd.read_csv(C.CACHE / 'market_virtuals.csv'); m = m[m.zone == f'{zone}:HUB'].rename(columns={'deliverydate': 'date', 'hour': 'he'})
    m['net'] = m.supplyschedule + m.loadschedule; return m[['date', 'he', 'net']]

def history(zone):
    import fear_rescue as FR
    e = FR.frame(zone); cr = crowd(zone)
    e = e.sort_values(['date', 'he']); e['vs'] = e.p_da - e.groupby('he').p_da.transform(lambda s: s.shift(1).rolling(14, min_periods=5).median()); cr['date'] = (pd.to_datetime(cr.date) + pd.Timedelta(days=1)).dt.strftime('%Y-%m-%d')
    e = e.merge(cr.rename(columns={'net': 'crowd1'}), on=['date', 'he'], how='left')
    e['cell'] = [cell(a, b, c) for a, b, c in zip(e.pub_sp, e.rescue, e.w_spread)]
    return e

def stats(g):
    x = g.rt - g.da
    return dict(hours=int(len(g)), sell=J(-x.mean(), 1) if len(g) else None, rt_gt_da=J((x > 0).mean() * 100) if len(g) else None,
                spike=J((x >= 25).mean() * 100) if len(g) else None, collapse=J((x <= -20).mean() * 100) if len(g) else None)

def build(D, bundle):
    out = {'date': D, 'hubs': {}}
    W = S.wind_at_bid(); w = W[W.date == D].set_index('he'); nw = [c for c in NWP if c in w]
    prac = {r['he']: r for r in bundle['fund']['prac']['rows']}; fund = {r['he']: r for r in bundle['fund']['rows']}
    for z in ('EAST', 'OTTAWA'):
        H = history(z); c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat(); H = H[(H.date <= c2) & (H.date >= SINCE)]
        cr = crowd(z); cy = cr[cr.date == (pd.Timestamp(D) - pd.Timedelta(days=1)).date().isoformat()].set_index('he').net
        rows = []
        for he in range(1, 25):
            p = prac.get(he, {}); f = fund.get(he, {})
            pub = None if p.get('sp') is None else p['sp']
            dl = None if p.get('met') is None or p.get('dem') is None else p['met'] - p['dem']
            if dl is None and p.get('tes') is not None and p.get('dem') is not None: dl = p['tes'] - p['dem']
            wpriv = p.get('wm') if p.get('wm') is not None else (float(w.loc[he, nw].median()) if he in w.index and nw else None)
            dw = None if wpriv is None or p.get('w') is None else wpriv - p['w']
            resc = None if dl is None and dw is None else -(dl or 0) + (dw or 0)
            ws = float(w.loc[he, nw].max() - w.loc[he, nw].min()) if he in w.index and nw and w.loc[he, nw].notna().sum() >= 3 else None
            valve = max(-(f.get('net_exp') or 0), 0) + max((f.get('hyd_av') or 0) - (f.get('hydro_exp') or 0), 0)   # net exports (fund stores them negative) + unscheduled hydro
            c = cell(pub, resc, ws)
            w3 = None if p.get('w3') is None else p['w3']
            act = action(c, p.get('vs'), pub, w3, dl, he)
            rows.append(dict(he=he, vs=J(p.get('vs'), 1), w3=J(w3), act=act, pub_sp=J(pub), priv_sp=None if pub is None or resc is None else J(pub + resc), rescue=J(resc), d_load=J(dl), d_wind=J(dw),
                             w_spread=J(ws), valve=J(valve), crowd=J(cy.get(he)), cell=c, action=ACTION.get(c, '')))
        cells = {}
        for k in ['FEAR -> RESCUE', 'FEAR + DANGER', 'FEAR, views agree', 'CALM -> DANGER', 'CALM -> RESCUE', 'CALM, views agree']:
            g = H[H.cell == k]; r90 = g[g.date > (pd.Timestamp(D) - pd.Timedelta(days=92)).date().isoformat()]
            cells[k] = dict(all=stats(g), last90=stats(r90), action=ACTION[k])
        # game-theory split: in FEAR + DANGER hours, was the crowd already long (danger priced) or not?
        fd = H[H.cell == 'FEAR + DANGER']
        crowd_split = {'DA fc well above usual (+24 or more)': stats(fd[fd.vs >= 24]), 'DA fc near usual (under +24)': stats(fd[fd.vs < 24]), 'crowd long yesterday': stats(fd[fd.crowd1 <= -40]), 'crowd not long': stats(fd[~(fd.crowd1 <= -40)])}
        fr = H[H.cell == 'FEAR -> RESCUE']
        crowd_split_fr = {'crowd long yesterday': stats(fr[fr.crowd1 <= -40]), 'crowd not long': stats(fr[~(fr.crowd1 <= -40)])}
        # what is mattering lately: rank correlation of each factor with RT - DA, all history vs the last 60 days
        H['x'] = H.rt - H.da; rec = H[H.date > (pd.Timestamp(D) - pd.Timedelta(days=62)).date().isoformat()]
        lab = {'rescue': 'Private vs public spare (rescue)', 'd_load': 'Best load minus IESO load', 'd_wind': 'Best wind minus IESO wind', 'w_spread': 'Wind model disagreement',
               'pub_sp': 'Public spare (IESO view)', 'valve': 'Valves: exports + spare hydro', 'crowd1': "Crowd's net position yesterday", 'p_da': 'DA forecast level'}
        mat = []
        for k, nm in lab.items():
            a = H[[k, 'x']].dropna(); b = rec[[k, 'x']].dropna()
            ca = a[k].rank().corr(a.x.rank()) if len(a) > 200 else np.nan; cb = b[k].rank().corr(b.x.rank()) if len(b) > 100 else np.nan
            mat.append(dict(factor=nm, all=J(ca * 100), last60=J(cb * 100), hours60=int(len(b))))
        mat.sort(key=lambda r: -abs(r['last60'] or 0))
        out['hubs'][z] = dict(rows=rows, cells=cells, crowd_fd=crowd_split, crowd_fr=crowd_split_fr, matters=mat, hist_from=H.date.min(), hist_to=H.date.max())
    return out

if __name__ == '__main__':
    b = json.loads((C.ROOT / 'site' / 'data' / 'bundle.json').read_text()); r = build(b['target'], b)
    E = r['hubs']['EAST']
    for x in E['rows']: print(x)
    print(json.dumps(E['cells'], indent=0)[:1500]); print(E['crowd_fd']); print(E['matters'])
