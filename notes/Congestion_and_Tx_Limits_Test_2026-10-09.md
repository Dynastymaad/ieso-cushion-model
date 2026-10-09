# Can bid-time data flag West congestion / spike days? (Oct 9 2026)
Script: model/tx_limits_test.py. Data: RT congestion by zone Jun 27 - Oct 8 2026 (data/rt_components.csv), IESO TxLimitsOutage0to2Days versions before D-1 09:00.

- When West/Southwest/Niagara is bottled (congestion < -$10), East RT-DA averages +$17 to +$26 in those hours. 20 days since late June (clusters Aug 5-22, Oct 4-8).
- NY export limit cut (<= 1,400 MW) at the bid: 33 days, bottled on 21% vs 19% normal; East RT-DA -3.9 vs -4.0. No signal.
- Michigan / FETT / Flow South limits: too few days to test.
- Persistence: bottled on D-2 -> bottled on D 42% vs 14%, but East RT-DA midday -15.8 vs -4.1 (DA prices it). Not tradable.
- Conclusion: nothing public at the bid flags these days. Spikes come from after-bid surprises (outages added after the bid ~51%, load miss, wind miss, intertie changes) and, on Oct 8, ramp timing inside the hour.
