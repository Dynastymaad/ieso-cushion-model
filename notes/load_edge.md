# Load forecasts at the DA bid deadline (D-1 08:00 MT)

Sample 2025-05-03 → 2026-11-13. Actual = IESO Ontario Demand. `lf_adq2` = the demand forecast in IESO Adequacy2 issued D-1 before 09:00 EST — the number the DA clears on.

## All available hours per source

        source  hours   MAE  bias(fc-act)
       lf_adq2  13417 414.0         225.0
    lf_dynasty  10154 367.0         -16.0
 lf_dynasty ml     43 313.0         250.0
       lf_ieso  13187 454.0         195.0
lf_meteologica   1632 230.0          78.0
      lf_tesla  13416 353.0         -19.0

## Common sample (hours where IESO, Adequacy2 and Tesla all exist)

  source  hours   MAE  bias
 lf_adq2  13186 416.0 228.0
 lf_ieso  13186 454.0 195.0
lf_tesla  13186 353.0 -18.0

## Monthly MAE, common sample

         lf_adq2  lf_ieso  lf_tesla
month                              
2025-05    284.0    671.0     217.0
2025-06    497.0    551.0     404.0
2025-07    680.0    771.0     442.0
2025-08    565.0    721.0     337.0
2025-09    367.0    422.0     266.0
2025-10    298.0    303.0     256.0
2025-11    278.0    292.0     474.0
2025-12    386.0    363.0     313.0
2026-01    412.0    417.0     354.0
2026-02    314.0    309.0     328.0
2026-03    403.0    402.0     438.0
2026-04    411.0    364.0     410.0
2026-05    360.0    371.0     321.0
2026-06    372.0    376.0     295.0
2026-07    790.0    762.0     495.0
2026-08    471.0    523.0     357.0
2026-09    347.0    334.0     371.0
2026-10    274.0    268.0     267.0
2026-11    241.0    241.0     336.0

## The edge: does a vendor disagreeing with IESO predict IESO's miss?

        source  hours  corr(src-IESO, act-IESO)  sign hit when |gap|>300  n |gap|>300  slope
    lf_dynasty  10154                     0.503                    0.788         4552  0.639
       lf_ieso  13187                     0.101                    0.600         2803  0.138
lf_meteologica   1632                     0.623                    0.882          431  0.763
      lf_tesla  13416                     0.585                    0.809         7252  0.649

## Bias-corrected / blended (trailing 28-day bias per HE, lagged 2 days)

       source  hours   MAE  bias
  lf_tesla_bc  13152 356.0  -1.0
lf_dynasty_bc   9587 355.0  -6.0
   lf_ieso_bc  12923 427.0 -23.0
   lf_tes_dyn  10154 337.0 -18.0