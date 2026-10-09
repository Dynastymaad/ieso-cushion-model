"""tesla_rules_bt.py -- Oct 7 2026: hard backtest of the two Tesla-vs-usual (tvu) ideas before anything is wired.
 A  skip TIGHT sells when tvu >= T                     (ladder: live score-5 tiers with the CAHR A/B repricing)
 B  'spike buy' HE16-21, not a sell, tvu >= T, head < Hk (bid = DA fc + $30, clears if DA <= bid)
Checks: threshold grid (plateau or lucky point?), walk-forward threshold (learned on trailing 120 d through D-2),
placebo (random hours of the same count, 2,000 draws), day bootstrap, halves/months, and 'is tvu adding anything beyond
the same rule without tvu?'. P&L per base ladder (sells 20/30/40 MW; buys per 1 MW). Period: Tesla-at-bid coverage, Sep 12 2025 ->."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, da_virtual_bt as DV
pd.set_option('display.width', 260); RNG = np.random.default_rng(11)
H1E, L90 = '2026-02-15', '2026-07-08'

def sell_pl(r):
    _, s = DV.ladder(5, r.p_da, r.p_rt)
    g = 'A' if r.cahr >= 12 else 'B'
    s = [(q, None if p is None else (round(min(p, 0.9 * r.p_rt)) if g == 'A' else p + 10)) for q, p in s]
    q = sum(a for a, p in s if p is not None and r.da >= p); return q * (r.da - r.rt)

def stats(pl, dates, name, **kw):
    s = pd.Series(pl.values, index=dates.values); dd = s.groupby(level=0).sum()
    f = lambda m: round(s[m].sum())
    return dict(rule=name, **kw, hours=int((s != 0).sum()), total=round(s.sum()), H1=f(s.index < H1E), H2=f(s.index >= H1E), last90=f(s.index >= L90),
                worst_day=round(dd.min()), days_lt_m5k=int((dd < -5000).sum()), sharpe=round(dd.mean() / dd.std() * np.sqrt(252), 2) if dd.std() > 0 else np.nan)

if __name__ == '__main__':
    for z in ('EAST', 'OTTAWA'):
        m = pd.read_csv(C.DATA / f'spike_frame_{z}.csv'); m = m[m.tvu.notna() & m.p_rt.notna()].reset_index(drop=True)
        print(f'\n#################### {z}: {m.date.min()} .. {m.date.max()} ####################')
        # ---------------- A: tight-sell filter ----------------
        t = m[m.why == 'tight'].copy(); t['pl'] = [sell_pl(r) for r in t.itertuples()]
        R = [stats(t.pl, t.date, 'A baseline: all tight sells')]
        for T in (0, 100, 200, 300, 400, 500, 700):
            keep = t.tvu < T; R.append(stats(t.pl.where(keep, 0), t.date, f'A skip tight if tvu>={T}', skipped=int((~keep).sum()), skipped_pl=round(t.pl[~keep].sum())))
        # walk-forward T: pick on trailing 120 d (through D-2) the T that maximises kept P&L (no skip allowed = T inf)
        grid = [0, 100, 200, 300, 400, 500, 700, 1e9]; wf = pd.Series(0.0, index=t.index); picks = {}
        for D in sorted(t.date.unique()):
            lo = (pd.Timestamp(D) - pd.Timedelta(days=120)).date().isoformat(); c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
            tr = t[(t.date > lo) & (t.date <= c2)]
            T = 1e9 if tr.date.nunique() < 30 else max(grid, key=lambda g: tr.pl[tr.tvu < g].sum()); picks[D] = T
            k = (t.date == D) & (t.tvu < T); wf[k] = t.pl[k]
        R.append(stats(wf, t.date, 'A WALK-FORWARD threshold', skipped=int(((t.date.map(picks)) <= t.tvu).sum())))
        # placebo: skip the same number of random tight hours as T=200
        n = int((t.tvu >= 200).sum()); base = t.pl.sum(); obs = t.pl[t.tvu < 200].sum() - base
        pb = np.array([-t.pl.values[RNG.choice(len(t), n, replace=False)].sum() for _ in range(2000)])
        print(f'A placebo: skipping {n} random tight hours changes P&L by median {np.median(pb):+,.0f} (90% {np.percentile(pb,5):+,.0f}..{np.percentile(pb,95):+,.0f}); tvu>=200 skip: {obs:+,.0f} -> percentile {(pb < obs).mean()*100:.0f}')
        big = t.pl < -2000; print(f'A big-loss hours (< -$2k on the ladder): {big.sum()}, of which tvu>=200: {(big & (t.tvu >= 200)).sum()} ({(big & (t.tvu >= 200)).sum()/max(big.sum(),1)*100:.0f}%); tvu>=200 share of all tight hours {n/len(t)*100:.0f}%')
        print('A walk-forward picks:', pd.Series(picks).value_counts().to_dict())
        print(pd.DataFrame(R).to_string(index=False))
        # ---------------- B: spike buy ----------------
        nb = m[m.why.isna() & m.he.between(16, 21)].copy()
        nb['clr'] = nb.da <= nb.p_da + 30; nb['pl'] = np.where(nb.clr, nb.rt - nb.da, 0.0)
        R = []
        for Hk in (8000, 9000, 10000, 1e9):
            for T in (-1e9, 0, 200, 300, 400, 500):
                k = (nb['head'] < Hk) & (nb.tvu >= T)
                R.append(stats(nb.pl.where(k, 0), nb.date, f'B head<{int(Hk/1000) if Hk<1e8 else "any"}k tvu>={"any" if T<-1e8 else int(T)}', per_mwh=round(nb.pl[k & nb.clr].mean(), 2)))
        G = pd.DataFrame(R); print('B grid (per 1 MW):'); print(G.to_string(index=False))
        # chosen rule vs placebo (random evening non-sell hours, same count, same months)
        k = (nb['head'] < 9000) & (nb.tvu >= 300); obs = nb.pl[k].sum()
        pool = nb.groupby(nb.date.str[:7]); cnt = nb[k].groupby(nb[k].date.str[:7]).size()
        pb = []
        for _ in range(2000):
            s = 0.0
            for mo, c in cnt.items():
                g = pool.get_group(mo).pl.values; s += g[RNG.choice(len(g), c, replace=False)].sum()
            pb.append(s)
        pb = np.array(pb); print(f'B placebo (same count per month, random evening non-sell hours): median {np.median(pb):+,.0f}, 95th {np.percentile(pb,95):+,.0f}; rule {obs:+,.0f} -> percentile {(pb < obs).mean()*100:.0f}')
        k2 = (nb['head'] < 9000)
        pb2 = []
        for _ in range(2000):
            s = 0.0
            for mo, c in cnt.items():
                g = nb[k2 & (nb.date.str[:7] == mo)].pl.values
                if len(g) >= c: s += g[RNG.choice(len(g), c, replace=False)].sum()
            pb2.append(s)
        pb2 = np.array(pb2); print(f'B placebo inside head<9k (does tvu add anything beyond headroom?): median {np.median(pb2):+,.0f}, 95th {np.percentile(pb2,95):+,.0f}; rule percentile {(pb2 < obs).mean()*100:.0f}')
        dd = nb.pl[k].groupby(nb.date[k]).sum(); bs = [dd.values[RNG.integers(0, len(dd), len(dd))].sum() for _ in range(3000)]
        print(f'B rule day-bootstrap total 90% CI {np.percentile(bs,5):+,.0f}..{np.percentile(bs,95):+,.0f}; without best 2 days {dd.sum()-dd.nlargest(2).sum():+,.0f}; without best 5 {dd.sum()-dd.nlargest(5).sum():+,.0f}')
        # walk-forward (T, Hk) chosen on trailing 120 d
        combos = [(T, H) for T in (0, 200, 300, 400, 500) for H in (8000, 9000, 10000, 1e9)]; wf = pd.Series(0.0, index=nb.index); pk = {}
        for D in sorted(nb.date.unique()):
            lo = (pd.Timestamp(D) - pd.Timedelta(days=120)).date().isoformat(); c2 = (pd.Timestamp(D) - pd.Timedelta(days=2)).date().isoformat()
            tr = nb[(nb.date > lo) & (nb.date <= c2)]
            if tr.date.nunique() < 30: continue
            sc = {c: tr.pl[(tr.tvu >= c[0]) & (tr['head'] < c[1])].sum() for c in combos}; best = max(sc, key=sc.get)
            if sc[best] <= 0: continue
            pk[D] = best; kk = (nb.date == D) & (nb.tvu >= best[0]) & (nb['head'] < best[1]); wf[kk] = nb.pl[kk]
        print('B WALK-FORWARD:', stats(wf, nb.date, 'B walk-forward'), '| picks:', pd.Series([str(v) for v in pk.values()]).value_counts().head(5).to_dict())
        print('B by month (rule, per MW):', nb.pl[k].groupby(nb.date[k].str[:7]).sum().round(0).to_dict())
