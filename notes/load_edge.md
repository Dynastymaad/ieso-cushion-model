# Load forecasts at the DA bid deadline (D-1 08:00 MT)

Sample 2025-05-03 → 2026-10-21. Actual = IESO Ontario Demand. `lf_adq2` = the demand forecast in IESO Adequacy2 issued D-1 before 09:00 EST — the number the DA clears on.

## All available hours per source

        source  hours   MAE  bias(fc-act)
       lf_adq2  12865 421.0         231.0
    lf_dynasty   9650 368.0         -16.0
       lf_ieso  12635 463.0         201.0
lf_meteologica   1081 244.0          77.0
      lf_tesla  12864 355.0         -18.0

## Common sample (hours where IESO, Adequacy2 and Tesla all exist)

  source  hours   MAE  bias
 lf_adq2  12634 423.0 236.0
 lf_ieso  12634 463.0 201.0
lf_tesla  12634 356.0 -16.0

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
2026-10    289.0    280.0     277.0

## The edge: does a vendor disagreeing with IESO predict IESO's miss?

        source  hours  corr(src-IESO, act-IESO)  sign hit when |gap|>300  n |gap|>300  slope
    lf_dynasty   9650                     0.509                    0.793         4373  0.660
       lf_ieso  12635                     0.100                    0.599         2790  0.137
lf_meteologica   1081                     0.620                    0.868          340  0.740
      lf_tesla  12864                     0.587                    0.812         7015  0.655

## Bias-corrected / blended (trailing 28-day bias per HE, lagged 2 days)

       source  hours   MAE  bias
  lf_tesla_bc  12600 360.0  -0.0
lf_dynasty_bc   9083 358.0  -6.0
   lf_ieso_bc  12371 435.0 -22.0
   lf_tes_dyn   9650 340.0 -17.0