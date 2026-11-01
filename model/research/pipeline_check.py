"""research/pipeline_check.py -- Oct 31 2026: newest date in every file the morning pipeline reads, and who writes it."""
import glob, os, re, json, time
import pandas as pd
FILES = ['cache/fwd_daily_ontario.csv', 'cache/fx_usdcad.csv', 'cache/ieso_adq2_final.csv', 'cache/ieso_adq2_leads.csv', 'cache/ieso_adq2_leads34.csv', 'cache/ieso_adq2_outage_timeline.csv',
 'cache/ieso_adq2_preDA.csv', 'cache/ieso_adq2x_final.csv', 'cache/ieso_load_actual.csv', 'cache/ieso_load_fc.csv', 'cache/ieso_wind_fc.csv', 'cache/cyyz_weather_actual.csv',
 'data/acc_blocks.csv', 'data/acc_horizon_hourly.csv', 'data/adq3_final.csv', 'data/after_bid_EAST.csv', 'data/blocks_features.csv', 'data/bt_blocks.csv', 'data/bt_exports_fc.csv',
 'data/bt_hydro_fc.csv', 'data/bt_trading_rules.csv', 'data/da_cleared_ties.csv', 'data/dv_frame_EAST.csv', 'data/dynasty_trades_scored.csv', 'data/es_drivers.csv', 'data/es_gasband.csv',
 'data/fund_read_track.csv', 'data/fwd35.csv', 'data/gas_ladder.csv', 'data/ieso_preda_intertie_limits.csv', 'data/intertie_actual.csv', 'data/load_at_bid.csv',
 'data/nrg/da_intertie_limits.csv', 'data/nrg/da_intertie_limits_pq.csv', 'data/nrg/hub_prices_nrg.csv', 'data/nrg/on_zones_nrg.csv.gz', 'data/nrg/rt_intertie_limits.csv',
 'data/nyiso_dam_energy.csv', 'data/nyiso_zoneA_da.csv', 'data/outage_features.csv', 'data/prices_hourly.csv', 'data/qc_flows.csv', 'data/rt_patch.csv', 'data/shock_predict_EAST.csv',
 'data/spike_checklist_EAST.csv', 'data/spike_events_EAST.csv', 'data/wind_at_bid.csv', 'data/outlook/ro_weekly.csv', 'data/outlook/ro_vs_actual.csv', 'cache/market_virtuals.csv', 'cache/dynasty_virtuals.csv']
CANDS = ['date', 'Date', 'EffectiveDateTime', 'EffectiveDate', 'ts_ept_begin', 'DeliveryDate', 'week', 'day']
rows = []
for f in FILES:
    if not os.path.exists(f): rows.append((f, 'MISSING', '', '')); continue
    mt = time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(f)))
    try:
        h = pd.read_csv(f, nrows=0).columns; c = next((c for c in CANDS if c in h), None)
        mx = str(pd.read_csv(f, usecols=[c])[c].astype(str).str[:10].max()) if c else '(no date col)'
    except Exception as ex: mx = f'ERR {str(ex)[:40]}'; c = ''
    rows.append((f, mx, c or '', mt))
for f in ['data/wx/openmeteo_view.json', 'data/qc_adq2x.json', 'data/quebec2.json', 'data/zone_bt17.json', 'data/outage_priced.json']:
    rows.append((f, '(json)', '', time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(f))) if os.path.exists(f) else 'MISSING'))
for a in ['Adequacy3', 'Demand', 'GenOutputCapability', 'GenOutputbyFuelHourly', 'IntertieScheduleFlowYear', 'DASecurityConstraints2', 'RealtimeZonalEnergyPrices', 'DAHourlyZonal', 'PreDAIntertieSchedLimits', 'TxLimitsOutage0to2Days', 'TxOutagesTodayAll']:
    z = sorted(glob.glob(f'archive/{a}/*'))
    rows.append((f'archive/{a}', time.strftime('%Y-%m-%d %H:%M', time.localtime(max(os.path.getmtime(x) for x in z))) if z else 'EMPTY', 'last write', ''))
print(pd.DataFrame(rows, columns=['file', 'newest_date', 'col', 'file_written']).to_string(index=False))
