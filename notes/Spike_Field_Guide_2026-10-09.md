# Spike field guide: what causes RT spikes, and the warning signs (East, Sep 2025 – Oct 6 2026)

Scripts (TEST / UNDERSTANDING ONLY): `model/spike_anatomy.py`. Data: `data/spike_events_EAST.csv`, `data/spike_checklist_EAST.csv`.

## How often
- A spike here = RT ≥ DA + $50. There were 721 hours on 229 days: 7.5% of all hours.

| Segment | Spike rate |
|---|---|
| Overnight | 3% |
| Morning | 7.5% |
| Midday | 8% |
| **Evening** | **11%** |
| Late | 8% |

| Month | Spike rate |
|---|---|
| Dec | 15% |
| Jan | 11% |
| Feb | 16% |
| Sep | 2–4% |
| Apr, Jul | 4% |

## What caused them (the largest surprise after the bid)
| Cause | Share of spikes | Can you see it at the bid? |
|---|---|---|
| **Outages IESO added after the bid** (trips, derates) | **51%** | No |
| **Wind came in short** of forecast | 22% | Partly: windy forecasts that fall into the hour |
| **Load came in above IESO** | 16% | Partly: Tesla or Dynasty above IESO |
| No surprise over 250 MW (ramp or dusk alone) | 11% | Partly: sunset hour, steep ramp |
| Intertie changes | under 1% | — |

The total surprise in spike hours is about 1,040 MW, against about 480 in normal hours. **Half of all spikes come from unit trips you cannot see coming.** That is the irreducible risk of being short.

## Evening risk checklist (HE16–21; base spike rate 11.1%)
"Mean RT−DA" is what the hour paid a long. + = longs paid on average; − = DA already over-priced it.

| Warning sign | Spike rate | × base | Mean RT−DA | H1 / H2 rate | Last 120 days |
|---|---|---|---|---|---|
| Windy (≥ 1,500) **and** wind falling 300+ into the hour | **19.4%** | 1.75 | **+$16.8** | 18 / 20% | 9% |
| Tesla > IESO **and** sunset hour (or the one after) | 18.4% | 1.67 | +$7.4 | 26 / 11% | 12% |
| Wind falling 300+ into the hour | 17.4% | 1.58 | +$12.4 | 21 / 16% | 13% |
| CAHR ≥ 12 | 15.4% | 1.39 | −$12.4 | 18 / 11% | 11% |
| Sunset hour or the one after | 15.2% | 1.37 | −$1.1 | 20 / 11% | 8% |
| Spare gas < 1,000 | 14.8% | 1.34 | −$28.6 | 17 / 11% | 10% |
| Dynasty > IESO | 14.7% | 1.33 | +$5.6 | 19 / 11% | 8% |
| Tesla 200+ > IESO | 14.4% | 1.30 | +$6.4 | 20 / 9% | 10% |
| Headroom < 6,000 | 14.2% | 1.28 | −$21.3 | 16 / 10% | 10% |
| **Calm (wind < 600)** | **6.3%** | **0.57** | −$15.9 | 5 / 7% | 7% |
| Gas outages high (known at the bid) | 9.3% | 0.84 | −$7.9 | 14 / 6% | 6% |

### How to read the checklist
1. **Signs that raise spike risk *and* paid longs on average** are the ones that matter for "don't be short": wind falling into a windy evening, Tesla or Dynasty above IESO, the sunset hour. They are about the *after-bid surprise*.
2. **Signs that raise spike risk but DA already over-prices** (CAHR ≥ 12, spare < 1,000, headroom < 6,000) still favour the sell on average. More spikes, but DA charges more than enough.
3. **Calm evenings are the safest sells.** The spike rate is about half the base.
4. **Scheduled outages that are already known lower the risk** (priced in). Outages *added after the bid* are the danger.
5. **Weakness:** most signs were stronger in H1 (winter) than in H2 or the last 120 days. The patterns hold in direction but not in size.

## Size and season checks (10 MW base, Jul 2025 – Oct 8 2026, price-taker)
| | East total | H1 / H2 | Since Sep 24 | Worst 5 days | Ottawa total |
|---|---|---|---|---|---|
| Live | 554k | 341k / 213k | −1.5k | −102k | 485k |
| Evening sells at 3 MW | 429k | | +1.7k | −71k | 385k |
| Evening sells at 5 MW | 465k | | +0.8k | −73k | 413k |
| **No evening sells in shoulder months** (Mar–Jun, Oct–Dec) | **579k** | 340k / 239k | **+5.0k** | −92k | **533k** |

**Caveat:** the shoulder months were picked by looking at this same year, so this is in-sample. Each season has been seen once. Re-check next spring before trusting it.
