"""segment_lookback.py -- Oct 9 2026: an UNBIASED, segment-by-segment rule and how far back it should learn.
Segments: overnight HE1-6 | morning ramp HE7-10 | midday HE11-15 | evening ramp HE16-21 | end of day HE22-24.
For each day D and segment: take the last N days of that segment (through D-2), split by headroom into 5 buckets (edges from those
N days), and for D's hour trade the bucket's direction if |mean DA-RT| >= $3 with >= 20 hours (SELL if DA beat RT, BUY if RT beat DA).
No side is preferred. Compared with the live model (v2 sells + buy band) segment by segment. Price-taker $ per MW, Oct 2025 -> Oct 6 2026."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C
pd.set_option('display.width', 260)
SEG = {'overnight 1-6': range(1, 7), 'morning 7-10': range(7, 11), 'midday 11-15': range(11, 16), 'evening 16-21': range(16, 22), 'late 22-24': range(22, 25)}
segof = {h: s for s, r in SEG.items() for h in r}

def run(d, N):
    d = d.copy(); d['side'] = 0
    days = sorted(d.date.unique()); dt = pd.to_datetime(d.date)
    for D in days:
        if D < '2025-10-01': continue
        Dt = pd.Timestamp(D); tr = d[(dt <= Dt - pd.Timedelta(days=2)) & (dt > Dt - pd.Timedelta(days=N + 2)) & d.sp.notna()]
        for s in SEG:
            h = tr[tr.seg == s]
            if len(h) < 60: continue
            edges = np.unique(np.quantile(h['head'], [0, .2, .4, .6, .8, 1]))
            if len(edges) < 3: continue
            b = np.clip(np.searchsorted(edges, h['head'], side='right') - 1, 0, len(edges) - 2)
            g = h.groupby(b).sp.agg(['mean', 'size'])
            idx = d.index[(d.date == D) & (d.seg == s)]
            for i in idx:
                k = int(np.clip(np.searchsorted(edges, d.at[i, 'head'], side='right') - 1, 0, len(edges) - 2))
                if k in g.index and g.at[k, 'size'] >= 20 and abs(g.at[k, 'mean']) >= 3: d.at[i, 'side'] = 1 if g.at[k, 'mean'] > 0 else -1
    return d.side

def score(d, side):
    x = d[(d.date >= '2025-10-01') & d.sp.notna()].copy(); x['s'] = side.loc[x.index]; x['pl'] = x.s * x.sp
    out = {}
    for s in list(SEG) + ['ALL']:
        y = x if s == 'ALL' else x[x.seg == s]; tr = y[y.s != 0]
        out[s] = dict(hours=len(tr), sells=int((tr.s > 0).sum()), buys=int((tr.s < 0).sum()), usd_mwh=round(tr.pl.mean(), 1) if len(tr) else 0,
                      total=round(tr.pl.sum()), H1=round(tr.pl[tr.date < '2026-02-15'].sum()), H2=round(tr.pl[tr.date >= '2026-02-15'].sum()),
                      last90=round(tr.pl[tr.date >= '2026-07-08'].sum()))
    return out

if __name__ == '__main__':
    Ns = [int(a) for a in sys.argv[2:]] or [30, 60, 90, 120]
    z = sys.argv[1]
    d = pd.read_csv(C.DATA / f'dv_frame_{z}.csv'); d = d[d.date <= '2026-10-06'].dropna(subset=['head']).reset_index(drop=True)
    d['sp'] = d.da - d.rt; d['seg'] = d.he.map(segof)
    live = pd.Series(np.where(d.v2 == 1, 1, np.where(d.buyband == -1, -1, 0)), index=d.index)
    rows = [dict(rule='LIVE model', seg=s, **v) for s, v in score(d, live).items()]
    for N in Ns:
        rows += [dict(rule=f'segment rule, last {N}d', seg=s, **v) for s, v in score(d, run(d, N)).items()]
    R = pd.DataFrame(rows); R.to_csv(C.DATA / f'segment_lookback_{z}_{"_".join(map(str, Ns))}.csv', index=False)
    print(z); print(R.to_string(index=False))
