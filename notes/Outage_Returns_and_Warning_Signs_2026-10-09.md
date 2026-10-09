# Outage returns + evening warning signs (Oct 9 2026)

## Outage returns (Outages tab, new section; display only)
Return day = 300+ MW gas scheduled back HE12-21 (IESO Adequacy at the bid). East HE16-21, Sep 2025 - Oct 2026:
| | Days | RT-DA | Days with a spike | Return slipped (200+ MW re-added) |
|---|---|---|---|---|
| Return days | 46 | -12.3 | 24% | 52% |
| Other days | 345 | -1.7 | 37% | 47% |
- Fewer spike days on return days in both halves (H1 25% vs 50%, H2 23% vs 30%).
- Slipped returns: no worse (-12.5 vs -12.0).
- Average RT-DA flips between halves (H1 -33, H2 +11) -> not a signal. Context only. Script: model/outage_returns.py.

## Warning signs (warn_validate.py) -> nothing new wired
- Wind falling 300+ into evening: pays (+$27/MWh, 190 h) but 145 of those hours are already Spike Watch hours.
- Add-on outside Spike Watch (45 h): last 120 days -113, w/o best 3 days -173. Not robust.
- Tesla>IESO + sunset, Tesla/Dynasty 200+: longs fail robustness.
- Skipping the model's sells in flagged hours loses money (those sells still made +$3 to +$8/MWh).
