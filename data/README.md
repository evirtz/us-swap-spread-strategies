# Input data

`raw/` contains the two supplied workbooks. The backtest reads their SOFR sheets as data, leaves the files unchanged and records their SHA256 hashes. `manifest.json` identifies the exact workbook copies used for this repository.

| Workbook | Data used |
| --- | --- |
| US_Daily_Raw_Final_Models_With Libor.xlsx | Original 10Y/30Y swap spreads, MOVE, GBP/EUR 2Y/5Y basis |
| Rates_Swaps_Daily - With Libor.xlsx | SOFRRATE and Treasury/IRS quotes at 7Y, 10Y, 20Y and 30Y |

The first workbook's required column names are `10yr swap spreads`, `30yr swap spreads`, `Move`, `2yr_Basis_GBP_SOFR`, `5yr_Basis_GBP_SOFR`, `2yr_Basis_EU_SOFR` and `5yr_Basis_EU_SOFR`.

The rates reader requires `SOFRRATE`, `UST_7yrs`, `UST_10yrs`, `UST_20yrs`, `UST_30yrs` and the corresponding `IRS_*yrs_SOFR` columns. Both sheets use `Date` as their first column. The reader rejects duplicate dates and missing or duplicate required headers.

Spread and basis observations are in basis points. MOVE is in index points. Rates are quoted as percentages in the workbooks. Missing predictor values remain missing; the code does not interpolate them.

The regression observations span 19 February 2021 to 3 September 2026. Rates may have a wider history. Additional workbook sheets and columns are preserved but are not inputs to this SOFR backtest.

The statistical study uses its preserved `research/data/observations.csv` snapshot. Its historical source workbook has a different file hash from the current workbook copy. The repository checks the selected 10Y observations separately so a formatting or workbook-version change is not mistaken for a change in the statistical sample.
