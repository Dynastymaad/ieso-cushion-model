"""update_intertie_actual.py -- Oct 28 2026. Keeps data/intertie_actual.csv current from the archived IESO
IntertieScheduleFlowYear reports (it had stopped at Sep 25, which left gas_hat blank in dv_frame from Sep 28).
Columns: ny_flow, ny_exp, ny_imp (New York) and tot_flow (Total Flow). Archive rows replace/extend the file."""
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import pandas as pd, common as C

def main():
    rows = []
    for f in sorted((C.ARCH / 'IntertieScheduleFlowYear').glob('*.csv')):
        x = pd.read_csv(f, skiprows=4, header=None); x = x[pd.to_numeric(x[1], errors='coerce').notna()]
        rows.append(pd.DataFrame({'date': pd.to_datetime(x[0]).dt.strftime('%Y-%m-%d'), 'he': x[1].astype(int),
                                  'ny_flow': x[16].astype(float), 'ny_exp': x[15].astype(float), 'ny_imp': x[14].astype(float), 'tot_flow': x[46].astype(float)}))
    new = pd.concat(rows).drop_duplicates(['date', 'he'], keep='last')
    p = C.DATA / 'intertie_actual.csv'; old = pd.read_csv(p)
    out = pd.concat([old[~old.set_index(['date', 'he']).index.isin(new.set_index(['date', 'he']).index)], new]).sort_values(['date', 'he'])
    out.to_csv(p, index=False); print('intertie_actual ->', out.date.max(), len(out), 'rows')

if __name__ == '__main__':
    main()
