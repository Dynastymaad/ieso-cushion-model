"""qc_adq2x.py -- IESO Adequacy2 intertie bids and schedules for Quebec (canpower archive, pulled with --only adq2x).
Finding 1: the pre-DA vintage (the one we bid on) has NO intertie bids/offers/schedules -- IESO fills them only after the DA run.
So the bid-safe version is the final DA schedule of D-2 (fully published before D-1's bid).
Tests (17 months, East and Ottawa):
  explanatory, same day: Quebec export bids in excess of what was scheduled (unfilled demand from Quebec = limit binding)
                         vs the zone DA basis and the PQ.AT DA congestion flag (IESO intertie LMP, May-Sep 2026)
  bid-time: the same excess on D-2 at the same HE -> v2 SELL DA-RT (pre-declared split: above / below its trailing 30-day median)"""
import sys, json, warnings; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent)); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, common as C, fail_fix as FF, quebec as Q

def load():
    x = pd.read_csv(C.CACHE / 'ieso_adq2x_final.csv'); x['v'] = pd.to_numeric(x.value, errors='coerce')
    x = x[x.subtype.isin(['Quebec Bid', 'Quebec Schedule', 'Quebec Offer']) | (x.resourcetype == 'Total Exports')]
    x['k'] = np.where(x.resourcetype == 'Total Exports', 'tot_' + x.subtype.str.lower(), x.resourcetype.str.split().str[1].str.lower() + '_' + x.subtype.str.replace('Quebec ', '').str.lower())
    w = x.pivot_table(index=['date', 'hour'], columns='k', values='v', aggfunc='last').reset_index().rename(columns={'hour': 'he'})
    w['qx_bid'] = w.export_bid; w['qx_sched'] = -w.export_schedule; w['qx_excess'] = w.qx_bid - w.qx_sched      # MW of Quebec export bids not scheduled
    w = w.sort_values(['date', 'he'])
    for c in ('qx_excess', 'qx_sched', 'qx_bid'):
        p = w.pivot_table(index='date', columns='he', values=c)
        w = w.merge(p.shift(2).stack().rename(c + '_d2').reset_index(), on=['date', 'he'], how='left')
        med = p.shift(2).rolling(30, min_periods=15).median().stack().rename(c + '_med30').reset_index()
        w = w.merge(med, on=['date', 'he'], how='left')
    return w

def run():
    w = load(); out = {}
    f = Q.frame(history=True).merge(w, on=['date', 'he'], how='left')
    print('Quebec DA schedule (final) vs actual PQ exports: corr', round(f[['qx_sched', 'pq_exp']].corr().iloc[0, 1], 2), ' mean', round(f.qx_sched.mean()), 'vs', round(f.pq_exp.mean()))
    print('export bids: mean', round(f.qx_bid.mean()), ' excess over schedule mean', round(f.qx_excess.mean()), ' share of hours excess > 200 MW', round((f.qx_excess > 200).mean() * 100, 1))
    L = pd.read_csv(C.DATA / 'qc_intertie_lmp.csv')[['date', 'he', 'bind']]; g = f.merge(L, on=['date', 'he'])
    g['xb'] = pd.cut(g.qx_excess, [-1e9, 50, 300, 800, 1e9], labels=['<50', '50-300', '300-800', '>800'])
    t = g.groupby('xb').agg(bind=('bind', 'mean'), e_basis=('east_da_basis', 'mean'), o_basis=('ottawa_da_basis', 'mean'), h=('bind', 'size')).round(2)
    print('\nsame day, May-Sep 2026: PQ.AT congestion and zone basis by unscheduled Quebec export bids (MW):'); print(t.to_string()); out['same_day'] = t.reset_index().astype({'xb': str}).to_dict('records')
    b = np.polyfit(f.dropna(subset=['qx_excess', 'east_da_basis']).qx_excess / 1000, f.dropna(subset=['qx_excess', 'east_da_basis']).east_da_basis, 1)
    print('East DA basis per GW unscheduled bids (same day):', round(b[0], 2))
    # bid-time, 17 months
    for z in ('EAST', 'OTTAWA'):
        d = pd.read_csv(C.DATA / f'dv_frame_{z}.csv')[['date', 'he', 'v2', 'sp']].merge(w[['date', 'he', 'qx_excess_d2', 'qx_excess_med30']], on=['date', 'he']).dropna()
        d = d[d.date >= '2025-07-01']; d['hi'] = d.qx_excess_d2 > d.qx_excess_med30
        r = {}
        for n, s in (('all', d), ('v2', d[d.v2 == 1])):
            for hn, hf in (('all', lambda x: x == x), ('Jul-Jan', lambda x: x < '2026-02-01'), ('Feb-Sep', lambda x: x >= '2026-02-01')):
                u = s[hf(s.date)]; a, c = u[u.hi], u[~u.hi]
                la, ha = FF.boot(a.sp.values, a.date.values); lc, hc = FF.boot(c.sp.values, c.date.values)
                r[f'{n}|{hn}'] = dict(hi=[round(a.sp.mean(), 2), round(la, 2), round(ha, 2), len(a)], lo=[round(c.sp.mean(), 2), round(lc, 2), round(hc, 2), len(c)])
                print(f'{z} {n:3s} {hn:8s}  D-2 excess above median: DA-RT {a.sp.mean():+6.2f} ({la:+.2f}..{ha:+.2f}) h {len(a):5d} | below: {c.sp.mean():+6.2f} ({lc:+.2f}..{hc:+.2f}) h {len(c):5d}')
        out[z] = r
    (C.DATA / 'qc_adq2x.json').write_text(json.dumps(out, default=float, indent=1))

if __name__ == '__main__': run()
