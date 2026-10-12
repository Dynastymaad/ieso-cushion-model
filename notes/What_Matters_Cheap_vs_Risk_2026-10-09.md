# Which fundamentals matter: cheap hours vs "what could go wrong" (Oct 9 2026)
Scripts: model/what_matters.py (quintiles, adjusted for hour of day), model/cheap_risk_test.py. East, Sep 2025 - Oct 2026.

## Raise spike odds AND RT beats DA (not priced) -> emphasise
| Sign | Spike odds top vs bottom fifth | RT-DA top vs bottom fifth |
|---|---|---|
| Wind falling over 3 h (IESO) | 1.44x vs 0.85x | +9.0 vs -2.4 |
| Tesla - IESO | 1.35x vs 0.60x | +5.7 vs -7.5 |
| Gas need ramp 3 h | 1.19x vs 0.74x | +2.6 vs -3.0 |
| Wind models spread | | +3.5 vs -2.5 |
Both halves same sign.

## Raise spike odds but DA over-prices them -> these favour SELLS, not longs
Tight headroom / low gas spare / high CAHR / high DA fc / DA fc above its usual level / spikes in the last 2-4 days
(e.g. headroom bottom fifth: spike odds 1.34x but RT-DA -14.2; recent spikes: 1.43x but -6.4).

## Little information
Gas outage level, hydro, net exports, solar change, last-7-day RT-DA, IESO wind minus models' low.

## Cheap vs risk (long, non-sell hours, DA fc + $30)
| | Hours | $/MWh | Total/MW | last 120 | w/o best 3 | placebo |
|---|---|---|---|---|---|---|
| Headroom band 9.5-11.5k | 1,317 | +1.8 | +2.4k | +2.7k | +0.1k | 0% |
| Cheap (DA fc < 30d median) | 1,951 | +4.5 | +8.9k | +2.2k | +4.8k | 0% |
| Any risk sign (Tesla+150 / wind -200 / gas +500) | 1,937 | +8.4 | +16.3k | +2.7k | +11.8k | 100% |
| Risk sign, NOT cheap | 1,003 | +10.7 | +10.7k | +1.4k | +6.2k | 100% |
Cheapness adds nothing once a risk sign is present. Risk add-on on top of current longs (buy band + Spike Watch): +4.5k/MW East, +4.0k Ottawa,
positive in every window (Ottawa last 60 days -24). Wind falling 200+ is the strongest single add-on (+$11/MWh).

## Done
Fundamentals tab: "What could go wrong" column (the three signs) and "vs usual" (DA fc minus its 30-day median). Display only; scoring unchanged per Maad.
