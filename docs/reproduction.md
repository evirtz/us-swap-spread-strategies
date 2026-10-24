# Reproduction and checks

The repository was checked on 24 October 2026 with Python 3.12.14. The trading run used numpy 2.3.5, pandas 3.0.1 and openpyxl 3.1.5. The statistical checks used the separately pinned versions in `research/requirements.txt`.

## Trading backtest

The code was run from the two raw workbooks with no saved trade, daily P&L or monthly files supplied to the calculation. It rebuilt 24 strategies, 323 trades and 20,760 daily strategy marks. Each cost case contains 96 accounts and 5,376 monthly grid rows.

Saved results were used afterwards for comparisons. The verification checked 72 first/middle/final regression fits, every trade's next-close execution, all four carry legs for all 323 trades, six missing-predictor cases and daily/trade capital reconciliation. It compared 90,336 saved fields for gross results and 101,184 for cost-adjusted results. All matched the repository's saved tables exactly; the independent carry check differed by at most 7.82e-14 bp.

The saved tables come from the previously verified raw-data rebuild. That earlier rebuild matched the historical monthly-result package within 8.0e-15 in decimal return units and 8.3e-13 in capital units. Exact agreement with the repository copies and rounded agreement with the historical package are separate comparisons.

## Input and boundary checks

The input verifier confirmed both workbook hashes and exact agreement between the selected raw 10-year observations and the preserved 1,353-row statistical snapshot. Six unit tests passed. They cover duplicate source dates, missing or duplicate headers, preserved missing predictors, weekend SOFR accrual, a zero-day holding period and rejection of optimized execution that disables assertions.

Run them from the repository root:

```bash
python scripts/verify_inputs.py
python -m unittest discover -s tests -v
```

The main backtest and verification entry points reject Python's `-O` option, which would disable reconciliation assertions.

## Statistical work

Integration/cointegration, endpoint regressions and Johansen groups were rerun from the packaged snapshot and matched their historical references. The statistical workbook reader was also checked against the current raw workbook using named columns.

The exhaustive adjustment and stability groups were not rerun during repository preparation. Their original full-suite checks are preserved under `research/VERIFICATION.json`. All statistical calculation functions remain unchanged; repository changes are confined to input handling, comparison-file checks and execution guards.

## Review limits

These checks test reproduction and selected financial/data contracts. They do not establish a stable economic relationship, realistic market capacity or live profitability. Carry, rolldown and instrument DV01 retain the original approximations. Swap-margin funding and constraints are excluded.

The code review covered the maintained trading modules, verifier, tests, research entry point and its changes. The unchanged statistical routines were checked for preservation and reviewed through their methods, saved results and prior validation. The internal source of third-party libraries was not audited.
