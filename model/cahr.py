"""cahr.py -- carbon-adjusted implied heat rate (MMBtu/MWh), known at the bid.

  Price  = HR x Gas + (HR x EF - Benchmark) x CarbonPrice
  HR     = (Price + Benchmark x CarbonPrice) / (Gas + EF x CarbonPrice)

  Price        our DA forecast, CAD/MWh
  Gas          Dawn (ICE CVX, USD/MMBtu) x USD/CAD -> CAD/MMBtu; last settle for strip D struck on or before D-2
  EF           0.0554 tCO2e/MMBtu (desk number)
  Benchmark    0.310 tCO2e/MWh, Ontario EPS natural-gas generation standard (IESO APO Carbon Pricing Module, 2024)
  CarbonPrice  Ontario EPS excess-emissions price, follows the federal benchmark: $80 2024, $95 2025, $110 2026 (CAD/t)
Reading it: an efficient combined cycle runs ~6.5-7.5, older CCGT/cogen ~8-9, peakers ~10-12. A DA forecast that
implies a heat rate well above the marginal unit's means DA carries a scarcity premium."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import numpy as np, pandas as pd, common as C, blocks as B

EF, BENCH = 0.0554, 0.310
A_GRADE = 12.0      # tight sells at or above: priced to clear (offers capped at 0.9 x RT fc); below: offers +$10 (cahr_ladder.py)
B_UP, A_CAP = 10, 0.9
CPRICE = {2024: 80.0, 2025: 95.0, 2026: 110.0, 2027: 125.0}

def cprice(D): return CPRICE.get(pd.Timestamp(D).year, 110.0)

def gas_table(dates):
    """{date: (dawn_usd, fx, gas_cad)} with only what was known at D-2."""
    c = B.fwd_asof(B.settles(), 'CVX', 'Dawn Ontario')
    fx = pd.read_csv(C.CACHE / 'fx_usdcad.csv', parse_dates=['Date']).sort_values('Date')
    out = {}
    for D in dates:
        Dt = pd.Timestamp(D); g = B.asof(c, Dt, Dt - pd.Timedelta(days=1))
        f = fx[fx.Date <= Dt - pd.Timedelta(days=2)].Rate
        r = float(f.iloc[-1]) if len(f) else np.nan
        out[D] = (g, r, g * r if pd.notna(g) else np.nan)
    return out

def hr(price, gas_cad, cp):
    return (price + BENCH * cp) / (gas_cad + EF * cp)

def add(e, price_col='p_da'):
    """adds dawn, fx, gas_cad, cp, cahr columns to a frame with date + price_col."""
    t = gas_table(sorted(e.date.unique()))
    e = e.copy(); e['dawn'] = e.date.map(lambda d: t[d][0]); e['fx'] = e.date.map(lambda d: t[d][1]); e['gas_cad'] = e.date.map(lambda d: t[d][2])
    e['cp'] = e.date.map(cprice); e['cahr'] = hr(e[price_col], e.gas_cad, e.cp)
    return e
