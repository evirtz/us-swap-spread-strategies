# Historical statistical verification

The original full study was tested with Python 3.12.14 and the pinned libraries. Every test group was rerun on the observed data and compared with the recorded results. All twenty result-file comparisons passed, covering 13,045 records. The repository's current checks are recorded separately in `docs/reproduction.md`.

The original raw workbook was also read directly in a separate check; its observations and all 24 endpoint regressions matched. Original source files were not modified.

The original validation checked that fifteen statistical functions retained the same syntax tree. The runner also supplies portable file handling, endpoint regression exports, currency-specific Holm corrections and the conversion of standardized FMOLS coefficients back to basis-point units.

Validation was performed in stages. The full stability computation first exposed the omitted reporting-unit conversion; that conversion was included and verified before final packaging. This affected the displayed beta units, not the underlying stability test statistics.

| Saved output | Records | Match |
| --- | --- | --- |
| bounds | 16 | Yes |
| bounds_fixed_lags | 16 | Yes |
| bounds_sensitivity | 16 | Yes |
| cointegration | 192 | Yes |
| currency_corrections | 72 | Yes |
| ecm_adjustment | 48 | Yes |
| endpoint_dols_stability | 36 | Yes |
| gregory_hansen | 16 | Yes |
| integration | 366 | Yes |
| johansen_models | 176 | Yes |
| johansen_statistics | 880 | Yes |
| long_run_estimators | 128 | Yes |
| prospective | 576 | Yes |
| refit_crossings | 12 | Yes |
| regression_coefficients | 72 | Yes |
| regression_models | 24 | Yes |
| rolling | 10371 | Yes |
| rolling_checks | metadata | Yes |
| rolling_summary | 12 | Yes |
| stability | 16 | Yes |
