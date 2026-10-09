"""guard_validate.py -- Oct 9 2026: is the tight-evening guard (Tesla>IESO -> no edge; + wind fc >= 1,500 -> flip to buy) real or cherry-picked?
Checks on tight HE16-21 hours, Sep 2025 -> Oct 6 2026, real sell ladders vs 85 MW long at DA fc + $30:
 grid of thresholds (plateau?), walk-forward thresholds (chosen each day on trailing 120 d), placebo (random tight evening hours,
 same count per month), concentration (gain without best 1/3 days), halves, both zones."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 250); RNG = np.random.default_rng(3)
def gain(t, k):     # flip: replace sell P&L with long P&L in flagged hours
    return (t.pl_buy - t.pl_sell)[k]
for z in ('EAST', 'OTTAWA'):
    t = pd.read_csv(C.DATA / f'tight_eval_{z}.csv'); t = t[t.date >= '2025-09-12'].reset_index(drop=True)
    print(f'\n========== {z}: {len(t)} tight evening hours, {t.date.nunique()} days ==========')
    rows = []
    for tg in (-100, 0, 100, 200):
        for w in (0, 1000, 1250, 1500, 1750, 2000):
            k = (t.gapT > tg) & (t.wind_fc >= w); g = gain(t, k); d = g.groupby(t.date[k]).sum().sort_values(ascending=False)
            rows.append(dict(tesla_gt=tg, wind_ge=w, hours=int(k.sum()), days=t.date[k].nunique(), flip_gain=round(g.sum()), H1=round(g[t.date[k] < '2026-02-15'].sum()),
                             H2=round(g[t.date[k] >= '2026-02-15'].sum()), ex_best1=round(d.iloc[1:].sum()) if len(d) else 0, ex_best3=round(d.iloc[3:].sum()) if len(d) else 0))
    G = pd.DataFrame(rows); print('FLIP gain grid (long instead of the sell):'); print(G.pivot(index='tesla_gt', columns='wind_ge', values='flip_gain').to_string())
    print('… without the best 3 days:'); print(G.pivot(index='tesla_gt', columns='wind_ge', values='ex_best3').to_string())
    print('… H1 / H2 for the wired rule (Tesla>0, wind>=1500):', G[(G.tesla_gt == 0) & (G.wind_ge == 1500)][['hours', 'days', 'flip_gain', 'H1', 'H2', 'ex_best1', 'ex_best3']].to_dict('records'))
    # placebo: flip the same number of random tight evening hours per month
    k = (t.gapT > 0) & (t.wind_fc >= 1500); obs = gain(t, k).sum(); cnt = t[k].groupby(t.date[k].str[:7]).size(); allg = (t.pl_buy - t.pl_sell)
    pb = []
    for _ in range(3000):
        s = 0.0
        for mo, c in cnt.items():
            pool = allg[t.date.str[:7] == mo].values; s += pool[RNG.choice(len(pool), min(c, len(pool)), replace=False)].sum()
        pb.append(s)
    pb = np.array(pb); print(f'placebo: random flips median {np.median(pb):+,.0f}, 95th {np.percentile(pb,95):+,.0f}; rule {obs:+,.0f} -> beats {(pb<obs).mean()*100:.1f}% of random')
    # no-edge part (Tesla>IESO, not windy): skip the sell
    n = (t.gapT > 0) & (t.wind_fc < 1500); print(f'NO-EDGE part (skip sell): {int(n.sum())} h, sells made {t.pl_sell[n].sum():+,.0f} (H1 {t.pl_sell[n & (t.date < "2026-02-15")].sum():+,.0f} / H2 {t.pl_sell[n & (t.date >= "2026-02-15")].sum():+,.0f}) -> skipping changes P&L by {-t.pl_sell[n].sum():+,.0f}')
    # walk-forward: each day pick (tesla, wind) thresholds that maximised flip gain on trailing 120 days (or no rule)
    combos = [(a, b) for a in (-100, 0, 100, 200) for b in (0, 1000, 1500, 2000)]; wf = 0.0; picks = []
    for D in sorted(t.date.unique()):
        lo = (pd.Timestamp(D) - pd.Timedelta(days=120)).date().isoformat(); c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
        tr = t[(t.date > lo) & (t.date <= c2)]
        if tr.date.nunique() < 20: picks.append(None); continue
        sc = {c: gain(tr, (tr.gapT > c[0]) & (tr.wind_fc >= c[1])).sum() for c in combos}; best = max(sc, key=sc.get)
        if sc[best] <= 0: picks.append(None); continue
        x = t[t.date == D]; wf += gain(x, (x.gapT > best[0]) & (x.wind_fc >= best[1])).sum(); picks.append(best)
    print(f'WALK-FORWARD thresholds: flip gain {wf:+,.0f} | most-picked {pd.Series([str(p) for p in picks]).value_counts().head(4).to_dict()}')
